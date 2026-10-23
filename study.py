# -*- coding: utf-8 -*-
"""Study Studio (NotebookLM-style): notebooks, sources, chat, and generation."""
import json
import math
import os
import re
from pathlib import Path
from uuid import uuid4

from flask import (Blueprint, render_template, request, session, redirect, url_for,
                   flash, send_from_directory, jsonify, abort)
from werkzeug.utils import secure_filename

from db import get_db
from views import login_required
from docbuild import build_docx, build_pdf
from study_engine import (extract_pages, chunk_text, retrieve, answer, make_quiz, make_flashcards,
                          make_mindmap, make_booklet_content, summarize, key_terms,
                          ai_answer, ai_generate)

bp = Blueprint("study", __name__)

_BASE = Path(__file__).resolve().parent
_UPLOAD_ROOT = Path(os.environ.get("TEACHFLOW_UPLOAD_ROOT", str(_BASE / "uploads")))
STUDY_ROOT = _UPLOAD_ROOT / "study"

KIND_EXT = {"pdf": "pdf", "docx": "docx", "pptx": "pptx", "txt": "txt",
            "jpg": "image", "jpeg": "image", "png": "image", "webp": "image", "bmp": "image",
            "md": "txt", "csv": "txt"}

VOICES = {"en": "en-US-AriaNeural", "ms": "ms-MY-YasminNeural", "ta": "ta-IN-PallaviNeural"}


def _src_dir(uid):
    d = STUDY_ROOT / str(uid) / "sources"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _out_dir(uid):
    d = STUDY_ROOT / str(uid) / "outputs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _notebook_chunks(uid, notebook_id):
    db = get_db()
    rows = db.execute(
        "SELECT c.text, c.page, s.name FROM chunks c JOIN sources s ON s.id=c.source_id "
        "WHERE c.teacher_id=? AND s.notebook_id=?", (uid, notebook_id)).fetchall()
    db.close()
    return [{"text": r["text"], "source": r["name"], "page": r["page"]} for r in rows]


# --------------------------------------------------------------------------
# Pages
# --------------------------------------------------------------------------
@bp.route("/study")
@login_required
def index():
    uid = session["user_id"]
    db = get_db()
    nb = db.execute("SELECT n.*, (SELECT COUNT(*) FROM sources s WHERE s.notebook_id=n.id) AS cnt "
                    "FROM notebooks n WHERE n.teacher_id=? ORDER BY n.id DESC", (uid,)).fetchall()
    db.close()
    return render_template("study.html", notebooks=nb)


@bp.route("/study/items/<int:nbid>")
@login_required
def items(nbid):
    uid = session["user_id"]
    db = get_db()
    rows = db.execute("SELECT * FROM study_items WHERE teacher_id=? AND notebook_id=? ORDER BY id DESC",
                      (uid, nbid)).fetchall()
    db.close()
    out = [{"id": r["id"], "kind": r["kind"], "title": r["title"]} for r in rows]
    return jsonify(out)


@bp.route("/study/notebook/<int:nbid>")
@login_required
def notebook_data(nbid):
    uid = session["user_id"]
    db = get_db()
    srcs = db.execute("SELECT id, name, kind, page_count FROM sources WHERE notebook_id=? AND teacher_id=? ORDER BY id DESC",
                      (nbid, uid)).fetchall()
    its = db.execute("SELECT id, kind, title FROM study_items WHERE notebook_id=? AND teacher_id=? ORDER BY id DESC",
                     (nbid, uid)).fetchall()
    db.close()
    return jsonify({"sources": [dict(r) for r in srcs], "items": [dict(r) for r in its]})


# --------------------------------------------------------------------------
# Notebooks & sources
# --------------------------------------------------------------------------
@bp.route("/study/notebooks", methods=["POST"])
@login_required
def create_notebook():
    uid = session["user_id"]
    name = request.form.get("name", "").strip()
    if not name:
        flash("gen_empty", "error")
        return redirect(url_for("study.index"))
    db = get_db()
    db.execute("INSERT INTO notebooks (teacher_id, name) VALUES (?, ?)", (uid, name))
    db.commit()
    db.close()
    return redirect(url_for("study.index"))


