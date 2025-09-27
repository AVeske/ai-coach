# backend/python/analysis/chest_scorers.py
from __future__ import annotations
from typing import Dict, Any, List, Tuple, Optional
import os, time, logging
import numpy as np

# headless plotting support (kept in case you want to add local plots again)
import matplotlib
matplotlib.use("Agg")  # no window
import matplotlib.pyplot as plt

from .common import median_smooth, find_events, pair_top_bottom_top, summarize
from side_selector import series_y_for_joint, elbow_angle_series_for_side

log = logging.getLogger("aicoach")

# ───────────────────────── helpers ─────────────────────────

def _winsorize(arr: np.ndarray, lo: float, hi: float) -> np.ndarray:
    """Winsorize using percentile clip [lo, hi] where lo/hi ∈ [0,1]."""
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


def _json_safe_list(vals: List[float] | np.ndarray) -> List[Optional[float]]:
    """Convert list/array to JSON-safe floats (NaN/Inf -> None)."""
    out: List[Optional[float]] = []
    if isinstance(vals, np.ndarray):
        vals = vals.tolist()
    for v in vals:
        if v is None:
            out.append(None)
            continue
        try:
            f = float(v)
        except Exception:
            out.append(None)
            continue
        out.append(f if np.isfinite(f) else None)
    return out


def _filter_spans(spans: List[Tuple[int,int,int]], fps: float,
                  dur_min: float, dur_max: float, *, slack: float = 1.25):
    kept, dropped = [], []
    for a,b,c in spans:
        d = (c - a) / max(1.0, fps)
        if dur_min <= d <= (dur_max * slack):
            kept.append((a,b,c))
        else:
            dropped.append((a,b,c))
    return kept, dropped


def _first_span_start_s(spans: List[Tuple[int,int,int]], fps: float) -> float:
    return (spans[0][0] / max(1.0, fps)) if spans else float("inf")


def _span_amp(series: np.ndarray, span: Tuple[int,int,int]) -> Optional[float]:
    """Amplitude = average(top,top) - bottom in ORIGINAL elbow space."""
    a,b,c = span
    if any(i < 0 or i >= len(series) for i in (a,b,c)):
        return None
    va, vb, vc = series[a], series[b], series[c]
    if np.isnan(va) or np.isnan(vb) or np.isnan(vc):
        return None
    return float(((va + vc) / 2.0) - vb)


# ───────────── endpoint seeding (configurable) ─────────────

def _augment_endpoint_tops(
    series: np.ndarray,
    fps: float,
    tops: List[int],
    bottoms: List[int],
    *,
    window_s: float = 0.6,
    peak_frac: float = 0.96,
    tol_deg: float = 8.0,
    min_drop_frac: float = 0.05,
    min_drop_deg: float = 14.0,
    exclude_radius_frames: int = 3,
    skip_if_valid_span_starts_within_s: float = 1.0,
    known_spans: Optional[List[Tuple[int,int,int]]] = None,
) -> List[int]:
    """
    Add synthetic TOPS near start/end only if they look like true lockouts.
    Uses similarity (to global/median top), contrast (vs bottom/min),
    and duplication/timing guards.
    """
    n = len(series)
    if n == 0:
        return tops

    finite = np.where(~np.isnan(series), series, np.nanmedian(series))
    tops = sorted(int(x) for x in tops)
    bottoms = sorted(int(x) for x in bottoms) if bottoms else []
    w = max(1, int(window_s * fps))

    gmax = float(np.nanmax(finite)) if np.isfinite(np.nanmax(finite)) else np.nan
    med_top = None
    if tops:
        tv = [float(finite[t]) for t in tops if 0 <= t < n and np.isfinite(finite[t])]
        if tv:
            med_top = float(np.median(tv))

    def _ok_similarity(val: float) -> bool:
        c1 = (np.isfinite(gmax) and val >= gmax * peak_frac)
        c2 = (med_top is not None and val >= (med_top - tol_deg))
        return bool(c1 or c2)

    def _ok_contrast(peak_val: float, ref_val: float) -> bool:
        if not (np.isfinite(peak_val) and np.isfinite(ref_val)):
            return False
        return (peak_val - ref_val) >= max(min_drop_deg, abs(peak_val) * min_drop_frac)

    def _near_existing(idx: int) -> bool:
        return any(abs(idx - t) <= exclude_radius_frames for t in tops)

    def _span_starts_very_early() -> bool:
        if not known_spans:
            return False
        early = skip_if_valid_span_starts_within_s
        return any((a / max(1.0, fps)) <= early for (a,_,_) in known_spans)

    # START seeding
    if not _span_starts_very_early():
        lo, hi = 0, min(n, w)
        if hi - lo >= 3 and np.any(~np.isnan(finite[lo:hi])):
            idx = lo + int(np.nanargmax(finite[lo:hi]))
            pval = float(finite[idx])
            ref = (float(finite[bottoms[0]]) if bottoms and np.isfinite(finite[bottoms[0]])
                   else float(np.nanmin(finite[lo:hi])))
            if _ok_similarity(pval) and _ok_contrast(pval, ref) and not _near_existing(idx):
                tops = sorted(tops + [idx])
                log.info("Augmented FIRST top at frame %d (%.2fs)", idx, idx/max(1.0,fps))

    # END seeding
    lo, hi = max(0, n - w), n
    if hi - lo >= 3 and np.any(~np.isnan(finite[lo:hi])):
        idx = lo + int(np.nanargmax(finite[lo:hi]))
        pval = float(finite[idx])
        ref = (float(finite[bottoms[-1]]) if bottoms and np.isfinite(finite[bottoms[-1]])
               else float(np.nanmin(finite[lo:hi])))
        if _ok_similarity(pval) and _ok_contrast(pval, ref) and not _near_existing(idx):
            tops = sorted(tops + [idx])
            log.info("Augmented LAST top at frame %d (%.2fs)", idx, idx/max(1.0,fps))

    return tops


