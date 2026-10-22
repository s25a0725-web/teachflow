# -*- coding: utf-8 -*-
"""Documents module: upload any file, organize in folders, summarize, edit, e-sign."""
import base64
import os
import re
import zipfile
from pathlib import Path
from uuid import uuid4

from flask import (
    Blueprint, render_template, request, redirect, url_for, session, flash,
    send_from_directory, abort,
)
from werkzeug.utils import secure_filename

from db import get_db
from views import login_required

bp = Blueprint("documents", __name__)

BASE = Path(__file__).resolve().parent
UPLOAD_ROOT = Path(os.environ.get("TEACHFLOW_UPLOAD_ROOT", str(BASE / "uploads")))
DOC_ROOT = UPLOAD_ROOT / "documents"
SIG_DIR = UPLOAD_ROOT / "signatures"
DOC_ROOT.mkdir(parents=True, exist_ok=True)
SIG_DIR.mkdir(parents=True, exist_ok=True)

# Extractive-summarization stopwords (English + Malay)
STOPWORDS = set("""
a about above after again all am an and any are as at be because been before being
below between both but by can did do does doing down during each few for from
further had has have having he her here hers herself him himself his how i if in
into is it its itself just me more most my myself no nor not now of off on once
only or other our ours ourselves out over own same she should so some such than
that the their theirs them themselves then there these they this those through
to too under until up very was we were what when where which while who whom why
will with you your yours yourself yourselves dan yang di ke dari untuk pada
dengan adalah ini itu atau dalam akan kepada sebagai tidak juga boleh ada mereka
kita saya anda kami dia ialah telah bagi serta tetapi oleh kerana setiap antara
lain seperti selepas sebelum lebih kurang sahaja pun hanya sangat melalui apabila
maka supaya jika bila mana apa siapa bagaimana mengapa
""".split())


def _user_dir(teacher_id):
    d = DOC_ROOT / str(teacher_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _save_signature(data_url):
    """Decode a PNG data URL into a file; return the stored filename or None."""
    if not data_url or "," not in data_url:
        return None
    try:
        data = base64.b64decode(data_url.split(",", 1)[1])
    except Exception:
        return None
    if not data:
        return None
    fname = f"{uuid4().hex}.png"
    (SIG_DIR / fname).write_bytes(data)
    return fname


def _signer_identity():
    db = get_db()
    u = db.execute("SELECT email FROM users WHERE id=?", (session["user_id"],)).fetchone()
    db.close()
    return u["email"] if u else ""


# --------------------------------------------------------------------------
# Text extraction (PDF via pypdf, DOCX via zipfile, text formats directly)
# --------------------------------------------------------------------------
def extract_docx(path):
    try:
        with zipfile.ZipFile(path) as z:
            xml = z.read("word/document.xml").decode("utf-8", "ignore")
    except Exception:
        return ""
    xml = re.sub(r"</w:p>", "\n", xml)
    xml = re.sub(r"<w:tab[^>]*/>", "\t", xml)
    xml = re.sub(r"<[^>]+>", "", xml)
    return xml


def extract_text(doc):
    path = _user_dir(doc["teacher_id"]) / doc["stored_name"]
    name = (doc["stored_name"] or "").lower()
    mime = (doc["mime_type"] or "").lower()
    try:
        if name.endswith(".pdf") or mime == "application/pdf":
            from pypdf import PdfReader
            reader = PdfReader(str(path))
            parts = [page.extract_text() or "" for page in reader.pages]
            return "\n".join(parts)
        if name.endswith(".docx") or "wordprocessingml" in mime:
            return extract_docx(path)
        if name.endswith((".txt", ".md", ".csv", ".html", ".htm", ".json", ".xml", ".py", ".log")):
            return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""
    return ""


def summarize_text(text, max_sentences=4):
    """Extractive summarizer: rank sentences by word frequency, keep top N in order."""
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return ""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 20]
    if not sentences:
        sentences = [text[:400]]
    words = re.findall(r"[A-Za-z\u00C0-\u024F0-9']+", text.lower())
    freq = {}
    for w in words:
        if w in STOPWORDS or len(w) < 3:
            continue
        freq[w] = freq.get(w, 0) + 1
    if not freq:
        return " ".join(sentences[:max_sentences])

    def score(s):
        ws = re.findall(r"[A-Za-z\u00C0-\u024F0-9']+", s.lower())
        if not ws:
            return 0.0
        return sum(freq.get(w, 0) for w in ws) / len(ws)

    top = sorted(sentences, key=score, reverse=True)[:max_sentences]
    ordered = sorted(top, key=lambda s: sentences.index(s))
    return " ".join(ordered)


