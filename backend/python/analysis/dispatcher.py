from __future__ import annotations
from typing import Dict, Any, List
from .chest_scorers import score_pushup  # + bench later
from .legs_scorers import score_squat
# from .arms_scorers import ...
# from .back_scorers import ...

_SCORERS = {
    "pushup": score_pushup,
    "push-ups": score_pushup,
    "pushups": score_pushup,
    "squat": score_squat,
    "squats": score_squat,
}

def score_reps(exercise_id: str, samples: List[dict], fps: float, cfg: Dict[str, Any]) -> Dict[str, Any]:
    fn = _SCORERS.get((exercise_id or "").lower())
    if not fn:
        return {"reps": [], "summary": {"total_reps": 0, "good_reps": 0, "bad_reps": 0}, "warnings": ["unsupported_exercise"]}
    return fn(samples, fps, cfg)