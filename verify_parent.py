# -*- coding: utf-8 -*-
"""Verify parent login by student IC number."""
import os
import tempfile

os.chdir(os.path.dirname(os.path.abspath(__file__)))
os.environ["TEACHFLOW_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")
os.environ["TEACHFLOW_UPLOAD_ROOT"] = tempfile.mkdtemp()

from app import app  # noqa: E402

c = app.test_client()

# Teacher adds a student with an IC number (no parent email needed)
c.post("/register", data={"email": "t@x.com", "name": "Teacher", "password": "secret123"})
c.post("/login", data={"email": "t@x.com", "password": "secret123"})
c.post("/classes", data={"action": "add_class", "name": "1A", "subject": "Math", "grade": "1"})
c.post("/classes", data={"action": "add_student", "class_id": "1", "name": "Ali", "parent_name": "Parent", "ic_number": "900101-01-5555"})
c.post("/logout")

# Parent registers with IC number only (no email)
print("parent-register (IC):", c.post("/parent-register", data={
    "name": "Parent", "ic_number": "900101-01-5555", "email": "", "password": "secret123"}, follow_redirects=True).status_code)

# Parent logs in with IC number
r = c.post("/parent-login", data={"identifier": "900101-01-5555", "password": "secret123"}, follow_redirects=True)
print("parent-login (IC):", r.status_code)

r = c.get("/parent")
print("parent dashboard:", r.status_code, "| shows child 'Ali':", b"Ali" in r.data)
assert r.status_code == 200 and b"Ali" in r.data

print("\nIC LOGIN OK")
