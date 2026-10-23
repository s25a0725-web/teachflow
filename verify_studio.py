# -*- coding: utf-8 -*-
"""Verify Document Studio: build, create, export, ai-fix, convert, templates."""
import io
import os
import tempfile
from pathlib import Path

os.chdir(os.path.dirname(os.path.abspath(__file__)))
os.environ["TEACHFLOW_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")
os.environ["TEACHFLOW_UPLOAD_ROOT"] = tempfile.mkdtemp()

from docbuild import (generate_content, build_docx, build_pptx, build_pdf,  # noqa: E402
                      convert_file, content_to_text, parse_content_text, extract_placeholders)
from app import app  # noqa: E402

d = Path(tempfile.mkdtemp())

# Build DOCX/PPTX/PDF
content = generate_content("Notis Mesyuarat", "docx", "ms", "")
assert content["title"] and content["sections"]
for fn in [build_docx, build_pptx, build_pdf]:
    out = d / ("x." + fn.__name__.split("_")[1])
    fn(content, out)
    assert out.exists() and out.stat().st_size > 0
print("build docx/pptx/pdf OK")

# Text roundtrip
c2 = parse_content_text(content_to_text(content))
assert c2["title"] == content["title"] and c2["sections"]
print("parse roundtrip OK")

# Convert txt -> pdf (offline)
p = d / "note.txt"
p.write_text("hello world\n" * 20, encoding="utf-8")
out, _ = convert_file(p, "note.txt", "pdf")
assert out.endswith(".pdf")
print("txt->pdf convert OK")

# Studio routes
c = app.test_client()
c.post("/register", data={"email": "t@x.com", "name": "T", "password": "secret123"})
c.post("/login", data={"email": "t@x.com", "password": "secret123"})
assert c.get("/studio").status_code == 200
r = c.post("/studio/create", data={"topic": "Notis", "doc_type": "docx", "lang": "ms", "instructions": ""})
d = r.get_json()
assert d["link"] and d["text"]
print("studio create OK:", d["link"])
r = c.post("/studio/export", json={"text": d["text"], "doc_type": "pdf"})
assert r.get_json()["link"]
print("studio export OK")
r = c.post("/studio/ai-fix", json={"text": "hello", "instruction": "simpler", "lang": "en"})
assert r.get_json()["note"] == "no_ai"
print("studio ai-fix (no key -> note) OK")
r = c.post("/studio/convert", data={"file": (io.BytesIO(b"hello"), "a.txt"), "target": "pdf"},
           content_type="multipart/form-data")
assert r.get_json().get("link")
print("studio convert OK")

print("\nSTUDIO OK")
