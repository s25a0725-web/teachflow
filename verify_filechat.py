# -*- coding: utf-8 -*-
"""Verify chatbox file upload + conversion."""
import io
import os
import tempfile
import zipfile
from pathlib import Path

os.chdir(os.path.dirname(os.path.abspath(__file__)))
os.environ["TEACHFLOW_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")
os.environ["TEACHFLOW_UPLOAD_ROOT"] = tempfile.mkdtemp()

from PIL import Image  # noqa: E402
from file_assistant import convert  # noqa: E402
from app import app  # noqa: E402

d = Path(tempfile.mkdtemp())

# txt -> pdf
p = d / "note.txt"
p.write_text(("Line one\n" + "Line two line two line two\n") * 30, encoding="utf-8")
out, mime = convert(p, "note.txt", "pdf")
print("txt->pdf:", out, mime)
assert out and out.endswith(".pdf") and mime == "application/pdf"

# image -> pdf
ip = d / "pic.png"
Image.new("RGB", (120, 90), "red").save(ip)
out2, mime2 = convert(ip, "pic.png", "pdf")
print("image->pdf:", out2, mime2)
assert out2 and out2.endswith(".pdf")

# docx -> txt
docx = d / "d.docx"
xml = ('<?xml version="1.0"?>'
       '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
       '<w:body><w:p><w:r><w:t>Hello world</w:t></w:r></w:p></w:body></w:document>')
with zipfile.ZipFile(docx, "w") as z:
    z.writestr("word/document.xml", xml)
out3, mime3 = convert(docx, "d.docx", "txt")
print("docx->txt:", out3, mime3)
assert out3 and out3.endswith(".txt")

# upload route: save + organise by department + convert
c = app.test_client()
c.post("/register", data={"email": "t@x.com", "name": "T", "password": "secret123"})
c.post("/login", data={"email": "t@x.com", "password": "secret123"})
c.post("/classes", data={"action": "add_class", "name": "1A", "subject": "Science", "grade": "1"})
r = c.post("/chatbot/upload", data={
    "file": (io.BytesIO(b"science notes here"), "notes.txt"),
    "message": "convert to pdf Science",
}, content_type="multipart/form-data")
data = r.get_json()
print("upload reply:", data["reply"])
print("upload link:", data["link"])
assert data["reply"] and data["link"]

print("\nFILECHAT OK")
