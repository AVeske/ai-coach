from __future__ import annotations
from typing import List, Dict, Any, Tuple, Optional, Callable
import numpy as np
import logging
from scipy.signal import find_peaks

log = logging.getLogger("aicoach")

# ────────────────────────── math/smoothing ──────────────────────────

def xy(v):
    if not v:
        return None
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
        lo, hi = max(0, i - k), min(len(arr), i + k + 1)
        w = arr[lo:hi]
        w = w[~np.isnan(w)]
        out[i] = float(np.median(w)) if len(w) else np.nan
    return out

def interp_nans_max_gap(arr: np.ndarray, max_gap: int = 3) -> np.ndarray:
    """Linearly interpolate NaN runs up to max_gap; leave longer runs as NaN."""
    x = np.array(arr, dtype=float)
    n = len(x)
    if n == 0:
        return x
    isn = np.isnan(x)
    if not isn.any():
        return x
    idx = np.arange(n)
    i = 0
    while i < n:
        if not isn[i]:
            i += 1
            continue
        j = i
        while j < n and isn[j]:
            j += 1
        gap = j - i
        if gap <= max_gap:
            left = i - 1
            right = j
            if left >= 0 and right < n and not np.isnan(x[left]) and not np.isnan(x[right]):
                x[i:j] = np.interp(idx[i:j], [left, right], [x[left], x[right]])
        i = j
    return x

# ───────────────────────── event detection / pairing ─────────────────────────

def find_events(
    primary: np.ndarray,
    fps: float,
    *,
    peak_is_top: bool = True,
    min_dist_s: float = 0.30,
    prom_std: float = 0.18,
    width_s: float = 0.08,
):
    """Peak picking with NaN-safe fallback to median; returns (tops, bottoms) indices."""
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

def pair_top_bottom_top(
    primary: np.ndarray,
    tops,
    bottoms,
    fps: float,
    *,
    dur_min: float = 0.45,
    dur_max: float = 7.0,
):
    """Pair events into (top, bottom, top) spans obeying duration limits."""
    events = sorted([(int(i), "top") for i in tops] + [(int(i), "bottom") for i in bottoms])
    reps, last_top = [], None
    for idx, typ in events:
        if typ == "top":
            if last_top is None:
                last_top = idx
            else:
                mids = [i for i, t2 in events if t2 == "bottom" and last_top < i < idx]
                if mids:
                    i_bot = int(min(mids, key=lambda k: primary[k] if not np.isnan(primary[k]) else 9e9))
                    dur = (idx - last_top) / max(1.0, fps)
                    if dur_min <= dur <= dur_max:
                        reps.append((last_top, i_bot, idx))
                last_top = idx
    return reps

# ───────────────────────── grading / summaries ─────────────────────────

def tier_of(value: Optional[float], tiers: Dict[str, List[float]]) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "unknown"
    for name, rng in tiers.items():
        lo, hi = float(rng[0]), float(rng[1])
        if lo <= float(value) <= hi:
            return name
    return "unknown"

def summarize(per_rep: List[Dict[str, Any]]):
    total = len(per_rep)
    bad = sum(1 for r in per_rep if not r.get("good", False))
    good = total - bad
    flags: Dict[str, int] = {}
    for r in per_rep:
        for f in r.get("flags", []):
            flags[f] = flags.get(f, 0) + 1
    out = {"total_reps": total, "good_reps": good, "bad_reps": bad}
    out.update({f"{k}_reps": v for k, v in flags.items()})
    return out

# ───────────────────────── utilities (public) ─────────────────────────

def winsorize(arr: np.ndarray, lo: float, hi: float) -> np.ndarray:
    """Percentile-clip values into [lo, hi] (lo/hi ∈ [0,1]). NaN-safe."""
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

def json_safe_list(vals: List[float] | np.ndarray) -> List[Optional[float]]:
    """Convert to JSON-safe floats (NaN/Inf -> None)."""
    if isinstance(vals, np.ndarray):
        vals = vals.tolist()
    out: List[Optional[float]] = []
    for v in vals:
        if v is None:
            out.append(None); continue
        try:
            f = float(v)
        except Exception:
            out.append(None); continue
        out.append(f if np.isfinite(f) else None)
    return out

def filter_spans(
    spans: List[Tuple[int, int, int]],
    fps: float,
    dur_min: float,
    dur_max: float,
    *,
    slack: float = 1.25,
):
    """Keep spans with duration ∈ [dur_min, dur_max*slack]."""
    kept, dropped = [], []
    for a, b, c in spans:
        d = (c - a) / max(1.0, fps)
        (kept if (dur_min <= d <= dur_max * slack) else dropped).append((a, b, c))
    return kept, dropped

