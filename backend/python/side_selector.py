# backend/python/side_selector.py
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
import os
import csv
import logging
import numpy as np

log = logging.getLogger("aicoach")

# --- landmarks by side ---
LEFT = ["left_shoulder","left_elbow","left_wrist","left_hip","left_knee","left_ankle"]
RIGHT = ["right_shoulder","right_elbow","right_wrist","right_hip","right_knee","right_ankle"]
CORE = ("shoulder","elbow","wrist","hip")

def _pair(side: str, name: str) -> str:
    return f"{side}_{name}"

# ---------------------------------------------------------------------
# Global side selection (coverage + median confidence with safety margin)
# ---------------------------------------------------------------------
def _coverage_and_conf(samples: List[Dict[str, Any]], side: str) -> Tuple[float, float]:
    if not samples:
        return 0.0, 0.0
    seen = 0
    confs: List[float] = []
    for s in samples:
        lm = s.get("landmarks", {})
        vals = []
        for part in CORE:
            v = lm.get(_pair(side, part))
            if v and len(v) >= 3 and v[2] is not None:
                vals.append(float(v[2]))
        if vals:
            seen += 1
            confs.append(float(np.median(vals)))
    coverage = seen / float(len(samples))
    med = float(np.median(confs)) if confs else 0.0
    return coverage, med

def pick_primary_side(
    samples: List[Dict[str, Any]],
    *,
    min_coverage: float = 0.6,
    conf_margin: float = 0.10
) -> Tuple[str, Dict[str, Any]]:
    covL, medL = _coverage_and_conf(samples, "left")
    covR, medR = _coverage_and_conf(samples, "right")

    left_ok  = (covL >= min_coverage)
    right_ok = (covR >= min_coverage)

    if left_ok and right_ok:
        side = "right" if (medR - medL) >= conf_margin else "left"
    elif left_ok:
        side = "left"
    elif right_ok:
        side = "right"
    else:
        side = "left" if medL >= medR else "right"  # low-certainty fallback

    dbg = {
        "coverage": {"left": covL, "right": covR},
        "median_conf": {"left": medL, "right": medR},
        "eligibility": {"left": left_ok, "right": right_ok},
        "conf_margin": conf_margin,
        "min_coverage": min_coverage,
        "picked": side,
        "low_certainty": (not left_ok and not right_ok),
    }
    return side, dbg

# ---------------------------------------------------------------------
# Confidence-weighted smoothing + tiny gap fill (EMA per landmark)
# ---------------------------------------------------------------------
def _ema(prev: Optional[float], x: Optional[float], alpha: float) -> Optional[float]:
    if x is None:
        return prev
    if prev is None:
        return x
    return alpha * x + (1.0 - alpha) * prev

