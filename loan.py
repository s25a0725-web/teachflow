# -*- coding: utf-8 -*-
"""Tool 5 — REKOD PINJAMAN PERKAKASAN ICT (ICT Equipment Loan) + inventory."""
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
from loan_doc import build_loan_pdf, build_loan_docx, FIELDS

bp = Blueprint("loan", __name__, url_prefix="/ict-loan")

_BASE = Path(__file__).resolve().parent
_TMP = Path(os.environ.get("TEACHFLOW_UPLOAD_ROOT", str(_BASE / "uploads"))) / "loan"
_TMP.mkdir(parents=True, exist_ok=True)

CATEGORIES = ["Laptop", "Desktop", "Projektor", "Pencetak", "Tablet", "Papan Kekunci", "Tetikus", "Lain-lain"]


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not userstore.is_admin_role(session.get("user_id")):
            return jsonify({"error": "forbidden"}), 403
        return f(*args, **kwargs)
    return wrapper


def _json_body():
    return request.get_json(silent=True) or {}


def _teacher_name():
    u = userstore.get_by_id(session["user_id"])
    return (u or {}).get("name") or session.get("name") or ""


_SYSTEM = (
    "You are a Malaysian school ICT equipment loan clerk. Convert the teacher's "
    "request into a structured loan record. Output ONLY valid JSON (no markdown) "
    "with exactly these keys: "
    '{"teacher_name":"","equipment_name":"","category":"","serial_no":"","quantity":1,'
    '"borrow_date":"YYYY-MM-DD","borrow_time":"HH:MM","purpose":"","expected_return":"YYYY-MM-DD",'
    '"actual_return":"","condition_out":"","condition_in":"","status":"Dipinjam",'
    '"witness":"","approver":"","remarks":""}. '
    "Retrieve equipment name/category from the provided inventory list if a match exists. "
    "Never invent a serial number or return status. Today is %s."
)


def _fallback(text):
    iso, day = parse_date_day(text)
    from docgen import parse_time
    s, _ = parse_time(text)
    return {
        "teacher_name": "", "equipment_name": "", "category": "", "serial_no": "",
        "quantity": 1, "borrow_date": iso or "", "borrow_time": s, "purpose": "",
        "expected_return": "", "actual_return": "", "condition_out": "Baik",
        "condition_in": "", "status": "Dipinjam", "witness": "", "approver": "",
        "remarks": (text or "").strip(),
    }


def _inventory():
    db = get_db()
    rows = db.execute("SELECT id, name, category, serial_no, quantity, condition FROM ict_inventory ORDER BY name").fetchall()
    db.close()
    return [dict(r) for r in rows]


def _normalise(data, fields):
    out = {k: "" for k in fields}
    for k in fields:
        out[k] = data.get(k) if data.get(k) is not None else ""
    out["quantity"] = data.get("quantity") or 1
    return out


# ---------------------------------------------------------------------------
# Inventory (admin)
# ---------------------------------------------------------------------------
@bp.route("/inventory", methods=["GET"])
@login_required
def inventory_list():
    return jsonify({"items": _inventory()})


@bp.route("/inventory", methods=["POST"])
@login_required
@admin_required
def inventory_add():
    d = _json_body()
    if not d.get("name"):
        return jsonify({"error": "name_required"}), 400
    db = get_db()
    cur = db.execute(
        "INSERT INTO ict_inventory (name, category, serial_no, quantity, condition) VALUES (?,?,?,?,?)",
        (d.get("name"), d.get("category") or "", d.get("serial_no") or "",
         d.get("quantity") or 1, d.get("condition") or "Baik"),
    )
    db.commit()
    iid = cur.lastrowid
    db.close()
    return jsonify({"ok": True, "id": iid})


@bp.route("/inventory/<int:iid>", methods=["DELETE"])
@login_required
@admin_required
def inventory_delete(iid):
    db = get_db()
    db.execute("DELETE FROM ict_inventory WHERE id = ?", (iid,))
    db.commit()
    db.close()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Loan pages