def first_span_start_s(spans: List[Tuple[int, int, int]], fps: float) -> float:
    return (spans[0][0] / max(1.0, fps)) if spans else float("inf")

def last_span_end_s(spans: List[Tuple[int, int, int]], fps: float, n_frames: int) -> float:
    """Seconds from last span end to the end of the series (smaller => closer to tail)."""
    return ((n_frames - spans[-1][2]) / max(1.0, fps)) if spans else float("inf")

def span_amp(series: np.ndarray, span: Tuple[int, int, int]) -> Optional[float]:
    """Amplitude in ORIGINAL space: avg(top, top) - bottom (great for elbow/knee/hip angles)."""
    a, b, c = span
    if any(i < 0 or i >= len(series) for i in (a, b, c)):
        return None
    va, vb, vc = series[a], series[b], series[c]
    if np.isnan(va) or np.isnan(vb) or np.isnan(vc):
        return None
    return float(((va + vc) / 2.0) - vb)

# ───────────────────── endpoint seeding & negspace pairing ─────────────────────

def augment_endpoint_tops(
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
    known_spans: Optional[List[Tuple[int, int, int]]] = None,
) -> List[int]:
    """
    Add synthetic TOPS near start/end only if they look like true lockouts.
    Works on the ORIGINAL space of the provided series.
    """
    n = len(series)
    if n == 0 or np.isnan(series).all():
        return tops

    finite = np.where(~np.isnan(series), series, np.nanmedian(series))
    tops = sorted(int(x) for x in tops)
    bottoms = sorted(int(x) for x in bottoms) if bottoms else []
    w = max(1, int(window_s * fps))

    fmax = np.nanmax(finite)
    gmax = float(fmax) if np.isfinite(fmax) else np.nan
    med_top: Optional[float] = None
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
        return any((a / max(1.0, fps)) <= early for (a, _, _) in known_spans)

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
                log.info("Augmented FIRST top at frame %d (%.2fs)", idx, idx / max(1.0, fps))

    # END seeding
    lo, hi = max(0, n - w), n
    if hi - lo >= 3 and np.any(~np.isnan(finite[lo:hi])):
        idx = lo + int(np.nanargmax(finite[lo:hi]))
        pval = float(finite[idx])
        ref = (float(finite[bottoms[-1]]) if bottoms and np.isfinite(finite[bottoms[-1]])
               else float(np.nanmin(finite[lo:hi])))
        if _ok_similarity(pval) and _ok_contrast(pval, ref) and not _near_existing(idx):
            tops = sorted(tops + [idx])
            log.info("Augmented LAST top at frame %d (%.2fs)", idx, idx / max(1.0, fps))

    return tops

def pair_negspace_in_original(
    series: np.ndarray,
    fps: float,
    *,
    min_dist_s: float,
    prom_std: float,
    width_s: float,
    dur_min: float,
    dur_max: float,
    seed_params: Dict[str, float] | None = None,
) -> Tuple[List[Tuple[int, int, int]], Dict[str, Any]]:
    """
    Detect peaks on -series (make bottoms salient), then pair on ORIGINAL series
    so spans are Top–Bottom–Top in original space.
    """
    if series.size == 0:
        return [], {
            "peaks_all": {"tops": [], "bottoms": []},
            "peaks_btb": {"tops_on_neg": [], "bottoms_on_neg": []},
        }

    finite = np.where(~np.isnan(series), series, np.nanmedian(series))
    neg = -finite
    ntops, nbots = find_events(
        neg, fps, peak_is_top=True, min_dist_s=min_dist_s, prom_std=prom_std, width_s=width_s
    )
    orig_tops, orig_bots = nbots, ntops

    if seed_params:
        orig_tops = augment_endpoint_tops(
            finite,
            fps,
            list(orig_tops),
            list(orig_bots),
            window_s=float(seed_params.get("window_s", 0.6)),
            peak_frac=float(seed_params.get("peak_frac", 0.96)),
            tol_deg=float(seed_params.get("tol_deg", 8.0)),
            min_drop_frac=float(seed_params.get("min_drop_frac", 0.05)),
            min_drop_deg=float(seed_params.get("min_drop_deg", 14.0)),
            exclude_radius_frames=int(seed_params.get("exclude_radius_frames", 3)),
            skip_if_valid_span_starts_within_s=float(seed_params.get("skip_if_valid_span_starts_within_s", 1.0)),
            known_spans=None,
        )

    spans = pair_top_bottom_top(finite, orig_tops, orig_bots, fps, dur_min=dur_min, dur_max=dur_max)
    dbg = {
        "peaks_all": {"tops": [int(x) for x in orig_tops], "bottoms": [int(x) for x in orig_bots]},
        "peaks_btb": {"tops_on_neg": [int(x) for x in ntops], "bottoms_on_neg": [int(x) for x in nbots]},
    }
    return spans, dbg

