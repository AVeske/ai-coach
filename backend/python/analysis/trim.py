from __future__ import annotations
from typing import List, Dict, Any, Tuple
import numpy as np

# Looser motion gate to keep more usable frames

def trim_active_window(samples: List[Dict[str, Any]], fps: float, *, min_run_s: float = 1.2, pad_s: float = 0.35) -> Tuple[List[Dict[str,Any]], int, int]:
    if not samples:
        return samples, 0, 0
    # simple motion energy on all available landmarks
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
    if cur_lo >= 0:  # tail run
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

    return samples[lo:hi], lo, hi