# ---------------------------------------------------------------------------
@bp.route("/")
@login_required
def index():
    db = get_db()
    recent = db.execute(
        "SELECT id, teacher_name, equipment_name, serial_no, borrow_date, status FROM ict_loans "
        "WHERE teacher_id = ? ORDER BY id DESC LIMIT 20",
        (session["user_id"],),
    ).fetchall()
    db.close()
    return render_template("loan.html", school=school_profile(), categories=CATEGORIES,
                           inventory=_inventory(), recent=[dict(r) for r in recent])


@bp.route("/autofill", methods=["POST"])
@login_required
def autofill():
    payload = _json_body()
    text = payload.get("instruction") or ""
    fields = ["teacher_name", "equipment_name", "category", "serial_no", "quantity",
              "borrow_date", "borrow_time", "purpose", "expected_return", "actual_return",
              "condition_out", "condition_in", "status", "witness", "approver", "remarks"]
    sys_prompt = _SYSTEM % datetime.now().strftime("%Y-%m-%d (%A)")
    # augment with inventory for AI to match equipment
    inv = _inventory()
    if inv:
        sys_prompt += " Inventory: " + json.dumps([{"name": i["name"], "category": i["category"], "serial_no": i["serial_no"]} for i in inv], ensure_ascii=False)
    data = ai_autofill(sys_prompt, text, fields, _fallback)
    data["teacher_name"] = data.get("teacher_name") or _teacher_name()
    # match inventory serial automatically if equipment name matches
    if not data.get("serial_no"):
        for i in inv:
            if i["name"].lower() in (data.get("equipment_name") or "").lower():
                data["serial_no"] = i["serial_no"] or ""
                data["category"] = data["category"] or i["category"] or ""
                break
    return jsonify({"data": data})


@bp.route("/save", methods=["POST"])
@login_required
def save():
    payload = _json_body()
    d = _normalise(payload.get("data") or {}, ["teacher_name", "equipment_name", "category", "serial_no",
                    "quantity", "borrow_date", "borrow_time", "purpose", "expected_return",
                    "actual_return", "condition_out", "condition_in", "status", "witness",
                    "approver", "remarks"])
    db = get_db()
    cur = db.execute(
        "INSERT INTO ict_loans (teacher_id, teacher_name, equipment_name, category, serial_no, "
        "quantity, borrow_date, borrow_time, purpose, expected_return, actual_return, condition_out, "
        "condition_in, status, witness, approver, remarks, doc_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (session["user_id"], d.get("teacher_name") or _teacher_name(), d.get("equipment_name") or "",
         d.get("category") or "", d.get("serial_no") or "", d.get("quantity") or 1,
         d.get("borrow_date") or "", d.get("borrow_time") or "", d.get("purpose") or "",
         d.get("expected_return") or "", d.get("actual_return") or "", d.get("condition_out") or "",
         d.get("condition_in") or "", d.get("status") or "Dipinjam", d.get("witness") or "",
         d.get("approver") or "", d.get("remarks") or "", json.dumps(d, ensure_ascii=False)),
    )
    db.commit()
    lid = cur.lastrowid
    db.close()
    return jsonify({"ok": True, "id": lid})


@bp.route("/export", methods=["POST"])
@login_required
def export():
    payload = _json_body()
    d = _normalise(payload.get("data") or {}, ["teacher_name", "equipment_name", "category", "serial_no",
                    "quantity", "borrow_date", "borrow_time", "purpose", "expected_return",
                    "actual_return", "condition_out", "condition_in", "status", "witness",
                    "approver", "remarks"])
    d.setdefault("teacher_name", _teacher_name())
    fmt = payload.get("format") or "pdf"
    stem = "Rekod_Pinjaman_Perkakasan_ICT_%s" % datetime.now().strftime("%Y%m%d_%H%M%S")
    if fmt == "pdf":
        out = _TMP / (uuid4().hex + ".pdf")
        build_loan_pdf(d, out)
        body = out.read_bytes(); out.unlink(missing_ok=True)
        return Response(body, mimetype="application/pdf",
                        headers={"Content-Disposition": f"attachment; filename={stem}.pdf"})
    if fmt == "docx":
        out = _TMP / (uuid4().hex + ".docx")
        build_loan_docx(d, out)
        body = out.read_bytes(); out.unlink(missing_ok=True)
        return Response(body,
                        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        headers={"Content-Disposition": f"attachment; filename={stem}.docx"})
    return jsonify({"error": "bad_format"}), 400
