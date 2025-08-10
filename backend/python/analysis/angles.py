# backend/python/analysis/angles.py
from __future__ import annotations
import numpy as np
from typing import Dict, Optional

def _vec(a, b):
    return np.array(b) - np.array(a)

def angle_deg(a, b, c) -> float:
    """Angle ABC in degrees given 2D points a,b,c (use x,y only)."""
    ab = _vec(b, a)
    cb = _vec(b, c)
    denom = np.linalg.norm(ab) * np.linalg.norm(cb)
    if denom == 0:
        return float("nan")
    cosang = np.clip(np.dot(ab, cb) / denom, -1.0, 1.0)
    return float(np.degrees(np.arccos(cosang)))

def get_xy(lm: Dict[str, float]) -> Optional[np.ndarray]:
    # Landmarks are [x, y, z, visibility]; we only need x,y
    if not lm or len(lm) < 2:
        return None
    return np.array([lm[0], lm[1]], dtype=float)
