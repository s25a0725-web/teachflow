# -*- coding: utf-8 -*-
"""Offline document conversion helpers for the chatbox."""
import re
import zipfile
from pathlib import Path

IMAGE_EXTS = ("jpg", "jpeg", "png", "webp", "bmp", "gif")
TEXT_EXTS = ("txt", "md", "csv", "html", "htm", "json", "log")


def pdf_to_text(path):
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    return "\n".join((p.extract_text() or "") for p in reader.pages)


def docx_to_text(path):
    try:
        with zipfile.ZipFile(path) as z:
            xml = z.read("word/document.xml").decode("utf-8", "ignore")
    except Exception:
        return ""
    xml = re.sub(r"</w:p>", "\n", xml)
    xml = re.sub(r"<[^>]+>", "", xml)
    return xml


def image_to_pdf(src, dst):
    from PIL import Image
    img = Image.open(src)
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGB")
    img.save(dst, "PDF", resolution=100.0)


def text_to_pdf_bytes(text, font_size=11, line_height=16, chars=92, lines_per_page=42):
    """Minimal single-font PDF (Helvetica/Latin-1: fine for English & Malay)."""
    def esc(s):
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    wrapped = []
    for raw in (text or "").split("\n"):
        raw = raw.rstrip()
        if not raw:
            wrapped.append("")
            continue
        while len(raw) > chars:
            wrapped.append(raw[:chars])
            raw = raw[chars:]
        wrapped.append(raw)
    pages = []
    cur = []
    for ln in wrapped:
        cur.append(ln)
        if len(cur) >= lines_per_page:
            pages.append(cur)
            cur = []
    if cur or not pages:
        pages.append(cur)

    objs = [b"<< /Type /Catalog /Pages 2 0 R >>"]
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    page_refs = []
    for i, lines in enumerate(pages):
        ops = [b"BT /F1 %d Tf 50 740 Td %d TL" % (font_size, line_height)]
        for ln in lines:
            ops.append(b"(%s) Tj T*" % esc(ln).encode("latin-1", "replace"))
        ops.append(b"ET")
        stream = b"\n".join(ops)
        objs.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
        content_num = 4 + 2 * i
        page_num = 5 + 2 * i
        objs.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                    b"/Contents %d 0 R /Resources << /Font << /F1 3 0 R >> >> >>" % content_num)
        page_refs.append(b"%d 0 R" % page_num)
    pages_obj = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (b" ".join(page_refs), len(pages))
    objs.insert(1, pages_obj)

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n" % (len(objs) + 1)
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%EOF" % (len(objs) + 1, xref)
    return bytes(out)


def convert(src_path, src_name, target):
    """Convert a file to 'pdf' or 'txt'. Returns (output_name, mime) or (None, None)."""
    src = Path(src_path)
    name = src_name.lower()
    stem = Path(src_name).stem or "document"
    ext = name.rsplit(".", 1)[-1] if "." in name else ""

    if target == "pdf":
        if ext in IMAGE_EXTS:
            dst = src.parent / (stem + ".pdf")
            try:
                image_to_pdf(src, dst)
                return dst.name, "application/pdf"
            except Exception:
                return None, None
        if ext == "pdf":
            return src.name, "application/pdf"
        if ext in TEXT_EXTS:
            dst = src.parent / (stem + ".pdf")
            dst.write_bytes(text_to_pdf_bytes(src.read_text(encoding="utf-8", errors="ignore")))
            return dst.name, "application/pdf"
        if ext == "docx":
            dst = src.parent / (stem + ".pdf")
            dst.write_bytes(text_to_pdf_bytes(docx_to_text(src)))
            return dst.name, "application/pdf"

    elif target == "txt":
        if ext == "pdf":
            dst = src.parent / (stem + ".txt")
            dst.write_text(pdf_to_text(src), encoding="utf-8")
            return dst.name, "text/plain"
        if ext == "docx":
            dst = src.parent / (stem + ".txt")
            dst.write_text(docx_to_text(src), encoding="utf-8")
            return dst.name, "text/plain"
        if ext in TEXT_EXTS:
            return src.name, "text/plain"

    return None, None
