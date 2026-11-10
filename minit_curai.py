# -*- coding: utf-8 -*-
"""Minit Curai module — KPM-style meeting/briefing minutes generation & export.

Teachers enter programme details and discussion notes; the AI formalises them
into numbered discussion points and follow-up actions in proper Bahasa Melayu;
the backend exports a two-page A4 document (PDF / DOCX) reproducing the school
reference layout, including uploaded evidence photos and signature blocks.
"""
import json
import os
import re
from datetime import datetime
from functools import wraps
from pathlib import Path
from uuid import uuid4

from flask import (
    Blueprint, render_template, request, session, redirect, url_for,
    jsonify, Response, send_from_directory,
)
from werkzeug.utils import secure_filename

from db import get_db, get_setting
from i18n import t
import userstore
from minit_doc import build_minit_pdf, build_minit_docx, FIELDS
from views import BRANDING_DIR

bp = Blueprint("minit", __name__, url_prefix="/minit-curai")

_BASE = Path(__file__).resolve().parent
_UPLOAD = Path(os.environ.get("TEACHFLOW_UPLOAD_ROOT", str(_BASE / "uploads"))) / "minit"
_UPLOAD.mkdir(parents=True, exist_ok=True)

ALLOWED_IMG = (".png", ".jpg", ".jpeg", ".webp")


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return wrapper


def _school_info():
    return {
        "school_name": get_setting("school_name") or "SJK(T) Sepang",
        "school_name_en": get_setting("school_name_en") or "",
        "school_address": get_setting("school_address") or "",
    }


def _json_body():
    return request.get_json(silent=True) or {}


# ---------------------------------------------------------------------------
# AI generation
# ---------------------------------------------------------------------------
def _ai_minit(fields, lang):
    from ai_provider import complete, configured
    if not configured():
        return None
    system = (
        "You are an expert Malaysian school clerk. Convert the provided meeting/briefing "
        "details into formal, correct Bahasa Melayu for a MINIT CURAI document. "
        "Output ONLY valid JSON (no markdown, no commentary) with exactly these keys: "
        '{"isu": ["numbered discussion point", ...], "tindakan": ["follow-up action", ...], "bahan": ["material", ...]}. '
        "'isu' is a list of 3-8 specific, correctly worded discussion points derived from the notes. "
        "'tindakan' is a list of 1-5 actionable follow-up items with a responsible party where known. "
        "'bahan' is a list of distributed materials, or an empty list if none. "
        "Never invent dates, attendee names, venues, or decisions not present in the input. "
        "Fix grammar and spelling, avoid repetition, use accurate educational terminology."
    )
    user = "Butiran program:\n" + json.dumps(fields, ensure_ascii=False)
    try:
        raw = complete([{"role": "system", "content": system},
                        {"role": "user", "content": user}], max_tokens=1500, temperature=0.5)
    except Exception:
        return None
    return _parse_json(raw)


def _parse_json(raw):
    text = (raw or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except ValueError:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            return None
        try:
            data = json.loads(m.group(0))
        except ValueError:
            return None
    return data if isinstance(data, dict) else None


def _split_lines(val):
    """Turn free-form text into a list of non-empty lines."""
    if isinstance(val, list):
        return [str(x).strip() for x in val if str(x).strip()]
    if not val:
        return []
    return [ln.strip() for ln in str(val).split("\n") if ln.strip()]


def _normalise(data, fields):
    out = dict(fields)
    out["isu"] = _split_lines(data.get("isu"))
    out["tindakan"] = _split_lines(data.get("tindakan"))
    out["bahan"] = _split_lines(data.get("bahan"))
    out["photos"] = data.get("photos") or []
    out["disediakan_nama"] = data.get("disediakan_nama") or ""
    out["disediakan_jawatan"] = data.get("disediakan_jawatan") or ""
    out["disediakan_tarikh"] = data.get("disediakan_tarikh") or ""
    out["disahkan_nama"] = data.get("disahkan_nama") or ""
    out["disahkan_jawatan"] = data.get("disahkan_jawatan") or ""
    out["disahkan_sekolah"] = data.get("disahkan_sekolah") or out.get("school_name") or ""
    return out


# ---------------------------------------------------------------------------
# Photo upload
# ---------------------------------------------------------------------------
@bp.route("/photo", methods=["POST"])
@login_required
def upload_photo():
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error": "no_file"}), 400
    ext = Path(f.filename).suffix.lower()
    if ext not in ALLOWED_IMG:
        return jsonify({"error": "bad_type"}), 400
    name = uuid4().hex + ext
    f.save(_UPLOAD / name)
    return jsonify({"name": name, "url": url_for("minit.photo", name=name)})


@bp.route("/photo/<name>")
@login_required
def photo(name):
    name = secure_filename(name)
    return send_from_directory(str(_UPLOAD), name)


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------
@bp.route("/")
@login_required
def index():
    lang_code = session.get("lang", "en")
    return render_template("minit_curai.html", school=_school_info(), fields=FIELDS,
                           fields_json=json.dumps(FIELDS),
                           school_json=json.dumps(_school_info()))


@bp.route("/generate", methods=["POST"])
@login_required
def generate():
    fields = _json_body()
    lang = fields.get("lang") or session.get("lang", "en")
    data = _ai_minit(fields, lang)
    source = "ai" if data else "offline"
    if not data:
        data = {"isu": _split_lines(fields.get("isu")), "tindakan": _split_lines(fields.get("tindakan")),
                "bahan": _split_lines(fields.get("bahan"))}
    rph = _normalise(data, fields)
    return jsonify({"minit": rph, "source": source})


@bp.route("/export", methods=["POST"])
@login_required
def export():
    payload = _json_body()
    data = _normalise(payload.get("minit") or {}, payload.get("minit") or {})
    fmt = payload.get("format") or "pdf"
    uid = session["user_id"]
    stem = "Minit_Curai_%s" % datetime.now().strftime("%Y%m%d_%H%M%S")
    if fmt == "pdf":
        out = _UPLOAD / (uuid4().hex + ".pdf")
        build_minit_pdf(data, out)
        body = out.read_bytes(); out.unlink(missing_ok=True)
        return Response(body, mimetype="application/pdf",
                        headers={"Content-Disposition": f"attachment; filename={stem}.pdf"})
    if fmt == "docx":
        out = _UPLOAD / (uuid4().hex + ".docx")
        build_minit_docx(data, out)
        body = out.read_bytes(); out.unlink(missing_ok=True)
        return Response(body,
                        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        headers={"Content-Disposition": f"attachment; filename={stem}.docx"})
    return jsonify({"error": "bad_format"}), 400


@bp.route("/save", methods=["POST"])
@login_required
def save():
    payload = _json_body()
    data = _normalise(payload.get("minit") or {}, payload.get("minit") or {})
    db = get_db()
    cur = db.execute(
        "INSERT INTO minit_documents (teacher_id, title, jenis, unit, minit_json) VALUES (?,?,?,?,?)",
        (session["user_id"], data.get("perkara") or "Minit Curai", data.get("jenis") or "",
         data.get("unit") or "", json.dumps(data, ensure_ascii=False)),
    )
    db.commit()
    mid = cur.lastrowid
    db.close()
    return jsonify({"ok": True, "id": mid})
