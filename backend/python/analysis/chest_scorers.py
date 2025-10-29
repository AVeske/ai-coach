# backend/python/analysis/chest_scorers.py
from __future__ import annotations
from typing import Dict, Any, List
import logging

from .common import (
    rep_counter,          # generic T–B–T counter
    signal_elbow_angle,   # ready-made signal factory (median-smoothed elbow angle)
)

log = logging.getLogger("aicoach")


def score_pushup(
    samples: List[Dict[str, Any]],
    fps: float,
    cfg: Dict[str, Any],
    *,
    primary_side: str = "left",
) -> Dict[str, Any]:
    """
    Counts push-ups using elbow-angle as the primary 1-D signal.
    Small behavior tweaks (durations, prominence, bookends, etc.) live in YAML.
    """
    return rep_counter(
        samples,
        fps,
        cfg,
        primary_side=primary_side,
        signal_factory=signal_elbow_angle,
        signal_name="elbow_angle",
    )


def score_bench_press(
    samples: List[Dict[str, Any]],
    fps: float,
    cfg: Dict[str, Any],
    *,
    primary_side: str = "left",
) -> Dict[str, Any]:
    """
    Bench press reps via the same elbow-angle counter.
    Tune per-exercise thresholds in configs/exercises/bench_press.yaml.
    """
    return rep_counter(
        samples,
        fps,
        cfg,
        primary_side=primary_side,
        signal_factory=signal_elbow_angle,
        signal_name="elbow_angle",
    )


def score_incline_bench(
    samples: List[Dict[str, Any]],
    fps: float,
    cfg: Dict[str, Any],
    *,
    primary_side: str = "left",
) -> Dict[str, Any]:
    """
    Incline bench reps via elbow-angle; tempo/range differences should be set in YAML.
    """
    return rep_counter(
        samples,
        fps,
        cfg,
        primary_side=primary_side,
        signal_factory=signal_elbow_angle,
        signal_name="elbow_angle",
    )
