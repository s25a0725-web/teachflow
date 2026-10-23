# -*- coding: utf-8 -*-
"""Smart generation: a natural-language request -> the right document (RPH, Excel, letter, quiz...)."""
import re
from datetime import date
from uuid import uuid4

from docbuild import (build_docx, build_pptx, build_pdf, build_xlsx,  # noqa: F401
                      content_to_text, generate_content)
from generators import lesson_plan, generate_quiz

# --------------------------------------------------------------------------
# Detection
# --------------------------------------------------------------------------
SUBJECTS = [
    ("matematik", "Matematik"), ("math", "Matematik"), ("mathematics", "Matematik"), ("கணிதம்", "Matematik"),
    ("sains", "Sains"), ("science", "Sains"), ("அறிவியல்", "Sains"),
    ("bahasa melayu", "Bahasa Melayu"), ("melayu", "Bahasa Melayu"), ("bm", "Bahasa Melayu"),
    ("english", "English"), ("bahasa inggeris", "English"), ("inggeris", "English"),
    ("sejarah", "Sejarah"), ("history", "Sejarah"), ("வரலாறு", "Sejarah"),
    ("geografi", "Geografi"), ("geography", "Geografi"),
    ("tamil", "Bahasa Tamil"), ("தமிழ்", "Bahasa Tamil"),
    ("reka bentuk", "RBT"), ("rbt", "RBT"),
    ("pendidikan islam", "Pendidikan Islam"), ("islam", "Pendidikan Islam"),
    ("pendidikan moral", "Pendidikan Moral"), ("moral", "Pendidikan Moral"),
    ("sains komputer", "Asas Sains Komputer"), ("ask", "Asas Sains Komputer"),
    ("seni", "Pendidikan Seni"), ("art", "Pendidikan Seni"),
]

MS_WORDS = ["buat", "untuk", "murid", "kelas", "tahun", "soalan", "markah", "kehadiran", "jadual",
            "surat", "notis", "rancangan", "pengajaran", "tajuk", "topik", "mesyuarat", "sila",
            "saya", "nak", "rph", "e-rph", "erph", "pibg", "sekolah", "pecahan", "guru", "pelajar",
            "cikgu", "hari", "bulan", "minggu", "semua", "cara", "senarai", "borang", "laporan"]


def detect_lang(text):
    if re.search(r"[\u0B80-\u0BFF]", text):
        return "ta"
    t = text.lower()
    score = sum(1 for w in MS_WORDS if re.search(r"\b" + re.escape(w) + r"\b", t))
    return "ms" if score >= 2 else "en"


def detect_subject(text):
    t = text.lower()
    for alias, canon in SUBJECTS:
        if alias in t:
            return canon
    return "Umum"


def detect_grade(text):
    t = text.lower()
    m = re.search(r"(?:tahun|darjah|year|grade)\s*(\d{1,2})", t) or re.search(r"(?:tingkatan|form)\s*(\d{1,2})", t)
    return int(m.group(1)) if m else None


def detect_count(text):
    t = text.lower()
    m = re.search(r"(\d{1,3})\s*(?:murid|student|pelajar|orang|pupil|pelajar)", t)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d{1,3})\s*(?:murid|student|pelajar)", t)
    return 30


def detect_doc_type(text):
    t = text.lower()
    if re.search(r"\b(rph|e-rph|erph)\b", t) or any(k in t for k in ("lesson plan", "lesson", "rancangan pengajaran", "rancangan", "பாடத்திட்டம்", "பாட திட்டம்")):
        return "rph"
    if any(k in t for k in ("excel", "spreadsheet", "xlsx", "marksheet", "markah", "mark list", "senarai markah", "gred", "kehadiran", "attendance", "jadual", "timetable", "time table", "jadual waktu", "jadual bertugas")):
        return "excel"
    if any(k in t for k in ("presentation", "slide", "ppt", "slaid", "pembentangan", "powerpoint", "slides")):
        return "pptx"
    if any(k in t for k in ("quiz", "soalan", "uasa", "exam", "peperiksaan", "kuiz", "pentaksiran", "கேள்வி")):
        return "quiz"
    if any(k in t for k in ("notis", "notice", "surat", "letter", "memo", "circular", "pengumuman", "jemputan", "invitation", "kebenaran")):
        return "letter"
    if any(k in t for k in ("laporan", "report", "sijil", "certificate")):
        return "report"
    return "doc"


