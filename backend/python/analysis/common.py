from __future__ import annotations
from typing import List, Dict, Any, Tuple, Optional
import numpy as np
from scipy.signal import find_peaks

# ─────────── low-level helpers ───────────
def xy(v):
    if not v: return None
    return np.array([float(v[0]), float(v[1])], dtype=float)

def angle_deg(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    ba, bc = a - b, c - b
    nba = ba / (np.linalg.norm(ba) + 1e-9)
    nbc = bc / (np.linalg.norm(bc) + 1e-9)
    cosang = np.clip(np.dot(nba, nbc), -1.0, 1.0)
    return float(np.degrees(np.arccos(cosang)))

def median_smooth(arr: np.ndarray, k: int = 5) -> np.ndarray:
    out = arr.copy()
    for i in range(len(arr)):
        lo, hi = max(0, i-k), min(len(arr), i+k+1)
        w = arr[lo:hi]
        w = w[~np.isnan(w)]
        out[i] = float(np.median(w)) if len(w) else np.nan
    return out

# ─────────── series builders ───────────
def angle_series(samples: List[Dict[str, Any]], triplet: List[str]) -> np.ndarray:
    A,B,C = triplet
    vals = []
    for s in samples:
        lm = s.get("landmarks", {})
        a,b,c = xy(lm.get(A)), xy(lm.get(B)), xy(lm.get(C))
        vals.append(angle_deg(a,b,c) if a is not None and b is not None and c is not None else np.nan)
    return np.array(vals, dtype=float)

def best_of_two(samples, t1, t2) -> np.ndarray:
    a = angle_series(samples, t1); b = angle_series(samples, t2)
    # pick the one with fewer NaNs; if equal, prefer the one with higher median confidence implicitly
    if np.isnan(a).sum() <= np.isnan(b).sum():
        return a
    return b

# ─────────── event detection / pairing ───────────
def find_events(primary: np.ndarray, fps: float, *, peak_is_top=True, min_dist_s=0.30, prom_std=0.18, width_s=0.08):
    finite = np.where(~np.isnan(primary), primary, np.nanmedian(primary))
    prom = float(np.nanstd(finite) * prom_std)
    width = max(1, int(width_s * fps))
    min_dist = max(1, int(min_dist_s * fps))
    if peak_is_top:
        tops, _ = find_peaks(finite, distance=min_dist, prominence=prom, width=width)
        bottoms, _ = find_peaks(-finite, distance=min_dist, prominence=prom, width=width)
    else:
        tops, _ = find_peaks(-finite, distance=min_dist, prominence=prom, width=width)
        bottoms, _ = find_peaks(finite, distance=min_dist, prominence=prom, width=width)
    return tops, bottoms

def pair_top_bottom_top(primary: np.ndarray, tops, bottoms, fps: float, *, dur_min=0.45, dur_max=7.0):
    events = sorted([(int(i),"top") for i in tops] + [(int(i),"bottom") for i in bottoms])
    reps, last_top = [], None
    for idx, typ in events:
        if typ == "top":
            if last_top is None:
                last_top = idx
            else:
                mids = [i for i,t2 in events if t2=="bottom" and last_top < i < idx]
                if mids:
                    i_bot = int(min(mids, key=lambda k: primary[k] if not np.isnan(primary[k]) else 9e9))
                    dur = (idx-last_top)/max(1.0,fps)
                    if dur_min <= dur <= dur_max:
                        reps.append((last_top, i_bot, idx))
                last_top = idx
    return reps

# ─────────── grading helpers ───────────
def tier_of(value: Optional[float], tiers: Dict[str, List[float]]) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "unknown"
    for name, rng in tiers.items():
        lo, hi = float(rng[0]), float(rng[1])
        if lo <= float(value) <= hi:
            return name
    return "unknown"

def summarize(per_rep: List[Dict[str,Any]]):
    total = len(per_rep)
    bad = sum(1 for r in per_rep if not r.get("good", False))
    good = total - bad
    flags = {}
    for r in per_rep:
        for f in r.get("flags", []):
            flags[f] = flags.get(f,0)+1
    out = {"total_reps": total, "good_reps": good, "bad_reps": bad}
    out.update({f"{k}_reps": v for k,v in flags.items()})
    return out
