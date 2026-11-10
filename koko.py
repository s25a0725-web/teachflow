# -*- coding: utf-8 -*-
"""Tool 2 — LAPORAN BERGAMBAR UNIT KOKURIKULUM (co-curricular report)."""
import json
import os
from datetime import datetime
from functools import wraps
from pathlib import Path
from uuid import uuid4

from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify, Response, send_from_directory
from werkzeug.utils import secure_filename

from db import get_db, get_setting
from i18n import t
import userstore
from docgen import ai_autofill, parse_date_day, school_profile
from koko_doc import build_koko_pdf, build_koko_docx, FIELDS
from esig import resolve_signatures

bp = Blueprint("koko", __name__, url_prefix="/kokurikulum")

_BASE = Path(__file__).resolve().parent
_UPLOAD = Path(os.environ.get("TEACHFLOW_UPLOAD_ROOT", str(_BASE / "uploads"))) / "koko"
_UPLOAD.mkdir(parents=True, exist_ok=True)

ALLOWED_IMG = (".png", ".jpg", ".jpeg", ".webp")


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return wrapper


def _json_body():
    return request.get_json(silent=True) or {}


def _teacher_name():
    u = userstore.get_by_id(session["user_id"])
    return (u or {}).get("name") or session.get("name") or ""


_SYSTEM = (
    "You are a Malaysian school co-curricular coordinator writing a LAPORAN BERGAMBAR "
    "UNIT KOKURIKULUM in formal Bahasa Melayu. Convert the teacher's notes into a "
    "structured report. Output ONLY valid JSON (no markdown) with exactly these keys: "
    '{"program":"","tempat":"","tarikh":"YYYY-MM-DD","sasaran":"","objektif":["..."],'
    '"aktiviti":["..."],"penilaian":["..."],"analisis":["..."],"keberhasilan":["..."],'
    '"cadangan":["..."]}. '
    "All list fields are arrays of complete, correctly worded Bahasa Melayu sentences. "
    "objektif: 2-4 programme objectives. aktiviti: what was conducted. "
    "penilaian: assessment of the activity. analisis: analysis. "
    "keberhasilan: programme outcomes/success. cadangan: improvement suggestions. "
    "Never invent participant numbers, outcomes or activities not implied by the input. "
    "Fix grammar and spelling, use accurate terminology. Today is %s."
)


def _fallback(text):
    iso, day = parse_date_day(text)
    return {
        "program": "", "tempat": "", "tarikh": iso or "", "sasaran": "",
        "objektif": [], "aktiviti": [], "penilaian": [], "analisis": [],
        "keberhasilan": [], "cadangan": [],
        "_notes": (text or "").strip(),
    }


def _normalise(data, fields):
    out = dict(fields)
    for k in ("program", "tempat", "tarikh", "sasaran", "disediakan_nama", "disediakan_jawatan",
              "disahkan_nama", "disahkan_jawatan"):
        out[k] = data.get(k) or ""
    for k in ("objektif", "aktiviti", "penilaian", "analisis", "keberhasilan", "cadangan"):
        v = data.get(k)
        out[k] = v if isinstance(v, list) else ([x.strip() for x in str(v or "").split("\n") if x.strip()])
    out["photos"] = data.get("photos") or []
    out["signatures"] = data.get("signatures") or {}
    return out


@bp.route("/")
@login_required
def index():
    db = get_db()
    recent = db.execute(
        "SELECT id, title, programme, created_at FROM kokurikulum_docs WHERE teacher_id = ? ORDER BY id DESC LIMIT 20",
        (session["user_id"],),
    ).fetchall()
    db.close()
    return render_template("koko.html", school=school_profile(),
                           recent=[dict(r) for r in recent])


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
    return jsonify({"name": name, "url": url_for("koko.photo", name=name)})


@bp.route("/photo/<name>")
@login_required
def photo(name):
    name = secure_filename(name)
    return send_from_directory(str(_UPLOAD), name)


@bp.route("/autofill", methods=["POST"])
@login_required
def autofill():
    payload = _json_body()
    text = payload.get("instruction") or ""
    fields = ["program", "tempat", "tarikh", "sasaran", "objektif", "aktiviti",
              "penilaian", "analisis", "keberhasilan", "cadangan"]
    sys_prompt = _SYSTEM % datetime.now().strftime("%Y-%m-%d (%A)")
    data = ai_autofill(sys_prompt, text, fields, _fallback)
    return jsonify({"data": data})


@bp.route("/save", methods=["POST"])
@login_required
def save():
    payload = _json_body()
    d = _normalise(payload.get("data") or {}, {})
    db = get_db()
    cur = db.execute(
        "INSERT INTO kokurikulum_docs (teacher_id, title, programme, doc_json) VALUES (?,?,?,?)",
        (session["user_id"], d.get("program") or "Laporan Kokurikulum", d.get("program") or "",
         json.dumps(d, ensure_ascii=False)),
    )
    db.commit()
    kid = cur.lastrowid
    db.close()
    return jsonify({"ok": True, "id": kid})


@bp.route("/export", methods=["POST"])
@login_required
def export():
    payload = _json_body()
    d = _normalise(payload.get("data") or {}, {})
    d.setdefault("disediakan_nama", _teacher_name())
    resolve_signatures(d)
    fmt = payload.get("format") or "pdf"
    stem = "Laporan_Kokurikulum_%s" % datetime.now().strftime("%Y%m%d_%H%M%S")
    if fmt == "pdf":
        out = _UPLOAD / (uuid4().hex + ".pdf")
        build_koko_pdf(d, out)
        body = out.read_bytes(); out.unlink(missing_ok=True)
        return Response(body, mimetype="application/pdf",
                        headers={"Content-Disposition": f"attachment; filename={stem}.pdf"})
    if fmt == "docx":
        out = _UPLOAD / (uuid4().hex + ".docx")
        build_koko_docx(d, out)
        body = out.read_bytes(); out.unlink(missing_ok=True)
        return Response(body,
                        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        headers={"Content-Disposition": f"attachment; filename={stem}.docx"})
    return jsonify({"error": "bad_format"}), 400