# ───────────── negspace pairing in ORIGINAL space ─────────────

def _pair_negspace_in_original(
    elbow: np.ndarray,
    fps: float,
    *,
    min_dist_s: float,
    prom_std: float,
    width_s: float,
    dur_min: float,
    dur_max: float,
    seed_params: Dict[str, float] | None = None,
) -> Tuple[List[Tuple[int,int,int]], Dict[str, Any]]:
    """
    Detect peaks on -elbow (to make bottoms salient), then pair on ORIGINAL elbow
    so spans are Top–Bottom–Top in original space.
    """
    finite = np.where(~np.isnan(elbow), elbow, np.nanmedian(elbow))
    neg = -finite
    ntops, nbots = find_events(
        neg, fps, peak_is_top=True,
        min_dist_s=min_dist_s, prom_std=prom_std, width_s=width_s
    )
    # In ORIGINAL space:
    orig_tops = nbots   # original TOPS
    orig_bots = ntops   # original BOTTOMS

    # Optional endpoint seeding (in original space)
    if seed_params:
        orig_tops = _augment_endpoint_tops(
            finite, fps, list(orig_tops), list(orig_bots),
            window_s=float(seed_params.get("window_s", 0.6)),
            peak_frac=float(seed_params.get("peak_frac", 0.96)),
            tol_deg=float(seed_params.get("tol_deg", 8.0)),
            min_drop_frac=float(seed_params.get("min_drop_frac", 0.05)),
            min_drop_deg=float(seed_params.get("min_drop_deg", 14.0)),
            exclude_radius_frames=int(seed_params.get("exclude_radius_frames", 3)),
            skip_if_valid_span_starts_within_s=float(seed_params.get("skip_if_valid_span_starts_within_s", 1.0)),
            known_spans=None,
        )

    spans = pair_top_bottom_top(
        finite, orig_tops, orig_bots, fps, dur_min=dur_min, dur_max=dur_max
    )

    dbg = {
        # For plotting in ORIGINAL space:
        "peaks_all": {"tops": [int(x) for x in orig_tops],
                      "bottoms": [int(x) for x in orig_bots]},
        # Raw neg indices if you want to see them:
        "peaks_btb": {"tops_on_neg": [int(x) for x in ntops],      # original bottoms
                      "bottoms_on_neg": [int(x) for x in nbots]},  # original tops
    }
    return spans, dbg


# ───────────────────────── main scorer ─────────────────────────

