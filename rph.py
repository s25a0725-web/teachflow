# -*- coding: utf-8 -*-
"""RPH (Rancangan Pengajaran Harian) module — full document generation & export.

Teachers enter lesson details, the AI (or an offline template) builds a
complete structured RPH, and the backend exports it as a professional A4 PDF
or Word document. Edits made in the preview are sent back and reflected in
the exported files.
"""
import io
import json
import re
from datetime import datetime
from functools import wraps
from pathlib import Path
from uuid import uuid4

from flask import (
    Blueprint, render_template, request, session, redirect, url_for,
    jsonify, Response, flash,
)

from db import get_db, get_setting
from i18n import t
import userstore
from rph_doc import build_rph_pdf, build_rph_docx, RPH_SECTIONS, META_FIELDS

bp = Blueprint("rph", __name__, url_prefix="/rph")

_BASE = Path(__file__).resolve().parent
_TMP = Path(__import__("os").environ.get("TEACHFLOW_UPLOAD_ROOT", str(_BASE / "uploads"))) / "rph"
_TMP.mkdir(parents=True, exist_ok=True)

LANGS = {"en": "English", "ms": "Bahasa Malaysia", "ta": "Tamil"}


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return wrapper


def _teacher():
    u = userstore.get_by_id(session["user_id"])
    return {
        "name": (u or {}).get("name") or session.get("name") or "",
        "school": get_setting("school_name") or "SJK(T) Sepang",
    }


def _json_body():
    return request.get_json(silent=True) or {}


# ---------------------------------------------------------------------------
# RPH generation
# ---------------------------------------------------------------------------
def _ai_rph(fields, lang):
    """Ask DeepSeek for a structured RPH JSON. Returns a dict or None."""
    from ai_provider import complete, configured
    if not configured():
        return None
    keys = [k for k, _, _ in RPH_SECTIONS]
    system = (
        "You are an expert Malaysian teacher writing a complete RPH "
        "(Rancangan Pengajaran Harian) aligned with KSSR/KSSM. "
        "Output ONLY valid JSON, no markdown, no commentary, with EXACTLY these keys: "
        + json.dumps(keys) +
        ". Rules: 'objectives', 'success_criteria', 'bbm' and 'emk' are arrays of strings; "
        "'activities' is an array of objects {step, time, detail}; every other key is a string. "
        "Write ALL content in " + LANGS.get(lang, "English") + "."
    )
    user = "Lesson details: " + json.dumps(fields, ensure_ascii=False)
    try:
        raw = complete([{"role": "system", "content": system},
                        {"role": "user", "content": user}], max_tokens=2500, temperature=0.6)
    except Exception:
        return None
    return _parse_rph_json(raw)


