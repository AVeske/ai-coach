from __future__ import annotations
from typing import Dict, Any, List, Callable
import numpy as np

from .common import (
    rep_counter,
    signal_elbow_angle,   # elbow-angle series (median-smoothed)
    summarize,
    median_smooth,
)
from side_selector import series_y_for_joint

# ─────────────────────────────────────────────────────────────
# Standing Bicep Curls
# ─────────────────────────────────────────────────────────────
def score_standing_curl(
    samples: List[Dict[str, Any]],
    fps: float,
    cfg: Dict[str, Any],
    *,
    primary_side: str = "left",
) -> Dict[str, Any]:
    return rep_counter(
        samples, fps, cfg,
        primary_side=primary_side,
        signal_factory=signal_elbow_angle,
        signal_name="elbow_angle",
    )

# ─────────────────────────────────────────────────────────────
# Tricep Extensions (overhead or cable)
# ─────────────────────────────────────────────────────────────
def score_tricep_extensions(
    samples: List[Dict[str, Any]],
    fps: float,
    cfg: Dict[str, Any],
    *,
    primary_side: str = "left",
) -> Dict[str, Any]:
    # Same elbow-angle flow; tune thresholds from YAML if needed.
    return rep_counter(
        samples, fps, cfg,
        primary_side=primary_side,
        signal_factory=signal_elbow_angle,
        signal_name="elbow_angle",
    )

# ─────────────────────────────────────────────────────────────
# Preacher Curls
# ─────────────────────────────────────────────────────────────
def score_preacher_curls(
    samples: List[Dict[str, Any]],
    fps: float,
    cfg: Dict[str, Any],
    *,
    primary_side: str = "left",
) -> Dict[str, Any]:
    return rep_counter(
        samples, fps, cfg,
        primary_side=primary_side,
        signal_factory=signal_elbow_angle,
        signal_name="elbow_angle",
    )

# ─────────────────────────────────────────────────────────────
# Lateral Raises (front view, both arms)
# Signal: combine both wrists’ Y (invert Y so “up” = larger value),
# then median-smooth and detect T–B–T on that 1-D series.
# ─────────────────────────────────────────────────────────────
def score_lateral_raises(
    samples: List[Dict[str, Any]],
    fps: float,
    cfg: Dict[str, Any],
    *,
    primary_side: str = "left",   # ignored here; we use both arms
) -> Dict[str, Any]:

    def _both_wrists_inverted_y(samps, _side_ignored) -> np.ndarray:
        # y increases downward in screen coords, so raise → smaller y.
        # We invert to make "raise" a TOP.
        yL = series_y_for_joint(samps, "wrist", "left",  conf_thresh=0.20)
        yR = series_y_for_joint(samps, "wrist", "right", conf_thresh=0.20)

        # invert where finite
        invL = np.where(np.isfinite(yL), -yL, np.nan)
        invR = np.where(np.isfinite(yR), -yR, np.nan)

        # mean across sides, ignoring NaNs (works if only one arm is visible)
        combo = np.nanmean(np.vstack([invL, invR]), axis=0)
        # smooth to reduce jitter
        combo = median_smooth(combo, 5)
        return combo

    return rep_counter(
        samples, fps, cfg,
        primary_side=primary_side,
        signal_factory=_both_wrists_inverted_y,
        signal_name="wrist_y_both_inverted",
    )
