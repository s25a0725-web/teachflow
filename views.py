# -*- coding: utf-8 -*-
"""Main application routes for all teacher features."""
import json
import os
from datetime import date
from functools import wraps
from pathlib import Path

from flask import (
    Blueprint, render_template, request, redirect, url_for, session, flash, g,
    send_from_directory, current_app,
)

from db import get_db, get_setting, set_setting
from generators import (
    lesson_plan as gen_lesson_plan,
    generate_quiz,
    suggest_feedback,
    report_comment,
)

_BASE = Path(__file__).resolve().parent
_UPLOAD_ROOT = Path(os.environ.get("TEACHFLOW_UPLOAD_ROOT", str(_BASE / "uploads")))
BRANDING_DIR = _UPLOAD_ROOT / "branding"
BRANDING_DIR.mkdir(parents=True, exist_ok=True)

bp = Blueprint("views", __name__)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return wrapper


def current_user():
    if "user_id" not in session:
        return None
    db = get_db()
    u = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    db.close()
    return u


def lang():
    return session.get("lang", "en")


def my_classes(user_id):
    db = get_db()
    rows = db.execute("SELECT * FROM classes WHERE teacher_id = ? ORDER BY name", (user_id,)).fetchall()
    db.close()
    return rows


def my_students(user_id):
    db = get_db()
    rows = db.execute(
        "SELECT s.*, c.name AS class_name FROM students s "
        "JOIN classes c ON c.id = s.class_id "
        "WHERE c.teacher_id = ? ORDER BY s.name", (user_id,)).fetchall()
    db.close()
    return rows


@bp.before_request
def load_globals():
    g.lang = session.get("lang", "en")
    g.user = None
    if "user_id" in session:
        g.user = current_user()


# --------------------------------------------------------------------------
# Language toggle
# --------------------------------------------------------------------------
@bp.route("/lang/<code>")
def set_lang(code):
    if code in ("en", "ms", "ta"):
        session["lang"] = code
    return redirect(request.referrer or url_for("views.dashboard"))


# --------------------------------------------------------------------------
# Dashboard
# --------------------------------------------------------------------------
@bp.route("/")
@login_required
def dashboard():
    uid = session["user_id"]
    db = get_db()
    n_classes = db.execute("SELECT COUNT(*) c FROM classes WHERE teacher_id=?", (uid,)).fetchone()["c"]
    n_students = db.execute(
        "SELECT COUNT(*) c FROM students s JOIN classes cl ON cl.id=s.class_id WHERE cl.teacher_id=?", (uid,)
    ).fetchone()["c"]
    n_assignments = db.execute("SELECT COUNT(*) c FROM assignments WHERE teacher_id=?", (uid,)).fetchone()["c"]
    today = date.today().isoformat()
    n_att = db.execute(
        "SELECT COUNT(*) c FROM attendance a JOIN classes cl ON cl.id=a.class_id "
        "WHERE cl.teacher_id=? AND a.date=?", (uid, today)).fetchone()["c"]
    db.close()
    return render_template("dashboard.html", n_classes=n_classes, n_students=n_students,
                           n_assignments=n_assignments, n_att=n_att)


# --------------------------------------------------------------------------
# Lesson plans
# --------------------------------------------------------------------------
@bp.route("/lesson-plans", methods=["GET", "POST"])
@login_required
def lesson_plans():
    uid = session["user_id"]
    if request.method == "POST":
        topic = request.form.get("topic", "").strip()
        if not topic:
            flash("gen_empty", "error")
            return redirect(url_for("views.lesson_plans"))
        subject = request.form.get("subject", "").strip()
        grade = request.form.get("grade", "").strip()
        duration = request.form.get("duration", "60").strip() or "60"
        lp_lang = request.form.get("lp_lang", lang())
        content = gen_lesson_plan(topic, subject, grade, int(duration), lp_lang)
        db = get_db()
        db.execute(
            "INSERT INTO lesson_plans (teacher_id, title, topic, subject, grade, language, content) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (uid, f"{topic} - {subject}", topic, subject, grade, lp_lang, content),
        )
        db.commit()
        db.close()
        flash("lp_generated", "success")
        return render_template("lesson_plans.html", content=content, saved=saved_plans(uid))

    return render_template("lesson_plans.html", content=None, saved=saved_plans(uid))


