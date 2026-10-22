# -*- coding: utf-8 -*-
"""Offline content generators: lesson plans, KPM-style quizzes, feedback, reports.

All generators work without any external API. Questions follow the Malaysian
Ministry of Education (KPM) exam style: objective (multiple choice) and
structured/subjective items with higher-order (KBAT) wording, in three languages.
"""
import random

# --------------------------------------------------------------------------
# Lesson plan phrases per language
# --------------------------------------------------------------------------
LP = {
    "en": {
        "objectives": "Learning objectives",
        "materials": "Materials",
        "warmup": "Warm-up / Starter",
        "main": "Main activity",
        "diff": "Differentiation",
        "assess": "Assessment",
        "homework": "Homework",
        "obj_by_end": "By the end of the lesson, students will be able to:",
        "obj_define": "- Define and explain {topic} in their own words.",
        "obj_apply": "- Apply {topic} to solve at least one real-world problem.",
        "obj_compare": "- Compare and contrast key ideas within {topic}.",
        "materials_list": "Whiteboard/markers, worksheets, {topic} reference notes, and digital resources if available.",
        "warmup_q": "Pose a short question: \u201cWhat do you already know about {topic}?\u201d Take 2-3 responses and link them to today's goal.",
        "warmup_activity": "Quick think-pair-share on {topic} to activate prior knowledge.",
        "main_steps": [
            "Introduce {topic} with a short explanation and a worked example.",
            "Guide students through a group activity applying {topic}.",
            "Have students complete a short individual practice task on {topic}.",
        ],
        "diff_support": "For struggling learners: provide sentence starters and worked examples on {topic}.",
        "diff_extend": "For advanced learners: challenge them to explain {topic} or extend the task to a new context.",
        "assess_activity": "Exit ticket: one question on {topic} to check understanding before leaving.",
        "assess_observe": "Observe group work and note who can independently apply {topic}.",
        "homework_task": "Complete the worksheet on {topic} and be ready to discuss one question next lesson.",
    },
    "ms": {
        "objectives": "Objektif pembelajaran",
        "materials": "Bahan",
        "warmup": "Set induksi",
        "main": "Aktiviti utama",
        "diff": "Pembezaan",
        "assess": "Pentaksiran",
        "homework": "Kerja rumah",
        "obj_by_end": "Pada akhir pelajaran, murid dapat:",
        "obj_define": "- Menyatakan dan menerangkan {topic} dengan perkataan sendiri.",
        "obj_apply": "- Mengaplikasikan {topic} untuk menyelesaikan sekurang-kurangnya satu masalah sebenar.",
        "obj_compare": "- Membanding beza idea utama dalam {topic}.",
        "materials_list": "Papan putih/penanda, lembaran kerja, nota rujukan {topic}, dan sumber digital jika ada.",
        "warmup_q": "Kemukakan soalan ringkas: \u201cApa yang anda sudah tahu tentang {topic}?\u201d Ambil 2-3 jawapan dan kaitkan dengan matlamat hari ini.",
        "warmup_activity": "Aktiviti think-pair-share ringkas tentang {topic} untuk mengaktifkan pengetahuan sedia ada.",
        "main_steps": [
            "Perkenalkan {topic} dengan penerangan ringkas dan satu contoh yang dikerjakan.",
            "Bimbing murid melalui aktiviti berkumpulan yang mengaplikasikan {topic}.",
            "Minta murid menyiapkan tugasan latihan individu tentang {topic}.",
        ],
        "diff_support": "Murid yang lemah: berikan rangka ayat dan contoh langkah demi langkah tentang {topic}.",
        "diff_extend": "Murid cemerlang: cabar mereka untuk menerangkan {topic} atau mengembangkan tugasan ke konteks baharu.",
        "assess_activity": "Exit ticket: satu soalan tentang {topic} untuk menyemak kefahaman sebelum keluar.",
        "assess_observe": "Perhatikan kerja berkumpulan dan catat siapa yang boleh mengaplikasikan {topic} secara sendiri.",
        "homework_task": "Siapkan lembaran kerja tentang {topic} dan bersedia membincangkan satu soalan pada pelajaran seterusnya.",
    },
    "ta": {
        "objectives": "கற்றல் நோக்கங்கள்",
        "materials": "பொருட்கள்",
        "warmup": "முன்னோட்டம்",
        "main": "முக்கிய செயல்பாடு",
        "diff": "வேறுபடுத்தல்",
        "assess": "மதிப்பீடு",
        "homework": "வீட்டுப்பாடம்",
        "obj_by_end": "பாடத்தின் முடிவில், மாணவர்கள் பின்வருவனவற்றைச் செய்ய முடியும்:",
        "obj_define": "- {topic} வரையறுத்து சொந்த வார்த்தைகளில் விளக்குதல்.",
        "obj_apply": "- {topic} ஐப் பயன்படுத்தி குறைந்தது ஒரு நிஜப் பிரச்சினையைத் தீர்த்தல்.",
        "obj_compare": "- {topic} இல் உள்ள முக்கிய கருத்துகளை ஒப்பிட்டு வேறுபடுத்துதல்.",
        "materials_list": "வெள்ளைப் பலகை/மார்க்கர், பயிற்சித் தாள்கள், {topic} குறிப்புகள், மற்றும் கிடைத்தால் டிஜிட்டல் வளங்கள்.",
        "warmup_q": "சிறு கேள்வி: \u201c{topic} பற்றி உங்களுக்கு ஏற்கனவே என்ன தெரியும்?\u201d 2-3 பதில்களைப் பெற்று இன்றைய இலக்குடன் இணைக்கவும்.",
        "warmup_activity": "{topic} பற்றிய முன் அறிவை செயல்படுத்த சிறிய think-pair-share செயல்பாடு.",
        "main_steps": [
            "{topic} ஐ சுருக்கமான விளக்கத்துடனும் ஒரு எடுத்துக்காட்டுடனும் அறிமுகப்படுத்தவும்.",
            "{topic} ஐப் பயன்படுத்தும் குழு செயல்பாட்டில் மாணவர்களை வழிநடத்தவும்.",
            "{topic} பற்றிய தனிப்பட்ட பயிற்சிப் பணியை மாணவர்கள் முடிக்கச் செய்யவும்.",
        ],
        "diff_support": "பின்தங்கிய மாணவர்களுக்கு: {topic} க்கான வாக்கியத் தொடக்கங்கள் மற்றும் படிப்படியான எடுத்துக்காட்டுகள் வழங்கவும்.",
        "diff_extend": "சிறந்த மாணவர்களுக்கு: {topic} ஐ விளக்கவோ அல்லது பணியை புதிய சூழலுக்கு விரிவுபடுத்தவோ சவால் விடவும்.",
        "assess_activity": "வெளியேறும் டிக்கெட்: {topic} பற்றிய ஒரு கேள்வி மூலம் புரிதலைச் சரிபார்க்கவும்.",
        "assess_observe": "குழு வேலையைக் கவனித்து, யார் {topic} ஐத் தனித்து பயன்படுத்த முடிகிறது எனக் குறிக்கவும்.",
        "homework_task": "{topic} பற்றிய பயிற்சித் தாளை முடித்து, அடுத்த பாடத்தில் ஒரு கேள்வியை விவாதிக்கத் தயாராகுங்கள்.",
    },
}


