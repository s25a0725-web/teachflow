# -*- coding: utf-8 -*-
"""Flat-file user store (JSON) — a drop-in replacement for the SQL `users` table.

Why: login must work on a fresh VPS where the SQLite DB may not have been
copied. This file travels with the code and is the source of truth for
authentication.

Structure (migrates 1:1 to SQL later — each entry's keys mirror the `users`
columns, so migration is a plain `INSERT INTO users (...) VALUES (...)`):

    {
      "users": [
        {"id": 1, "email": "...", "password_hash": "scrypt:...", "name": "...",
         "role": "admin", "security_question": null, "security_answer_hash": null,
         "created_at": "2026-10-22 02:36:49"},
        ...
      ]
    }

Passwords are werkzeug scrypt hashes (never plaintext). Writes are atomic
(write-temp + os.replace), so a crash never leaves a half-written file.
"""
import json
import os
import tempfile
import threading
from datetime import datetime
from pathlib import Path

from werkzeug.security import generate_password_hash, check_password_hash

USERS_FILE = os.environ.get("TEACHFLOW_USERS", str(Path(__file__).resolve().parent / "users.json"))

_lock = threading.Lock()


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _load():
    """Return the list of user dicts ([] if the file is missing or empty)."""
    if not os.path.exists(USERS_FILE):
        return []
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []
    if isinstance(data, list):          # tolerate a bare array too
        return data
    return data.get("users", []) if isinstance(data, dict) else []


def _save(users):
    payload = {"users": users}
    d = os.path.dirname(os.path.abspath(USERS_FILE)) or "."
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".users-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, USERS_FILE)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def _normalize_email(email):
    return (email or "").strip().lower()


# --------------------------------------------------------------------------
# Public API (swap the backend behind these to move to SQL later)
# --------------------------------------------------------------------------
def get_by_email(email):
    email = _normalize_email(email)
    with _lock:
        for u in _load():
            if _normalize_email(u.get("email")) == email:
                return u
    return None


def get_by_id(uid):
    with _lock:
        for u in _load():
            if u.get("id") == uid:
                return u
    return None


def all_users():
    """All users, ordered by id (mirrors `SELECT * FROM users ORDER BY id`)."""
    with _lock:
        return sorted(_load(), key=lambda u: u.get("id", 0))


def count():
    with _lock:
        return len(_load())


def add(email, password, name, role="teacher", security_question=None, security_answer=None):
    email = _normalize_email(email)
    with _lock:
        users = _load()
        uid = max([u.get("id", 0) for u in users], default=0) + 1
        row = {
            "id": uid,
            "email": email,
            "password_hash": generate_password_hash(password),
            "name": (name or "").strip(),
            "role": role if role in ("admin", "teacher") else "teacher",
            "security_question": security_question or None,
            "security_answer_hash": generate_password_hash(security_answer)
                if security_answer else None,
            "created_at": _now(),
        }
        users.append(row)
        _save(users)
    return row


def update_password(uid, password):
    with _lock:
        users = _load()
        for u in users:
            if u.get("id") == uid:
                u["password_hash"] = generate_password_hash(password)
                _save(users)
                return True
    return False


def update_role(uid, role):
    if role not in ("admin", "teacher"):
        return False
    with _lock:
        users = _load()
        for u in users:
            if u.get("id") == uid:
                u["role"] = role
                _save(users)
                return True
    return False


def delete(uid):
    with _lock:
        users = _load()
        kept = [u for u in users if u.get("id") != uid]
        if len(kept) == len(users):
            return False
        _save(kept)
        return True


def check(user, password):
    return bool(user) and check_password_hash(user.get("password_hash"), password)


# --------------------------------------------------------------------------
# One-time import from the old SQLite users table (run manually once).
# --------------------------------------------------------------------------
def migrate_from_sqlite(db_path=None):
    """Copy rows from the SQLite `users` table into users.json.

    Safe to run repeatedly: only imports when users.json currently holds no
    users (it never overwrites accounts you created in the flat file).
    """
    import sqlite3

    db_path = db_path or str(Path(__file__).resolve().parent / "teachflow.db")
    if not os.path.exists(db_path):
        return 0
    with _lock:
        if _load():
            return 0
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute("SELECT * FROM users ORDER BY id").fetchall()
        finally:
            conn.close()
        users = []
        for r in rows:
            users.append({
                "id": r["id"],
                "email": _normalize_email(r["email"]),
                "password_hash": r["password_hash"],
                "name": r["name"],
                "role": r["role"],
                "security_question": r["security_question"],
                "security_answer_hash": r["security_answer_hash"],
                "created_at": r["created_at"],
            })
        if users:
            _save(users)
        return len(users)