def saved_plans(uid):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM lesson_plans WHERE teacher_id=? ORDER BY id DESC LIMIT 20", (uid,)).fetchall()
    db.close()
    return rows


@bp.route("/lesson-plans/<int:pid>")
@login_required
def view_plan(pid):
    uid = session["user_id"]
    db = get_db()
    plan = db.execute("SELECT * FROM lesson_plans WHERE id=? AND teacher_id=?", (pid, uid)).fetchone()
    db.close()
    if plan is None:
        return redirect(url_for("views.lesson_plans"))
    return render_template("lesson_plan_view.html", plan=plan)


# --------------------------------------------------------------------------
# Quiz generator
# --------------------------------------------------------------------------
@bp.route("/quizzes", methods=["GET", "POST"])
@login_required
def quizzes():
    uid = session["user_id"]
    if request.method == "POST":
        topic = request.form.get("topic", "").strip()
        if not topic:
            flash("gen_empty", "error")
            return redirect(url_for("views.quizzes"))
        subject = request.form.get("subject", "").strip()
        grade = request.form.get("grade", "").strip()
        num = int(request.form.get("num", "5"))
        difficulty = request.form.get("difficulty", "medium")
        qz_lang = request.form.get("qz_lang", lang())
        qz_type = request.form.get("qz_type", "mixed")
        qs = generate_quiz(subject, topic, grade, num, difficulty, qz_lang, qz_type)
        db = get_db()
        db.execute(
            "INSERT INTO quizzes (teacher_id, title, subject, topic, language, questions_json) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (uid, f"{topic} - {subject}", subject, topic, qz_lang, json.dumps(qs)),
        )
        db.commit()
        db.close()
        return render_template("quizzes.html", questions=qs, saved=saved_quizzes(uid))

    return render_template("quizzes.html", questions=None, saved=saved_quizzes(uid))


def saved_quizzes(uid):
    db = get_db()
    rows = db.execute("SELECT * FROM quizzes WHERE teacher_id=? ORDER BY id DESC LIMIT 20", (uid,)).fetchall()
    db.close()
    return rows


@bp.route("/quizzes/<int:qid>")
@login_required
def view_quiz(qid):
    uid = session["user_id"]
    db = get_db()
    qz = db.execute("SELECT * FROM quizzes WHERE id=? AND teacher_id=?", (qid, uid)).fetchone()
    db.close()
    if qz is None:
        return redirect(url_for("views.quizzes"))
    questions = json.loads(qz["questions_json"])
    return render_template("quiz_view.html", qz=qz, questions=questions)


# --------------------------------------------------------------------------
# Grading
# --------------------------------------------------------------------------
@bp.route("/grading")
@login_required
def grading():
    uid = session["user_id"]
    db = get_db()
    assignments = db.execute(
        "SELECT a.*, c.name AS class_name, "
        "(SELECT COUNT(*) FROM submissions s WHERE s.assignment_id=a.id) AS n_sub "
        "FROM assignments a JOIN classes c ON c.id=a.class_id "
        "WHERE a.teacher_id=? ORDER BY a.id DESC", (uid,)).fetchall()
    db.close()
    return render_template("grading.html", assignments=assignments, classes=my_classes(uid))


@bp.route("/grading/new", methods=["POST"])
@login_required
def new_assignment():
    uid = session["user_id"]
    title = request.form.get("title", "").strip()
    class_id = int(request.form.get("class_id"))
    total_marks = int(request.form.get("total_marks", "100"))
    description = request.form.get("description", "").strip()
    db = get_db()
    db.execute(
        "INSERT INTO assignments (class_id, teacher_id, title, description, total_marks) VALUES (?, ?, ?, ?, ?)",
        (class_id, uid, title, description, total_marks),
    )
    db.commit()
    db.close()
    return redirect(url_for("views.grading"))


