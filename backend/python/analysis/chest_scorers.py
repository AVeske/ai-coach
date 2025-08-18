from __future__ import annotations
from typing import Dict, Any, List
import numpy as np
from .common import best_of_two, median_smooth, find_events, pair_top_bottom_top, summarize, tier_of, xy

# Push‑up

def score_pushup(samples: List[Dict[str,Any]], fps: float, cfg: Dict[str,Any]) -> Dict[str,Any]:
    # series
    elbow = best_of_two(samples,
        ["left_shoulder","left_elbow","left_wrist"],
        ["right_shoulder","right_elbow","right_wrist"])
    back  = best_of_two(samples,
        ["left_shoulder","left_hip","left_ankle"],
        ["right_shoulder","right_hip","right_ankle"])
    elbow = median_smooth(elbow, 5); back = median_smooth(back, 5)

    ev = cfg.get("events", {})
    tops,bottoms = find_events(
        elbow, fps,
        peak_is_top=ev.get("peak_is_top", True),
        min_dist_s=float(str(ev.get("min_peak_distance_frames","0.30s")).replace("s","")),
        prom_std=float(ev.get("prominence_std", 0.18)),
        width_s=float(ev.get("width_sec", 0.08)),
    )
    reps = pair_top_bottom_top(
        elbow, tops, bottoms, fps,
        dur_min=float(ev.get("min_rep_duration_s", 0.40)),
        dur_max=float(ev.get("max_rep_duration_s", 7.0)),
    )

    metrics_cfg = cfg.get("metrics", {})
    bad_set = set(cfg.get("bad_flags", ["suboptimal"]))

    per = []
    edge_guard = int(0.25*fps)
    for t1, bot, t2 in reps:
        if t1 < edge_guard or t2 > (len(samples)-edge_guard):
            continue
        # values
        e1, eb, e2 = elbow[t1], elbow[bot], elbow[t2]
        rom = float(max(e1, e2) - eb) if not any(np.isnan([e1,eb,e2])) else None
        back_btm = float(back[bot]) if not np.isnan(back[bot]) else None
        tempo = (t2 - t1) / max(1.0, fps)

        grades = {}
        if "rom_deg" in metrics_cfg:
            grades["rom_deg"] = tier_of(rom, metrics_cfg["rom_deg"].get("tiers", {}))
        if "back_neutral_deg" in metrics_cfg:
            grades["back_neutral_deg"] = tier_of(back_btm, metrics_cfg["back_neutral_deg"].get("tiers", {}))
        if "tempo_s" in metrics_cfg:
            grades["tempo_s"] = tier_of(tempo, metrics_cfg["tempo_s"].get("tiers", {}))

        is_bad = any(g in bad_set for g in grades.values())
        per.append({
            "start_frame": int(t1), "bottom_frame": int(bot), "end_frame": int(t2),
            "duration_s": float(tempo), "grades": grades, "good": (not is_bad)
        })

    return {"reps": per, "summary": summarize(per)}

# Bench press (stub – uses same structure, different series/tiers via benchpress.yaml later)

def score_benchpress(samples: List[Dict[str,Any]], fps: float, cfg: Dict[str,Any]) -> Dict[str,Any]:
    return {"reps": [], "summary": {"total_reps": 0, "good_reps": 0, "bad_reps": 0}}