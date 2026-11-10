# -*- coding: utf-8 -*-
"""Minit Curai document builders (KPM-style, two-page A4 portrait).

Reproduces the school reference layout: a header (school logo left, name +
address centre, emblem right), a centred MINIT CURAI title, a bordered
single-column table of PERKARA / JENIS / UNIT / NAMA PEGAWAI / JAWATAN /
TARIKH / MASA / TEMPAT / PENGANJUR / KEHADIRAN / MAKLUMAN / ISU DIBINCANGKAN /
TINDAKAN SUSULAN / BAHAN EDARAN, then a second page with FOTO 1 / FOTO 2 side
by side and DISEDIAKAN OLEH / DISAHKAN OLEH signature blocks.
"""
import os
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image,
    PageBreak, KeepTogether,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from db import get_setting
from views import BRANDING_DIR


_FONTS = {}


def _register_fonts():
    if _FONTS:
        return _FONTS
    body, bold = "Helvetica", "Helvetica-Bold"
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
    _FONTS["body"] = body
    _FONTS["bold"] = bold
    return _FONTS


# Main table fields, in reference order: (key, label)
FIELDS = [
    ("perkara", "PERKARA"),
    ("jenis", "JENIS"),
    ("unit", "UNIT"),
    ("nama_pegawai", "NAMA PEGAWAI"),
    ("jawatan", "JAWATAN"),
    ("tarikh", "TARIKH"),
    ("masa", "MASA"),
    ("tempat", "TEMPAT"),
    ("penganjur", "PENGANJUR"),
    ("kehadiran", "KEHADIRAN PEGAWAI"),
    ("makluman", "MAKLUMAN"),
    ("isu", "ISU DIBINCANGKAN"),
    ("tindakan", "TINDAKAN SUSULAN"),
    ("bahan", "BAHAN EDARAN"),
]


def _esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _logo_path():
    """Raster school logo (PNG/JPG) uploaded by an admin, else None.

    Never fabricates a logo: only an actual uploaded raster is embedded.
    """
    fname = get_setting("logo_filename")
    if fname and fname.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
        p = BRANDING_DIR / fname
        if p.exists():
            return str(p)
    return None


def _emblem_path():
    fname = get_setting("emblem_filename")
    if fname and fname.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
        p = BRANDING_DIR / fname
        if p.exists():
            return str(p)
    return None


def _fit(path, max_w, max_h):
    """Return (w, h) preserving aspect ratio, bounded by max_w x max_h."""
    try:
        from PIL import Image as PILImage
        with PILImage.open(path) as im:
            w, h = im.size
    except Exception:
        return max_w, max_h
    scale = min(max_w / w, max_h / h)
    return w * scale, h * scale


class _NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
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
        self.setFillColor(colors.HexColor("#94a3b8"))
        self.drawCentredString(w / 2, 8 * mm, "Muka surat %d / %d" % (self._pageNumber, total))


def _styles(body, bold):
    return {
        "school": ParagraphStyle("mc_school", fontName=bold, fontSize=11.5, leading=15,
                                 alignment=1, textColor=colors.HexColor("#111827")),
        "sub": ParagraphStyle("mc_sub", fontName=body, fontSize=9, leading=12,
                              alignment=1, textColor=colors.HexColor("#374151")),
        "title": ParagraphStyle("mc_title", fontName=bold, fontSize=16, leading=21,
                                alignment=1, spaceBefore=8, spaceAfter=8,
                                textColor=colors.HexColor("#111827")),
        "label": ParagraphStyle("mc_label", fontName=bold, fontSize=9.5, leading=12,
                                textColor=colors.HexColor("#111827")),
        "value": ParagraphStyle("mc_value", fontName=body, fontSize=9.5, leading=13,
                                textColor=colors.HexColor("#1f2937")),
        "head": ParagraphStyle("mc_head", fontName=bold, fontSize=11, leading=14,
                               spaceBefore=6, spaceAfter=4, textColor=colors.HexColor("#111827")),
        "sign": ParagraphStyle("mc_sign", fontName=body, fontSize=9.5, leading=13,
                               textColor=colors.HexColor("#1f2937")),
    }


