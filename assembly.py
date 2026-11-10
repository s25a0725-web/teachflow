# -*- coding: utf-8 -*-
"""Tool 4 — LAPORAN PERHIMPUNAN (School Assembly Report)."""
import json
import os
from datetime import datetime
from functools import wraps
from pathlib import Path
from uuid import uuid4

from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify, Response

from db import get_db, get_setting
from i18n import t
import userstore
from docgen import ai_autofill, parse_date_day, school_profile
from assembly_doc import build_assembly_pdf, build_assembly_docx, FIELDS

bp = Blueprint("assembly", __name__, url_prefix="/assembly-report")

_BASE = Path(__file__).resolve().parent
_TMP = Path(os.environ.get("TEACHFLOW_UPLOAD_ROOT", str(_BASE / "uploads"))) / "assembly"
_TMP.mkdir(parents=True, exist_ok=True)


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
    "You are a Malaysian school teacher writing a LAPORAN PERHIMPUNAN (assembly report) "
    "in formal Bahasa Melayu. Convert the teacher's notes into the correct sections. "
    "Output ONLY valid JSON (no markdown) with exactly these keys: "
    '{"week":"","date":"YYYY-MM-DD","day":"HARI","venue":"","teacher_duty":"","agenda":"",'
    '"negaraku":"","state_anthem":"","rukun_negara":"","headteacher_speech":"",'
    '"teacher_announcements":"","student_announcements":"","performances":"",'
    '"special_activities":"","messages":"","remarks":"","conclusion":""}. '
    "Use accurate terminology. Write empty string for missing info. "
    "Never invent a speech, announcement, performance or message not implied by the input. "
    "Fix grammar and spelling. Today is %s."
)


def _fallback(text):
    iso, day = parse_date_day(text)
    return {
        "week": "", "date": iso or "", "day": day, "venue": "", "teacher_duty": "",
        "agenda": "", "negaraku": "", "state_anthem": "", "rukun_negara": "",
        "headteacher_speech": "", "teacher_announcements": "", "student_announcements": "",
        "performances": "", "special_activities": "", "messages": "",
        "remarks": (text or "").strip(), "conclusion": "",
    }


def _normalise(data, fields):
    out = {k: "" for k in fields}
    for k in fields:
        out[k] = data.get(k) or ""
    return out


@bp.route("/")
@login_required
def index():
    db = get_db()
    recent = db.execute(
        "SELECT id, title, week, created_at FROM assembly_docs WHERE teacher_id = ? ORDER BY id DESC LIMIT 20",
        (session["user_id"],),
    ).fetchall()
    db.close()
    return render_template("assembly.html", school=school_profile(),
                           recent=[dict(r) for r in recent])


@bp.route("/autofill", methods=["POST"])
@login_required
def autofill():
    payload = _json_body()
    text = payload.get("instruction") or ""
    fields = [k for k, _ in FIELDS]
    sys_prompt = _SYSTEM % datetime.now().strftime("%Y-%m-%d (%A)")
    data = ai_autofill(sys_prompt, text, fields, _fallback)
    data["teacher_duty"] = data.get("teacher_duty") or _teacher_name()
    return jsonify({"data": data})


@bp.route("/save", methods=["POST"])
@login_required
def save():
    payload = _json_body()
    d = _normalise(payload.get("data") or {}, [k for k, _ in FIELDS])
    db = get_db()
    cur = db.execute(
        "INSERT INTO assembly_docs (teacher_id, title, week, doc_json) VALUES (?,?,?,?)",
        (session["user_id"], d.get("date") or "Laporan Perhimpunan", d.get("week") or "",
         json.dumps(d, ensure_ascii=False)),
    )
    db.commit()
    aid = cur.lastrowid
    db.close()
    return jsonify({"ok": True, "id": aid})


@bp.route("/export", methods=["POST"])
@login_required
def export():
    payload = _json_body()
    d = _normalise(payload.get("data") or {}, [k for k, _ in FIELDS])
    d.setdefault("teacher_duty", _teacher_name())
    fmt = payload.get("format") or "pdf"
    stem = "Laporan_Perhimpunan_%s" % datetime.now().strftime("%Y%m%d_%H%M%S")
    if fmt == "pdf":
        out = _TMP / (uuid4().hex + ".pdf")
        build_assembly_pdf(d, out)
        body = out.read_bytes(); out.unlink(missing_ok=True)
        return Response(body, mimetype="application/pdf",
                        headers={"Content-Disposition": f"attachment; filename={stem}.pdf"})
    if fmt == "docx":
        out = _TMP / (uuid4().hex + ".docx")
        build_assembly_docx(d, out)
        body = out.read_bytes(); out.unlink(missing_ok=True)
        return Response(body,
                        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        headers={"Content-Disposition": f"attachment; filename={stem}.docx"})
    return jsonify({"error": "bad_format"}), 400
