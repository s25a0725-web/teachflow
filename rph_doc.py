# -*- coding: utf-8 -*-
"""RPH (Rancangan Pengajaran Harian) document builders.

Produce professional KPM-style A4 documents (PDF and DOCX) from a structured
RPH dict. Both builders share the same section order and labels so the two
exports look consistent. Latin text uses Arial; Tamil text falls back to the
Nirmala font when available.
"""
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


_FONTS = {}


def _register_fonts():
    if _FONTS:
        return _FONTS
    body = "Helvetica"
    bold = "Helvetica-Bold"
    try:
        for tag, path in (("Arial", "C:/Windows/Fonts/arial.ttf"),
                          ("Arial-Bold", "C:/Windows/Fonts/arialbd.ttf"),
                          ("Arial-Italic", "C:/Windows/Fonts/ariali.ttf"),
                          ("Arial-BoldItalic", "C:/Windows/Fonts/arialbi.ttf")):
            if os.path.exists(path):
                pdfmetrics.registerFont(TTFont(tag, path))
        if "Arial" in pdfmetrics.getRegisteredFontNames():
            from reportlab.pdfbase.pdfmetrics import registerFontFamily
            registerFontFamily("Arial", normal="Arial", bold="Arial-Bold",
                               italic="Arial-Italic", boldItalic="Arial-BoldItalic")
            body, bold = "Arial", "Arial-Bold"
    except Exception:
        body, bold = "Helvetica", "Helvetica-Bold"
    # Tamil support (optional)
    for p in ("C:/Windows/Fonts/Nirmala.ttc", "C:/Windows/Fonts/Nirmala.ttf"):
        if os.path.exists(p):
            try:
                pdfmetrics.registerFont(TTFont("Nirmala", p, subfontIndex=0))
                _FONTS["tamil"] = "Nirmala"
                break
            except Exception:
                pass
    _FONTS["body"] = body
    _FONTS["bold"] = bold
    return _FONTS


# ---- Section metadata shared by PDF/DOCX/template -------------------------
# Each tuple: (key, "heading", kind) where kind is "text" | "list" | "steps".
RPH_SECTIONS = [
    ("sk", "Standard Kandungan (SK)", "text"),
    ("sp", "Standard Pembelajaran (SP)", "text"),
    ("objectives", "Objektif Pembelajaran", "list"),
    ("success_criteria", "Kriteria Kejayaan", "list"),
    ("set_induksi", "Set Induksi", "text"),
    ("activities", "Aktiviti Pengajaran dan Pembelajaran", "steps"),
    ("bbm", "Bahan Bantu Mengajar (BBM)", "list"),
    ("pak21", "PAK21", "text"),
    ("kbat", "KBAT", "text"),
    ("emk", "EMK", "list"),
    ("pbd", "Pentaksiran (PBD)", "text"),
    ("remedial", "Pemulihan", "text"),
    ("enrichment", "Pengayaan", "text"),
    ("reflection", "Refleksi Guru", "text"),
]

META_FIELDS = [
    ("subject", "Mata Pelajaran"),
    ("class", "Kelas"),
    ("date", "Tarikh"),
    ("day", "Hari"),
    ("duration", "Masa"),
    ("teacher", "Guru"),
]


def _esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _styles(body, bold):
    s = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("rph_title", fontName=bold, fontSize=15, leading=20,
                                alignment=1, spaceAfter=2, textColor=colors.HexColor("#111827")),
        "subtitle": ParagraphStyle("rph_sub", fontName=body, fontSize=10, leading=14,
                                   alignment=1, spaceAfter=10, textColor=colors.HexColor("#475569")),
        "h": ParagraphStyle("rph_h", fontName=bold, fontSize=11.5, leading=15,
                            spaceBefore=10, spaceAfter=4, textColor=colors.HexColor("#1e3a8a"),
                            borderPadding=0),
        "body": ParagraphStyle("rph_body", fontName=body, fontSize=10, leading=14,
                               spaceAfter=3, textColor=colors.HexColor("#1f2937")),
        "cell": ParagraphStyle("rph_cell", fontName=body, fontSize=9.5, leading=13,
                               textColor=colors.HexColor("#1f2937")),
        "cellb": ParagraphStyle("rph_cellb", fontName=bold, fontSize=9.5, leading=13,
                                textColor=colors.HexColor("#111827")),
    }