def _photos_rows(photos, st):
    """Build two FOTO boxes side by side (bordered, aspect-preserving)."""
    pics = photos or []
    rows = []
    for i in range(0, max(len(pics), 2), 2):
        cells = []
        for j in (0, 1):
            idx = i + j
            if idx < len(pics) and pics[idx].get("path") and os.path.exists(pics[idx]["path"]):
                w, h = _fit(pics[idx]["path"], 78 * mm, 58 * mm)
                cells.append(Image(pics[idx]["path"], width=w, height=h))
            else:
                cells.append(Paragraph("—", st["value"]))
        caption = []
        for j in (0, 1):
            idx = i + j
            cap = (pics[idx].get("caption") or "") if idx < len(pics) else ""
            if cap:
                caption.append("FOTO %d: %s" % (idx + 1, _esc(cap)))
            else:
                caption.append("FOTO %d" % (idx + 1))
        tbl = Table([cells, [Paragraph(_esc(cap), st["value"]) for cap in caption]],
                    colWidths=[84 * mm, 84 * mm])
        tbl.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, 0), 0.8, colors.HexColor("#64748b")),
            ("VALIGN", (0, 0), (-1, 0), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, 0), 6),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
            ("ALIGN", (0, 1), (-1, 1), "CENTER"),
            ("FONTSIZE", (0, 1), (-1, 1), 8.5),
            ("TEXTCOLOR", (0, 1), (-1, 1), colors.HexColor("#475569")),
        ]))
        rows.append(tbl)
        rows.append(Spacer(1, 8))
    return rows


def build_minit_pdf(data, out_path):
    fonts = _register_fonts()
    body, bold = fonts["body"], fonts["bold"]
    st = _styles(body, bold)

    doc = SimpleDocTemplate(str(out_path), pagesize=A4,
                            leftMargin=16 * mm, rightMargin=16 * mm,
                            topMargin=14 * mm, bottomMargin=16 * mm,
                            title="MINIT CURAI")

    story = []
    # ---- Header: logo left, school name centre, emblem right ----
    logo = _logo_path()
    emblem = _emblem_path()
    header_cells = []
    if logo:
        lw, lh = _fit(logo, 22 * mm, 22 * mm)
        header_cells.append(Image(logo, width=lw, height=lh))
    else:
        header_cells.append(Paragraph("", st["sub"]))
    school = data.get("school_name") or get_setting("school_name") or "SJK(T) Sepang"
    school_en = data.get("school_name_en") or get_setting("school_name_en") or ""
    address = data.get("school_address") or get_setting("school_address") or ""
    centre = [Paragraph(_esc(school), st["school"])]
    if school_en:
        centre.append(Paragraph(_esc(school_en), st["sub"]))
    if address:
        centre.append(Paragraph(_esc(address), st["sub"]))
    from reportlab.platypus import Flowable

    class _V(Flowable):
        def __init__(self, items):
            super().__init__()
            self.items = items

        def wrap(self, aw, ah):
            self.width = aw
            self.height = 0
            for it in self.items:
                w, h = it.wrap(aw, ah)
                self.height += h
            return aw, self.height

        def draw(self):
            y = self.height
            for it in self.items:
                w, h = it.wrap(self.width, self.height)
                it.drawOn(self.canv, 0, y - h)
                y -= h

    header_cells.append(_V(centre))
    if emblem:
        ew, eh = _fit(emblem, 22 * mm, 22 * mm)
        header_cells.append(Image(emblem, width=ew, height=eh))
    else:
        header_cells.append(Paragraph("", st["sub"]))
    hdr = Table([header_cells], colWidths=[24 * mm, 120 * mm, 24 * mm])
    hdr.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, 0), "LEFT"),
        ("ALIGN", (2, 0), (2, 0), "RIGHT"),
    ]))
    story.append(hdr)

    story.append(Paragraph("MINIT CURAI", st["title"]))

    # ---- Main bordered table ----
    rows = []
    for key, label in FIELDS:
        val = data.get(key) or ""
        if key == "isu":
            items = val if isinstance(val, list) else []
            body_flow = []
            for i, it in enumerate(items, 1):
                body_flow.append(Paragraph("%d. %s" % (i, _esc(str(it))), st["value"]))
            rows.append([Paragraph(label, st["label"]), _V(body_flow) if body_flow else Paragraph("—", st["value"])])
        elif key == "tindakan":
            items = val if isinstance(val, list) else []
            body_flow = []
            for i, it in enumerate(items, 1):
                body_flow.append(Paragraph("%d. %s" % (i, _esc(str(it))), st["value"]))
            rows.append([Paragraph(label, st["label"]), _V(body_flow) if body_flow else Paragraph("—", st["value"])])
        elif key == "bahan":
            items = val if isinstance(val, list) else []
            txt = "\n".join("- " + str(x) for x in items) if items else str(val or "Tiada")
            rows.append([Paragraph(label, st["label"]), Paragraph(_esc(txt), st["value"])])
        else:
            rows.append([Paragraph(label, st["label"]), Paragraph(_esc(str(val)) or "—", st["value"])])
    # EVIDENS header row (spans both columns, grey separator)
    rows.append([Paragraph("EVIDENS", st["label"]), Paragraph("", st["value"])])
    main = Table(rows, colWidths=[44 * mm, 124 * mm], repeatRows=0)
    main.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.8, colors.HexColor("#475569")),
        ("BACKGROUND", (0, 0), (0, -2), colors.HexColor("#eef2ff")),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#d1d5db")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(main)

    # ---- Page 2: evidence photos + signatures ----
    story.append(PageBreak())
    photos = data.get("photos") or []
    if photos:
        story.extend(_photos_rows(photos, st))
    else:
        story.append(Paragraph("EVIDENS", st["head"]))
        story.append(Paragraph("Tiada gambar dimuat naik.", st["sign"]))
        story.append(Spacer(1, 20))

    # Signature blocks side by side
    def sign_block(title, name, pos, extra):
        inner = Table([
            [Paragraph(_esc(title), st["label"])],
            [Paragraph("", st["sign"])],
            [Paragraph("", st["sign"])],
            [Paragraph("(", st["sign"])],  # placeholder line
            [Paragraph(_esc(name or ""), st["sign"])],
            [Paragraph(_esc(pos or ""), st["sign"])],
        ] + ([ [Paragraph(_esc(extra), st["sign"])] ] if extra else []),
            colWidths=[80 * mm])
        inner.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 1), (-1, 1), 22),
        ]))
        return inner

    sig = Table([[sign_block("DISEDIAKAN OLEH:", data.get("disediakan_nama") or "", data.get("disediakan_jawatan") or "", data.get("disediakan_tarikh") or ""),
                  sign_block("DISAHKAN OLEH:", data.get("disahkan_nama") or "", data.get("disahkan_jawatan") or "", data.get("disahkan_sekolah") or "")]],
                colWidths=[84 * mm, 84 * mm])
    sig.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(sig)

    doc.build(story, canvasmaker=_NumberedCanvas)
    return out_path


# --------------------------------------------------------------------------
# DOCX
# --------------------------------------------------------------------------
def _docx_cell(cell, text, bold=False, size=9.5, align=None):
    cell.text = ""
    p = cell.paragraphs[0]
    if align:
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        p.alignment = align
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
    p = section.footer.paragraphs[0]
    p.alignment = 1
    run = p.add_run()
    f1 = OxmlElement("w:fldChar"); f1.set(qn("w:fldCharType"), "begin")
    it = OxmlElement("w:instrText"); it.set(qn("xml:space"), "preserve"); it.text = "PAGE"
    f2 = OxmlElement("w:fldChar"); f2.set(qn("w:fldCharType"), "end")
    run._r.append(f1); run._r.append(it); run._r.append(f2)


