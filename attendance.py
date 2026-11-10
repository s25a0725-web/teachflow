# -*- coding: utf-8 -*-
"""Smart Attendance: GPS check-in/out, late/absent detection, MC, leave,
admin + teacher dashboards, reports, audit logs and notifications."""
import math
import os
from datetime import date, datetime, timedelta
from functools import wraps
from pathlib import Path
from uuid import uuid4

from flask import (Blueprint, render_template, request, session, redirect, url_for,
                   flash, send_from_directory, abort, jsonify)
from werkzeug.utils import secure_filename

from db import get_db, get_setting, set_setting
import userstore
from views import login_required

bp = Blueprint("attendance", __name__, url_prefix="/attendance")

BASE = Path(__file__).resolve().parent
UPLOAD_ROOT = Path(os.environ.get("TEACHFLOW_UPLOAD_ROOT", str(BASE / "uploads")))
MC_DIR = UPLOAD_ROOT / "mc"
REPORT_DIR = UPLOAD_ROOT / "reports"
MC_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)

MC_ALLOWED = {".pdf", ".jpg", ".jpeg", ".png"}
MC_MAX_BYTES = 10 * 1024 * 1024  # 10 MB

LEAVE_TYPES = ["annual", "medical", "emergency", "unpaid", "other"]
LEAVE_DEFAULTS = {"annual": 14.0, "medical": 14.0, "emergency": 5.0, "unpaid": 0.0, "other": 0.0}


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _now():
    return datetime.now()


def _today():
    return date.today().isoformat()


def _name(uid):
    u = userstore.get_by_id(uid)
    return (u.get("name") or u.get("email") or f"User {uid}") if u else f"User {uid}"


def _is_admin():
    return userstore.is_admin_role(session.get("role"))


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not _is_admin():
            flash("forbidden", "error")
            return redirect(url_for("attendance.index"))
        return f(*args, **kwargs)
    return wrapper


def _audit(uid, action, details=""):
    db = get_db()
    db.execute("INSERT INTO audit_logs (user_id, action, details, ip) VALUES (?,?,?,?)",
               (uid, action, details, request.remote_addr or ""))
    db.commit()
    db.close()


def _notify(user_id, message, kind="attendance"):
    db = get_db()
    db.execute("INSERT INTO notifications (user_id, message, kind) VALUES (?,?,?)", (user_id, message, kind))
    db.commit()
    db.close()


def _notify_admins(message, kind="attendance"):
    for u in userstore.all_users():
        if u.get("role") == "admin":
            _notify(u["id"], message, kind)


