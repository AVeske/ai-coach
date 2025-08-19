# backend/python/pose_extractor.py
from __future__ import annotations
import os
import csv
import cv2
import time
import numpy as np
from typing import Dict, Any, List, Tuple, Optional

# Prefer tflite-runtime (smaller), fall back to TF Lite if present

from tensorflow.lite.python.interpreter import Interpreter  # type: ignore

# ---------- MoveNet Thunder model ----------
# Download once and place it here (or anywhere and point MOVENET_PATH to it)
# e.g. https://tfhub.dev/google/movenet/singlepose/thunder/4?lite-format=tflite
MOVENET_PATH = os.path.join(os.path.dirname(__file__), "models", "movenet_thunder.tflite")

# MoveNet returns 17 keypoints in this fixed order:
MOVENET_KEYPOINTS = [
    "nose",
    "left_eye",
    "right_eye",
    "left_ear",
    "right_ear",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
]

# You asked to drop these 5 face/ear points:
EXCLUDE = {"nose", "left_eye", "right_eye", "left_ear", "right_ear"}

# MoveNet Thunder expects 256x256 RGB
INPUT_SIZE = 256


def _load_interpreter() -> Interpreter:
    if not os.path.exists(MOVENET_PATH):
        raise FileNotFoundError(
            f"MoveNet TFLite not found at {MOVENET_PATH}.\n"
            "Download movenet_thunder.tflite and place it under backend/python/models/"
        )
    interpreter = Interpreter(model_path=MOVENET_PATH, num_threads=max(1, os.cpu_count() or 1))
    interpreter.allocate_tensors()
    return interpreter


def _preprocess_frame(bgr: np.ndarray) -> np.ndarray:
    # BGR -> RGB, center-crop square, resize to 256, return uint8 with batch axis
    h, w = bgr.shape[:2]
    if h != w:
        side = min(h, w); y0 = (h - side) // 2; x0 = (w - side) // 2
        bgr = bgr[y0:y0+side, x0:x0+side]
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    rgb = cv2.resize(rgb, (INPUT_SIZE, INPUT_SIZE), interpolation=cv2.INTER_LINEAR)
    return rgb[np.newaxis, ...]  # (1,256,256,3) uint8


def _infer_keypoints(interpreter: Interpreter, frame_bgr: np.ndarray) -> List[Tuple[float, float, float]]:
    """
    Run MoveNet on one frame and return a list of 17 (x, y, score) with coords normalized to 0..1.
    This is the helper you were asking about — it *actually* performs the TFLite inference.
    """
    inp = _preprocess_frame(frame_bgr)

    # Set input tensor
    input_details = interpreter.get_input_details()
    dtype = input_details[0]["dtype"]
    if dtype == np.float32:
        inp = inp.astype(np.float32) / 255.0         # for older float models
    elif dtype == np.uint8:
        inp = inp.astype(np.uint8)                   # v4 quantized expects uint8
    else:
        raise TypeError(f"Unsupported input dtype: {dtype}")
    
    interpreter.set_tensor(input_details[0]["index"], inp)
    output_details = interpreter.get_output_details()
    interpreter.set_tensor(input_details[0]["index"], inp)

    # Run inference
    interpreter.invoke()

    # Output shape for MoveNet single pose: (1,1,17,3): y, x, score
    out = interpreter.get_tensor(output_details[0]["index"])  # type: ignore
    # Defensive checks
    if out.ndim != 4 or out.shape[2] != 17 or out.shape[3] != 3:
        # Unexpected; return zeros
        return [(0.0, 0.0, 0.0)] * 17

    kp = out[0, 0, :, :]  # (17,3)
    # Convert (y,x,score) -> (x,y,score) and clamp to [0,1]
    res: List[Tuple[float, float, float]] = []
    for i in range(17):
        y, x, s = float(kp[i, 0]), float(kp[i, 1]), float(kp[i, 2])
        res.append((
            float(np.clip(x, 0.0, 1.0)),
            float(np.clip(y, 0.0, 1.0)),
            float(np.clip(s, 0.0, 1.0)),
        ))
    return res


def _sample_stride(in_fps: float, sample_fps: float) -> int:
    if in_fps <= 0:
        return 2  # assume ~30 -> ~15fps
    return max(1, int(round(in_fps / max(1e-6, sample_fps))))


def _write_csv(csv_path: str, samples: List[Dict[str, Any]]) -> None:
    """
    Optional debugging: write one row per frame with selected joints.
    """
    joints = [
        "left_shoulder", "right_shoulder",
        "left_elbow", "right_elbow",
        "left_wrist", "right_wrist",
        "left_hip", "right_hip",
        "left_knee", "right_knee",
        "left_ankle", "right_ankle",
    ]
    headers = ["t"] + [f"{j}_{c}" for j in joints for c in ("x", "y", "conf")]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        for s in samples:
            row = [s.get("t", 0.0)]
            lm: Dict[str, List[float]] = s.get("landmarks", {})
            for j in joints:
                v = lm.get(j, [None, None, None])
                row.extend([v[0], v[1], v[2]])
            w.writerow(row)


def extract_pose_from_video(
    video_path: str,
    sample_fps: float = 15.0,
    max_samples: int = 600,
) -> Dict[str, Any]:
    """
    Server-side MoveNet Thunder extractor.
      • Reads the video with OpenCV.
      • Samples frames to ~sample_fps (e.g., 15–20).
      • Runs TFLite MoveNet on each kept frame via _infer_keypoints().
      • Maps indices -> names, drops face/ear points, returns a compact JSON.
      • Optionally writes a CSV next to the input (for debugging).

    Returns:
      {
        "ok": True/False,
        "fps": <effective sampling fps>,
        "frames": <total frames read>,
        "samples": [
           { "t": seconds, "landmarks": { "left_shoulder": [x,y,conf], ... } },
           ...
        ],
        "dbg": {...}  # optional timing, counts, etc.
      }
    """
    if not os.path.exists(video_path):
        return {"ok": False, "error": "file_not_found", "samples": []}

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return {"ok": False, "error": "cannot_open_video", "samples": []}

    in_fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0) or 30.0
    stride = _sample_stride(in_fps, sample_fps)
    out_fps = in_fps / max(1, stride)

    interpreter = _load_interpreter()

    total_frames = 0
    kept = 0
    samples: List[Dict[str, Any]] = []
    t0 = time.time()

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            total_frames += 1

            # keep every 'stride' frame
            if (total_frames - 1) % stride != 0:
                continue

            kps = _infer_keypoints(interpreter, frame)  # <-- WIRE-IN HAPPENS HERE

            # map to dict and drop undesired points
            lm_dict: Dict[str, List[float]] = {}
            for idx, name in enumerate(MOVENET_KEYPOINTS):
                if name in EXCLUDE:
                    continue
                x, y, c = kps[idx]
                lm_dict[name] = [x, y, c]

            t_sec = kept / max(1.0, out_fps)
            samples.append({"t": float(t_sec), "landmarks": lm_dict})

            kept += 1
            if kept >= max_samples:
                break
    finally:
        cap.release()

    # Optional CSV export for debugging (saved next to the video)
    try:
        base, _ = os.path.splitext(video_path)
        _write_csv(base + "_pose.csv", samples)
    except Exception:
        pass  # never crash analysis because CSV failed

    return {
        "ok": True,
        "fps": float(out_fps),
        "frames": int(total_frames),
        "samples": samples,
        "dbg": {
            "input_fps": in_fps,
            "stride": stride,
            "kept": kept,
            "duration_s": time.time() - t0,
        },
    }