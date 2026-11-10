# -*- coding: utf-8 -*-
"""Tool 1 — REKOD PENEMPAHAN BILIK ICT (ICT Room Booking Record).

Reproduces the school reference form: 3-part header (logo / school name +
address + tel / emblem), centred title, a grey-bordered two-column table of
TARIKH | HARI / MASA CADANGAN PENEMPAHAN / NAMA PENEMPAH | BILIK /
TUJUAN | TEMPOH MASA PENGGUNAAN / CATATAN, then a two-block signature footer
(Tandatangan Guru Pemohon / Disahkan oleh).
"""
import os
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from docgen import (styles, pdf_header_flowables, NumberedCanvas, _esc,
                    _docx_cell, _docx_shade, docx_header, new_doc, add_title)

# Field order for the booking table: (key, label)
FIELDS = [
    ("teacher_name", "NAMA PENEMPAH"),
    ("room", "BILIK"),
    ("booking_date", "TARIKH"),
    ("day", "HARI"),
    ("start_time", "MASA CADANGAN PENEMPAHAN"),
    ("purpose", "TUJUAN"),
    ("class_info", "KELAS / KUMPULAN"),
    ("duration", "TEMPOH MASA PENGGUNAAN"),
    ("remarks", "CATATAN"),
]


def _rows_pdf(data, st):
    """Reference layout rows, two per line where paired."""
    pairs = [
        [("TARIKH", data.get("booking_date")), ("HARI", data.get("day"))],
        [("MASA CADANGAN PENEMPAHAN", data.get("start_time")), ("", "")],
        [("NAMA PENEMPAH", data.get("teacher_name")), ("BILIK", data.get("room"))],
        [("TUJUAN", data.get("purpose")), ("TEMPOH MASA PENGGUNAAN", data.get("duration"))],
        [("KELAS / KUMPULAN", data.get("class_info")), ("CATATAN", data.get("remarks"))],
    ]
    rows = []
    for left, right in pairs:
        cells = []
        for label, val in (left, right):
            if not label and not val:
                continue
            inner = [Paragraph(_esc(label), st["label"]),
                     Paragraph(_esc(val) or "&nbsp;" if val else "&nbsp;", st["value"])]
            cells.append(Table([inner], colWidths=[84 * mm]))
        # pad to 2 cells
        while len(cells) < 2:
            cells.append(Table([[Paragraph("", st["value"])]], colWidths=[84 * mm]))
        rows.append(cells)
    return rows


def build_ict_pdf(data, out_path):
    st = styles()
    doc = SimpleDocTemplate(str(out_path), pagesize=A4,
                            leftMargin=16 * mm, rightMargin=16 * mm,
                            topMargin=14 * mm, bottomMargin=16 * mm,
                            title="REKOD PENEMPAHAN BILIK ICT")

    story = []
    story.extend(pdf_header_flowables(data, st))
    story.append(Paragraph("REKOD PENEMPAHAN BILIK ICT", st["title"]))

    rows = _rows_pdf(data, st)
    main = Table(rows, colWidths=[84 * mm, 84 * mm])
    main.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.8, colors.HexColor("#64748b")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(main)

    story.append(Spacer(1, 40))

    def block(title, name):
        inner = Table([
            [Paragraph(_esc(title), st["label"])],
            [Paragraph("", st["sign"])],
            [Paragraph("", st["sign"])],
            [Paragraph("", st["sign"])],
            [Paragraph("____________________________", st["sign"])],
            [Paragraph(_esc(name or ""), st["sign"])],
        ], colWidths=[80 * mm])
        inner.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
        return inner

    sig = Table([[block("Tandatangan Guru Pemohon:", data.get("teacher_name")),
                  block("Disahkan oleh:", data.get("approver") or "")]],
                colWidths=[84 * mm, 84 * mm])
    sig.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(sig)

    doc.build(story, canvasmaker=NumberedCanvas)
    return out_path


def build_ict_docx(data, out_path):
    from docx.shared import Pt
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = new_doc()
    docx_header(doc, data)
    add_title(doc, "REKOD PENEMPAHAN BILIK ICT")

    table = doc.add_table(rows=0, cols=2)
    table.style = "Table Grid"
    row_data = [
        ("TARIKH", data.get("booking_date") or ""), ("HARI", data.get("day") or ""),
        ("MASA CADANGAN PENEMPAHAN", data.get("start_time") or ""), ("", ""),
        ("NAMA PENEMPAH", data.get("teacher_name") or ""), ("BILIK", data.get("room") or ""),
        ("TUJUAN", data.get("purpose") or ""), ("TEMPOH MASA PENGGUNAAN", data.get("duration") or ""),
        ("KELAS / KUMPULAN", data.get("class_info") or ""), ("CATATAN", data.get("remarks") or ""),
    ]
    for i in range(0, len(row_data), 2):
        lbl1, val1 = row_data[i]
        lbl2, val2 = row_data[i + 1]
        cells = table.add_row().cells
        _docx_cell(cells[0], ("%s\n%s" % (lbl1, val1)) if lbl1 else (val1 or ""), bold=bool(lbl1 and not val1))
        _docx_cell(cells[1], ("%s\n%s" % (lbl2, val2)) if lbl2 else (val2 or ""), bold=bool(lbl2 and not val2))

    doc.add_paragraph()
    doc.add_paragraph()
    sig = doc.add_table(rows=1, cols=2)
    for j, (title, name) in enumerate([("Tandatangan Guru Pemohon:", data.get("teacher_name") or ""),
                                        ("Disahkan oleh:", data.get("approver") or "")]):
        cell = sig.rows[0].cells[j]
        cell.text = ""
        p1 = cell.paragraphs[0]; r1 = p1.add_run(title); r1.bold = True; r1.font.size = Pt(10)
        cell.add_paragraph()
        cell.add_paragraph()
        cell.add_paragraph("____________________________")
        cell.add_paragraph(name)

    doc.save(str(out_path))
    return out_path