# ───────────────────────── generic rep counter ─────────────────────────

def rep_counter(
    samples: List[Dict[str, Any]],
    fps: float,
    cfg: Dict[str, Any],
    *,
    primary_side: str,
    signal_factory: Callable[[List[Dict[str, Any]], str], np.ndarray],
    signal_name: str,
) -> Dict[str, Any]:
    """
    Generic T–B–T rep detector with:
      - peak picking (simple & negspace)
      - endpoint seeding
      - early/late tiny-rep guard ("bookend")
    """

    if not samples:
        return {"reps": [], "summary": {"total_reps": 0, "good_reps": 0, "bad_reps": 0}}

    ev = (cfg.get("events") or {})
    # Accept numeric or "0.28s"
    _md = ev.get("min_peak_distance_frames", 0.28)
    try:
        min_dist_s = float(str(_md).replace("s", ""))
    except Exception:
        min_dist_s = 0.28

    prom_std = float(ev.get("prominence_std", 0.08))
    width_s  = float(ev.get("width_sec", 0.05))
    dur_min  = float(ev.get("min_rep_duration_s", 0.40))
    dur_max  = float(ev.get("max_rep_duration_s", 7.0))
    wins_lo  = float(ev.get("winsor_lo", 0.10))
    wins_hi  = float(ev.get("winsor_hi", 0.90))
    seed_cfg = (ev.get("seed") or {})

    # Bookend guard
    bookend      = (ev.get("bookend") or {})
    edge_s_start = float(bookend.get("edge_start_s", 1.0))
    edge_s_end   = float(bookend.get("edge_end_s", 1.0))
    min_amp_abs  = float(bookend.get("min_amp_deg", 25.0))
    min_frac_med = float(bookend.get("min_frac_of_median", 0.60))
    pre_ignore   = float(bookend.get("pre_start_ignore_s", 0.0))  # optional

    # Build series
    series = signal_factory(samples, primary_side)
    series_wins = winsorize(series, wins_lo, wins_hi)

    # Simple peaks in original space
    tops, bots = find_events(series, fps, peak_is_top=True,
                             min_dist_s=min_dist_s, prom_std=prom_std, width_s=width_s)
    tops_seeded = augment_endpoint_tops(
        series, fps, list(tops), list(bots),
        window_s=float(seed_cfg.get("window_s", 0.6)),
        peak_frac=float(seed_cfg.get("peak_frac", 0.96)),
        tol_deg=float(seed_cfg.get("tol_deg", 8.0)),
        min_drop_frac=float(seed_cfg.get("min_drop_frac", 0.05)),
        min_drop_deg=float(seed_cfg.get("min_drop_deg", 14.0)),
        exclude_radius_frames=int(seed_cfg.get("exclude_radius_frames", 3)),
        skip_if_valid_span_starts_within_s=float(seed_cfg.get("skip_if_valid_span_starts_within_s", 1.0)),
        known_spans=None,
    )
    spans_simple = pair_top_bottom_top(series, tops_seeded, bots, fps, dur_min=dur_min, dur_max=dur_max)
    kept_simple, drop_simple = filter_spans(spans_simple, fps, dur_min, dur_max)

    # Negspace variant
    spans_neg, dbg_neg = pair_negspace_in_original(
        series, fps,
        min_dist_s=min_dist_s, prom_std=prom_std, width_s=width_s,
        dur_min=dur_min, dur_max=dur_max, seed_params=seed_cfg
    )
    kept_neg, drop_neg = filter_spans(spans_neg, fps, dur_min, dur_max)

    # Choose by count + early-start bonus
    def _score_variant(spans: List[Tuple[int, int, int]]) -> float:
        t0 = first_span_start_s(spans, fps)
        if t0 <= 0.6:   bonus = 1.0
        elif t0 <= 1.2: bonus = 0.6
        elif t0 <= 1.8: bonus = 0.3
        else:           bonus = 0.0
        return len(spans) + bonus

    use_simple = (_score_variant(kept_simple) >= _score_variant(kept_neg))
    spans_used = kept_simple if use_simple else kept_neg

    # Optionally ignore a too-early first span
    if spans_used and pre_ignore > 0:
        t0 = first_span_start_s(spans_used, fps)
        if t0 <= pre_ignore:
            log.info("Dropping pre-start span at %.2fs (≤ %.2fs)", t0, pre_ignore)
            spans_used = spans_used[1:]

    # Bookend amplitude guard
    if spans_used:
        amps = [span_amp(series, s) for s in spans_used]
        amps_clean = [a for a in amps if a is not None]
        if len(amps_clean) >= 2:
            # median of middle reps (if any), else of all
            if len(spans_used) >= 3:
                mid_amps = [amps[i] for i in range(1, len(amps) - 1) if amps[i] is not None]
                med_amp = float(np.median(np.asarray(mid_amps))) if mid_amps else float(np.median(np.asarray(amps_clean)))
            else:
                med_amp = float(np.median(np.asarray(amps_clean)))

            # drop first if very early and tiny
            starts_early = (first_span_start_s(spans_used, fps) <= edge_s_start)
            if starts_early and amps[0] is not None and (amps[0] < max(min_amp_abs, min_frac_med * med_amp)):
                log.info("Dropping FIRST span: amp=%.1f med=%.1f thresh=%.1f",
                         amps[0], med_amp, max(min_amp_abs, min_frac_med * med_amp))
                spans_used = spans_used[1:]
                amps = amps[1:]

            # drop last if very late and tiny
            if spans_used:
                ends_late = (last_span_end_s(spans_used, fps, len(series)) <= edge_s_end)
                if ends_late and amps[-1] is not None and (amps[-1] < max(min_amp_abs, min_frac_med * med_amp)):
                    log.info("Dropping LAST span: amp=%.1f med=%.1f thresh=%.1f",
                             amps[-1], med_amp, max(min_amp_abs, min_frac_med * med_amp))
                    spans_used = spans_used[:-1]

    # Emit reps
    reps: List[Dict[str, Any]] = []
    for (t1, bot, t2) in spans_used:
        reps.append({
            "start_frame": int(t1),
            "bottom_frame": int(bot),
            "end_frame": int(t2),
            "duration_s": float((t2 - t1) / max(1.0, fps)),
            "signals": {"used_signal": signal_name},
            "good": True,
        })

    # Debug
    if use_simple:
        e_tops = [int(x) for x in tops_seeded]
        e_bots = [int(x) for x in bots]
        e_spans = kept_simple
    else:
        e_tops = dbg_neg["peaks_all"]["tops"]
        e_bots = dbg_neg["peaks_all"]["bottoms"]
        e_spans = kept_neg

    event_debug = {
        "used_signal": signal_name,
        f"{signal_name}_events": {
            "kept": len(spans_used),
            "best_variant": "simple" if use_simple else "negspace",
            "tops": e_tops,
            "bottoms": e_bots,
            "spans": e_spans,
            "drop_simple": drop_simple,
            "drop_neg": drop_neg,
        },
        "winsor": {"lo": wins_lo, "hi": wins_hi},
        "series": {
            signal_name: json_safe_list(series),
            f"{signal_name}_wins": json_safe_list(series_wins),
        },
        "fps": fps,
    }

    return {
        "reps": reps,
        "summary": summarize(reps),
        "event_debug": event_debug,
    }

