# -*- coding: utf-8 -*-
"""UASA (KPM) style question bank for core subjects.

Each subject has topics; each topic has objective (MCQ) and subjective
(structured) questions in English and Bahasa Malaysia. Mathematics is
generated computationally in generators.py, so it is not in this bank.
Questions are written to match the UASA format: Bahagian A (objective) and
Bahagian B (subjective/structured), with KBAT-style wording where suitable.

Extend coverage by adding more topics per subject.
"""

SUBJECT_ALIASES = {
    "science": ["sains", "science", "biologi", "biology", "kimia", "chemistry", "fizik", "physics", "அறிவியல்"],
    "sejarah": ["sejarah", "history", "வரலாறு"],
    "bahasa_melayu": ["bahasa melayu", "bahasa malaysia", "melayu", "tatabahasa", "bm"],
    "english": ["english", "bahasa inggeris", "inggeris", "grammar", "vocabulary", "ஆங்கிலம்"],
}


def detect_subject(subject):
    s = (subject or "").lower()
    for key, aliases in SUBJECT_ALIASES.items():
        if any(a in s for a in aliases):
            return key
    return None


BANK = {
    "science": {
        "photosynthesis": {
            "keywords": ["photosynthesis", "fotosintesis", "plant", "tumbuhan", "leaf", "daun", "chlorophyll", "klorofil"],
            "en": {
                "objective": [
                    {"q": "Which gas do plants take in for photosynthesis?", "options": ["Oxygen", "Carbon dioxide", "Nitrogen", "Hydrogen"], "a": "Carbon dioxide"},
                    {"q": "Photosynthesis mainly takes place in which part of the plant?", "options": ["Root", "Stem", "Leaf", "Flower"], "a": "Leaf"},
                    {"q": "Which green pigment captures sunlight during photosynthesis?", "options": ["Chlorophyll", "Haemoglobin", "Melanin", "Keratin"], "a": "Chlorophyll"},
                    {"q": "Which of these is a product of photosynthesis?", "options": ["Carbon dioxide", "Oxygen", "Nitrogen", "Water vapour"], "a": "Oxygen"},
                ],
                "subjective": [
                    {"q": "State two raw materials needed for photosynthesis.", "a": "Carbon dioxide and water (with sunlight and chlorophyll)."},
                    {"q": "Give one way photosynthesis is important to animals.", "a": "It produces oxygen (and food/glucose) that animals need."},
                    {"q": "What is the main source of energy for photosynthesis?", "a": "Sunlight."},
                ],
            },
            "ms": {
                "objective": [
                    {"q": "Gas manakah yang diambil oleh tumbuhan untuk fotosintesis?", "options": ["Oksigen", "Karbon dioksida", "Nitrogen", "Hidrogen"], "a": "Karbon dioksida"},
                    {"q": "Fotosintesis terutamanya berlaku di bahagian manakah pada tumbuhan?", "options": ["Akar", "Batang", "Daun", "Bunga"], "a": "Daun"},
                    {"q": "Pigmen hijau yang menyerap cahaya matahari semasa fotosintesis ialah?", "options": ["Klorofil", "Hemoglobin", "Melanin", "Keratin"], "a": "Klorofil"},
                    {"q": "Antara berikut, yang manakah hasil fotosintesis?", "options": ["Karbon dioksida", "Oksigen", "Nitrogen", "Wap air"], "a": "Oksigen"},
                ],
                "subjective": [
                    {"q": "Nyatakan dua bahan mentah yang diperlukan untuk fotosintesis.", "a": "Karbon dioksida dan air (dengan cahaya matahari dan klorofil)."},
                    {"q": "Berikan satu kepentingan fotosintesis kepada haiwan.", "a": "Menghasilkan oksigen (dan makanan/glukosa) yang diperlukan haiwan."},
                    {"q": "Apakah sumber tenaga utama bagi fotosintesis?", "a": "Cahaya matahari."},
                ],
            },
        },
        "matter": {
            "keywords": ["jirim", "matter", "states of matter", "pepejal", "cecair", "solid", "liquid"],
            "en": {
                "objective": [
                    {"q": "Which state of matter has a fixed shape and fixed volume?", "options": ["Solid", "Liquid", "Gas", "Plasma"], "a": "Solid"},
                    {"q": "Water changes to ice through which process?", "options": ["Melting", "Freezing", "Evaporation", "Condensation"], "a": "Freezing"},
                    {"q": "Which process changes a liquid into a gas?", "options": ["Freezing", "Condensation", "Evaporation", "Melting"], "a": "Evaporation"},
                ],
                "subjective": [
                    {"q": "State the three states of matter.", "a": "Solid, liquid and gas."},
                    {"q": "Give one example of condensation in daily life.", "a": "Water droplets forming on a cold glass."},
                ],
            },
            "ms": {
                "objective": [
                    {"q": "Keadaan jirim yang manakah mempunyai bentuk dan isi padu yang tetap?", "options": ["Pepejal", "Cecair", "Gas", "Plasma"], "a": "Pepejal"},
                    {"q": "Air berubah menjadi ais melalui proses?", "options": ["Peleburan", "Pembekuan", "Penyejatan", "Kondensasi"], "a": "Pembekuan"},
                    {"q": "Proses yang menukarkan cecair kepada gas ialah?", "options": ["Pembekuan", "Kondensasi", "Penyejatan", "Peleburan"], "a": "Penyejatan"},
                ],
                "subjective": [
                    {"q": "Nyatakan tiga keadaan jirim.", "a": "Pepejal, cecair dan gas."},
                    {"q": "Berikan satu contoh kondensasi dalam kehidupan harian.", "a": "Titisan air terbentuk pada gelas sejuk."},
                ],
            },
        },
        "electricity": {
            "keywords": ["elektrik", "electric", "current", "arus", "litar", "circuit"],
            "en": {
                "objective": [
                    {"q": "Which material is a good conductor of electricity?", "options": ["Copper", "Rubber", "Wood", "Plastic"], "a": "Copper"},
                    {"q": "The unit of electric current is the ...", "options": ["Volt", "Ampere", "Ohm", "Watt"], "a": "Ampere"},
                    {"q": "Which of these is an electrical insulator?", "options": ["Iron", "Copper", "Rubber", "Aluminium"], "a": "Rubber"},
                ],
                "subjective": [
                    {"q": "Name one safety rule when using electricity.", "a": "Do not touch switches with wet hands."},
                    {"q": "State one source of electrical energy.", "a": "Battery or a power station (generator)."},
                ],
            },
            "ms": {
                "objective": [
                    {"q": "Bahan yang manakah pengalir elektrik yang baik?", "options": ["Kuprum", "Getah", "Kayu", "Plastik"], "a": "Kuprum"},
                    {"q": "Unit bagi arus elektrik ialah?", "options": ["Volt", "Ampere", "Ohm", "Watt"], "a": "Ampere"},
                    {"q": "Antara berikut, yang manakah penebat elektrik?", "options": ["Besi", "Kuprum", "Getah", "Aluminium"], "a": "Getah"},
                ],
                "subjective": [
                    {"q": "Nyatakan satu peraturan keselamatan semasa menggunakan elektrik.", "a": "Jangan sentuh suis dengan tangan basah."},
                    {"q": "Nyatakan satu sumber tenaga elektrik.", "a": "Bateri atau stesen janakuasa (penjana)."},
                ],
            },
        },
    },
    "sejarah": {
        "melaka": {
            "keywords": ["melaka", "malacca", "kesultanan", "sultanate"],
            "en": {
                "objective": [
                    {"q": "Who founded the Malacca Sultanate?", "options": ["Parameswara", "Hang Tuah", "Sultan Mahmud Shah", "Tun Perak"], "a": "Parameswara"},
                    {"q": "Melaka became a famous port mainly because of its ...", "options": ["strategic location", "large army", "gold mines", "climate"], "a": "strategic location"},
                    {"q": "Which waterway made Melaka an important trade route?", "options": ["Strait of Malacca", "Suez Canal", "Strait of Hormuz", "Panama Canal"], "a": "Strait of Malacca"},
                ],
                "subjective": [
                    {"q": "State one factor that made Melaka a successful trading port.", "a": "Its strategic location along the Strait of Malacca."},
                    {"q": "Name the famous Melakan admiral (laksamana).", "a": "Hang Tuah."},
                ],
            },
            "ms": {
                "objective": [
                    {"q": "Siapakah pengasas Kesultanan Melayu Melaka?", "options": ["Parameswara", "Hang Tuah", "Sultan Mahmud Shah", "Tun Perak"], "a": "Parameswara"},
                    {"q": "Melaka menjadi pelabuhan terkenal terutamanya kerana ...", "options": ["kedudukan strategik", "tentera yang besar", "lombong emas", "iklim"], "a": "kedudukan strategik"},
                    {"q": "Selat yang manakah menjadikan Melaka laluan perdagangan penting?", "options": ["Selat Melaka", "Terusan Suez", "Selat Hormuz", "Terusan Panama"], "a": "Selat Melaka"},
                ],
                "subjective": [
                    {"q": "Nyatakan satu faktor kejayaan Melaka sebagai pelabuhan.", "a": "Kedudukan strategik di sepanjang Selat Melaka."},
                    {"q": "Namakan laksamana Melaka yang terkenal.", "a": "Hang Tuah."},
                ],
            },
        },
        "merdeka": {
            "keywords": ["merdeka", "kemerdekaan", "independence", "1957", "malaysia day", "hari kebangsaan"],
            "en": {
                "objective": [
                    {"q": "Malaya gained independence on ...", "options": ["31 August 1957", "16 September 1963", "31 August 1963", "1 January 1957"], "a": "31 August 1957"},
                    {"q": "Who was the first Prime Minister of Malaysia?", "options": ["Tunku Abdul Rahman", "Tun Abdul Razak", "Tun Hussein Onn", "Mahathir Mohamad"], "a": "Tunku Abdul Rahman"},
                    {"q": "Where was Malaya's independence declared?", "options": ["Merdeka Stadium", "Dataran Merdeka", "Parliament House", "Istana Negara"], "a": "Merdeka Stadium"},
                ],
                "subjective": [
                    {"q": "State the meaning of 'Merdeka'.", "a": "Independence / freedom from colonial rule."},
                    {"q": "Name one leader involved in gaining independence.", "a": "Tunku Abdul Rahman."},
                ],
            },
            "ms": {
                "objective": [
                    {"q": "Tanah Melayu mencapai kemerdekaan pada ...", "options": ["31 Ogos 1957", "16 September 1963", "31 Ogos 1963", "1 Januari 1957"], "a": "31 Ogos 1957"},
                    {"q": "Siapakah Perdana Menteri Malaysia yang pertama?", "options": ["Tunku Abdul Rahman", "Tun Abdul Razak", "Tun Hussein Onn", "Mahathir Mohamad"], "a": "Tunku Abdul Rahman"},
                    {"q": "Di manakah kemerdekaan Tanah Melayu diisytiharkan?", "options": ["Stadium Merdeka", "Dataran Merdeka", "Bangunan Parlimen", "Istana Negara"], "a": "Stadium Merdeka"},
                ],
                "subjective": [
                    {"q": "Nyatakan maksud 'Merdeka'.", "a": "Kemerdekaan / bebas daripada penjajahan."},
                    {"q": "Namakan seorang pemimpin yang terlibat dalam mencapai kemerdekaan.", "a": "Tunku Abdul Rahman."},
                ],
            },
        },
    },
    "bahasa_melayu": {
        "kata_nama": {
            "keywords": ["kata nama", "noun", "kata nama khas"],
            "ms": {
                "objective": [
                    {"q": "Antara berikut, yang manakah kata nama?", "options": ["meja", "berlari", "cantik", "tetapi"], "a": "meja"},
                    {"q": "Dalam ayat 'Ahmad membaca buku', perkataan 'buku' ialah ...", "options": ["kata nama", "kata kerja", "kata adjektif", "kata sendi"], "a": "kata nama"},
                    {"q": "Kata nama khas ditulis dengan ...", "options": ["huruf besar pada huruf pertama", "huruf kecil", "tanda koma", "tanda seru"], "a": "huruf besar pada huruf pertama"},
                ],
                "subjective": [
                    {"q": "Berikan satu contoh kata nama khas.", "a": "Contoh: Ali, Kuala Lumpur, Proton."},
                    {"q": "Berikan satu contoh kata kerja.", "a": "Contoh: berlari, menulis, membaca."},
                ],
            },
        },
        "simpulan_bahasa": {
            "keywords": ["simpulan bahasa", "peribahasa", "idiom"],
            "ms": {
                "objective": [
                    {"q": "'Buah tangan' bermaksud ...", "options": ["hadiah atau oleh-oleh", "buah di atas tangan", "sejenis makanan", "wang"], "a": "hadiah atau oleh-oleh"},
                    {"q": "'Ringan tulang' bermaksud ...", "options": ["rajin bekerja", "malas", "sakit", "kuat"], "a": "rajin bekerja"},
                    {"q": "'Anak emas' bermaksud ...", "options": ["orang yang disayangi", "anak kecil", "barang kemas", "anak sulung"], "a": "orang yang disayangi"},
                ],
                "subjective": [
                    {"q": "Berikan maksud 'berat tulang'.", "a": "Malas bekerja."},
                    {"q": "Bina satu ayat menggunakan simpulan bahasa 'buah hati'.", "a": "Contoh: 'Dia ialah buah hati ibu bapanya.'"},
                ],
            },
        },
    },
    "english": {
        "grammar": {
            "keywords": ["grammar", "tense", "noun", "verb", "article", "tatabahasa"],
            "en": {
                "objective": [
                    {"q": "Choose the correct word: 'She ___ to school every day.'", "options": ["go", "goes", "going", "gone"], "a": "goes"},
                    {"q": "Which of these is a noun?", "options": ["happy", "table", "quickly", "run"], "a": "table"},
                    {"q": "Choose the correct article: '___ apple a day.'", "options": ["An", "A", "Some", "The"], "a": "An"},
                ],
                "subjective": [
                    {"q": "Give the past tense of 'go'.", "a": "went"},
                    {"q": "Give one example of an adjective.", "a": "Example: happy, tall, beautiful."},
                ],
            },
        },
        "vocabulary": {
            "keywords": ["vocabulary", "vocab", "spelling", "antonym", "synonym"],
            "en": {
                "objective": [
                    {"q": "Which word means the same as 'happy'?", "options": ["sad", "joyful", "angry", "tired"], "a": "joyful"},
                    {"q": "Choose the correct spelling:", "options": ["recieve", "receive", "receeve", "receve"], "a": "receive"},
                    {"q": "Which word is the opposite (antonym) of 'hot'?", "options": ["warm", "cold", "boiling", "sunny"], "a": "cold"},
                ],
                "subjective": [
                    {"q": "Give one synonym of 'big'.", "a": "large / huge."},
                    {"q": "Give one antonym of 'fast'.", "a": "slow."},
                ],
            },
        },
    },
}


