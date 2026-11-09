# -*- coding: utf-8 -*-
"""Tests for the AI Teacher Assistant module (no external API calls)."""
import io
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
r = c.get("/ai/")
ok("ai page requires login", r.status_code == 302, r.status_code)

# --- register + login (first user = admin) ---
c.post("/register", data={"email": "admin@ai.com", "name": "Admin", "password": "secret123"})
c.post("/login", data={"email": "admin@ai.com", "password": "secret123"})

r = c.get("/ai/")
html = r.get_data(as_text=True)
ok("ai page renders", r.status_code == 200, r.status_code)
ok("ai app present", "ai-app" in html)
ok("tools injected", "Lesson Planner" in html)

# --- regression: every el.<name> referenced via addEventListener must be defined in the el map ---
import re
_m = re.search(r'<script>\s*(\(function.*?)</script>', html, re.S)
_script = _m.group(1) if _m else ""
_defined = set(re.findall(r'\b(\w+):\s*\$\(', _script))
_used = set(re.findall(r'el\.(\w+)\.addEventListener', _script))
_missing = _used - _defined
ok("every el.* element is mapped (no missing DOM refs)", not _missing, _missing)
ok("newChatBtn mapped", "newChatBtn" in _defined)

r = c.get("/ai/api/status").get_json()
ok("status not configured without key", r["configured"] is False, r)

r = c.get("/ai/api/conversations").get_json()
ok("conversations empty initially", r == [], r)

# --- conversation CRUD ---
r = c.post("/ai/api/conversations").get_json()
cid = r["id"]
ok("new conversation created", cid is not None, r)

r = c.get("/ai/api/conversations").get_json()
ok("conversation listed", len(r) == 1 and r[0]["id"] == cid, r)

r = c.post(f"/ai/api/conversations/{cid}", json={"title": "My lesson"})
ok("rename conversation", r.get_json() == {"ok": True}, r.get_json())

r = c.get(f"/ai/api/conversations/{cid}/messages").get_json()
ok("messages empty for new conv", r == [], r)

# --- message update (editable results) with ownership scoping ---
from db import get_db
_db = get_db()
_db.execute("INSERT INTO ai_messages (conversation_id, role, content, tool) VALUES (?,?,?,?)", (cid, "assistant", "draft answer", "chat"))
_db.commit()
mid = _db.execute("SELECT MAX(id) AS id FROM ai_messages").fetchone()["id"]
_db.close()
r = c.post(f"/ai/api/messages/{mid}", json={"content": "edited answer"})
ok("update own message", r.get_json() == {"ok": True}, r.get_json())
r = c.get(f"/ai/api/conversations/{cid}/messages").get_json()
ok("edited content persisted", r and r[0]["content"] == "edited answer", r)
r = c.post("/ai/api/messages/999999", json={"content": "x"})
ok("update missing message -> 404", r.status_code == 404, r.status_code)

# --- feedback (like / dislike) ---
r = c.post(f"/ai/api/messages/{mid}/feedback", json={"feedback": "like"})
ok("feedback like saved", r.get_json() == {"ok": True, "feedback": "like"}, r.get_json())
r = c.get(f"/ai/api/conversations/{cid}/messages").get_json()
ok("feedback persisted in history", r and r[0]["feedback"] == "like", r)
r = c.post(f"/ai/api/messages/{mid}/feedback", json={"feedback": "dislike"})
ok("feedback changed to dislike", r.get_json()["feedback"] == "dislike", r.get_json())
r = c.post(f"/ai/api/messages/{mid}/feedback", json={"feedback": None})
ok("feedback cleared", r.get_json()["feedback"] is None, r.get_json())
r = c.post(f"/ai/api/messages/{mid}/feedback", json={"feedback": "bad"})
ok("feedback rejects invalid value", r.status_code == 400, r.status_code)
r = c.post("/ai/api/messages/999999/feedback", json={"feedback": "like"})
ok("feedback on missing message -> 404", r.status_code == 404, r.status_code)

# --- chat blocked without key ---
r = c.post("/ai/api/chat", json={"message": "hi"})
ok("chat returns no_key when unconfigured", r.status_code == 400 and r.get_json()["error"] == "no_key", (r.status_code, r.get_json()))

# --- generate-doc (pdf + docx) ---
r = c.post("/ai/api/generate-doc", json={"text": "Hello world\nLine two", "format": "pdf"})
ok("generate pdf", r.status_code == 200 and r.data[:4] == b"%PDF", r.status_code)
r = c.post("/ai/api/generate-doc", json={"text": "Hello world", "format": "docx"})
ok("generate docx", r.status_code == 200 and r.data[:2] == b"PK", (r.status_code, r.data[:2]))

# --- upload ---
bad = c.post("/ai/api/upload", data={"file": (io.BytesIO(b"x"), "evil.exe")}, content_type="multipart/form-data")
ok("upload rejects bad type", bad.status_code == 400 and bad.get_json()["error"] == "bad_type", bad.get_json())
good = c.post("/ai/api/upload", data={"file": (io.BytesIO("hello from file".encode()), "notes.txt")}, content_type="multipart/form-data")
gj = good.get_json()
ok("upload extracts text", good.status_code == 200 and "hello from file" in gj.get("text", ""), gj)

# --- admin-only settings ---
c.post("/register", data={"email": "teacher@ai.com", "name": "Teacher", "password": "secret123"})
c.post("/logout")
c.post("/login", data={"email": "teacher@ai.com", "password": "secret123"})
r = c.get("/ai/settings")
ok("teacher blocked from ai settings", r.status_code == 302, r.status_code)
r = c.post(f"/ai/api/messages/{mid}", json={"content": "hack"})
ok("teacher blocked from other's message", r.status_code == 404, r.status_code)

c.post("/logout")
c.post("/login", data={"email": "admin@ai.com", "password": "secret123"})
r = c.get("/ai/settings")
ok("admin sees ai settings", r.status_code == 200, r.status_code)
c.post("/ai/settings", data={"api_key": "sk-test", "model": "deepseek-chat", "daily_limit": "10"}, follow_redirects=False)
r = c.get("/ai/api/status").get_json()
ok("status configured after key saved", r["configured"] is True and r["model"] == "deepseek-chat", r)

print()
if failures:
    print("FAILURES:", failures)
    sys.exit(1)
print("RESULT: ALL PASS")
