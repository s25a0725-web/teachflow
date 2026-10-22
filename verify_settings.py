# -*- coding: utf-8 -*-
"""Verify admin settings: branding edit, logo upload, user role management."""
import io
import os
import tempfile

os.chdir(os.path.dirname(os.path.abspath(__file__)))
os.environ["TEACHFLOW_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")
os.environ["TEACHFLOW_UPLOAD_ROOT"] = tempfile.mkdtemp()

from app import app  # noqa: E402
from db import get_db, get_setting  # noqa: E402

c = app.test_client()
c.post("/register", data={"email": "admin@x.com", "name": "Admin", "password": "secret123"})
c.post("/login", data={"email": "admin@x.com", "password": "secret123"})

print("settings GET:", c.get("/settings").status_code)
print("branding logo (fallback):", c.get("/branding/logo").status_code)

r = c.post("/settings", data={
    "action": "branding",
    "school_name": "SJK(T) Sepang",
    "tagline": "Ilmu Suluh Hidup",
    "logo": (io.BytesIO(b"fake-image-bytes"), "logo.png"),
}, content_type="multipart/form-data", follow_redirects=True)
print("settings POST branding:", r.status_code)
print("school_name persisted:", get_setting("school_name"))
print("logo_filename persisted:", get_setting("logo_filename"))
print("branding logo (uploaded):", c.get("/branding/logo").status_code)

# second user, promote to admin
c.post("/register", data={"email": "t2@x.com", "name": "T2", "password": "secret123"})
db = get_db()
t2 = db.execute("SELECT id FROM users WHERE email='t2@x.com'").fetchone()
db.close()
c.post("/settings", data={"action": "user_role", "user_id": str(t2["id"]), "role": "admin"}, follow_redirects=True)
db = get_db()
role = db.execute("SELECT role FROM users WHERE id=?", (t2["id"],)).fetchone()["role"]
db.close()
print("t2 role after promote:", role)
assert role == "admin"

# non-admin blocked from settings
c.post("/logout")
c.post("/register", data={"email": "t3@x.com", "name": "T3", "password": "secret123"})
c.post("/login", data={"email": "t3@x.com", "password": "secret123"})
r = c.get("/settings")
print("non-admin /settings (expect 302 redirect):", r.status_code)
assert r.status_code == 302

print("\nSETTINGS OK")
