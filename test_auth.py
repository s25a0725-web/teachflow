# -*- coding: utf-8 -*-
"""Authentication & security test suite (runs with CSRF ENABLED).

Covers: CSRF enforcement, register roles, validation, login, remember-me,
secure logout, role permissions, rate limiting, and the password reset flow.
"""
import os
import re
import sys
import tempfile

os.environ["TEACHFLOW_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["TEACHFLOW_UPLOAD_ROOT"] = tempfile.mkdtemp()
os.environ["TEACHFLOW_USERS"] = os.path.join(tempfile.mkdtemp(), "users.json")
os.environ["TEACHFLOW_SECRET"] = "auth-test-secret"
os.environ["TEACHFLOW_CSRF"] = "1"  # CSRF ON

sys.path.insert(0, r"C:\Users\tinee\teachflow")

from app import app  # noqa: E402
import userstore  # noqa: E402

fail = 0


def ok(name, cond, extra=""):
    global fail
    if not cond:
        fail += 1
    print(("OK  " if cond else "FAIL") + f"  {name}" + (f"  [got: {extra}]" if extra and not cond else ""))


def csrf(client):
    html = client.get("/login").get_data(as_text=True)
    m = re.search(r'name="csrf-token" content="([^"]+)"', html)
    return m.group(1) if m else ""


# --- CSRF enforcement ---
c = app.test_client()
r = c.post("/login", data={"email": "admin@school.edu", "password": "secret123"})
ok("token-less login POST rejected", r.status_code in (302, 400), r.status_code)
r = c.get("/", follow_redirects=False)
ok("token-less POST did not authenticate", r.status_code == 302, r.status_code)

r = app.test_client().post("/chatbot", json={"message": "hi", "lang": "en"})
ok("fetch-style POST without header rejected (400 json)",
   r.status_code == 400 and r.is_json and r.get_json().get("error") == "csrf", r.status_code)

# --- Registration roles + validation ---
tok = csrf(c)
r = c.post("/register", data={"email": "admin@school.edu", "name": "Admin One",
                              "password": "secret123", "csrf_token": tok}, follow_redirects=True)
ok("register (first user) returns 200", r.status_code == 200)
u = userstore.get_by_email("admin@school.edu")
ok("first registered user is admin", bool(u) and u["role"] == "admin", u and u["role"])

tok = csrf(c)
r = c.post("/register", data={"email": "bademail", "name": "X", "password": "secret123",
                              "csrf_token": tok}, follow_redirects=True)
ok("register rejects invalid email", "valid email address" in r.get_data(as_text=True))

tok = csrf(c)
r = c.post("/register", data={"email": "teacher@school.edu", "name": "Teacher Two",
                              "password": "secret123", "csrf_token": tok}, follow_redirects=True)
u2 = userstore.get_by_email("teacher@school.edu")
ok("second registered user is teacher", bool(u2) and u2["role"] == "teacher", u2 and u2["role"])

# --- Login + remember-me ---
c2 = app.test_client()
tok = csrf(c2)
r = c2.post("/login", data={"email": "admin@school.edu", "password": "secret123",
                            "remember": "on", "csrf_token": tok})
ok("login success -> 302 redirect", r.status_code == 302, r.status_code)
sc = r.headers.get("Set-Cookie", "")
ok("remember-me sets permanent cookie", "Expires=" in sc or "Max-Age=" in sc, sc[:90])
r = c2.get("/", follow_redirects=True)
ok("authenticated dashboard loads", r.status_code == 200 and "Admin One" in r.get_data(as_text=True))

# --- Role permissions ---
r = c2.get("/settings")
ok("admin can access /settings (200)", r.status_code == 200, r.status_code)

# --- Secure logout (POST) ---
tok = csrf(c2)
r = c2.post("/logout", data={"csrf_token": tok}, follow_redirects=True)
ok("logout (POST) returns 200", r.status_code == 200, r.status_code)
r = c2.get("/settings", follow_redirects=False)
ok("after logout /settings redirects", r.status_code == 302, r.status_code)
r = c2.get("/logout")
ok("GET /logout is rejected (405)", r.status_code == 405, r.status_code)

# --- Teacher role restriction ---
c3 = app.test_client()
tok = csrf(c3)
c3.post("/login", data={"email": "teacher@school.edu", "password": "secret123", "csrf_token": tok})
r = c3.get("/settings", follow_redirects=False)
ok("teacher cannot access /settings (302)", r.status_code == 302, r.status_code)

# --- Rate limiting ---
rl = app.test_client()
for _ in range(5):
    tok = csrf(rl)
    rl.post("/login", data={"email": "victim@school.edu", "password": "wrong", "csrf_token": tok})
tok = csrf(rl)
r = rl.post("/login", data={"email": "victim@school.edu", "password": "wrong",
                            "csrf_token": tok}, follow_redirects=True)
ok("rate limit blocks after 5 failures", "Too many attempts" in r.get_data(as_text=True))

# --- Forgot / reset password flow ---
f = app.test_client()
tok = csrf(f)
f.post("/register", data={"email": "resetme@school.edu", "name": "Reset Me", "password": "oldpass123",
                          "security_question": "sq_pet", "security_answer": "fluffy",
                          "csrf_token": tok}, follow_redirects=True)
tok = csrf(f)
r = f.post("/forgot-password", data={"email": "resetme@school.edu", "csrf_token": tok}, follow_redirects=True)
ok("forgot-password reaches reset page", r.status_code == 200 and 'name="answer"' in r.get_data(as_text=True))
tok = csrf(f)
r = f.post("/reset-password", data={"answer": "fluffy", "password": "newpass123", "csrf_token": tok},
           follow_redirects=True)
ok("reset-password succeeds", r.status_code == 200)
u3 = userstore.get_by_email("resetme@school.edu")
ok("password actually changed", bool(u3) and userstore.check(u3, "newpass123"))

print("\nRESULT:", "ALL PASS" if fail == 0 else f"{fail} FAILED")