class _NumberedCanvas(canvas.Canvas):
    """A4 pages with a school-name header line and 'Page X of Y' footer."""

    def __init__(self, *args, school="", doc_title="", **kw):
        super().__init__(*args, **kw)
        self._school = school
        self._doc_title = doc_title
        self._saved = []

    def showPage(self):
        self._saved.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved)
        for state in self._saved:
            self.__dict__.update(state)
            self._chrome(total)
            super().showPage()
        super().save()

    def _chrome(self, total):
        w, h = A4
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))
        self.drawString(20 * mm, h - 14 * mm, self._school[:60])
        self.drawRightString(w - 20 * mm, h - 14 * mm, self._doc_title[:40])
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.5)
        self.line(20 * mm, h - 16 * mm, w - 20 * mm, h - 16 * mm)
        self.drawCentredString(w / 2, 10 * mm, "Page %d of %d" % (self._pageNumber, total))


def _cell(txt, style):
    return Paragraph(_esc(txt), style)


def build_rph_pdf(rph, out_path):
    fonts = _register_fonts()
    body, bold = fonts["body"], fonts["bold"]
    st = _styles(body, bold)
    title = rph.get("topic") or rph.get("title") or "RPH"
    school = rph.get("school") or ""
    doc_title = "RANCANGAN PENGAJARAN HARIAN"

    doc = SimpleDocTemplate(
        str(out_path), pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm, topMargin=20 * mm, bottomMargin=18 * mm,
        title=title, author=rph.get("teacher", ""),
    )

    story = [Paragraph(_esc(school), st["subtitle"]),
             Paragraph(doc_title, st["title"]),
             Paragraph(_esc(title), st["subtitle"]),
             Spacer(1, 4)]

    # --- Info table ---
    meta_rows = [[_cell("Maklumat Pelajaran", st["cellb"]), _cell("", st["cell"])]]
    for key, label in META_FIELDS:
        meta_rows.append([_cell(label, st["cellb"]), _cell(rph.get(key, ""), st["cell"])])
    meta = Table(meta_rows, colWidths=[48 * mm, 122 * mm])
    meta.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#eef2ff")),
        ("SPAN", (0, 0), (1, 0)),
        ("BACKGROUND", (0, 1), (0, -1), colors.HexColor("#f8fafc")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(meta)
    story.append(Spacer(1, 6))

    # --- Sections ---
    for key, heading, kind in RPH_SECTIONS:
        story.append(Paragraph(_esc(heading), st["h"]))
        if kind == "list":
            items = rph.get(key) or []
            if isinstance(items, str):
                items = [items]
            if not items:
                story.append(Paragraph("—", st["body"]))
            for i, it in enumerate(items, 1):
                story.append(Paragraph("%d. %s" % (i, _esc(it)), st["body"]))
        elif kind == "steps":
            steps = rph.get(key) or []
            rows = [[_cell("Langkah", st["cellb"]), _cell("Masa", st["cellb"]), _cell("Aktiviti", st["cellb"])]]
            for s in steps:
                if isinstance(s, dict):
                    rows.append([_cell(s.get("step", ""), st["cell"]),
                                 _cell(s.get("time", ""), st["cell"]),
                                 _cell(s.get("detail", ""), st["cell"])])
                else:
                    rows.append([_cell("", st["cell"]), _cell("", st["cell"]), _cell(str(s), st["cell"])])
            if len(rows) == 1:
                rows.append([_cell("", st["cell"]), _cell("", st["cell"]), _cell("—", st["cell"])])
            tbl = Table(rows, colWidths=[22 * mm, 22 * mm, 126 * mm], repeatRows=1)
            tbl.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2ff")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(tbl)
        else:
            val = rph.get(key) or ""
            story.append(Paragraph(_esc(val) if val else "—", st["body"]))

    doc.build(story, canvasmaker=lambda *a, **kw: _NumberedCanvas(
        *a, school=school, doc_title=doc_title, **kw))
    return out_path


# --------------------------------------------------------------------------
# DOCX
# --------------------------------------------------------------------------
def _docx_set_cell(cell, text, bold=False, size=10):
    cell.text = ""
    p = cell.paragraphs[0]
    run = p.add_run(str(text or ""))
    run.bold = bold
    run.font.size = size


def _docx_shade(cell, hex_color):
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), hex_color)
    tcPr.append(shd)