# --------------------------------------------------------------------------
# Documents list + upload + folders
# --------------------------------------------------------------------------
@bp.route("/documents", methods=["GET", "POST"])
@login_required
def documents():
    uid = session["user_id"]
    if request.method == "POST":
        f = request.files.get("file")
        title = request.form.get("title", "").strip()
        folder_id = request.form.get("folder_id") or None
        if folder_id:
            folder_id = int(folder_id)
        if f and f.filename:
            orig = f.filename
            safe = secure_filename(orig) or f"{uuid4().hex}.bin"
            stored = f"{uuid4().hex}_{safe}"
            f.save(_user_dir(uid) / stored)
            db = get_db()
            db.execute(
                "INSERT INTO documents (teacher_id, title, original_name, stored_name, mime_type, folder_id) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (uid, title or orig, orig, stored, f.mimetype or "", folder_id),
            )
            db.commit()
            db.close()
            flash("doc_uploaded", "success")
        return redirect(url_for("documents.documents"))

    db = get_db()
    folders = db.execute(
        "SELECT f.*, (SELECT COUNT(*) FROM documents d WHERE d.folder_id = f.id) AS n "
        "FROM folders f WHERE f.teacher_id = ? ORDER BY f.name", (uid,)).fetchall()
    folder_filter = request.args.get("folder")
    base_sql = (
        "SELECT d.*, f.name AS folder_name, "
        "(SELECT COUNT(*) FROM signatures s WHERE s.document_id = d.id) AS n_sig "
        "FROM documents d LEFT JOIN folders f ON f.id = d.folder_id "
        "WHERE d.teacher_id = ?"
    )
    if folder_filter:
        docs = db.execute(base_sql + " AND d.folder_id = ? ORDER BY d.id DESC",
                          (uid, int(folder_filter))).fetchall()
    else:
        docs = db.execute(base_sql + " ORDER BY d.id DESC", (uid,)).fetchall()
    db.close()
    return render_template("documents.html", docs=docs, folders=folders,
                           folder_filter=folder_filter)


@bp.route("/folders/new", methods=["POST"])
@login_required
def folder_new():
    uid = session["user_id"]
    name = request.form.get("name", "").strip()
    if name:
        db = get_db()
        db.execute("INSERT INTO folders (teacher_id, name) VALUES (?, ?)", (uid, name))
        db.commit()
        db.close()
    return redirect(url_for("documents.documents"))


@bp.route("/folders/<int:fid>/delete", methods=["POST"])
@login_required
def folder_delete(fid):
    uid = session["user_id"]
    db = get_db()
    db.execute("UPDATE documents SET folder_id = NULL WHERE folder_id = ? AND teacher_id = ?", (fid, uid))
    db.execute("DELETE FROM folders WHERE id = ? AND teacher_id = ?", (fid, uid))
    db.commit()
    db.close()
    flash("doc_folder_deleted", "success")
    return redirect(url_for("documents.documents"))


@bp.route("/documents/<int:did>/move", methods=["POST"])
@login_required
def document_move(did):
    uid = session["user_id"]
    folder_id = request.form.get("folder_id") or None
    if folder_id:
        folder_id = int(folder_id)
    db = get_db()
    db.execute("UPDATE documents SET folder_id = ? WHERE id = ? AND teacher_id = ?",
               (folder_id, did, uid))
    db.commit()
    db.close()
    flash("doc_moved", "success")
    return redirect(url_for("documents.document_view", did=did))