def lesson_plan(topic, subject, grade, duration, lang="en"):
    """Return a structured lesson plan as plain text with sections."""
    T = LP.get(lang, LP["en"])
    lines = []
    lines.append(T["objectives"])
    lines.append(T["obj_by_end"])
    lines.append(T["obj_define"].format(topic=topic))
    lines.append(T["obj_apply"].format(topic=topic))
    lines.append(T["obj_compare"].format(topic=topic))
    lines.append("")
    lines.append(T["materials"])
    lines.append(T["materials_list"].format(topic=topic))
    lines.append("")
    lines.append(T["warmup"] + f" ({max(5, duration // 6)} min)")
    lines.append(T["warmup_q"].format(topic=topic))
    lines.append(T["warmup_activity"].format(topic=topic))
    lines.append("")
    lines.append(T["main"] + f" ({max(15, duration // 2)} min)")
    for i, step in enumerate(T["main_steps"], 1):
        lines.append(f"{i}. " + step.format(topic=topic))
    lines.append("")
    lines.append(T["diff"])
    lines.append(T["diff_support"].format(topic=topic))
    lines.append(T["diff_extend"].format(topic=topic))
    lines.append("")
    lines.append(T["assess"])
    lines.append(T["assess_activity"].format(topic=topic))
    lines.append(T["assess_observe"].format(topic=topic))
    lines.append("")
    lines.append(T["homework"])
    lines.append(T["homework_task"].format(topic=topic))
    return "\n".join(lines)