def find_bank(subject_id, topic, lang):
    """Return (objective_list, subjective_list) for a matched topic, or None."""
    subj = BANK.get(subject_id)
    if not subj:
        return None
    t = (topic or "").lower()
    for tid, entry in subj.items():
        for kw in entry.get("keywords", []):
            if kw in t or (t and t in kw):
                content = entry.get(lang) or entry.get("en") or entry.get("ms")
                return content.get("objective", []), content.get("subjective", [])
    return None


def compose_bank_quiz(obj_list, sub_list, num, qtype):
    """Build a question list from bank questions, honouring the requested type."""
    qs = []
    if qtype == "objective":
        for i in range(num):
            o = obj_list[i % len(obj_list)] if obj_list else None
            if o:
                qs.append({"type": "obj", "q": o["q"], "options": o["options"], "a": o["a"]})
    elif qtype == "subjective":
        for i in range(num):
            s = sub_list[i % len(sub_list)] if sub_list else None
            if s:
                qs.append({"type": "sub", "q": s["q"], "options": [], "a": s["a"]})
    else:  # mixed: alternate objective and subjective
        for i in range(num):
            if i % 2 == 0 and obj_list:
                o = obj_list[(i // 2) % len(obj_list)]
                qs.append({"type": "obj", "q": o["q"], "options": o["options"], "a": o["a"]})
            elif sub_list:
                s = sub_list[(i // 2) % len(sub_list)]
                qs.append({"type": "sub", "q": s["q"], "options": [], "a": s["a"]})
            elif obj_list:
                o = obj_list[i % len(obj_list)]
                qs.append({"type": "obj", "q": o["q"], "options": o["options"], "a": o["a"]})
    return qs