# ───────────────────────── ready-made signal factories ─────────────────────────
# Keep imports local (inside functions) to avoid circular imports with side_selector.

def signal_elbow_angle(samples, side) -> np.ndarray:
    """Elbow flex/extend (push-ups, bench, pulldown, rows, dips…)."""
    from side_selector import elbow_angle_series_for_side
    return median_smooth(elbow_angle_series_for_side(samples, side, conf_thresh=0.15), 5)

def signal_knee_angle(samples, side) -> np.ndarray:
    """Knee flex/extend (leg extension / leg curl)."""
    from side_selector import knee_angle_series_for_side
    return median_smooth(knee_angle_series_for_side(samples, side, conf_thresh=0.15), 5)

def signal_shoulder_y(samples, side) -> np.ndarray:
    """Vertical shoulder travel (useful fallback for pull-ups/rows). Screen-space Y."""
    from side_selector import series_y_for_joint
    return median_smooth(series_y_for_joint(samples, "shoulder", side, conf_thresh=0.15), 5)

def signal_wrist_y(samples, side) -> np.ndarray:
    from side_selector import series_y_for_joint
    return median_smooth(series_y_for_joint(samples, "wrist", side, conf_thresh=0.15), 5)

def signal_wrist_x(samples, side) -> np.ndarray:
    from side_selector import series_x_for_joint
    return median_smooth(series_x_for_joint(samples, "wrist", side, conf_thresh=0.15), 5)
