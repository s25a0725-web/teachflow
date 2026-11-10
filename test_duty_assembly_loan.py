# -*- coding: utf-8 -*-
"""Tests for Tools 3 (Duty), 4 (Assembly), 5 (ICT Loan)."""
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

# ---- Tool 3: Duty ----
r = c.get("/duty-report/")
ok("duty index 200", r.status_code == 200)
r = c.post("/duty-report/autofill", json={"instruction": "Hari ini Isnin. Kawasan bersih. Dua guru tidak hadir."})
ok("duty autofill", r.status_code == 200 and isinstance(r.get_json().get("data"), dict))
d = {"week": "5", "date": "2025-07-28", "day": "ISNIN", "teacher_duty": "Guru Duty",
     "teachers_absent": "2 orang", "cleanliness": "Bersih"}
r = c.post("/duty-report/save", json={"data": d})
ok("duty save", r.status_code == 200 and r.get_json().get("ok"))
r = c.post("/duty-report/export", json={"data": d, "format": "pdf"})
ok("duty pdf", r.status_code == 200 and r.data[:4] == b"%PDF")
r = c.post("/duty-report/export", json={"data": d, "format": "docx"})
ok("duty docx", r.status_code == 200 and r.data[:2] == b"PK")

# ---- Tool 4: Assembly ----
r = c.get("/assembly-report/")
ok("assembly index 200", r.status_code == 200)
r = c.post("/assembly-report/autofill", json={"instruction": "Perhimpunan Minggu 5, Negaraku dan lagu negeri, ucapan Guru Besar"})
ok("assembly autofill", r.status_code == 200 and isinstance(r.get_json().get("data"), dict))
a = {"week": "5", "date": "2025-07-28", "day": "ISNIN", "venue": "Dewan",
     "negaraku": "Dinyanyikan", "headteacher_speech": "Kebersihan diri"}
r = c.post("/assembly-report/save", json={"data": a})
ok("assembly save", r.status_code == 200 and r.get_json().get("ok"))
r = c.post("/assembly-report/export", json={"data": a, "format": "pdf"})
ok("assembly pdf", r.status_code == 200 and r.data[:4] == b"%PDF")
r = c.post("/assembly-report/export", json={"data": a, "format": "docx"})
ok("assembly docx", r.status_code == 200 and r.data[:2] == b"PK")

# ---- Tool 5: Loan + inventory ----
r = c.get("/ict-loan/")
ok("loan index 200", r.status_code == 200)
# inventory add requires admin; current user is teacher -> 403
r = c.post("/ict-loan/inventory", json={"name": "Laptop HP", "category": "Laptop", "serial_no": "HP123"})
ok("inventory add forbidden for teacher", r.status_code == 403)
r = c.post("/ict-loan/autofill", json={"instruction": "Pinjam laptop untuk Tahun 5 pada Isnin"})
ok("loan autofill", r.status_code == 200 and isinstance(r.get_json().get("data"), dict))
l = {"teacher_name": "Guru Duty", "equipment_name": "Laptop HP", "category": "Laptop",
     "serial_no": "HP123", "quantity": 1, "borrow_date": "2025-07-28", "purpose": "Pengajaran",
     "expected_return": "2025-08-01", "status": "Dipinjam"}
r = c.post("/ict-loan/save", json={"data": l})
ok("loan save", r.status_code == 200 and r.get_json().get("ok"))
r = c.post("/ict-loan/export", json={"data": l, "format": "pdf"})
ok("loan pdf", r.status_code == 200 and r.data[:4] == b"%PDF")
r = c.post("/ict-loan/export", json={"data": l, "format": "docx"})
ok("loan docx", r.status_code == 200 and r.data[:2] == b"PK")

print("RESULT:", "ALL PASS" if all(c for _, c in checks) else "FAILURES PRESENT")
