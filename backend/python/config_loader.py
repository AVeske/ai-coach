from __future__ import annotations
import os, yaml
from typing import Dict, Any

BASE = os.path.dirname(__file__)
CFG_DIR = os.path.join(BASE, "configs", "exercises")

_cache: dict[str, dict] = {}

def load_exercise_cfg(ex_id: str) -> Dict[str, Any]:
    key = (ex_id or "").lower()
    if key in _cache:
        return _cache[key]
    fname = f"{key}.yaml"
    path = os.path.join(CFG_DIR, fname)
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    _cache[key] = data
    return data