# --------------------------------------------------------------------------
# Document detail, file serving, summarize, edit
# --------------------------------------------------------------------------
@bp.route("/documents/<int:did>")
@login_required
def document_view(did):
    uid = session["user_id"]
    db = get_db()
    doc = db.execute("SELECT * FROM documents WHERE id = ? AND teacher_id = ?", (did, uid)).fetchone()
    if doc is None:
        db.close()
        return redirect(url_for("documents.documents"))
    sigs = db.execute("SELECT * FROM signatures WHERE document_id = ? ORDER BY id DESC", (did,)).fetchall()
    reqs = db.execute("SELECT * FROM sign_requests WHERE document_id = ? ORDER BY id DESC", (did,)).fetchall()
    folders = db.execute("SELECT * FROM folders WHERE teacher_id = ? ORDER BY name", (uid,)).fetchall()
    db.close()
    links = [(r, url_for("documents.public_sign", token=r["token"], _external=True)) for r in reqs]
    return render_template("document_view.html", doc=doc, sigs=sigs, links=links, folders=folders)


@bp.route("/documents/<int:did>/file")
@login_required
def document_file(did):
    uid = session["user_id"]
    db = get_db()
    doc = db.execute("SELECT * FROM documents WHERE id = ? AND teacher_id = ?", (did, uid)).fetchone()
    db.close()
    if doc is None:
        abort(404)
    return send_from_directory(str(_user_dir(doc["teacher_id"])), doc["stored_name"])


@bp.route("/documents/<int:did>/summarize", methods=["POST"])
@login_required
def document_summarize(did):
    uid = session["user_id"]
    db = get_db()
    doc = db.execute("SELECT * FROM documents WHERE id = ? AND teacher_id = ?", (did, uid)).fetchone()
    if doc is None:
        db.close()
        abort(404)
    summary = summarize_text(extract_text(doc))
    db.execute("UPDATE documents SET summary = ? WHERE id = ?", (summary, did))
    db.commit()
    db.close()
    if not summary:
        flash("doc_summary_empty", "error")
    else:
        flash("doc_saved", "success")
    return redirect(url_for("documents.document_view", did=did))


@bp.route("/documents/<int:did>/edit", methods=["GET", "POST"])
@login_required
def document_edit(did):
    uid = session["user_id"]
    db = get_db()
    doc = db.execute("SELECT * FROM documents WHERE id = ? AND teacher_id = ?", (did, uid)).fetchone()
    if doc is None:
        db.close()
        return redirect(url_for("documents.documents"))
    text = extract_text(doc)
    if request.method == "POST":
        new_text = request.form.get("text", "")
        base = Path(doc["stored_name"]).stem or "document"
        new_name = f"{base}_edited_{uuid4().hex[:6]}.txt"
        _user_dir(uid).joinpath(new_name).write_text(new_text, encoding="utf-8")
        db.execute(
            "INSERT INTO documents (teacher_id, title, original_name, stored_name, mime_type, folder_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (uid, doc["title"] + " (edited)", new_name, new_name, "text/plain", doc["folder_id"]),
        )
        db.commit()
        db.close()
        flash("doc_uploaded", "success")
        return redirect(url_for("documents.documents"))
    db.close()
    return render_template("document_edit.html", doc=doc, text=text)