@bp.route("/grading/<int:aid>", methods=["GET", "POST"])
@login_required
def grade_assignment(aid):
    uid = session["user_id"]
    db = get_db()
    assignment = db.execute(
        "SELECT a.*, c.name AS class_name FROM assignments a "
        "JOIN classes c ON c.id=a.class_id WHERE a.id=? AND a.teacher_id=?", (aid, uid)).fetchone()
    if assignment is None:
        db.close()
        return redirect(url_for("views.grading"))
    students = db.execute(
        "SELECT * FROM students WHERE class_id=? ORDER BY name", (assignment["class_id"],)).fetchall()

    if request.method == "POST":
        total = assignment["total_marks"]
        for s in students:
            marks_raw = request.form.get(f"marks_{s['id']}", "").strip()
            feedback = request.form.get(f"feedback_{s['id']}", "").strip()
            if marks_raw == "" and not feedback:
                continue
            if marks_raw == "":
                marks = None
            else:
                marks = float(marks_raw)
                if not feedback:
                    feedback = suggest_feedback(marks, total, s["name"], lang())
            status = "graded" if marks is not None else "pending"
            db.execute(
                "INSERT INTO submissions (assignment_id, student_id, marks, feedback, status) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(assignment_id, student_id) DO UPDATE SET "
                "marks=excluded.marks, feedback=excluded.feedback, status=excluded.status",
                (aid, s["id"], marks, feedback, status),
            )
        db.commit()
        flash("gr_mark_saved", "success")

    # reload submissions
    subs = db.execute("SELECT * FROM submissions WHERE assignment_id=?", (aid,)).fetchall()
    db.close()
    sub_map = {s["student_id"]: s for s in subs}
    return render_template("grade_assignment.html", assignment=assignment,
                           students=students, sub_map=sub_map)


# --------------------------------------------------------------------------
# Attendance
# --------------------------------------------------------------------------
@bp.route("/attendance", methods=["GET", "POST"])
@login_required
def attendance():
    uid = session["user_id"]
    classes = my_classes(uid)
    selected = None
    students = []
    att_date = request.form.get("date") if request.method == "POST" else date.today().isoformat()

    class_id = request.form.get("class_id") if request.method == "POST" else request.args.get("class_id")
    if class_id:
        class_id = int(class_id)
        selected = class_id
        db = get_db()
        students = db.execute("SELECT * FROM students WHERE class_id=? ORDER BY name", (class_id,)).fetchall()
        if request.method == "POST":
            for s in students:
                status = request.form.get(f"status_{s['id']}", "present")
                ttime = request.form.get(f"time_{s['id']}", "").strip()
                db.execute(
                    "INSERT INTO attendance (class_id, student_id, date, status, time) VALUES (?, ?, ?, ?, ?) "
                    "ON CONFLICT(class_id, student_id, date) DO UPDATE SET status=excluded.status, time=excluded.time",
                    (class_id, s["id"], att_date, status, ttime),
                )
            db.commit()
            flash("att_saved", "success")
        # existing marks for the selected date
        existing = db.execute(
            "SELECT student_id, status, time FROM attendance WHERE class_id=? AND date=?",
            (class_id, att_date)).fetchall()
        db.close()
        existing_map = {e["student_id"]: e for e in existing}
    else:
        existing_map = {}

    return render_template("attendance.html", classes=classes, selected=selected,
                           students=students, att_date=att_date, existing_map=existing_map)