# --------------------------------------------------------------------------
# KPM-style structured / subjective question stems (KBAT-oriented)
# --------------------------------------------------------------------------
KPM_STEMS = {
    "en": [
        ("Define {topic} and give one example.", "A clear definition with one correct example."),
        ("State two characteristics of {topic}.", "Any two accurate characteristics from the lesson."),
        ("Explain {topic} in your own words.", "A correct explanation using key terms."),
        ("Describe the importance of {topic} in daily life.", "A description linking {topic} to a real-life context."),
        ("Compare and contrast two ideas within {topic}.", "Two similarities and one difference."),
        ("Give two examples of {topic}.", "Two accurate examples."),
        ("Why is {topic} important? Justify your answer.", "A justified reason showing understanding."),
        ("Suggest one way to apply {topic} in a new situation.", "A realistic application of the concept."),
    ],
    "ms": [
        ("Definisikan {topic} dan berikan satu contoh.", "Definisi yang jelas dengan satu contoh yang betul."),
        ("Nyatakan dua ciri {topic}.", "Mana-mana dua ciri yang tepat daripada pelajaran."),
        ("Terangkan {topic} dengan perkataan anda sendiri.", "Penerangan yang betul menggunakan istilah utama."),
        ("Huraikan kepentingan {topic} dalam kehidupan harian.", "Huraian yang mengaitkan {topic} dengan konteks sebenar."),
        ("Banding beza dua idea dalam {topic}.", "Dua persamaan dan satu perbezaan."),
        ("Berikan dua contoh {topic}.", "Dua contoh yang tepat."),
        ("Mengapakah {topic} penting? Berikan justifikasi anda.", "Alasan yang berjustifikasi menunjukkan kefahaman."),
        ("Cadangkan satu cara untuk mengaplikasikan {topic} dalam situasi baharu.", "Aplikasi konsep yang realistik."),
    ],
    "ta": [
        ("{topic} வரையறுத்து ஓர் எடுத்துக்காட்டு தருக.", "தெளிவான வரையறை மற்றும் சரியான எடுத்துக்காட்டு."),
        ("{topic} இன் இரண்டு பண்புகளைக் கூறுக.", "பாடத்திலிருந்து ஏதேனும் இரண்டு சரியான பண்புகள்."),
        ("{topic} ஐ உன் சொந்த வார்த்தைகளில் விளக்குக.", "முக்கிய சொற்களைப் பயன்படுத்திய சரியான விளக்கம்."),
        ("அன்றாட வாழ்வில் {topic} இன் முக்கியத்துவத்தை விவரிக்க.", "{topic} ஐ நிஜ வாழ்வுடன் இணைக்கும் விளக்கம்."),
        ("{topic} இல் உள்ள இரண்டு கருத்துகளை ஒப்பிட்டு வேறுபடுத்து.", "இரண்டு ஒற்றுமைகள் மற்றும் ஒரு வேறுபாடு."),
        ("{topic} க்கு இரண்டு எடுத்துக்காட்டுகள் தருக.", "இரண்டு சரியான எடுத்துக்காட்டுகள்."),
        ("{topic} ஏன் முக்கியமானது? உன் விடையை நியாயப்படுத்து.", "புரிதலைக் காட்டும் நியாயமான காரணம்."),
        ("புதிய சூழலில் {topic} ஐப் பயன்படுத்த ஒரு வழி பரிந்துரை.", "கருத்தின் நடைமுறைப் பயன்பாடு."),
    ],
}


