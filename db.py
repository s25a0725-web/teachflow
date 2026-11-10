# -*- coding: utf-8 -*-
"""SQLite schema and connection helpers."""
import os
import sqlite3
from pathlib import Path

DB_PATH = os.environ.get("TEACHFLOW_DB", str(Path(__file__).resolve().parent / "teachflow.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'teacher',
    security_question TEXT,
    security_answer_hash TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS classes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    teacher_id INTEGER NOT NULL REFERENCES users(id),
    name TEXT NOT NULL,
    subject TEXT,
    grade TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    class_id INTEGER NOT NULL REFERENCES classes(id),
    name TEXT NOT NULL,
    parent_name TEXT,
    parent_email TEXT,
    ic_number TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    class_id INTEGER NOT NULL REFERENCES classes(id),
    teacher_id INTEGER NOT NULL REFERENCES users(id),
    title TEXT NOT NULL,
    description TEXT,
    total_marks INTEGER NOT NULL DEFAULT 100,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_id INTEGER NOT NULL REFERENCES assignments(id),
    student_id INTEGER NOT NULL REFERENCES students(id),
    marks REAL,
    feedback TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(assignment_id, student_id)
);

CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    class_id INTEGER NOT NULL REFERENCES classes(id),
    student_id INTEGER NOT NULL REFERENCES students(id),
    date TEXT NOT NULL,
    status TEXT NOT NULL,
    time TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(class_id, student_id, date)
);

CREATE TABLE IF NOT EXISTS teacher_attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    teacher_id INTEGER NOT NULL REFERENCES users(id),
    date TEXT NOT NULL,
    status TEXT NOT NULL,
    time TEXT,
    check_in_time TEXT,
    check_out_time TEXT,
    late_minutes INTEGER,
    source TEXT DEFAULT 'manual',
    latitude REAL,
    longitude REAL,
    accuracy_m REAL,
    verification TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(teacher_id, date)
);

CREATE TABLE IF NOT EXISTS timetable (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    teacher_id INTEGER NOT NULL REFERENCES users(id),
    day INTEGER NOT NULL,
    period INTEGER NOT NULL,
    subject TEXT NOT NULL,
    class_name TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS lesson_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    teacher_id INTEGER NOT NULL REFERENCES users(id),
    title TEXT NOT NULL,
    topic TEXT NOT NULL,
    subject TEXT,
    grade TEXT,
    language TEXT DEFAULT 'en',
    content TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS quizzes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    teacher_id INTEGER NOT NULL REFERENCES users(id),
    title TEXT NOT NULL,
    subject TEXT,
    topic TEXT,
    language TEXT DEFAULT 'en',
    questions_json TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    teacher_id INTEGER NOT NULL REFERENCES users(id),
    student_id INTEGER REFERENCES students(id),
    parent_name TEXT,
    parent_email TEXT,
    subject TEXT,
    body TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    teacher_id INTEGER NOT NULL REFERENCES users(id),
    title TEXT NOT NULL,
    original_name TEXT,
    stored_name TEXT NOT NULL,
    mime_type TEXT,
    folder_id INTEGER,
    summary TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS signatures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES documents(id),
    signer_name TEXT NOT NULL,
    signer_email TEXT,
    signature_file TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sign_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES documents(id),
    token TEXT UNIQUE NOT NULL,
    signer_name TEXT,
    signer_email TEXT,
    status TEXT DEFAULT 'pending',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS folders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    teacher_id INTEGER NOT NULL REFERENCES users(id),
    name TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS parent_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT,
    ic_number TEXT,
    password_hash TEXT NOT NULL,
    name TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS studio_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    teacher_id INTEGER NOT NULL REFERENCES users(id),
    name TEXT NOT NULL,
    stored_name TEXT NOT NULL,
    type TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS notebooks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    teacher_id INTEGER NOT NULL REFERENCES users(id),
    name TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    notebook_id INTEGER NOT NULL REFERENCES notebooks(id),
    teacher_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    stored_name TEXT NOT NULL,
    kind TEXT NOT NULL,
    page_count INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL REFERENCES sources(id),
    teacher_id INTEGER NOT NULL,
    idx INTEGER NOT NULL,
    page INTEGER DEFAULT 1,
    text TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS study_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    teacher_id INTEGER NOT NULL,
    notebook_id INTEGER,
    kind TEXT NOT NULL,
    title TEXT,
    content TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS school_locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    radius_m INTEGER NOT NULL DEFAULT 100,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS gps_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    teacher_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    event_date TEXT NOT NULL,
    latitude REAL,
    longitude REAL,
    accuracy_m REAL,
    verification TEXT DEFAULT 'verified',
    created_at TEXT NOT NULL,
    UNIQUE(teacher_id, event_type, event_date)
);

