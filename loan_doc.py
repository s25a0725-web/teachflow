# -*- coding: utf-8 -*-
"""Tool 5 — REKOD PINJAMAN PERKAKASAN ICT (ICT Equipment Loan Record).

Reference layout: header, centred title, a bordered table of teacher /
equipment / category / serial / quantity / borrow date-time / purpose /
expected return / actual return / condition / status / witness / approver /
remarks, then signature blocks.
"""
import os

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from docgen import (styles, pdf_header_flowables, NumberedCanvas, _esc,
                    _docx_cell, _docx_shade, docx_header, new_doc, add_title)

FIELDS = [
    ("teacher_name", "NAMA PEMINJAM"),
    ("equipment_name", "NAMA PERKAKASAN"),
    ("category", "KATEGORI"),
    ("serial_no", "NOMBOR SIRI"),
    ("quantity", "KUANTITI"),
    ("borrow_date", "TARIKH PINJAM"),
    ("borrow_time", "MASA PINJAM"),
    ("purpose", "TUJUAN"),
    ("expected_return", "TARIKH JANGKA PULANG"),
    ("actual_return", "TARIKH PULANG SEBENAR"),
    ("condition_out", "KEADAAN (PINJAM)"),
    ("condition_in", "KEADAAN (PULANG)"),
    ("status", "STATUS"),
    ("witness", "SAKSI"),
    ("approver", "PENGESAH"),
    ("remarks", "CATATAN"),
]


def build_loan_pdf(data, out_path):
    st = styles()
    doc = SimpleDocTemplate(str(out_path), pagesize=A4,
                            leftMargin=16 * mm, rightMargin=16 * mm,
                            topMargin=14 * mm, bottomMargin=16 * mm,
                            title="REKOD PINJAMAN PERKAKASAN ICT")

    story = []
    story.extend(pdf_header_flowables(data, st))
    story.append(Paragraph("REKOD PINJAMAN PERKAKASAN ICT", st["title"]))

    rows = []
    for key, label in FIELDS:
        val = data.get(key) or ""
        rows.append([Paragraph(label, st["label"]), Paragraph(_esc(val) or "—", st["value"])])

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

    story.append(Spacer(1, 40))

    def block(title, name):
        inner = Table([
            [Paragraph(_esc(title), st["label"])],
            [Paragraph("", st["sign"])],
            [Paragraph("", st["sign"])],
            [Paragraph("____________________________", st["sign"])],
            [Paragraph(_esc(name or ""), st["sign"])],
        ], colWidths=[80 * mm])
        inner.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
        return inner

    sig = Table([[block("Tandatangan Peminjam:", data.get("teacher_name")),
                  block("Disahkan oleh:", data.get("approver") or "")]],
                colWidths=[84 * mm, 84 * mm])
    sig.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(sig)

    doc.build(story, canvasmaker=NumberedCanvas)
    return out_path


def build_loan_docx(data, out_path):
    from docx.shared import Pt

    doc = new_doc()
    docx_header(doc, data)
    add_title(doc, "REKOD PINJAMAN PERKAKASAN ICT")

    table = doc.add_table(rows=0, cols=2)
    table.style = "Table Grid"
    for key, label in FIELDS:
        cells = table.add_row().cells
        _docx_cell(cells[0], label, bold=True)
        _docx_shade(cells[0], "EEF2FF")
        _docx_cell(cells[1], data.get(key) or "—")

    doc.add_paragraph()
    doc.add_paragraph()
    sig = doc.add_table(rows=1, cols=2)
    for j, (title, name) in enumerate([("Tandatangan Peminjam:", data.get("teacher_name") or ""),
                                        ("Disahkan oleh:", data.get("approver") or "")]):
        cell = sig.rows[0].cells[j]
        cell.text = ""
        p = cell.paragraphs[0]; r = p.add_run(title); r.bold = True; r.font.size = Pt(10)
        cell.add_paragraph()
        cell.add_paragraph()
        cell.add_paragraph("____________________________")
        cell.add_paragraph(name)

    doc.save(str(out_path))
    return out_path