@bp.route("/study/notebooks/<int:nbid>/delete", methods=["POST"])
@login_required
def delete_notebook(nbid):
    uid = session["user_id"]
    db = get_db()
    rows = db.execute("SELECT stored_name, kind FROM sources WHERE notebook_id=? AND teacher_id=?",
                      (nbid, uid)).fetchall()
    for r in rows:
        if r["kind"] != "url":
            try:
                (_src_dir(uid) / r["stored_name"]).unlink(missing_ok=True)
            except Exception:
                pass
    db.execute("DELETE FROM chunks WHERE teacher_id=? AND source_id IN (SELECT id FROM sources WHERE notebook_id=?)",
               (uid, nbid))
    db.execute("DELETE FROM sources WHERE notebook_id=? AND teacher_id=?", (nbid, uid))
    db.execute("DELETE FROM study_items WHERE notebook_id=? AND teacher_id=?", (nbid, uid))
    db.execute("DELETE FROM notebooks WHERE id=? AND teacher_id=?", (nbid, uid))
    db.commit()
    db.close()
    return redirect(url_for("study.index"))


@bp.route("/study/notebooks/<int:nbid>/sources", methods=["POST"])
@login_required
def add_source(nbid):
    uid = session["user_id"]
    db = get_db()
    nb = db.execute("SELECT id FROM notebooks WHERE id=? AND teacher_id=?", (nbid, uid)).fetchone()
    if not nb:
        db.close()
        abort(404)

    url = request.form.get("url", "").strip()
    f = request.files.get("file")
    if url:
        kind, name, stored = "url", url[:80], url
    elif f and f.filename:
        ext = Path(f.filename).suffix.lower().lstrip(".")
        kind = KIND_EXT.get(ext)
        if not kind:
            db.close()
            flash("bad_source", "error")
            return redirect(url_for("study.index"))
        safe = secure_filename(f.filename) or f"{uuid4().hex}.bin"
        stored = f"{uuid4().hex}_{safe}"
        name = f.filename
        f.save(_src_dir(uid) / stored)
    else:
        db.close()
        flash("chat_no_file", "error")
        return redirect(url_for("study.index"))

    path = stored if kind != "url" else url
    try:
        pages = extract_pages(_src_dir(uid) / path if kind != "url" else path, kind)
    except Exception:
        pages = []

    sid = db.execute(
        "INSERT INTO sources (notebook_id, teacher_id, name, stored_name, kind, page_count) VALUES (?,?,?,?,?,?)",
        (nbid, uid, name, stored, kind, max(1, len(pages)))).lastrowid
    for (page, text) in pages:
        for i, ch in enumerate(chunk_text(text)):
            db.execute("INSERT INTO chunks (source_id, teacher_id, idx, page, text) VALUES (?,?,?,?,?)",
                       (sid, uid, i, page, ch))
    db.commit()
    db.close()
    return redirect(url_for("study.index"))


@bp.route("/study/sources/<int:sid>/delete", methods=["POST"])
@login_required
def delete_source(sid):
    uid = session["user_id"]
    db = get_db()
    r = db.execute("SELECT stored_name, kind FROM sources WHERE id=? AND teacher_id=?", (sid, uid)).fetchone()
    if r:
        if r["kind"] != "url":
            try:
                (_src_dir(uid) / r["stored_name"]).unlink(missing_ok=True)
            except Exception:
                pass
        db.execute("DELETE FROM chunks WHERE source_id=?", (sid,))
        db.execute("DELETE FROM sources WHERE id=?", (sid,))
        db.commit()
    db.close()
    return redirect(url_for("study.index"))