# --------------------------------------------------------------------------
# Signing
# --------------------------------------------------------------------------
@bp.route("/documents/<int:did>/sign", methods=["POST"])
@login_required
def document_sign(did):
    uid = session["user_id"]
    fname = _save_signature(request.form.get("signature", ""))
    if not fname:
        flash("doc_sign_empty", "error")
        return redirect(url_for("documents.document_view", did=did))
    signer_name = request.form.get("signer_name", "").strip() or session.get("name", "")
    signer_email = request.form.get("signer_email", "").strip() or _signer_identity()
    db = get_db()
    doc = db.execute("SELECT id FROM documents WHERE id = ? AND teacher_id = ?", (did, uid)).fetchone()
    if doc is None:
        db.close()
        abort(404)
    db.execute(
        "INSERT INTO signatures (document_id, signer_name, signer_email, signature_file) VALUES (?, ?, ?, ?)",
        (did, signer_name, signer_email, fname),
    )
    db.commit()
    db.close()
    flash("doc_sign_saved", "success")
    return redirect(url_for("documents.document_view", did=did))


@bp.route("/documents/<int:did>/request-signature", methods=["POST"])
@login_required
def request_signature(did):
    uid = session["user_id"]
    token = uuid4().hex
    signer_name = request.form.get("signer_name", "").strip()
    signer_email = request.form.get("signer_email", "").strip()
    db = get_db()
    doc = db.execute("SELECT id FROM documents WHERE id = ? AND teacher_id = ?", (did, uid)).fetchone()
    if doc is None:
        db.close()
        abort(404)
    db.execute(
        "INSERT INTO sign_requests (document_id, token, signer_name, signer_email) VALUES (?, ?, ?, ?)",
        (did, token, signer_name, signer_email),
    )
    db.commit()
    db.close()
    flash("doc_request_sent", "success")
    return redirect(url_for("documents.document_view", did=did))


@bp.route("/sign/<token>", methods=["GET", "POST"])
def public_sign(token):
    db = get_db()
    req = db.execute("SELECT * FROM sign_requests WHERE token = ?", (token,)).fetchone()
    if req is None:
        db.close()
        abort(404)
    doc = db.execute("SELECT * FROM documents WHERE id = ?", (req["document_id"],)).fetchone()
    db.close()
    if doc is None:
        abort(404)
    signed = req["status"] == "signed"
    if request.method == "POST" and not signed:
        fname = _save_signature(request.form.get("signature", ""))
        if fname:
            name = request.form.get("signer_name", "").strip() or req["signer_name"]
            db = get_db()
            db.execute(
                "INSERT INTO signatures (document_id, signer_name, signer_email, signature_file) VALUES (?, ?, ?, ?)",
                (doc["id"], name, req["signer_email"], fname),
            )
            db.execute("UPDATE sign_requests SET status = 'signed' WHERE token = ?", (token,))
            db.commit()
            db.close()
            signed = True
    return render_template("public_sign.html", doc=doc, req=req, signed=signed, token=token)


@bp.route("/sign/<token>/file")
def public_sign_file(token):
    db = get_db()
    req = db.execute("SELECT * FROM sign_requests WHERE token = ?", (token,)).fetchone()
    if req is None:
        db.close()
        abort(404)
    doc = db.execute("SELECT * FROM documents WHERE id = ?", (req["document_id"],)).fetchone()
    db.close()
    if doc is None:
        abort(404)
    return send_from_directory(str(_user_dir(doc["teacher_id"])), doc["stored_name"])


@bp.route("/signature/<path:fname>")
def signature_file(fname):
    return send_from_directory(str(SIG_DIR), fname)


@bp.route("/documents/<int:did>/delete", methods=["POST"])
@login_required
def document_delete(did):
    uid = session["user_id"]
    db = get_db()
    doc = db.execute("SELECT * FROM documents WHERE id = ? AND teacher_id = ?", (did, uid)).fetchone()
    if doc is not None:
        try:
            (_user_dir(doc["teacher_id"]) / doc["stored_name"]).unlink(missing_ok=True)
        except Exception:
            pass
        db.execute("DELETE FROM signatures WHERE document_id = ?", (did,))
        db.execute("DELETE FROM sign_requests WHERE document_id = ?", (did,))
        db.execute("DELETE FROM documents WHERE id = ?", (did,))
        db.commit()
    db.close()
    flash("doc_deleted", "success")
    return redirect(url_for("documents.documents"))