@bp.route("/teacher-attendance", methods=["GET", "POST"])
@login_required
def teacher_attendance():
    uid = session["user_id"]
    is_admin = session.get("role") == "admin"
    att_date = request.form.get("date") if request.method == "POST" else (request.args.get("date") or date.today().isoformat())
    db = get_db()
    if is_admin:
        teachers = db.execute("SELECT id, name FROM users ORDER BY name").fetchall()
    else:
        teachers = db.execute("SELECT id, name FROM users WHERE id=?", (uid,)).fetchall()

    if request.method == "POST":
        for t in teachers:
            status = request.form.get(f"status_{t['id']}")
            if status is None:
                continue
            ttime = request.form.get(f"time_{t['id']}", "").strip()
            db.execute(
                "INSERT INTO teacher_attendance (teacher_id, date, status, time) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(teacher_id, date) DO UPDATE SET status=excluded.status, time=excluded.time",
                (t["id"], att_date, status, ttime),
            )
        db.commit()
        flash("att_saved", "success")

    existing = db.execute(
        "SELECT teacher_id, status, time FROM teacher_attendance WHERE date=?", (att_date,)).fetchall()
    db.close()
    existing_map = {e["teacher_id"]: e for e in existing}
    return render_template("teacher_attendance.html", teachers=teachers, att_date=att_date,
                           existing_map=existing_map, is_admin=is_admin)


@bp.route("/branding/logo")
def branding_logo():
    fname = get_setting("logo_filename")
    if fname and (BRANDING_DIR / fname).exists():
        return send_from_directory(str(BRANDING_DIR), fname)
    return send_from_directory(current_app.static_folder, "logo.svg")


@bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if session.get("role") != "admin":
        return redirect(url_for("views.dashboard"))
    if request.method == "POST":
        action = request.form.get("action")
        if action == "branding":
            set_setting("school_name", request.form.get("school_name", "").strip())
            set_setting("tagline", request.form.get("tagline", "").strip())
            f = request.files.get("logo")
            if f and f.filename:
                ext = Path(f.filename).suffix.lower()
                if ext not in (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"):
                    ext = ".png"
                fname = f"logo{ext}"
                f.save(BRANDING_DIR / fname)
                set_setting("logo_filename", fname)
            flash("settings_saved", "success")
        elif action == "remove_logo":
            set_setting("logo_filename", "")
            flash("settings_saved", "success")
        elif action == "user_role":
            target = int(request.form.get("user_id"))
            role = request.form.get("role")
            if target != session["user_id"] and role in ("admin", "teacher"):
                db = get_db()
                db.execute("UPDATE users SET role=? WHERE id=?", (role, target))
                db.commit()
                db.close()
                flash("settings_saved", "success")
        return redirect(url_for("views.settings"))
    db = get_db()
    users = db.execute("SELECT id, email, name, role FROM users ORDER BY id").fetchall()
    db.close()
    return render_template("settings.html", users=users,
                           school_name=get_setting("school_name") or "",
                           tagline=get_setting("tagline") or "",
                           has_logo=bool(get_setting("logo_filename")))


# --------------------------------------------------------------------------
# Timetable
# --------------------------------------------------------------------------
@bp.route("/timetable", methods=["GET", "POST"])
@login_required
def timetable():
    uid = session["user_id"]
    db = get_db()
    if request.method == "POST":
        day = int(request.form.get("day"))
        period = int(request.form.get("period"))
        subject = request.form.get("subject", "").strip()
        class_name = request.form.get("class_name", "").strip()
        db.execute(
            "INSERT INTO timetable (teacher_id, day, period, subject, class_name) VALUES (?, ?, ?, ?, ?)",
            (uid, day, period, subject, class_name),
        )
        db.commit()
    entries = db.execute("SELECT * FROM timetable WHERE teacher_id=? ORDER BY day, period", (uid,)).fetchall()
    db.close()
    return render_template("timetable.html", entries=entries)


@bp.route("/timetable/delete/<int:tid>", methods=["POST"])
@login_required
def timetable_delete(tid):
    uid = session["user_id"]
    db = get_db()
    db.execute("DELETE FROM timetable WHERE id=? AND teacher_id=?", (tid, uid))
    db.commit()
    db.close()
    return redirect(url_for("views.timetable"))


# --------------------------------------------------------------------------
# Classes & students
# --------------------------------------------------------------------------
@bp.route("/classes", methods=["GET", "POST"])
@login_required
def classes():
    uid = session["user_id"]
    db = get_db()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add_class":
            db.execute("INSERT INTO classes (teacher_id, name, subject, grade) VALUES (?, ?, ?, ?)",
                       (uid, request.form.get("name", "").strip(),
                        request.form.get("subject", "").strip(),
                        request.form.get("grade", "").strip()))
        elif action == "add_student":
            db.execute("INSERT INTO students (class_id, name, parent_name, parent_email) VALUES (?, ?, ?, ?)",
                       (int(request.form.get("class_id")),
                        request.form.get("name", "").strip(),
                        request.form.get("parent_name", "").strip(),
                        request.form.get("parent_email", "").strip()))
        db.commit()

    classes_rows = my_classes(uid)
    # attach student counts
    student_counts = {}
    students_rows = my_students(uid)
    for s in students_rows:
        student_counts[s["class_id"]] = student_counts.get(s["class_id"], 0) + 1
    db.close()
    return render_template("classes.html", classes=classes_rows,
                           students=students_rows, student_counts=student_counts)


# --------------------------------------------------------------------------
# Reports
# --------------------------------------------------------------------------
@bp.route("/reports")
@login_required
def reports():
    uid = session["user_id"]
    students = my_students(uid)
    report = None
    sid = request.args.get("student_id")
    if sid:
        sid = int(sid)
        report = build_report(sid)
    return render_template("reports.html", students=students, report=report, selected=sid)


def build_report(sid):
    db = get_db()
    student = db.execute(
        "SELECT s.*, c.name AS class_name, c.subject AS class_subject FROM students s "
        "JOIN classes c ON c.id=s.class_id WHERE s.id=?", (sid,)).fetchone()
    if student is None:
        db.close()
        return None
    grades = db.execute(
        "SELECT a.title, a.total_marks, s.marks, s.feedback FROM submissions s "
        "JOIN assignments a ON a.id=s.assignment_id "
        "WHERE s.student_id=? AND s.marks IS NOT NULL ORDER BY a.id DESC", (sid,)).fetchall()
    att = db.execute(
        "SELECT status, COUNT(*) c FROM attendance WHERE student_id=? GROUP BY status", (sid,)).fetchall()
    db.close()

    total_att = sum(r["c"] for r in att)
    present = sum(r["c"] for r in att if r["status"] == "present")
    late = sum(r["c"] for r in att if r["status"] == "late")
    att_rate = round((present + late) / total_att * 100, 1) if total_att else None

    marks_list = [g["marks"] for g in grades]
    avg = round(sum(marks_list) / len(marks_list), 1) if marks_list else None
    comment = report_comment(avg if avg is not None else 0, student["name"], lang())

    return {
        "student": student, "grades": grades, "avg": avg,
        "att_rate": att_rate, "total_att": total_att, "present": present, "late": late,
        "comment": comment,
    }


# --------------------------------------------------------------------------
# Parent messages
# --------------------------------------------------------------------------
@bp.route("/parents", methods=["GET", "POST"])
@login_required
def parents():
    uid = session["user_id"]
    students = my_students(uid)
    body = ""
    selected = request.args.get("student_id") or (request.form.get("student_id") if request.method == "POST" else None)

    if request.method == "POST":
        action = request.form.get("action")
        sid = request.form.get("student_id")
        if action == "generate" and sid:
            rep = build_report(int(sid))
            if rep:
                selected = sid
                st = rep["student"]
                if lang() == "ms":
                    avg_txt = f"purata {rep['avg']}%" if rep["avg"] is not None else "tiada markah lagi"
                    body = (f"Tuan/Puan, berikut ringkasan kemajuan {st['name']}: {avg_txt}, "
                            f"kehadiran {rep['att_rate']}%. {rep['comment']}")
                else:
                    avg_txt = f"average {rep['avg']}%" if rep["avg"] is not None else "no marks yet"
                    body = (f"Dear parent, here is a summary of {st['name']}'s progress: {avg_txt}, "
                            f"attendance {rep['att_rate']}%. {rep['comment']}")
        elif action == "save" and sid:
            st = next((s for s in students if s["id"] == int(sid)), None)
            db = get_db()
            db.execute(
                "INSERT INTO messages (teacher_id, student_id, parent_name, parent_email, subject, body) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (uid, int(sid), st["parent_name"] if st else "",
                 st["parent_email"] if st else "",
                 request.form.get("subject", "").strip(),
                 request.form.get("body", "").strip()),
            )
            db.commit()
            db.close()
            flash("pt_sent", "success")
            selected = sid
            body = request.form.get("body", "").strip()

    db = get_db()
    sent = db.execute("SELECT * FROM messages WHERE teacher_id=? ORDER BY id DESC LIMIT 20", (uid,)).fetchall()
    db.close()
    return render_template("parents.html", students=students, body=body, selected=selected, sent=sent)


