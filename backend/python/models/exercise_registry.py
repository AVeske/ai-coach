from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional

@dataclass(frozen=True)
class ExerciseInfo:
    id: str
    label: str
    yaml: str

REGISTRY: Dict[str, ExerciseInfo] = {
    "pushup": ExerciseInfo(id="pushup", label="Push-up", yaml="pushup.yaml"),
    "bench_press_flat": ExerciseInfo(id="bench_press_flat", label="Bench Press (Flat)", yaml="bench_press.yaml"),
    "squat": ExerciseInfo(id="squat", label="Back Squat", yaml="squat.yaml"),
    # add more as you go…
}

def get_exercise_info(ex_id: str) -> Optional[ExerciseInfo]:
    return REGISTRY.get(ex_id)