def score_pushup(
    samples: List[Dict[str,Any]],
    fps: float,
    cfg: Dict[str,Any],
    *,
    primary_side: str = "left",
) -> Dict[str,Any]:
    if not samples:
        return {"reps": [], "summary": {"total_reps": 0, "good_reps": 0, "bad_reps": 0}}

    ev = (cfg.get("events") or {})
    prom_std   = float(ev.get("prominence_std", 0.09))
    width_s    = float(ev.get("width_sec", 0.05))
    dur_min    = float(ev.get("min_rep_duration_s", 0.40))
    dur_max    = float(ev.get("max_rep_duration_s", 7.0))
    min_dist_s = float(str(ev.get("min_peak_distance_frames", "0.28s")).replace("s", ""))
    refractory_ms = float(ev.get("refractory_ms", 300.0))  # not used here but kept for parity / future
    force_signal = (ev.get("force_signal") or "auto").lower().strip()

    # Winsor for debug bands / CSV
    winsor_lo  = float(ev.get("winsor_lo", 0.15))
    winsor_hi  = float(ev.get("winsor_hi", 0.85))

    # Seeding params (optional)
    seed_cfg = (ev.get("seed") or {})

    # Build series (smooth=5)
    sh_y   = series_y_for_joint(samples, "shoulder", primary_side, conf_thresh=0.15)
    elbow  = elbow_angle_series_for_side(samples, primary_side, conf_thresh=0.15)
    sh_y   = median_smooth(sh_y, 5)
    elbow  = median_smooth(elbow, 5)
    sh_y_wins = _winsorize(sh_y, winsor_lo, winsor_hi)

    # ── ELBOW: simple path (T–B–T on original)
    tops_e, bots_e = find_events(
        elbow, fps, peak_is_top=True,
        min_dist_s=min_dist_s, prom_std=prom_std, width_s=width_s
    )

    # Seed endpoints for simple path (original space)
    tops_e_seeded = _augment_endpoint_tops(
        elbow, fps, list(tops_e), list(bots_e),
        window_s=float(seed_cfg.get("window_s", 0.6)),
        peak_frac=float(seed_cfg.get("peak_frac", 0.96)),
        tol_deg=float(seed_cfg.get("tol_deg", 8.0)),
        min_drop_frac=float(seed_cfg.get("min_drop_frac", 0.05)),
        min_drop_deg=float(seed_cfg.get("min_drop_deg", 14.0)),
        exclude_radius_frames=int(seed_cfg.get("exclude_radius_frames", 3)),
        skip_if_valid_span_starts_within_s=float(seed_cfg.get("skip_if_valid_span_starts_within_s", 1.0)),
        known_spans=None,
    )

    spans_simple = pair_top_bottom_top(
        elbow, tops_e_seeded, bots_e, fps, dur_min=dur_min, dur_max=dur_max
    )
    kept_simple, drop_simple = _filter_spans(spans_simple, fps, dur_min, dur_max)

    # ── ELBOW: negspace detection, but pair in original space (T–B–T)
    spans_neg, dbg_neg = _pair_negspace_in_original(
        elbow, fps,
        min_dist_s=min_dist_s, prom_std=prom_std, width_s=width_s,
        dur_min=dur_min, dur_max=dur_max, seed_params=seed_cfg
    )
    kept_neg, drop_neg = _filter_spans(spans_neg, fps, dur_min, dur_max)

    # ── Choose elbow variant by count, then by early start
    def _score_variant(spans: List[Tuple[int,int,int]]) -> float:
        # weight more if it starts early (helps capture the first rep)
        t0 = _first_span_start_s(spans, fps)
        if t0 <= 0.6:   bonus = 1.0
        elif t0 <= 1.2: bonus = 0.6
        elif t0 <= 1.8: bonus = 0.3
        else:           bonus = 0.0
        return len(spans) + bonus

    score_simple = _score_variant(kept_simple)
    score_neg    = _score_variant(kept_neg)

    use_variant = "simple" if score_simple >= score_neg else "negspace"
    spans_elbow = kept_simple if use_variant == "simple" else kept_neg

    # ── Optional: force_signal (for testing)
    if force_signal == "elbow":
        use_variant = use_variant  # already elbow
    elif force_signal == "shoulder":
        # Shoulder path below is not used for counting yet (focus on elbow),
        # but we keep the flag for future parity. For now we stick with elbow.
        pass

    # ── Early tiny-span amplitude guard (drops settling motion)
    if spans_elbow:
        amps = [_span_amp(elbow, s) for s in spans_elbow]
        amps_clean = [a for a in amps if a is not None]
        if len(amps_clean) >= 3:
            med_amp = float(np.median(amps_clean[1:]))  # compare first to the rest
            first_amp = amps[0]
            starts_early = (_first_span_start_s(spans_elbow, fps) <= 1.2)
            if first_amp is not None and (
                (starts_early and first_amp < 0.55 * med_amp) or
                (first_amp < 20.0)
            ):
                log.info("Dropping early tiny span: amp=%.1f med=%.1f", first_amp, med_amp)
                spans_elbow = spans_elbow[1:]

    # ── Emit reps
    reps: List[Dict[str, Any]] = []
    for (t1, bot, t2) in spans_elbow:
        dur_s = (t2 - t1) / max(1.0, fps)
        log.info("[COUNT] rep frames=(%d,%d,%d) secs=(%.2f, %.2f, %.2f) signal=elbow_angle",
                 int(t1), int(bot), int(t2),
                 t1/max(1.0,fps), bot/max(1.0,fps), t2/max(1.0,fps))
        reps.append({
            "start_frame": int(t1),
            "bottom_frame": int(bot),
            "end_frame": int(t2),
            "duration_s": float(dur_s),
            "signals": {
                "used_signal": "elbow_angle",
            },
            "good": True,
        })

    # ── Pack debug (what main.py needs for plots/CSV)
    if use_variant == "simple":
        e_tops = [int(x) for x in tops_e_seeded]
        e_bots = [int(x) for x in bots_e]
        e_spans = kept_simple
    else:
        e_tops = dbg_neg["peaks_all"]["tops"]
        e_bots = dbg_neg["peaks_all"]["bottoms"]
        e_spans = kept_neg

    event_debug = {
        "used_signal": "elbow_angle",
        "elbow_events": {
            "kept": len(spans_elbow),
            "best_variant": use_variant,
            "tops": e_tops,
            "bottoms": e_bots,
            "spans": e_spans,
            "drop_simple": drop_simple,
            "drop_neg": drop_neg,
        },
        "winsor": {"lo": winsor_lo, "hi": winsor_hi},
        "series": {
            "elbow_angle": _json_safe_list(elbow),
            "shoulder_y": _json_safe_list(sh_y),
            "shoulder_y_wins": _json_safe_list(sh_y_wins),
        },
        "fps": fps,
    }

    return {
        "reps": reps,
        "summary": summarize(reps),
        "event_debug": event_debug,
    }
