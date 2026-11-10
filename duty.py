# -*- coding: utf-8 -*-
"""Tool 3 — LAPORAN HARIAN GURU BERTUGAS (Daily Teacher Duty Report)."""
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
from duty_doc import build_duty_pdf, build_duty_docx, FIELDS
from esig import resolve_signatures

bp = Blueprint("duty", __name__, url_prefix="/duty-report")

_BASE = Path(__file__).resolve().parent
_TMP = Path(os.environ.get("TEACHFLOW_UPLOAD_ROOT", str(_BASE / "uploads"))) / "duty"
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
    "You are a Malaysian school duty teacher writing a LAPORAN HARIAN GURU BERTUGAS "
    "in formal Bahasa Melayu. Convert the teacher's raw daily observations into the "
    "correct report sections. Output ONLY valid JSON (no markdown) with exactly these keys: "
    '{"week":"","date":"YYYY-MM-DD","day":"HARI","teacher_duty_1":"","teacher_duty_2":"",'
    '"teachers_absent":"","special_activities":"","visitors":"",'
    '"facilities":{"Bilik-bilik Khas":"","Makmal":"","Bengkel":"","Padang":"","Tandas Guru":"",'
    '"Tandas Murid":"","Kantin":"","Pra Sekolah":"","Pejabat":"","Bilik ICT":""},'
    '"remarks":"","disemak_nama":"","disahkan_nama":""}. '
    "Each facility value is a condition, default 'BAIK' when reported good or empty. "
    "Write empty string for missing info. Never invent absent names or incidents. "
    "Use accurate terminology, fix grammar and spelling. Today is %s."
)


def _fallback(text):
    iso, day = parse_date_day(text)
    return {
        "week": "", "date": iso or "", "day": day, "teacher_duty_1": "",
        "teacher_duty_2": "", "teachers_absent": "", "special_activities": "",
        "visitors": "", "facilities": {}, "remarks": (text or "").strip(),
        "disemak_nama": "", "disahkan_nama": "",
    }


def _normalise(data, fields):
    out = {k: "" for k in fields}
    for k in fields:
        out[k] = data.get(k) or ""
    # facilities is a dict
    fac = data.get("facilities")
    out["facilities"] = fac if isinstance(fac, dict) else {}
    # signature passthrough
    out["signatures"] = data.get("signatures") or {}
    return out


@bp.route("/")
@login_required
def index():
    db = get_db()
    recent = db.execute(
        "SELECT id, title, duty_date, created_at FROM duty_docs WHERE teacher_id = ? ORDER BY id DESC LIMIT 20",
        (session["user_id"],),
    ).fetchall()
    db.close()
    return render_template("duty.html", school=school_profile(),
                           recent=[dict(r) for r in recent])


@bp.route("/autofill", methods=["POST"])
@login_required
def autofill():
    payload = _json_body()
    text = payload.get("instruction") or ""
    fields = [k for k, _ in FIELDS]
    sys_prompt = _SYSTEM % datetime.now().strftime("%Y-%m-%d (%A)")
    data = ai_autofill(sys_prompt, text, fields, _fallback)
    data["teacher_duty_1"] = data.get("teacher_duty_1") or _teacher_name()
    return jsonify({"data": data})


@bp.route("/save", methods=["POST"])
@login_required
def save():
    payload = _json_body()
    d = _normalise(payload.get("data") or {}, [k for k, _ in FIELDS])
    db = get_db()
    cur = db.execute(
        "INSERT INTO duty_docs (teacher_id, title, duty_date, doc_json) VALUES (?,?,?,?)",
        (session["user_id"], d.get("date") or "Laporan Bertugas", d.get("date") or "",
         json.dumps(d, ensure_ascii=False)),
    )
    db.commit()
    did = cur.lastrowid
    db.close()
    return jsonify({"ok": True, "id": did})


@bp.route("/export", methods=["POST"])
@login_required
def export():
    payload = _json_body()
    d = _normalise(payload.get("data") or {}, [k for k, _ in FIELDS])
    d.setdefault("teacher_duty_1", _teacher_name())
    resolve_signatures(d)
    fmt = payload.get("format") or "pdf"
    stem = "Laporan_Harian_Guru_Bertugas_%s" % datetime.now().strftime("%Y%m%d_%H%M%S")
    if fmt == "pdf":
        out = _TMP / (uuid4().hex + ".pdf")
        build_duty_pdf(d, out)
        body = out.read_bytes(); out.unlink(missing_ok=True)
        return Response(body, mimetype="application/pdf",
                        headers={"Content-Disposition": f"attachment; filename={stem}.pdf"})
    if fmt == "docx":
        out = _TMP / (uuid4().hex + ".docx")
        build_duty_docx(d, out)
        body = out.read_bytes(); out.unlink(missing_ok=True)
        return Response(body,
                        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        headers={"Content-Disposition": f"attachment; filename={stem}.docx"})
    return jsonify({"error": "bad_format"}), 400
