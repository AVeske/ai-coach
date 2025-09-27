# backend/python/analysis/dispatcher.py
from __future__ import annotations
from typing import Dict, Any, List, Callable

from .chest_scorers import score_pushup
from .legs_scorers import score_squat  # <- make sure your filename is legs_scorers.py

# All scorers should share the same signature: (samples, fps, cfg, *, primary_side="left") -> Dict[str, Any]
_SCORERS: Dict[str, Callable[[List[dict], float, Dict[str, Any]], Dict[str, Any]]] = {
    "pushup":   score_pushup,
    "squat":    score_squat,
}

def score_reps(
    exercise_id: str,
    samples: List[dict],
    fps: float,
    cfg: Dict[str, Any],
    *,
    primary_side: str = "left",
) -> Dict[str, Any]:
    fn = _SCORERS.get((exercise_id or "").lower())
    if not fn:
        return {
            "reps": [],
            "summary": {"total_reps": 0, "good_reps": 0, "bad_reps": 0},
            "warnings": ["unsupported_exercise", (exercise_id or "").lower()],
        }
    # pass primary_side through so each scorer can use the chosen side
    return fn(samples, fps, cfg, primary_side=primary_side)