def _parse_rph_json(raw):
    text = (raw or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except ValueError:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            return None
        try:
            data = json.loads(m.group(0))
        except ValueError:
            return None
    if not isinstance(data, dict):
        return None
    return data


def _offline_rph(fields, lang):
    """Deterministic, complete RPH template when no API key is configured."""
    topic = fields.get("topic") or ""
    subject = fields.get("subject") or ""
    cls = fields.get("class") or ""
    T = {
        "en": {
            "sk": "Content standard related to %s." % topic,
            "sp": "Learning standard for %s appropriate to the class level." % topic,
            "objectives": ["By the end of the lesson, pupils will be able to state the key ideas about %s." % topic,
                           "By the end of the lesson, pupils will be able to apply %s in a simple task." % topic,
                           "By the end of the lesson, pupils will be able to explain %s in their own words." % topic],
            "success_criteria": ["Pupils can state at least 2 key points about %s." % topic,
                                 "Pupils can complete the given activity with minimal guidance."],
            "set_induksi": "Begin with a short question-and-answer session to activate prior knowledge about %s." % topic,
            "activities": [
                {"step": "Langkah 1", "time": "10 min", "detail": "Teacher introduces %s with examples and whole-class discussion." % topic},
                {"step": "Langkah 2", "time": "15 min", "detail": "Pupils work in groups on a guided activity about %s." % topic},
                {"step": "Langkah 3", "time": "10 min", "detail": "Groups present their findings; teacher clarifies misconceptions."},
                {"step": "Langkah 4", "time": "5 min", "detail": "Teacher summarises the lesson and links to the next lesson."},
            ],
            "bbm": ["Textbook", "Worksheets", "Whiteboard / projector"],
            "pak21": "Group work (Think-Pair-Share) to encourage collaboration.",
            "kbat": "Analysis and application questions during the main activity.",
            "emk": ["Values", "Language"],
            "pbd": "Observation and a short written task to assess understanding.",
            "remedial": "Pupils who struggle receive a simpler worksheet and one-to-one guidance.",
            "enrichment": "Pupils who finish early attempt an extension task with a higher-order question.",
            "reflection": "Review whether the objectives were met and note any adjustments for the next lesson.",
        },
        "ms": {
            "sk": "Standard kandungan berkaitan dengan %s." % topic,
            "sp": "Standard pembelajaran bagi %s yang sesuai dengan tahap kelas." % topic,
            "objectives": ["Pada akhir pelajaran, murid dapat menyatakan idea utama tentang %s." % topic,
                           "Pada akhir pelajaran, murid dapat mengaplikasikan %s dalam tugasan ringkas." % topic,
                           "Pada akhir pelajaran, murid dapat menerangkan %s dengan perkataan sendiri." % topic],
            "success_criteria": ["Murid dapat menyatakan sekurang-kurangnya 2 perkara utama tentang %s." % topic,
                                 "Murid dapat menyiapkan aktiviti yang diberi dengan bimbingan minimum."],
            "set_induksi": "Mulakan dengan sesi soal jawab ringkas untuk mencungkil pengetahuan sedia ada tentang %s." % topic,
            "activities": [
                {"step": "Langkah 1", "time": "10 min", "detail": "Guru memperkenalkan %s dengan contoh dan perbincangan kelas." % topic},
                {"step": "Langkah 2", "time": "15 min", "detail": "Murid bekerja dalam kumpulan untuk aktiviti berpandu tentang %s." % topic},
                {"step": "Langkah 3", "time": "10 min", "detail": "Kumpulan membentangkan hasil; guru membetulkan salah faham."},
                {"step": "Langkah 4", "time": "5 min", "detail": "Guru merumus pelajaran dan mengaitkan dengan pelajaran seterusnya."},
            ],
            "bbm": ["Buku teks", "Lembaran kerja", "Papan putih / projektor"],
            "pak21": "Kerja berkumpulan (Think-Pair-Share) untuk menggalakkan kerjasama.",
            "kbat": "Soalan analisis dan aplikasi semasa aktiviti utama.",
            "emk": ["Nilai", "Bahasa"],
            "pbd": "Pemerhatian dan tugasan bertulis ringkas untuk menilai kefahaman.",
            "remedial": "Murid yang lemah menerima lembaran kerja ringkas dan bimbingan individu.",
            "enrichment": "Murid yang pantas menyiapkan tugasan lanjutan dengan soalan aras tinggi.",
            "reflection": "Semak sama ada objektif tercapai dan catat penambahbaikan untuk pelajaran seterusnya.",
        },
        "ta": {
            "sk": "%s தொடர்பான உள்ளடக்கத் தரம்." % topic,
            "sp": "வகுப்பு நிலைக்கு ஏற்ப %s க்கான கற்றல் தரம்." % topic,
            "objectives": ["பாட முடிவில் மாணவர்கள் %s பற்றிய முக்கிய கருத்துகளைக் கூற முடியும்." % topic,
                           "பாட முடிவில் மாணவர்கள் %s ஐ எளிய பணியில் பயன்படுத்த முடியும்." % topic,
                           "பாட முடிவில் மாணவர்கள் %s ஐத் தங்கள் சொற்களில் விளக்க முடியும்." % topic],
            "success_criteria": ["மாணவர்கள் %s பற்றி குறைந்தது 2 முக்கிய கருத்துகளைக் கூறலாம்." % topic,
                                 "மாணவர்கள் வழங்கப்பட்ட செயலை குறைந்த வழிகாட்டலுடன் முடிக்கலாம்."],
            "set_induksi": "%s பற்றிய முன் அறிவைத் தூண்ட குறுகிய கேள்வி-பதில் அமர்வுடன் தொடங்குங்கள்." % topic,
            "activities": [
                {"step": "படி 1", "time": "10 நிமி", "detail": "ஆசிரியர் %s ஐ எடுத்துக்காட்டுகளுடன் அறிமுகப்படுத்துகிறார்." % topic},
                {"step": "படி 2", "time": "15 நிமி", "detail": "மாணவர்கள் %s பற்றி குழுவாக வழிகாட்டப்பட்ட செயலைச் செய்கிறார்கள்." % topic},
                {"step": "படி 3", "time": "10 நிமி", "detail": "குழுக்கள் முடிவுகளை வழங்குகின்றன; ஆசிரியர் தவறுகளைத் திருத்துகிறார்."},
                {"step": "படி 4", "time": "5 நிமி", "detail": "ஆசிரியர் பாடத்தைச் சுருக்கி அடுத்த பாடத்துடன் இணைக்கிறார்."},
            ],
            "bbm": ["பாடநூல்", "பயிற்சித் தாள்கள்", "வெள்ளைப் பலகை / திரைப்படி"],
            "pak21": "ஒத்துழைப்பை ஊக்குவிக்க குழு செயல்பாடு (Think-Pair-Share).",
            "kbat": "முக்கிய செயலின்போது பகுப்பாய்வு மற்றும் பயன்பாட்டு கேள்விகள்.",
            "emk": ["மதிப்புகள்", "மொழி"],
            "pbd": "புரிதலை மதிப்பிட கவனிப்பு மற்றும் குறுகிய எழுத்துப் பணி.",
            "remedial": "பின்தங்கிய மாணவர்களுக்கு எளிய பயிற்சித் தாளும் தனி வழிகாட்டலும்.",
            "enrichment": "முன்னேறிய மாணவர்கள் உயர்நிலை கேள்வியுடன் கூடிய நீட்டிப்பு பணியைச் செய்கிறார்கள்.",
            "reflection": "குறிக்கோள்கள் எட்டப்பட்டதா எனச் சரிபார்த்து அடுத்த பாடத்திற்கான மாற்றங்களைக் குறிக்கவும்.",
        },
    }.get(lang) or {
        "sk": "Content standard related to %s." % topic,
        "sp": "Learning standard for %s appropriate to the class level." % topic,
        "objectives": ["By the end of the lesson, pupils will be able to state the key ideas about %s." % topic],
        "success_criteria": ["Pupils can state at least 2 key points about %s." % topic],
        "set_induksi": "Begin with a short Q&A to activate prior knowledge about %s." % topic,
        "activities": [{"step": "Step 1", "time": "10 min", "detail": "Introduce %s with examples." % topic}],
        "bbm": ["Textbook", "Worksheets"],
        "pak21": "Group work.",
        "kbat": "Analysis questions.",
        "emk": ["Values"],
        "pbd": "Observation and written task.",
        "remedial": "Simpler worksheet for struggling pupils.",
        "enrichment": "Extension task for fast finishers.",
        "reflection": "Review objective attainment.",
    }
    return {
        "school": fields.get("school") or "SJK(T) Sepang",
        "teacher": fields.get("teacher") or "",
        "subject": subject,
        "class": cls,
        "date": fields.get("date") or "",
        "day": fields.get("day") or "",
        "duration": fields.get("duration") or "60 minit",
        "topic": topic,
        **T,
    }


def _normalise_rph(data, fields):
    """Merge generated/edited content with meta fields and coerce types."""
    keys = [k for k, _, _ in RPH_SECTIONS]
    out = {
        "school": fields.get("school") or data.get("school") or "SJK(T) Sepang",
        "teacher": fields.get("teacher") or data.get("teacher") or "",
        "subject": fields.get("subject") or data.get("subject") or "",
        "class": fields.get("class") or data.get("class") or "",
        "date": fields.get("date") or data.get("date") or "",
        "day": fields.get("day") or data.get("day") or "",
        "duration": fields.get("duration") or data.get("duration") or "60 minit",
        "topic": fields.get("topic") or data.get("topic") or "",
    }
    for key, _, kind in RPH_SECTIONS:
        val = data.get(key)
        if kind == "list":
            if isinstance(val, str):
                val = [x for x in (v.strip() for v in val.split("\n")) if x]
            if not isinstance(val, list):
                val = []
            out[key] = val
        elif kind == "steps":
            steps = val if isinstance(val, list) else []
            clean = []
            for s in steps:
                if isinstance(s, dict):
                    clean.append({"step": s.get("step", ""), "time": s.get("time", ""),
                                  "detail": s.get("detail", "")})
                else:
                    clean.append({"step": "", "time": "", "detail": str(s)})
            out[key] = clean
        else:
            out[key] = str(val or "")
    return out


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------
@bp.route("/")
@login_required
def index():
    lang_code = session.get("lang", "en")
    return render_template("rph.html", teacher=_teacher(),
                           sections=RPH_SECTIONS, meta=META_FIELDS, lang_code=lang_code,
                           sections_json=json.dumps(RPH_SECTIONS),
                           meta_json=json.dumps(META_FIELDS),
                           teacher_json=json.dumps(_teacher()))


@bp.route("/generate", methods=["POST"])
@login_required
def generate():
    fields = _json_body()
    lang = fields.get("lang") or session.get("lang", "en")
    data = _ai_rph(fields, lang)
    if data:
        rph = _normalise_rph(data, fields)
        source = "ai"
    else:
        rph = _offline_rph(fields, lang)
        source = "offline"
    return jsonify({"rph": rph, "source": source})


@bp.route("/regenerate", methods=["POST"])
@login_required
def regenerate():
    """Regenerate a single section in place."""
    fields = _json_body()
    lang = fields.get("lang") or session.get("lang", "en")
    rph = fields.get("rph") or {}
    section = fields.get("section")
    data = _ai_rph(fields, lang)
    if data and section in data:
        rph[section] = data[section]
        return jsonify({"ok": True, "value": data[section]})
    # offline fallback: regenerate from template for that section
    tmpl = _offline_rph(fields, lang)
    if section in tmpl:
        rph[section] = tmpl[section]
        return jsonify({"ok": True, "value": tmpl[section]})
    return jsonify({"error": "bad_section"}), 400


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------
def _build_response(rph, fmt):
    uid = session["user_id"]
    name = "RPH_%s_%s" % (rph.get("subject") or "Pelajaran", datetime.now().strftime("%Y%m%d_%H%M%S"))
    stem = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in name)[:60] or "RPH"
    if fmt == "pdf":
        out = _TMP / (uuid4().hex + ".pdf")
        build_rph_pdf(rph, out)
        data = out.read_bytes()
        out.unlink(missing_ok=True)
        return Response(data, mimetype="application/pdf",
                        headers={"Content-Disposition": f"attachment; filename={stem}.pdf"})
    if fmt == "docx":
        out = _TMP / (uuid4().hex + ".docx")
        build_rph_docx(rph, out)
        data = out.read_bytes()
        out.unlink(missing_ok=True)
        return Response(data,
                        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        headers={"Content-Disposition": f"attachment; filename={stem}.docx"})
    return jsonify({"error": "bad_format"}), 400