def extract_topic(text, subject, lang):
    """Remove detected subject/grade/doc-type words, return the leftover topic."""
    t = text.lower()
    for alias, _ in SUBJECTS:
        t = re.sub(r"\b" + re.escape(alias) + r"\b", " ", t)
    t = re.sub(r"(?:tahun|darjah|year|grade|tingkatan|form)\s*\d{1,2}", " ", t)
    for w in ("buat", "sila", "saya", "nak", "untuk", "topik", "topic", "tajuk", "mengenai", "tentang",
              "pasal", "about", "on", "the", "a", "an", "of", "untuk", "dan", "and", "create", "make",
              "generate", "buatkan", "sediakan", "rph", "e-rph", "erph", "lesson", "plan", "excel",
              "spreadsheet", "notis", "notice", "surat", "letter", "soalan", "quiz", "markah",
              "kehadiran", "jadual", "kelas", "murid", "pelajar", "student", "buku", "tahun", "hari ini",
              "laporan", "report", "presentation", "powerpoint", "slide", "slides", "slaid", "pembentangan"):
        t = re.sub(r"\b" + re.escape(w) + r"\b", " ", t)
    t = re.sub(r"\s+", " ", t).strip(" ,-:.")
    return t or "Umum"


def classify_excel(text):
    t = text.lower()
    if any(k in t for k in ("kehadiran", "attendance", "kedatangan")):
        return "attendance"
    if any(k in t for k in ("jadual", "timetable", "time table", "jadual waktu", "bertugas")):
        return "timetable"
    return "marksheet"


# --------------------------------------------------------------------------
# Labels (trilingual)
# --------------------------------------------------------------------------
RPH_LABELS = {
    "en": {"title": "Daily Lesson Plan (RPH)", "subject": "Subject", "class": "Class", "date": "Date",
           "time": "Time", "theme": "Theme", "topic": "Topic", "obj": "Learning Objectives",
           "act": "Teaching Activities", "induksi": "Set Induction", "perkembangan": "Lesson Development",
           "penutup": "Closure", "bbm": "Teaching Aids (BBM)", "assess": "Assessment", "ref": "Reflection"},
    "ms": {"title": "Rancangan Pengajaran Harian (RPH)", "subject": "Mata Pelajaran", "class": "Kelas",
           "date": "Tarikh", "time": "Masa", "theme": "Tema", "topic": "Tajuk",
           "obj": "Objektif Pembelajaran", "act": "Aktiviti Pengajaran", "induksi": "Set Induksi",
           "perkembangan": "Perkembangan", "penutup": "Penutup", "bbm": "Bahan Bantu Mengajar (BBM)",
           "assess": "Penilaian", "ref": "Refleksi"},
    "ta": {"title": "தினசரி பாடத்திட்டம் (RPH)", "subject": "பாடம்", "class": "வகுப்பு", "date": "தேதி",
           "time": "நேரம்", "theme": "கருப்பொருள்", "topic": "தலைப்பு", "obj": "கற்றல் நோக்கங்கள்",
           "act": "கற்பித்தல் செயல்பாடுகள்", "induksi": "தொடக்க செயல்பாடு", "perkembangan": "வளர்ச்சி நிலை",
           "penutup": "முடிவு", "bbm": "கற்பித்தல் கருவிகள் (BBM)", "assess": "மதிப்பீடு", "ref": "பிரதிபலிப்பு"},
}

CLASS_LABEL = {"en": "Year", "ms": "Tahun", "ta": "தரம்"}


def _grade_label(grade, lang):
    return f"{CLASS_LABEL.get(lang, 'Year')} {grade}" if grade else f"{CLASS_LABEL.get(lang, 'Year')} 5"