# --------------------------------------------------------------------------
# Chat
# --------------------------------------------------------------------------
@bp.route("/study/chat", methods=["POST"])
@login_required
def chat():
    uid = session["user_id"]
    data = request.get_json(silent=True) or {}
    nbid = data.get("notebook_id")
    question = (data.get("question") or "").strip()
    lang = data.get("lang", "en")
    if not nbid or not question:
        return jsonify({"error": "missing"})
    chunks = _notebook_chunks(uid, nbid)
    res = answer(chunks, question, top_k=6, max_sents=3)
    if not res["found"]:
        return jsonify({"answer": "", "note": "empty",
                        "citations": [], "msg": "no_match"})
    cites = res["cites"]
    ai = ai_answer(question, cites, lang)
    if ai and isinstance(ai, dict) and ai.get("answer"):
        return jsonify({"answer": ai["answer"], "note": "ai",
                        "citations": [{"source": c["source"], "page": c["page"],
                                       "snippet": c["text"][:160]} for c in cites]})
    return jsonify({"answer": res["answer"], "note": "offline",
                    "citations": [{"source": c["source"], "page": c["page"],
                                   "snippet": c["text"][:160]} for c in cites]})


# --------------------------------------------------------------------------
# Generate
# --------------------------------------------------------------------------
def _content_bullets(payload, kind):
    if kind == "quiz":
        qs = payload.get("questions") or []
        body = [f"Q{i+1}. {q['q']}" + (f"  ({', '.join(q['options'])})" if q.get("options") else "")
                for i, q in enumerate(qs)]
        ans = [f"Q{i+1}. {q['a']}" for i, q in enumerate(qs)]
        return [{"heading": "Questions", "bullets": body}, {"heading": "Answer Key", "bullets": ans}]
    if kind == "summary":
        return [{"heading": "Summary", "bullets": [payload.get("summary", "")]}]
    if kind == "mindmap":
        lines = [payload.get("central", "")]
        for b in payload.get("branches", []):
            lines.append("## " + b["node"])
            for l in b.get("leaves", []):
                lines.append("- " + l)
        return [{"heading": "Mind Map", "bullets": lines}]
    if kind == "flashcards":
        return [{"heading": "Flashcards", "bullets": [f"{c['front']}  ->  {c['back']}" for c in payload.get("cards", [])]}]
    if kind == "booklet":
        return payload.get("sections", [])
    return [{"heading": "", "bullets": [json.dumps(payload)[:2000]]}]


@bp.route("/study/generate", methods=["POST"])
@login_required
def generate():
    uid = session["user_id"]
    data = request.get_json(silent=True) or {}
    nbid = data.get("notebook_id")
    kind = data.get("kind", "summary")
    lang = data.get("lang", "en")
    level = data.get("level", "medium")
    length = data.get("length", "medium")
    title = data.get("title", "").strip()

    chunks = _notebook_chunks(uid, nbid) if nbid else []
    text = "\n".join(c["text"] for c in chunks)
    if not text.strip():
        return jsonify({"error": "no_text"})

    payload = ai_generate(kind, text, lang, level, length)
    if not payload or not isinstance(payload, dict):
        payload = _offline_generate(kind, text, lang, level, length, title)

    if not title:
        title = payload.get("title") or payload.get("central") or "Study " + kind

    if kind == "infographic":
        payload["svg"] = _infographic_svg(payload)
    elif kind == "mindmap":
        payload["svg"] = _mindmap_svg(payload)

    # save item
    db = get_db()
    iid = db.execute("INSERT INTO study_items (teacher_id, notebook_id, kind, title, content) VALUES (?,?,?,?,?)",
                     (uid, nbid, kind, title, json.dumps(payload, ensure_ascii=False))).lastrowid
    db.commit()
    db.close()

    links = _export(kind, payload, uid, lang, title)
    resp = {"item_id": iid, "kind": kind, "title": title, "payload": payload, "links": links}
    if kind == "audio":
        resp["audio_url"] = url_for("study.audio", iid=iid)
    return jsonify(resp)


def _offline_generate(kind, text, lang, level, length, title):
    if kind == "quiz":
        return {"questions": make_quiz(text, lang, level, length)}
    if kind == "flashcards":
        return {"cards": make_flashcards(text, 10)}
    if kind == "mindmap":
        return make_mindmap(title or "Topic", text, 8)
    if kind == "summary":
        return {"summary": summarize(text, length)}
    if kind == "audio":
        return {"summary": summarize(text, length), "lang": lang}
    if kind == "booklet":
        return make_booklet_content(title or "Study Booklet", text, lang, level, length)
    if kind == "infographic":
        return {"title": title or "Infographic", "terms": key_terms(text, 8),
                "summary": summarize(text, "short"), "lang": lang}
    return {"text": text[:2000]}


