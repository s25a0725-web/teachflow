# -*- coding: utf-8 -*-
"""Sample the UASA question bank across subjects."""
import os
import tempfile

os.environ["TEACHFLOW_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")
os.environ["TEACHFLOW_UPLOAD_ROOT"] = tempfile.mkdtemp()

from generators import generate_quiz  # noqa: E402

print("=== Science objective (MS) ===")
for q in generate_quiz("Sains", "Fotosintesis", "Tingkatan 1", 3, "easy", "ms", "objective"):
    print(" ", q["q"], "=>", q["a"])
    assert q["type"] == "obj" and q["a"] in q["options"]

print("\n=== Sejarah objective (EN) ===")
for q in generate_quiz("Sejarah", "Melaka", "Tingkatan 1", 3, "easy", "en", "objective"):
    print(" ", q["q"], "=>", q["a"])

print("\n=== Bahasa Melayu objective (kata nama) ===")
for q in generate_quiz("Bahasa Melayu", "kata nama", "Tingkatan 1", 2, "easy", "ms", "objective"):
    print(" ", q["q"], "=>", q["a"])

print("\n=== English objective (grammar) ===")
for q in generate_quiz("English", "grammar", "Form 1", 2, "easy", "en", "objective"):
    print(" ", q["q"], "=>", q["a"])

print("\n=== Science mixed (jirim, MS) ===")
for q in generate_quiz("Sains", "jirim", "Tingkatan 1", 4, "medium", "ms", "mixed"):
    print(" ", q["type"], "|", q["q"], "=>", q["a"])

print("\nBANK OK")
