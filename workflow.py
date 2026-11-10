# -*- coding: utf-8 -*-
"""Workflow module: approvals, projects & tasks (Kanban), academic calendar.

Approvals follow Draft -> Submitted -> Under Review -> Approved/Rejected/Revision
Required with a full status history. Projects group tasks shown in a Kanban board.
The calendar stores events/deadlines/meetings for the academic year.
"""
from datetime import date
from functools import wraps

from flask import (
    Blueprint, render_template, request, session, redirect, url_for, flash, jsonify,
)

from db import get_db
import userstore
from views import login_required

bp = Blueprint("workflow", __name__)

APPROVAL_STATUSES = ["draft", "submitted", "under_review", "approved", "rejected", "revision_required"]
TASK_STATUSES = ["todo", "in_progress", "done"]
TASK_PRIORITIES = ["low", "medium", "high"]
PROJECT_STATUSES = ["active", "completed", "archived"]


def _reviewer_required(f):
    """Only admins (or the assigned reviewer) may act on an approval."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not userstore.is_admin_role(session.get("role")):
            flash("forbidden", "error")
            return redirect(url_for("workflow.approvals"))
        return f(*args, **kwargs)
    return wrapper


def _log_history(db, approval_id, status, note, actor):
    db.execute(
        "INSERT INTO approval_history (approval_id, status, note, actor_id) VALUES (?,?,?,?)",
        (approval_id, status, note, actor),
    )


# ---------------------------------------------------------------------------
# Approvals
# ---------------------------------------------------------------------------
@bp.route("/approvals")
@login_required
def approvals():
    uid = session["user_id"]
    is_admin = userstore.is_admin_role(session.get("role"))
    db = get_db()
    if is_admin:
        rows = db.execute(
            "SELECT a.*, u.name AS owner_name FROM approvals a "
            "LEFT JOIN users u ON u.id = a.teacher_id ORDER BY a.id DESC"
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT a.* FROM approvals a WHERE a.teacher_id = ? ORDER BY a.id DESC", (uid,)
        ).fetchall()
    db.close()
    return render_template("approvals.html", approvals=rows, is_admin=is_admin,
                           statuses=APPROVAL_STATUSES)


@bp.route("/approvals/new", methods=["POST"])
@login_required
def approval_new():
    title = request.form.get("title", "").strip()
    doc_type = request.form.get("doc_type", "").strip()
    content = request.form.get("content", "").strip()
    if not title:
        flash("gen_empty", "error")
        return redirect(url_for("workflow.approvals"))
    db = get_db()
    cur = db.execute(
        "INSERT INTO approvals (teacher_id, title, doc_type, content, status) VALUES (?,?,?,?, 'draft')",
        (session["user_id"], title, doc_type, content),
    )
    _log_history(db, cur.lastrowid, "draft", "Created", session["user_id"])
    db.commit()
    db.close()
    flash("settings_saved", "success")
    return redirect(url_for("workflow.approvals"))


@bp.route("/approvals/<int:aid>/status", methods=["POST"])
@login_required
def approval_set_status(aid):
    new_status = request.form.get("status")
    note = request.form.get("note", "").strip()
    if new_status not in APPROVAL_STATUSES:
        flash("bad_status", "error")
        return redirect(url_for("workflow.approvals"))
    uid = session["user_id"]
    db = get_db()
    row = db.execute("SELECT * FROM approvals WHERE id = ?", (aid,)).fetchone()
    if not row:
        db.close()
        flash("not_found", "error")
        return redirect(url_for("workflow.approvals"))
    # Owners may only submit their own; reviewers/admin may approve/reject/revise.
    if row["teacher_id"] == uid and new_status not in ("submitted", "draft"):
        if not userstore.is_admin_role(session.get("role")):
            db.close()
            flash("forbidden", "error")
            return redirect(url_for("workflow.approvals"))
    if row["teacher_id"] != uid and not userstore.is_admin_role(session.get("role")):
        db.close()
        flash("forbidden", "error")
        return redirect(url_for("workflow.approvals"))
    db.execute(
        "UPDATE approvals SET status = ?, reviewer_note = ?, reviewer_id = ?, updated_at = datetime('now') WHERE id = ?",
        (new_status, note, uid if new_status != "submitted" else row["reviewer_id"], aid),
    )
    _log_history(db, aid, new_status, note, uid)
    db.commit()
    db.close()
    flash("settings_saved", "success")
    return redirect(url_for("workflow.approvals"))


@bp.route("/approvals/<int:aid>")
@login_required
def approval_detail(aid):
    uid = session["user_id"]
    is_admin = userstore.is_admin_role(session.get("role"))
    db = get_db()
    row = db.execute("SELECT * FROM approvals WHERE id = ?", (aid,)).fetchone()
    if not row or (row["teacher_id"] != uid and not is_admin):
        db.close()
        flash("not_found", "error")
        return redirect(url_for("workflow.approvals"))
    history = db.execute(
        "SELECT h.*, u.name AS actor_name FROM approval_history h "
        "LEFT JOIN users u ON u.id = h.actor_id WHERE h.approval_id = ? ORDER BY h.id",
        (aid,),
    ).fetchall()
    db.close()
    return render_template("approval_detail.html", a=row, history=history, is_admin=is_admin)


# ---------------------------------------------------------------------------
# Projects & tasks (Kanban)
# ---------------------------------------------------------------------------
@bp.route("/projects")
@login_required
def projects():
    uid = session["user_id"]
    db = get_db()
    projs = db.execute(
        "SELECT p.*, (SELECT COUNT(*) FROM tasks t WHERE t.project_id=p.id) AS n_tasks, "
        "(SELECT COUNT(*) FROM tasks t WHERE t.project_id=p.id AND t.status='done') AS n_done "
        "FROM projects p WHERE p.teacher_id = ? ORDER BY p.id DESC", (uid,)
    ).fetchall()
    db.close()
    return render_template("projects.html", projects=projs)


@bp.route("/projects/new", methods=["POST"])
@login_required
def project_new():
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    if not name:
        flash("gen_empty", "error")
        return redirect(url_for("workflow.projects"))
    db = get_db()
    db.execute("INSERT INTO projects (teacher_id, name, description) VALUES (?,?,?)",
               (session["user_id"], name, description))
    db.commit()
    db.close()
    flash("settings_saved", "success")
    return redirect(url_for("workflow.projects"))


@bp.route("/projects/<int:pid>/status", methods=["POST"])
@login_required
def project_status(pid):
    status = request.form.get("status")
    if status not in PROJECT_STATUSES:
        return redirect(url_for("workflow.projects"))
    db = get_db()
    db.execute("UPDATE projects SET status = ? WHERE id = ? AND teacher_id = ?",
               (status, pid, session["user_id"]))
    db.commit()
    db.close()
    return redirect(url_for("workflow.projects"))


@bp.route("/projects/<int:pid>")
@login_required
def project_board(pid):
    uid = session["user_id"]
    db = get_db()
    proj = db.execute("SELECT * FROM projects WHERE id = ? AND teacher_id = ?", (pid, uid)).fetchone()
    if not proj:
        db.close()
        flash("not_found", "error")
        return redirect(url_for("workflow.projects"))
    tasks = db.execute("SELECT * FROM tasks WHERE project_id = ? ORDER BY id", (pid,)).fetchall()
    users = userstore.all_users()
    db.close()
    by_status = {s: [t for t in tasks if t["status"] == s] for s in TASK_STATUSES}
    return render_template("project_board.html", proj=proj, by_status=by_status,
                           users=users, priorities=TASK_PRIORITIES)


@bp.route("/projects/<int:pid>/tasks/new", methods=["POST"])
@login_required
def task_new(pid):
    title = request.form.get("title", "").strip()
    if not title:
        return redirect(url_for("workflow.project_board", pid=pid))
    db = get_db()
    proj = db.execute("SELECT id FROM projects WHERE id = ? AND teacher_id = ?", (pid, session["user_id"])).fetchone()
    if not proj:
        db.close()
        return redirect(url_for("workflow.projects"))
    db.execute(
        "INSERT INTO tasks (project_id, title, description, status, priority, assignee_id, due_date) "
        "VALUES (?,?,?,?,?,?,?)",
        (pid, title, request.form.get("description", "").strip(),
         request.form.get("status", "todo"),
         request.form.get("priority", "medium"),
         request.form.get("assignee_id") or None,
         request.form.get("due_date") or None),
    )
    db.commit()
    db.close()
    return redirect(url_for("workflow.project_board", pid=pid))


@bp.route("/tasks/<int:tid>/move", methods=["POST"])
@login_required
def task_move(tid):
    status = request.form.get("status")
    if status not in TASK_STATUSES:
        return jsonify({"error": "bad_status"}), 400
    db = get_db()
    db.execute(
        "UPDATE tasks SET status = ? WHERE id = ? AND project_id IN "
        "(SELECT id FROM projects WHERE teacher_id = ?)",
        (status, tid, session["user_id"]),
    )
    db.commit()
    db.close()
    return jsonify({"ok": True})


@bp.route("/tasks/<int:tid>/delete", methods=["POST"])
@login_required
def task_delete(tid):
    db = get_db()
    db.execute(
        "DELETE FROM tasks WHERE id = ? AND project_id IN (SELECT id FROM projects WHERE teacher_id = ?)",
        (tid, session["user_id"]),
    )
    db.commit()
    db.close()
    return redirect(request.referrer or url_for("workflow.projects"))


# ---------------------------------------------------------------------------
# Academic calendar
# ---------------------------------------------------------------------------
@bp.route("/calendar")
@login_required
def calendar():
    uid = session["user_id"]
    db = get_db()
    events = db.execute(
        "SELECT * FROM calendar_events WHERE teacher_id = ? ORDER BY start_date", (uid,)
    ).fetchall()
    db.close()
    return render_template("calendar.html", events=events)


@bp.route("/calendar/new", methods=["POST"])
@login_required
def calendar_new():
    title = request.form.get("title", "").strip()
    start_date = request.form.get("start_date", "").strip()
    if not title or not start_date:
        flash("gen_empty", "error")
        return redirect(url_for("workflow.calendar"))
    db = get_db()
    db.execute(
        "INSERT INTO calendar_events (teacher_id, title, event_type, start_date, end_date, description) "
        "VALUES (?,?,?,?,?,?)",
        (session["user_id"], title, request.form.get("event_type", "").strip(),
         start_date, request.form.get("end_date") or None,
         request.form.get("description", "").strip()),
    )
    db.commit()
    db.close()
    flash("settings_saved", "success")
    return redirect(url_for("workflow.calendar"))


@bp.route("/calendar/<int:eid>/delete", methods=["POST"])
@login_required
def calendar_delete(eid):
    db = get_db()
    db.execute("DELETE FROM calendar_events WHERE id = ? AND teacher_id = ?", (eid, session["user_id"]))
    db.commit()
    db.close()
    return redirect(url_for("workflow.calendar"))
