# -*- coding: utf-8 -*-
"""AI Teacher Assistant blueprint — ChatGPT-style assistant powered by DeepSeek.

Chat + streaming + per-user conversation history + a catalogue of teacher
tools (lesson planner, worksheet, exam paper, ...). All AI calls go through
ai_provider (server-side key only). Read-only access to attendance data is
provided to the attendance-summary tool; the AI can never write records here.
"""
import io
import json
from functools import wraps
from pathlib import Path
from uuid import uuid4

from flask import (
    Blueprint, render_template, request, session, redirect, url_for,
    jsonify, Response, stream_with_context, flash,
)
from werkzeug.utils import secure_filename

from db import get_db, get_setting, set_setting
from i18n import t
import userstore
from persona import SYSTEM_PROMPT
from ai_provider import stream_chat, complete, configured, model
from file_assistant import pdf_to_text, docx_to_text, text_to_pdf_bytes

bp = Blueprint("ai", __name__, url_prefix="/ai")

_BASE = Path(__file__).resolve().parent
UPLOAD_ROOT = Path(__import__("os").environ.get("TEACHFLOW_UPLOAD_ROOT", str(_BASE / "uploads")))

ALLOWED_EXTS = ("pdf", "docx", "txt", "md", "csv", "json", "xlsx", "xls", "html", "htm")

LANGS = {"en": "English", "ms": "Bahasa Malaysia", "ta": "Tamil"}


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not userstore.is_admin_role(session.get("role")):
            flash("admin_only", "error")
            return redirect(url_for("views.dashboard"))
        return f(*args, **kwargs)
    return wrapper


