from __future__ import annotations
from typing import Dict, Any, List
import numpy as np

MIN_FRAMES_WITH_LANDMARKS = 0.5
MIN_MOTION_ENERGY = 0.012
CORE_KEYS = ["left_shoulder","right_shoulder","left_hip","right_hip"]

def _avg_core_visibility(sample: Dict[str, Any]) -> float:
    lm = sample.get("landmarks", {})
    vals = [float(v[2]) for k,v in lm.items() if k in CORE_KEYS and v and len(v)>=3]
    return float(np.mean(vals)) if vals else 0.0

def frames_with_landmarks_ratio(samples: List[Dict[str, Any]]) -> float:
    return sum(1 for s in samples if s.get("landmarks")) / max(1, len(samples))

def motion_energy(samples: List[Dict[str, Any]]) -> float:
    seq = []
    for s in samples:
        pts = [(float(v[0]), float(v[1])) for v in (s.get("landmarks") or {}).values() if v]
        if pts: seq.append(np.array(pts).flatten())
    if len(seq) < 2: return 0.0
    diffs = [np.linalg.norm(seq[i]-seq[i-1]) for i in range(1,len(seq))]
    return float(np.mean(diffs))

def basic_validation(pose_out: Dict[str, Any]) -> Dict[str, Any]:
    samples = pose_out.get("samples", [])
    if len(samples) < 6:
        return {"valid": False, "reason": "too_few_frames"}
    if frames_with_landmarks_ratio(samples) < MIN_FRAMES_WITH_LANDMARKS:
        return {"valid": False, "reason": "no_person_detected"}
    if motion_energy(samples) < MIN_MOTION_ENERGY:
        return {"valid": False, "reason": "not_enough_motion"}
    if sum(1 for s in samples if _avg_core_visibility(s) >= 0.45) / len(samples) < 0.35:
        return {"valid": False, "reason": "low_pose_confidence"}
    return {"valid": True}