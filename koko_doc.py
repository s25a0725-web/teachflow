# -*- coding: utf-8 -*-
"""Tool 2 — LAPORAN BERGAMBAR UNIT KOKURIKULUM (co-curricular illustrated report).

Reproduces the reference: header (logo / school name / emblem) with doc code
"PK1/3" top-right, centred title, a single-column bordered table of
PROGRAM / TEMPAT / TARIKH PROGRAM / SASARAN / OBJEKTIF / BULATAN AKTIVITI /
PENILAIAN AKTIVITI / ANALISIS / KEBERHASILAN PROGRAM / CADANGAN PENAMBAHBAIKAN,
then LAMPIRAN, a 2x2 photo grid (Gambar 1-4) with captions, and Disiplin oleh /
Disahkan oleh signature blocks.
"""
import os
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak

from docgen import (styles, pdf_header_flowables, NumberedCanvas, _esc, _fit,
                    _docx_cell, _docx_shade, docx_header, new_doc, add_title,
                    pdf_signature_flowable, docx_signature_block)

FIELDS = [
    ("program", "PROGRAM"),
    ("tempat", "TEMPAT"),
    ("tarikh", "TARIKH PROGRAM"),
    ("sasaran", "SASARAN"),
    ("objektif", "OBJEKTIF"),
    ("aktiviti", "BULATAN AKTIVITI"),
    ("penilaian", "PENILAIAN AKTIVITI"),
    ("analisis", "ANALISIS"),
    ("keberhasilan", "KEBERHASILAN PROGRAM"),
    ("cadangan", "CADANGAN PENAMBAHBAIKAN"),
]


def _as_list(val):
    if isinstance(val, list):
        return [str(x).strip() for x in val if str(x).strip()]
    if not val:
        return []
    return [ln.strip() for ln in str(val).split("\n") if ln.strip()]


def _list_flow(items, st):
    from reportlab.platypus import Flowable

    class _V(Flowable):
        def __init__(self, its):
            super().__init__()
            self.its = its

        def wrap(self, aw, ah):
            self.width = aw
            self.height = 0
            for it in self.its:
                w, h = it.wrap(aw, ah)
                self.height += h
            return aw, self.height

        def draw(self):
            y = self.height
            for it in self.its:
                w, h = it.wrap(self.width, self.height)
                it.drawOn(self.canv, 0, y - h)
                y -= h

    return _V(items)