# ---------------------------------------------------------------------------
# Tool catalogue
# ---------------------------------------------------------------------------
TOOLS = {
    "chat": {
        "id": "chat", "name_key": "ai_chat", "desc_key": "ai_chat_desc",
        "icon": "chat", "system": "", "fields": [],
        "max_tokens": 1500,
    },
    "lesson_planner": {
        "id": "lesson_planner", "name_key": "ai_lesson_planner", "desc_key": "ai_lesson_planner_desc",
        "icon": "plan",
        "system": ("Create a complete, classroom-ready lesson plan aligned with the Malaysian "
                   "curriculum where applicable. Include: learning objectives, set induction, "
                   "lesson development (step-by-step activities with time), teaching aids, "
                   "differentiation, assessment and closure. Use headings and a table where useful."),
        "fields": [
            {"key": "subject", "label_key": "subject", "type": "text"},
            {"key": "topic", "label_key": "topic", "type": "text"},
            {"key": "grade", "label_key": "grade", "type": "text"},
            {"key": "duration", "label_key": "ai_duration", "type": "text"},
        ],
        "max_tokens": 2000,
    },
    "worksheet": {
        "id": "worksheet", "name_key": "ai_worksheet", "desc_key": "ai_worksheet_desc",
        "icon": "sheet",
        "system": ("Create a printable student worksheet. Include a clear title, instructions, "
                   "a mix of question types (fill-in, short answer, structured) with increasing "
                   "difficulty, space for answers, and an answer key at the end."),
        "fields": [
            {"key": "subject", "label_key": "subject", "type": "text"},
            {"key": "topic", "label_key": "topic", "type": "text"},
            {"key": "grade", "label_key": "grade", "type": "text"},
            {"key": "questions", "label_key": "ai_num_questions", "type": "text"},
        ],
        "max_tokens": 2000,
    },
    "exam_paper": {
        "id": "exam_paper", "name_key": "ai_exam_paper", "desc_key": "ai_exam_paper_desc",
        "icon": "exam",
        "system": ("Create a formal examination paper in UASA/KPM style. Structure it into "
                   "sections (objective and subjective/structured), mark each question with its "
                   "marks, keep language appropriate to the level, and include a marking guide."),
        "fields": [
            {"key": "subject", "label_key": "subject", "type": "text"},
            {"key": "topic", "label_key": "topic", "type": "text"},
            {"key": "grade", "label_key": "grade", "type": "text"},
            {"key": "questions", "label_key": "ai_num_questions", "type": "text"},
        ],
        "max_tokens": 2500,
    },
    "marking_scheme": {
        "id": "marking_scheme", "name_key": "ai_marking_scheme", "desc_key": "ai_marking_scheme_desc",
        "icon": "grade",
        "system": ("Create a detailed marking scheme / answer key for the questions provided. "
                   "For each question give the correct answer or acceptable answers, the marks "
                   "allocation, and any marking notes or common misconceptions."),
        "fields": [
            {"key": "subject", "label_key": "subject", "type": "text"},
            {"key": "questions", "label_key": "ai_questions", "type": "textarea"},
        ],
        "max_tokens": 2000,
    },
    "report_writer": {
        "id": "report_writer", "name_key": "ai_report_writer", "desc_key": "ai_report_writer_desc",
        "icon": "report",
        "system": ("Write a professional, encouraging student progress report. Be specific, "
                   "balanced (strengths and areas to improve), constructive, and written for "
                   "parents/guardians. Avoid generic filler."),
        "fields": [
            {"key": "student", "label_key": "ai_student_name", "type": "text"},
            {"key": "subject", "label_key": "subject", "type": "text"},
            {"key": "grade", "label_key": "grade", "type": "text"},
            {"key": "notes", "label_key": "ai_notes", "type": "textarea"},
        ],
        "max_tokens": 1200,
    },
    "official_letter": {
        "id": "official_letter", "name_key": "ai_official_letter", "desc_key": "ai_official_letter_desc",
        "icon": "mail",
        "system": ("Write a formal, correctly formatted official letter/circular. Use the proper "
                   "structure (reference, date, recipient, salutation, body, closing). Keep the "
                   "tone professional and concise."),
        "fields": [
            {"key": "letter_type", "label_key": "ai_letter_type", "type": "text"},
            {"key": "recipient", "label_key": "ai_recipient", "type": "text"},
            {"key": "subject", "label_key": "subject", "type": "text"},
            {"key": "points", "label_key": "ai_body_points", "type": "textarea"},
        ],
        "max_tokens": 1500,
    },
    "meeting_minutes": {
        "id": "meeting_minutes", "name_key": "ai_meeting_minutes", "desc_key": "ai_meeting_minutes_desc",
        "icon": "time",
        "system": ("Write clear, structured meeting minutes. Include: date/time/venue, "
                   "attendees, agenda, discussion points, decisions, and action items with "
                   "responsible person and deadline."),
        "fields": [
            {"key": "meeting", "label_key": "ai_meeting_title", "type": "text"},
            {"key": "attendees", "label_key": "ai_attendees", "type": "text"},
            {"key": "agenda", "label_key": "ai_agenda", "type": "textarea"},
        ],
        "max_tokens": 1500,
    },
    "teaching_materials": {
        "id": "teaching_materials", "name_key": "ai_materials", "desc_key": "ai_materials_desc",
        "icon": "book",
        "system": ("Create teaching/learning materials: notes, slides outline, flashcards, "
                   "diagrams described in words, or revision summary. Make it clear, structured, "
                   "and appropriate for the grade level."),
        "fields": [
            {"key": "subject", "label_key": "subject", "type": "text"},
            {"key": "topic", "label_key": "topic", "type": "text"},
            {"key": "grade", "label_key": "grade", "type": "text"},
            {"key": "material_type", "label_key": "ai_material_type", "type": "text"},
        ],
        "max_tokens": 2000,
    },
    "parent_comm": {
        "id": "parent_comm", "name_key": "ai_parent_comm", "desc_key": "ai_parent_comm_desc",
        "icon": "parent",
        "system": ("Draft a warm, professional message to a parent/guardian. Be respectful, "
                   "specific and constructive. Offer clear next steps and an invitation to "
                   "discuss further."),
        "fields": [
            {"key": "student", "label_key": "ai_student_name", "type": "text"},
            {"key": "points", "label_key": "ai_message_points", "type": "textarea"},
        ],
        "max_tokens": 1000,
    },
    "translator": {
        "id": "translator", "name_key": "ai_translator", "desc_key": "ai_translator_desc",
        "icon": "lang",
        "system": ("Translate the given text accurately and naturally, preserving meaning and "
                   "tone. Provide the translation followed by nothing else unless asked."),
        "fields": [
            {"key": "source", "label_key": "ai_source_lang", "type": "text"},
            {"key": "target", "label_key": "ai_target_lang", "type": "text"},
            {"key": "text", "label_key": "ai_text", "type": "textarea"},
        ],
        "max_tokens": 1500,
    },
    "attendance_summary": {
        "id": "attendance_summary", "name_key": "ai_attendance_summary", "desc_key": "ai_attendance_summary_desc",
        "icon": "staff",
        "system": ("Summarize the provided attendance data into a clear administrative report. "
                   "Highlight totals, trends, late arrivals and any patterns. Present a concise "
                   "summary with a short table. Do not invent records that are not in the data."),
        "fields": [],
        "max_tokens": 1500,
    },
}