def _export(kind, payload, uid, lang, title):
    links = []
    out = _out_dir(uid)
    safe_title = re.sub(r"[^A-Za-z0-9]+", "_", title or "doc")[:40] or "doc"
    content = {"title": title, "sections": _content_bullets(payload, kind)}

    if kind in ("quiz", "summary", "flashcards", "booklet"):
        d = out / f"{uuid4().hex[:8]}_{safe_title}.docx"
        build_docx(content, d)
        links.append({"fmt": "docx", "label": "DOCX", "url": url_for("study.download", fname=d.name)})
        p = out / f"{uuid4().hex[:8]}_{safe_title}.pdf"
        build_pdf(content, p)
        links.append({"fmt": "pdf", "label": "PDF", "url": url_for("study.download", fname=p.name)})

    if kind == "infographic":
        if payload.get("svg"):
            svg = out / f"{uuid4().hex[:8]}_{safe_title}.svg"
            svg.write_text(payload["svg"], encoding="utf-8")
            links.append({"fmt": "svg", "label": "SVG", "url": url_for("study.download", fname=svg.name)})
        png = out / f"{uuid4().hex[:8]}_{safe_title}.png"
        try:
            _infographic_png(payload, png)
            links.append({"fmt": "png", "label": "PNG", "url": url_for("study.download", fname=png.name)})
        except Exception:
            pass
        p = out / f"{uuid4().hex[:8]}_{safe_title}.pdf"
        _build_infographic_pdf(payload, p)
        links.append({"fmt": "pdf", "label": "PDF", "url": url_for("study.download", fname=p.name)})

    if kind == "mindmap":
        if payload.get("svg"):
            svg = out / f"{uuid4().hex[:8]}_{safe_title}.svg"
            svg.write_text(payload["svg"], encoding="utf-8")
            links.append({"fmt": "svg", "label": "SVG", "url": url_for("study.download", fname=svg.name)})
        p = out / f"{uuid4().hex[:8]}_{safe_title}.pdf"
        _build_mindmap_pdf(payload, p)
        links.append({"fmt": "pdf", "label": "PDF", "url": url_for("study.download", fname=p.name)})

    return links


def _build_infographic_pdf(payload, out_path):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(str(out_path), pagesize=A4)
    w, h = A4
    c.setFillColorRGB(0.31, 0.27, 0.9)
    c.rect(0, h - 90, w, 90, fill=1, stroke=0)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 22)
    c.drawString(40, h - 55, payload.get("title", "Infographic")[:60])
    y = h - 140
    c.setFillColorRGB(0.1, 0.1, 0.1)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(40, y, "Key terms")
    y -= 20
    c.setFont("Helvetica", 11)
    for t in payload.get("terms", [])[:8]:
        c.drawString(40, y, "- " + t)
        y -= 18
    y -= 10
    c.setFont("Helvetica-Bold", 13)
    c.drawString(40, y, "Summary")
    y -= 18
    c.setFont("Helvetica", 10)
    for line in _wrap(payload.get("summary", ""), 95)[:12]:
        c.drawString(40, y, line)
        y -= 14
    c.save()


def _build_mindmap_pdf(payload, out_path):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(str(out_path), pagesize=A4)
    w, h = A4
    cx, cy = w / 2, h / 2 + 120
    c.setFont("Helvetica-Bold", 16)
    c.setFillColorRGB(0.31, 0.27, 0.9)
    c.drawCentredString(cx, cy, payload.get("central", "Topic"))
    branches = payload.get("branches", [])
    for i, b in enumerate(branches):
        ang = (i / max(1, len(branches))) * 6.283
        x = cx + 200 * math.cos(ang)
        y = cy + 120 * math.sin(ang)
        c.setStrokeColorRGB(0.5, 0.5, 0.5)
        c.line(cx, cy - 5, x, y)
        c.setFillColorRGB(0.1, 0.1, 0.1)
        c.setFont("Helvetica-Bold", 11)
        c.drawCentredString(x, y, b["node"][:22])
    c.save()