@bp.route("/export", methods=["POST"])
@login_required
def export():
    payload = _json_body()
    rph = _normalise_rph(payload.get("rph") or {}, payload.get("fields") or payload.get("rph") or {})
    return _build_response(rph, payload.get("format") or "pdf")


@bp.route("/save", methods=["POST"])
@login_required
def save():
    payload = _json_body()
    rph = _normalise_rph(payload.get("rph") or {}, payload.get("rph") or {})
    db = get_db()
    cur = db.execute(
        "INSERT INTO rph_documents (teacher_id, title, subject, class_name, rph_json) VALUES (?,?,?,?,?)",
        (session["user_id"], rph.get("topic") or "RPH", rph.get("subject") or "",
         rph.get("class") or "", json.dumps(rph, ensure_ascii=False)),
    )
    db.commit()
    rid = cur.lastrowid
    db.close()
    return jsonify({"ok": True, "id": rid})


@bp.route("/print/<int:rid>")
@login_required
def print_view(rid):
    db = get_db()
    row = db.execute(
        "SELECT rph_json FROM rph_documents WHERE id = ? AND teacher_id = ?",
        (rid, session["user_id"]),
    ).fetchone()
    db.close()
    if not row:
        return redirect(url_for("rph.index"))
    rph = json.loads(row["rph_json"])
    return render_template("rph_print.html", rph=rph, sections=RPH_SECTIONS, meta=META_FIELDS)