def tools_catalog(lang_code):
    """Translated tool list for the frontend."""
    out = []
    for tool in TOOLS.values():
        fields = []
        for f in tool["fields"]:
            fields.append({
                "key": f["key"],
                "label": t(f["label_key"], lang_code),
                "type": f.get("type", "text"),
            })
        out.append({
            "id": tool["id"],
            "name": t(tool["name_key"], lang_code),
            "desc": t(tool["desc_key"], lang_code),
            "icon": tool["icon"],
            "fields": fields,
        })
    return out


def build_system(tool_id, lang_code):
    tool = TOOLS.get(tool_id, TOOLS["chat"])
    parts = [SYSTEM_PROMPT]
    if tool.get("system"):
        parts.append("You are currently using the '%s' tool. Follow this guidance:\n%s"
                     % (tool["name_key"], tool["system"]))
    parts.append("Respond in %s unless the user asks otherwise." % LANGS.get(lang_code, "English"))
    return "\n\n".join(parts)


def _usage_ok(uid):
    limit = int(get_setting("ai_daily_limit") or 500)
    db = get_db()
    n = db.execute(
        "SELECT COUNT(*) c FROM ai_messages m "
        "JOIN ai_conversations c ON m.conversation_id = c.id "
        "WHERE c.teacher_id = ? AND m.role = 'user' AND m.created_at >= datetime('now','-1 day')",
        (uid,),
    ).fetchone()["c"]
    db.close()
    return n < limit


def _stream_assistant(conv_id, messages, tool_id):
    def generate():
        full = ""
        try:
            for delta in stream_chat(messages, max_tokens=TOOLS.get(tool_id, TOOLS["chat"])["max_tokens"]):
                full += delta
                yield "data: " + json.dumps({"delta": delta}) + "\n\n"
        except RuntimeError as e:
            yield "data: " + json.dumps({"error": str(e)}) + "\n\n"
            return
        except Exception:
            yield "data: " + json.dumps({"error": "stream_failed"}) + "\n\n"
            return
        db = get_db()
        db.execute(
            "INSERT INTO ai_messages (conversation_id, role, content, tool) VALUES (?,?,?,?)",
            (conv_id, "assistant", full, tool_id),
        )
        db.execute("UPDATE ai_conversations SET updated_at = datetime('now') WHERE id = ?", (conv_id,))
        db.commit()
        db.close()
        yield "data: " + json.dumps({"done": True, "conversation_id": conv_id}) + "\n\n"

    return Response(stream_with_context(generate()), content_type="text/event-stream")


def _history(db, conv_id, limit=30):
    rows = db.execute(
        "SELECT role, content, tool FROM ai_messages WHERE conversation_id = ? ORDER BY id DESC LIMIT ?",
        (conv_id, limit),
    ).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def _attendance_data(uid):
    from userstore import get_by_id
    db = get_db()
    if session.get("role") == "admin":
        rows = db.execute(
            "SELECT teacher_id, date, status, time, late_minutes FROM teacher_attendance "
            "WHERE date >= date('now','-30 day') ORDER BY date DESC"
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT teacher_id, date, status, time, late_minutes FROM teacher_attendance "
            "WHERE teacher_id = ? AND date >= date('now','-30 day') ORDER BY date DESC",
            (uid,),
        ).fetchall()
    db.close()
    counts = {}
    lines = []
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
        who = ""
        u = get_by_id(r["teacher_id"])
        if u:
            who = (u.get("name") or "?") + " | "
        detail = f"{who}{r['date']}: {r['status']}"
        if r["time"]:
            detail += f", {r['time']}"
        if r["late_minutes"]:
            detail += f", late {r['late_minutes']} min"
        lines.append(detail)
    summary = ", ".join(f"{k} = {v}" for k, v in sorted(counts.items())) or "no records"
    return "Attendance records (last 30 days): " + summary + "\n\n" + "\n".join(lines[:300])


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------
@bp.route("/")
@login_required
def index():
    lang_code = session.get("lang", "en")
    js_strings = [
        "ai_new_chat", "ai_search", "ai_history", "ai_rename", "ai_delete",
        "ai_copy", "ai_regenerate", "ai_edit", "ai_attach", "ai_download_pdf",
        "ai_download_docx", "ai_placeholder", "ai_thinking", "ai_no_key",
        "ai_configure_key", "ai_select_tool", "ai_empty_state", "ai_send",
        "ai_generate", "ai_clear", "ai_attached", "ai_remove_attach",
        "save", "cancel", "ai_tagline",
        "ai_task_lesson", "ai_task_worksheet", "ai_task_exam",
        "ai_task_parent", "ai_task_attendance", "ai_task_translate",
        "ai_hello", "ai_subheading", "ai_stop", "ai_account_settings",
        "ai_suggest_lesson", "ai_suggest_exam", "ai_suggest_worksheet",
        "ai_suggest_letter", "ai_suggest_attendance", "ai_suggest_materials",
        "ai_like", "ai_dislike", "ai_share", "ai_feedback_saved",
    ]
    return render_template(
        "ai_assistant.html",
        tools_json=json.dumps(tools_catalog(lang_code)),
        strings_json=json.dumps({k: t(k, lang_code) for k in js_strings}),
        configured=configured(),
        model_name=model(),
    )