# --------------------------------------------------------------------------
# Mathematics (computed, KPM exam wording)
# --------------------------------------------------------------------------
SUBJECT_ALIASES = ["math", "mathematics", "matematik", "addmath", "additional mathematics", "கணிதம்"]

NUMERIC_OPS = {"addition", "subtraction", "multiplication", "division", "mixed"}

MATH_OPS = {
    "easy": ["addition", "subtraction", "multiplication"],
    "medium": ["multiplication", "division", "mixed"],
    "hard": ["algebra", "fraction", "exponent", "mixed"],
}

MATH_WORDING = {
    "en": {"sub": "Calculate: {expr}"},
    "ms": {"sub": "Selesaikan: {expr}"},
    "ta": {"sub": "கணக்கிடுக: {expr}"},
}

MATH_TEXT = {
    "en": {
        "solve": "Solve for x: {a}x + {b} = {c}",
        "fraction": "Simplify {a}/{b} (give the decimal to 1 d.p.)",
        "exponent": "{a}\u00b2 - {b}\u00b2",
    },
    "ms": {
        "solve": "Cari nilai x: {a}x + {b} = {c}",
        "fraction": "Permudahkan {a}/{b} (beri perpuluhan kepada 1 t.t.)",
        "exponent": "{a}\u00b2 - {b}\u00b2",
    },
    "ta": {
        "solve": "x இன் மதிப்பைக் காண்க: {a}x + {b} = {c}",
        "fraction": "{a}/{b} ஐ எளிமைப்படுத்து (1 தசம இடம் வரை)",
        "exponent": "{a}\u00b2 - {b}\u00b2",
    },
}


def _is_math(subject):
    s = (subject or "").lower()
    return any(a in s for a in SUBJECT_ALIASES)


def _grade_number(grade):
    digits = "".join(c for c in str(grade or "") if c.isdigit())
    return int(digits) if digits else 6


def _math_item(op, level, lang):
    T = MATH_TEXT.get(lang, MATH_TEXT["en"])
    if op == "addition":
        a = random.randint(10 * max(1, level - 2), 30 * max(1, level))
        b = random.randint(1, 20 * max(1, level))
        return f"{a} + {b}", a + b
    if op == "subtraction":
        a = random.randint(10 * max(1, level - 2), 30 * max(1, level))
        b = random.randint(1, a)
        return f"{a} - {b}", a - b
    if op == "multiplication":
        a = random.randint(2, 12 + level)
        b = random.randint(2, 12 + level)
        return f"{a} \u00d7 {b}", a * b
    if op == "division":
        b = random.randint(2, 9 + level)
        q = random.randint(2, 9 + level)
        return f"{b * q} \u00f7 {b}", q
    if op == "mixed":
        a = random.randint(2, 9 + level)
        b = random.randint(1, 9)
        return f"{a} + {b} \u00d7 {a}", b * a + a
    if op == "algebra":
        a = random.randint(2, 9)
        b = random.randint(1, 20)
        return T["solve"].format(a=a, b=b, c=a * 5 + b), 5
    if op == "fraction":
        a = random.randint(1, 9)
        b = random.randint(2, 9)
        return T["fraction"].format(a=a, b=b), round(a / b, 1)
    if op == "exponent":
        a = random.randint(2, 12)
        b = random.randint(1, a - 1)
        return T["exponent"].format(a=a, b=b), a * a - b * b
    # fallback
    return f"{level} + {level}", level * 2