def build_koko_pdf(data, out_path):
    st = styles()
    doc = SimpleDocTemplate(str(out_path), pagesize=A4,
                            leftMargin=16 * mm, rightMargin=16 * mm,
                            topMargin=14 * mm, bottomMargin=16 * mm,
                            title="LAPORAN BERGAMBAR UNIT KOKURIKULUM")

    story = []
    story.extend(pdf_header_flowables(data, st))
    story.append(Paragraph("LAPORAN BERGAMBAR UNIT KOKURIKULUM", st["title"]))

    # doc code top-right handled via a small right-aligned line
    rows = []
    for key, label in FIELDS:
        val = _as_list(data.get(key))
        if val and key in ("objektif", "aktiviti", "penilaian", "analisis", "keberhasilan", "cadangan"):
            items = [Paragraph("%d. %s" % (i + 1, _esc(v)), st["value"]) for i, v in enumerate(val)]
            cell = _list_flow(items, st)
        else:
            cell = Paragraph(_esc("\n".join(val)) if val else "—", st["value"])
        rows.append([Paragraph(label, st["label"]), cell])

    main = Table(rows, colWidths=[52 * mm, 116 * mm])
    main.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.8, colors.HexColor("#64748b")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eef2ff")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(main)

    story.append(Spacer(1, 6))
    story.append(Paragraph("LAMPIRAN", st["head"]))

    # Photo grid (2x2)
    photos = data.get("photos") or []
    story.append(PageBreak())
    story.append(Paragraph("LAMPIRAN (GAMBAR)", st["head"]))
    grid_rows = []
    for i in range(0, 4, 2):
        cells = []
        for j in (0, 1):
            idx = i + j
            if idx < len(photos) and photos[idx].get("path") and os.path.exists(photos[idx]["path"]):
                w, h = _fit(photos[idx]["path"], 80 * mm, 60 * mm)
                cells.append(Image(photos[idx]["path"], width=w, height=h))
            else:
                cells.append(Paragraph("—", st["value"]))
        captions = []
        for j in (0, 1):
            idx = i + j
            cap = (photos[idx].get("caption") or "") if idx < len(photos) else ""
            captions.append(Paragraph("Gambar %d: %s" % (idx + 1, _esc(cap)), st["value"]))
        tbl = Table([cells, captions], colWidths=[84 * mm, 84 * mm])
        tbl.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, 0), 0.8, colors.HexColor("#64748b")),
            ("VALIGN", (0, 0), (-1, 0), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, 0), 6),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
            ("FONTSIZE", (0, 1), (-1, 1), 8.5),
            ("TEXTCOLOR", (0, 1), (-1, 1), colors.HexColor("#475569")),
        ]))
        grid_rows.append(tbl)
        grid_rows.append(Spacer(1, 8))
    if not grid_rows:
        story.append(Paragraph("Tiada gambar dimuat naik.", st["sign"]))
    story.extend(grid_rows)

    story.append(Spacer(1, 24))

    sig = Table([[pdf_signature_flowable("disediakan", "Disediakan oleh:", data, st, data.get("disediakan_nama")),
                  pdf_signature_flowable("disahkan", "Disahkan oleh:", data, st, data.get("disahkan_nama"))]],
                colWidths=[84 * mm, 84 * mm])
    sig.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(sig)

    doc.build(story, canvasmaker=NumberedCanvas)
    return out_path


def build_koko_docx(data, out_path):
    from docx.shared import Pt
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = new_doc()
    docx_header(doc, data)
    add_title(doc, "LAPORAN BERGAMBAR UNIT KOKURIKULUM")

    table = doc.add_table(rows=0, cols=2)
    table.style = "Table Grid"
    for key, label in FIELDS:
        val = _as_list(data.get(key))
        text = ("\n".join("%d. %s" % (i + 1, v) for i, v in enumerate(val))
                if val and key in ("objektif", "aktiviti", "penilaian", "analisis", "keberhasilan", "cadangan")
                else ("\n".join(val) if val else "—"))
        cells = table.add_row().cells
        _docx_cell(cells[0], label, bold=True)
        _docx_shade(cells[0], "EEF2FF")
        _docx_cell(cells[1], text)

    doc.add_paragraph("LAMPIRAN").runs[0].bold = True

    photos = data.get("photos") or []
    if photos:
        doc.add_page_break()
        for i in range(0, 4, 2):
            pt = doc.add_table(rows=1, cols=2)
            pt.style = "Table Grid"
            for j in (0, 1):
                idx = i + j
                cell = pt.rows[0].cells[j]
                cell.text = ""
                if idx < len(photos) and photos[idx].get("path") and os.path.exists(photos[idx]["path"]):
                    cell.paragraphs[0].add_run().add_picture(photos[idx]["path"], width=Pt(220))
                cap = (photos[idx].get("caption") or "") if idx < len(photos) else ""
                cp = cell.add_paragraph(); cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
                cr = cp.add_run("Gambar %d: %s" % (idx + 1, cap) if cap else "Gambar %d" % (idx + 1))
                cr.font.size = Pt(8.5)
    else:
        doc.add_paragraph("Tiada gambar dimuat naik.")

    doc.add_paragraph()
    docx_signature_block(doc, "disediakan", "Disediakan oleh:", data, data.get("disediakan_nama"))
    docx_signature_block(doc, "disahkan", "Disahkan oleh:", data, data.get("disahkan_nama"))

    doc.save(str(out_path))
    return out_path