@bp.route("/settings", methods=["GET", "POST"])
@login_required
@admin_required
def settings():
    if request.method == "POST":
        set_setting("deepseek_api_key", request.form.get("api_key", "").strip())
        set_setting("deepseek_model", (request.form.get("model", "") or "deepseek-chat").strip())
        set_setting("ai_daily_limit", (request.form.get("daily_limit", "") or "500").strip())
        flash("settings_saved", "success")
        return redirect(url_for("ai.settings"))
    return render_template(
        "ai_settings.html",
        configured=configured(),
        model_name=model(),
        has_key=bool(get_setting("deepseek_api_key")),
        daily_limit=get_setting("ai_daily_limit") or "500",
    )


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------
@bp.route("/api/conversations")
@login_required
def conversations():
    db = get_db()
    rows = db.execute(
        "SELECT id, title, updated_at FROM ai_conversations WHERE teacher_id = ? ORDER BY updated_at DESC",
        (session["user_id"],),
    ).fetchall()
    db.close()
    return jsonify([{"id": r["id"], "title": r["title"] or "New chat", "updated_at": r["updated_at"]} for r in rows])


@bp.route("/api/conversations", methods=["POST"])
@login_required
def new_conversation():
    db = get_db()
    cur = db.execute(
        "INSERT INTO ai_conversations (teacher_id, title) VALUES (?, 'New chat')",
        (session["user_id"],),
    )
    db.commit()
    cid = cur.lastrowid
    db.close()
    return jsonify({"id": cid, "title": "New chat"})


@bp.route("/api/conversations/<int:cid>", methods=["POST"])
@login_required
def rename_conversation(cid):
    title = (request.get_json(silent=True) or {}).get("title", "").strip()
    if not title:
        return jsonify({"error": "empty"}), 400
    db = get_db()
    cur = db.execute(
        "UPDATE ai_conversations SET title = ? WHERE id = ? AND teacher_id = ?",
        (title[:120], cid, session["user_id"]),
    )
    db.commit()
    db.close()
    if cur.rowcount == 0:
        return jsonify({"error": "not_found"}), 404
    return jsonify({"ok": True})


@bp.route("/api/conversations/<int:cid>", methods=["DELETE"])
@login_required
def delete_conversation(cid):
    db = get_db()
    db.execute("DELETE FROM ai_messages WHERE conversation_id = ?", (cid,))
    db.execute("DELETE FROM ai_conversations WHERE id = ? AND teacher_id = ?", (cid, session["user_id"]))
    db.commit()
    db.close()
    return jsonify({"ok": True})


@bp.route("/api/conversations/<int:cid>/messages")
@login_required
def messages(cid):
    db = get_db()
    conv = db.execute(
        "SELECT id FROM ai_conversations WHERE id = ? AND teacher_id = ?", (cid, session["user_id"])
    ).fetchone()
    if not conv:
        db.close()
        return jsonify({"error": "not_found"}), 404
    rows = db.execute(
        "SELECT id, role, content, tool, feedback, created_at FROM ai_messages WHERE conversation_id = ? ORDER BY id",
        (cid,),
    ).fetchall()
    db.close()
    return jsonify([{"id": r["id"], "role": r["role"], "content": r["content"],
                     "tool": r["tool"], "feedback": r["feedback"],
                     "created_at": r["created_at"]} for r in rows])


