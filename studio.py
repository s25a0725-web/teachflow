# -*- coding: utf-8 -*-
"""Document Studio: create, convert, edit, and template documents."""
import os
from pathlib import Path
from uuid import uuid4

from flask import (Blueprint, render_template, request, session, redirect, url_for,
                   flash, send_from_directory, jsonify)
from werkzeug.utils import secure_filename

from db import get_db
from views import login_required
from docbuild import (generate_content, build_docx, build_pptx, build_pdf,
                      convert_file, fill_template, content_to_text, parse_content_text,
                      extract_placeholders, libreoffice_available, ai_revise)
from smartgen import smart_generate

bp = Blueprint("studio", __name__)

_BASE = Path(__file__).resolve().parent
_UPLOAD_ROOT = Path(os.environ.get("TEACHFLOW_UPLOAD_ROOT", str(_BASE / "uploads")))
STUDIO_ROOT = _UPLOAD_ROOT / "studio"

MIME = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "pdf": "application/pdf",
    "csv": "text/csv",
}


def _out_dir(uid):
    d = STUDIO_ROOT / str(uid) / "outputs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _tpl_dir(uid):
    d = STUDIO_ROOT / str(uid) / "templates"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _build(content, doc_type, uid):
    ext = {"docx": ".docx", "pptx": ".pptx", "pdf": ".pdf"}[doc_type]
    name = uuid4().hex[:8] + ext
    out = _out_dir(uid) / name
    if doc_type == "docx":
        build_docx(content, out)
    elif doc_type == "pptx":
        build_pptx(content, out)
    else:
        build_pdf(content, out)
    return name


@bp.route("/studio")
@login_required
def index():
    uid = session["user_id"]
    db = get_db()
    rows = db.execute("SELECT * FROM studio_templates WHERE teacher_id=? ORDER BY id DESC", (uid,)).fetchall()
    db.close()
    tpl_list = []
    for t in rows:
        try:
            ph = extract_placeholders(_tpl_dir(uid) / t["stored_name"])
        except Exception:
            ph = []
        tpl_list.append((t, ph))
    return render_template("studio.html", templates=tpl_list, lo=libreoffice_available())


@bp.route("/studio/create", methods=["POST"])
@login_required
def create():
    uid = session["user_id"]
    topic = request.form.get("topic", "").strip()
    doc_type = request.form.get("doc_type", "docx")
    lang = request.form.get("lang", "en")
    instructions = request.form.get("instructions", "").strip()
    content = generate_content(topic, doc_type, lang, instructions)
    name = _build(content, doc_type, uid)
    return jsonify({"link": url_for("studio.download", fname=name),
                    "text": content_to_text(content)})


@bp.route("/studio/smart", methods=["POST"])
@login_required
def smart():
    uid = session["user_id"]
    data = request.get_json(silent=True) or {}
    text = data.get("ask", "")
    out = smart_generate(text, _out_dir(uid))
    return jsonify({"link": url_for("studio.download", fname=out["fname"]),
                    "preview": out["preview"], "kind": out["kind"], "label": out["label"]})


@bp.route("/studio/export", methods=["POST"])
@login_required
def export():
    uid = session["user_id"]
    data = request.get_json(silent=True) or {}
    text = data.get("text", "")
    doc_type = data.get("doc_type", "docx")
    content = parse_content_text(text)
    name = _build(content, doc_type, uid)
    return jsonify({"link": url_for("studio.download", fname=name)})


@bp.route("/studio/ai-fix", methods=["POST"])
@login_required
def ai_fix():
    data = request.get_json(silent=True) or {}
    text = data.get("text", "")
    instruction = data.get("instruction", "")
    lang = data.get("lang", "en")
    revised = ai_revise(text, instruction, lang)
    if revised:
        return jsonify({"text": revised})
    return jsonify({"text": text, "note": "no_ai"})


