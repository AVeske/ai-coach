# backend/python/analysis/legs_scorers.py
from __future__ import annotations
from typing import Dict, Any, List, Tuple, Optional
import logging
import numpy as np

from .common import (
    median_smooth, find_events, pair_top_bottom_top, summarize,
    winsorize, json_safe_list, filter_spans,
    first_span_start_s, span_amp,
    augment_endpoint_tops, pair_negspace_in_original, last_span_end_s,
    interp_nans_max_gap, signal_knee_angle, rep_counter,
)
from side_selector import series_y_for_joint, knee_angle_series_for_side

log = logging.getLogger("aicoach")


# ---------- SQUAT ----------

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
    width_s  = float(ev.get("width_sec", 0.06))
    dur_min  = float(ev.get("min_rep_duration_s", 0.50))
    dur_max  = float(ev.get("max_rep_duration_s", 8.0))
    # allow "0.35s" or 0.35
    _md = ev.get("min_peak_distance_frames", "0.35s")
    try:
        min_dist_s = float(str(_md).replace("s", ""))
    except Exception:
        min_dist_s = 0.35

    winsor_lo = float(ev.get("winsor_lo", 0.05))
    winsor_hi = float(ev.get("winsor_hi", 0.95))
    seed_cfg  = (ev.get("seed") or {})

    # Bookend / extra guards
    bookend = (ev.get("bookend") or {})
    edge_s_start        = float(bookend.get("edge_start_s", 1.2))
    edge_s_end          = float(bookend.get("edge_end_s", 1.0))
    min_amp_deg         = float(bookend.get("min_amp_deg", 40.0))
    min_frac            = float(bookend.get("min_frac_of_median", 0.75))
    pre_start_ignore_s  = float(bookend.get("pre_start_ignore_s", 0.6))
    depth_guard_deg     = float(bookend.get("depth_guard_deg", 10.0))

    # series
    hip_y = series_y_for_joint(samples, "hip", primary_side, conf_thresh=0.15)
    knee  = knee_angle_series_for_side(samples, primary_side, conf_thresh=0.15)
    hip_y = median_smooth(hip_y, 5)
    knee  = median_smooth(knee, 5)

    # repair short gaps (avoids event breaks / ugly plots)
    hip_y = interp_nans_max_gap(hip_y, max_gap=3)
    knee  = interp_nans_max_gap(knee,  max_gap=3)

    # retry knee if too sparse
    def _valid_frac(arr: np.ndarray) -> float:
        return float(np.isfinite(arr).sum()) / max(1, arr.size)

    if knee.size == 0 or _valid_frac(knee) < 0.20:
        knee_retry = knee_angle_series_for_side(samples, primary_side, conf_thresh=0.05)
        knee = median_smooth(knee_retry, 5)
        knee = interp_nans_max_gap(knee, max_gap=3)

    knee_unusable = (knee.size == 0) or (_valid_frac(knee) < 0.10)
    hip_y_wins = winsorize(hip_y, winsor_lo, winsor_hi)  # debug/plots only

    used_signal = "knee_angle"
    drop_simple_info: List[Tuple[int, int, int]] = []
    drop_neg_info: List[Tuple[int, int, int]] = []
    bookend_dbg = {"head_dropped": False, "tail_dropped": False, "med_amp": None, "first_amp": None, "last_amp": None}

    if not knee_unusable:
        # knee primary
        tops_k, bots_k = find_events(
            knee, fps, peak_is_top=True, min_dist_s=min_dist_s, prom_std=prom_std, width_s=width_s
        )
        tops_k_seeded = augment_endpoint_tops(
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
        kept_simple, drop_simple_info = filter_spans(spans_simple, fps, dur_min, dur_max)

        spans_neg, dbg_neg = pair_negspace_in_original(
            knee, fps, min_dist_s=min_dist_s, prom_std=prom_std, width_s=width_s,
            dur_min=dur_min, dur_max=dur_max, seed_params=seed_cfg
        )
        kept_neg, drop_neg_info = filter_spans(spans_neg, fps, dur_min, dur_max)

        def _score_variant(spans: List[Tuple[int, int, int]]) -> float:
            t0 = first_span_start_s(spans, fps)
            return len(spans) + (1.0 if t0 <= 0.6 else 0.6 if t0 <= 1.2 else 0.3 if t0 <= 1.8 else 0.0)

        use_variant = "simple" if _score_variant(kept_simple) >= _score_variant(kept_neg) else "negspace"
        spans_used = kept_simple if use_variant == "simple" else kept_neg

        # guards
        if spans_used:
            amps = [span_amp(knee, s) for s in spans_used]
            amps_clean = [a for a in amps if a is not None]
            if len(amps_clean) >= 2:
                med_amp = float(np.median(amps_clean[1:-1])) if len(amps_clean) >= 3 else float(np.median(amps_clean))
                bookend_dbg["med_amp"] = med_amp
                bookend_dbg["first_amp"] = amps[0]
                bookend_dbg["last_amp"] = amps[-1]

            # ignore very-early tiny span
            keep = []
            amp_med_for_early = (float(np.nanmedian(amps_clean)) if amps_clean else 0.0)
            for s, a in zip(spans_used, amps):
                t0 = s[0] / max(1.0, fps)
                if t0 <= pre_start_ignore_s and (a is None or a < max(min_amp_deg, 0.75 * amp_med_for_early)):
                    continue
                keep.append(s)
            spans_used = keep

            # depth guard: drop bottoms that are much shallower (knee angle too large) than typical
            if spans_used:
                bottoms_vals = []
                for (_, b, _) in spans_used:
                    if 0 <= b < len(knee) and np.isfinite(knee[b]):
                        bottoms_vals.append(float(knee[b]))
                if len(bottoms_vals) >= 3:
                    med_bottom = float(np.median(bottoms_vals))
                    keep2: List[Tuple[int, int, int]] = []
                    for (a, b, c) in spans_used:
                        val = float(knee[b]) if 0 <= b < len(knee) and np.isfinite(knee[b]) else np.nan
                        # knee: shallower → larger angle at bottom
                        if np.isnan(val) or (val > med_bottom + depth_guard_deg):
                            continue
                        keep2.append((a, b, c))
                    spans_used = keep2

            # bookend head/tail
            if spans_used and amps_clean:
                starts_early = (first_span_start_s(spans_used, fps) <= edge_s_start)
                med_amp2 = float(np.median([span_amp(knee, s) for s in spans_used if span_amp(knee, s) is not None])) if spans_used else 0.0
                if starts_early and (span_amp(knee, spans_used[0]) or 0.0) < max(min_amp_deg, min_frac * med_amp2):
                    spans_used = spans_used[1:]; bookend_dbg["head_dropped"] = True
                if spans_used:
                    ends_late = (last_span_end_s(spans_used, fps, len(knee)) <= edge_s_end)
                    if ends_late and (span_amp(knee, spans_used[-1]) or 0.0) < max(min_amp_deg, min_frac * med_amp2):
                        spans_used = spans_used[:-1]; bookend_dbg["tail_dropped"] = True

        e_tops = [int(x) for x in (tops_k_seeded if use_variant == "simple" else dbg_neg["peaks_all"]["tops"])]
        e_bots = [int(x) for x in (bots_k if use_variant == "simple" else dbg_neg["peaks_all"]["bottoms"])]
        e_spans = spans_used

    else:
        # fallback to hip-Y
        used_signal = "hip_y"
        finite_hip = np.where(~np.isnan(hip_y), hip_y, np.nanmedian(hip_y)) if not np.isnan(hip_y).all() else np.zeros_like(hip_y)
        tops_h, bots_h = find_events(
            finite_hip, fps, peak_is_top=False,
            min_dist_s=min_dist_s, prom_std=max(0.06, prom_std), width_s=max(0.04, width_s)
        )
        tops_h_seeded = augment_endpoint_tops(
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
        kept_h, _ = filter_spans(spans_h, fps, dur_min, dur_max)

        def _hip_amp(span: Tuple[int, int, int]) -> Optional[float]:
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
            keep: List[Tuple[int, int, int]] = []
            amp_med_for_early = (float(np.nanmedian(amps_clean)) if amps_clean else 0.0)
            for s, a in zip(spans_used, amps):
                t0 = s[0] / max(1.0, fps)
                if t0 <= pre_start_ignore_s and (a is None or a < max(min_amp_deg, 0.75 * amp_med_for_early)):
                    continue
                keep.append(s)
            spans_used = keep

            # bookends
            if spans_used and amps_clean:
                med_amp2 = float(np.median(amps_clean))
                starts_early = (first_span_start_s(spans_used, fps) <= edge_s_start)
                if starts_early and (_hip_amp(spans_used[0]) or 0.0) < max(min_amp_deg, min_frac * med_amp2):
                    spans_used = spans_used[1:]; bookend_dbg["head_dropped"] = True
                if spans_used:
                    ends_late = (last_span_end_s(spans_used, fps, len(finite_hip)) <= edge_s_end)
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
            "knee_angle": json_safe_list(knee),
            "hip_y": json_safe_list(hip_y),
            "hip_y_wins": json_safe_list(hip_y_wins),
        },
        "fps": fps,
    }

    return {"reps": reps, "summary": summarize(reps), "event_debug": event_debug}


# ---------- LEG EXTENSION ----------

def score_leg_extension(samples, fps, cfg, *, primary_side: str = "left"):
    """
    Same behavior, but routed through the generic counter.
    """
    # Ensure cfg carries your old params; this just forwards them.
    # Signal: knee angle; Variant: auto (simple vs negspace); Bookend guards: from cfg.events.bookend
    return rep_counter(
        samples, fps, cfg,
        primary_side=primary_side,
        signal_factory=signal_knee_angle,
        signal_name="knee_angle",
    )

def score_hamstring_curl(samples, fps, cfg, *, primary_side: str = "left"):
    """
    Hamstring curl prefers the negspace variant. We hint that via cfg.
    """
    # You can set this in YAML; doing it here defensively if missing:
    ev = cfg.setdefault("events", {})
    ev.setdefault("prefer_negspace", True)  # gentle nudge; rep_counter still scores both
    # If you want to *force* negspace, add ev["force_variant"] = "negspace" to your YAML or here.

    return rep_counter(
        samples, fps, cfg,
        primary_side=primary_side,
        signal_factory=signal_knee_angle,
        signal_name="knee_angle",
    )