def build_minit_docx(data, out_path):
    from docx import Document
    from docx.shared import Pt, RGBColor, Cm
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT

    doc = Document()
    doc.styles["Normal"].font.name = "Arial"
    doc.styles["Normal"].font.size = Pt(9.5)
    _docx_page_number_footer(doc)

    school = data.get("school_name") or get_setting("school_name") or "SJK(T) Sepang"
    school_en = data.get("school_name_en") or get_setting("school_name_en") or ""
    address = data.get("school_address") or get_setting("school_address") or ""

    # Header: 3-col (logo / names / emblem)
    hdr = doc.add_table(rows=1, cols=3)
    hdr.alignment = WD_TABLE_ALIGNMENT.CENTER
    logo = _logo_path()
    emblem = _emblem_path()
    if logo:
        hdr.rows[0].cells[0].paragraphs[0].add_run().add_picture(logo, width=Cm(2.2))
    hc = hdr.rows[0].cells[1]
    hc.text = ""
    p = hc.paragraphs[0]; p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(school); r.bold = True; r.font.size = Pt(11.5)
    for line in ([school_en] if school_en else []) + ([address] if address else []):
        pp = hc.add_paragraph(); pp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        rr = pp.add_run(line); rr.font.size = Pt(9); rr.font.color.rgb = RGBColor(0x37, 0x41, 0x51)
    if emblem:
        hdr.rows[0].cells[2].paragraphs[0].add_run().add_picture(emblem, width=Cm(2.2))

    # Title
    tp = doc.add_paragraph(); tp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    tr = tp.add_run("MINIT CURAI"); tr.bold = True; tr.font.size = Pt(16)

    # Main table
    main = doc.add_table(rows=0, cols=2)
    main.style = "Table Grid"
    for key, label in FIELDS:
        val = data.get(key)
        if key == "isu":
            items = val if isinstance(val, list) else []
            text = "\n".join("%d. %s" % (i + 1, x) for i, x in enumerate(items)) or "—"
        elif key == "tindakan":
            items = val if isinstance(val, list) else []
            text = "\n".join("%d. %s" % (i + 1, x) for i, x in enumerate(items)) or "—"
        elif key == "bahan":
            items = val if isinstance(val, list) else []
            text = "\n".join("- " + str(x) for x in items) if items else (str(val) if val else "Tiada")
        else:
            text = str(val) if val else "—"
        cells = main.add_row().cells
        _docx_cell(cells[0], label, bold=True)
        _docx_shade(cells[0], "EEF2FF")
        _docx_cell(cells[1], text)
    # EVIDENS row (grey)
    er = main.add_row().cells
    _docx_cell(er[0], "EVIDENS", bold=True)
    _docx_shade(er[0], "D1D5DB")
    _docx_shade(er[1], "D1D5DB")

    # Page 2
    doc.add_page_break()
    photos = data.get("photos") or []
    if photos:
        for i in range(0, max(len(photos), 2), 2):
            pt = doc.add_table(rows=1, cols=2)
            pt.style = "Table Grid"
            for j in (0, 1):
                idx = i + j
                cell = pt.rows[0].cells[j]
                cell.text = ""
                if idx < len(photos) and photos[idx].get("path") and os.path.exists(photos[idx]["path"]):
                    cell.paragraphs[0].add_run().add_picture(photos[idx]["path"], width=Cm(7.5))
                cap = (photos[idx].get("caption") or "") if idx < len(photos) else ""
                cpp = cell.add_paragraph()
                cpp.alignment = WD_ALIGN_PARAGRAPH.CENTER
                cr = cpp.add_run("FOTO %d: %s" % (idx + 1, cap) if cap else "FOTO %d" % (idx + 1))
                cr.font.size = Pt(8.5)
                cr.font.color.rgb = RGBColor(0x47, 0x55, 0x69)
    else:
        doc.add_paragraph("Tiada gambar dimuat naik.")

    # Signatures
    st = doc.add_table(rows=1, cols=2)
    for j, (title, name, pos, extra) in enumerate([
        ("DISEDIAKAN OLEH:", data.get("disediakan_nama") or "", data.get("disediakan_jawatan") or "", data.get("disediakan_tarikh") or ""),
        ("DISAHKAN OLEH:", data.get("disahkan_nama") or "", data.get("disahkan_jawatan") or "", data.get("disahkan_sekolah") or ""),
    ]):
        cell = st.rows[0].cells[j]
        cell.text = ""
        p1 = cell.paragraphs[0]; rr = p1.add_run(title); rr.bold = True; rr.font.size = Pt(10)
        cell.add_paragraph()
        cell.add_paragraph()
        cell.add_paragraph("____________________________")
        for line in ([name] if name else []) + ([pos] if pos else []) + ([extra] if extra else []):
            cell.add_paragraph(line)

    doc.save(str(out_path))
    return out_path
