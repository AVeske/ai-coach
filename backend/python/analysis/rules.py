# backend/python/analysis/rules.py
from __future__ import annotations
from typing import Dict, Any, List
import math

from .angles import angle_deg, get_xy

# Very lightweight heuristics to prove the flow works.
# Later you’ll make these exercise-specific and way more robust.

def summarize_pushup(samples: List[Dict[str, Any]]) -> str:
    elbows = []
    hips_line = []
    for s in samples:
        lm = s["landmarks"]
        ls, le, lw = lm.get("left_shoulder"), lm.get("left_elbow"), lm.get("left_wrist")
        rs, re, rw = lm.get("right_shoulder"), lm.get("right_elbow"), lm.get("right_wrist")
        lh, rh = lm.get("left_hip"), lm.get("right_hip")

        if ls and le and lw:
            ang_left = angle_deg(get_xy(ls), get_xy(le), get_xy(lw))
            if not math.isnan(ang_left): elbows.append(ang_left)
        if rs and re and rw:
            ang_right = angle_deg(get_xy(rs), get_xy(re), get_xy(rw))
            if not math.isnan(ang_right): elbows.append(ang_right)
        if lh and rh:
            hips_line.append(abs(get_xy(lh)[1] - get_xy(rh)[1]))  # vertical symmetry crude check

    feedback = []
    if elbows:
        min_elbow = min(elbows)
        if min_elbow > 110:
            feedback.append("Get deeper: bend elbows more at the bottom.")
        elif min_elbow < 60:
            feedback.append("You might be going too deep; keep elbows around ~90° at bottom.")
        else:
            feedback.append("Depth looks decent on push-ups.")

    if hips_line:
        mean_diff = sum(hips_line) / len(hips_line)
        if mean_diff > 0.05:
            feedback.append("Keep hips level; avoid twisting during reps.")
        else:
            feedback.append("Hip alignment looks good.")

    if not feedback:
        feedback.append("Could not confidently detect form; try clearer lighting and framing.")
    return " ".join(feedback)

def summarize_squat(samples: List[Dict[str, Any]]) -> str:
    knees = []
    torso = []
    for s in samples:
        lm = s["landmarks"]
        lk, lh, la = lm.get("left_knee"), lm.get("left_hip"), lm.get("left_ankle")
        rk, rh, ra = lm.get("right_knee"), lm.get("right_hip"), lm.get("right_ankle")
        ls, rs = lm.get("left_shoulder"), lm.get("right_shoulder")

        # Knee angle (hip-knee-ankle)
        if lh and lk and la:
            knees.append(angle_deg(get_xy(lh), get_xy(lk), get_xy(la)))
        if rh and rk and ra:
            knees.append(angle_deg(get_xy(rh), get_xy(rk), get_xy(ra)))

        # Torso angle approx (hip-shoulder vertical)
        if lh and ls:
            torso.append(abs(get_xy(lh)[0] - get_xy(ls)[0]))

    feedback = []
    if knees:
        min_knee = min(knees)
        if min_knee > 110:
            feedback.append("Try to reach at least parallel; bend knees more at depth.")
        else:
            feedback.append("Depth looks solid.")
    if torso:
        mean_tilt = sum(torso)/len(torso)
        if mean_tilt > 0.15:
            feedback.append("Keep chest up; avoid excessive forward lean.")
        else:
            feedback.append("Torso position is controlled.")
    if not feedback:
        feedback.append("Hard to read your squat; ensure full body is in frame.")
    return " ".join(feedback)

def make_feedback(exercise: str, pose_output: Dict[str, Any]) -> str:
    if not pose_output.get("ok"):
        return f"Pose extraction failed: {pose_output.get('error','unknown error')}"

    samples = pose_output.get("samples", [])

    ex = exercise.strip().lower()
    if "push" in ex:
        return summarize_pushup(samples)
    if "squat" in ex:
        return summarize_squat(samples)

    # fallback generic
    return "Video received. Pose detected. More detailed exercise rules coming soon."