# --------------------------------------------------------------------------
# RPH
# --------------------------------------------------------------------------
def _make_rph(subject, topic, grade, lang):
    L = RPH_LABELS.get(lang, RPH_LABELS["en"])
    g = _grade_label(grade, lang)
    today = date.today().strftime("%d/%m/%Y")
    lp = lesson_plan(topic, subject, g, 60, lang)
    lines = [x for x in lp.split("\n")]
    content = {
        "title": L["title"],
        "sections": [
            {"heading": L["obj"], "bullets": [f"{topic}" + (" — objektif" if lang == "ms" else ""),
                                              ("Pada akhir pelajaran, murid dapat:" if lang == "ms" else "By the end of the lesson, students can:")]},
            {"heading": L["act"], "bullets": [L["induksi"], L["perkembangan"], L["penutup"]]},
            {"heading": L["bbm"], "bullets": ["Buku teks" if lang == "ms" else "Textbook",
                                              "Lembaran kerja" if lang == "ms" else "Worksheet",
                                              "LCD / projektor"]},
            {"heading": L["assess"], "bullets": ["Soalan lisan" if lang == "ms" else "Oral questions",
                                                 "Latihan bertulis" if lang == "ms" else "Written exercise"]},
            {"heading": L["ref"], "bullets": ["Murid mencapai objektif." if lang == "ms" else "Objectives achieved."]},
        ],
    }
    meta = [(L["subject"], subject), (L["class"], g), (L["date"], today),
            (L["time"], "60 minit" if lang == "ms" else "60 minutes"), (L["theme"], topic), (L["topic"], topic)]
    return content, meta


# --------------------------------------------------------------------------
# Excel
# --------------------------------------------------------------------------
def _make_excel(subject, topic, grade, lang, subtype, n):
    if subtype == "attendance":
        days = list(range(1, 32))
        headers = ["Bil", "Nama Murid"] + [str(d) for d in days]
        rows = [[i, f"Murid {i}"] + [""] * 31 for i in range(1, n + 1)]
        return "Kehadiran", headers, rows
    if subtype == "timetable":
        times = ["07:30-08:00", "08:00-08:30", "08:30-09:00", "09:00-09:30", "09:30-10:00",
                 "10:30-11:00", "11:00-11:30", "11:30-12:00", "12:00-12:30", "12:30-13:00"]
        days = ["Isnin", "Selasa", "Rabu", "Khamis", "Jumaat"]
        headers = ["Masa"] + days
        rows = [[t] + [""] * 5 for t in times]
        return "Jadual Waktu", headers, rows
    headers = ["Bil", "Nama Murid", "Ujian 1", "Ujian 2", "Pentaksiran", "Jumlah", "Gred"]
    rows = []
    for i in range(1, n + 1):
        r = i + 1
        rows.append([i, f"Murid {i}", "", "", "", f"=SUM(C{r}:E{r})", ""])
    return "Markah " + subject, headers, rows


# --------------------------------------------------------------------------
# Letter / Notice
# --------------------------------------------------------------------------
def _make_letter(subject, topic, grade, lang):
    L = {"en": ("Notice", "Date", "To", "Dear all,", "This is to inform you that"),
         "ms": ("Notis", "Tarikh", "Kepada", "Kepada semua,", "Dimaklumkan bahawa"),
         "ta": ("அறிவிப்பு", "தேதி", "பெறுநர்", "அனைவருக்கும்,", "இது தொடர்பாக அறிவிக்கப்படுகிறது")}.get(lang)
    title, dlbl, tolbl, dear, body = L
    today = date.today().strftime("%d/%m/%Y")
    content = {"title": title, "sections": [
        {"heading": "", "bullets": [f"{body} {topic}."]},
        {"heading": ("Sekian, terima kasih." if lang == "ms" else "Thank you."), "bullets": []},
    ]}
    meta = [(dlbl, today), (tolbl, "Semua guru / ibu bapa" if lang == "ms" else "All teachers / parents")]
    return content, meta


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------
def _make_report(subject, topic, grade, lang):
    H = {"en": ["Introduction", "Findings", "Recommendations", "Conclusion"],
         "ms": ["Pengenalan", "Dapatan", "Cadangan", "Kesimpulan"],
         "ta": ["அறிமுகம்", "கண்டுபிடிப்புகள்", "பரிந்துரைகள்", "முடிவு"]}.get(lang)
    content = {"title": topic, "sections": [{"heading": h, "bullets": [topic]} for h in H]}
    return content, None


