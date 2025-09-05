import os, shutil, tempfile, logging, time
from typing import Any, Dict, Optional, List

import cv2
from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import numpy as np

# --- local modules ---
from pose_extractor import extract_pose_from_video
from analysis.validators import basic_validation
from analysis.trim import trim_active_window
from config_loader import load_exercise_cfg
from analysis.chest_scorers import score_pushup
from side_selector import (
    pick_primary_side, smooth_samples, write_samples_csv,
    elbow_angle_series_for_side,
)
from agents.coach_agent import get_feedback
from services.firebase_db import ensure_firebase, verify_token, save_session

load_dotenv()
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("aicoach")

app = FastAPI(title="AI Coach Backend", version="0.8.3")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten for prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/healthz")
def healthz():
    return {"ok": True, "model": "movenet_server", "version": "0.8.3"}

def _one_line_summary(ex_id: str, summ: Dict[str, Any]) -> str:
    total = int(summ.get("total_reps", 0) or 0)
    good  = int(summ.get("good_reps", 0) or 0)
    bad   = int(summ.get("bad_reps", 0) or 0)
    return f"{ex_id}: {total} reps • {good} good • {bad} needs work."

def _clockwise90(img_bgr):
    return cv2.rotate(img_bgr, cv2.ROTATE_90_CLOCKWISE)

def _save_sample_images(
    video_path: str,
    sample_indices: List[int],     # indices in sampled space
    stride: int,                   # pose_out['dbg']['stride']
    input_fps: float,              # pose_out['dbg']['input_fps']
    sample_fps: float,             # pose_out['fps']
    rotate_deg: int = 90,
    out_dir: Optional[str] = None,
) -> List[str]:
    """
    Save PNGs for the given sampled indices (for visual inspection only).
    Rotation here is just for the saved pictures (the model rotation happens in pose_extractor).
    """
    if out_dir is None:
        out_dir = os.path.join(os.path.dirname(__file__), "angleshots")
    os.makedirs(out_dir, exist_ok=True)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return []

    saved = []
    try:
        for idx in sample_indices:
            raw_frame_no = int(round(idx * max(1, stride)))
            cap.set(cv2.CAP_PROP_POS_FRAMES, raw_frame_no)
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            # rotate image for inspection if requested
            if rotate_deg % 360 == 90:
                frame = _clockwise90(frame)
            elif rotate_deg % 360 == 180:
                frame = cv2.rotate(frame, cv2.ROTATE_180)
            elif rotate_deg % 360 == 270:
                frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

            t_sec = float(idx) / max(1.0, sample_fps)
            fname = f"{raw_frame_no:06d}_{t_sec:08.3f}s.png"
            fpath = os.path.join(out_dir, fname)
            cv2.imwrite(fpath, frame)
            saved.append(fpath)
    finally:
        cap.release()
    return saved

