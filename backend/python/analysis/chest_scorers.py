# backend/python/analysis/chest_scorers.py
from __future__ import annotations
from typing import Dict, Any, List, Tuple
import numpy as np
import logging

from .common import median_smooth, find_events, pair_top_bottom_top, summarize
from side_selector import (
    series_y_for_joint, elbow_angle_series_for_side,
)

log = logging.getLogger("aicoach")

# ---------------- helpers (kept minimal) ----------------

def _winsorize(arr: np.ndarray, lo: float = 0.10, hi: float = 0.90) -> np.ndarray:
    """Clip finite values of arr to [P_lo, P_hi] percentiles to blunt outliers."""
    if arr.size == 0:
        return arr
    finite = arr[~np.isnan(arr)]
    if finite.size == 0:
        return arr
    plo = float(np.percentile(finite, lo * 100.0))
    phi = float(np.percentile(finite, hi * 100.0))
    out = arr.copy()
    mask = ~np.isnan(out)
    out[mask] = np.clip(out[mask], plo, phi)
    return out

def _dynamic_thresholds_winsorized(
    y_series: np.ndarray,
    bottom_pct: float,
    top_pct: float,
    win_lo: float = 0.10,
    win_hi: float = 0.90,
) -> Dict[str, float]:
    """
    Winsorize then compute bottom/top/mid percentiles on shoulder-Y.
    y larger at bottom -> 'bottom' uses higher percentile (e.g., 0.72), 'top' uses lower (e.g., 0.28).
    """
    y = _winsorize(y_series, lo=win_lo, hi=win_hi)
    finite = y[~np.isnan(y)]
    if finite.size == 0:
        return {"bottom": np.nan, "top": np.nan, "mid": np.nan}
    bottom = float(np.percentile(finite, bottom_pct * 100.0))
    top    = float(np.percentile(finite, top_pct * 100.0))
    return {"bottom": bottom, "top": top, "mid": float((bottom + top) / 2.0)}

def _filter_spans(spans: List[Tuple[int,int,int]], fps: float, dur_min: float, dur_max: float, slack: float = 1.25):
    """Throw away spans that are way too long; keep plausible ones."""
    kept, dropped = [], []
    for t1, b, t2 in spans:
        d = (t2 - t1) / max(1.0, fps)
        if dur_min <= d <= dur_max * slack:
            kept.append((t1, b, t2))
        else:
            dropped.append((t1, b, t2))
    return kept, dropped

# ---------------- main scorer: COUNT ONLY ----------------

