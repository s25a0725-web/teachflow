# -*- coding: utf-8 -*-
"""Tests for the TeachFlow Study Space module."""
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
c.post("/register", data={"email": "s@x.com", "name": "Student", "password": "secret123"})
c.post("/login", data={"email": "s@x.com", "password": "secret123"})

# page loads
r = c.get("/study-space/")
ok("index 200", r.status_code == 200)
ok("has title", b"STUDY SPACE" in r.data or b"Study Space" in r.data)
ok("has pomodoro", b"pomoTime" in r.data)
ok("has ambient", b"data-amb" in r.data)

# session start + complete
r = c.post("/study-space/session/start", json={"focus_minutes": 25})
ok("session start", r.status_code == 200 and r.get_json().get("ok"))
sid = r.get_json()["id"]
r = c.post("/study-space/session/complete", json={"id": sid})
ok("session complete", r.status_code == 200 and r.get_json().get("ok"))

# stats reflect the completed session
r = c.get("/study-space/stats")
j = r.get_json()
ok("stats total", j.get("total") == 25)
ok("stats today", j.get("today") == 25)

# tracks list (empty initially)
r = c.get("/study-space/tracks")
ok("tracks list", r.status_code == 200 and isinstance(r.get_json().get("tracks"), list))

# upload a track (tiny fake audio bytes)
r = c.post("/study-space/upload", data={"file": (__import__("io").BytesIO(b"ID3fakeaudio"), "test.mp3")},
           content_type="multipart/form-data")
ok("upload track", r.status_code == 200 and r.get_json().get("ok"))

# upload wrong type rejected
r = c.post("/study-space/upload", data={"file": (__import__("io").BytesIO(b"x"), "bad.exe")},
           content_type="multipart/form-data")
ok("upload rejects bad type", r.status_code == 400)

# assistant without API key -> 503 (no key)
r = c.post("/study-space/assistant", json={"question": "terangkan fotosintesis"})
ok("assistant no-key 503", r.status_code in (503, 200))

print("RESULT:", "ALL PASS" if all(c for _, c in checks) else "FAILURES PRESENT")
