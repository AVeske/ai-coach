from __future__ import annotations
from typing import Dict, Any, List
import numpy as np

MIN_FRAMES_WITH_LANDMARKS = 0.5  # ≥50% frames must have landmarks
MIN_MOTION_ENERGY = 0.015        # tune per device/video scale

def frames_with_landmarks_ratio(samples: List[Dict[str, Any]]) -> float:
    ok = sum(1 for s in samples if s.get("landmarks"))
    return ok / max(1, len(samples))

def motion_energy(samples: List[Dict[str, Any]], keys=("left_wrist","right_wrist","left_elbow","right_elbow")) -> float:
    """Very crude motion estimate: mean frame-to-frame L2 on a few joints (normalized coords)."""
    seq = []
    for s in samples:
        lm = s.get("landmarks", {})
        pts = []
        for k in keys:
            v = lm.get(k)
            if v: pts.append((float(v[0]), float(v[1])))
        if pts:
            seq.append(np.array(pts).flatten())
    if len(seq) < 2: return 0.0
    diffs = [np.linalg.norm(seq[i] - seq[i-1]) for i in range(1, len(seq))]
    return float(np.mean(diffs))

def basic_validation(pose_out: Dict[str, Any]) -> Dict[str, Any]:
    if not pose_out.get("ok"):
        return {"valid": False, "reason": f"pose_failed: {pose_out.get('error','unknown')}"}
    samples = pose_out.get("samples", [])
    if len(samples) < 6:
        return {"valid": False, "reason": "too_few_frames"}
    ratio = frames_with_landmarks_ratio(samples)
    if ratio < MIN_FRAMES_WITH_LANDMARKS:
        return {"valid": False, "reason": "no_person_detected_enough_frames", "ratio": ratio}
    energy = motion_energy(samples)
    if energy < MIN_MOTION_ENERGY:
        return {"valid": False, "reason": "not_enough_motion", "motion_energy": energy}
    return {"valid": True, "ratio": ratio, "motion_energy": energy}