# --------------------------------------------------------------------------
# Delete actions (every module)
# --------------------------------------------------------------------------
@bp.route("/lesson-plans/<int:pid>/delete", methods=["POST"])
@login_required
def delete_plan(pid):
    uid = session["user_id"]
    db = get_db()
    db.execute("DELETE FROM lesson_plans WHERE id=? AND teacher_id=?", (pid, uid))
    db.commit()
    db.close()
    flash("deleted", "success")
    return redirect(url_for("views.lesson_plans"))


@bp.route("/quizzes/<int:qid>/delete", methods=["POST"])
@login_required
def delete_quiz(qid):
    uid = session["user_id"]
    db = get_db()
    db.execute("DELETE FROM quizzes WHERE id=? AND teacher_id=?", (qid, uid))
    db.commit()
    db.close()
    flash("deleted", "success")
    return redirect(url_for("views.quizzes"))


@bp.route("/grading/<int:aid>/delete", methods=["POST"])
@login_required
def delete_assignment(aid):
    uid = session["user_id"]
    db = get_db()
    db.execute("DELETE FROM submissions WHERE assignment_id=?", (aid,))
    db.execute("DELETE FROM assignments WHERE id=? AND teacher_id=?", (aid, uid))
    db.commit()
    db.close()
    flash("deleted", "success")
    return redirect(url_for("views.grading"))


@bp.route("/classes/<int:cid>/delete", methods=["POST"])
@login_required
def delete_class(cid):
    uid = session["user_id"]
    db = get_db()
    cls = db.execute("SELECT id FROM classes WHERE id=? AND teacher_id=?", (cid, uid)).fetchone()
    if cls:
        sids = [r["id"] for r in db.execute("SELECT id FROM students WHERE class_id=?", (cid,)).fetchall()]
        if sids:
            ph = ",".join("?" * len(sids))
            db.execute(f"DELETE FROM submissions WHERE student_id IN ({ph})", sids)
            db.execute(f"DELETE FROM attendance WHERE student_id IN ({ph})", sids)
            db.execute(f"DELETE FROM messages WHERE student_id IN ({ph})", sids)
        aids = [r["id"] for r in db.execute("SELECT id FROM assignments WHERE class_id=?", (cid,)).fetchall()]
        if aids:
            ph = ",".join("?" * len(aids))
            db.execute(f"DELETE FROM submissions WHERE assignment_id IN ({ph})", aids)
        db.execute("DELETE FROM attendance WHERE class_id=?", (cid,))
        db.execute("DELETE FROM assignments WHERE class_id=?", (cid,))
        db.execute("DELETE FROM students WHERE class_id=?", (cid,))
        db.execute("DELETE FROM classes WHERE id=?", (cid,))
        db.commit()
    db.close()
    flash("deleted", "success")
    return redirect(url_for("views.classes"))