def _docx_page_number_footer(doc):
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    section = doc.sections[0]
    footer = section.footer
    p = footer.paragraphs[0]
    p.alignment = 1  # center
    run = p.add_run()
    fld1 = OxmlElement("w:fldChar"); fld1.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText"); instr.set(qn("xml:space"), "preserve"); instr.text = "PAGE"
    fld2 = OxmlElement("w:fldChar"); fld2.set(qn("w:fldCharType"), "end")
    run._r.append(fld1); run._r.append(instr); run._r.append(fld2)


def build_rph_docx(rph, out_path):
    from docx import Document
    from docx.shared import Pt, RGBColor, Cm
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Arial"
    style.font.size = Pt(10)

    # Header (school) + footer page number
    section = doc.sections[0]
    header = section.header
    hp = header.paragraphs[0]
    hp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    hr = hp.add_run(rph.get("school") or "")
    hr.font.size = Pt(8)
    hr.font.color.rgb = RGBColor(0x64, 0x74, 0x8b)
    _docx_page_number_footer(doc)

    # Title
    t = doc.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    tr = t.add_run("RANCANGAN PENGAJARAN HARIAN")
    tr.bold = True
    tr.font.size = Pt(15)
    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sr = sub.add_run(rph.get("topic") or "RPH")
    sr.font.size = Pt(11)
    sr.font.color.rgb = RGBColor(0x47, 0x55, 0x69)

    # Info table
    info = doc.add_table(rows=1, cols=2)
    info.style = "Table Grid"
    _docx_set_cell(info.rows[0].cells[0], "Maklumat Pelajaran", bold=True)
    _docx_set_cell(info.rows[0].cells[1], "")
    _docx_shade(info.rows[0].cells[0], "EEF2FF")
    _docx_shade(info.rows[0].cells[1], "EEF2FF")
    for key, label in META_FIELDS:
        row = info.add_row().cells
        _docx_set_cell(row[0], label, bold=True)
        _docx_set_cell(row[1], rph.get(key, ""))
        _docx_shade(row[0], "F8FAFC")

    # Sections
    for key, heading, kind in RPH_SECTIONS:
        doc.add_heading(heading, level=1)
        if kind == "list":
            items = rph.get(key) or []
            if isinstance(items, str):
                items = [items]
            if not items:
                doc.add_paragraph("—")
            for i, it in enumerate(items, 1):
                doc.add_paragraph("%d. %s" % (i, it), style="List Number")
        elif kind == "steps":
            steps = rph.get(key) or []
            at = doc.add_table(rows=1, cols=3)
            at.style = "Table Grid"
            hdr = at.rows[0].cells
            _docx_set_cell(hdr[0], "Langkah", bold=True)
            _docx_set_cell(hdr[1], "Masa", bold=True)
            _docx_set_cell(hdr[2], "Aktiviti", bold=True)
            for c in hdr:
                _docx_shade(c, "EEF2FF")
            for s in steps:
                if isinstance(s, dict):
                    vals = (s.get("step", ""), s.get("time", ""), s.get("detail", ""))
                else:
                    vals = ("", "", str(s))
                cells = at.add_row().cells
                for c, v in zip(cells, vals):
                    _docx_set_cell(c, v)
            if len(steps) == 0:
                cells = at.add_row().cells
                _docx_set_cell(cells[2], "—")
        else:
            doc.add_paragraph(rph.get(key) or "—")

    doc.save(str(out_path))
    return out_path
