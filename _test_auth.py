# -*- coding: utf-8 -*-
"""Throwaway auth smoke test — uses a TEMP users.json + TEMP sqlite DB."""
import os
import sys
import tempfile

sys.path.insert(0, ".")

tmp = tempfile.gettempdir()
os.environ["TEACHFLOW_USERS"] = os.path.join(tmp, "tf_users_test.json")
os.environ["TEACHFLOW_DB"] = os.path.join(tmp, "tf_db_test.sqlite")
for p in (os.environ["TEACHFLOW_USERS"], os.environ["TEACHFLOW_DB"]):
    if os.path.exists(p):
        os.remove(p)

from app import create_app  # noqa: E402
import userstore  # noqa: E402

app = create_app()
app.config["TESTING"] = True

# 1. first registration -> admin
c = app.test_client()
r = c.post("/register", data={"email": "admin@test.com", "name": "Admin",
                              "password": "secret123", "security_question": "",
                              "security_answer": ""}, follow_redirects=True)
print("register status:", r.status_code)
print("users after register:", [(u["email"], u["role"]) for u in userstore.all_users()])

# 2. correct login (email case-insensitive)
c2 = app.test_client()
r = c2.post("/login", data={"email": "Admin@Test.com", "password": "secret123"})
print("login correct:", r.status_code, "->", r.headers.get("Location"))
with c2.session_transaction() as s:
    print("session:", s.get("user_id"), s.get("role"), s.get("name"))

# 3. wrong password
r = c2.post("/login", data={"email": "admin@test.com", "password": "WRONG"},
            follow_redirects=True)
print("login wrong status:", r.status_code, "| invalid_login shown:",
      "invalid_login" in r.get_data(as_text=True))

# 4. protected route without session redirects to login
c3 = app.test_client()
r = c3.get("/", follow_redirects=False)
print("protected / no session:", r.status_code, "->", r.headers.get("Location"))

# 5. password reset path (register a security answer first)
c4 = app.test_client()
r = c4.post("/register", data={"email": "t2@test.com", "name": "T2",
                               "password": "secret123", "security_question": "sq_school",
                               "security_answer": "sepang"}, follow_redirects=True)
print("register t2:", r.status_code)
r = c4.post("/forgot-password", data={"email": "t2@test.com"})
print("forgot ->", r.status_code, "->", r.headers.get("Location"))
r = c4.post("/reset-password", data={"answer": "sepang", "password": "newpass99"},
            follow_redirects=True)
print("reset:", r.status_code, "| done shown:", "reset_done" in r.get_data(as_text=True))
# confirm new password works
r = c4.post("/login", data={"email": "t2@test.com", "password": "newpass99"})
print("login after reset:", r.status_code, "->", r.headers.get("Location"))
