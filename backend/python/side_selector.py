# backend/python/side_selector.py
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
import os
import csv
import logging

log = logging.getLogger("aicoach")

# --- filming side landmarks ---
LEFT = [
    "left_shoulder", "left_elbow", "left_wrist",
    "left_hip", "left_knee", "left_ankle",
]
RIGHT = [
    "right_shoulder", "right_elbow", "right_wrist",
    "right_hip", "right_knee", "right_ankle",
]

# --- filming side inference ---
def infer_side(samples: List[Dict[str, Any]]) -> tuple[str, float, float]:
    """
    Decide 'left' or 'right' filming side, based on average confidence of
    left- vs right-side landmarks across frames.
    Returns: (side, left_mean_conf, right_mean_conf)
    """
    def mean_conf(names: List[str]) -> float:
        tot = 0.0
        cnt = 0.0
        for s in samples:
            lm = s.get("landmarks", {})
            for n in names:
                v = lm.get(n)
                if v and len(v) >= 3 and v[2] is not None:
                    tot += float(v[2]); cnt += 1
        return (tot / cnt) if cnt else 0.0

    ml = mean_conf(LEFT)
    mr = mean_conf(RIGHT)
    return ("left" if ml >= mr else "right", ml, mr)

# --- smoothing (EMA) ---
def _ema(prev: Optional[float], x: Optional[float], alpha: float) -> Optional[float]:
    if x is None:
        return prev  # keep last if missing
    if prev is None:
        return x     # initialize
    return alpha * x + (1.0 - alpha) * prev

def smooth_samples(
    samples: List[Dict[str, Any]],
    alpha: float = 0.2,
) -> List[Dict[str, Any]]:
    """
    Apply exponential moving average to pose landmarks across time.
    Each sample is expected to look like:
      {"landmarks": {name: [x, y, conf], ...}, "t": <float>?}
    Returns a NEW list (doesn't mutate input).
    """
    smoothed: List[Dict[str, Any]] = []
    # rolling state per landmark name -> (x, y, c)
    state: Dict[str, Tuple[Optional[float], Optional[float], Optional[float]]] = {}

    for s in samples:
        lm = (s.get("landmarks") or {})
        out_lm: Dict[str, List[Optional[float]]] = {}

        keys = set(state.keys()) | set(lm.keys())
        for k in keys:
            cur = lm.get(k)
            x = float(cur[0]) if (cur and cur[0] is not None) else None
            y = float(cur[1]) if (cur and cur[1] is not None) else None
            c = float(cur[2]) if (cur and cur[2] is not None) else None

            prev = state.get(k, (None, None, None))
            sx = _ema(prev[0], x, alpha)
            sy = _ema(prev[1], y, alpha)
            sc = _ema(prev[2], c, alpha)

            state[k] = (sx, sy, sc)
            out_lm[k] = [sx, sy, sc]

        smoothed.append({
            **{k: v for k, v in s.items() if k != "landmarks"},
            "landmarks": out_lm,
        })
    return smoothed

# --- CSV writer for samples ---
def write_samples_csv(
    samples: List[Dict[str, Any]],
    out_dir: str,
    base_name: str,
) -> Optional[str]:
    """
    Write samples to CSV. Columns: frame, optional t, then one triplet per landmark:
      <name>_x, <name>_y, <name>_c
    Returns file path or None on failure.
    """
    try:
        os.makedirs(out_dir, exist_ok=True)

        # all landmark names encountered
        names: set[str] = set()
        for s in samples:
            lm = s.get("landmarks") or {}
            names.update(lm.keys())
        ordered = sorted(names)

        header = ["frame"]
        has_t = any("t" in s for s in samples)
        if has_t:
            header.append("t")
        for n in ordered:
            header.extend([f"{n}_x", f"{n}_y", f"{n}_c"])

        path = os.path.join(out_dir, f"{base_name}.csv")
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(header)
            for i, s in enumerate(samples):
                row: list[Any] = [i]
                if has_t:
                    row.append(s.get("t"))
                lm = s.get("landmarks") or {}
                for n in ordered:
                    v = lm.get(n) or [None, None, None]
                    x = v[0] if len(v) > 0 else None
                    y = v[1] if len(v) > 1 else None
                    c = v[2] if len(v) > 2 else None
                    row.extend([x, y, c])
                w.writerow(row)
        return path
    except Exception as e:
        log.exception("Failed to write CSV: %s", e)
        return None
