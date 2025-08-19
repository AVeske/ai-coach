import os, shutil, tempfile, logging, yaml
from typing import Any, Dict

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

# --- local modules ---
from pose_extractor import extract_pose_from_video
from analysis.validators import basic_validation
from analysis.dispatcher import score_reps
from agents.coach_agent import get_feedback

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
    base = os.path.dirname(__file__)
    fname = os.path.join(base, "configs", f"{ex_id}.yaml")
    if not os.path.exists(fname):
        return {}
    with open(fname, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

# --- filming side inference ---
LEFT = ["left_shoulder","left_elbow","left_wrist","left_hip","left_knee","left_ankle"]
RIGHT = ["right_shoulder","right_elbow","right_wrist","right_hip","right_knee","right_ankle"]

def infer_side(samples):
    def mean_conf(names):
        tot = cnt = 0.0
        for s in samples:
            lm = s.get("landmarks", {})
            for n in names:
                v = lm.get(n)
                if v and v[2] is not None:
                    tot += float(v[2]); cnt += 1
        return (tot / cnt) if cnt else 0.0
    ml = mean_conf(LEFT)
    mr = mean_conf(RIGHT)
    return ("left" if ml >= mr else "right", ml, mr)

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
            sample_fps=15.0,
            max_samples=600,
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

        # Choose filming side before temp cleanup
        fps = float(pose_out.get("fps", 30.0) or 30.0)
        samples = pose_out.get("samples", [])
        side, left_mean, right_mean = infer_side(samples)

        # Score reps (unchanged)
        metrics = score_reps(exercise_id, samples, fps, cfg)

        # Attach side info
        metrics["selected_side"] = side
        metrics["side_confidence"] = {"left": left_mean, "right": right_mean}

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
