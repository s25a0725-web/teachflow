# -*- coding: utf-8 -*-
"""TeachFlow Study Space — distraction-free study environment.

Pomodoro timer, study-session tracker (persisted per user), ambient sounds
(generated in-browser, no audio files), a music player for user-uploaded
tracks, and a DeepSeek study assistant. No copyrighted audio is bundled.
"""
import json
import os
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from uuid import uuid4

from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify, send_from_directory

from db import get_db
from i18n import t
import userstore

bp = Blueprint("studyspace", __name__, url_prefix="/study-space")

_BASE = Path(__file__).resolve().parent
_UPLOAD = Path(os.environ.get("TEACHFLOW_UPLOAD_ROOT", str(_BASE / "uploads"))) / "studyspace"
_UPLOAD.mkdir(parents=True, exist_ok=True)

ALLOWED_AUDIO = (".mp3", ".m4a", ".wav", ".ogg", ".aac")


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return wrapper


def _json_body():
    return request.get_json(silent=True) or {}


def _uid():
    return session["user_id"]


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------
@bp.route("/")
@login_required
def index():
    db = get_db()
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    week_start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")

    def total_since(since):
        r = db.execute(
            "SELECT COALESCE(SUM(focus_minutes),0) AS m FROM study_sessions "
            "WHERE teacher_id = ? AND completed = 1 AND started_at >= ?",
            (session["user_id"], since),
        ).fetchone()
        return r["m"] or 0

    stats = {
        "total_minutes": total_since("1970-01-01"),
        "today_minutes": total_since(today),
        "week_minutes": total_since(week_start),
        "sessions": db.execute(
            "SELECT COUNT(*) AS c FROM study_sessions WHERE teacher_id = ? AND completed = 1",
            (session["user_id"],),
        ).fetchone()["c"],
    }
    tracks = db.execute(
        "SELECT id, title, artist, filename FROM studyspace_tracks WHERE teacher_id = ? ORDER BY id DESC",
        (session["user_id"],),
    ).fetchall()
    db.close()
    return render_template("studyspace.html", stats=stats, tracks=[dict(r) for r in tracks])


# ---------------------------------------------------------------------------
# Session tracker
# ---------------------------------------------------------------------------
@bp.route("/session/start", methods=["POST"])
@login_required
def session_start():
    payload = _json_body()
    focus = int(payload.get("focus_minutes") or 25)
    db = get_db()
    cur = db.execute(
        "INSERT INTO study_sessions (teacher_id, focus_minutes, completed) VALUES (?,?,0)",
        (session["user_id"], focus),
    )
    db.commit()
    sid = cur.lastrowid
    db.close()
    return jsonify({"ok": True, "id": sid})


@bp.route("/session/complete", methods=["POST"])
@login_required
def session_complete():
    payload = _json_body()
    sid = payload.get("id")
    db = get_db()
    db.execute(
        "UPDATE study_sessions SET completed = 1, ended_at = datetime('now') WHERE id = ? AND teacher_id = ?",
        (sid, session["user_id"]),
    )
    db.commit()
    db.close()
    return jsonify({"ok": True})


@bp.route("/stats", methods=["GET"])
@login_required
def stats():
    db = get_db()
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    week_start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")

    def total_since(since):
        r = db.execute(
            "SELECT COALESCE(SUM(focus_minutes),0) AS m FROM study_sessions "
            "WHERE teacher_id = ? AND completed = 1 AND started_at >= ?",
            (session["user_id"], since),
        ).fetchone()
        return r["m"] or 0

    total = total_since("1970-01-01")
    today_m = total_since(today)
    week_m = total_since(week_start)
    db.close()
    return jsonify({"total": total, "today": today_m, "week": week_m})


# ---------------------------------------------------------------------------
# Music player (user-uploaded tracks only — no bundled copyrighted audio)
# ---------------------------------------------------------------------------
@bp.route("/tracks", methods=["GET"])
@login_required
def tracks():
    db = get_db()
    rows = db.execute(
        "SELECT id, title, artist, filename FROM studyspace_tracks WHERE teacher_id = ? ORDER BY id DESC",
        (session["user_id"],),
    ).fetchall()
    db.close()
    return jsonify({"tracks": [dict(r) for r in rows]})


@bp.route("/upload", methods=["POST"])
@login_required
def upload_track():
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error": "no_file"}), 400
    ext = Path(f.filename).suffix.lower()
    if ext not in ALLOWED_AUDIO:
        return jsonify({"error": "bad_type"}), 400
    name = uuid4().hex + ext
    f.save(_UPLOAD / name)
    title = request.form.get("title", "").strip() or Path(f.filename).stem
    artist = request.form.get("artist", "").strip() or ""
    db = get_db()
    cur = db.execute(
        "INSERT INTO studyspace_tracks (teacher_id, title, artist, filename) VALUES (?,?,?,?)",
        (session["user_id"], title, artist, name),
    )
    db.commit()
    tid = cur.lastrowid
    db.close()
    return jsonify({"ok": True, "id": tid})


@bp.route("/track/<name>")
@login_required
def track_file(name):
    from werkzeug.utils import secure_filename
    name = secure_filename(name)
    return send_from_directory(str(_UPLOAD), name)


# ---------------------------------------------------------------------------
# AI study assistant (reuses DeepSeek)
# ---------------------------------------------------------------------------
@bp.route("/assistant", methods=["POST"])
@login_required
def assistant():
    from ai_provider import complete, configured
    payload = _json_body()
    question = (payload.get("question") or "").strip()
    if not question:
        return jsonify({"error": "empty"}), 400
    if not configured():
        return jsonify({"error": "no_key"}), 503
    system = (
        "You are a friendly study tutor for Malaysian school students. Answer in the "
        "language the student used. Explain clearly, give examples, and keep it "
        "age-appropriate. If the student asks for revision notes, summarise key points "
        "as bullet lists. Never give harmful or unsafe advice."
    )
    try:
        answer = complete([{"role": "system", "content": system},
                           {"role": "user", "content": question}],
                          max_tokens=1200, temperature=0.5)
    except Exception as e:
        return jsonify({"error": "ai_error", "detail": str(e)}), 502
    return jsonify({"answer": answer})
