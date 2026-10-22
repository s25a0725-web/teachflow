# -*- coding: utf-8 -*-
"""End-to-end smoke test through Flask's test client."""
import base64
import io
import os
import tempfile

os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Isolate test data from any real database / uploads so it never touches user data.
os.environ["TEACHFLOW_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["TEACHFLOW_UPLOAD_ROOT"] = tempfile.mkdtemp()

from app import app  # noqa: E402
from db import get_db  # noqa: E402

c = app.test_client()
ok = True


def check(name, resp, expect=200):
    global ok
    status = resp.status_code
    flag = "OK " if status == expect else "FAIL"
    if status != expect:
        ok = False
    print(f"[{flag}] {name}: {status} (expect {expect})")


# Auth
check("register", c.post("/register", data={
    "email": "teacher@test.com", "name": "Cikgu Amin", "password": "secret123"}, follow_redirects=True))
check("login", c.post("/login", data={
    "email": "teacher@test.com", "password": "secret123"}, follow_redirects=True))

# Dashboard
check("dashboard", c.get("/"))

# Lesson plan
check("lesson-plan", c.post("/lesson-plans", data={
    "topic": "Photosynthesis", "subject": "Science", "grade": "Form 2",
    "duration": "60", "lp_lang": "en"}, follow_redirects=True))
check("lesson-plan-ms", c.post("/lesson-plans", data={
    "topic": "Fotosintesis", "subject": "Sains", "grade": "Tingkatan 2",
    "duration": "60", "lp_lang": "ms"}, follow_redirects=True))

# Quiz
check("quiz", c.post("/quizzes", data={
    "topic": "Algebra", "subject": "Mathematics", "grade": "Form 1",
    "num": "5", "difficulty": "easy", "qz_lang": "en"}, follow_redirects=True))
check("quiz-ms", c.post("/quizzes", data={
    "topic": "Fotosintesis", "subject": "Sains", "grade": "Tingkatan 1",
    "num": "3", "difficulty": "medium", "qz_lang": "ms"}, follow_redirects=True))

# Classes + students
check("add-class", c.post("/classes", data={
    "action": "add_class", "name": "2 Mawar", "subject": "Science", "grade": "Form 2"}, follow_redirects=True))
check("add-student", c.post("/classes", data={
    "action": "add_student", "class_id": "1", "name": "Ali bin Abu",
    "parent_name": "Abu", "parent_email": "abu@example.com"}, follow_redirects=True))

# Grading
check("new-assignment", c.post("/grading/new", data={
    "title": "Test 1", "class_id": "1", "total_marks": "100", "description": "Topic 1"}, follow_redirects=True))
check("grade-assignment", c.post("/grading/1", data={
    "marks_1": "85", "feedback_1": ""}, follow_redirects=True))

# Attendance
check("attendance", c.post("/attendance", data={
    "class_id": "1", "date": "2026-10-22", "status_1": "present"}, follow_redirects=True))
check("attendance-time", c.post("/attendance", data={
    "class_id": "1", "date": "2026-10-22", "status_1": "late", "time_1": "08:30"}, follow_redirects=True))
# Teacher (staff) attendance — first user is admin, sees the roster
check("teacher-attendance", c.post("/teacher-attendance", data={
    "date": "2026-10-22", "status_1": "present", "time_1": "07:45"}, follow_redirects=True))

# Timetable
check("timetable", c.post("/timetable", data={
    "day": "0", "period": "1", "subject": "Science", "class_name": "2 Mawar"}, follow_redirects=True))

# Reports
check("reports", c.get("/reports?student_id=1"))
check("parents-generate", c.post("/parents", data={
    "action": "generate", "student_id": "1"}, follow_redirects=True))

# Documents: upload any file type (a .txt here)
check("upload-txt", c.post("/documents", data={
    "file": (io.BytesIO(b"Photosynthesis is the process by which plants make food. "
                        b"Plants use sunlight, water and carbon dioxide. "
                        b"This process produces oxygen and glucose. "
                        b"It happens in the leaves. Chlorophyll captures the light. "
                        b"Photosynthesis is essential for life on Earth."), "notes.txt"),
    "title": "Science Notes", "folder_id": ""}, content_type="multipart/form-data", follow_redirects=True))

check("summarize", c.post("/documents/1/summarize", follow_redirects=True))
check("edit", c.post("/documents/1/edit", data={"text": "edited content here"}, follow_redirects=True))
check("folder-new", c.post("/folders/new", data={"name": "Admin"}, follow_redirects=True))
check("request-signature", c.post("/documents/1/request-signature", data={
    "signer_name": "Parent A", "signer_email": "p@example.com"}, follow_redirects=True))

# Public sign flow
db = get_db()
row = db.execute("SELECT token FROM sign_requests ORDER BY id DESC LIMIT 1").fetchone()
db.close()
token = row["token"]
check("public-sign-get", c.get(f"/sign/{token}"))
png = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * 40).decode()
check("public-sign-post", c.post(f"/sign/{token}", data={
    "signature": "data:image/png;base64," + png, "signer_name": "Parent A"}, follow_redirects=True))

# Language toggle
check("lang-toggle", c.get("/lang/ms", follow_redirects=True))

# Verify time was persisted
db = get_db()
t_att = db.execute("SELECT status, time FROM teacher_attendance").fetchall()
s_row = db.execute("SELECT status, time FROM attendance LIMIT 1").fetchone()
db.close()
print("teacher_attendance:", [(r["status"], r["time"]) for r in t_att])
print("student attendance time:", (s_row["status"], s_row["time"]) if s_row else None)

print("\nRESULT:", "ALL PASS" if ok else "SOME FAILED")
