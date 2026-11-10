# -*- coding: utf-8 -*-
"""Tool 3 — LAPORAN HARIAN GURU BERTUGAS (Daily Teacher Duty Report).

Reproduces the reference layout: header, centred title, then rows
MINGGU/TARIKH/HARI, NAMA GURU BERTUGAS 1 & 2, a grey NAMA GURU TIDAK HADIR
row, AKTIVITI KHAS + LAWATAN TETAMU side by side, a KEADAAN KEMUDAHAN
SEKOLAH 10-item grid, ULASAN KESELURUHAN, then Disemak oleh / Disahkan oleh
signature blocks (e-signing aware).
"""
import os

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from docgen import (styles, pdf_header_flowables, NumberedCanvas, _esc,
                    _docx_cell, _docx_shade, docx_header, new_doc, add_title,
                    pdf_signature_flowable, docx_signature_block)

FACILITIES = ["Bilik-bilik Khas", "Makmal", "Bengkel", "Padang", "Tandas Guru",
              "Tandas Murid", "Kantin", "Pra Sekolah", "Pejabat", "Bilik ICT"]

FIELDS = [
    ("week", "MINGGU"),
    ("date", "TARIKH"),
    ("day", "HARI"),
    ("teacher_duty_1", "NAMA GURU BERTUGAS 1"),
    ("teacher_duty_2", "NAMA GURU BERTUGAS 2"),
    ("teachers_absent", "NAMA GURU TIDAK HADIR"),
    ("special_activities", "AKTIVITI KHAS"),
    ("visitors", "LAWATAN TETAMU"),
    ("remarks", "ULASAN KESELURUHAN"),
]


def build_duty_pdf(data, out_path):
    st = styles()
    doc = SimpleDocTemplate(str(out_path), pagesize=A4,
                            leftMargin=16 * mm, rightMargin=16 * mm,
                            topMargin=14 * mm, bottomMargin=16 * mm,
                            title="LAPORAN HARIAN GURU BERTUGAS")

    story = []
    story.extend(pdf_header_flowables(data, st))
    story.append(Paragraph("LAPORAN HARIAN GURU BERTUGAS", st["title"]))

    def lp(t):
        return Paragraph(_esc(t), st["label"])
    def vp(k, default="—"):
        return Paragraph(_esc(data.get(k) or "") or default, st["value"])
    def vpf(v):
        return Paragraph(_esc(v or "BAIK"), st["value"])

    rows = [
        [lp("MINGGU"), vp("week"), lp("TARIKH"), vp("date"), lp("HARI"), vp("day")],
        [lp("NAMA GURU BERTUGAS 1"), vp("teacher_duty_1"), lp("NAMA GURU BERTUGAS 2"), vp("teacher_duty_2")],
        [lp("AKTIVITI KHAS"), vp("special_activities"), lp("LAWATAN TETAMU"), vp("visitors")],
    ]
    main = Table(rows, colWidths=[36 * mm, 48 * mm, 36 * mm, 48 * mm])
    main.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.8, colors.HexColor("#64748b")),
        ("SPAN", (2, 0), (3, 0)),
        ("SPAN", (4, 0), (5, 0)),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(main)

    absent = Table([[lp("NAMA GURU TIDAK HADIR"), vp("teachers_absent", "")]], colWidths=[36 * mm, 132 * mm])
    absent.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.8, colors.HexColor("#64748b")),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#d1d5db")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(absent)

    story.append(Spacer(1, 8))
    story.append(Paragraph("KEADAAN KEMUDAHAN SEKOLAH", st["head"]))
    fac = data.get("facilities") or {}
    grid_rows = []
    for i in range(0, len(FACILITIES), 2):
        left = [lp(FACILITIES[i]), vpf(fac.get(FACILITIES[i]))]
        right = [lp(FACILITIES[i + 1]), vpf(fac.get(FACILITIES[i + 1]))] if i + 1 < len(FACILITIES) else [Paragraph("", st["value"]), Paragraph("", st["value"])]
        grid_rows.append([Table([left], colWidths=[60 * mm, 24 * mm]),
                          Table([right], colWidths=[60 * mm, 24 * mm])])
    fac_table = Table(grid_rows, colWidths=[84 * mm, 84 * mm])
    fac_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.8, colors.HexColor("#64748b")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(fac_table)

    story.append(Spacer(1, 8))
    ula = Table([[lp("ULASAN KESELURUHAN"), vp("remarks", "BAIK")]], colWidths=[52 * mm, 116 * mm])
    ula.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.8, colors.HexColor("#64748b")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(ula)

    story.append(Spacer(1, 36))
    sig = Table([[pdf_signature_flowable("disemak", "Disemak oleh:", data, st, data.get("disemak_nama")),
                  pdf_signature_flowable("disahkan", "Disahkan oleh:", data, st, data.get("disahkan_nama"))]],
                colWidths=[84 * mm, 84 * mm])
    sig.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(sig)

    doc.build(story, canvasmaker=NumberedCanvas)
    return out_path


