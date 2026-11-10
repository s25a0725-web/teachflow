# -*- coding: utf-8 -*-
"""Tests for Tools 3 (Duty), 4 (Assembly), 5 (ICT Loan) + e-signing."""
import base64
import os
import sys
import tempfile
from pathlib import Path

_TMP = tempfile.mkdtemp()
os.environ["TEACHFLOW_DB"] = os.path.join(_TMP, "test.db")
os.environ["TEACHFLOW_UPLOAD_ROOT"] = os.path.join(_TMP, "uploads")
os.environ["TEACHFLOW_USERS"] = os.path.join(_TMP, "users.json")
os.environ["TEACHFLOW_SECRET"] = "test-secret"
os.environ["TEACHFLOW_CSRF"] = "0"
sys.path.insert(0, str(Path(__file__).resolve().parent))

checks = []
def ok(name, cond):
    checks.append((name, bool(cond)))
    print(("OK  " if cond else "FAIL"), name)

from app import app
c = app.test_client()
c.post("/register", data={"email": "d@x.com", "name": "Guru Duty", "password": "secret123"})
c.post("/login", data={"email": "d@x.com", "password": "secret123"})

# ---- Tool 3: Duty (new layout) ----
r = c.get("/duty-report/")
ok("duty index 200", r.status_code == 200)
r = c.post("/duty-report/autofill", json={"instruction": "Hari ini Isnin. Kawasan bersih. Dua guru tidak hadir."})
ok("duty autofill", r.status_code == 200 and isinstance(r.get_json().get("data"), dict))
d = {"week": "5", "date": "2025-07-28", "day": "ISNIN", "teacher_duty_1": "Guru Duty",
     "teacher_duty_2": "Guru Lain", "teachers_absent": "2 orang",
     "facilities": {"Kantin": "Baik", "Padang": "Baik"}, "remarks": "Baik"}
r = c.post("/duty-report/save", json={"data": d})
ok("duty save", r.status_code == 200 and r.get_json().get("ok"))
r = c.post("/duty-report/export", json={"data": d, "format": "pdf"})
ok("duty pdf", r.status_code == 200 and r.data[:4] == b"%PDF")
r = c.post("/duty-report/export", json={"data": d, "format": "docx"})
ok("duty docx", r.status_code == 200 and r.data[:2] == b"PK")

# ---- Tool 4: Assembly (new layout) ----
r = c.get("/assembly-report/")
ok("assembly index 200", r.status_code == 200)
r = c.post("/assembly-report/autofill", json={"instruction": "Perhimpunan Minggu 5, Negaraku dan lagu negeri, ucapan Guru Besar"})
ok("assembly autofill", r.status_code == 200 and isinstance(r.get_json().get("data"), dict))
a = {"week": "5", "date": "2025-07-28", "day": "ISNIN", "teacher_speech": "Guru A",
     "teacher_duty_1": "Guru Duty", "teacher_duty_2": "Guru Lain", "topic": "Kebersihan Diri",
     "agenda": ["Lagu Negaraku", "Lagu Negeri", "Ucapan Guru Besar"],
     "headteacher_speech": "Kebersihan diri"}
r = c.post("/assembly-report/save", json={"data": a})
ok("assembly save", r.status_code == 200 and r.get_json().get("ok"))
r = c.post("/assembly-report/export", json={"data": a, "format": "pdf"})
ok("assembly pdf", r.status_code == 200 and r.data[:4] == b"%PDF")
r = c.post("/assembly-report/export", json={"data": a, "format": "docx"})
ok("assembly docx", r.status_code == 200 and r.data[:2] == b"PK")

# ---- Tool 5: Loan (new Bahagian A/B layout) ----
r = c.get("/ict-loan/")
ok("loan index 200", r.status_code == 200)
r = c.post("/ict-loan/inventory", json={"name": "Laptop HP", "category": "Laptop", "serial_no": "HP123"})
ok("inventory add forbidden for teacher", r.status_code == 403)
r = c.post("/ict-loan/autofill", json={"instruction": "Pinjam laptop untuk Tahun 5 pada Isnin"})
ok("loan autofill", r.status_code == 200 and isinstance(r.get_json().get("data"), dict))
l = {"teacher_name": "Guru Duty", "equipment_name": "Laptop HP", "category": "Laptop",
     "serial_no": "HP123", "quantity": 1, "borrow_date": "2025-07-28", "purpose": "Pengajaran",
     "witness": "Saksi A", "return_date": "", "status": "Dipinjam"}
r = c.post("/ict-loan/save", json={"data": l})
ok("loan save", r.status_code == 200 and r.get_json().get("ok"))
r = c.post("/ict-loan/export", json={"data": l, "format": "pdf"})
ok("loan pdf", r.status_code == 200 and r.data[:4] == b"%PDF")
r = c.post("/ict-loan/export", json={"data": l, "format": "docx"})
ok("loan docx", r.status_code == 200 and r.data[:2] == b"PK")

# ---- E-signing (shared) ----
from PIL import Image as _PILImage
import io as _io
_buf = _io.BytesIO()
_PILImage.new("RGB", (8, 8), (0, 0, 0)).save(_buf, "PNG")
PNG = "data:image/png;base64," + base64.b64encode(_buf.getvalue()).decode()
r = c.post("/esig/save", json={"tool": "duty", "role": "disemak", "type": "draw", "signature": PNG})
ok("esig draw save", r.status_code == 200 and r.get_json().get("ok") and r.get_json().get("file"))
r = c.post("/esig/save", json={"tool": "duty", "role": "disahkan", "type": "typed", "signer_name": "Guru Besar"})
ok("esig typed save", r.status_code == 200 and r.get_json().get("ok"))
r = c.get("/esig/list")
ok("esig list", r.status_code == 200 and len(r.get_json().get("signatures", [])) >= 2)

# ---- E-signature embedding in PDF ----
r0 = c.post("/esig/save", json={"tool": "duty", "role": "disemak", "type": "draw", "signature": PNG})
fname = r0.get_json()["file"]
d_signed = dict(d)
d_signed["signatures"] = {"disemak": {"type": "draw", "file": fname}, "disahkan": {"type": "typed", "signer_name": "Guru Besar"}}
r = c.post("/duty-report/export", json={"data": d_signed, "format": "pdf"})
ok("duty pdf with signature", r.status_code == 200 and r.data[:4] == b"%PDF")

print("RESULT:", "ALL PASS" if all(c for _, c in checks) else "FAILURES PRESENT")
