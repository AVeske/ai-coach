# backend/python/testing/proov.py
# Extract trimmed frames (rotated 90° CW), save as images AND CSV of keypoints.

from __future__ import annotations
import os
import sys
import time
import csv
import cv2
import numpy as np
from typing import Dict, Any, List, Tuple, Optional

# ────────────── Resolve imports ──────────────
_THIS = os.path.abspath(__file__)
_TESTING_DIR = os.path.dirname(_THIS)
_BACKEND_PY_DIR = os.path.dirname(_TESTING_DIR)
if _BACKEND_PY_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_PY_DIR)

from pose_extractor import INPUT_SIZE, _load_interpreter, _infer_keypoints, MOVENET_KEYPOINTS, EXCLUDE
from analysis.trim import trim_active_window


def ensure_dir(p: str) -> None:
    os.makedirs(p, exist_ok=True)


def preprocess_like_model(bgr: np.ndarray, out_size: int = INPUT_SIZE) -> np.ndarray:
    h, w = bgr.shape[:2]
    if h != w:
        side = min(h, w)
        y0 = (h - side) // 2
        x0 = (w - side) // 2
        bgr = bgr[y0:y0+side, x0:x0+side]
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    rgb = cv2.resize(rgb, (out_size, out_size), interpolation=cv2.INTER_LINEAR)
    return rgb


def fname_for_time(t: float, idx: int) -> str:
    return f"{idx:06d}_{t:09.3f}s.png"


def save_trimmed_frames_and_csv(
    video_path: str = "pushups.mp4",
    out_dir: str = "images",
    sample_fps: float = 15.0,
    rotate_cw_90: bool = True,
) -> dict:
    t0 = time.perf_counter()
    base = os.path.dirname(os.path.abspath(__file__))
    video_path = os.path.join(base, video_path)
    out_dir = os.path.join(base, out_dir)
    ensure_dir(out_dir)

    if not os.path.exists(video_path):
        raise FileNotFoundError(video_path)

    # Load interpreter once
    interpreter = _load_interpreter()

    # Open video
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open {video_path}")
    in_fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    stride = max(1, int(round(in_fps / sample_fps)))
    out_fps = in_fps / stride
    dt = 1.0 / max(1e-6, out_fps)

    # Pass 1: run raw extraction to know samples
    total_frames, kept, samples = 0, 0, []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        total_frames += 1
        if (total_frames - 1) % stride != 0:
            continue
        kps = _infer_keypoints(interpreter, frame)
        lm_dict: Dict[str, List[float]] = {}
        for idx, name in enumerate(MOVENET_KEYPOINTS):
            if name in EXCLUDE:
                continue
            x, y, c = kps[idx]
            lm_dict[name] = [x, y, c]
        samples.append({"t": kept / out_fps, "landmarks": lm_dict})
        kept += 1
    cap.release()

    # Trim
    samples_trim, lo_idx, hi_idx, trim_dbg = trim_active_window(samples, out_fps)
    head_sec = lo_idx / out_fps
    end_sec = hi_idx / out_fps

    # Pass 2: reopen for saving frames
    cap = cv2.VideoCapture(video_path)
    cap.set(cv2.CAP_PROP_POS_MSEC, head_sec * 1000.0)
    idx, written, next_t = 0, 0, head_sec

    csv_path = os.path.join(out_dir, "poses.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f_csv:
        w = csv.writer(f_csv)
        # header
        header = ["frame", "t"] + [f"{j}_{c}" for j in samples_trim[0]["landmarks"].keys() for c in ("x", "y", "conf")]
        w.writerow(header)

        while True:
            ok, frame = cap.read()
            if not ok:
                break
            t_now = float(cap.get(cv2.CAP_PROP_POS_MSEC)) / 1000.0
            if t_now > end_sec + 0.25:
                break

            while next_t <= end_sec + 1e-6 and t_now >= next_t:
                rgb = preprocess_like_model(frame)
                if rotate_cw_90:
                    rgb = cv2.rotate(rgb, cv2.ROTATE_90_CLOCKWISE)

                out_path = os.path.join(out_dir, fname_for_time(next_t, idx))
                cv2.imwrite(out_path, cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))

                lm = samples_trim[idx]["landmarks"]
                row = [idx, next_t]
                for j in samples_trim[0]["landmarks"].keys():
                    v = lm.get(j, [None, None, None])
                    row.extend(v)
                w.writerow(row)

                written += 1
                idx += 1
                next_t += dt

    cap.release()
    t1 = time.perf_counter()

    return {
        "ok": True,
        "video": video_path,
        "out_dir": out_dir,
        "effective_fps": out_fps,
        "frames_written": written,
        "csv": csv_path,
        "trim": {"head_sec": head_sec, "end_sec": end_sec, "debug": trim_dbg},
        "timers_s": {"total": t1 - t0},
    }


if __name__ == "__main__":
    video_arg = sys.argv[1] if len(sys.argv) > 1 else "pushups.mp4"
    out_arg = sys.argv[2] if len(sys.argv) > 2 else "images"
    dbg = save_trimmed_frames_and_csv(video_arg, out_arg)
    print("[DONE]", dbg)
