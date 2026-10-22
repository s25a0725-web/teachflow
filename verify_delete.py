# -*- coding: utf-8 -*-
"""Verify delete actions cascade correctly across modules."""
import os
import tempfile

os.chdir(os.path.dirname(os.path.abspath(__file__)))
os.environ["TEACHFLOW_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")
os.environ["TEACHFLOW_UPLOAD_ROOT"] = tempfile.mkdtemp()

from app import app  # noqa: E402
from db import get_db  # noqa: E402

c = app.test_client()
c.post("/register", data={"email": "a@x.com", "name": "A", "password": "secret123"})
c.post("/login", data={"email": "a@x.com", "password": "secret123"})

c.post("/classes", data={"action": "add_class", "name": "1A", "subject": "Math", "grade": "1"})
c.post("/classes", data={"action": "add_student", "class_id": "1", "name": "S1", "parent_name": "P", "parent_email": "p@x.com"})
c.post("/grading/new", data={"title": "T", "class_id": "1", "total_marks": "10"})
c.post("/lesson-plans", data={"topic": "X", "subject": "Y", "grade": "1", "duration": "60", "lp_lang": "en"})
c.post("/quizzes", data={"topic": "X", "subject": "Mathematics", "grade": "1", "num": "2", "difficulty": "easy", "qz_lang": "en", "qz_type": "objective"})

db = get_db()
before = {t: db.execute(f"SELECT COUNT(*) c FROM {t}").fetchone()["c"]
          for t in ["classes", "students", "assignments", "lesson_plans", "quizzes"]}
db.close()
print("before:", before)

c.post("/students/1/delete")
c.post("/classes/1/delete")
c.post("/lesson-plans/1/delete")
c.post("/quizzes/1/delete")
c.post("/grading/1/delete")

db = get_db()
after = {t: db.execute(f"SELECT COUNT(*) c FROM {t}").fetchone()["c"]
         for t in ["classes", "students", "assignments", "submissions", "lesson_plans", "quizzes"]}
db.close()
print("after:", after)
assert all(v == 0 for v in after.values()), "delete cascade failed"
print("\nDELETE OK")