@bp.route("/api/messages/<int:mid>/feedback", methods=["POST"])
@login_required
def feedback(mid):
    """Persist like/dislike on an assistant message (like | dislike | null)."""
    data = request.get_json(silent=True) or {}
    value = data.get("feedback")
    if value not in ("like", "dislike", None):
        return jsonify({"error": "bad_feedback"}), 400
    db = get_db()
    row = db.execute(
        "SELECT m.id FROM ai_messages m JOIN ai_conversations c ON m.conversation_id = c.id "
        "WHERE m.id = ? AND c.teacher_id = ?",
        (mid, session["user_id"]),
    ).fetchone()
    if not row:
        db.close()
        return jsonify({"error": "not_found"}), 404
    db.execute("UPDATE ai_messages SET feedback = ? WHERE id = ?", (value, mid))
    db.commit()
    db.close()
    return jsonify({"ok": True, "feedback": value})


@bp.route("/api/messages/<int:mid>", methods=["POST"])
@login_required
def update_message(mid):
    data = request.get_json(silent=True) or {}
    content = data.get("content")
    if content is None:
        return jsonify({"error": "empty"}), 400
    db = get_db()
    row = db.execute(
        "SELECT m.id FROM ai_messages m JOIN ai_conversations c ON m.conversation_id = c.id "
        "WHERE m.id = ? AND c.teacher_id = ?",
        (mid, session["user_id"]),
    ).fetchone()
    if not row:
        db.close()
        return jsonify({"error": "not_found"}), 404
    db.execute("UPDATE ai_messages SET content = ? WHERE id = ?", (content, mid))
    db.commit()
    db.close()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Chat (streaming) + regenerate
# ---------------------------------------------------------------------------
@bp.route("/api/chat", methods=["POST"])
@login_required
def chat():
    if not configured():
        return jsonify({"error": "no_key"}), 400
    if not _usage_ok(session["user_id"]):
        return jsonify({"error": "limit"}), 429

    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"error": "empty"}), 400
    tool_id = data.get("tool") or "chat"
    if tool_id not in TOOLS:
        tool_id = "chat"
    context = (data.get("context") or "").strip()
    uid = session["user_id"]

    db = get_db()
    conv_id = data.get("conversation_id")
    if conv_id:
        conv = db.execute(
            "SELECT id FROM ai_conversations WHERE id = ? AND teacher_id = ?", (conv_id, uid)
        ).fetchone()
        if not conv:
            db.close()
            return jsonify({"error": "not_found"}), 404
        conv_id = conv["id"]
    else:
        title = message[:60] + ("…" if len(message) > 60 else "")
        cur = db.execute("INSERT INTO ai_conversations (teacher_id, title) VALUES (?, ?)", (uid, title))
        conv_id = cur.lastrowid

    db.execute(
        "INSERT INTO ai_messages (conversation_id, role, content, tool) VALUES (?,?,?,?)",
        (conv_id, "user", message, tool_id),
    )
    db.execute("UPDATE ai_conversations SET updated_at = datetime('now') WHERE id = ?", (conv_id,))
    db.commit()

    messages = [{"role": "system", "content": build_system(tool_id, session.get("lang", "en"))}]
    messages += _history(db, conv_id)
    if context:
        messages[-1]["content"] += "\n\n[Attached document content]\n" + context[:12000]
    if tool_id == "attendance_summary":
        messages.append({"role": "user", "content": "Here is the attendance data to summarize:\n\n" + _attendance_data(uid)})
    db.close()

    return _stream_assistant(conv_id, messages, tool_id)


