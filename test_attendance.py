# -*- coding: utf-8 -*-
"""Smart Attendance module test suite (CSRF off for raw flow testing)."""
import io
import os
import sys
import tempfile

os.environ["TEACHFLOW_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")
os.environ["TEACHFLOW_UPLOAD_ROOT"] = tempfile.mkdtemp()
os.environ["TEACHFLOW_USERS"] = os.path.join(tempfile.mkdtemp(), "u.json")
os.environ["TEACHFLOW_SECRET"] = "att-test"
os.environ["TEACHFLOW_CSRF"] = "0"

sys.path.insert(0, r"C:\Users\tinee\teachflow")

from app import app  # noqa: E402
from db import get_db  # noqa: E402
import userstore  # noqa: E402

fail = 0


def ok(name, cond, extra=""):
    global fail
    if not cond:
        fail += 1
    print(("OK  " if cond else "FAIL") + f"  {name}" + (f"  [got {extra}]" if extra and not cond else ""))


c = app.test_client()
c.post("/register", data={"email": "admin@t.com", "name": "Admin", "password": "secret123"})
c.post("/register", data={"email": "teacher@t.com", "name": "Teacher", "password": "secret123"})
admin = userstore.get_by_email("admin@t.com")
teacher = userstore.get_by_email("teacher@t.com")
ok("first user is admin", admin and admin["role"] == "admin")
ok("second user is teacher", teacher and teacher["role"] == "teacher")

# admin login + configure school location (start 00:00 grace 0 => any check-in is late)
c.post("/login", data={"email": "admin@t.com", "password": "secret123"})
r = c.post("/attendance/settings", data={
    "location_name": "SJK(T) Sepang", "latitude": "2.6810", "longitude": "101.7500",
    "radius": "200", "start_time": "00:00", "grace_minutes": "0",
    "end_time": "23:59", "absent_deadline": "09:00"}, follow_redirects=True)
ok("admin saves settings", r.status_code == 200, r.status_code)

# teacher login + GPS check-in
tc = app.test_client()
tc.post("/login", data={"email": "teacher@t.com", "password": "secret123"})
r = tc.post("/attendance/check-in", json={"latitude": 2.6810, "longitude": 101.7500, "accuracy": 10})
d = r.get_json() or {}
ok("GPS check-in ok", r.status_code == 200 and d.get("ok"), (r.status_code, d))
ok("check-in computes late (start 00:00 grace 0)", d.get("late_minutes") is not None, d.get("late_minutes"))

r = tc.post("/attendance/check-in", json={"latitude": 2.6810, "longitude": 101.7500, "accuracy": 10})
ok("duplicate check-in rejected (409)", r.status_code == 409, r.status_code)

r = tc.post("/attendance/check-out", json={"latitude": 3.0, "longitude": 101.0, "accuracy": 10})
ok("outside geofence rejected (400)", r.status_code == 400, r.status_code)

r = tc.post("/attendance/check-out", json={"latitude": 2.6810, "longitude": 101.7500, "accuracy": 10})
ok("GPS check-out ok", r.status_code == 200, r.status_code)

r = tc.get("/attendance/status")
d = r.get_json() or {}
ok("status reflects late + recorded times", d.get("record") and d["record"]["status"] == "late" and d["record"]["check_in_time"], d)

r = tc.get("/attendance/me")
ok("teacher dashboard 200", r.status_code == 200, r.status_code)
r = c.get("/attendance/admin")
ok("admin dashboard 200", r.status_code == 200, r.status_code)
r = c.get("/attendance/report")
ok("report 200", r.status_code == 200, r.status_code)

# MC submission (teacher)
r = tc.post("/attendance/mc", data={
    "start_date": "2026-11-05", "end_date": "2026-11-06", "reason": "Fever",
    "document": (io.BytesIO(b"%PDF-1.4 fake mc"), "mc.pdf")},
    content_type="multipart/form-data", follow_redirects=True)
ok("MC submitted", r.status_code == 200, r.status_code)

db = get_db()
mcrow = db.execute("SELECT id FROM mc_applications ORDER BY id DESC LIMIT 1").fetchone()
db.close()
r = c.post(f"/attendance/mc/{mcrow['id']}/review", data={"status": "approved", "remark": "verified"}, follow_redirects=True)
ok("admin approves MC", r.status_code == 200, r.status_code)
r = tc.get(f"/attendance/mc/{mcrow['id']}/file")
ok("teacher can view own MC file", r.status_code == 200, r.status_code)

# MC file access control: a different teacher must be denied
c3 = app.test_client()
c3.post("/register", data={"email": "other@t.com", "name": "Other", "password": "secret123"})
c3.post("/login", data={"email": "other@t.com", "password": "secret123"})
r = c3.get(f"/attendance/mc/{mcrow['id']}/file")
ok("other teacher blocked from MC file (403)", r.status_code == 403, r.status_code)

# Leave submission + review
r = tc.post("/attendance/leave", data={"leave_type": "annual", "start_date": "2026-11-10", "end_date": "2026-11-12", "reason": "Holiday"}, follow_redirects=True)
ok("leave submitted", r.status_code == 200, r.status_code)
db = get_db()
lrow = db.execute("SELECT id FROM leave_applications ORDER BY id DESC LIMIT 1").fetchone()
db.close()
r = c.post(f"/attendance/leave/{lrow['id']}/review", data={"status": "approved", "remark": "ok"}, follow_redirects=True)
ok("admin approves leave", r.status_code == 200, r.status_code)

# RBAC: teacher blocked from admin dashboard
r = tc.get("/attendance/admin", follow_redirects=False)
ok("teacher blocked from admin dashboard (302)", r.status_code == 302, r.status_code)

print("\nRESULT:", "ALL PASS" if fail == 0 else f"{fail} FAILED")