def _wrap(text, n):
    words = (text or "").split()
    lines, cur = [], ""
    for w in words:
        if len(cur) + len(w) + 1 > n:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return lines


def _svg_esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _infographic_svg(p):
    title = p.get("title", "Infographic")
    stats = p.get("stats", [])
    terms = p.get("terms", [])
    summary = p.get("summary", "")
    W, H = 800, 1000
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="Segoe UI, sans-serif">',
             f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
             f'<rect x="0" y="0" width="{W}" height="110" fill="#4f46e5"/>',
             f'<text x="40" y="65" fill="#ffffff" font-size="34" font-weight="bold">{_svg_esc(title[:44])}</text>']
    sx = 40
    for label, val in stats:
        parts.append(f'<rect x="{sx}" y="130" width="220" height="70" rx="10" fill="#eef2ff"/>')
        parts.append(f'<text x="{sx+20}" y="160" font-size="26" font-weight="bold" fill="#312e81">{_svg_esc(str(val))}</text>')
        parts.append(f'<text x="{sx+20}" y="185" font-size="14" fill="#64748b">{_svg_esc(str(label))}</text>')
        sx += 240
    parts.append('<text x="40" y="245" font-size="20" font-weight="bold" fill="#111827">Key ideas</text>')
    cx, cy = 40, 268
    for t in terms:
        w = min(300, 24 + len(t) * 9)
        parts.append(f'<rect x="{cx}" y="{cy}" width="{w}" height="34" rx="17" fill="#4f46e5"/>')
        parts.append(f'<text x="{cx+16}" y="{cy+22}" font-size="14" fill="#ffffff">{_svg_esc(t[:28])}</text>')
        cx += w + 10
        if cx > 740:
            cx = 40
            cy += 44
    sy = cy + 70
    parts.append(f'<text x="40" y="{sy}" font-size="20" font-weight="bold" fill="#111827">Summary</text>')
    ly = sy + 28
    for line in _wrap(summary, 88)[:14]:
        parts.append(f'<text x="40" y="{ly}" font-size="15" fill="#334155">{_svg_esc(line)}</text>')
        ly += 24
    parts.append('</svg>')
    return "".join(parts)


def _mindmap_svg(p):
    central = p.get("central", "Topic")
    branches = p.get("branches", [])
    W, H = 900, 700
    cx, cy = W / 2, H / 2
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="Segoe UI, sans-serif">',
             f'<rect width="{W}" height="{H}" fill="#f8fafc"/>',
             f'<circle cx="{cx}" cy="{cy}" r="62" fill="#4f46e5"/>',
             f'<text x="{cx}" y="{cy}" fill="#ffffff" font-size="15" font-weight="bold" text-anchor="middle">{_svg_esc(central[:18])}</text>']
    n = max(1, len(branches))
    for i, b in enumerate(branches):
        ang = -math.pi / 2 + (i * 2 * math.pi / n)
        x = cx + 260 * math.cos(ang)
        y = cy + 180 * math.sin(ang)
        parts.append(f'<line x1="{cx}" y1="{cy}" x2="{x}" y2="{y}" stroke="#c7d2fe" stroke-width="2"/>')
        parts.append(f'<rect x="{x-72}" y="{y-20}" width="144" height="40" rx="8" fill="#6366f1"/>')
        parts.append(f'<text x="{x}" y="{y+5}" fill="#ffffff" font-size="13" text-anchor="middle">{_svg_esc(b["node"][:16])}</text>')
        for j, leaf in enumerate(b.get("leaves", [])[:3]):
            parts.append(f'<text x="{x}" y="{y + 34 + j*20}" font-size="11" fill="#475569" text-anchor="middle">{_svg_esc(leaf[:34])}</text>')
    parts.append('</svg>')
    return "".join(parts)


