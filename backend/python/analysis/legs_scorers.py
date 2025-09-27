# backend/python/analysis/legs_scorers.py
from __future__ import annotations
from typing import Dict, Any, List, Tuple, Optional
import logging
import numpy as np

from .common import median_smooth, find_events, pair_top_bottom_top, summarize
from side_selector import series_y_for_joint, knee_angle_series_for_side

log = logging.getLogger("aicoach")

# ---------- small helpers ----------

def _winsorize(arr: np.ndarray, lo: float, hi: float) -> np.ndarray:
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


def _json_safe_list(vals) -> List[Optional[float]]:
    if isinstance(vals, np.ndarray):
        vals = vals.tolist()
    out: List[Optional[float]] = []
    for v in vals:
        try:
            f = float(v) if v is not None else None
        except Exception:
            f = None
        out.append(f if (f is not None and np.isfinite(f)) else (None if f is not None else None))
    return out


def _filter_spans(
    spans: List[Tuple[int, int, int]],
    fps: float,
    dur_min: float,
    dur_max: float,
    *,
    slack: float = 1.25,
):
    kept, dropped = [], []
    for a, b, c in spans:
        d = (c - a) / max(1.0, fps)
        (kept if (dur_min <= d <= dur_max * slack) else dropped).append((a, b, c))
    return kept, dropped


def _first_span_start_s(spans: List[Tuple[int, int, int]], fps: float) -> float:
    return (spans[0][0] / max(1.0, fps)) if spans else float("inf")


def _last_span_end_s(spans: List[Tuple[int, int, int]], fps: float, n_frames: int) -> float:
    return ((n_frames - spans[-1][2]) / max(1.0, fps)) if spans else float("inf")


def _span_amp(series: np.ndarray, span: Tuple[int, int, int]) -> Optional[float]:
    """Amplitude in ORIGINAL angle space: avg(top, top) - bottom."""
    a, b, c = span
    if any(i < 0 or i >= len(series) for i in (a, b, c)):
        return None
    va, vb, vc = series[a], series[b], series[c]
    if np.isnan(va) or np.isnan(vb) or np.isnan(vc):
        return None
    return float(((va + vc) / 2.0) - vb)


def _interp_nans_max_gap(arr: np.ndarray, max_gap: int = 3) -> np.ndarray:
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

# ---------- endpoint seeding (same logic as pushups) ----------

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
    known_spans: Optional[List[Tuple[int, int, int]]] = None,
) -> List[int]:
    n = len(series)
    if n == 0:
        return tops
    if np.isnan(series).all():  # guard for all-NaN window
        return tops

    finite = np.where(~np.isnan(series), series, np.nanmedian(series))
    tops, bottoms = sorted(tops), sorted(bottoms)
    w = max(1, int(window_s * fps))

    # gmax & med_top (safe)
    fmax = np.nanmax(finite)
    gmax = float(fmax) if np.isfinite(fmax) else np.nan
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
        return any((a / max(1.0, fps)) <= early for (a, _, _) in known_spans)

    # start seeding
    if not _span_starts_very_early():
        lo, hi = 0, min(n, w)
        if hi - lo >= 3 and np.any(~np.isnan(finite[lo:hi])):
            idx = lo + int(np.nanargmax(finite[lo:hi]))
            pval = float(finite[idx])
            ref = (float(finite[bottoms[0]]) if bottoms else float(np.nanmin(finite[lo:hi])))
            if _ok_similarity(pval) and _ok_contrast(pval, ref) and not _near_existing(idx):
                tops = sorted(tops + [idx])
                log.info("Augmented FIRST top at frame %d (%.2fs)", idx, idx / max(1.0, fps))

    # end seeding
    lo, hi = max(0, n - w), n
    if hi - lo >= 3 and np.any(~np.isnan(finite[lo:hi])):
        idx = lo + int(np.nanargmax(finite[lo:hi]))
        pval = float(finite[idx])
        ref = (float(finite[bottoms[-1]]) if bottoms else float(np.nanmin(finite[lo:hi])))
        if _ok_similarity(pval) and _ok_contrast(pval, ref) and not _near_existing(idx):
            tops = sorted(tops + [idx])
            log.info("Augmented LAST top at frame %d (%.2fs)", idx, idx / max(1.0, fps))

    return tops


# ---------- negspace pairing in ORIGINAL space ----------

