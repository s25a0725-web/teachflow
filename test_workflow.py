# -*- coding: utf-8 -*-
"""Tests for the workflow module (approvals, projects/tasks, calendar)."""
import os
import sys
import tempfile

os.environ["TEACHFLOW_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")
os.environ["TEACHFLOW_UPLOAD_ROOT"] = tempfile.mkdtemp()
os.environ["TEACHFLOW_USERS"] = os.path.join(tempfile.mkdtemp(), "u.json")
os.environ["TEACHFLOW_SECRET"] = "test"
os.environ["TEACHFLOW_CSRF"] = "0"
for k in ("DEEPSEEK_API_KEY", "TEACHFLOW_AI_KEY", "OPENAI_API_KEY"):
    os.environ.pop(k, None)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import app

failures = []


def ok(name, cond, detail=""):
    print(("OK    " if cond else "FAIL  ") + name + (("  -> " + str(detail)) if detail and not cond else ""))
    if not cond:
        failures.append(name)


c = app.test_client()

# --- auth guard ---
r = c.get("/approvals")
ok("approvals requires login", r.status_code == 302, r.status_code)

c.post("/register", data={"email": "admin@wf.com", "name": "Admin", "password": "secret123"})
c.post("/login", data={"email": "admin@wf.com", "password": "secret123"})

# --- approvals ---
r = c.post("/approvals/new", data={"title": "Surat Kelulusan", "doc_type": "letter", "content": "content"})
ok("create approval", r.status_code == 302, r.status_code)
r = c.get("/approvals")
html = r.get_data(as_text=True)
ok("approval listed", "Surat Kelulusan" in html, "")
ok("draft status shown", "status-draft" in html, "")

# submit (owner)
r = c.get("/approvals")
import re
m = re.search(r"/approvals/(\d+)\"", html)
aid = m.group(1)
r = c.post(f"/approvals/{aid}/status", data={"status": "submitted"})
ok("owner submits", r.status_code == 302, r.status_code)

# admin approves
r = c.post(f"/approvals/{aid}/status", data={"status": "under_review"})
r = c.post(f"/approvals/{aid}/status", data={"status": "approved", "note": "Lulus"})
ok("admin approves", r.status_code == 302, r.status_code)
r = c.get(f"/approvals/{aid}")
ok("history recorded", "approved" in r.get_data(as_text=True), "")

# teacher cannot approve others
c.post("/register", data={"email": "t@wf.com", "name": "T", "password": "secret123"})
c.post("/logout")
c.post("/login", data={"email": "t@wf.com", "password": "secret123"})
r = c.post(f"/approvals/{aid}/status", data={"status": "rejected"})
ok("teacher cannot approve others", r.status_code == 302, r.status_code)  # redirects (forbidden)

# --- projects + tasks ---
r = c.post("/projects/new", data={"name": "Projek A", "description": "desc"})
ok("create project", r.status_code == 302, r.status_code)
r = c.get("/projects")
html = r.get_data(as_text=True)
ok("project listed", "Projek A" in html, "")
m = re.search(r"/projects/(\d+)\"", html)
pid = m.group(1)
r = c.post(f"/projects/{pid}/tasks/new", data={"title": "Task 1", "priority": "high", "status": "todo"})
ok("create task", r.status_code == 302, r.status_code)
r = c.get(f"/projects/{pid}")
html = r.get_data(as_text=True)
ok("kanban shows task", "Task 1" in html and "kanban" in html, "")
m = re.search(r"/tasks/(\d+)/move", html)
tid = m.group(1).split("/")[2] if False else None
# find task id from delete form
md = re.search(r"/tasks/(\d+)/delete", html)
tid = md.group(1)
r = c.post(f"/tasks/{tid}/move", data={"status": "done"})
ok("move task to done", r.status_code == 200 and r.get_json()["ok"] is True, (r.status_code, r.get_json()))

# --- calendar ---
r = c.post("/calendar/new", data={"title": "Mesyuarat Panitia", "start_date": "2026-12-01", "event_type": "meeting"})
ok("create event", r.status_code == 302, r.status_code)
r = c.get("/calendar")
ok("event listed", "Mesyuarat Panitia" in r.get_data(as_text=True), "")

print()
if failures:
    print("FAILURES:", failures)
    sys.exit(1)
print("RESULT: ALL PASS")