def build_duty_docx(data, out_path):
    from docx.shared import Pt

    doc = new_doc()
    docx_header(doc, data)
    add_title(doc, "LAPORAN HARIAN GURU BERTUGAS")

    table = doc.add_table(rows=0, cols=4)
    table.style = "Table Grid"
    rows = [
        ("MINGGU", data.get("week"), "TARIKH", data.get("date")),
        ("NAMA GURU BERTUGAS 1", data.get("teacher_duty_1"), "NAMA GURU BERTUGAS 2", data.get("teacher_duty_2")),
        ("AKTIVITI KHAS", data.get("special_activities"), "LAWATAN TETAMU", data.get("visitors")),
    ]
    for a, b, c, d in rows:
        cells = table.add_row().cells
        _docx_cell(cells[0], a, bold=True); _docx_shade(cells[0], "EEF2FF")
        _docx_cell(cells[1], b or "—")
        _docx_cell(cells[2], c, bold=True); _docx_shade(cells[2], "EEF2FF")
        _docx_cell(cells[3], d or "—")

    absent = doc.add_table(rows=1, cols=2)
    absent.style = "Table Grid"
    ac = absent.rows[0].cells
    _docx_cell(ac[0], "NAMA GURU TIDAK HADIR", bold=True); _docx_shade(ac[0], "D1D5DB")
    _docx_cell(ac[1], data.get("teachers_absent") or ""); _docx_shade(ac[1], "D1D5DB")

    fac = data.get("facilities") or {}
    doc.add_paragraph()
    fp = doc.add_paragraph(); fr = fp.add_run("KEADAAN KEMUDAHAN SEKOLAH"); fr.bold = True
    ft = doc.add_table(rows=0, cols=4)
    ft.style = "Table Grid"
    for i in range(0, len(FACILITIES), 2):
        cells = ft.add_row().cells
        _docx_cell(cells[0], FACILITIES[i], bold=True)
        _docx_cell(cells[1], fac.get(FACILITIES[i]) or "BAIK")
        if i + 1 < len(FACILITIES):
            _docx_cell(cells[2], FACILITIES[i + 1], bold=True)
            _docx_cell(cells[3], fac.get(FACILITIES[i + 1]) or "BAIK")
        else:
            _docx_cell(cells[2], ""); _docx_cell(cells[3], "")

    doc.add_paragraph()
    ut = doc.add_table(rows=1, cols=2)
    ut.style = "Table Grid"
    uc = ut.rows[0].cells
    _docx_cell(uc[0], "ULASAN KESELURUHAN", bold=True); _docx_shade(uc[0], "EEF2FF")
    _docx_cell(uc[1], data.get("remarks") or "BAIK")

    doc.add_paragraph()
    doc.add_paragraph()
    docx_signature_block(doc, "disemak", "Disemak oleh:", data, data.get("disemak_nama"))
    docx_signature_block(doc, "disahkan", "Disahkan oleh:", data, data.get("disahkan_nama"))

    doc.save(str(out_path))
    return out_path