def _math_options(ans, level):
    opts = {ans}
    attempts = 0
    while len(opts) < 4 and attempts < 300:
        d = random.choice([1, 2, 3, 5, 10, -1, -2, -5, -10, (ans // 2) or 1, (2 * ans) if ans else 1])
        c = ans + d
        if c >= 0 and c != ans and c not in opts:
            opts.add(c)
        attempts += 1
    i = 1
    while len(opts) < 4:
        c = ans + i * 3
        if c >= 0 and c not in opts:
            opts.add(c)
        i += 1
    opts = list(opts)
    random.shuffle(opts)
    return [str(o) for o in opts]


def _math_questions(num, difficulty, grade, qtype, lang):
    level = _grade_number(grade)
    W = MATH_WORDING.get(lang, MATH_WORDING["en"])
    qs = []
    for _ in range(num):
        op = random.choice(MATH_OPS.get(difficulty, MATH_OPS["medium"]))
        expr, answer = _math_item(op, level, lang)
        can_obj = op in NUMERIC_OPS
        is_obj = can_obj and (qtype == "objective" or (qtype == "mixed" and random.random() < 0.5))
        if is_obj:
            qs.append({
                "type": "obj",
                "q": f"{expr} =",
                "options": _math_options(answer, level),
                "a": str(answer),
            })
        else:
            q = expr if op not in NUMERIC_OPS else W["sub"].format(expr=expr)
            qs.append({"type": "sub", "q": q, "options": [], "a": str(answer)})
    return qs


def generate_quiz(subject, topic, grade, num, difficulty, lang="en", qtype="mixed"):
    """Return a list of question dicts: {type, q, options, a}."""
    num = max(1, min(int(num), 30))
    if _is_math(subject):
        return _math_questions(num, difficulty, grade or topic or subject, qtype, lang)
    from question_bank import detect_subject, find_bank, compose_bank_quiz
    subj_id = detect_subject(subject)
    if subj_id:
        bank = find_bank(subj_id, topic, lang)
        if bank:
            return compose_bank_quiz(bank[0], bank[1], num, qtype)
    stems = KPM_STEMS.get(lang, KPM_STEMS["en"])
    qs = []
    for i in range(num):
        q_tpl, a_tpl = stems[i % len(stems)]
        qs.append({"type": "sub", "q": q_tpl.format(topic=topic), "options": [], "a": a_tpl})
    return qs


# --------------------------------------------------------------------------
# Feedback comment bank
# --------------------------------------------------------------------------
FEEDBACK = {
    "en": [
        ("excellent", "Excellent work, {name}. You show a strong understanding of the material. Keep challenging yourself with extension tasks."),
        ("good", "Good effort, {name}. You understand most of the material. Review the parts you missed and you will be at the top."),
        ("satisfactory", "Satisfactory, {name}. You are on the right track. Focus on the areas where you lost marks and ask for help early."),
        ("improve", "{name}, this needs more work. Let's review the topic together and set a small improvement goal for next time."),
        ("support", "{name}, please see me for extra support. We will break the topic into smaller steps so it feels manageable."),
    ],
    "ms": [
        ("excellent", "Cemerlang, {name}. Anda menunjukkan kefahaman yang kuat. Teruskan mencabar diri dengan tugasan lanjutan."),
        ("good", "Usaha yang baik, {name}. Anda memahami kebanyakan bahan. Ulang kaji bahagian yang tersilap dan anda akan ke tahap teratas."),
        ("satisfactory", "Memuaskan, {name}. Anda berada di landasan yang betul. Fokus pada bahagian yang hilang markah dan minta bantuan awal."),
        ("improve", "{name}, tugasan ini perlu lebih usaha. Mari kita ulang kaji topik ini bersama dan tetapkan matlamat kecil untuk penambahbaikan."),
        ("support", "{name}, sila jumpa saya untuk sokongan tambahan. Kita akan pecahkan topik ini kepada langkah kecil agar mudah difahami."),
    ],
    "ta": [
        ("excellent", "சிறப்பு, {name}. நீங்கள் பாடத்தை நன்றாகப் புரிந்துள்ளீர்கள். மேலும் சவாலான பணிகளில் முயலுங்கள்."),
        ("good", "நல்ல முயற்சி, {name}. பெரும்பாலானவற்றைப் புரிந்துள்ளீர்கள். தவறிய பகுதிகளை மீள்பார்வை செய்யுங்கள்."),
        ("satisfactory", "திருப்திகரம், {name}. சரியான பாதையில் உள்ளீர்கள். மதிப்பெண் இழந்த பகுதிகளில் கவனம் செலுத்துங்கள்."),
        ("improve", "{name}, இதற்கு மேலும் முயற்சி தேவை. தலைப்பை மீள்பார்வை செய்து சிறிய இலக்கை அமைப்போம்."),
        ("support", "{name}, கூடுதல் உதவிக்கு என்னைச் சந்திக்கவும். தலைப்பை சிறிய படிகளாகப் பிரிப்போம்."),
    ],
}


def suggest_feedback(score, total, student_name, lang="en"):
    """Return a feedback comment based on the percentage score."""
    pct = 0 if total == 0 else (score / total) * 100
    bank = FEEDBACK.get(lang, FEEDBACK["en"])
    if pct >= 85:
        key = "excellent"
    elif pct >= 70:
        key = "good"
    elif pct >= 55:
        key = "satisfactory"
    elif pct >= 40:
        key = "improve"
    else:
        key = "support"
    for k, text in bank:
        if k == key:
            return text.format(name=student_name)
    return bank[-1][1].format(name=student_name)


# --------------------------------------------------------------------------
# Report card
# --------------------------------------------------------------------------
REPORT = {
    "en": {
        "comment_excellent": "{name} has performed excellently this term. Keep up the great work.",
        "comment_good": "{name} has shown good progress. With consistent effort, results will keep improving.",
        "comment_ok": "{name} is progressing steadily. Regular revision will strengthen the results.",
        "comment_weak": "{name} needs additional support and consistent practice. A follow-up meeting is recommended.",
    },
    "ms": {
        "comment_excellent": "{name} menunjukkan prestasi cemerlang pada penggal ini. Teruskan usaha yang baik.",
        "comment_good": "{name} menunjukkan kemajuan yang baik. Dengan usaha yang konsisten, keputusan akan terus meningkat.",
        "comment_ok": "{name} berkembang secara konsisten. Ulang kaji yang tetap akan mengukuhkan keputusan.",
        "comment_weak": "{name} memerlukan sokongan tambahan dan latihan yang konsisten. Perjumpaan susulan adalah disyorkan.",
    },
    "ta": {
        "comment_excellent": "{name} இந்தப் பருவத்தில் சிறப்பாகச் செயல்பட்டுள்ளார். தொடர்ந்து நன்றாகச் செய்யுங்கள்.",
        "comment_good": "{name} நல்ல முன்னேற்றம் காட்டியுள்ளார். தொடர்ந்த முயற்சியால் முடிவுகள் மேம்படும்.",
        "comment_ok": "{name} நிலையாக முன்னேறி வருகிறார். வழக்கமான மீள்பார்வை முடிவுகளை வலுப்படுத்தும்.",
        "comment_weak": "{name} க்கு கூடுதல் ஆதரவும் தொடர்ந்த பயிற்சியும் தேவை. பின்தொடர்தல் சந்திப்பு பரிந்துரைக்கப்படுகிறது.",
    },
}


def report_comment(avg, name, lang="en"):
    T = REPORT.get(lang, REPORT["en"])
    if avg >= 85:
        key = "comment_excellent"
    elif avg >= 70:
        key = "comment_good"
    elif avg >= 50:
        key = "comment_ok"
    else:
        key = "comment_weak"
    return T[key].format(name=name)
