# backend/python/main.py
from __future__ import annotations
import os
import shutil
import tempfile
import logging

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from pose_extractor import extract_pose_from_video
from analysis.rules import make_feedback  # (optional) still available
from agents.coach_agent import get_feedback  # <-- LLM agent

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("aicoach")

app = FastAPI(title="AI Coach Backend", version="0.2.0")

# CORS (relax for dev; tighten in prod)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.get("/")
def root():
    # convenience: point people to docs
    return {"ok": True, "docs": "/docs"}

@app.post("/analyze")
async def analyze_video(
    exercise: str = Form(...),
    video: UploadFile = File(...),
):
    """
    1) Save upload to temp file
    2) Run BlazePose on sampled frames
    3) Optionally compute rule-based feedback (make_feedback)
    4) Call LLM agent for human-friendly feedback
    5) Return JSON
    """
    tmpdir = tempfile.mkdtemp(prefix="aicoach_")
    try:
        suffix = os.path.splitext(video.filename or "upload.mp4")[1] or ".mp4"
        tmp_path = os.path.join(tmpdir, f"input{suffix}")

        # Save upload
        raw = await video.read()
        with open(tmp_path, "wb") as f:
            f.write(raw)
        received_bytes = len(raw or b"")

        log.info("Received upload: name=%s bytes=%s exercise=%s path=%s",
                 video.filename, received_bytes, exercise, tmp_path)

        # Pose extraction
        pose_out = extract_pose_from_video(
            tmp_path,
            max_frames=48,
            model_complexity=2,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        analysis_ok = bool(pose_out.get("ok"))
        frames = int(pose_out.get("frames", 0))

        # Optional rules-based text (can be combined with LLM)
        rules_text = make_feedback(exercise, pose_out) if analysis_ok else "Pose extraction failed."

        # LLM agent feedback (pass structured data)
        llm_text = await get_feedback(exercise, pose_out)

        return JSONResponse(
            {
                "ok": True,
                "message": "Success",
                "exercise": exercise,
                "received_bytes": received_bytes,
                "analysis_ok": analysis_ok,
                "frames_sampled": frames,
                "rules_feedback": rules_text,     # optional: keep or drop
                "agent_feedback": llm_text,       # main text your app will show
            }
        )
    finally:
        try:
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass
