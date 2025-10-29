# backend/python/analysis/rep_quality.py
from __future__ import annotations
from typing import Dict, Any, List, Tuple, Optional
import numpy as np

# Optional: if you already have span_amp in .common you can import it.
# For portability, we re-implement the same logic locally.
def _span_delta_mid_vs_bottom(series: np.ndarray, span: Tuple[int, int, int]) -> Optional[float]:
    """
    | ((val at start + val at end)/2) - (val at bottom) |
    Works for both angles and displacement-like series.
    Returns None if any index invalid or NaN.
    """
    a, b, c = span
    n = len(series)
    if any(i < 0 or i >= n for i in (a, b, c)):
        return None
    va, vb, vc = series[a], series[b], series[c]
    if np.isnan(va) or np.isnan(vb) or np.isnan(vc):
        return None
    return float(abs(((va + vc) / 2.0) - vb))


# ----------------------------- helpers -----------------------------

def _get(cfg: Dict[str, Any], path: str, default=None):
    """
    Safe config getter with dotted path, e.g. _get(cfg, "metrics.rom_deg.min_delta", 25)
    """
    cur: Any = cfg
    for key in path.split("."):
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def _classify_tier(value: float, tiers: Dict[str, List[float]], higher_is_better: bool = True) -> str:
    """
    Classify a scalar into 'optimal' | 'acceptable' | 'suboptimal' using YAML tiers:
      tiers:
        optimal:    [lo, hi]
        acceptable: [lo, hi]
        suboptimal: [lo, hi]
    If a band is missing, it's ignored. First match wins (order: optimal, acceptable, suboptimal).
    """
    if value is None:
        return "unknown"

    # Normalize and guard
    def _in_band(v: float, band: Optional[List[float]]) -> bool:
        if not band or len(band) != 2:
            return False
        lo, hi = float(band[0]), float(band[1])
        return (lo <= v <= hi) if higher_is_better else (hi <= v <= lo)

    # We try optimal -> acceptable -> suboptimal in that order
    if _in_band(value, tiers.get("optimal")):
        return "optimal"
    if _in_band(value, tiers.get("acceptable")):
        return "acceptable"
    if _in_band(value, tiers.get("suboptimal")):
        return "suboptimal"
    # If nothing matched, choose based on directionality as a fall-through heuristic
    # (but prefer to fully specify tiers in YAML).
    if higher_is_better:
        # if below all known lows, call it suboptimal
        return "suboptimal"
    else:
        return "suboptimal"


def _add_flag(flags: List[str], flag: Optional[str]):
    if flag and flag not in flags:
        flags.append(flag)


# ----------------------------- core per-rep evaluation -----------------------------

