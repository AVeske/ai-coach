# backend/python/analysis/visualize.py
from __future__ import annotations
from typing import List, Tuple, Optional
import os
import numpy as np
import matplotlib.pyplot as plt

def _secs(i: int, fps: float) -> float:
    return float(i) / max(1.0, fps)

def plot_signal_with_spans(
    *,
    series: np.ndarray,                 # y-values (already smoothed/winsorized as you like)
    fps: float,
    tops: List[int],
    bottoms: List[int],
    spans: List[Tuple[int,int,int]],
    used_signal: str,                   # "elbow_angle" | "shoulder_y"
    title: Optional[str] = None,
    out_path: str,
) -> str:
    """
    Renders:
      - curve of series
      - green circles at TOPS, red X at BOTTOMS (true extrema)
      - shaded bars for each counted span (top->bottom->top)
    Saves to out_path and returns that path.
    """
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    x = np.arange(len(series), dtype=float) / max(1.0, fps)
    y = np.array(series, dtype=float)

    fig = plt.figure(figsize=(10, 4.2), dpi=130)
    ax = plt.gca()
    ax.plot(x, y, linewidth=1.5)

    if len(tops):
        ax.scatter([_secs(i, fps) for i in tops], [y[i] for i in tops], s=28, marker='o')
    if len(bottoms):
        ax.scatter([_secs(i, fps) for i in bottoms], [y[i] for i in bottoms], s=28, marker='x')

    for (t1, b, t2) in spans:
        ax.axvspan(_secs(t1, fps), _secs(t2, fps), alpha=0.15)

    ax.set_xlabel("time (s)")
    ax.set_ylabel("value")
    ax.set_title(title or f"{used_signal} (n={len(series)})")
    ax.grid(True, linewidth=0.3)

    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    return out_path
