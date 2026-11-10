# -*- coding: utf-8 -*-
"""Tests for Tool 2 — Co-curricular Activity Report generator."""
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
c.post("/register", data={"email": "k@x.com", "name": "Guru Koko", "password": "secret123"})
c.post("/login", data={"email": "k@x.com", "password": "secret123"})

r = c.get("/kokurikulum/")
ok("index 200", r.status_code == 200)
ok("index title", b"Laporan Bergambar Unit Kokurikulum" in r.data)

r = c.post("/kokurikulum/autofill", json={"instruction": "Jana laporan kelab bola sepak, latihan Rabu di padang sekolah"})
j = r.get_json()
ok("autofill 200", r.status_code == 200)
ok("autofill data", isinstance(j.get("data"), dict))

d = {"program": "Kelab Bola Sepak", "tempat": "Padang Sekolah", "tarikh": "2025-07-30",
     "sasaran": "Murid", "objektif": ["Meningkatkan kemahiran", "Memupuk disiplin"],
     "aktiviti": ["Latihan hantaran", "Latihan tendangan"], "penilaian": ["Baik"],
     "analisis": ["Prestasi baik"], "keberhasilan": ["Berjaya"], "cadangan": ["Lebih kerap"],
     "photos": [], "disediakan_nama": "Guru Koko", "disahkan_nama": "Guru Besar"}

r = c.post("/kokurikulum/save", json={"data": d})
ok("save 200", r.status_code == 200 and r.get_json().get("ok"))

r = c.post("/kokurikulum/export", json={"data": d, "format": "pdf"})
ok("pdf export 200", r.status_code == 200)
ok("pdf is PDF", r.data[:4] == b"%PDF")

r = c.post("/kokurikulum/export", json={"data": d, "format": "docx"})
ok("docx export 200", r.status_code == 200)
ok("docx is ZIP", r.data[:2] == b"PK")

print("RESULT:", "ALL PASS" if all(c for _, c in checks) else "FAILURES PRESENT")