def score_pushup(
    samples: List[Dict[str,Any]],
    fps: float,
    cfg: Dict[str,Any],
    *,
    primary_side: str = "left",
) -> Dict[str,Any]:
    """
    COUNTING VERSION:
      • Build elbow-angle and shoulder-Y series (median smoothed).
      • Find events + pair spans for BOTH signals.
      • Filter absurdly long spans.
      • Choose the segmentation with MORE plausible reps (tie-break keeps elbow unless it degenerated).
      • Emit ALL kept spans as reps. No flags/grades. Everything is 'good' by definition here.
    """
    if not samples:
        return {"reps": [], "summary": {"total_reps": 0, "good_reps": 0, "bad_reps": 0}}

    ev = (cfg.get("events") or {})
    # Sensitivities (friendly defaults; tweak in YAML if desired)
    prom_std   = float(ev.get("prominence_std", 0.09))
    width_s    = float(ev.get("width_sec", 0.05))
    dur_min    = float(ev.get("min_rep_duration_s", 0.40))
    dur_max    = float(ev.get("max_rep_duration_s", 7.0))
    min_dist_s = float(str(ev.get("min_peak_distance_frames", "0.28s")).replace("s", ""))

    # winsorization from YAML (now actually used)
    win_lo     = float(ev.get("winsor_lo", 0.10))
    win_hi     = float(ev.get("winsor_hi", 0.90))

    bottom_pct = float(ev.get("shoulder_y_bottom_pct", 0.72))
    top_pct    = float(ev.get("shoulder_y_top_pct", 0.28))

    # ---- series (low conf threshold so bottoms don't NaN out) ----
    sh_y   = series_y_for_joint(samples, "shoulder", primary_side, conf_thresh=0.15)
    elbow  = elbow_angle_series_for_side(samples, primary_side, conf_thresh=0.15)

    # Smooth
    sh_y  = median_smooth(sh_y, 6)
    elbow = median_smooth(elbow, 6)

    # Shoulder winsorized thresholds (for debug only; not gating)
    bands = _dynamic_thresholds_winsorized(sh_y, bottom_pct, top_pct, win_lo=win_lo, win_hi=win_hi)

    # ---- segmentation 1: elbow-angle (tops at lockout, bottoms at depth) ----
    tops_e, bots_e = find_events(
        elbow, fps, peak_is_top=True,
        min_dist_s=min_dist_s, prom_std=prom_std, width_s=max(0.04, width_s),
    )
    spans_e = pair_top_bottom_top(elbow, tops_e, bots_e, fps, dur_min=dur_min, dur_max=dur_max)
    kept_e, drop_e = _filter_spans(spans_e, fps, dur_min, dur_max, slack=1.25)

    # ---- segmentation 2: shoulder-Y (peaks at bottom if we treat finite series directly) ----
    finite_sh = np.where(~np.isnan(sh_y), sh_y, np.nanmedian(sh_y))
    prom_std_s = max(0.06, prom_std)      # a bit more sensitive on shoulder
    width_s_s  = max(0.04, width_s)
    tops_s, bots_s = find_events(
        finite_sh, fps, peak_is_top=False,   # bottom are peaks on finite; tops are peaks on -finite
        min_dist_s=min_dist_s, prom_std=prom_std_s, width_s=width_s_s,
    )
    spans_s = pair_top_bottom_top(finite_sh, tops_s, bots_s, fps, dur_min=dur_min, dur_max=dur_max)
    kept_s, drop_s = _filter_spans(spans_s, fps, dur_min, dur_max, slack=1.25)

    if drop_e:
        log.info("Elbow spans filtered (overlong): %s", [(a,c) for (a,_,c) in drop_e])
    if drop_s:
        log.info("Shoulder spans filtered (overlong): %s", [(a,c) for (a,_,c) in drop_s])

    # ---- choose which segmentation to use ----
    if len(kept_s) > len(kept_e):
        use_elbow = False
        spans = kept_s
    elif len(kept_e) > 0:
        use_elbow = True
        spans = kept_e
        # If elbow has only 1 kept span but originally had overlong spans and shoulder has >=1, prefer shoulder:
        if len(kept_e) == 1 and (len(kept_s) >= 1) and (len(drop_e) > 0):
            use_elbow = False
            spans = kept_s
    elif len(kept_s) > 0:
        use_elbow = False
        spans = kept_s
    else:
        # Nothing plausible
        dbg = {
            "elbow_events": {"tops_found": int(len(tops_e)), "bottoms_found": int(len(bots_e)), "spans_after_pair": int(len(spans_e)), "kept": len(kept_e)},
            "shoulder_events": {"tops_found": int(len(tops_s)), "bottoms_found": int(len(bots_s)), "spans_after_pair": int(len(spans_s)), "kept": len(kept_s)},
            "used_signal": "none",
            "bands": bands,
            "note": "no spans within duration limits",
        }
        return {"reps": [], "summary": {"total_reps": 0, "good_reps": 0, "bad_reps": 0}, "event_debug": dbg}

    # ---- emit ALL kept spans as reps (counting only) + LOG timeframes ----
    per: List[Dict[str, Any]] = []
    for idx, (t1, bot, t2) in enumerate(spans, start=1):
        dur_s = (t2 - t1) / max(1.0, fps)
        # Log both frames and seconds for visibility
        log.info(
            "[COUNT] rep %d frames=(%d,%d,%d) secs=(%.2f, %.2f, %.2f) signal=%s",
            idx, int(t1), int(bot), int(t2),
            t1 / max(1.0, fps), bot / max(1.0, fps), t2 / max(1.0, fps),
            "elbow_angle" if use_elbow else "shoulder_y",
        )
        per.append({
            "start_frame": int(t1),
            "bottom_frame": int(bot),
            "end_frame": int(t2),
            "duration_s": float(dur_s),
            "signals": {
                "used_signal": "elbow_angle" if use_elbow else "shoulder_y",
                "bands": bands,  # for visibility; not used to veto
            },
            "good": True,   # by design in this counting-only phase
        })

    # Summary: all reps are "good" right now
    out = {
        "reps": per,
        "summary": {
            "total_reps": len(per),
            "good_reps": len(per),
            "bad_reps": 0,
        },
        "event_debug": {
            "elbow_events": {"tops_found": int(len(tops_e)), "bottoms_found": int(len(bots_e)), "spans_after_pair": int(len(spans_e)), "kept": len(kept_e)},
            "shoulder_events": {"tops_found": int(len(tops_s)), "bottoms_found": int(len(bots_s)), "spans_after_pair": int(len(spans_s)), "kept": len(kept_s)},
            "used_signal": "elbow_angle" if use_elbow else "shoulder_y",
            "thresholds": {
                "prom_std": prom_std,
                "width_s": width_s,
                "min_dist_s": min_dist_s,
                "bottom_pct": bottom_pct,
                "top_pct": top_pct,
                "winsor_lo": win_lo,
                "winsor_hi": win_hi,
            },
        },
    }
    return out
