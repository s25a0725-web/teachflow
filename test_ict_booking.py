# -*- coding: utf-8 -*-
"""Tests for Tool 1 — ICT Room Booking generator."""
import io
import json
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

# create + login a teacher
c.post("/register", data={"email": "t@x.com", "name": "Revathy", "password": "secret123"})
c.post("/login", data={"email": "t@x.com", "password": "secret123"})

# 1. page loads
r = c.get("/ict-booking/")
ok("index 200", r.status_code == 200)
ok("index has title", b"Rekod Penempahan Bilik ICT" in r.data)

# 2. autofill with natural language (offline fallback — no API key)
r = c.post("/ict-booking/autofill", json={"instruction": "Saya ingin tempah Bilik ICT 1 pada Isnin dari 10.00 pagi hingga 11.30 pagi untuk Tahun 5, tujuan akademik"})
j = r.get_json()
ok("autofill 200", r.status_code == 200)
ok("autofill returns data", isinstance(j.get("data"), dict))
d = j["data"]
ok("autofill detects room", d.get("room") == "Bilik ICT 1")
ok("autofill detects purpose", (d.get("purpose") or "").lower() == "akademik")
ok("autofill sets day", d.get("day") == "ISNIN")
ok("autofill sets start time", d.get("start_time") == "10:00")

# 3. save
r = c.post("/ict-booking/save", json={"data": d})
ok("save 200", r.status_code == 200 and r.get_json().get("ok"))

# 4. conflict detection on a second booking, same room+date+time
d2 = dict(d)
r = c.post("/ict-booking/autofill", json={"instruction": "Tempah Bilik ICT 1 pada Isnin 10.00 pagi untuk Tahun 4"})
j2 = r.get_json()
ok("conflict detected", isinstance(j2.get("conflicts"), list) and len(j2["conflicts"]) >= 1)

# 5. export PDF
r = c.post("/ict-booking/export", json={"data": d, "format": "pdf"})
ok("pdf export 200", r.status_code == 200)
ok("pdf is PDF", r.data[:4] == b"%PDF")

# 6. export DOCX
r = c.post("/ict-booking/export", json={"data": d, "format": "docx"})
ok("docx export 200", r.status_code == 200)
ok("docx is ZIP", r.data[:2] == b"PK")

# 7. date/day detection unit checks
from docgen import parse_date_day, parse_time
iso, day = parse_date_day("pada 5/6/2026")
ok("parse date dd/mm/yyyy", iso == "2026-06-05")
iso2, day2 = parse_date_day("pada Isnin")
ok("parse day word", day2 == "ISNIN")
s, e = parse_time("10.00 pagi hingga 11.30 pagi")
ok("parse times", s == "10:00" and e == "11:30")

print("RESULT:", "ALL PASS" if all(c for _, c in checks) else "FAILURES PRESENT")