def _pil_font(size):
    from PIL import ImageFont
    for p in ("C:/Windows/Fonts/Nirmala.ttf", "C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf"):
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _infographic_png(p, out_path):
    from PIL import Image, ImageDraw
    W, H = 800, 1000
    img = Image.new("RGB", (W, H), "#ffffff")
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 110], fill="#4f46e5")
    fb = _pil_font(32)
    f = _pil_font(16)
    fs = _pil_font(22)
    fc = _pil_font(26)
    d.text((40, 40), (p.get("title") or "Infographic")[:40], font=fb, fill="#ffffff")
    sx = 40
    for label, val in p.get("stats", []):
        d.rounded_rectangle([sx, 130, sx + 220, 200], radius=10, fill="#eef2ff")
        d.text((sx + 20, 145), str(val), font=fc, fill="#312e81")
        d.text((sx + 20, 175), str(label), font=f, fill="#64748b")
        sx += 240
    d.text((40, 235), "Key ideas", font=fs, fill="#111827")
    cx, cy = 40, 270
    for t in p.get("terms", []):
        w = min(300, 24 + len(t) * 9)
        d.rounded_rectangle([cx, cy, cx + w, cy + 34], radius=17, fill="#4f46e5")
        d.text((cx + 16, cy + 9), t[:28], font=f, fill="#ffffff")
        cx += w + 10
        if cx > 740:
            cx = 40
            cy += 44
    sy = cy + 70
    d.text((40, sy), "Summary", font=fs, fill="#111827")
    ly = sy + 28
    for line in _wrap(p.get("summary", ""), 88)[:14]:
        d.text((40, ly), line, font=f, fill="#334155")
        ly += 24
    img.save(str(out_path))


# --------------------------------------------------------------------------
# Save quiz to bank
# --------------------------------------------------------------------------
@bp.route("/study/save-quiz", methods=["POST"])
@login_required
def save_quiz():
    uid = session["user_id"]
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "Study Quiz").strip()
    subject = (data.get("subject") or "").strip()
    topic = (data.get("topic") or title).strip()
    lang = data.get("lang", "en")
    questions = data.get("questions") or []
    if not questions:
        return jsonify({"error": "no questions"})
    db = get_db()
    db.execute("INSERT INTO quizzes (teacher_id, title, subject, topic, language, questions_json) VALUES (?,?,?,?,?,?)",
               (uid, title, subject, topic, lang, json.dumps(questions, ensure_ascii=False)))
    db.commit()
    db.close()
    return jsonify({"ok": True})


# --------------------------------------------------------------------------
# Download / views
# --------------------------------------------------------------------------
@bp.route("/study/download/<path:fname>")
@login_required
def download(fname):
    uid = session["user_id"]
    return send_from_directory(str(_out_dir(uid)), fname)


@bp.route("/study/flashcards/<int:iid>")
@login_required
def flashcards(iid):
    uid = session["user_id"]
    db = get_db()
    item = db.execute("SELECT * FROM study_items WHERE id=? AND teacher_id=?", (iid, uid)).fetchone()
    db.close()
    if not item:
        abort(404)
    payload = json.loads(item["content"] or "{}")
    cards = payload.get("cards", [])
    return render_template("study_flashcards.html", cards=cards, title=item["title"])


@bp.route("/study/audio/<int:iid>")
@login_required
def audio(iid):
    uid = session["user_id"]
    db = get_db()
    item = db.execute("SELECT * FROM study_items WHERE id=? AND teacher_id=?", (iid, uid)).fetchone()
    db.close()
    if not item:
        abort(404)
    payload = json.loads(item["content"] or "{}")
    text = payload.get("summary") or payload.get("text") or item["title"] or ""
    lang = payload.get("lang", "en")
    voice = VOICES.get(lang, "en-US-AriaNeural")
    out = _out_dir(uid) / f"audio_{iid}.mp3"
    if not out.exists():
        try:
            import asyncio
            import edge_tts
            asyncio.run(edge_tts.Communicate(text[:4000], voice).save(str(out)))
        except Exception:
            abort(500, "audio_generation_failed")
    return send_from_directory(str(_out_dir(uid)), out.name)


@bp.route("/study/items/<int:iid>/delete", methods=["POST"])
@login_required
def delete_item(iid):
    uid = session["user_id"]
    db = get_db()
    db.execute("DELETE FROM study_items WHERE id=? AND teacher_id=?", (iid, uid))
    db.commit()
    db.close()
    return jsonify({"ok": True})
