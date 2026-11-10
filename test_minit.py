# -*- coding: utf-8 -*-
"""Tests for the Minit Curai generation & export module (no external AI calls)."""
import io
import json
import os
import sys
import tempfile

os.environ["TEACHFLOW_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")
os.environ["TEACHFLOW_UPLOAD_ROOT"] = tempfile.mkdtemp()
os.environ["TEACHFLOW_USERS"] = os.path.join(tempfile.mkdtemp(), "u.json")
os.environ["TEACHFLOW_SECRET"] = "test"
os.environ["TEACHFLOW_CSRF"] = "0"
for k in ("DEEPSEEK_API_KEY", "TEACHFLOW_AI_KEY", "OPENAI_API_KEY"):
    os.environ.pop(k, None)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import app

failures = []


def ok(name, cond, detail=""):
    print(("OK    " if cond else "FAIL  ") + name + (("  -> " + str(detail)) if detail and not cond else ""))
    if not cond:
        failures.append(name)


c = app.test_client()

# --- auth guard ---
r = c.get("/minit-curai/")
ok("minit page requires login", r.status_code == 302, r.status_code)

c.post("/register", data={"email": "admin@mc.com", "name": "Admin", "password": "secret123"})
c.post("/login", data={"email": "admin@mc.com", "password": "secret123"})

r = c.get("/minit-curai/")
html = r.get_data(as_text=True)
ok("minit page renders", r.status_code == 200, r.status_code)
ok("minit form present", "f_perkara" in html and "genBtn" in html, "")

# --- generate (offline fallback) ---
payload = {
    "school_name": "SJK(T) Sepang", "school_name_en": "SEK.JEN.KEB (TAMIL) SEPANG",
    "school_address": "43900 SEPANG",
    "perkara": "Taklimat Pelaksanaan Trace and Track 2M",
    "jenis": "Taklimat", "unit": "Kurikulum",
    "nama_pegawai": "M KALIAPPAN MUNIANDY", "jawatan": "Ketua Panitia",
    "tarikh": "5/6/2026", "masa": "11.00 Pagi - 1.30 Petang",
    "tempat": "Google Meet", "penganjur": "PPD Sepang",
    "kehadiran": "Md Faizal, Mohd Yuzuf Hanif",
    "makluman": "Semua Guru dan Ahli Panitia Bahasa Melayu",
    "isu": "Kelebihan Trace and Track\nPenggunaan bahan modul\nSistem semakan digital",
    "tindakan": "Ketua Panitia membentuk unit pemulihan khas",
    "bahan": "Tiada",
}
r = c.post("/minit-curai/generate", json=payload)
j = r.get_json()
ok("generate returns minit", r.status_code == 200 and "minit" in j, (r.status_code, list(j.keys()) if isinstance(j, dict) else j))
minit = j["minit"]
ok("source is offline (no key)", j.get("source") == "offline", j.get("source"))
ok("isu is a list", isinstance(minit["isu"], list) and len(minit["isu"]) >= 1, minit["isu"])
ok("tindakan is a list", isinstance(minit["tindakan"], list), minit["tindakan"])
ok("meta fields preserved", minit["perkara"] == payload["perkara"] and minit["nama_pegawai"] == payload["nama_pegawai"], minit)

# --- export PDF ---
r = c.post("/minit-curai/export", json={"minit": minit, "format": "pdf"})
ok("export pdf", r.status_code == 200 and r.data[:4] == b"%PDF", (r.status_code, r.data[:4]))

# --- export DOCX ---
r = c.post("/minit-curai/export", json={"minit": minit, "format": "docx"})
ok("export docx", r.status_code == 200 and r.data[:2] == b"PK", (r.status_code, r.data[:2]))

# --- export rejects bad format ---
r = c.post("/minit-curai/export", json={"minit": minit, "format": "exe"})
ok("export rejects bad format", r.status_code == 400, r.status_code)

# --- photo upload ---
good = c.post("/minit-curai/photo", data={"file": (io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"x" * 40), "photo.png")},
              content_type="multipart/form-data")
ok("photo upload ok", good.status_code == 200 and good.get_json().get("name"), good.get_json())
bad = c.post("/minit-curai/photo", data={"file": (io.BytesIO(b"x"), "evil.exe")},
             content_type="multipart/form-data")
ok("photo upload rejects bad type", bad.status_code == 400, bad.status_code)

# --- save ---
r = c.post("/minit-curai/save", json={"minit": minit})
j = r.get_json()
ok("save returns id", r.status_code == 200 and j.get("ok") is True and j.get("id"), j)

print()
if failures:
    print("FAILURES:", failures)
    sys.exit(1)
print("RESULT: ALL PASS")