@app.post("/analyze")
async def analyze_video(
    request: Request,
    exercise_id: str = Form(...),
    video: UploadFile = File(...),
    weight_value: Optional[str] = Form(None),
    weight_unit: Optional[str] = Form(None),  # 'kg' | 'lb'
):
    tmpdir = tempfile.mkdtemp(prefix="aicoach_")
    debug_png_path = os.path.join(os.path.dirname(__file__), "debug_frame.png")
    ROTATE_DEG = 90  # rotate frames for the model inside pose_extractor

    try:
        # --- ID token (if present) ---
        auth_header = request.headers.get("Authorization", "")
        id_token = auth_header.split(" ", 1)[1].strip() if auth_header.lower().startswith("bearer ") else None

        # --- Save upload to temp ---
        suffix = os.path.splitext(video.filename or "upload.mp4")[1] or ".mp4"
        tmp_path = os.path.join(tmpdir, f"input{suffix}")
        raw = await video.read()
        with open(tmp_path, "wb") as f:
            f.write(raw)
        log.info("Received: name=%s bytes=%d exercise_id=%s path=%s",
                 video.filename, len(raw), exercise_id, tmp_path)

        # --- Pose extraction (rotation happens inside) ---
        t0 = time.time()
        pose_out: Dict[str, Any] = extract_pose_from_video(
            tmp_path, sample_fps=15.0, max_samples=600, rotate_deg=ROTATE_DEG, save_debug_png=True
        )
        log.info("TIMER pose_extraction: %.3fs (debug_png=%s)", time.time()-t0, debug_png_path)

        if not pose_out.get("ok"):
            return JSONResponse({"ok": False, "message": "pose_extraction_failed"}, status_code=400)

        # --- Basic validation ---
        t1 = time.time()
        gate = basic_validation(pose_out)
        log.info("TIMER validation: %.3fs", time.time()-t1)
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

        # Timing and samples
        fps = float(pose_out.get("fps", 15.0) or 15.0)
        samples = pose_out.get("samples", [])
        dbg = pose_out.get("dbg", {}) or {}
        stride = int(dbg.get("stride", 2))
        input_fps = float(dbg.get("input_fps", 30.0) or 30.0)

        # --- Global side selection ---
        t_side = time.time()
        side, side_dbg = pick_primary_side(samples, min_coverage=0.60, conf_margin=0.10)
        log.info("TIMER side_pick: %.3fs (picked=%s, coverage L/R=%.2f/%.2f, med_conf L/R=%.2f/%.2f)",
                 time.time()-t_side,
                 side,
                 side_dbg["coverage"]["left"], side_dbg["coverage"]["right"],
                 side_dbg["median_conf"]["left"], side_dbg["median_conf"]["right"])

        # --- Trim (rep-envelope preferred; motion fallback) ---
        t_trim = time.time()
        trimmed, lo, hi, trim_reasons = trim_active_window(
            samples, fps,
            min_run_s=1.2,
            pad_s=0.35,
        )
        head_frames = int(lo)
        tail_frames = int(len(samples) - hi)
        log.info(
            "TIMER trim: %.3fs  (head=%.2fs tail=%.2fs, method=%s)",
            time.time()-t_trim,
            head_frames/max(1.0, fps),
            tail_frames/max(1.0, fps),
            trim_reasons.get("method"),
        )

        # --- Smooth AFTER trim ---
        t_smooth = time.time()
        smoothed = smooth_samples(trimmed, alpha_min=0.08, alpha_max=0.35, conf_for_alpha=0.60, max_hold_gap=3)
        # CSV for inspection
        csv_dir = os.path.join(os.path.dirname(__file__), "csvs")
        os.makedirs(csv_dir, exist_ok=True)
        base_name = time.strftime("%Y%m%dT%H%M%SZ") + f"_{exercise_id}_smoothed"
        csv_path = write_samples_csv(smoothed, csv_dir, base_name)
        log.info("TIMER smoothing+csv: %.3fs (csv_saved=%s)", time.time()-t_smooth, bool(csv_path))

        # --- Angle logging ~1Hz and save corresponding frames ---
        elbow_series = elbow_angle_series_for_side(smoothed, side, conf_thresh=0.30)
        hz_step = max(1, int(round(fps)))  # ~1Hz in sampled space
        log_parts = []
        img_indices = []
        for i in range(0, len(elbow_series), hz_step):
            ang = elbow_series[i]
            if ang is None or (isinstance(ang, float) and np.isnan(ang)):
                txt = "  nan"
            else:
                txt = f"{ang:6.1f}°"
            log_parts.append(f"{i:04d}: {txt}")
            img_indices.append(i)
        if log_parts:
            preview = " | ".join(log_parts[:12])
            if len(log_parts) > 12:
                preview += " | ..."
            log.info("[ELBOW ~1Hz] %s", preview)

        # Save the frames for those indices (global sampled indices = head + local)
        global_sample_indices = [head_frames + j for j in img_indices if (head_frames + j) < len(samples)]
        saved_imgs = _save_sample_images(
            tmp_path,
            global_sample_indices,
            stride=stride,
            input_fps=input_fps,
            sample_fps=fps,
            rotate_deg=ROTATE_DEG,
            out_dir=os.path.join(os.path.dirname(__file__), "angleshots"),
        )

        # --- Score ---
        cfg = load_exercise_cfg(exercise_id)
        t_score = time.time()
        if exercise_id.lower() == "pushup":
            metrics = score_pushup(smoothed, fps, cfg, primary_side=side)
        else:
            metrics = {"reps": [], "summary": {"total_reps": 0, "good_reps": 0, "bad_reps": 0}}
        log.info("TIMER scoring: %.3fs", time.time()-t_score)

        summary = metrics.get("summary", {}) or {}
        one_line = _one_line_summary(exercise_id, summary)

        # --- Optional weight payload ---
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

        # --- LLM feedback (with fallback) ---
        try:
            agent_text = await get_feedback(exercise_id, metrics, "")
        except Exception as e:
            agent_text = (
                f"Total reps: {int(summary.get('total_reps',0))}, "
                f"Good: {int(summary.get('good_reps',0))}, "
                f"Needs work: {int(summary.get('bad_reps',0))}. "
                f"(trim: removed ~{head_frames/max(1.0,fps):.1f}s from start, ~{tail_frames/max(1.0,fps):.1f}s from end)"
            )
            log.exception("LLM feedback failed; using fallback: %s", e)

        # --- Save to Firestore if we can verify the user ---
        saved = False
        session_id = None
        if id_token and ensure_firebase():
            uid = verify_token(id_token)
            if uid:
                payload: Dict[str, Any] = {
                    "exerciseId": exercise_id,
                    "repsCount": int(summary.get("total_reps", 0) or 0),
                    "goodReps": int(summary.get("good_reps", 0) or 0),
                    "badReps": int(summary.get("bad_reps", 0) or 0),
                    "feedbackSummary": one_line,
                    "feedbackFull": agent_text,
                    "source": "server",
                    "selectedSide": side,
                    "sideDebug": side_dbg,
                    "analyzedWindow": {
                        "frames": int(len(smoothed)),
                        "start_sec": head_frames / max(1.0, fps),
                        "end_sec": hi / max(1.0, fps),
                    },
                    "trim": {
                        "headSec": head_frames / max(1.0, fps),
                        "tailSec": tail_frames / max(1.0, fps),
                        "reasons": trim_reasons,
                    },
                    "debug": {
                        "angleshots_saved": len(saved_imgs),
                    }
                }
                if weight:
                    payload["weight"] = weight

                t_save = time.time()
                sid = save_session(uid, payload)
                log.info("TIMER firestore_save: %.3fs (saved=%s)", time.time()-t_save, bool(sid))
                if sid:
                    saved = True
                    session_id = sid

        return JSONResponse({
            "ok": True,
            "exercise_id": exercise_id,
            "analysis_ok": True,
            "fps": fps,
            "selected_side": side,
            "side_debug": side_dbg,
            "metrics": metrics,
            "agent_feedback": agent_text,
            "weight_echo": weight,
            "saved": saved,
            "session_id": session_id,
            "csv_path": csv_path,
            "angleshots": saved_imgs,
            "analyzed_window": {
                "frames": int(len(smoothed)),
                "start_sec": head_frames / max(1.0, fps),
                "end_sec": hi / max(1.0, fps),
            },
            "trim": {
                "headSec": head_frames / max(1.0, fps),
                "tailSec": tail_frames / max(1.0, fps),
                "reasons": trim_reasons,
            },
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
