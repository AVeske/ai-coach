# backend/python/analysis/dispatcher.py
from __future__ import annotations
from typing import Dict, Any, List, Callable

from .chest_scorers import score_pushup, score_bench_press, score_incline_bench
from .legs_scorers import score_squat, score_hamstring_curl, score_leg_extension  # <- make sure your filename is legs_scorers.py
from .back_scorers import score_lat_pulldown, score_pullup, score_bent_over_row
from .arms_scorers import score_preacher_curls, score_standing_curl, score_lateral_raises, score_tricep_extensions

# All scorers should share the same signature: (samples, fps, cfg, *, primary_side="left") -> Dict[str, Any]
_SCORERS: Dict[str, Callable[[List[dict], float, Dict[str, Any]], Dict[str, Any]]] = {
    "push_up":   score_pushup,
    "squat":    score_squat,
    "bench_press": score_bench_press,
    "incline_bench": score_incline_bench,
    "leg_extension" : score_leg_extension,
    "hamstring_curl": score_hamstring_curl,
    "lat_pulldown": score_lat_pulldown,
    "pull_up": score_pullup,
    "bent_over_row": score_bent_over_row,
    "lateral_raises": score_lateral_raises,
    "preacher_curls": score_preacher_curls,
    "standing_curls": score_standing_curl,
    "tricep_extensions": score_tricep_extensions,
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