@bp.route("/students/<int:sid>/delete", methods=["POST"])
@login_required
def delete_student(sid):
    uid = session["user_id"]
    db = get_db()
    st = db.execute(
        "SELECT s.id FROM students s JOIN classes c ON c.id=s.class_id WHERE s.id=? AND c.teacher_id=?",
        (sid, uid)).fetchone()
    if st:
        db.execute("DELETE FROM submissions WHERE student_id=?", (sid,))
        db.execute("DELETE FROM attendance WHERE student_id=?", (sid,))
        db.execute("DELETE FROM messages WHERE student_id=?", (sid,))
        db.execute("DELETE FROM students WHERE id=?", (sid,))
        db.commit()
    db.close()
    flash("deleted", "success")
    return redirect(url_for("views.classes"))


@bp.route("/parents/<int:mid>/delete", methods=["POST"])
@login_required
def delete_message(mid):
    uid = session["user_id"]
    db = get_db()
    db.execute("DELETE FROM messages WHERE id=? AND teacher_id=?", (mid, uid))
    db.commit()
    db.close()
    flash("deleted", "success")
    return redirect(url_for("views.parents"))


@bp.route("/settings/user/<int:uid2>/delete", methods=["POST"])
@login_required
def delete_user(uid2):
    if session.get("role") != "admin" or uid2 == session["user_id"]:
        return redirect(url_for("views.settings"))
    db = get_db()
    cids = [r["id"] for r in db.execute("SELECT id FROM classes WHERE teacher_id=?", (uid2,)).fetchall()]
    for cid in cids:
        sids = [r["id"] for r in db.execute("SELECT id FROM students WHERE class_id=?", (cid,)).fetchall()]
        if sids:
            ph = ",".join("?" * len(sids))
            db.execute(f"DELETE FROM submissions WHERE student_id IN ({ph})", sids)
            db.execute(f"DELETE FROM attendance WHERE student_id IN ({ph})", sids)
            db.execute(f"DELETE FROM messages WHERE student_id IN ({ph})", sids)
        aids = [r["id"] for r in db.execute("SELECT id FROM assignments WHERE class_id=?", (cid,)).fetchall()]
        if aids:
            ph = ",".join("?" * len(aids))
            db.execute(f"DELETE FROM submissions WHERE assignment_id IN ({ph})", aids)
    if cids:
        ph = ",".join("?" * len(cids))
        db.execute(f"DELETE FROM students WHERE class_id IN ({ph})", cids)
        db.execute(f"DELETE FROM attendance WHERE class_id IN ({ph})", cids)
        db.execute(f"DELETE FROM assignments WHERE class_id IN ({ph})", cids)
        db.execute(f"DELETE FROM classes WHERE id IN ({ph})", cids)
    doc_dir = _UPLOAD_ROOT / "documents" / str(uid2)
    docs = db.execute("SELECT id, stored_name FROM documents WHERE teacher_id=?", (uid2,)).fetchall()
    for d in docs:
        try:
            (doc_dir / d["stored_name"]).unlink(missing_ok=True)
        except Exception:
            pass
        db.execute("DELETE FROM signatures WHERE document_id=?", (d["id"],))
        db.execute("DELETE FROM sign_requests WHERE document_id=?", (d["id"],))
    db.execute("DELETE FROM documents WHERE teacher_id=?", (uid2,))
    db.execute("DELETE FROM lesson_plans WHERE teacher_id=?", (uid2,))
    db.execute("DELETE FROM quizzes WHERE teacher_id=?", (uid2,))
    db.execute("DELETE FROM timetable WHERE teacher_id=?", (uid2,))
    db.execute("DELETE FROM teacher_attendance WHERE teacher_id=?", (uid2,))
    db.execute("DELETE FROM messages WHERE teacher_id=?", (uid2,))
    db.execute("DELETE FROM folders WHERE teacher_id=?", (uid2,))
    db.execute("DELETE FROM users WHERE id=?", (uid2,))
    db.commit()
    db.close()
    flash("deleted", "success")
    return redirect(url_for("views.settings"))
