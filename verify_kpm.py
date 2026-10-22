# -*- coding: utf-8 -*-
"""Quick content verification for KPM-style quiz + trilingual generators + doc delete."""
import io
import os
import tempfile

os.chdir(os.path.dirname(os.path.abspath(__file__)))
os.environ["TEACHFLOW_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")
os.environ["TEACHFLOW_UPLOAD_ROOT"] = tempfile.mkdtemp()

from generators import generate_quiz, lesson_plan  # noqa: E402
from app import app  # noqa: E402

print("=== Math objective (EN) ===")
for q in generate_quiz("Mathematics", "Algebra", "Form 1", 3, "easy", "en", "objective"):
    print(" Q:", q["q"], "| opts:", q["options"], "| ans:", q["a"])
    assert q["type"] == "obj" and len(q["options"]) == 4 and q["a"] in q["options"]

print("\n=== Science structured (MS) ===")
for q in generate_quiz("Sains", "Fotosintesis", "Tingkatan 1", 3, "medium", "ms", "subjective"):
    print(" Q:", q["q"])
    print("   model:", q["a"])
    assert q["type"] == "sub"

print("\n=== Science structured (TA - Tamil) ===")
for q in generate_quiz("Science", "Photosynthesis", "Form 1", 3, "medium", "ta", "subjective"):
    print(" Q:", q["q"])
    print("   model:", q["a"])

print("\n=== Lesson plan (TA) first 200 chars ===")
lp = lesson_plan("Fotosintesis", "Sains", "Tingkatan 2", 60, "ta")
print(lp[:200].replace("\n", " | "))

print("\n=== Document delete round-trip ===")
c = app.test_client()
c.post("/register", data={"email": "d@test.com", "name": "D", "password": "secret123"})
c.post("/login", data={"email": "d@test.com", "password": "secret123"})
c.post("/documents", data={"file": (io.BytesIO(b"hello world"), "a.txt"), "title": "A", "folder_id": ""},
       content_type="multipart/form-data")
from db import get_db
db = get_db()
before = db.execute("SELECT COUNT(*) c FROM documents").fetchone()["c"]
db.close()
r = c.post("/documents/1/delete", follow_redirects=True)
db = get_db()
after = db.execute("SELECT COUNT(*) c FROM documents").fetchone()["c"]
db.close()
print("status:", r.status_code, "| docs before:", before, "after:", after)
assert r.status_code == 200 and after == before - 1

print("\nALL CONTENT CHECKS PASS")
