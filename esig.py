# -*- coding: utf-8 -*-
"""Shared electronic-signature service for the five document generators.

Signatures are stored as PNG images (drawn on a canvas, or uploaded) or as a
typed signature. Every signer must authorise their own signature: the route
records the signer identity, tool, doc id, role and a timestamp (audit trail).
A signature is never created for another person — the logged-in teacher can
only sign with their own identity.
"""
import base64
import os
from functools import wraps
from pathlib import Path
from uuid import uuid4

from flask import Blueprint, request, session, redirect, url_for, jsonify, send_from_directory
from werkzeug.utils import secure_filename

from db import get_db
import userstore

bp = Blueprint("esig", __name__, url_prefix="/esig")

_BASE = Path(__file__).resolve().parent
_SIG_DIR = Path(os.environ.get("TEACHFLOW_UPLOAD_ROOT", str(_BASE / "uploads"))) / "sdg_sigs"
_SIG_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_IMG = (".png", ".jpg", ".jpeg")


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return wrapper


def _json_body():
    return request.get_json(silent=True) or {}


def _signer():
    u = userstore.get_by_id(session["user_id"])
    return {
        "name": (u or {}).get("name") or session.get("name") or "",
        "email": (u or {}).get("email") or "",
    }


def save_signature_image(data_url):
    """Decode a PNG data URL into a file; return stored filename or None."""
    if not data_url or "," not in data_url:
        return None
    try:
        data = base64.b64decode(data_url.split(",", 1)[1])
    except Exception:
        return None
    if not data:
        return None
    fname = uuid4().hex + ".png"
    (_SIG_DIR / fname).write_bytes(data)
    return fname


def signature_path(fname):
    """Absolute path for a stored signature, or None if missing."""
    if not fname:
        return None
    p = _SIG_DIR / secure_filename(fname)
    return str(p) if p.exists() else None


def resolve_signatures(data):
    """Convert client signature data-URLs into stored files (in place).

    `data["signatures"]` may be a dict {role: {type, signature, signer_name}}
    or a list. Any entry with a data-URL 'signature' is saved to disk and its
    'file' key is set, so the doc builders can embed it.
    """
    sigs = data.get("signatures")
    if not sigs:
        return data

    def fix(entry):
        if not isinstance(entry, dict):
            return entry
        if entry.get("type") in ("draw", "upload") and entry.get("signature"):
            fname = save_signature_image(entry["signature"])
            if fname:
                entry["file"] = fname
        return entry

    if isinstance(sigs, dict):
        for role, entry in sigs.items():
            sigs[role] = fix(entry)
    elif isinstance(sigs, list):
        data["signatures"] = [fix(s) for s in sigs]
    return data


@bp.route("/save", methods=["POST"])
@login_required
def save():
    """Save a signature (draw data URL, uploaded image, or typed)."""
    signer = _signer()
    payload = _json_body()
    sig_type = payload.get("type") or "draw"

    fname = None
    if sig_type in ("draw", "upload"):
        data_url = payload.get("signature") or ""
        fname = save_signature_image(data_url)
        if not fname:
            return jsonify({"error": "bad_signature"}), 400
    # typed: no image, sign_type records it as typed

    signer_name = payload.get("signer_name", "").strip() or signer["name"]
    db = get_db()
    cur = db.execute(
        "INSERT INTO sdg_signatures (teacher_id, tool, doc_id, role, signer_name, signer_email, "
        "signature_file, sign_type) VALUES (?,?,?,?,?,?,?,?)",
        (session["user_id"], payload.get("tool") or "", payload.get("doc_id"),
         payload.get("role") or "", signer_name, signer["email"], fname, sig_type),
    )
    db.commit()
    sid = cur.lastrowid
    db.close()
    return jsonify({"ok": True, "id": sid, "file": fname,
                    "url": url_for("esig.file", name=fname) if fname else None})


@bp.route("/file/<name>")
@login_required
def file(name):
    name = secure_filename(name)
    return send_from_directory(str(_SIG_DIR), name)


@bp.route("/list", methods=["GET"])
@login_required
def list_signatures():
    db = get_db()
    rows = db.execute(
        "SELECT id, tool, doc_id, role, signer_name, signer_email, sign_type, signature_file, created_at "
        "FROM sdg_signatures WHERE teacher_id = ? ORDER BY id DESC LIMIT 50",
        (session["user_id"],),
    ).fetchall()
    db.close()
    return jsonify({"signatures": [dict(r) for r in rows]})
