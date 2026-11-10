# -*- coding: utf-8 -*-
"""Tool 5 — REKOD PINJAMAN PERKAKASAN ICT (ICT Equipment Loan Record).

Reproduces the reference layout: header, centred title, then
BAHAGIAN A (NAMA GURU PEMINJAM / ALAT PINJAMAN PERKAKASAN ELEKTRONIK /
NO. SERIAL / TARIKH PINJAMAN / TUJUAN PINJAMAN / SAKSI + responsibility
declaration + borrower signature), BAHAGIAN B (TARIKH PEMULANGAN / STATUS /
ADUAN / SAKSI PEMULANGAN), AKUAN SERAHAN, and Disahkan oleh block.
E-signing aware.
"""
import os

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from docgen import (styles, pdf_header_flowables, NumberedCanvas, _esc,
                    _docx_cell, _docx_shade, docx_header, new_doc, add_title,
                    pdf_signature_flowable, docx_signature_block)

FIELDS = [
    ("teacher_name", "NAMA GURU (PEMINJAM)"),
    ("equipment_name", "ALAT PINJAMAN PERKAKASAN ELEKTRONIK"),
    ("serial_no", "NO. SERIAL"),
    ("borrow_date", "TARIKH PINJAMAN"),
    ("purpose", "TUJUAN PINJAMAN"),
    ("witness", "SAKSI"),
    ("return_date", "TARIKH PEMULANGAN"),
    ("status", "STATUS"),
    ("complaint", "ADUAN"),
    ("return_witness", "SAKSI (PEMULANGAN)"),
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

    def lp(t):
        return Paragraph(_esc(t), st["label"])
    def vp(k, default="—"):
        return Paragraph(_esc(data.get(k) or "") or default, st["value"])

    # Bahagian A
    story.append(Paragraph("BAHAGIAN A — MAKLUMAT PINJAMAN", st["head"]))
    a_rows = [
        [lp("NAMA GURU (PEMINJAM)"), vp("teacher_name")],
        [lp("ALAT PINJAMAN PERKAKASAN ELEKTRONIK"), vp("equipment_name")],
        [lp("NO. SERIAL"), vp("serial_no")],
        [lp("TARIKH PINJAMAN"), vp("borrow_date")],
        [lp("TUJUAN PINJAMAN"), vp("purpose")],
        [lp("SAKSI"), vp("witness")],
    ]
    a_table = Table(a_rows, colWidths=[52 * mm, 116 * mm])
    a_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.8, colors.HexColor("#64748b")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eef2ff")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(a_table)

    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "Saya bertanggungjawab sepenuhnya ke atas peralatan yang dipinjam sehingga dikembalikan.",
        st["sign"]))
    story.append(Spacer(1, 4))
    story.append(pdf_signature_flowable("peminjam", "Tandatangan Peminjam:", data, st, data.get("teacher_name")))

    # Bahagian B
    story.append(Spacer(1, 16))
    story.append(Paragraph("BAHAGIAN B — MAKLUMAT PEMULANGAN", st["head"]))
    b_rows = [
        [lp("TARIKH PEMULANGAN"), vp("return_date", "")],
        [lp("STATUS"), vp("status", "")],
        [lp("ADUAN"), vp("complaint", "")],
        [lp("SAKSI (PEMULANGAN)"), vp("return_witness", "")],
    ]
    b_table = Table(b_rows, colWidths=[52 * mm, 116 * mm])
    b_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.8, colors.HexColor("#64748b")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eef2ff")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(b_table)

    story.append(Spacer(1, 8))
    story.append(Paragraph("AKUAN SERAHAN PERKAKASAN ICT", st["head"]))
    story.append(Paragraph(
        "Saya memulangkan perkakasan yang dipinjam dalam keadaan baik dan sempurna.",
        st["sign"]))

    story.append(Spacer(1, 24))
    sig = Table([[pdf_signature_flowable("pengesah", "Disahkan oleh:", data, st, data.get("approver"))]],
                colWidths=[84 * mm])
    sig.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(sig)

    doc.build(story, canvasmaker=NumberedCanvas)
    return out_path


def build_loan_docx(data, out_path):
    from docx.shared import Pt

    doc = new_doc()
    docx_header(doc, data)
    add_title(doc, "REKOD PINJAMAN PERKAKASAN ICT")

    p = doc.add_paragraph(); r = p.add_run("BAHAGIAN A — MAKLUMAT PINJAMAN"); r.bold = True
    table = doc.add_table(rows=0, cols=2)
    table.style = "Table Grid"
    for key, label in [("teacher_name", "NAMA GURU (PEMINJAM)"), ("equipment_name", "ALAT PINJAMAN PERKAKASAN ELEKTRONIK"),
                       ("serial_no", "NO. SERIAL"), ("borrow_date", "TARIKH PINJAMAN"),
                       ("purpose", "TUJUAN PINJAMAN"), ("witness", "SAKSI")]:
        cells = table.add_row().cells
        _docx_cell(cells[0], label, bold=True); _docx_shade(cells[0], "EEF2FF")
        _docx_cell(cells[1], data.get(key) or "—")

    doc.add_paragraph("Saya bertanggungjawab sepenuhnya ke atas peralatan yang dipinjam sehingga dikembalikan.")
    docx_signature_block(doc, "peminjam", "Tandatangan Peminjam:", data, data.get("teacher_name"))

    doc.add_paragraph()
    p = doc.add_paragraph(); r = p.add_run("BAHAGIAN B — MAKLUMAT PEMULANGAN"); r.bold = True
    table = doc.add_table(rows=0, cols=2)
    table.style = "Table Grid"
    for key, label in [("return_date", "TARIKH PEMULANGAN"), ("status", "STATUS"),
                       ("complaint", "ADUAN"), ("return_witness", "SAKSI (PEMULANGAN)")]:
        cells = table.add_row().cells
        _docx_cell(cells[0], label, bold=True); _docx_shade(cells[0], "EEF2FF")
        _docx_cell(cells[1], data.get(key) or "")

    doc.add_paragraph()
    p = doc.add_paragraph(); r = p.add_run("AKUAN SERAHAN PERKAKASAN ICT"); r.bold = True
    doc.add_paragraph("Saya memulangkan perkakasan yang dipinjam dalam keadaan baik dan sempurna.")
    doc.add_paragraph()
    docx_signature_block(doc, "pengesah", "Disahkan oleh:", data, data.get("approver"))

    doc.save(str(out_path))
    return out_path
