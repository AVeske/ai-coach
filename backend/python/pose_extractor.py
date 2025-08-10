# backend/python/pose_extractor.py
from __future__ import annotations
import cv2
import numpy as np
from typing import List, Dict, Any, Optional

import mediapipe as mp

# BlazePose: 33 landmarks (full body), indices:
# https://developers.google.com/mediapipe/solutions/vision/pose_landmarker
# We’ll return a simple dict: [{"frame": i, "landmarks": {name: [x,y,z,visibility], ...}}, ...]

POSE = mp.solutions.pose

LANDMARK_NAMES = [
    "nose","left_eye_inner","left_eye","left_eye_outer",
    "right_eye_inner","right_eye","right_eye_outer",
    "left_ear","right_ear","mouth_left","mouth_right",
    "left_shoulder","right_shoulder","left_elbow","right_elbow",
    "left_wrist","right_wrist","left_pinky","right_pinky",
    "left_index","right_index","left_thumb","right_thumb",
    "left_hip","right_hip","left_knee","right_knee",
    "left_ankle","right_ankle","left_heel","right_heel",
    "left_foot_index","right_foot_index"
]

def _landmarks_to_dict(landmarks) -> Dict[str, List[float]]:
    out = {}
    for i, lm in enumerate(landmarks.landmark):
        out[LANDMARK_NAMES[i]] = [lm.x, lm.y, lm.z, lm.visibility]
    return out

def sample_frames_total(cap: cv2.VideoCapture, max_frames: int = 48) -> List[int]:
    """Uniformly sample up to max_frames indices across the video duration."""
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total <= 0:
        return []
    if total <= max_frames:
        return list(range(total))
    step = total / float(max_frames)
    return [int(i * step) for i in range(max_frames)]

def extract_pose_from_video(
    path: str,
    max_frames: int = 48,
    model_complexity: int = 2,   # 0/1/2 => lightning/medium/heavy
    min_detection_confidence: float = 0.5,
    min_tracking_confidence: float = 0.5,
) -> Dict[str, Any]:
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return {"ok": False, "error": "Cannot open video"}

    frames_idx = sample_frames_total(cap, max_frames=max_frames)
    results_all = []

    with POSE.Pose(
        static_image_mode=False,
        model_complexity=model_complexity,
        enable_segmentation=False,
        min_detection_confidence=min_detection_confidence,
        min_tracking_confidence=min_tracking_confidence,
    ) as pose:
        for fi in frames_idx:
            cap.set(cv2.CAP_PROP_POS_FRAMES, fi)
            ok, frame = cap.read()
            if not ok:
                continue
            # Convert BGR -> RGB
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            res = pose.process(rgb)
            if res.pose_landmarks:
                lm = _landmarks_to_dict(res.pose_landmarks)
            else:
                lm = {}
            results_all.append({"frame": fi, "landmarks": lm})

    cap.release()
    return {
        "ok": True,
        "frames": len(frames_idx),
        "samples": results_all,
    }