CREATE TABLE IF NOT EXISTS mc_applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    teacher_id INTEGER NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    reason TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    admin_remark TEXT,
    reviewed_by INTEGER,
    reviewed_at TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS mc_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mc_application_id INTEGER NOT NULL,
    stored_name TEXT NOT NULL,
    original_name TEXT,
    mime_type TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS leave_applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    teacher_id INTEGER NOT NULL,
    leave_type TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    reason TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    admin_remark TEXT,
    reviewed_by INTEGER,
    reviewed_at TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS leave_balances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    teacher_id INTEGER NOT NULL,
    leave_type TEXT NOT NULL,
    total_days REAL NOT NULL DEFAULT 0,
    used_days REAL NOT NULL DEFAULT 0,
    UNIQUE(teacher_id, leave_type)
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    kind TEXT,
    message TEXT NOT NULL,
    is_read INTEGER NOT NULL DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action TEXT NOT NULL,
    details TEXT,
    ip TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ai_conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    teacher_id INTEGER NOT NULL,
    title TEXT NOT NULL DEFAULT 'New chat',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ai_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    tool TEXT,
    feedback TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS rph_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    teacher_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    subject TEXT,
    class_name TEXT,
    rph_json TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS minit_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    teacher_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    jenis TEXT,
    unit TEXT,
    minit_json TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);
"""


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Auth lives in users.json (userstore.py), not the SQLite `users` table, so
    # the `REFERENCES users(id)` columns on other tables have no matching row on
    # a fresh install. The app does its own cascade deletes (see views.py), so
    # foreign-key enforcement is disabled to keep those inserts working.
    conn.execute("PRAGMA foreign_keys = OFF")
    return conn


def init_db():
    conn = get_db()
    conn.executescript(SCHEMA)
    # Lightweight migrations for columns added after an earlier schema version.
    cols = {r[1] for r in conn.execute("PRAGMA table_info(documents)").fetchall()}
    if "folder_id" not in cols:
        conn.execute("ALTER TABLE documents ADD COLUMN folder_id INTEGER")
    if "summary" not in cols:
        conn.execute("ALTER TABLE documents ADD COLUMN summary TEXT")
    att_cols = {r[1] for r in conn.execute("PRAGMA table_info(attendance)").fetchall()}
    if "time" not in att_cols:
        conn.execute("ALTER TABLE attendance ADD COLUMN time TEXT")
    stud_cols = {r[1] for r in conn.execute("PRAGMA table_info(students)").fetchall()}
    if "ic_number" not in stud_cols:
        conn.execute("ALTER TABLE students ADD COLUMN ic_number TEXT")
    user_cols = {r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()}
    if "security_question" not in user_cols:
        conn.execute("ALTER TABLE users ADD COLUMN security_question TEXT")
    if "security_answer_hash" not in user_cols:
        conn.execute("ALTER TABLE users ADD COLUMN security_answer_hash TEXT")
    par_cols = {r[1] for r in conn.execute("PRAGMA table_info(parent_accounts)").fetchall()}
    if "ic_number" not in par_cols:
        conn.execute("ALTER TABLE parent_accounts RENAME TO parent_accounts_old")
        conn.execute("""CREATE TABLE parent_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT,
            ic_number TEXT,
            password_hash TEXT NOT NULL,
            name TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )""")
        conn.execute(
            "INSERT INTO parent_accounts (id, email, ic_number, password_hash, name, created_at) "
            "SELECT id, email, NULL, password_hash, name, created_at FROM parent_accounts_old"
        )
        conn.execute("DROP TABLE parent_accounts_old")
    ta_cols = {r[1] for r in conn.execute("PRAGMA table_info(teacher_attendance)").fetchall()}
    for col, typ in [
        ("check_in_time", "TEXT"),
        ("check_out_time", "TEXT"),
        ("late_minutes", "INTEGER"),
        ("source", "TEXT DEFAULT 'manual'"),
        ("latitude", "REAL"),
        ("longitude", "REAL"),
        ("accuracy_m", "REAL"),
        ("verification", "TEXT"),
    ]:
        if col not in ta_cols:
            conn.execute(f"ALTER TABLE teacher_attendance ADD COLUMN {col} {typ}")
    aim_cols = {r[1] for r in conn.execute("PRAGMA table_info(ai_messages)").fetchall()}
    if "feedback" not in aim_cols:
        conn.execute("ALTER TABLE ai_messages ADD COLUMN feedback TEXT")
    conn.commit()
    conn.close()


def get_setting(key, default=None):
    conn = get_db()
    r = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return r["value"] if r else default


def set_setting(key, value):
    conn = get_db()
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()
    conn.close()