def _eval_rep_metrics(
    span: Tuple[int, int, int],
    fps: float,
    series_map: Dict[str, np.ndarray],
    cfg: Dict[str, Any],
    *,
    primary_signal: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Compute tempo (total/ecc/con), ROM (deg or disp), lockout/depth guards, and flags per configured tiers.
    Returns a dict with fields and flags; 'good' is decided later using bad_flags.
    """
    a, b, c = span
    total_s = (c - a) / max(1.0, fps)
    ecc_s   = (b - a) / max(1.0, fps)  # down phase
    con_s   = (c - b) / max(1.0, fps)  # up phase

    metrics_out: Dict[str, Any] = {
        "tempo": {
            "total_s": float(total_s),
            "ecc_s": float(ecc_s),
            "con_s": float(con_s),
            "tiers": {}
        },
        "flags": [],
    }

    flag_labels = _get(cfg, "flag_labels", {}) or {}
    # Helper to convert canonical flag -> human label later
    def _label(flag_key: str) -> str:
        return str(flag_labels.get(flag_key, flag_key.replace("_", " ").title()))

    # ---------------- TEMPO TIERS ----------------
    tempo_tiers = _get(cfg, "metrics.tempo_s.tiers", None)
    if tempo_tiers:
        t_tier = _classify_tier(total_s, tempo_tiers, higher_is_better=False)  # shorter isn't better; we use ranges
        metrics_out["tempo"]["tiers"]["total"] = t_tier
        if t_tier == "suboptimal":
            _add_flag(metrics_out["flags"], "too_fast_or_slow")

    ecc_tiers = _get(cfg, "metrics.eccentric_s.tiers", None)
    if ecc_tiers:
        e_tier = _classify_tier(ecc_s, ecc_tiers, higher_is_better=False)
        metrics_out["tempo"]["tiers"]["ecc"] = e_tier
        if e_tier == "suboptimal":
            _add_flag(metrics_out["flags"], "eccentric_tempo_off")

    con_tiers = _get(cfg, "metrics.concentric_s.tiers", None)
    if con_tiers:
        c_tier = _classify_tier(con_s, con_tiers, higher_is_better=False)
        metrics_out["tempo"]["tiers"]["con"] = c_tier
        if c_tier == "suboptimal":
            _add_flag(metrics_out["flags"], "concentric_tempo_off")

    # ---------------- ROM ----------------
    # Determine which metric we should evaluate first (deg vs disp)
    rom_deg_cfg   = _get(cfg, "metrics.rom_deg", None)
    rom_disp_cfg  = _get(cfg, "metrics.rom_disp", None)

    # Pick a series for ROM. Use primary_signal if its array exists; else try common fallbacks.
    candidate_keys = []
    if primary_signal:
        candidate_keys.append(primary_signal)
    candidate_keys.extend(["elbow_angle", "knee_angle", "shoulder_y", "hip_y"])

    rom_series = None
    rom_key_used = None
    for k in candidate_keys:
        arr = series_map.get(k)
        if isinstance(arr, np.ndarray) and arr.size:
            rom_series = arr
            rom_key_used = k
            break

    if rom_deg_cfg and rom_series is not None and "angle" in (rom_key_used or ""):
        # Angle ROM (degrees)
        delta = _span_delta_mid_vs_bottom(rom_series, span)
        metrics_out["rom_deg"] = {"delta": float(delta) if delta is not None else None, "tier": "unknown"}
        if delta is not None:
            # Enforce an absolute minimum ROM (min_delta) as a quick early gate (optional)
            min_delta = float(rom_deg_cfg.get("min_delta", 0.0))
            tiers = rom_deg_cfg.get("tiers", {}) or {}
            tier = _classify_tier(delta, tiers, higher_is_better=True)
            metrics_out["rom_deg"]["tier"] = tier
            if delta < min_delta or tier == "suboptimal":
                _add_flag(metrics_out["flags"], "low_rom")

    elif rom_disp_cfg and rom_series is not None:
        # Displacement ROM (e.g., Y signal)
        delta = _span_delta_mid_vs_bottom(rom_series, span)
        metrics_out["rom_disp"] = {"delta": float(delta) if delta is not None else None, "tier": "unknown"}
        if delta is not None:
            min_delta = float(rom_disp_cfg.get("min_delta", 0.0))
            tiers = rom_disp_cfg.get("tiers", {}) or {}
            tier = _classify_tier(delta, tiers, higher_is_better=True)
            metrics_out["rom_disp"]["tier"] = tier
            if delta < min_delta or tier == "suboptimal":
                _add_flag(metrics_out["flags"], "low_rom")

    # ---------------- ANGLE GUARDRAILS (optional) ----------------
    # Only make sense for angle series (elbow/knee/shoulder_abd, etc.)
    if rom_series is not None and "angle" in (rom_key_used or ""):
        a_val = float(rom_series[a]) if 0 <= a < len(rom_series) and not np.isnan(rom_series[a]) else None
        b_val = float(rom_series[b]) if 0 <= b < len(rom_series) and not np.isnan(rom_series[b]) else None
        c_val = float(rom_series[c]) if 0 <= c < len(rom_series) and not np.isnan(rom_series[c]) else None

        lockout_min = _get(cfg, "metrics.lockout_min_deg", None)
        bottom_max  = _get(cfg, "metrics.bottom_max_deg", None)

        angle_checks = {}
        if lockout_min is not None and a_val is not None and c_val is not None:
            lockout_ok = (a_val >= lockout_min) and (c_val >= lockout_min)
            angle_checks["lockout_ok"] = bool(lockout_ok)
            if not lockout_ok:
                _add_flag(metrics_out["flags"], "no_lockout")

        if bottom_max is not None and b_val is not None:
            # "Shallower" at bottom (too large angle) => b_val > bottom_max -> shallow
            depth_ok = (b_val <= bottom_max)
            angle_checks["depth_ok"] = bool(depth_ok)
            if not depth_ok:
                _add_flag(metrics_out["flags"], "shallow_depth")

        if angle_checks:
            metrics_out["angle_checks"] = angle_checks

    # ---------------- FRIENDLY LABELS (optional; UI/AI can map later too) ----------------
    if metrics_out["flags"]:
        metrics_out["flag_labels"] = {f: _label(f) for f in metrics_out["flags"]}

    return metrics_out


# ----------------------------- public API -----------------------------

def score_quality_for_spans(
    spans: List[Tuple[int, int, int]],
    fps: float,
    series_map: Dict[str, np.ndarray],
    cfg: Dict[str, Any],
    *,
    head_trim_frames: int = 0,
    primary_signal: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Turns spans into rep-level quality with flags & tiers, using unified YAML schema.

    Params
    ------
    spans: list of (start_idx, bottom_idx, end_idx) in the *analyzed window* indices
    fps:   sampling fps (float)
    series_map: {"elbow_angle": np.ndarray, "knee_angle": np.ndarray, ...}
    cfg:   loaded YAML dict (with metrics/flag_labels/bad_flags)
    head_trim_frames: offset to compute global timestamps (original clip), if you trimmed head
    primary_signal: hint to choose the series for ROM first ("elbow_angle", "knee_angle", ...)

    Returns
    -------
    {
      "reps": [
        {
          "index": 1,
          "start_frame": ...,
          "bottom_frame": ...,
          "end_frame": ...,
          "times": { "local": {...}, "global": {...} },
          "tempo": { total_s, ecc_s, con_s, tiers{...} },
          "rom_deg" | "rom_disp": { delta, tier }?,
          "angle_checks": { lockout_ok?, depth_ok? }?,
          "flags": [...],
          "flag_labels": {flag: "Human label"}?,
          "good": true/false
        },
        ...
      ],
      "summary": { "total_reps": N, "good_reps": G, "bad_reps": B }
    }
    """
    fps = float(fps or 15.0)
    bad_flags_conf = (_get(cfg, "bad_flags", []) or [])
    reps_out: List[Dict[str, Any]] = []

    for i, (a, b, c) in enumerate(spans, start=1):
        # Compute metric bundle + flags
        m = _eval_rep_metrics((a, b, c), fps, series_map, cfg, primary_signal=primary_signal)

        # Decide "good" using configured bad_flags (intersection)
        flags = m.get("flags", []) or []
        is_bad = any((f in bad_flags_conf) for f in flags)
        m["good"] = (not is_bad)

        # Build rep record
        rep = {
            "index": int(i),
            "start_frame": int(a),
            "bottom_frame": int(b),
            "end_frame": int(c),
            "times": {
                "local": {
                    "start": a / max(1.0, fps),
                    "bottom": b / max(1.0, fps),
                    "end": c / max(1.0, fps),
                },
                "global": {
                    "start": (head_trim_frames + a) / max(1.0, fps),
                    "bottom": (head_trim_frames + b) / max(1.0, fps),
                    "end": (head_trim_frames + c) / max(1.0, fps),
                },
                "label": f"Rep {i} — {a/max(1.0,fps):.2f}s → {c/max(1.0,fps):.2f}s",
            },
            **m,
        }
        reps_out.append(rep)

    total = len(reps_out)
    good = sum(1 for r in reps_out if r.get("good", False))
    summary = {"total_reps": total, "good_reps": good, "bad_reps": total - good}

    return {"reps": reps_out, "summary": summary}


# ----------------------------- convenience merger -----------------------------

def merge_quality_into_metrics(
    base_metrics: Dict[str, Any],
    quality: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Non-destructively merge quality outputs into your existing `metrics` dict
    (e.g., from rep_counter / exercise scorer). Prefers existing keys in base_metrics.
    """
    out = dict(base_metrics)
    # Attach/replace rep list and summary
    if quality.get("reps"):
        out["reps"] = quality["reps"]
    if quality.get("summary"):
        out["summary"] = quality["summary"]
    return out
