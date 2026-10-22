# -*- coding: utf-8 -*-
"""Verify PDF + DOCX text extraction used by summarize/edit."""
import io
import os
import sqlite3
import zipfile

os.chdir(os.path.dirname(os.path.abspath(__file__)))

from db import get_db  # noqa: E402
import documents  # noqa: E402

TXT = "Photosynthesis converts light energy into chemical energy. Plants make glucose this way. Oxygen is released as a by-product. The process happens inside the chloroplast."


def build_pdf(text):
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
    ]
    stream = f"BT /F1 14 Tf 72 720 Td ({text}) Tj ET".encode()
    objs.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    return bytes(out)


def build_docx(text):
    xml = ('<?xml version="1.0"?>'
           '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
           '<w:body><w:p><w:r><w:t>' + text + '</w:t></w:r></w:p></w:body></w:document>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("word/document.xml", xml)
    return buf.getvalue()


uid = 1
doc_dir = documents._user_dir(uid)

pdf_name = "testdoc.pdf"
(doc_dir / pdf_name).write_bytes(build_pdf(TXT))
docx_name = "testdoc.docx"
(doc_dir / docx_name).write_bytes(build_docx(TXT))

db = get_db()
db.execute("INSERT INTO documents (teacher_id, title, original_name, stored_name, mime_type) "
           "VALUES (1, 'PDF', 'testdoc.pdf', ?, 'application/pdf')", (pdf_name,))
db.execute("INSERT INTO documents (teacher_id, title, original_name, stored_name, mime_type) "
           "VALUES (1, 'DOCX', 'testdoc.docx', ?, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')",
           (docx_name,))
db.commit()

pdf_row = db.execute("SELECT * FROM documents WHERE stored_name=?", (pdf_name,)).fetchone()
docx_row = db.execute("SELECT * FROM documents WHERE stored_name=?", (docx_name,)).fetchone()

pdf_text = documents.extract_text(pdf_row)
docx_text = documents.extract_text(docx_row)

print("PDF  extract:", repr(pdf_text[:90]))
print("DOCX extract:", repr(docx_text[:90]))
print("PDF  summary:", documents.summarize_text(pdf_text))
print("DOCX summary:", documents.summarize_text(docx_text))

assert "Photosynthesis" in pdf_text, "PDF text extraction failed"
assert "Photosynthesis" in docx_text, "DOCX text extraction failed"
print("\nPDF + DOCX extraction: PASS")