@bp.route("/studio/convert", methods=["POST"])
@login_required
def convert():
    uid = session["user_id"]
    f = request.files.get("file")
    target = request.form.get("target", "pdf")
    if not f or not f.filename:
        return jsonify({"error": "no_file"})
    safe = secure_filename(f.filename) or f"{uuid4().hex}.bin"
    stored = f"{uuid4().hex}_{safe}"
    out_dir = _out_dir(uid)
    f.save(out_dir / stored)
    try:
        out_name, _mime = convert_file(out_dir / stored, f.filename, target)
    except RuntimeError as e:
        return jsonify({"error": str(e)})
    except Exception:
        return jsonify({"error": "conversion failed"})
    return jsonify({"link": url_for("studio.download", fname=out_name)})


@bp.route("/studio/download/<path:fname>")
@login_required
def download(fname):
    uid = session["user_id"]
    return send_from_directory(str(_out_dir(uid)), fname)


# --------------------------------------------------------------------------
# Templates
# --------------------------------------------------------------------------
@bp.route("/studio/templates/upload", methods=["POST"])
@login_required
def tpl_upload():
    uid = session["user_id"]
    f = request.files.get("file")
    name = request.form.get("name", "").strip()
    if not f or not f.filename:
        flash("chat_no_file", "error")
        return redirect(url_for("studio.index"))
    ext = Path(f.filename).suffix.lower()
    if ext not in (".docx", ".pptx"):
        flash("bad_template", "error")
        return redirect(url_for("studio.index"))
    safe = secure_filename(f.filename) or f"{uuid4().hex}.bin"
    stored = f"{uuid4().hex}_{safe}"
    f.save(_tpl_dir(uid) / stored)
    db = get_db()
    db.execute("INSERT INTO studio_templates (teacher_id, name, stored_name, type) VALUES (?, ?, ?, ?)",
               (uid, name or f.filename, stored, ext[1:]))
    db.commit()
    db.close()
    flash("settings_saved", "success")
    return redirect(url_for("studio.index"))


@bp.route("/studio/templates/<int:tid>/delete", methods=["POST"])
@login_required
def tpl_delete(tid):
    uid = session["user_id"]
    db = get_db()
    row = db.execute("SELECT stored_name FROM studio_templates WHERE id=? AND teacher_id=?", (tid, uid)).fetchone()
    if row:
        try:
            (_tpl_dir(uid) / row["stored_name"]).unlink(missing_ok=True)
        except Exception:
            pass
        db.execute("DELETE FROM studio_templates WHERE id=?", (tid,))
        db.commit()
    db.close()
    flash("deleted", "success")
    return redirect(url_for("studio.index"))


@bp.route("/studio/templates/<int:tid>/rename", methods=["POST"])
@login_required
def tpl_rename(tid):
    uid = session["user_id"]
    name = request.form.get("name", "").strip()
    db = get_db()
    db.execute("UPDATE studio_templates SET name=? WHERE id=? AND teacher_id=?", (name, tid, uid))
    db.commit()
    db.close()
    return redirect(url_for("studio.index"))


@bp.route("/studio/templates/<int:tid>/generate", methods=["POST"])
@login_required
def tpl_generate(tid):
    uid = session["user_id"]
    db = get_db()
    row = db.execute("SELECT * FROM studio_templates WHERE id=? AND teacher_id=?", (tid, uid)).fetchone()
    db.close()
    if not row:
        return redirect(url_for("studio.index"))
    src = _tpl_dir(uid) / row["stored_name"]
    topic = request.form.get("topic", "").strip()
    from datetime import date
    data = {}
    for p in extract_placeholders(src):
        manual = request.form.get("ph_" + p, "").strip()
        if manual:
            data[p] = manual
        else:
            k = (p or "").lower().strip()
            if k in ("date", "tarikh", "tanggal", "தேதி"):
                data[p] = date.today().strftime("%d/%m/%Y")
            elif k in ("title", "topic", "tajuk", "topik", "subject", "subjek", "தலைப்பு"):
                data[p] = topic
            else:
                data[p] = ""
    ext = ".pptx" if row["type"] == "pptx" else ".docx"
    out_name = f"filled_{uuid4().hex[:8]}{ext}"
    out = _out_dir(uid) / out_name
    try:
        fill_template(src, data, out)
    except Exception:
        flash("bad_template", "error")
        return redirect(url_for("studio.index"))
    return redirect(url_for("studio.download", fname=out_name))
