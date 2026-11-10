# -*- coding: utf-8 -*-
"""Tool 4 — LAPORAN PERHIMPUNAN (School Assembly Report).

Reproduces the reference layout: header, centred title, then rows
MINGGU/TARIKH/HARI, GURU BERUCAP, GURU BERTUGAS MINGGU INI (two columns),
TAJUK PERHIMPUNAN, AGENDA (numbered), then a report table with columns
UCAPAN GURU BESAR / PESANAN BARISAN PENTADBIR / PERSEMBAHAN MURID / CATATAN,
then DISEDIAKAN OLEH PENYEDIA / DISEMAK OLEH signature blocks (e-signing aware).
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
    ("week", "MINGGU"),
    ("date", "TARIKH"),
    ("day", "HARI"),
    ("teacher_speech", "GURU BERUCAP"),
    ("teacher_duty_1", "GURU BERTUGAS MINGGU INI"),
    ("teacher_duty_2", "GURU BERTUGAS MINGGU INI"),
    ("topic", "TAJUK PERHIMPUNAN"),
    ("agenda", "AGENDA"),
    ("headteacher_speech", "UCAPAN GURU BESAR"),
    ("admin_notices", "PESANAN BARISAN PENTADBIR"),
    ("performances", "PERSEMBAHAN MURID"),
    ("notes", "CATATAN"),
]


def _as_list(val):
    if isinstance(val, list):
        return [str(x).strip() for x in val if str(x).strip()]
    if not val:
        return []
    return [ln.strip() for ln in str(val).split("\n") if ln.strip()]


def build_assembly_pdf(data, out_path):
    st = styles()
    doc = SimpleDocTemplate(str(out_path), pagesize=A4,
                            leftMargin=16 * mm, rightMargin=16 * mm,
                            topMargin=14 * mm, bottomMargin=16 * mm,
                            title="LAPORAN PERHIMPUNAN")

    story = []
    story.extend(pdf_header_flowables(data, st))
    story.append(Paragraph("LAPORAN PERHIMPUNAN", st["title"]))

    def lp(t):
        return Paragraph(_esc(t), st["label"])
    def vp(k, default="—"):
        return Paragraph(_esc(data.get(k) or "") or default, st["value"])

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

    agenda = _as_list(data.get("agenda"))
    agenda_flow = _V([Paragraph("%d. %s" % (i + 1, _esc(v)), st["value"]) for i, v in enumerate(agenda)]) if agenda else Paragraph("—", st["value"])

    rows = [
        [lp("MINGGU"), vp("week"), lp("TARIKH"), vp("date"), lp("HARI"), vp("day")],
        [lp("GURU BERUCAP"), vp("teacher_speech"), "", "", "", ""],
        [lp("GURU BERTUGAS MINGGU INI"), vp("teacher_duty_1"), lp("GURU BERTUGAS MINGGU INI"), vp("teacher_duty_2"), "", ""],
        [lp("TAJUK PERHIMPUNAN"), vp("topic"), "", "", "", ""],
        [lp("AGENDA"), agenda_flow, "", "", "", ""],
    ]
    main = Table(rows, colWidths=[34 * mm, 50 * mm, 34 * mm, 50 * mm])
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

    # report table (4 columns)
    story.append(Spacer(1, 8))
    report = Table([
        [Paragraph("UCAPAN GURU BESAR", st["label"]), Paragraph("PESANAN BARISAN PENTADBIR", st["label"]),
         Paragraph("PERSEMBAHAN MURID", st["label"]), Paragraph("CATATAN", st["label"])],
        [Paragraph(_esc(data.get("headteacher_speech") or "TIADA"), st["value"]),
         Paragraph(_esc(data.get("admin_notices") or "TIADA"), st["value"]),
         Paragraph(_esc(data.get("performances") or "TIADA"), st["value"]),
         Paragraph(_esc(data.get("notes") or ""), st["value"])],
    ], colWidths=[42 * mm, 42 * mm, 42 * mm, 42 * mm])
    report.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.8, colors.HexColor("#64748b")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2ff")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(report)

    story.append(Spacer(1, 36))
    sig = Table([[pdf_signature_flowable("penyedia", "DISEDIAKAN OLEH PENYEDIA:", data, st, data.get("disediakan_nama")),
                  pdf_signature_flowable("disemak", "DISEMAK OLEH:", data, st, data.get("disemak_nama"))]],
                colWidths=[84 * mm, 84 * mm])
    sig.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(sig)

    doc.build(story, canvasmaker=NumberedCanvas)
    return out_path


def build_assembly_docx(data, out_path):
    from docx.shared import Pt

    doc = new_doc()
    docx_header(doc, data)
    add_title(doc, "LAPORAN PERHIMPUNAN")

    table = doc.add_table(rows=0, cols=4)
    table.style = "Table Grid"
    agenda = _as_list(data.get("agenda"))
    agenda_txt = "\n".join("%d. %s" % (i + 1, x) for i, x in enumerate(agenda)) if agenda else "—"
    rows = [
        ("MINGGU", data.get("week"), "TARIKH", data.get("date")),
        ("GURU BERUCAP", data.get("teacher_speech"), "GURU BERTUGAS MINGGU INI", "%s / %s" % (data.get("teacher_duty_1") or "", data.get("teacher_duty_2") or "")),
        ("TAJUK PERHIMPUNAN", data.get("topic"), "", ""),
        ("AGENDA", agenda_txt, "", ""),
    ]
    for a, b, c, d in rows:
        cells = table.add_row().cells
        _docx_cell(cells[0], a, bold=True); _docx_shade(cells[0], "EEF2FF")
        _docx_cell(cells[1], b or "—")
        _docx_cell(cells[2], c, bold=True); _docx_shade(cells[2], "EEF2FF")
        _docx_cell(cells[3], d or "—")

    doc.add_paragraph()
    report = doc.add_table(rows=2, cols=4)
    report.style = "Table Grid"
    heads = ["UCAPAN GURU BESAR", "PESANAN BARISAN PENTADBIR", "PERSEMBAHAN MURID", "CATATAN"]
    vals = [data.get("headteacher_speech") or "TIADA", data.get("admin_notices") or "TIADA",
            data.get("performances") or "TIADA", data.get("notes") or ""]
    for j in range(4):
        _docx_cell(report.rows[0].cells[j], heads[j], bold=True); _docx_shade(report.rows[0].cells[j], "EEF2FF")
        _docx_cell(report.rows[1].cells[j], vals[j])

    doc.add_paragraph()
    doc.add_paragraph()
    docx_signature_block(doc, "penyedia", "DISEDIAKAN OLEH PENYEDIA:", data, data.get("disediakan_nama"))
    docx_signature_block(doc, "disemak", "DISEMAK OLEH:", data, data.get("disemak_nama"))

    doc.save(str(out_path))
    return out_path
