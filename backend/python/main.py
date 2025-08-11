# backend/python/main.py
from __future__ import annotations

import os
import shutil
import tempfile
import logging
from typing import Dict, Any

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import yaml

# ── local modules ─────────────────────────────────────────────────────────────
# Pose extractor (returns {"ok": bool, "samples": [...], "frames": int, ...})
from pose_extractor import extract_pose_from_video

# Exercise registry (exact IDs/slugs and YAML file names)
from models.exercise_registry import get_exercise_info

# Simple sanity gates (person present, motion present, etc.)
from analysis.validators import basic_validation

# Rep detection / metrics for pushups (add others later)
from analysis.scoring import detect_reps_pushup

# LLM agent: turns metrics + rubric into human feedback
from agents.coach_agent import get_feedback

# ── setup ────────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("aicoach")

app = FastAPI(title="AI Coach Backend", version="0.3.0")

# Dev CORS (tighten in prod)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # in prod: set to your app domain(s)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── helpers ──────────────────────────────────────────────────────────────────
def load_rubric_yaml(filename: str) -> Dict[str, Any]:
    """Load exercise rubric YAML from configs/exercises/."""
    base = os.path.join(os.path.dirname(__file__), "configs", "exercises")
    path = os.path.join(base, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Rubric not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

# ── routes ───────────────────────────────────────────────────────────────────
@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.get("/")
def root():
    return {"ok": True, "docs": "/docs"}

@app.post("/analyze")
async def analyze_video(
    exercise_id: str = Form(...),     # exact slug, e.g. "pushup"
    video: UploadFile = File(...),
):
    """
    1) Save upload to a temp file
    2) Pose extraction (MediaPipe BlazePose)
    3) Basic validation (person present, motion present)
    4) Load rubric via exercise registry
    5) Compute metrics (per-rep) for the specific exercise
    6) Ask LLM for concise feedback based on metrics + rubric
    """
    tmpdir = tempfile.mkdtemp(prefix="aicoach_")
    try:
        # 1) Save upload
        suffix = os.path.splitext(video.filename or "upload.mp4")[1] or ".mp4"
        tmp_path = os.path.join(tmpdir, f"input{suffix}")
        raw = await video.read()
        with open(tmp_path, "wb") as f:
            f.write(raw or b"")
        received_bytes = len(raw or b"")
        log.info("Received upload: name=%s bytes=%s exercise_id=%s path=%s",
                 video.filename, received_bytes, exercise_id, tmp_path)

        # 2) Pose extraction
        pose_out = extract_pose_from_video(
            tmp_path,
            max_frames=72,                # sample up to ~72 frames
            model_complexity=2,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

        # 3) Basic validation gates
        gate = basic_validation(pose_out)
        if not gate.get("valid"):
            return JSONResponse(
                {
                    "ok": False,
                    "message": "We couldn’t analyze that video.",
                    "reason": gate.get("reason"),
                    "details": {k: v for k, v in gate.items() if k not in ("valid", "reason")},
                    "tips": [
                        "Ensure your whole body is in frame.",
                        "Use a side angle for push-ups/bench/squat.",
                        "Record 3–8 reps with full range of motion.",
                        "Avoid heavy backlight; use steady lighting.",
                    ],
                },
                status_code=200,
            )

        # 4) Registry lookup & rubric
        info = get_exercise_info(exercise_id)
        if not info:
            raise HTTPException(status_code=400, detail="Unknown exercise_id")
        rubric = load_rubric_yaml(info.yaml)

        # 5) Metrics per exercise
        fps = 30.0  # TODO: compute from video metadata if available
        metrics: Dict[str, Any] = {}
        if exercise_id == "pushup":
            metrics = detect_reps_pushup(pose_out["samples"], fps, rubric)
        # elif exercise_id == "bench_press_flat":
        #     metrics = detect_reps_bench(pose_out["samples"], fps, rubric)
        # elif exercise_id == "squat":
        #     metrics = detect_reps_squat(pose_out["samples"], fps, rubric)
        # else:
        #     metrics = {}  # default

        # 6) Agent feedback (compact rubric text)
        rubric_text = yaml.safe_dump(rubric, sort_keys=False)
        agent_text = await get_feedback(info.label, metrics, rubric_text)

        return JSONResponse(
            {
                "ok": True,
                "exercise_id": info.id,
                "exercise_label": info.label,
                "analysis_ok": True,
                "metrics": metrics,            # per-rep metrics + summary
                "agent_feedback": agent_text,  # human-friendly feedback
            }
        )
    finally:
        try:
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass
