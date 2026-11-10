# -*- coding: utf-8 -*-
"""Shared framework for the five school document generators (SDG).

Provides the reusable services every generator needs, while each generator
keeps its own data structure, AI system prompt, fields, and template layout:

  - school_profile()          -> dict of admin-configured school identity
  - ai_autofill()             -> natural-language -> structured dict via DeepSeek
  - parse_date_day()          -> ISO date + Malay day name detection
  - PDF helpers: fonts, logo/emblem, _NumberedCanvas, _styles, header builder
  - DOCX helpers: header table, shade, page-number footer
"""
import os
import re
import json
import datetime
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from db import get_setting
from views import BRANDING_DIR


# --------------------------------------------------------------------------
# School identity
# --------------------------------------------------------------------------
def school_profile():
    return {
        "school_name": get_setting("school_name") or "SJK(T) SEPANG",
        "school_name_en": get_setting("school_name_en") or "",
        "school_address": get_setting("school_address") or "",
        "school_code": get_setting("school_code") or "",
        "school_tel": get_setting("school_tel") or "",
        "school_email": get_setting("school_email") or "",
        "headteacher_name": get_setting("headteacher_name") or "",
    }


def _logo_path():
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
    try:
        from PIL import Image as PILImage
        with PILImage.open(path) as im:
            w, h = im.size
    except Exception:
        return max_w, max_h
    scale = min(max_w / w, max_h / h)
    return w * scale, h * scale


# --------------------------------------------------------------------------
# Date / day / time detection (offline, no AI)
# --------------------------------------------------------------------------
_DAYS_MS = ["isnin", "selasa", "rabu", "khamis", "jumaat", "sabtu", "ahad"]
_DAYS_EN = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_DAY_UPPER_MS = ["ISNIN", "SELASA", "RABU", "KHAMIS", "JUMAAT", "SABTU", "AHAD"]


def parse_date_day(text, default=None):
    """Return (iso_date, day_malay_upper). Tries explicit dates and day words."""
    iso = None
    day = ""
    low = (text or "").lower()
    # explicit date patterns: dd/mm/yyyy, yyyy-mm-dd, dd-mm-yyyy, d/m/yyyy
    m = re.search(r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})", text or "")
    if m:
        a, b, c = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if c < 100:
            c += 2000
        try:
            d = datetime.date(c, b, a)  # dd/mm/yyyy
            iso = d.isoformat()
            day = _DAY_UPPER_MS[d.weekday()]
        except ValueError:
            pass
    m2 = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", text or "")
    if not iso and m2:
        try:
            d = datetime.date(int(m2.group(1)), int(m2.group(2)), int(m2.group(3)))
            iso = d.isoformat()
            day = _DAY_UPPER_MS[d.weekday()]
        except ValueError:
            pass
    # day word
    for i, w in enumerate(_DAYS_MS):
        if w in low:
            day = _DAY_UPPER_MS[i]
            break
    if not day:
        for i, w in enumerate(_DAYS_EN):
            if w in low:
                day = _DAY_UPPER_MS[i]
                break
    if not iso and day:
        # resolve next occurrence of that weekday
        today = default or datetime.date.today()
        target = _DAY_UPPER_MS.index(day)
        delta = (target - today.weekday()) % 7
        iso = (today + datetime.timedelta(days=delta)).isoformat()
    if not iso and default:
        iso = (default if isinstance(default, datetime.date)
               else datetime.date.today()).isoformat()
    return iso, day


_TIME_RE = re.compile(r"(\d{1,2})(?:[.:](\d{2}))?\s*(am|pm|pagi|ptg|petang|malam|tgh|tengah hari)", re.IGNORECASE)


def parse_time(text):
    """Best-effort start/end time extraction. Returns (start, end) strings."""
    times = _TIME_RE.findall(text or "")
    out = []
    for hh, mm, ap in times:
        h = int(hh)
        ap = ap.lower()
        if ap in ("pm", "ptg", "petang", "malam") and h < 12:
            h += 12
        if ap in ("pagi",) and h == 12:
            h = 0
        out.append("%02d:%02d" % (h, int(mm or 0)))
    return (out[0] if len(out) > 0 else ""), (out[1] if len(out) > 1 else "")


# --------------------------------------------------------------------------
# AI autofill
# --------------------------------------------------------------------------
def _extract_json(text):
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    m = re.search(r"\{.*\}", text, re.DOTALL)
    return m.group(0) if m else text


def ai_autofill(system_prompt, user_input, fields, fallback):
    """Return dict of field keys. Uses DeepSeek (JSON) when configured; else
    deterministic fallback. Never raises; always returns a dict of fields."""
    result = fallback(user_input) if callable(fallback) else {}
    try:
        from ai_provider import complete, configured
        if configured() and (user_input or "").strip():
            msgs = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input},
            ]
            raw = complete(msgs, max_tokens=1400, temperature=0.2)
            data = json.loads(_extract_json(raw))
            if isinstance(data, dict):
                for k in fields:
                    if k in data and data[k] not in (None, ""):
                        result[k] = data[k]
    except Exception:
        pass
    # ensure every declared field exists
    for k in fields:
        result.setdefault(k, "")
    return result


