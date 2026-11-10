# -*- coding: utf-8 -*-
"""Tool 3 — LAPORAN HARIAN GURU BERTUGAS (Daily Teacher Duty Report).

Reference layout: header, centred title, a bordered table of week/date/day/
teacher/absence/attendance/weather/cleanliness/facilities/canteen/discipline/
special activities/visitors/incidents/remarks/recommendations, then a
Guru Bertugas signature block.
"""
import os

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from docgen import (styles, pdf_header_flowables, NumberedCanvas, _esc,
                    _docx_cell, _docx_shade, docx_header, new_doc, add_title)

FIELDS = [
    ("week", "MINGGU"),
    ("date", "TARIKH"),
    ("day", "HARI"),
    ("teacher_duty", "GURU BERTUGAS"),
    ("teachers_absent", "GURU TIDAK HADIR"),
    ("absence_reason", "SEBAB TIDAK HADIR"),
    ("students_absent", "MURID TIDAK HADIR"),
    ("attendance", "MAKLUMAT KEHADIRAN"),
    ("weather", "CUACA"),
    ("cleanliness", "KEBERSIHAN SEKOLAH"),
    ("facilities", "KEADAAN KEMUDAHAN"),
    ("canteen", "KEADAAN KANTIN"),
    ("discipline", "PEMERHATIAN DISIPLIN"),
    ("special_activities", "AKTIVITI KHAS"),
    ("visitors", "PELAWAT"),
    ("incidents", "INSIDEN PENTING"),
    ("remarks", "CATATAN KESELURUHAN"),
    ("recommendations", "CADANGAN"),
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
    inner = Table([
        [Paragraph("Guru Bertugas,", st["label"])],
        [Paragraph("", st["sign"])],
        [Paragraph("", st["sign"])],
        [Paragraph("____________________________", st["sign"])],
        [Paragraph(_esc(data.get("teacher_duty") or ""), st["sign"])],
    ], colWidths=[84 * mm])
    inner.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(inner)

    doc.build(story, canvasmaker=NumberedCanvas)
    return out_path


def build_duty_docx(data, out_path):
    from docx.shared import Pt

    doc = new_doc()
    docx_header(doc, data)
    add_title(doc, "LAPORAN HARIAN GURU BERTUGAS")

    table = doc.add_table(rows=0, cols=2)
    table.style = "Table Grid"
    for key, label in FIELDS:
        cells = table.add_row().cells
        _docx_cell(cells[0], label, bold=True)
        _docx_shade(cells[0], "EEF2FF")
        _docx_cell(cells[1], data.get(key) or "—")

    doc.add_paragraph()
    doc.add_paragraph()
    p = doc.add_paragraph()
    r = p.add_run("Guru Bertugas,"); r.bold = True; r.font.size = Pt(10)
    doc.add_paragraph()
    doc.add_paragraph()
    doc.add_paragraph("____________________________")
    doc.add_paragraph(data.get("teacher_duty") or "")

    doc.save(str(out_path))
    return out_path