def _pair_negspace_in_original(
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
    finite = (
        np.where(~np.isnan(series), series, np.nanmedian(series))
        if not np.isnan(series).all()
        else np.zeros_like(series)
    )
    neg = -finite
    ntops, nbots = find_events(
        neg, fps, peak_is_top=True, min_dist_s=min_dist_s, prom_std=prom_std, width_s=width_s
    )
    orig_tops, orig_bots = nbots, ntops
    if seed_params:
        orig_tops = _augment_endpoint_tops(
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
            skip_if_valid_span_starts_within_s=float(
                seed_params.get("skip_if_valid_span_starts_within_s", 1.0)
            ),
            known_spans=None,
        )
    spans = pair_top_bottom_top(finite, orig_tops, orig_bots, fps, dur_min=dur_min, dur_max=dur_max)
    dbg = {
        "peaks_all": {"tops": [int(x) for x in orig_tops], "bottoms": [int(x) for x in orig_bots]},
        "peaks_btb": {"tops_on_neg": [int(x) for x in ntops], "bottoms_on_neg": [int(x) for x in nbots]},
    }
    return spans, dbg


# ---------- main ----------

def score_squat(
    samples: List[Dict[str, Any]],
    fps: float,
    cfg: Dict[str, Any],
    *,
    primary_side: str = "left",
) -> Dict[str, Any]:
    if not samples:
        return {"reps": [], "summary": {"total_reps": 0, "good_reps": 0, "bad_reps": 0}}

    ev = (cfg.get("events") or {})
    prom_std = float(ev.get("prominence_std", 0.08))
    width_s = float(ev.get("width_sec", 0.06))
    dur_min = float(ev.get("min_rep_duration_s", 0.50))
    dur_max = float(ev.get("max_rep_duration_s", 8.0))
    min_dist_s = float(str(ev.get("min_peak_distance_frames", "0.35s")).replace("s", ""))

    winsor_lo = float(ev.get("winsor_lo", 0.05))
    winsor_hi = float(ev.get("winsor_hi", 0.95))
    seed_cfg = (ev.get("seed") or {})

    # Bookend & extras
    bookend = (ev.get("bookend") or {})
    edge_s_start = float(bookend.get("edge_start_s", 1.2))
    edge_s_end   = float(bookend.get("edge_end_s", 1.0))
    min_amp_deg  = float(bookend.get("min_amp_deg", 40.0))
    min_frac     = float(bookend.get("min_frac_of_median", 0.75))
    pre_start_ignore_s = float(bookend.get("pre_start_ignore_s", 0.6))
    depth_guard_deg    = float(bookend.get("depth_guard_deg", 10.0))

    # series (smooth=5)
    hip_y = series_y_for_joint(samples, "hip", primary_side, conf_thresh=0.15)
    knee  = knee_angle_series_for_side(samples, primary_side, conf_thresh=0.15)

    hip_y = median_smooth(hip_y, 5)
    knee  = median_smooth(knee, 5)

    # repair short gaps to avoid broken plots / missed events
    hip_y = _interp_nans_max_gap(hip_y, max_gap=3)
    knee  = _interp_nans_max_gap(knee,  max_gap=3)

    # recover if knee still too sparse
    def _valid_frac(arr):
        return float(np.isfinite(arr).sum()) / max(1, arr.size)

    if knee.size == 0 or _valid_frac(knee) < 0.20:
        knee_retry = knee_angle_series_for_side(samples, primary_side, conf_thresh=0.05)
        knee = median_smooth(knee_retry, 5)
        knee = _interp_nans_max_gap(knee, max_gap=3)

    knee_unusable = (knee.size == 0) or (_valid_frac(knee) < 0.10)

    hip_y_wins = _winsorize(hip_y, winsor_lo, winsor_hi)

    used_signal = "knee_angle"
    drop_simple_info: List[Tuple[int, int, int]] = []
    drop_neg_info: List[Tuple[int, int, int]] = []
    bookend_dbg = {"head_dropped": False, "tail_dropped": False, "med_amp": None, "first_amp": None, "last_amp": None}

    if not knee_unusable:
        # knee primary
        tops_k, bots_k = find_events(
            knee, fps, peak_is_top=True, min_dist_s=min_dist_s, prom_std=prom_std, width_s=width_s
        )
        tops_k_seeded = _augment_endpoint_tops(
            knee, fps, list(tops_k), list(bots_k),
            window_s=float(seed_cfg.get("window_s", 0.6)),
            peak_frac=float(seed_cfg.get("peak_frac", 0.96)),
            tol_deg=float(seed_cfg.get("tol_deg", 8.0)),
            min_drop_frac=float(seed_cfg.get("min_drop_frac", 0.05)),
            min_drop_deg=float(seed_cfg.get("min_drop_deg", 14.0)),
            exclude_radius_frames=int(seed_cfg.get("exclude_radius_frames", 3)),
            skip_if_valid_span_starts_within_s=float(seed_cfg.get("skip_if_valid_span_starts_within_s", 1.0)),
            known_spans=None,
        )
        spans_simple = pair_top_bottom_top(knee, tops_k_seeded, bots_k, fps, dur_min=dur_min, dur_max=dur_max)
        kept_simple, drop_simple_info = _filter_spans(spans_simple, fps, dur_min, dur_max)

        spans_neg, dbg_neg = _pair_negspace_in_original(
            knee, fps, min_dist_s=min_dist_s, prom_std=prom_std, width_s=width_s,
            dur_min=dur_min, dur_max=dur_max, seed_params=seed_cfg
        )
        kept_neg, drop_neg_info = _filter_spans(spans_neg, fps, dur_min, dur_max)

        def _score_variant(spans):
            t0 = _first_span_start_s(spans, fps)
            return len(spans) + (1.0 if t0 <= 0.6 else 0.6 if t0 <= 1.2 else 0.3 if t0 <= 1.8 else 0.0)

        use_variant = "simple" if _score_variant(kept_simple) >= _score_variant(kept_neg) else "negspace"
        spans_used = kept_simple if use_variant == "simple" else kept_neg

        # ---------- guards ----------
        if spans_used:
            amps = [_span_amp(knee, s) for s in spans_used]
            amps_clean = [a for a in amps if a is not None]
            if len(amps_clean) >= 2:
                med_amp = float(np.median(amps_clean[1:-1])) if len(amps_clean) >= 3 else float(np.median(amps_clean))
                bookend_dbg["med_amp"] = med_amp
                bookend_dbg["first_amp"] = amps[0]
                bookend_dbg["last_amp"] = amps[-1]

            # ignore spans that start extremely early unless amplitude is clearly big
            keep = []
            amp_med_for_early = (np.nanmedian(amps_clean) if amps_clean else 0.0)
            for s, a in zip(spans_used, amps):
                t0 = s[0] / max(1.0, fps)
                if t0 <= pre_start_ignore_s and (a is None or a < max(min_amp_deg, 0.75 * amp_med_for_early)):
                    continue
                keep.append(s)
            spans_used = keep

            # depth guard: drop bottoms much shallower than typical
            if spans_used:
                bottoms_vals = []
                for (_, b, _) in spans_used:
                    if 0 <= b < len(knee) and np.isfinite(knee[b]):
                        bottoms_vals.append(float(knee[b]))
                if len(bottoms_vals) >= 3:
                    med_bottom = float(np.median(bottoms_vals))
                    keep2 = []
                    for (a, b, c) in spans_used:
                        val = float(knee[b]) if 0 <= b < len(knee) and np.isfinite(knee[b]) else np.nan
                        # knee angle: shallower means larger angle at "bottom"
                        if np.isnan(val) or (val > med_bottom + depth_guard_deg):
                            continue
                        keep2.append((a, b, c))
                    spans_used = keep2

            # bookend amplitude at head/tail
            if spans_used and amps_clean:
                starts_early = (_first_span_start_s(spans_used, fps) <= edge_s_start)
                med_amp2 = float(np.median([_span_amp(knee, s) for s in spans_used if _span_amp(knee, s) is not None])) if spans_used else 0.0
                if starts_early and (_span_amp(knee, spans_used[0]) or 0.0) < max(min_amp_deg, min_frac * med_amp2):
                    spans_used = spans_used[1:]; bookend_dbg["head_dropped"] = True
                if spans_used:
                    ends_late = (_last_span_end_s(spans_used, fps, len(knee)) <= edge_s_end)
                    if ends_late and (_span_amp(knee, spans_used[-1]) or 0.0) < max(min_amp_deg, min_frac * med_amp2):
                        spans_used = spans_used[:-1]; bookend_dbg["tail_dropped"] = True

        e_tops = [int(x) for x in (tops_k_seeded if use_variant == "simple" else dbg_neg["peaks_all"]["tops"])]
        e_bots = [int(x) for x in (bots_k if use_variant == "simple" else dbg_neg["peaks_all"]["bottoms"])]
        e_spans = spans_used

    else:
        # fallback to hip-Y
        used_signal = "hip_y"
        finite_hip = (
            np.where(~np.isnan(hip_y), hip_y, np.nanmedian(hip_y))
            if not np.isnan(hip_y).all()
            else np.zeros_like(hip_y)
        )
        tops_h, bots_h = find_events(
            finite_hip, fps, peak_is_top=False,
            min_dist_s=min_dist_s, prom_std=max(0.06, prom_std), width_s=max(0.04, width_s)
        )
        tops_h_seeded = _augment_endpoint_tops(
            finite_hip, fps, list(tops_h), list(bots_h),
            window_s=float(seed_cfg.get("window_s", 0.6)),
            peak_frac=float(seed_cfg.get("peak_frac", 0.96)),
            tol_deg=float(seed_cfg.get("tol_deg", 8.0)),
            min_drop_frac=float(seed_cfg.get("min_drop_frac", 0.05)),
            min_drop_deg=float(seed_cfg.get("min_drop_deg", 14.0)),
            exclude_radius_frames=int(seed_cfg.get("exclude_radius_frames", 3)),
            skip_if_valid_span_starts_within_s=float(seed_cfg.get("skip_if_valid_span_starts_within_s", 1.0)),
            known_spans=None,
        )
        spans_h = pair_top_bottom_top(finite_hip, tops_h_seeded, bots_h, fps, dur_min=dur_min, dur_max=dur_max)
        kept_h, _ = _filter_spans(spans_h, fps, dur_min, dur_max)

        # hip guards analogous to knee
        def _hip_amp(span):
            a, b, c = span
            if any(i < 0 or i >= len(finite_hip) for i in (a, b, c)):
                return None
            va, vb, vc = finite_hip[a], finite_hip[b], finite_hip[c]
            if np.isnan(va) or np.isnan(vb) or np.isnan(vc):
                return None
            return float(abs(((va + vc) / 2.0) - vb))

        spans_used = kept_h
        if spans_used:
            amps = [_hip_amp(s) for s in spans_used]
            amps_clean = [a for a in amps if a is not None]

            # very-early ignore
            keep = []
            amp_med_for_early = (np.nanmedian(amps_clean) if amps_clean else 0.0)
            for s, a in zip(spans_used, amps):
                t0 = s[0] / max(1.0, fps)
                if t0 <= pre_start_ignore_s and (a is None or a < max(min_amp_deg, 0.75 * amp_med_for_early)):
                    continue
                keep.append(s)
            spans_used = keep

            # bookends
            if spans_used and amps_clean:
                med_amp2 = float(np.median(amps_clean))
                starts_early = (_first_span_start_s(spans_used, fps) <= edge_s_start)
                if starts_early and (_hip_amp(spans_used[0]) or 0.0) < max(min_amp_deg, min_frac * med_amp2):
                    spans_used = spans_used[1:]; bookend_dbg["head_dropped"] = True
                if spans_used:
                    ends_late = (_last_span_end_s(spans_used, fps, len(finite_hip)) <= edge_s_end)
                    if ends_late and (_hip_amp(spans_used[-1]) or 0.0) < max(min_amp_deg, min_frac * med_amp2):
                        spans_used = spans_used[:-1]; bookend_dbg["tail_dropped"] = True

        e_tops, e_bots, e_spans = [int(x) for x in tops_h_seeded], [int(x) for x in bots_h], spans_used

    # Emit reps
    reps: List[Dict[str, Any]] = []
    for (t1, bot, t2) in e_spans:
        dur_s = (t2 - t1) / max(1.0, fps)
        log.info(
            "[COUNT] SQUAT frames=(%d,%d,%d) secs=(%.2f, %.2f, %.2f) signal=%s",
            int(t1), int(bot), int(t2),
            t1 / max(1.0, fps), bot / max(1.0, fps), t2 / max(1.0, fps), used_signal
        )
        reps.append({
            "start_frame": int(t1),
            "bottom_frame": int(bot),
            "end_frame": int(t2),
            "duration_s": float(dur_s),
            "signals": {"used_signal": used_signal},
            "good": True,
        })

    # Debug payload
    event_key = "knee_events" if used_signal == "knee_angle" else "hip_events"
    event_debug = {
        "used_signal": used_signal,
        event_key: {
            "kept": len(e_spans),
            "tops": e_tops,
            "bottoms": e_bots,
            "spans": e_spans,
            "drop_simple": drop_simple_info,
            "drop_neg": drop_neg_info,
            "bookend": bookend_dbg,
        },
        "winsor": {"lo": winsor_lo, "hi": winsor_hi},
        "series": {
            "knee_angle": _json_safe_list(knee),
            "hip_y": _json_safe_list(hip_y),
            "hip_y_wins": _json_safe_list(hip_y_wins),
        },
        "fps": fps,
    }

    return {
        "reps": reps,
        "summary": summarize(reps),
        "event_debug": event_debug,
    }