# --------------------------------------------------------------------------
# PDF shared builders
# --------------------------------------------------------------------------
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


class NumberedCanvas(canvas.Canvas):
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


def _esc(s):
    return str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def styles():
    fonts = _register_fonts()
    body, bold = fonts["body"], fonts["bold"]
    return {
        "school": ParagraphStyle("s_school", fontName=bold, fontSize=11.5, leading=15,
                                 alignment=1, textColor=colors.HexColor("#111827")),
        "sub": ParagraphStyle("s_sub", fontName=body, fontSize=9, leading=12,
                              alignment=1, textColor=colors.HexColor("#374151")),
        "title": ParagraphStyle("s_title", fontName=bold, fontSize=15, leading=20,
                                alignment=1, spaceBefore=8, spaceAfter=8,
                                textColor=colors.HexColor("#111827")),
        "label": ParagraphStyle("s_label", fontName=bold, fontSize=9.5, leading=12,
                                textColor=colors.HexColor("#111827")),
        "value": ParagraphStyle("s_value", fontName=body, fontSize=9.5, leading=13,
                                textColor=colors.HexColor("#1f2937")),
        "head": ParagraphStyle("s_head", fontName=bold, fontSize=11, leading=14,
                               spaceBefore=6, spaceAfter=4, textColor=colors.HexColor("#111827")),
        "sign": ParagraphStyle("s_sign", fontName=body, fontSize=9.5, leading=13,
                               textColor=colors.HexColor("#1f2937")),
    }


def pdf_header_flowables(data, st):
    """Return list of flowables for the standard 3-part school header."""
    from reportlab.platypus import Flowable, Table, TableStyle, Image, Paragraph

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

    logo = _logo_path()
    emblem = _emblem_path()
    school = data.get("school_name") or get_setting("school_name") or "SJK(T) SEPANG"
    school_en = data.get("school_name_en") or get_setting("school_name_en") or ""
    address = data.get("school_address") or get_setting("school_address") or ""
    tel = data.get("school_tel") or get_setting("school_tel") or ""

    centre = [Paragraph(_esc(school), st["school"])]
    if school_en:
        centre.append(Paragraph(_esc(school_en), st["sub"]))
    if address:
        centre.append(Paragraph(_esc(address), st["sub"]))
    if tel:
        centre.append(Paragraph(_esc("TEL/FAKS: " + tel), st["sub"]))

    cells = []
    if logo:
        lw, lh = _fit(logo, 22 * mm, 22 * mm)
        cells.append(Image(logo, width=lw, height=lh))
    else:
        cells.append(Paragraph("", st["sub"]))
    cells.append(_V(centre))
    if emblem:
        ew, eh = _fit(emblem, 22 * mm, 22 * mm)
        cells.append(Image(emblem, width=ew, height=eh))
    else:
        cells.append(Paragraph("", st["sub"]))

    hdr = Table([cells], colWidths=[24 * mm, 120 * mm, 24 * mm])
    hdr.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, 0), "LEFT"),
        ("ALIGN", (2, 0), (2, 0), "RIGHT"),
    ]))
    return [hdr]


# --------------------------------------------------------------------------
# DOCX shared builders
# --------------------------------------------------------------------------
def _docx_cell(cell, text, bold=False, size=9.5, align=None):
    cell.text = ""
    p = cell.paragraphs[0]
    if align is not None:
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


def docx_header(doc, data):
    """Insert the standard 3-part header table into a python-docx Document."""
    from docx.shared import Pt, RGBColor, Cm
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT

    school = data.get("school_name") or get_setting("school_name") or "SJK(T) SEPANG"
    school_en = data.get("school_name_en") or get_setting("school_name_en") or ""
    address = data.get("school_address") or get_setting("school_address") or ""
    tel = data.get("school_tel") or get_setting("school_tel") or ""

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
    lines = ([school_en] if school_en else []) + ([address] if address else []) + (["TEL/FAKS: " + tel] if tel else [])
    for line in lines:
        pp = hc.add_paragraph(); pp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        rr = pp.add_run(line); rr.font.size = Pt(9); rr.font.color.rgb = RGBColor(0x37, 0x41, 0x51)
    if emblem:
        hdr.rows[0].cells[2].paragraphs[0].add_run().add_picture(emblem, width=Cm(2.2))
    return hdr


def new_doc():
    """Return a fresh python-docx Document with Arial + page-number footer."""
    from docx import Document
    from docx.shared import Pt
    doc = Document()
    doc.styles["Normal"].font.name = "Arial"
    doc.styles["Normal"].font.size = Pt(9.5)
    _docx_page_number_footer(doc)
    return doc


def add_title(doc, text):
    from docx.shared import Pt
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    tp = doc.add_paragraph(); tp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    tr = tp.add_run(text); tr.bold = True; tr.font.size = Pt(15)
    return tp
