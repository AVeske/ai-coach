from __future__ import annotations
from typing import List, Dict, Any, Tuple
import numpy as np

# We’ll borrow robust peak pairing from the analysis.common module
from analysis.common import find_peaks, find_events, pair_top_bottom_top  # type: ignore

# Helper: build a shoulder-Y series (choose the cleaner side)
def _shoulder_y_series(samples: List[Dict[str, Any]]) -> np.ndarray:
    yL, yR = [], []
    for s in samples:
        lm = s.get("landmarks", {})
        vL = lm.get("left_shoulder")
        vR = lm.get("right_shoulder")
        yL.append(float(vL[1]) if vL and vL[1] is not None else np.nan)
        yR.append(float(vR[1]) if vR and vR[1] is not None else np.nan)
    a = np.array(yL, dtype=float)
    b = np.array(yR, dtype=float)
    return a if np.isnan(a).sum() <= np.isnan(b).sum() else b

def _nan_fill(arr: np.ndarray) -> np.ndarray:
    out = arr.copy()
    # forward fill
    last = np.nan
    for i in range(len(out)):
        if np.isnan(out[i]):
            out[i] = last
        else:
            last = out[i]
    # back fill
    last = np.nan
    for i in range(len(out)-1, -1, -1):
        if np.isnan(out[i]):
            out[i] = last
        else:
            last = out[i]
    # replace remaining NaNs with 0
    out = np.where(np.isnan(out), 0.0, out)
    return out

def _median_smooth_1d(arr: np.ndarray, k: int = 5) -> np.ndarray:
    out = arr.copy()
    n = len(arr)
    for i in range(n):
        lo, hi = max(0, i-k), min(n, i+k+1)
        w = arr[lo:hi]
        w = w[~np.isnan(w)]
        out[i] = float(np.median(w)) if len(w) else np.nan
    return out

def _trim_by_rep_envelope(samples: List[Dict[str, Any]], fps: float, pad_s: float) -> Tuple[int, int, dict]:
    """
    Try to find rep tops across the whole clip using shoulder-Y (inverted).
    Use first-top to last-top span as the active envelope, padded by pad_s.
    Returns (lo_idx, hi_idx, dbg)
    """
    if not samples:
        return 0, 0, {"method": "none", "reason": "no_samples"}

    y = _shoulder_y_series(samples)
    y = _median_smooth_1d(y, k=3)
    inv = -y
    inv = _nan_fill(inv)

    # Find tops & bottoms on the inverted series (tops == lockout)
    tops, bottoms = find_events(inv, fps, peak_is_top=True, min_dist_s=0.30, prom_std=0.10, width_s=0.05)

    dbg = {"method": "peaks_envelope", "tops": int(len(tops)), "bottoms": int(len(bottoms))}
    if len(tops) >= 2:
        first_top = int(tops[0])
        last_top = int(tops[-1])
        pad = int(pad_s * fps)
        lo = max(0, first_top - pad)
        hi = min(len(samples), last_top + pad)
        # Ensure hi>lo
        if hi - lo >= max(1, int(0.8 * fps)):  # at least ~0.8s window
            return lo, hi, dbg

    # Not enough tops found; let caller fallback
    dbg["reason"] = "not_enough_tops"
    return 0, 0, dbg

def _trim_by_motion_energy(samples: List[Dict[str, Any]], fps: float, min_run_s: float, pad_s: float) -> Tuple[int, int, dict]:
    """
    Previous method: pick the longest run by motion energy.
    """
    if not samples:
        return 0, 0, {"method": "motion_energy", "reason": "no_samples"}

    seq = []
    for s in samples:
        pts = []
        for v in (s.get("landmarks") or {}).values():
            if v: pts.extend([float(v[0]), float(v[1])])
        if pts:
            seq.append(np.array(pts, dtype=float))
        else:
            seq.append(None)
    diffs = []
    prev = None
    for v in seq:
        if v is None or prev is None or prev.shape != v.shape:
            diffs.append(0.0)
        else:
            diffs.append(float(np.linalg.norm(v - prev)))
        prev = v
    diffs = np.array(diffs, dtype=float)
    thr = max(1e-6, np.percentile(diffs[diffs>0], 40) if np.any(diffs>0) else 0.0)
    active = (diffs >= thr).astype(np.int32)

    # find longest active run
    best_lo = best_hi = 0
    cur_lo = 0 if active[0] else -1
    best_len = 0
    for i,a in enumerate(active):
        if a == 1 and cur_lo < 0:
            cur_lo = i
        if a == 0 and cur_lo >= 0:
            if i-cur_lo > best_len:
                best_len = i-cur_lo; best_lo = cur_lo; best_hi = i
            cur_lo = -1
    if cur_lo >= 0:
        i = len(active)
        if i-cur_lo > best_len:
            best_len = i-cur_lo; best_lo = cur_lo; best_hi = i

    pad = int(pad_s * fps)
    lo = max(0, best_lo - pad)
    hi = min(len(samples), best_hi + pad)

    # ensure minimum window
    min_len = int(min_run_s * fps)
    if hi - lo < min_len:
        hi = min(len(samples), lo + min_len)

    return lo, hi, {"method": "motion_energy", "best_len": int(best_len), "thr": float(thr)}

def trim_active_window(
    samples: List[Dict[str, Any]],
    fps: float,
    *,
    min_run_s: float = 1.2,
    pad_s: float = 0.35
) -> Tuple[List[Dict[str,Any]], int, int, dict]:
    """
    Preferred: derive window from rep envelope (top-to-top) using shoulder-Y peaks.
    Fallback: longest motion-energy run.
    Returns: (trimmed_samples, lo_index, hi_index, debug)
    """
    if not samples:
        return samples, 0, 0, {"method": "none", "reason": "no_samples"}

    lo, hi, dbg1 = _trim_by_rep_envelope(samples, fps, pad_s)
    if hi > lo:
        return samples[lo:hi], lo, hi, dbg1

    lo2, hi2, dbg2 = _trim_by_motion_energy(samples, fps, min_run_s, pad_s)
    return samples[lo2:hi2], lo2, hi2, dbg2
