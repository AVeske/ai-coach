from __future__ import annotations
import os
from typing import Optional, Dict, Any

import firebase_admin
from firebase_admin import credentials, auth, firestore

import logging
log = logging.getLogger("aicoach")

_app_inited = False
_db: Optional[firestore.Client] = None

def ensure_firebase() -> bool:
    """
    Initialize Firebase Admin SDK once.
    Requires GOOGLE_APPLICATION_CREDENTIALS (service account JSON),
    or Application Default Credentials (gcloud), and ideally FIREBASE_PROJECT_ID.
    """
    global _app_inited, _db
    if _app_inited:
        return _db is not None
    try:
        if not firebase_admin._apps:
            cred = None
            sa = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            if sa and os.path.exists(sa):
                cred = credentials.Certificate(sa)
                log.info("Firebase Admin: using service account JSON at %s", sa)
            else:
                cred = credentials.ApplicationDefault()
                log.info("Firebase Admin: using Application Default Credentials")

            project_id = os.getenv("FIREBASE_PROJECT_ID")
            if project_id:
                firebase_admin.initialize_app(cred, {"projectId": project_id})
                log.info("Firebase Admin initialized (projectId=%s)", project_id)
            else:
                firebase_admin.initialize_app(cred)
                log.info("Firebase Admin initialized (projectId autodetect)")

        _db = firestore.client()
        _app_inited = True
        return True
    except Exception as e:
        log.exception("Firebase Admin init FAILED: %s", e)
        _db = None
        _app_inited = True
        return False

def verify_token(id_token: Optional[str]) -> Optional[str]:
    """
    Verify Firebase ID token from Authorization: Bearer <token>.
    Returns uid or None if invalid/missing.
    """
    if not id_token:
        log.warning("verify_token: missing id_token")
        return None
    try:
        decoded = auth.verify_id_token(id_token)
        uid = decoded.get("uid")
        if not uid:
            log.warning("verify_token: decoded but no uid present")
        return uid
    except Exception as e:
        log.warning("verify_token: FAILED to verify token: %s", e)
        return None

def save_session(uid: str, payload: Dict[str, Any]) -> Optional[str]:
    """
    Write a session document under users/{uid}/sessions.
    Returns document id, or None if failed/unavailable.
    """
    if _db is None and not ensure_firebase():
        log.error("save_session: Firestore client unavailable")
        return None

    data = dict(payload)
    # Use server timestamp so ordering is consistent
    data.setdefault("createdAt", firestore.SERVER_TIMESTAMP)
    data.setdefault("source", "server")

    try:
        ref = _db.collection("users").document(uid).collection("sessions").document()
        ref.set(data)
        log.info("save_session: wrote session for uid=%s doc=%s", uid, ref.id)
        return ref.id
    except Exception as e:
        log.exception("save_session: FAILED to write session: %s", e)
        return None
