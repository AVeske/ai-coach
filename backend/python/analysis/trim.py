# backend/python/analysis/trim.py
from __future__ import annotations
from typing import List, Dict, Any, Tuple
import numpy as np

CORE_PARTS = [
    "left_shoulder","right_shoulder",
    "left_hip","right_hip",
    "left_elbow","right_elbow",
    "left_knee","right_knee",
    "left_wrist","right_wrist",
    "left_ankle","right_ankle",
]

def _get_xyc(sample: Dict[str, Any], name: str):
    lm = sample.get("landmarks") or {}
    v = lm.get(name)
    if not v or len(v) < 3:
        return None, None, None
    x, y, c = v[0], v[1], v[2]
    return (float(x) if x is not None else None,
            float(y) if y is not None else None,
            float(c) if c is not None else None)

def _ema(arr: np.ndarray, alpha: float) -> np.ndarray:
    out = np.empty_like(arr, dtype=float)
    if arr.size == 0:
        return arr.astype(float)
    out[0] = arr[0]
    for i in range(1, len(arr)):
        out[i] = alpha * arr[i] + (1.0 - alpha) * out[i-1]
    return out

def _zscore(a: np.ndarray) -> np.ndarray:
    if a.size == 0:
        return a.astype(float)
    m = float(np.nanmean(a)) if not np.isnan(a).all() else 0.0
    s = float(np.nanstd(a)) if not np.isnan(a).all() else 1.0
    s = (s if s > 1e-6 else 1.0)
    return (a - m) / s

def _motion_energy(samples: List[Dict[str, Any]]) -> np.ndarray:
    """Side-agnostic motion from hips & shoulders (both sides), in pixel units."""
    n = len(samples)
    if n == 0:
        return np.zeros(0, dtype=float)
    xs, ys = [], []
    parts = ["left_shoulder","right_shoulder","left_hip","right_hip"]
    for p in parts:
        x = np.array([_get_xyc(s, p)[0] for s in samples], dtype=float)
        y = np.array([_get_xyc(s, p)[1] for s in samples], dtype=float)
        xs.append(x); ys.append(y)
    X = np.nanmean(np.vstack(xs), axis=0)  # [n]
    Y = np.nanmean(np.vstack(ys), axis=0)
    # forward diff magnitude
    dX = np.abs(np.diff(X, prepend=X[:1]))
    dY = np.abs(np.diff(Y, prepend=Y[:1]))
    return np.sqrt(dX*dX + dY*dY)

def _frame_conf(samples: List[Dict[str, Any]]) -> np.ndarray:
    n = len(samples)
    if n == 0:
        return np.zeros(0, dtype=float)
    confs = []
    for s in samples:
        vals = []
        lm = s.get("landmarks") or {}
        for k in CORE_PARTS:
            v = lm.get(k)
            if v and len(v) >= 3 and v[2] is not None:
                vals.append(float(v[2]))
        confs.append(float(np.median(vals)) if vals else 0.0)
    return np.array(confs, dtype=float)

def _pick_active_run(active: np.ndarray, min_len: int) -> Tuple[int,int]:
    """Pick the longest contiguous active run with length >= min_len. Returns [lo, hi) indexes."""
    n = len(active)
    best_len, best_lo, best_hi = 0, 0, 0
    i = 0
    while i < n:
        if active[i]:
            j = i+1
            while j < n and active[j]:
                j += 1
            run_len = j - i
            if run_len > best_len:
                best_len, best_lo, best_hi = run_len, i, j
            i = j
        else:
            i += 1
    if best_len >= min_len:
        return best_lo, best_hi
    return 0, n  # if nothing meets min_len, return full window (no trim)

def trim_active_window(
    samples: List[Dict[str, Any]],
    fps: float,
    *,
    min_run_s: float = 1.2,
    pad_s: float = 0.35,
    conf_ema_alpha: float = 0.25,
    motion_ema_alpha: float = 0.35,
    conf_weight: float = 0.6,
    motion_weight: float = 0.4,
    z_active_thresh: float = -0.2,
    z_inactive_thresh: float = -0.6,
) -> Tuple[List[Dict[str, Any]], int, int, Dict[str, Any]]:
    """
    Generic trim:
      - Computes EMA-smoothed frame confidence and motion energy.
      - Z-scores each, then combines into an 'activity' score.
      - Hysteresis thresholding (active > z_active_thresh; inactive < z_inactive_thresh).
      - Picks the longest active run (>= min_run_s). Adds symmetric pad_s on both ends.
    Returns (trimmed_samples, lo_idx, hi_idx, reasons).
    """
    n = len(samples)
    if n == 0 or fps <= 0:
        return samples, 0, n, {"method": "generic_trim", "reason": "empty_or_bad_fps"}

    conf = _frame_conf(samples)
    mot  = _motion_energy(samples)

    # Smooth
    conf_s = _ema(conf, conf_ema_alpha)
    mot_s  = _ema(mot, motion_ema_alpha)

    # Normalize
    zc = _zscore(conf_s)
    zm = _zscore(mot_s)

    # Combined activity (weighted)
    act = conf_weight * zc + motion_weight * zm

    # Hysteresis: build a boolean active mask
    active = np.zeros(n, dtype=bool)
    currently_on = False
    for i in range(n):
        if currently_on:
            currently_on = act[i] > z_inactive_thresh
        else:
            currently_on = act[i] > z_active_thresh
        active[i] = currently_on

    min_len = int(round(min_run_s * max(1.0, fps)))
    lo, hi = _pick_active_run(active, min_len=min_len)

    # Apply pad (clamped)
    pad = int(round(pad_s * max(1.0, fps)))
    lo_p = max(0, lo - pad)
    hi_p = min(n, hi + pad)

    trimmed = samples[lo_p:hi_p]
    reasons = {
        "method": "generic_trim",
        "frames_total": n,
        "lo_raw": lo, "hi_raw": hi,
        "lo_padded": lo_p, "hi_padded": hi_p,
        "min_run_s": min_run_s, "pad_s": pad_s,
        "conf_stats": {
            "median": float(np.median(conf)) if conf.size else 0.0,
            "ema_med": float(np.median(conf_s)) if conf_s.size else 0.0,
        },
        "motion_stats": {
            "median": float(np.median(mot)) if mot.size else 0.0,
            "ema_med": float(np.median(mot_s)) if mot_s.size else 0.0,
        },
        "thresholds": {
            "z_active": z_active_thresh,
            "z_inactive": z_inactive_thresh,
        }
    }
    return trimmed, lo_p, hi_p, reasons