def smooth_samples(
    samples: List[Dict[str, Any]],
    *,
    alpha_min: float = 0.08,
    alpha_max: float = 0.35,
    conf_for_alpha: float = 0.60,
    max_hold_gap: int = 3
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    state: Dict[str, Tuple[Optional[float], Optional[float], Optional[float]]] = {}
    gap_cnt: Dict[str, int] = {}

    for s in samples:
        lm = (s.get("landmarks") or {})
        o_lm: Dict[str, List[Optional[float]]] = {}
        keys = set(state.keys()) | set(lm.keys())
        for k in keys:
            v = lm.get(k)
            x = float(v[0]) if v and v[0] is not None else None
            y = float(v[1]) if v and v[1] is not None else None
            c = float(v[2]) if v and v[2] is not None else None

            prev = state.get(k, (None, None, None))
            cc = (c if c is not None else 0.0)
            t = max(0.0, min(1.0, cc / max(1e-6, conf_for_alpha)))
            alpha = alpha_min + (alpha_max - alpha_min) * t

            if x is None and gap_cnt.get(k, 0) < max_hold_gap:
                x = prev[0]
            if y is None and gap_cnt.get(k, 0) < max_hold_gap:
                y = prev[1]
            if c is None and gap_cnt.get(k, 0) < max_hold_gap:
                c = prev[2]

            sx = _ema(prev[0], x, alpha)
            sy = _ema(prev[1], y, alpha)
            sc = _ema(prev[2], c, alpha)

            if x is None or y is None or c is None:
                gap_cnt[k] = gap_cnt.get(k, 0) + 1
            else:
                gap_cnt[k] = 0

            state[k] = (sx, sy, sc)
            o_lm[k] = [sx, sy, sc]

        out.append({**{k:v for k,v in s.items() if k != "landmarks"}, "landmarks": o_lm})
    return out

# ---------------------------------------------------------------------
# Side-aware series builders with visibility masking
# ---------------------------------------------------------------------
def series_y_for_joint(samples: List[Dict[str, Any]], joint: str, side: str, *, conf_thresh: float = 0.30) -> np.ndarray:
    arr = []
    for s in samples:
        lm = s.get("landmarks", {})
        v = lm.get(f"{side}_{joint}")
        if v and len(v) >= 3 and v[1] is not None and v[2] is not None and float(v[2]) >= conf_thresh:
            arr.append(float(v[1]))
        else:
            arr.append(np.nan)
    return np.array(arr, dtype=float)

def elbow_angle_series_for_side(samples: List[Dict[str, Any]], side: str, *, conf_thresh: float = 0.30) -> np.ndarray:
    from analysis.common import xy, angle_deg
    out = []
    for s in samples:
        lm = s.get("landmarks", {})
        S = lm.get(f"{side}_shoulder")
        E = lm.get(f"{side}_elbow")
        W = lm.get(f"{side}_wrist")
        if S and E and W and min(S[2],E[2],W[2]) is not None and float(min(S[2],E[2],W[2])) >= conf_thresh:
            a=xy(S); b=xy(E); c=xy(W)
            out.append(angle_deg(a,b,c))
        else:
            out.append(np.nan)
    return np.array(out, dtype=float)

def torso_len_at(samples: List[Dict[str, Any]], idx: int, side: str) -> Optional[float]:
    lm = samples[idx].get("landmarks", {})
    S = lm.get(f"{side}_shoulder"); H = lm.get(f"{side}_hip")
    if not (S and H): return None
    if S[0] is None or S[1] is None or H[0] is None or H[1] is None: return None
    return float(np.hypot(float(S[0])-float(H[0]), float(S[1])-float(H[1])))

def elbow_angle_at_event(samples: List[Dict[str, Any]], idx: int, primary: str, *, conf_thresh: float = 0.30) -> Optional[float]:
    from analysis.common import xy, angle_deg
    def ang(side: str) -> Optional[float]:
        lm = samples[idx].get("landmarks", {})
        S = lm.get(f"{side}_shoulder"); E = lm.get(f"{side}_elbow"); W = lm.get(f"{side}_wrist")
        if S and E and W and min(S[2],E[2],W[2]) is not None and float(min(S[2],E[2],W[2])) >= conf_thresh:
            return float(angle_deg(xy(S),xy(E),xy(W)))
        return None
    a = ang(primary)
    if a is not None: return a
    other = "right" if primary == "left" else "left"
    return ang(other)


def knee_angle_series_for_side(samples: List[Dict[str, Any]], side: str, *, conf_thresh: float = 0.30) -> np.ndarray:
    from analysis.common import xy, angle_deg
    out = []
    for s in samples:
        lm = s.get("landmarks", {})
        H = lm.get(f"{side}_hip")
        K = lm.get(f"{side}_knee")
        A = lm.get(f"{side}_ankle")
        if H and K and A and min(H[2], K[2], A[2]) is not None and float(min(H[2], K[2], A[2])) >= conf_thresh:
            out.append(angle_deg(xy(H), xy(K), xy(A)))
        else:
            out.append(np.nan)
    return np.array(out, dtype=float)

# ---------------------------------------------------------------------
# CSV writer
# ---------------------------------------------------------------------
def write_samples_csv(samples: List[Dict[str, Any]], out_dir: str, base_name: str) -> Optional[str]:
    try:
        os.makedirs(out_dir, exist_ok=True)
        names: set[str] = set()
        for s in samples:
            lm = s.get("landmarks") or {}
            names.update(lm.keys())
        ordered = sorted(names)
        header = ["frame"]
        has_t = any("t" in s for s in samples)
        if has_t: header.append("t")
        for n in ordered:
            header.extend([f"{n}_x", f"{n}_y", f"{n}_c"])
        path = os.path.join(out_dir, f"{base_name}.csv")
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f); w.writerow(header)
            for i, s in enumerate(samples):
                row: List[Any] = [i]
                if has_t: row.append(s.get("t"))
                lm = s.get("landmarks") or {}
                for n in ordered:
                    v = lm.get(n) or [None, None, None]
                    row.extend([v[0] if len(v)>0 else None, v[1] if len(v)>1 else None, v[2] if len(v)>2 else None])
                w.writerow(row)
        return path
    except Exception as e:
        log.exception("Failed to write CSV: %s", e)
        return None