@bp.route("/api/regenerate", methods=["POST"])
@login_required
def regenerate():
    if not configured():
        return jsonify({"error": "no_key"}), 400
    if not _usage_ok(session["user_id"]):
        return jsonify({"error": "limit"}), 429

    data = request.get_json(silent=True) or {}
    conv_id = data.get("conversation_id")
    uid = session["user_id"]
    db = get_db()
    conv = db.execute(
        "SELECT id FROM ai_conversations WHERE id = ? AND teacher_id = ?", (conv_id, uid)
    ).fetchone()
    if not conv:
        db.close()
        return jsonify({"error": "not_found"}), 404

    # Drop the trailing assistant message(s) so we can regenerate the last turn.
    while True:
        last = db.execute(
            "SELECT id, role FROM ai_messages WHERE conversation_id = ? ORDER BY id DESC LIMIT 1",
            (conv_id,),
        ).fetchone()
        if last and last["role"] == "assistant":
            db.execute("DELETE FROM ai_messages WHERE id = ?", (last["id"],))
        else:
            break
    db.commit()

    history = _history(db, conv_id)
    # history ends with the last user message; that is what we regenerate.
    last_user = next((m for m in reversed(history) if m["role"] == "user"), None)
    if not last_user:
        db.close()
        return jsonify({"error": "nothing_to_regenerate"}), 400
    tool_id = TOOLS["chat"]["id"]
    # recover tool from the last user message row
    row = db.execute(
        "SELECT tool FROM ai_messages WHERE conversation_id = ? AND role = 'user' ORDER BY id DESC LIMIT 1",
        (conv_id,),
    ).fetchone()
    db.close()
    tool_id = row["tool"] if row and row["tool"] else "chat"
    if tool_id not in TOOLS:
        tool_id = "chat"

    messages = [{"role": "system", "content": build_system(tool_id, session.get("lang", "en"))}]
    messages += history
    if tool_id == "attendance_summary":
        messages.append({"role": "user", "content": "Here is the attendance data to summarize:\n\n" + _attendance_data(uid)})
    return _stream_assistant(conv_id, messages, tool_id)


# ---------------------------------------------------------------------------
# Document upload + analysis
# ---------------------------------------------------------------------------
def _extract_text(path, name):
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext == "pdf":
        try:
            return pdf_to_text(path)
        except Exception:
            return ""
    if ext == "docx":
        try:
            return docx_to_text(path)
        except Exception:
            return ""
    if ext in ("txt", "md", "csv", "json", "log", "html", "htm"):
        return Path(path).read_text(encoding="utf-8", errors="ignore")
    if ext in ("xlsx", "xls"):
        try:
            from openpyxl import load_workbook
            wb = load_workbook(path, read_only=True, data_only=True)
            out = []
            for ws in wb.worksheets:
                for row in ws.iter_rows(values_only=True):
                    out.append(" | ".join("" if c is None else str(c) for c in row))
            return "\n".join(out)
        except Exception:
            return ""
    return ""


@bp.route("/api/upload", methods=["POST"])
@login_required
def upload():
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error": "no_file"}), 400
    ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
    if ext not in ALLOWED_EXTS:
        return jsonify({"error": "bad_type"}), 400
    d = UPLOAD_ROOT / "ai" / str(session["user_id"])
    d.mkdir(parents=True, exist_ok=True)
    stored = d / (uuid4().hex + "." + ext)
    f.save(stored)
    text = _extract_text(stored, f.filename)
    if not text.strip():
        return jsonify({"error": "no_text", "name": secure_filename(f.filename)}), 400
    return jsonify({"name": secure_filename(f.filename), "text": text[:12000]})


# ---------------------------------------------------------------------------
# Downloadable documents (DOCX / PDF)
# ---------------------------------------------------------------------------
def _to_docx(text, title):
    try:
        from docx import Document
    except ImportError:
        return None
    doc = Document()
    doc.add_heading(title or "TeachFlow", 0)
    for line in (text or "").split("\n"):
        if line.strip():
            doc.add_paragraph(line)
        else:
            doc.add_paragraph()
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _safe_name(title):
    clean = "".join(ch if ch.isalnum() or ch in ("-", "_", " ") else "" for ch in (title or ""))
    clean = " ".join(clean.split())
    return clean[:80] or "document"


@bp.route("/api/generate-doc", methods=["POST"])
@login_required
def generate_doc():
    data = request.get_json(silent=True) or {}
    text = data.get("text") or ""
    fmt = data.get("format") or "docx"
    title = data.get("title") or "TeachFlow"
    if not text.strip():
        return jsonify({"error": "empty"}), 400
    if fmt == "docx":
        b = _to_docx(text, title)
        if b is None:
            return jsonify({"error": "docx_unavailable"}), 400
        return Response(
            b,
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": "attachment; filename=%s.docx" % _safe_name(title)},
        )
    b = text_to_pdf_bytes(text)
    return Response(
        b,
        mimetype="application/pdf",
        headers={"Content-Disposition": "attachment; filename=%s.pdf" % _safe_name(title)},
    )


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------
@bp.route("/api/status")
@login_required
def status():
    return jsonify({"configured": configured(), "model": model()})
