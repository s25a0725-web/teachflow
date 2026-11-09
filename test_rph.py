# -*- coding: utf-8 -*-
"""Tests for the RPH document generation & export module (no external AI calls)."""
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
r = c.get("/rph/")
ok("rph page requires login", r.status_code == 302, r.status_code)

c.post("/register", data={"email": "admin@rph.com", "name": "Admin", "password": "secret123"})
c.post("/login", data={"email": "admin@rph.com", "password": "secret123"})

r = c.get("/rph/")
html = r.get_data(as_text=True)
ok("rph page renders", r.status_code == 200, r.status_code)
ok("rph form present", "f_topic" in html and "genBtn" in html, "")

# --- generate (offline fallback, since no API key) ---
payload = {
    "subject": "Matematik", "class": "Tahun 3", "topic": "Pecahan",
    "date": "2026-11-09", "day": "Isnin", "duration": "60 minit", "lang": "ms",
}
r = c.post("/rph/generate", json=payload)
j = r.get_json()
ok("generate returns rph", r.status_code == 200 and "rph" in j, (r.status_code, list(j.keys()) if isinstance(j, dict) else j))
rph = j["rph"]
ok("source is offline (no key)", j.get("source") == "offline", j.get("source"))
ok("rph has all sections", all(k in rph for k, _, _ in
    [("sk", "", "text"), ("sp", "", "text"), ("objectives", "", "list"),
     ("success_criteria", "", "list"), ("set_induksi", "", "text"),
     ("activities", "", "steps"), ("bbm", "", "list"), ("pak21", "", "text"),
     ("kbat", "", "text"), ("emk", "", "list"), ("pbd", "", "text"),
     ("remedial", "", "text"), ("enrichment", "", "text"), ("reflection", "", "text")]), rph)
ok("meta fields present", all(k in rph for k in ("school", "teacher", "subject", "class", "date", "day", "duration", "topic")), rph)
ok("objectives is list", isinstance(rph["objectives"], list) and len(rph["objectives"]) >= 1, rph["objectives"])
ok("activities is list of dicts", isinstance(rph["activities"], list) and isinstance(rph["activities"][0], dict), rph["activities"])

# --- export PDF ---
r = c.post("/rph/export", json={"rph": rph, "format": "pdf"})
ok("export pdf", r.status_code == 200 and r.data[:4] == b"%PDF", (r.status_code, r.data[:4]))

# --- export DOCX ---
r = c.post("/rph/export", json={"rph": rph, "format": "docx"})
ok("export docx", r.status_code == 200 and r.data[:2] == b"PK", (r.status_code, r.data[:2]))

# --- export rejects bad format ---
r = c.post("/rph/export", json={"rph": rph, "format": "exe"})
ok("export rejects bad format", r.status_code == 400, r.status_code)

# --- save + print view ---
r = c.post("/rph/save", json={"rph": rph})
j = r.get_json()
ok("save returns id", r.status_code == 200 and j.get("ok") is True and j.get("id"), j)
rid = j["id"]
r = c.get(f"/rph/print/{rid}")
ok("print view renders", r.status_code == 200, r.status_code)
ok("print view has content", "RANCANGAN PENGAJARAN HARIAN" in r.get_data(as_text=True), "")

# --- regenerate a section (offline fallback) ---
r = c.post("/rph/regenerate", json={"fields": payload, "rph": rph, "section": "kbat", "lang": "ms"})
j = r.get_json()
ok("regenerate section", r.status_code == 200 and j.get("ok") is True, j)

# --- ownership: other teacher can't see saved print view ---
c.post("/register", data={"email": "t2@rph.com", "name": "T2", "password": "secret123"})
c.post("/logout")
c.post("/login", data={"email": "t2@rph.com", "password": "secret123"})
r = c.get(f"/rph/print/{rid}")
ok("other teacher blocked from print view", r.status_code == 302, r.status_code)

print()
if failures:
    print("FAILURES:", failures)
    sys.exit(1)
print("RESULT: ALL PASS")
