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


def _rotate_image(bgr: np.ndarray, rotate_deg: int) -> np.ndarray:
    """Rotate BGR image by given degrees. Fast path for multiples of 90."""
    deg = int(rotate_deg) % 360
    if deg == 0:
        return bgr
    if deg == 90:
        return cv2.rotate(bgr, cv2.ROTATE_90_CLOCKWISE)
    if deg == 180:
        return cv2.rotate(bgr, cv2.ROTATE_180)
    if deg == 270:
        return cv2.rotate(bgr, cv2.ROTATE_90_COUNTERCLOCKWISE)
    # Arbitrary angle: rotate about image center, keep same size (black corners may appear)
    h, w = bgr.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), -deg, 1.0)  # negative for clockwise
    return cv2.warpAffine(bgr, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)


def _center_crop_square(bgr: np.ndarray) -> np.ndarray:
    h, w = bgr.shape[:2]
    if h == w:
        return bgr
    side = min(h, w)
    y0 = (h - side) // 2
    x0 = (w - side) // 2
    return bgr[y0:y0 + side, x0:x0 + side]


def _preprocess_frame_from_bgr(bgr: np.ndarray) -> np.ndarray:
    """
    BGR -> RGB, resize to 256x256, return with batch axis for inference.
    Assumes the image is already rotated and square-cropped if desired.
    """
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    rgb = cv2.resize(rgb, (INPUT_SIZE, INPUT_SIZE), interpolation=cv2.INTER_LINEAR)
    return rgb[np.newaxis, ...]  # (1,256,256,3) uint8 or float depending on model I/O


def _infer_keypoints(interpreter: Interpreter, preprocessed_batch: np.ndarray) -> List[Tuple[float, float, float]]:
    """
    Run MoveNet on one preprocessed frame (with batch axis).
    Return a list of 17 (x, y, score) with coords normalized to [0,1].
    """
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()

    inp = preprocessed_batch
    dtype = input_details[0]["dtype"]
    if dtype == np.float32:
        inp = inp.astype(np.float32) / 255.0  # for float models
    elif dtype == np.uint8:
        inp = inp.astype(np.uint8)           # for quantized models
    else:
        raise TypeError(f"Unsupported input dtype: {dtype}")

    interpreter.set_tensor(input_details[0]["index"], inp)
    interpreter.invoke()

    # Output shape for MoveNet single pose: (1,1,17,3): y, x, score
    out = interpreter.get_tensor(output_details[0]["index"])  # type: ignore
    if out.ndim != 4 or out.shape[2] != 17 or out.shape[3] != 3:
        return [(0.0, 0.0, 0.0)] * 17

    kp = out[0, 0, :, :]  # (17, 3) in (y, x, score)
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
    *,
    rotate_deg: int = 0,            # <<< NEW: rotate frames before inference & CSV
    save_debug_png: bool = True,
) -> Dict[str, Any]:
    """
    Server-side MoveNet Thunder extractor.
      • Reads the video with OpenCV.
      • Optionally rotates each frame by rotate_deg (0, 90, 180, 270 fast path).
      • Center-crops to square, resizes to 256.
      • Samples frames to ~sample_fps.
      • Runs TFLite MoveNet on each kept frame.
      • Maps indices -> names, drops face/ear points.
      • Writes a CSV next to the input (post-rotation coordinates), for debugging.

    Returns:
      {
        "ok": True/False,
        "fps": <effective sampling fps>,
        "frames": <total frames read>,
        "samples": [
           { "t": seconds, "landmarks": { "left_shoulder": [x,y,conf], ... } },
           ...
        ],
        "dbg": {
          "input_fps": ...,
          "stride": ...,
          "kept": ...,
          "duration_s": ...,
          "rotate_deg": ...
        }
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

    debug_written = False
    debug_png_path = os.path.join(os.path.dirname(__file__), "debug_frame.png")

    try:
        while True:
            ok, frame_bgr = cap.read()
            if not ok:
                break
            total_frames += 1

            # keep every 'stride' frame
            if (total_frames - 1) % stride != 0:
                continue

            # 1) rotate (so model + CSV see upright orientation)
            frame_bgr = _rotate_image(frame_bgr, rotate_deg)

            # 2) center-crop square
            frame_bgr = _center_crop_square(frame_bgr)

            # 3) save the very first kept (post-rotation) frame for sanity check
            if save_debug_png and not debug_written:
                try:
                    cv2.imwrite(debug_png_path, frame_bgr)
                    debug_written = True
                except Exception:
                    pass

            # 4) preprocess to model input
            inp = _preprocess_frame_from_bgr(frame_bgr)

            # 5) MoveNet inference
            kps = _infer_keypoints(interpreter, inp)

            # 6) map to dict and drop undesired points
            lm_dict: Dict[str, List[float]] = {}
            for idx, name in enumerate(MOVENET_KEYPOINTS):
                if name in EXCLUDE:
                    continue
                x, y, c = kps[idx]
                lm_dict[name] = [x, y, c]

            # 7) timestamp in sampled space
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
            "rotate_deg": int(rotate_deg),
            "debug_png": debug_png_path if debug_written else None,
        },
    }