def _haversine(lat1, lon1, lat2, lon2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlam / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _school_location():
    lat = get_setting("school_latitude")
    lon = get_setting("school_longitude")
    if lat in (None, "") or lon in (None, ""):
        return None
    try:
        return {"latitude": float(lat), "longitude": float(lon),
                "radius_m": int(get_setting("school_radius") or 100)}
    except (ValueError, TypeError):
        return None


def _time_minutes(t):
    if not t:
        return None
    try:
        h, m = str(t).split(":")
        return int(h) * 60 + int(m)
    except (ValueError, AttributeError):
        return None


def _start_time():
    return get_setting("school_start") or "07:30"


def _end_time():
    return get_setting("school_end") or "13:30"


def _grace_minutes():
    try:
        return int(get_setting("grace_minutes") or 5)
    except ValueError:
        return 5


def _max_accuracy():
    try:
        return int(get_setting("max_accuracy_m") or 50)
    except ValueError:
        return 50


def _validate_location(lat, lon, acc):
    """Return (distance_m, error). error is None when the location is valid."""
    loc = _school_location()
    if loc is None:
        return None, "no_location"
    if not (-90 <= lat <= 90 and -180 <= lon <= 180) or (lat == 0 and lon == 0):
        return None, "invalid_coords"
    if acc is not None and acc > _max_accuracy():
        return None, "low_accuracy"
    dist = _haversine(loc["latitude"], loc["longitude"], lat, lon)
    if dist > loc["radius_m"]:
        return None, "outside_geofence"
    return dist, None


def _leave_balances(uid):
    db = get_db()
    rows = db.execute("SELECT * FROM leave_balances WHERE teacher_id=?", (uid,)).fetchall()
    db.close()
    bal = {lt: {"total": LEAVE_DEFAULTS.get(lt, 0.0), "used": 0.0} for lt in LEAVE_TYPES}
    for r in rows:
        if r["leave_type"] in bal:
            bal[r["leave_type"]]["total"] = r["total_days"]
            bal[r["leave_type"]]["used"] = r["used_days"]
    return bal


# --------------------------------------------------------------------------
# Settings (admin)
# --------------------------------------------------------------------------
@bp.route("/settings", methods=["GET", "POST"])
@login_required
@admin_required
def settings():
    if request.method == "POST":
        set_setting("location_name", request.form.get("location_name", "").strip())
        lat = request.form.get("latitude", "").strip()
        lon = request.form.get("longitude", "").strip()
        if lat and lon:
            set_setting("school_latitude", lat)
            set_setting("school_longitude", lon)
        set_setting("school_radius", request.form.get("radius", "100").strip() or "100")
        set_setting("school_start", request.form.get("start_time", "07:30").strip() or "07:30")
        set_setting("grace_minutes", request.form.get("grace_minutes", "5").strip() or "5")
        set_setting("school_end", request.form.get("end_time", "13:30").strip() or "13:30")
        set_setting("absent_deadline", request.form.get("absent_deadline", "09:00").strip() or "09:00")
        set_setting("max_accuracy_m", request.form.get("max_accuracy_m", "50").strip() or "50")
        _audit(session["user_id"], "attendance_settings_updated")
        flash("settings_saved", "success")
        return redirect(url_for("attendance.settings"))
    loc = _school_location()
    return render_template(
        "attendance_settings.html",
        location_name=get_setting("location_name") or "",
        latitude=loc["latitude"] if loc else "",
        longitude=loc["longitude"] if loc else "",
        radius=loc["radius_m"] if loc else 100,
        start_time=_start_time(), grace_minutes=_grace_minutes(),
        end_time=_end_time(), absent_deadline=get_setting("absent_deadline") or "09:00",
        max_accuracy=_max_accuracy(), has_location=loc is not None,
    )


# --------------------------------------------------------------------------
# GPS check-in / check-out (foreground, server-authoritative timestamps)
# --------------------------------------------------------------------------
def _record_event(event_type):
    uid = session["user_id"]
    data = request.get_json(silent=True) or {}
    try:
        lat = float(data.get("latitude"))
        lon = float(data.get("longitude"))
    except (TypeError, ValueError):
        return jsonify({"error": "bad_coords"}), 400
    acc = data.get("accuracy")
    try:
        acc = float(acc) if acc is not None else None
    except (TypeError, ValueError):
        acc = None

    dist, err = _validate_location(lat, lon, acc)
    if err:
        return jsonify({"error": err, "distance_m": round(dist, 1) if dist is not None else None,
                        "accuracy_req": _max_accuracy()}), 400

    now = _now()
    today = now.strftime("%Y-%m-%d")
    tstr = now.strftime("%H:%M:%S")

    db = get_db()
    dup = db.execute("SELECT id FROM gps_events WHERE teacher_id=? AND event_type=? AND event_date=?",
                     (uid, event_type, today)).fetchone()
    if dup:
        db.close()
        return jsonify({"error": "duplicate"}), 409

    db.execute(
        "INSERT INTO gps_events (teacher_id, event_type, event_date, latitude, longitude, accuracy_m, verification, created_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (uid, event_type, today, lat, lon, acc, "verified", now.strftime("%Y-%m-%d %H:%M:%S")))

    row = db.execute("SELECT id FROM teacher_attendance WHERE teacher_id=? AND date=?", (uid, today)).fetchone()
    late_minutes = None
    early_minutes = None

    if event_type == "check_in":
        status = "present"
        st, grace = _time_minutes(_start_time()), _grace_minutes()
        cur = _time_minutes(now.strftime("%H:%M"))
        if st is not None and cur is not None:
            late_by = cur - (st + grace)
            if late_by > 0:
                status = "late"
                late_minutes = late_by
        if row:
            db.execute(
                "UPDATE teacher_attendance SET status=?, time=?, check_in_time=?, late_minutes=?, source='gps', "
                "latitude=?, longitude=?, accuracy_m=?, verification='verified' WHERE id=?",
                (status, tstr, tstr, late_minutes, lat, lon, acc, row["id"]))
        else:
            db.execute(
                "INSERT INTO teacher_attendance (teacher_id, date, status, time, check_in_time, late_minutes, source, latitude, longitude, accuracy_m, verification) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (uid, today, status, tstr, tstr, late_minutes, "gps", lat, lon, acc, "verified"))
    else:
        et = _time_minutes(_end_time())
        cur = _time_minutes(now.strftime("%H:%M"))
        if et is not None and cur is not None:
            early_by = et - cur
            if early_by > 0:
                early_minutes = early_by
        if row:
            db.execute("UPDATE teacher_attendance SET check_out_time=?, verification='verified' WHERE id=?", (tstr, row["id"]))
        else:
            db.execute(
                "INSERT INTO teacher_attendance (teacher_id, date, status, time, check_out_time, source, verification) "
                "VALUES (?,?,?,?,?,?,?)",
                (uid, today, "present", tstr, tstr, "gps", "verified"))
    db.commit()
    db.close()

    _audit(uid, f"gps_{event_type}", f"lat={lat},lon={lon},acc={acc},dist={round(dist,1)}m")
    if event_type == "check_in" and late_minutes:
        _notify_admins(f"{_name(uid)} checked in late by {late_minutes} minutes.", "late")
    if event_type == "check_out" and early_minutes:
        _notify_admins(f"{_name(uid)} checked out early by {early_minutes} minutes.", "early")

    return jsonify({"ok": True, "time": tstr, "date": today, "distance_m": round(dist, 1),
                    "late_minutes": late_minutes, "early_minutes": early_minutes})


@bp.route("/check-in", methods=["POST"])
@login_required
def check_in():
    return _record_event("check_in")


@bp.route("/check-out", methods=["POST"])
@login_required
def check_out():
    return _record_event("check_out")


@bp.route("/test-location", methods=["POST"])
@login_required
def test_location():
    data = request.get_json(silent=True) or {}
    try:
        lat = float(data.get("latitude"))
        lon = float(data.get("longitude"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "bad_coords"}), 400
    acc = data.get("accuracy")
    try:
        acc = float(acc) if acc is not None else None
    except (TypeError, ValueError):
        acc = None
    dist, err = _validate_location(lat, lon, acc)
    if err:
        return jsonify({"ok": False, "error": err,
                        "distance_m": round(dist, 1) if dist is not None else None,
                        "accuracy": acc, "accuracy_req": _max_accuracy()})
    return jsonify({"ok": True, "within": True, "distance_m": round(dist, 1),
                    "accuracy": acc, "accuracy_req": _max_accuracy()})


@bp.route("/status")
@login_required
def status():
    uid = session["user_id"]
    today = _today()
    db = get_db()
    row = db.execute("SELECT * FROM teacher_attendance WHERE teacher_id=? AND date=?", (uid, today)).fetchone()
    db.close()
    return jsonify({
        "today": today,
        "configured": _school_location() is not None,
        "record": dict(row) if row else None,
        "school_start": _start_time(),
        "school_end": _end_time(),
        "grace_minutes": _grace_minutes(),
    })


# --------------------------------------------------------------------------
# Dashboards
# --------------------------------------------------------------------------
@bp.route("/")
@login_required
def index():
    if _is_admin():
        return admin_dashboard()
    return teacher_dashboard()


@bp.route("/me")
@login_required
def teacher_dashboard():
    uid = session["user_id"]
    today = _today()
    db = get_db()
    record = db.execute("SELECT * FROM teacher_attendance WHERE teacher_id=? AND date=?", (uid, today)).fetchone()
    history = db.execute("SELECT * FROM teacher_attendance WHERE teacher_id=? ORDER BY date DESC LIMIT 30", (uid,)).fetchall()
    mcs = db.execute("SELECT * FROM mc_applications WHERE teacher_id=? ORDER BY id DESC", (uid,)).fetchall()
    leaves = db.execute("SELECT * FROM leave_applications WHERE teacher_id=? ORDER BY id DESC", (uid,)).fetchall()
    notes = db.execute("SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 10", (uid,)).fetchall()
    db.close()
    return render_template("attendance_me.html", record=record, history=history, mcs=mcs, leaves=leaves,
                           balances=_leave_balances(uid), notes=notes, today=today,
                           start_time=_start_time(), end_time=_end_time(),
                           leave_types=LEAVE_TYPES)


@bp.route("/admin")
@login_required
@admin_required
def admin_dashboard():
    today = _today()
    last7 = (date.today() - timedelta(days=6)).isoformat()
    db = get_db()
    recs = db.execute("SELECT * FROM teacher_attendance WHERE date=?", (today,)).fetchall()
    rec_map = {r["teacher_id"]: r for r in recs}
    approved_leaves = db.execute(
        "SELECT * FROM leave_applications WHERE status='approved' AND start_date<=? AND end_date>=?", (today, today)).fetchall()
    approved_mcs = db.execute(
        "SELECT * FROM mc_applications WHERE status='approved' AND start_date<=? AND end_date>=?", (today, today)).fetchall()
    on_leave = {l["teacher_id"] for l in approved_leaves} | {m["teacher_id"] for m in approved_mcs}
    pending_mc = db.execute("SELECT COUNT(*) c FROM mc_applications WHERE status='pending'").fetchone()["c"]
    pending_leave = db.execute("SELECT COUNT(*) c FROM leave_applications WHERE status='pending'").fetchone()["c"]
    trend_rows = db.execute(
        "SELECT date, status, COUNT(*) c FROM teacher_attendance WHERE date>=? GROUP BY date, status ORDER BY date",
        (last7,)).fetchall()
    db.close()

    users = userstore.all_users()
    present = late = absent = unverified = onleave = 0
    rows = []
    for u in users:
        name = u.get("name") or u.get("email") or f"User {u['id']}"
        if u["id"] in on_leave:
            onleave += 1
            rows.append({"id": u["id"], "name": name, "state": "leave"})
            continue
        rec = rec_map.get(u["id"])
        if rec and rec["check_in_time"]:
            if rec["status"] == "late":
                late += 1
                rows.append({"id": u["id"], "name": name, "state": "late", "late_minutes": rec["late_minutes"]})
            else:
                present += 1
                rows.append({"id": u["id"], "name": name, "state": "present"})
        elif rec and rec["verification"] == "failed":
            unverified += 1
            rows.append({"id": u["id"], "name": name, "state": "unverified"})
        else:
            absent += 1
            rows.append({"id": u["id"], "name": name, "state": "absent"})

    # Build weekly trend
    days = []
    for i in range(6, -1, -1):
        d = (date.today() - timedelta(days=i)).isoformat()
        days.append(d)
    agg = {}
    for r in trend_rows:
        agg.setdefault(r["date"], {"present": 0, "late": 0})
        if r["status"] in ("present", "late"):
            agg[r["date"]]["present"] += r["c"]
        if r["status"] == "late":
            agg[r["date"]]["late"] += r["c"]
    chart = {
        "dates": [d[5:] for d in days],
        "present": [agg.get(d, {}).get("present", 0) for d in days],
        "late": [agg.get(d, {}).get("late", 0) for d in days],
        "counts": {"present": present, "late": late, "absent": absent,
                   "leave": onleave, "unverified": unverified},
    }
    return render_template("attendance_admin.html", rows=rows, chart=chart, today=today,
                           total=len(users), pending_mc=pending_mc, pending_leave=pending_leave)


# --------------------------------------------------------------------------
# MC (medical certificate)
# --------------------------------------------------------------------------
@bp.route("/mc", methods=["GET", "POST"])
@login_required
def mc():
    uid = session["user_id"]
    if request.method == "POST":
        start_date = request.form.get("start_date", "").strip()
        end_date = request.form.get("end_date", "").strip()
        reason = request.form.get("reason", "").strip()
        if not start_date or not end_date:
            flash("gen_empty", "error")
            return redirect(url_for("attendance.mc"))
        db = get_db()
        cur = db.execute("INSERT INTO mc_applications (teacher_id, start_date, end_date, reason) VALUES (?,?,?,?)",
                         (uid, start_date, end_date, reason))
        mcid = cur.lastrowid
        db.commit()
        db.close()
        f = request.files.get("document")
        if f and f.filename:
            ext = Path(f.filename).suffix.lower()
            if ext not in MC_ALLOWED:
                flash("bad_file", "error")
                return redirect(url_for("attendance.mc"))
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(0)
            if size > MC_MAX_BYTES:
                flash("file_too_large", "error")
                return redirect(url_for("attendance.mc"))
            safe = secure_filename(f.filename) or "mc.bin"
            stored = f"{mcid}_{uuid4().hex}{ext}"
            f.save(MC_DIR / stored)
            db = get_db()
            db.execute("INSERT INTO mc_documents (mc_application_id, stored_name, original_name, mime_type) VALUES (?,?,?,?)",
                       (mcid, stored, f.filename, f.mimetype or ""))
            db.commit()
            db.close()
        _notify_admins(f"{_name(uid)} submitted an MC application ({start_date} to {end_date}).", "mc")
        _audit(uid, "mc_submit", f"id={mcid}")
        flash("doc_uploaded", "success")
        return redirect(url_for("attendance.mc"))

    db = get_db()
    if _is_admin():
        apps = db.execute("SELECT m.*, (SELECT COUNT(*) FROM mc_documents d WHERE d.mc_application_id=m.id) AS n_docs "
                          "FROM mc_applications m ORDER BY m.id DESC").fetchall()
    else:
        apps = db.execute("SELECT m.*, (SELECT COUNT(*) FROM mc_documents d WHERE d.mc_application_id=m.id) AS n_docs "
                          "FROM mc_applications m WHERE m.teacher_id=? ORDER BY m.id DESC", (uid,)).fetchall()
    db.close()
    apps = [dict(a) for a in apps]
    for a in apps:
        a["teacher_name"] = _name(a["teacher_id"])
    return render_template("attendance_mc.html", apps=apps, is_admin=_is_admin())


@bp.route("/mc/<int:mcid>/review", methods=["POST"])
@login_required
@admin_required
def mc_review(mcid):
    status = request.form.get("status")
    if status not in ("approved", "rejected", "need_info"):
        flash("gen_empty", "error")
        return redirect(url_for("attendance.mc"))
    remark = request.form.get("remark", "").strip()
    db = get_db()
    row = db.execute("SELECT * FROM mc_applications WHERE id=?", (mcid,)).fetchone()
    if row:
        db.execute("UPDATE mc_applications SET status=?, admin_remark=?, reviewed_by=?, reviewed_at=? WHERE id=?",
                   (status, remark, session["user_id"], _now().strftime("%Y-%m-%d %H:%M:%S"), mcid))
        db.commit()
        _notify(row["teacher_id"], f"Your MC application ({row['start_date']} to {row['end_date']}) was {status}.", "mc")
    db.close()
    _audit(session["user_id"], "mc_review", f"id={mcid},status={status}")
    flash("settings_saved", "success")
    return redirect(url_for("attendance.mc"))


@bp.route("/mc/<int:mcid>/file")
@login_required
def mc_file(mcid):
    db = get_db()
    row = db.execute("SELECT * FROM mc_applications WHERE id=?", (mcid,)).fetchone()
    if row is None or (row["teacher_id"] != session["user_id"] and not _is_admin()):
        db.close()
        abort(403)
    doc = db.execute("SELECT * FROM mc_documents WHERE mc_application_id=? ORDER BY id DESC LIMIT 1", (mcid,)).fetchone()
    db.close()
    if doc is None:
        abort(404)
    return send_from_directory(str(MC_DIR), doc["stored_name"], download_name=doc["original_name"])


# --------------------------------------------------------------------------
# Leave
# --------------------------------------------------------------------------
@bp.route("/leave", methods=["GET", "POST"])
@login_required
def leave():
    uid = session["user_id"]
    if request.method == "POST":
        leave_type = request.form.get("leave_type", "").strip()
        start_date = request.form.get("start_date", "").strip()
        end_date = request.form.get("end_date", "").strip()
        reason = request.form.get("reason", "").strip()
        if leave_type not in LEAVE_TYPES or not start_date or not end_date:
            flash("gen_empty", "error")
            return redirect(url_for("attendance.leave"))
        db = get_db()
        db.execute("INSERT INTO leave_applications (teacher_id, leave_type, start_date, end_date, reason) VALUES (?,?,?,?,?)",
                   (uid, leave_type, start_date, end_date, reason))
        db.commit()
        db.close()
        _notify_admins(f"{_name(uid)} applied for {leave_type} leave ({start_date} to {end_date}).", "leave")
        _audit(uid, "leave_submit", f"type={leave_type}")
        flash("doc_uploaded", "success")
        return redirect(url_for("attendance.leave"))

    db = get_db()
    if _is_admin():
        apps = db.execute("SELECT * FROM leave_applications ORDER BY id DESC").fetchall()
    else:
        apps = db.execute("SELECT * FROM leave_applications WHERE teacher_id=? ORDER BY id DESC", (uid,)).fetchall()
    db.close()
    apps = [dict(a) for a in apps]
    for a in apps:
        a["teacher_name"] = _name(a["teacher_id"])
    return render_template("attendance_leave.html", apps=apps, is_admin=_is_admin(),
                           leave_types=LEAVE_TYPES, balances=_leave_balances(uid))


@bp.route("/leave/<int:lid>/review", methods=["POST"])
@login_required
@admin_required
def leave_review(lid):
    status = request.form.get("status")
    if status not in ("approved", "rejected"):
        flash("gen_empty", "error")
        return redirect(url_for("attendance.leave"))
    remark = request.form.get("remark", "").strip()
    db = get_db()
    row = db.execute("SELECT * FROM leave_applications WHERE id=?", (lid,)).fetchone()
    if row:
        db.execute("UPDATE leave_applications SET status=?, admin_remark=?, reviewed_by=?, reviewed_at=? WHERE id=?",
                   (status, remark, session["user_id"], _now().strftime("%Y-%m-%d %H:%M:%S"), lid))
        db.commit()
        _notify(row["teacher_id"], f"Your {row['leave_type']} leave ({row['start_date']} to {row['end_date']}) was {status}.", "leave")
    db.close()
    _audit(session["user_id"], "leave_review", f"id={lid},status={status}")
    flash("settings_saved", "success")
    return redirect(url_for("attendance.leave"))


# --------------------------------------------------------------------------
# Reports & export
# --------------------------------------------------------------------------
def _report_rows(period):
    today = date.today()
    if period == "daily":
        start = today.isoformat()
    elif period == "weekly":
        start = (today - timedelta(days=6)).isoformat()
    else:
        start = (today - timedelta(days=29)).isoformat()
    db = get_db()
    rows = db.execute(
        "SELECT a.* FROM teacher_attendance a WHERE a.date>=? ORDER BY a.date DESC, a.teacher_id", (start,)).fetchall()
    db.close()
    out = []
    for r in rows:
        out.append({
            "date": r["date"], "teacher": _name(r["teacher_id"]), "status": r["status"],
            "check_in": r["check_in_time"] or "", "check_out": r["check_out_time"] or "",
            "late_minutes": r["late_minutes"], "source": r["source"] or "manual",
        })
    return out


@bp.route("/report")
@login_required
@admin_required
def report():
    period = request.args.get("period", "daily")
    rows = _report_rows(period)
    return render_template("attendance_report.html", rows=rows, period=period)


@bp.route("/report/export", methods=["POST"])
@login_required
@admin_required
def report_export():
    period = request.form.get("period", "daily")
    fmt = request.form.get("format", "xlsx")
    rows = _report_rows(period)
    headers = ["Date", "Teacher", "Status", "Check-in", "Check-out", "Late (min)", "Source"]
    data = [[r["date"], r["teacher"], r["status"], r["check_in"], r["check_out"],
             r["late_minutes"] or 0, r["source"]] for r in rows]
    name = f"attendance_{period}_{uuid4().hex[:6]}"
    if fmt == "xlsx":
        from docbuild import build_xlsx
        path = REPORT_DIR / f"{name}.xlsx"
        build_xlsx("Attendance", headers, data, path)
        return send_from_directory(str(REPORT_DIR), path.name, as_attachment=True)
    from docbuild import build_pdf
    content = {"title": f"Attendance Report ({period})",
               "sections": [{"heading": "Records", "bullets": [" | ".join(map(str, row)) for row in data[:500]]}]}
    path = REPORT_DIR / f"{name}.pdf"
    build_pdf(content, path)
    return send_from_directory(str(REPORT_DIR), path.name, as_attachment=True)
