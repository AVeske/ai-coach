# main.py
import os, shutil, tempfile, logging
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from pose_extractor import extract_pose_from_video
from analysis.rules import make_feedback

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("aicoach")

app = FastAPI(title="AI Coach Backend", version="0.1.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.post("/analyze")
async def analyze(
    exercise: str = Form(...),
    video: UploadFile = File(...),
):
    tmpdir = tempfile.mkdtemp(prefix="aicoach_")
    try:
        suffix = os.path.splitext(video.filename or "upload.mp4")[1] or ".mp4"
        tmp_path = os.path.join(tmpdir, f"input{suffix}")

        received_bytes = 0
        with open(tmp_path, "wb") as f:
            chunk = await video.read()  # read all because file is small (<=30s)
            received_bytes = len(chunk or b"")
            f.write(chunk or b"")

        log.info("Received upload: name=%s bytes=%s exercise=%s path=%s",
                 video.filename, received_bytes, exercise, tmp_path)

        pose_out = extract_pose_from_video(tmp_path, max_frames=48, model_complexity=2)
        analyzed_ok = bool(pose_out.get("ok"))
        frames = int(pose_out.get("frames", 0))

        # You can still compute the natural-language feedback if you want
        feedback_text = make_feedback(exercise, pose_out) if analyzed_ok else "Pose extraction failed."

        log.info("Analysis: ok=%s frames=%s", analyzed_ok, frames)

        return JSONResponse({
            "ok": True,
            "message": "Success",
            "received_bytes": received_bytes,
            "exercise": exercise,
            "analysis_ok": analyzed_ok,
            "frames": frames,
            "feedback": feedback_text,  # you can hide this if you only want 'Success'
        })
    finally:
        try:
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass
