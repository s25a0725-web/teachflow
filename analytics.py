# -*- coding: utf-8 -*-
"""Analytics dashboard: teacher-scoped KPIs and charts."""
from collections import defaultdict

from flask import Blueprint, render_template, session

from db import get_db
from views import login_required

bp = Blueprint("analytics", __name__)


@bp.route("/analytics")
@login_required
def index():
    uid = session["user_id"]
    db = get_db()
    classes = db.execute(
        "SELECT id, name FROM classes WHERE teacher_id=? ORDER BY name", (uid,)
    ).fetchall()
    n_students = db.execute(
        "SELECT COUNT(*) c FROM students s JOIN classes c ON c.id=s.class_id "
        "WHERE c.teacher_id=?", (uid,)
    ).fetchone()["c"]
    n_assignments = db.execute(
        "SELECT COUNT(*) c FROM assignments WHERE teacher_id=?", (uid,)
    ).fetchone()["c"]
    subs = db.execute(
        "SELECT s.marks, a.title, c.name AS class_name "
        "FROM submissions s JOIN assignments a ON a.id=s.assignment_id "
        "JOIN classes c ON c.id=a.class_id "
        "WHERE a.teacher_id=? AND s.marks IS NOT NULL ORDER BY a.id",
        (uid,),
    ).fetchall()
    att = db.execute(
        "SELECT a.status, COUNT(*) c FROM attendance a "
        "JOIN classes cl ON cl.id=a.class_id WHERE cl.teacher_id=? GROUP BY a.status",
        (uid,),
    ).fetchall()
    db.close()

    marks = [r["marks"] for r in subs]
    avg_mark = round(sum(marks) / len(marks), 1) if marks else None
    att_map = {r["status"]: r["c"] for r in att}
    present = att_map.get("present", 0) + att_map.get("late", 0)
    total_att = sum(att_map.values())
    att_rate = round(present / total_att * 100, 1) if total_att else None

    # Average marks per assignment (stable order = assignment creation order)
    by_assign = defaultdict(list)
    for r in subs:
        by_assign[r["title"]].append(r["marks"])
    assign_labels = list(by_assign.keys())
    assign_avgs = [round(sum(by_assign[k]) / len(by_assign[k]), 1) for k in assign_labels]

    # Class performance
    by_class = defaultdict(list)
    for r in subs:
        by_class[r["class_name"]].append(r["marks"])
    class_labels = list(by_class.keys())
    class_avgs = [round(sum(by_class[k]) / len(by_class[k]), 1) for k in class_labels]

    # Marks distribution buckets
    buckets = [("0-39", 0, 39), ("40-54", 40, 54), ("55-69", 55, 69),
               ("70-84", 70, 84), ("85-100", 85, 100)]
    dist_labels, dist_counts = [], []
    for label, lo, hi in buckets:
        dist_labels.append(label)
        dist_counts.append(sum(1 for m in marks if lo <= m <= hi))

    chart = {
        "assign_labels": assign_labels,
        "assign_avgs": assign_avgs,
        "class_labels": class_labels,
        "class_avgs": class_avgs,
        "dist_labels": dist_labels,
        "dist_counts": dist_counts,
        "att": {
            "present": att_map.get("present", 0),
            "late": att_map.get("late", 0),
            "absent": att_map.get("absent", 0),
        },
    }

    kpi = {
        "students": n_students,
        "classes": len(classes),
        "assignments": n_assignments,
        "avg_mark": avg_mark,
        "att_rate": att_rate,
    }

    return render_template("analytics.html", chart=chart, kpi=kpi)
