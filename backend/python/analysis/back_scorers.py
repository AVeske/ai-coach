from __future__ import annotations
from typing import Dict, Any, List
import logging
import numpy as np

from .common import (
    rep_counter,
    signal_elbow_angle,
    signal_shoulder_y,
)

from side_selector import elbow_angle_series_for_side  # for quick sparsity check

log = logging.getLogger("aicoach")


def _valid_frac(arr: np.ndarray) -> float:
    if arr.size == 0:
        return 0.0
    return float(np.isfinite(arr).sum()) / float(arr.size)


def _pick_signal(
    samples: List[Dict[str, Any]],
    primary_side: str,
    cfg: Dict[str, Any],
    *,
    elbow_thresh: float = 0.12,
):
    """Choose elbow-angle unless coverage is poor or YAML forces an alternative."""
    force = (cfg.get("events", {}).get("force_signal", "auto") or "auto").lower()
    if force == "elbow":
        return signal_elbow_angle, "elbow_angle"
    if force == "shoulder":
        return signal_shoulder_y, "shoulder_y"

    elbow_raw = elbow_angle_series_for_side(samples, primary_side, conf_thresh=0.15)
    elbow_ok = (_valid_frac(elbow_raw) >= elbow_thresh)
    if elbow_ok:
        return signal_elbow_angle, "elbow_angle"
    return signal_shoulder_y, "shoulder_y"


# ──────────────────────────────────────────────────────────────────────────────
# LAT PULLDOWN
# ──────────────────────────────────────────────────────────────────────────────
def score_lat_pulldown(
    samples: List[Dict[str, Any]],
    fps: float,
    cfg: Dict[str, Any],
    *,
    primary_side: str = "left",
) -> Dict[str, Any]:
    """
    Lat pulldown:
      - Primary: elbow angle (TOP≈arms extended; BOTTOM≈elbows flexed)
      - Fallback: shoulder-Y when elbows/wrists are occluded by bar/cable.
    """
    if not samples:
        return {"reps": [], "summary": {"total_reps": 0, "good_reps": 0, "bad_reps": 0}}

    sig_factory, sig_name = _pick_signal(samples, primary_side, cfg, elbow_thresh=0.12)

    return rep_counter(
        samples, fps, cfg,
        primary_side=primary_side,
        signal_factory=sig_factory,
        signal_name=sig_name,
    )


# ──────────────────────────────────────────────────────────────────────────────
# PULL-UPS
# ──────────────────────────────────────────────────────────────────────────────
def score_pullup(
    samples: List[Dict[str, Any]],
    fps: float,
    cfg: Dict[str, Any],
    *,
    primary_side: str = "left",
) -> Dict[str, Any]:
    """
    Pull-ups:
      - Wrist X/Y can be static; prefer elbow angle or shoulder-Y.
      - Same T–B–T pairing and bookend guards as other lifts.
    """
    if not samples:
        return {"reps": [], "summary": {"total_reps": 0, "good_reps": 0, "bad_reps": 0}}

    # Pull-ups often have good shoulder visibility; elbow can be occluded overhead.
    # Try elbow first; fall back to shoulder-Y if too sparse.
    sig_factory, sig_name = _pick_signal(samples, primary_side, cfg, elbow_thresh=0.12)

    return rep_counter(
        samples, fps, cfg,
        primary_side=primary_side,
        signal_factory=sig_factory,
        signal_name=sig_name,
    )


# ──────────────────────────────────────────────────────────────────────────────
# BENT-OVER ROWS
# ──────────────────────────────────────────────────────────────────────────────
def score_bent_over_row(
    samples: List[Dict[str, Any]],
    fps: float,
    cfg: Dict[str, Any],
    *,
    primary_side: str = "left",
) -> Dict[str, Any]:
    """
    Bent-over rows:
      - Primary: elbow angle (elbow flexion during pull)
      - Fallback: shoulder-Y (torso/shoulder vertical travel in frame)
    """
    if not samples:
        return {"reps": [], "summary": {"total_reps": 0, "good_reps": 0, "bad_reps": 0}}

    # Rows usually show elbows well from a 45° or side view.
    sig_factory, sig_name = _pick_signal(samples, primary_side, cfg, elbow_thresh=0.10)

    return rep_counter(
        samples, fps, cfg,
        primary_side=primary_side,
        signal_factory=sig_factory,
        signal_name=sig_name,
    )
