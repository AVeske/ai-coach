# backend/python/main.py
import os, shutil, tempfile, logging, yaml
from typing import Any, Dict

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

# --- local modules ---
from pose_extractor import extract_pose_from_video                  # MoveNet Thunder extractor (JSON + CSV)
from analysis.validators import basic_validation                    # human/motion gate
from analysis.dispatcher import score_reps                          # <-- dispatcher (replaces analysis.scoring)
from agents.coach_agent import get_feedback                         # async LLM feedback

load_dotenv()
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("aicoach")

app = FastAPI(title="AI Coach Backend", version="0.6.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],           # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/healthz")
def healthz():
    return {"ok": True, "model": "movenet_server", "version": "0.6.0"}

def _load_rubric(ex_id: str) -> Dict[str, Any]:
    """
    Load exercise YAML (e.g., backend/python/configs/pushup.yaml).
    Returns {} if not found (agent will fall back to generic feedback).
    """
    base = os.path.dirname(__file__)
    fname = os.path.join(base, "configs", f"{ex_id}.yaml")
    if not os.path.exists(fname):
        return {}
    with open(fname, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

@app.post("/analyze")
async def analyze_video(
    exercise_id: str = Form(...),          # slug like "pushup" or "squats"
    video: UploadFile = File(...),
):
    tmpdir = tempfile.mkdtemp(prefix="aicoach_")
    try:
        # Save upload to temp
        suffix = os.path.splitext(video.filename or "upload.mp4")[1] or ".mp4"
        tmp_path = os.path.join(tmpdir, f"input{suffix}")
        raw = await video.read()
        with open(tmp_path, "wb") as f:
            f.write(raw)
        log.info("Received: name=%s bytes=%d exercise_id=%s path=%s",
                 video.filename, len(raw), exercise_id, tmp_path)

        # Pose extraction (MoveNet Thunder)
        pose_out: Dict[str, Any] = extract_pose_from_video(
            tmp_path,
            sample_fps=15.0,     # 15–20 FPS recommended
            max_samples=600,     # cap ~30–40s
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

        # Score reps (dispatcher calls the right per-exercise scorer)
        fps = float(pose_out.get("fps", 30.0) or 30.0)
        samples = pose_out.get("samples", [])
        metrics = score_reps(exercise_id, samples, fps, cfg)

        # LLM feedback
        rubric_text = yaml.safe_dump(cfg, sort_keys=False) if cfg else ""
        agent_text = await get_feedback(exercise_id, metrics, rubric_text)

        return JSONResponse({
            "ok": True,
            "exercise_id": exercise_id,
            "analysis_ok": True,
            "fps": fps,
            "metrics": metrics,
            "agent_feedback": agent_text,
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