# --------------------------------------------------------------------------
# Main entry
# --------------------------------------------------------------------------
def smart_generate(text, out_dir):
    """Interpret the request and build the right file. Returns {fname, preview, kind}."""
    text = (text or "").strip()
    if not text:
        text = "lesson plan"
    lang = detect_lang(text)
    subject = detect_subject(text)
    grade = detect_grade(text)
    dtype = detect_doc_type(text)
    topic = extract_topic(text, subject, lang)
    out_dir = __import__("pathlib").Path(out_dir)

    if dtype == "rph":
        content, meta = _make_rph(subject, topic, grade, lang)
        name = uuid4().hex[:8] + ".docx"
        build_docx(content, out_dir / name, meta=meta)
        return {"fname": name, "preview": content_to_text(content), "kind": "docx",
                "label": content["title"]}

    if dtype == "excel":
        n = detect_count(text)
        sheet, headers, rows = _make_excel(subject, topic, grade, lang, classify_excel(text), n)
        name = uuid4().hex[:8] + ".xlsx"
        build_xlsx(sheet, headers, rows, out_dir / name)
        return {"fname": name, "preview": "", "kind": "xlsx", "label": sheet}

    if dtype == "quiz":
        qs = generate_quiz(subject, topic, grade, 10, "medium", lang, "mixed")
        lines = [topic]
        n_obj = 0
        for i, q in enumerate(qs, 1):
            if q.get("type") in ("obj", "mcq"):
                n_obj += 1
            lines.append(f"## Soalan {i}")
            lines.append("- " + q["q"])
            for o in q.get("options", []):
                lines.append("-   " + o)
            lines.append("- Jawapan: " + q["a"])
        content = {"title": topic, "sections": [{"heading": "Kertas Soalan", "bullets": lines[1:]}]}
        name = uuid4().hex[:8] + ".docx"
        build_docx({"title": f"Kuiz: {topic}", "sections": [{"heading": "Soalan", "bullets": [q['q'] for q in qs]}]}, out_dir / name)
        # rebuild preview from the same structure
        preview = content_to_text({"title": f"Kuiz: {topic}",
                                   "sections": [{"heading": "Soalan", "bullets": [q['q'] for q in qs]}]})
        return {"fname": name, "preview": preview, "kind": "docx", "label": "Kuiz"}

    if dtype == "letter":
        content, meta = _make_letter(subject, topic, grade, lang)
        name = uuid4().hex[:8] + ".docx"
        build_docx(content, out_dir / name, meta=meta)
        return {"fname": name, "preview": content_to_text(content), "kind": "docx",
                "label": content["title"]}

    if dtype == "report":
        content, meta = _make_report(subject, topic, grade, lang)
        name = uuid4().hex[:8] + ".docx"
        build_docx(content, out_dir / name, meta=meta)
        return {"fname": name, "preview": content_to_text(content), "kind": "docx",
                "label": content["title"]}

    if dtype == "pptx":
        content = generate_content(topic, "pptx", lang, "")
        name = uuid4().hex[:8] + ".pptx"
        build_pptx(content, out_dir / name)
        return {"fname": name, "preview": content_to_text(content), "kind": "pptx",
                "label": topic}

    # default generic doc
    content = generate_content(topic, "docx", lang, "")
    name = uuid4().hex[:8] + ".docx"
    build_docx(content, out_dir / name)
    return {"fname": name, "preview": content_to_text(content), "kind": "docx", "label": topic}
