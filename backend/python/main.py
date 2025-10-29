# backend/python/main.py
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
from analysis.trim import trim_active_window  # <-- generic trim
from config_loader import load_exercise_cfg
from analysis.dispatcher import score_reps
from side_selector import (
    pick_primary_side, smooth_samples, write_samples_csv,
)
from analysis.visualize import plot_signal_with_spans
from agents.coach_agent import get_feedback
from services.firebase_db import ensure_firebase, verify_token, save_session

load_dotenv()
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("aicoach")

APP_VERSION = "0.8.7"

app = FastAPI(title="AI Coach Backend", version=APP_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten for prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/healthz")
def healthz():
    return {"ok": True, "model": "movenet_server", "version": APP_VERSION}

def _one_line_summary(ex_id: str, summ: Dict[str, Any]) -> str:
    total = int(summ.get("total_reps", 0) or 0)
    good  = int(summ.get("good_reps", 0) or 0)
    bad   = int(summ.get("bad_reps", 0) or 0)
    return f"{ex_id}: {total} reps • {good} good • {bad} needs work."

def _clockwise90(img_bgr):
    return cv2.rotate(img_bgr, cv2.ROTATE_90_CLOCKWISE)

def _save_sample_images(
    video_path: str,
    sample_indices: List[int],
    stride: int,
    input_fps: float,
    sample_fps: float,
    rotate_deg: int = 90,
    out_dir: Optional[str] = None,
) -> List[str]:
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
    weight_unit: Optional[str] = Form(None),
):
    tmpdir = tempfile.mkdtemp(prefix="aicoach_")
    debug_png_path = os.path.join(os.path.dirname(__file__), "debug_frame.png")
    ROTATE_DEG = 90

    try:
        auth_header = request.headers.get("Authorization", "")
        id_token = auth_header.split(" ", 1)[1].strip() if auth_header.lower().startswith("bearer ") else None

        suffix = os.path.splitext(video.filename or "upload.mp4")[1] or ".mp4"
        tmp_path = os.path.join(tmpdir, f"input{suffix}")
        raw = await video.read()
        with open(tmp_path, "wb") as f:
            f.write(raw)
        log.info("Received: name=%s bytes=%d exercise_id=%s path=%s",
                 video.filename, len(raw), exercise_id, tmp_path)

        # Pose extraction
        t0 = time.time()
        try:
            pose_out: Dict[str, Any] = extract_pose_from_video(
                tmp_path, sample_fps=15.0, max_samples=600, rotate_deg=ROTATE_DEG
            )
        except TypeError:
            log.warning("pose_extractor.extract_pose_from_video() has no rotate_deg parameter; frames will NOT be rotated for inference.")
            pose_out = extract_pose_from_video(tmp_path, sample_fps=15.0, max_samples=600)
        log.info("TIMER pose_extraction: %.3fs (debug_png=%s)", time.time()-t0, debug_png_path)

        if not pose_out.get("ok"):
            return JSONResponse({"ok": False, "message": "pose_extraction_failed"}, status_code=400)

        # Basic validation
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

        # Timing + raw info
        fps = float(pose_out.get("fps", 15.0) or 15.0)
        samples = pose_out.get("samples", [])
        dbg = pose_out.get("dbg", {}) or {}
        stride = int(dbg.get("stride", 2))
        input_fps = float(dbg.get("input_fps", 30.0) or 30.0)

        # Side pick
        t_side = time.time()
        side, side_dbg = pick_primary_side(samples, min_coverage=0.60, conf_margin=0.10)
        log.info("TIMER side_pick: %.3fs (picked=%s, coverage L/R=%.2f/%.2f, med_conf L/R=%.2f/%.2f)",
                 time.time()-t_side,
                 side,
                 side_dbg["coverage"]["left"], side_dbg["coverage"]["right"],
                 side_dbg["median_conf"]["left"], side_dbg["median_conf"]["right"])

        # Load cfg
        cfg = load_exercise_cfg(exercise_id)
        trim_cfg = (cfg.get("trim") or {})
        trim_enabled = False #bool(trim_cfg.get("enabled", True))

        # Generic trim (confidence + motion) – now optional + safe fallback
        t_trim = time.time()
        if not trim_enabled:
            trimmed, lo, hi = samples, 0, len(samples)
            trim_reasons = {"method": "disabled_via_yaml"}
        else:
            trimmed, lo, hi, trim_reasons = trim_active_window(
                samples, fps,
                min_run_s=float(trim_cfg.get("min_run_s", 1.2)),
                pad_s=float(trim_cfg.get("pad_s", 0.35)),
                conf_ema_alpha=float(trim_cfg.get("conf_ema_alpha", 0.25)),
                motion_ema_alpha=float(trim_cfg.get("motion_ema_alpha", 0.35)),
                conf_weight=float(trim_cfg.get("conf_weight", 0.6)),
                motion_weight=float(trim_cfg.get("motion_weight", 0.4)),
                z_active_thresh=float(trim_cfg.get("z_active_thresh", -0.2)),
                z_inactive_thresh=float(trim_cfg.get("z_inactive_thresh", -0.6)),
            )

            # SAFETY RAIL: if trim nuked the window, fall back to no-trim
            min_keep_frames = int(max(1.0, fps) * 0.8)  # ≈ 0.8s
            if (hi - lo) < min_keep_frames:
                log.warning("Trim produced too small window (%d frames) — falling back to no-trim.", hi - lo)
                trimmed, lo, hi = samples, 0, len(samples)
                trim_reasons = {**trim_reasons, "fallback": "window_too_small"}

        head_frames = int(lo)
        tail_frames = int(len(samples) - hi)
        log.info(
            "TIMER trim: %.3fs  (head=%.2fs tail=%.2fs, method=%s)",
            time.time()-t_trim,
            head_frames/max(1.0, fps),
            tail_frames/max(1.0, fps),
            trim_reasons.get("method"),
        )

        # Smooth AFTER trim
        t_smooth = time.time()
        smoothed = smooth_samples(trimmed, alpha_min=0.08, alpha_max=0.35, conf_for_alpha=0.60, max_hold_gap=3)

        # CSV (all landmarks)
        csv_dir = os.path.join(os.path.dirname(__file__), "csvs")
        os.makedirs(csv_dir, exist_ok=True)
        base_name = time.strftime("%Y%m%dT%H%M%SZ") + f"_{exercise_id}_smoothed"
        csv_path = write_samples_csv(smoothed, csv_dir, base_name)
        log.info("TIMER smoothing+csv: %.3fs (csv_saved=%s)", time.time()-t_smooth, bool(csv_path))

        # Score via dispatcher
        t_score = time.time()
        metrics = score_reps(exercise_id, smoothed, fps, cfg, primary_side=side)
        log.info("TIMER scoring: %.3fs", time.time()-t_score)

        # --- Per-rep timestamps (local & global) -------------------------------
        # Use the scorer's fps if provided (stays consistent with plotting/debug)
        evd = (metrics.get("event_debug") or {})
        fps_used = float(evd.get("fps", fps) or fps)

        reps = metrics.get("reps") or []
        rep_times: List[Dict[str, Any]] = []
        for i, r in enumerate(reps, start=1):
            sf = int(r.get("start_frame", 0) or 0)
            bf = int(r.get("bottom_frame", sf) or sf)
            ef = int(r.get("end_frame", sf) or sf)

            start_local  = sf / max(1.0, fps_used)
            bottom_local = bf / max(1.0, fps_used)
            end_local    = ef / max(1.0, fps_used)

            start_global  = (head_frames + sf) / max(1.0, fps_used)
            bottom_global = (head_frames + bf) / max(1.0, fps_used)
            end_global    = (head_frames + ef) / max(1.0, fps_used)

            times = {
                "local":  {"start": start_local,  "bottom": bottom_local,  "end": end_local},
                "global": {"start": start_global, "bottom": bottom_global, "end": end_global},
                "label":  f"Rep {i} — {start_local:.2f}s → {end_local:.2f}s",
            }
            r["times"] = times               # attach to each rep
            rep_times.append({"index": i, **times})

        metrics["rep_times"] = rep_times      # easy to consume on the client
        # -----------------------------------------------------------------------

        summary = metrics.get("summary", {}) or {}
        one_line = _one_line_summary(exercise_id, summary)

        # Event-based logging (adaptive)
        saved_imgs: List[str] = []
        try:
            evd = metrics.get("event_debug", {}) or {}
            series = (evd.get("series") or {})
            fps_dbg = float(evd.get("fps", fps) or fps)
            used_signal = (evd.get("used_signal") or "elbow_angle").lower()

            if used_signal == "knee_angle":
                events_key = "knee_events"; primary_series = np.array(series.get("knee_angle", []), dtype=float)
            elif used_signal == "hip_y":
                events_key = "hip_events"; primary_series = np.array(series.get("hip_y", []), dtype=float)
            else:
                events_key = "elbow_events"; primary_series = np.array(series.get("elbow_angle", []), dtype=float)

            events = (evd.get(events_key) or {})
            tops = [int(x) for x in (events.get("tops") or [])]
            bottoms = [int(x) for x in (events.get("bottoms") or [])]
            used_variant = (events.get("best_variant") or "").lower()

            def _safe_val(arr, idx):
                if 0 <= idx < len(arr) and not (arr[idx] is None or np.isnan(arr[idx])):
                    return float(arr[idx])
                return None

            if len(primary_series) and (tops or bottoms):
                parts = []
                for i in sorted(set(tops + bottoms)):
                    val = _safe_val(primary_series, i)
                    txt = "nan" if val is None else f"{val:6.1f}"
                    tag = "TOP" if i in tops else "BOT"
                    parts.append(f"{i:04d}@{i/max(1.0,fps_dbg):.2f}s:{tag}:{txt}")
                preview = " | ".join(parts[:24])
                if len(parts) > 24:
                    preview += " | ..."
                log.info("[%s events] %s (variant=%s)", used_signal.upper(), preview, used_variant)

                event_global_indices = [head_frames + j for j in sorted(set(tops + bottoms))
                                        if (head_frames + j) < len(samples)]
                saved_imgs = _save_sample_images(
                    tmp_path,
                    event_global_indices,
                    stride=stride,
                    input_fps=input_fps,
                    sample_fps=fps_dbg,
                    rotate_deg=ROTATE_DEG,
                    out_dir=os.path.join(os.path.dirname(__file__), "angleshots"),
                )
        except Exception as e:
            log.debug("Event-based logging failed: %s", e)

        # DEBUG plots + winsor CSV (unchanged, adapts if series present)
        try:
            evd = metrics.get("event_debug", {}) or {}
            fps_dbg = float(evd.get("fps", fps))
            series  = evd.get("series", {}) or {}
            used    = evd.get("used_signal", "elbow_angle")

            plots_dir = os.path.join(os.path.dirname(__file__), "plots")
            os.makedirs(plots_dir, exist_ok=True)

            e_elbow = evd.get("elbow_events", {}) or {}
            e_knee  = evd.get("knee_events", {}) or {}
            e_hip   = evd.get("hip_events", {}) or {}

            ts_label = str(int(time.time()))

            if "elbow_angle" in series and e_elbow:
                plot_signal_with_spans(
                    series=np.array(series["elbow_angle"], dtype=float),
                    fps=fps_dbg,
                    tops=e_elbow.get("tops", []),
                    bottoms=e_elbow.get("bottoms", []),
                    spans=e_elbow.get("spans", []),
                    used_signal="elbow_angle" + (" (USED)" if used == "elbow_angle" else ""),
                    title="Elbow angle — tops/bottoms & counted spans",
                    out_path=os.path.join(plots_dir, f"elbow_{ts_label}.png"),
                )

            if "knee_angle" in series and e_knee:
                plot_signal_with_spans(
                    series=np.array(series["knee_angle"], dtype=float),
                    fps=fps_dbg,
                    tops=e_knee.get("tops", []),
                    bottoms=e_knee.get("bottoms", []),
                    spans=e_knee.get("spans", []),
                    used_signal="knee_angle" + (" (USED)" if used == "knee_angle" else ""),
                    title="Knee angle — tops/bottoms & counted spans",
                    out_path=os.path.join(plots_dir, f"knee_{ts_label}.png"),
                )

            if "hip_y_wins" in series and e_hip:
                plot_signal_with_spans(
                    series=np.array(series["hip_y_wins"], dtype=float),
                    fps=fps_dbg,
                    tops=e_hip.get("tops", []),
                    bottoms=e_hip.get("bottoms", []),
                    spans=e_hip.get("spans", []),
                    used_signal="hip_y" + (" (USED)" if used == "hip_y" else ""),
                    title="Hip-Y (winsorized) — tops/bottoms & counted spans",
                    out_path=os.path.join(plots_dir, f"hip_{ts_label}.png"),
                )

            # CSV
            try:
                csv_dir2 = os.path.join(os.path.dirname(__file__), "csvs")
                os.makedirs(csv_dir2, exist_ok=True)
                wins_csv = os.path.join(csv_dir2, f"{ts_label}_winsorized_series.csv")
                with open(wins_csv, "w", encoding="utf-8") as f:
                    cols = ["frame","t"]
                    has = {k: (k in series) for k in ["elbow_angle","shoulder_y","shoulder_y_wins","knee_angle","hip_y","hip_y_wins"]}
                    for k in ["elbow_angle","shoulder_y","shoulder_y_wins","knee_angle","hip_y","hip_y_wins"]:
                        if has[k]: cols.append(k)
                    f.write(",".join(cols) + "\n")
                    n = max(len(series.get(k, [])) for k in ["elbow_angle","shoulder_y","shoulder_y_wins","knee_angle","hip_y","hip_y_wins"])
                    for i in range(n):
                        tsec = i / max(1.0, fps_dbg)
                        row = [str(i), f"{tsec:.3f}"]
                        for k in ["elbow_angle","shoulder_y","shoulder_y_wins","knee_angle","hip_y","hip_y_wins"]:
                            if has[k]:
                                v = series[k][i] if i < len(series[k]) else None
                                row.append("" if v is None else str(v))
                        f.write(",".join(row) + "\n")
                wins_cfg = evd.get("winsor", {"lo": 0.10, "hi": 0.90})
                log.info("WINS CSV: %s (winsor lo/hi=%.2f/%.2f)", wins_csv, wins_cfg.get("lo",0.1), wins_cfg.get("hi",0.9))
            except Exception as e:
                log.exception("Failed writing winsorized CSV: %s", e)

            log.info("PLOTS: generated for %s (and alternate) in %s", used, plots_dir)
        except Exception as e:
            log.exception("Plot generation failed: %s", e)

        # Weight echo
        weight = None
        if weight_value:
            try:
                val = float(str(weight_value).replace(",", "."))
                unit = (weight_unit or "kg").lower()
                unit = unit if unit in ("kg","lb") else "kg"
                weight = {"value": val, "unit": unit}
            except Exception:
                weight = None

        # Feedback (improved fallback for 0 reps)
        try:
            agent_text = await get_feedback(exercise_id, metrics, "")
        except Exception as e:
            total = int(summary.get('total_reps',0))
            if total == 0:
                agent_text = (
                    "I couldn’t detect any complete reps in this clip. "
                    "Try: keep your full body in frame, good lighting, and perform at least 3 continuous reps."
                )
            else:
                agent_text = (
                    f"Total reps: {total}, Good: {int(summary.get('good_reps',0))}, "
                    f"Needs work: {int(summary.get('bad_reps',0))}. "
                    f"(trim: removed ~{head_frames/max(1.0,fps):.1f}s from start, ~{tail_frames/max(1.0,fps):.1f}s from end)"
                )
            log.exception("LLM feedback failed; using fallback: %s", e)

        # Save to Firestore (unchanged)
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
                    "debug": {"angleshots_saved": len(saved_imgs)},
                    "repTimes": metrics.get("rep_times", []),
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
