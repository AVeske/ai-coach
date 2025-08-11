from __future__ import annotations
from typing import Dict, Any, List, Tuple
import numpy as np
from scipy.signal import find_peaks
from .angles import angle_deg, get_xy

def _series_from_frames(samples: List[Dict[str, Any]], joint_triplet: Tuple[str,str,str]) -> List[float]:
    """Build angle series (deg) across frames for A-B-C (angle at B)."""
    A, B, C = joint_triplet
    out = []
    for s in samples:
        lm = s["landmarks"]
        a, b, c = lm.get(A), lm.get(B), lm.get(C)
        if a and b and c:
            ang = angle_deg(get_xy(a), get_xy(b), get_xy(c))
        else:
            ang = float("nan")
        out.append(ang)
    return out

def _smooth(x: List[float], k: int = 5) -> np.ndarray:
    arr = np.array(x, dtype=float)
    # simple moving median to kill spikes
    out = []
    for i in range(len(arr)):
        lo = max(0, i - k)
        hi = min(len(arr), i + k + 1)
        window = arr[lo:hi]
        window = window[~np.isnan(window)]
        out.append(float(np.median(window)) if len(window) else np.nan)
    return np.array(out, dtype=float)

def _shoulder_hip_ankle_angle(sample: Dict[str, Any], side: str = "left") -> float:
    # angle at hip between shoulder-hip-ankle (approx “back neutral”)
    lm = sample["landmarks"]
    sh = lm.get(f"{side}_shoulder")
    hip = lm.get(f"{side}_hip")
    an = lm.get(f"{side}_ankle")
    if sh and hip and an:
        return angle_deg(get_xy(sh), get_xy(hip), get_xy(an))
    return float("nan")

def _hip_level_diff(sample: Dict[str, Any]) -> float:
    lm = sample["landmarks"]
    lh, rh = lm.get("left_hip"), lm.get("right_hip")
    if lh and rh:
        return abs(get_xy(lh)[1] - get_xy(rh)[1])  # normalized Y diff
    return float("nan")

def detect_reps_pushup(samples: List[Dict[str, Any]], fps: float, cfg: Dict[str, Any]):
    """
    Returns: dict with per-rep metrics + overall summary.
    """
    thr = cfg["thresholds"]
    elbow = _series_from_frames(samples, ("left_shoulder","left_elbow","left_wrist"))
    # fallback to right if left is mostly NaN
    if np.isnan(np.nanmedian(elbow)):
        elbow = _series_from_frames(samples, ("right_shoulder","right_elbow","right_wrist"))

    elbow = _smooth(elbow, k=3)
    t = np.arange(len(elbow)) / max(fps, 1.0)

    # peaks = top (lockout), troughs = bottom
    # invert series to find troughs as peaks
    peaks, _ = find_peaks(elbow, distance=max(2, int(0.25*fps)))
    troughs, _ = find_peaks(-elbow, distance=max(2, int(0.25*fps)))

    events = sorted([(i, "top") for i in peaks] + [(i, "bottom") for i in troughs])
    reps = []
    # define a rep between consecutive tops with a bottom in between
    last_top = None
    for idx, typ in events:
        if typ == "top":
            if last_top is None:
                last_top = idx
            else:
                # look for a bottom between last_top..idx
                bottoms = [i for i, t2 in events if t2=="bottom" and last_top < i < idx]
                if bottoms:
                    bot = int(bottoms[np.argmin([abs(elbow[i]) for i in bottoms])])  # deepest
                    reps.append((last_top, bot, idx))
                last_top = idx

    rep_summaries = []
    for (i_top1, i_bot, i_top2) in reps:
        start_t, end_t = t[i_top1], t[i_top2]
        dur = end_t - start_t
        if not (thr["min_rep_duration_s"] <= dur <= thr["max_rep_duration_s"]):
            continue

        e_top1 = elbow[i_top1]; e_bot = elbow[i_bot]; e_top2 = elbow[i_top2]
        rom = max(e_top1, e_top2) - e_bot

        # posture metrics at bottom
        s_bot = samples[i_bot] if i_bot < len(samples) else samples[-1]
        hip_diff = _hip_level_diff(s_bot)
        back_left = _shoulder_hip_ankle_angle(s_bot, "left")
        back_right = _shoulder_hip_ankle_angle(s_bot, "right")
        back_neutral = np.nanmean([back_left, back_right])

        flags = []
        if rom < thr["rep_depth_min_deg"]:
            flags.append("shallow")
        if hip_diff > thr["hip_level_max_diff"]:
            flags.append("hip_twist")
        br = thr["back_neutral_range_deg"]
        if not (br[0] <= back_neutral <= br[1]):
            flags.append("back_not_neutral")

        rep_summaries.append({
            "start_frame": int(i_top1),
            "bottom_frame": int(i_bot),
            "end_frame": int(i_top2),
            "duration_s": float(dur),
            "elbow_top1_deg": float(e_top1),
            "elbow_bottom_deg": float(e_bot),
            "elbow_top2_deg": float(e_top2),
            "rom_deg": float(rom),
            "hip_level_diff": float(hip_diff) if not np.isnan(hip_diff) else None,
            "back_neutral_deg": float(back_neutral) if not np.isnan(back_neutral) else None,
            "flags": flags,
        })

    overall = {
        "total_reps": len(rep_summaries),
        "good_reps": sum(1 for r in rep_summaries if not r["flags"]),
        "shallow_reps": sum(1 for r in rep_summaries if "shallow" in r["flags"]),
        "hip_twist_reps": sum(1 for r in rep_summaries if "hip_twist" in r["flags"]),
        "back_not_neutral_reps": sum(1 for r in rep_summaries if "back_not_neutral" in r["flags"]),
    }
    return {"reps": rep_summaries, "summary": overall}
