# backend/python/main.py
from __future__ import annotations
import os
import shutil
import tempfile
import logging
import yaml
import datetime as dt
from typing import Any, Dict, Optional

from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

# --- local modules ---
from pose_extractor import extract_pose_from_video
from analysis.validators import basic_validation
from analysis.dispatcher import score_reps
from agents.coach_agent import get_feedback
from services.firebase_db import ensure_firebase, verify_token, save_session
from side_selector import infer_side, smooth_samples, write_samples_csv

load_dotenv()
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("aicoach")

app = FastAPI(title="AI Coach Backend", version="0.8.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten for prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/healthz")
def healthz():
    return {"ok": True, "model": "movenet_server", "version": "0.8.1"}

def _load_rubric(ex_id: str) -> Dict[str, Any]:
    base = os.path.dirname(__file__)
    fname = os.path.join(base, "configs", f"{ex_id}.yaml")
    if not os.path.exists(fname):
        return {}
    with open(fname, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

@app.post("/analyze")
async def analyze_video(
    request: Request,
    exercise_id: str = Form(...),
    video: UploadFile = File(...),
    weight_value: Optional[str] = Form(None),   # optional
    weight_unit: Optional[str] = Form(None),    # 'kg' | 'lb'
):
    tmpdir = tempfile.mkdtemp(prefix="aicoach_")
    try:
        # Extract Firebase ID token (if present)
        auth_header = request.headers.get("Authorization", "")
        id_token = auth_header.split(" ", 1)[1].strip() if auth_header.lower().startswith("bearer ") else None

        # Save upload to temp
        suffix = os.path.splitext(video.filename or "upload.mp4")[1] or ".mp4"
        tmp_path = os.path.join(tmpdir, f"input{suffix}")
        raw = await video.read()
        with open(tmp_path, "wb") as f:
            f.write(raw)
        log.info(
            "Received: name=%s bytes=%d exercise_id=%s path=%s",
            video.filename, len(raw), exercise_id, tmp_path
        )

        # Pose extraction
        pose_out: Dict[str, Any] = extract_pose_from_video(
            tmp_path, sample_fps=15.0, max_samples=600,
        )
        if not pose_out.get("ok"):
            return JSONResponse(
                {"ok": False, "message": "pose_extraction_failed"},
                status_code=400
            )

        # Basic human/motion validation
        gate = basic_validation(pose_out)
        if not gate.get("valid", False):
            return JSONResponse({
                "ok": False,
                "exercise_id": exercise_id,
                "message": "We couldn’t analyze that video.",
                "reason": gate.get("reason", "unknown"),
                "tips": [
                    "Ensure your full body is visible.",
                    "Use good lighting and a stable camera.",
                    "Do continuous reps so we can track motion."
                ],
                "dbg": pose_out.get("dbg", {}),
            })

        # Load exercise rubric (optional)
        cfg = _load_rubric(exercise_id)

        # Choose fps & gather raw samples
        fps = float(pose_out.get("fps", 30.0) or 30.0)
        samples_raw = pose_out.get("samples", [])

        # ---- Smoothing + CSV export (analyze on smoothed) ----
        alpha = 0.2  # lower = smoother, higher = snappier
        samples_smooth = smooth_samples(samples_raw, alpha=alpha)

        # CSV directory: backend/python/csvs/
        base_dir = os.path.dirname(__file__)
        csv_dir = os.path.join(base_dir, "csvs")
        ts_utc = dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

        uid = None
        uid_for_name = "anon"
        if id_token and ensure_firebase():
            uid = verify_token(id_token)
            if uid:
                uid_for_name = uid[:6]

        csv_base = f"{ts_utc}_{exercise_id}_{uid_for_name}_smoothed"
        csv_path = write_samples_csv(samples_smooth, csv_dir, csv_base)
        csv_saved = csv_path is not None
        # ------------------------------------------------------

        # Use smoothed for side inference and scoring
        side, left_mean, right_mean = infer_side(samples_smooth)

        metrics = score_reps(exercise_id, samples_smooth, fps, cfg)
        metrics["selected_side"] = side
        metrics["side_confidence"] = {"left": left_mean, "right": right_mean}
        metrics["smoothing"] = {"method": "ema", "alpha": alpha}

        # LLM feedback
        rubric_text = yaml.safe_dump(cfg, sort_keys=False) if cfg else ""
        agent_text = await get_feedback(exercise_id, metrics, rubric_text)

        # One-line summary
        s = (metrics.get("summary") or {})
        total = int(s.get("total_reps", 0) or 0)
        good = int(s.get("good_reps", 0) or 0)
        bad  = int(s.get("bad_reps", 0) or 0)
        one_line = f"{exercise_id}: {total} reps • {good} good • {bad} needs work."

        # Optional weight
        weight = None
        if weight_value:
            try:
                val = float(str(weight_value).replace(",", "."))
                unit = (weight_unit or "kg").lower()
                if unit not in ("kg", "lb"):
                    unit = "kg"
                weight = {"value": val, "unit": unit}
            except Exception:
                weight = None

        # If verified user, save to Firestore server-side
        saved = False
        session_id = None
        if uid:
            payload = {
                "exerciseId": exercise_id,
                "repsCount": total,
                "goodReps": good,
                "badReps": bad,
                "feedbackSummary": one_line,
                "feedbackFull": agent_text,
            }
            if weight:
                payload["weight"] = weight
            sid = save_session(uid, payload)
            if sid:
                saved = True
                session_id = sid

        return JSONResponse({
            "ok": True,
            "exercise_id": exercise_id,
            "analysis_ok": True,
            "fps": fps,
            "metrics": metrics,
            "agent_feedback": agent_text,
            "weight_echo": weight,
            "saved": saved,
            "session_id": session_id,
            # debug/visibility:
            "csv_saved": csv_saved,
            "csv_file": (
                os.path.relpath(csv_path, start=os.path.dirname(base_dir))
                if csv_saved else None
            ),
            "dbg": pose_out.get("dbg", {}),
        })

    except Exception as e:
        log.exception("Analyze failed")
        return JSONResponse(
            {"ok": False, "message": "server_error", "error": str(e)},
            status_code=500
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
