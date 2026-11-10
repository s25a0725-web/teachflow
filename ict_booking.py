# -*- coding: utf-8 -*-
"""Tool 1 — REKOD PENEMPAHAN BILIK ICT (ICT Room Booking).

Natural-language booking -> structured fields -> KPM-style PDF/DOCX.
Includes real booking-conflict detection against saved records.
"""
import json
import os
import re
from datetime import datetime
from functools import wraps
from pathlib import Path
from uuid import uuid4

from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify, Response

from db import get_db, get_setting
from i18n import t
import userstore
from docgen import ai_autofill, parse_date_day, parse_time, school_profile
from ict_booking_doc import build_ict_pdf, build_ict_docx, FIELDS

bp = Blueprint("ict_booking", __name__, url_prefix="/ict-booking")

_BASE = Path(__file__).resolve().parent
_TMP = Path(os.environ.get("TEACHFLOW_UPLOAD_ROOT", str(_BASE / "uploads"))) / "ict"
_TMP.mkdir(parents=True, exist_ok=True)

ROOMS = ["Bilik ICT 1", "Bilik ICT 2", "Bilik ICT 3", "Makmal Komputer"]


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


# ---------------------------------------------------------------------------
# AI autofill
# ---------------------------------------------------------------------------
_SYSTEM = (
    "You are a Malaysian school ICT room booking assistant. Convert the teacher's "
    "natural-language request into a structured booking. Output ONLY valid JSON, no "
    "markdown, with exactly these keys: "
    '{"teacher_name":"","booking_date":"YYYY-MM-DD","day":"HARI (ISNIN..AHAD)",'
    '"start_time":"HH:MM","end_time":"HH:MM","room":"","purpose":"","class_info":"",'
    '"duration":"","remarks":""}. '
    "Detect the date and day automatically (today is %s). Convert times to 24h HH:MM. "
    "If a day name is given but no date, use the next occurrence of that day. "
    "The purpose is usually AKADEMIK, KOKURIKULUM or PENTADBIRAN unless stated. "
    "Never invent a teacher name, date, room or time that is not in the request."
)


def _fallback(text):
    """Deterministic field extraction when no API key is configured."""
    iso, day = parse_date_day(text)
    start, end = parse_time(text)
    room = ""
    for r in ROOMS:
        if r.lower().replace("bilik ", "").replace(" ", "") in (text or "").lower().replace(" ", ""):
            room = r
            break
    purpose = ""
    for k in ("AKADEMIK", "KOKURIKULUM", "PENTADBIRAN", "MESYUARAT"):
        if k in (text or "").upper():
            purpose = k.capitalize()
            break
    return {
        "teacher_name": "",
        "booking_date": iso or "",
        "day": day,
        "start_time": start,
        "end_time": end,
        "room": room,
        "purpose": purpose,
        "class_info": "",
        "duration": "",
        "remarks": (text or "").strip(),
    }


def _to_min(t):
    if not t:
        return None
    m = re.match(r"(\d{1,2}):(\d{2})", str(t))
    if not m:
        return None
    return int(m.group(1)) * 60 + int(m.group(2))


def _conflicts(date, start, room, exclude_id=None):
    """Return saved bookings on the same date+room overlapping the requested slot."""
    db = get_db()
    rows = db.execute(
        "SELECT id, teacher_name, start_time, end_time, room FROM ict_bookings "
        "WHERE booking_date = ? AND room = ? AND status != 'cancelled'",
        (date, room),
    ).fetchall()
    db.close()
    s = _to_min(start)
    out = []
    for r in rows:
        if exclude_id and r["id"] == exclude_id:
            continue
        rs = _to_min(r["start_time"])
        re_ = _to_min(r["end_time"])
        if rs is None:
            continue
        # conflict if requested start equals an existing start, or overlaps [rs,re_)
        if s is not None and s == rs:
            out.append(dict(r))
            continue
        if s is not None and re_ is not None and rs <= s < re_:
            out.append(dict(r))
    return out


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------
@bp.route("/")
@login_required
def index():
    db = get_db()
    recent = db.execute(
        "SELECT id, teacher_name, booking_date, day, start_time, room, purpose, created_at "
        "FROM ict_bookings WHERE teacher_id = ? ORDER BY id DESC LIMIT 20",
        (session["user_id"],),
    ).fetchall()
    db.close()
    return render_template("ict_booking.html", rooms=ROOMS,
                           teacher_name=_teacher_name(), school=school_profile(),
                           recent=[dict(r) for r in recent])


@bp.route("/autofill", methods=["POST"])
@login_required
def autofill():
    payload = _json_body()
    text = payload.get("instruction") or ""
    fields = ["teacher_name", "booking_date", "day", "start_time", "end_time",
              "room", "purpose", "class_info", "duration", "remarks"]
    sys_prompt = _SYSTEM % datetime.now().strftime("%Y-%m-%d (%A)")
    data = ai_autofill(sys_prompt, text, fields, _fallback)
    data["teacher_name"] = data.get("teacher_name") or _teacher_name()
    # ensure date/day consistency
    if not data.get("day") and data.get("booking_date"):
        _, d = parse_date_day(data["booking_date"])
        data["day"] = d
    # conflict check
    conflicts = []
    if data.get("booking_date") and data.get("room"):
        conflicts = _conflicts(data["booking_date"], data.get("start_time"), data.get("room"))
    return jsonify({"data": data, "conflicts": conflicts})


@bp.route("/save", methods=["POST"])
@login_required
def save():
    payload = _json_body()
    d = payload.get("data") or {}
    db = get_db()
    cur = db.execute(
        "INSERT INTO ict_bookings (teacher_id, teacher_name, booking_date, day, start_time, "
        "end_time, room, purpose, class_info, duration, remarks, status, doc_json) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (session["user_id"], d.get("teacher_name") or _teacher_name(), d.get("booking_date") or "",
         d.get("day") or "", d.get("start_time") or "", d.get("end_time") or "",
         d.get("room") or "", d.get("purpose") or "", d.get("class_info") or "",
         d.get("duration") or "", d.get("remarks") or "", "confirmed", json.dumps(d, ensure_ascii=False)),
    )
    db.commit()
    bid = cur.lastrowid
    db.close()
    return jsonify({"ok": True, "id": bid})


@bp.route("/export", methods=["POST"])
@login_required
def export():
    payload = _json_body()
    d = payload.get("data") or {}
    d.setdefault("teacher_name", _teacher_name())
    d.setdefault("school_name", school_profile()["school_name"])
    fmt = payload.get("format") or "pdf"
    stem = "Rekod_Penempahan_Bilik_ICT_%s" % datetime.now().strftime("%Y%m%d_%H%M%S")
    if fmt == "pdf":
        out = _TMP / (uuid4().hex + ".pdf")
        build_ict_pdf(d, out)
        body = out.read_bytes(); out.unlink(missing_ok=True)
        return Response(body, mimetype="application/pdf",
                        headers={"Content-Disposition": f"attachment; filename={stem}.pdf"})
    if fmt == "docx":
        out = _TMP / (uuid4().hex + ".docx")
        build_ict_docx(d, out)
        body = out.read_bytes(); out.unlink(missing_ok=True)
        return Response(body,
                        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        headers={"Content-Disposition": f"attachment; filename={stem}.docx"})
    return jsonify({"error": "bad_format"}), 400
