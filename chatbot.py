# -*- coding: utf-8 -*-
"""Friendly, conversational assistant for the school system.

Talks like a helpful friend/colleague. Rule-based (works offline) with an
optional real-AI layer: if OPENAI_API_KEY / TEACHFLOW_AI_KEY is set, the LLM
answers every question and this rule engine is only the fallback.
"""
import os
import re

SHORT_KW = 3


def _match(message, kw):
    if len(kw) <= SHORT_KW:
        return re.search(r"(?<![a-z0-9])" + re.escape(kw) + r"(?![a-z0-9])", message) is not None
    return kw in message


INTENTS = [
    {
        "keywords": ["hi", "hello", "hey", "salam", "hai", "selamat", "vanakkam", "வணக்கம்", "good morning", "selamat pagi"],
        "responses": {
            "en": "Hey! 😄 Great to see you. I'm here whenever you need a hand — ask me anything, like how to make a quiz or mark attendance. What's on your mind?",
            "ms": "Hai! 😄 Seronok jumpa anda. Saya sentiasa ada untuk bantu — tanya apa-apa, macam cara buat kuiz atau tanda kehadiran. Apa yang anda nak tanya?",
            "ta": "வணக்கம்! 😄 உங்களைப் பார்ப்பதில் மகிழ்ச்சி. வினாத்தாள் அல்லது வருகை பற்றி என்ன வேண்டுமானாலும் கேளுங்கள். என்ன தெரிந்து கொள்ள வேண்டும்?",
        },
    },
    {
        "keywords": ["thank", "terima kasih", "nandri", "நன்றி", "thx", "thanks"],
        "responses": {
            "en": "Anytime! 😊 That's what friends are for.",
            "ms": "Sama-sama! 😊 Tak perlu segan, saya memang di sini untuk bantu.",
            "ta": "பரவாயில்லை! 😊 எப்போது வேண்டுமானாலும் கேளுங்கள்.",
        },
    },
    {
        "keywords": ["bye", "goodbye", "jumpa lagi", "selamat tinggal", "விடை"],
        "responses": {
            "en": "See you later! 👋 Have an awesome day at school — and don't forget to rest!",
            "ms": "Jumpa lagi! 👋 Semoga hari anda indah di sekolah — jangan lupa rehat ya!",
            "ta": "பிறகு சந்திப்போம்! 👋 பள்ளியில் நல்ல நாளாக அமையட்டும்!",
        },
    },
    {
        "keywords": ["who are you", "what are you", "siapakah anda", "நீங்கள் யார்", "what can you do", "apa yang anda boleh"],
        "responses": {
            "en": "I'm the AI Smart Teacher Assistant for SJK(T) Sepang 🤖 — your friendly helper around here. Think of me as your teaching buddy: I know how every button works and I'm happy to walk you through it. Just ask!",
            "ms": "Saya AI Smart Teacher Assistant untuk SJK(T) Sepang 🤖 — pembantu mesra anda. Anggap saya rakan mengajar anda: saya tahu semua fungsi di sini dan sedia tunjukkan caranya. Tanya sahaja!",
            "ta": "நான் SJK(T) செபாங்கிற்கான AI Smart ஆசிரியர் உதவியாளர் 🤖 — உங்கள் நட்பு உதவியாளர். என்னை உங்கள் கற்பித்தல் தோழனாக நினையுங்கள். கேளுங்கள்!",
        },
    },
    {
        "keywords": ["quiz", "kuiz", "soalan", "question", "uasa", "வினா", "exam", "peperiksaan", "தேர்வு"],
        "responses": {
            "en": "Easy one! 😎 Go to 'Quiz Generator', type the topic, subject, level and how many questions you want, then hit Generate. Boom — UASA-style questions with answers, ready to print.\nLittle tip: pick Objective, Subjective or Mixed to get the exact format you like.",
            "ms": "Senang je! 😎 Pergi ke 'Penjana Kuiz', taip topik, subjek, tingkatan dan bilangan soalan, lepas tu tekan Jana. Boom — soalan gaya UASA dengan jawapan, sedia untuk dicetak.\nTip sikit: pilih Objektif, Subjektif atau Campuran ikut format yang anda suka.",
            "ta": "ரொம்ப எளிது! 😎 'வினா உருவாக்கி' சென்று, தலைப்பு, பாடம், நிலை, கேள்வி எண்ணிக்கை உள்ளிட்டு உருவாக்குங்கள். UASA பாணி வினாக்கள் விடைகளுடன் கிடைக்கும்.\nகுறிப்பு: பல்தேர்வு, விளக்க வகை அல்லது கலப்பு எனத் தேர்ந்தெடுக்கலாம்.",
        },
    },
    {
        "keywords": ["lesson plan", "rancangan", "rph", "பாடத்திட்டம்", "lesson", "teaching plan"],
        "responses": {
            "en": "No stress, this one's a breeze! 🌟 Open 'Lesson Plans', type your topic, and Generate. You'll get the whole plan — objectives, warm-up, activities, assessment, homework — all done for you.",
            "ms": "Jangan risau, yang ini mudah! 🌟 Buka 'Rancangan Pengajaran', taip topik, dan Jana. Anda dapat rancangan lengkap — objektif, set induksi, aktiviti, pentaksiran, kerja rumah — semua siap untuk anda.",
            "ta": "கவலை வேண்டாம், இது எளிது! 🌟 'பாடத்திட்டங்கள்' திறந்து தலைப்பை உள்ளிட்டு உருவாக்குங்கள். முழு திட்டமும் தயாராகக் கிடைக்கும்.",
        },
    },
    {
        "keywords": ["student", "pelajar", "murid", "மாணவர்", "add student", "daftar", "child", "budak"],
        "responses": {
            "en": "Let's do it together 😊: go to 'Classes & Students' → create a class → 'Add Student' with the name, IC number and parent email. Once that's in, the parent can log in with the IC number. Easy, right?",
            "ms": "Kita buat sama-sama 😊: pergi 'Kelas & Pelajar' → cipta kelas → 'Tambah Pelajar' dengan nama, nombor IC dan e-mel ibu bapa. Selepas itu, ibu bapa boleh log masuk guna nombor IC. Mudah kan?",
            "ta": "சேர்ந்து செய்வோம் 😊: 'வகுப்புகள் & மாணவர்கள்' → வகுப்பை உருவாக்கு → 'மாணவரைச் சேர்' பெயர், IC எண், பெற்றோர் மின்னஞ்சலுடன். அவ்வளவுதான்!",
        },
    },
    {
        "keywords": ["marks", "marking", "grade", "feedback", "markah", "gred", "தரம்", "pemarkahan", "grading", "nilai"],
        "responses": {
            "en": "Here's a little gift from the system 🎁: open 'Grading', create an assignment, type in the marks, and leave feedback blank — it writes a nice comment for you automatically. Saves you so much time!",
            "ms": "Ada hadiah kecil dari sistem untuk anda 🎁: buka 'Pemarkahan', cipta tugasan, masukkan markah, dan biarkan maklum balas kosong — ia tulis komen untuk anda secara automatik. Jimat banyak masa!",
            "ta": "ஒரு சிறிய பரிசு 🎁: 'தரமிடல்' திறந்து, பணியை உருவாக்கி, மதிப்பெண் இடுங்கள். கருத்தை காலியாக விட்டால் தானாக எழுதப்படும். நேரம் மிச்சம்!",
        },
    },
    {
        "keywords": ["attendance", "kehadiran", "hadir", "வருகை", "absen", "kedatangan"],
        "responses": {
            "en": "Quick as a wink ⚡: open 'Attendance', pick the class and date, tap Present / Late / Absent with the time, and Save. Staff attendance lives under 'Staff Attendance' if you need it.",
            "ms": "Sekelip mata ⚡: buka 'Kehadiran', pilih kelas dan tarikh, tanda Hadir / Lewat / Tidak hadir dengan masa, lepas tu Simpan. Kehadiran guru ada di bawah 'Kehadiran Guru'.",
            "ta": "மின்னல் வேகம் ⚡: 'வருகை' திறந்து, வகுப்பு மற்றும் தேதியைத் தேர்ந்தெடுத்து, நேரத்துடன் குறித்து சேமிக்கவும்.",
        },
    },
    {
        "keywords": ["timetable", "jadual", "நேர அட்டவணை", "schedule", "waktu"],
        "responses": {
            "en": "Open 'Timetable' and add each subject with its day and period — your whole week lines up nicely in one place. 😊",
            "ms": "Buka 'Jadual Waktu' dan tambah setiap subjek dengan hari dan waktunya — seluruh minggu anda tersusun kemas di satu tempat. 😊",
            "ta": "'கால அட்டவணை' திறந்து பாடங்களை நாள் மற்றும் காலத்துடன் சேர்க்கவும். உங்கள் வாரம் அழகாக அமையும். 😊",
        },
    },
    {
        "keywords": ["report", "laporan", "அறிக்கை", "keputusan", "result", "kad laporan", "report card"],
        "responses": {
            "en": "Open 'Reports', pick a student, and it's all there — grades, attendance rate and a ready comment. Parents see the same results (with your feedback) on their side. 👍",
            "ms": "Buka 'Laporan', pilih pelajar, dan semuanya ada — gred, kadar kehadiran dan ulasan siap. Ibu bapa melihat keputusan yang sama (dengan maklum balas anda) di bahagian mereka. 👍",
            "ta": "'அறிக்கைகள்' திறந்து மாணவரைத் தேர்ந்தெடுக்கவும் — மதிப்பெண்கள், வருகை, கருத்து எல்லாம் உள்ளது. 👍",
        },
    },
    {
        "keywords": ["parent", "ibu bapa", "பெற்றோர்", "ic", "login parent", "waris", "penjaga"],
        "responses": {
            "en": "Parents have their own door 🚪 — the 'Parent login' link. They register with their child's IC number and see just that child's results and your feedback. Just make sure you type the IC number (and parent email) when adding the student, and it links up automatically.",
            "ms": "Ibu bapa ada pintu sendiri 🚪 — pautan 'Log masuk ibu bapa'. Mereka daftar dengan nombor IC anak dan hanya melihat keputusan serta maklum balas anda. Pastikan anda masukkan nombor IC (dan e-mel) semasa tambah pelajar, nanti ia sambung sendiri.",
            "ta": "பெற்றோருக்கு தனி வாசல் உள்ளது 🚪 — 'பெற்றோர் உள்நுழைவு'. பிள்ளையின் IC எண்ணுடன் பதிவு செய்து முடிவுகளைப் பார்க்கிறார்கள். மாணவரைச் சேர்க்கும்போது IC எண்ணை உள்ளிடவும்.",
        },
    },
    {
        "keywords": ["document", "dokumen", "sign", "tandatangan", "ஆவணம்", "upload", "muat naik", "signature", "கையொப்பம்", "convert", "fail", "file", "tukar ke pdf", "tukar ke teks"],
        "responses": {
            "en": "Two easy ways 🗂️:\n1) 'Documents' page — upload anything, sort into folders, summarise, edit, sign.\n2) Right here in the chat — tap 📎, attach a file, and type your subject + 'convert to pdf' or 'convert to text'. I'll sort it into your subject folder for you.",
            "ms": "Dua cara mudah 🗂️:\n1) Halaman 'Dokumen' — muat naik apa sahaja, susun dalam folder, ringkas, sunting, tandatangan.\n2) Di sini dalam chat — tekan 📎, lampirkan fail, taip subjek + 'tukar ke pdf' atau 'tukar ke teks'. Saya susun ke folder subjek untuk anda.",
            "ta": "இரண்டு எளிய வழிகள் 🗂️:\n1) 'ஆவணங்கள்' — பதிவேற்றம், கோப்புறை, சுருக்கம், திருத்தம், கையொப்பம்.\n2) இங்கே chat இல் — 📎 அழுத்தி கோப்பை இணைத்து, பாடம் + 'pdf ஆக மாற்று' எனத் தட்டச்சு செய்யுங்கள்.",
        },
    },
    {
        "keywords": ["settings", "tetapan", "அமைப்புகள்", "logo", "admin", "school name", "nama sekolah", "tukar nama", "change name"],
        "responses": {
            "en": "If you're an admin, 'Settings' is your playground 🎨 — change the school name, logo, tagline, background theme, and manage users. Teachers won't see this menu.",
            "ms": "Kalau anda pentadbir, 'Tetapan' ialah taman permainan anda 🎨 — tukar nama sekolah, logo, cogan kata, tema latar belakang, dan urus pengguna. Guru tidak nampak menu ini.",
            "ta": "நீங்கள் நிர்வாகி என்றால் 'அமைப்புகள்' உங்கள் இடம் 🎨 — பள்ளி பெயர், லோகோ, பின்னணி பாணி மாற்றலாம், பயனர்களை நிர்வகிக்கலாம்.",
        },
    },
    {
        "keywords": ["language", "bahasa", "தமிழ்", "tamil", "melayu", "english", "மொழி", "tukar bahasa", "change language"],
        "responses": {
            "en": "Top-right corner! 😉 Tap EN / BM / தமிழ் and the whole system (me included) switches language instantly.",
            "ms": "Penjuru kanan atas! 😉 Tekan EN / BM / தமிழ் dan seluruh sistem (termasuk saya) bertukar bahasa serta-merta.",
            "ta": "மேல்-வலது மூலையில்! 😉 EN / BM / தமிழ் அழுத்தினால் முழு அமைப்பும் (நானும் சேர்த்து) மொழி மாறும்.",
        },
    },
    {
        "keywords": ["login", "register", "akaun", "account", "password", "kata laluan", "கடவுச்சொல்", "daftar", "lupa", "forgot", "reset", "tidak boleh masuk", "cannot login"],
        "responses": {
            "en": "Teachers register from the main login page — the very first account becomes the admin. Parents use 'Parent login'.\nForgot your password? No self-reset yet — just ask your admin, they can clear the account in Settings so you can register again. 😊",
            "ms": "Guru mendaftar dari halaman log masuk utama — akaun pertama menjadi pentadbir. Ibu bapa guna 'Log masuk ibu bapa'.\nLupa kata laluan? Belum ada set semula sendiri — minta pentadbir padam akaun di Tetapan supaya anda boleh daftar semula. 😊",
            "ta": "ஆசிரியர்கள் முதன்மை உள்நுழைவு பக்கத்தில் பதிவு செய்கிறார்கள் — முதல் கணக்கே நிர்வாகி. பெற்றோர் 'பெற்றோர் உள்நுழைவு' பயன்படுத்துகின்றனர்.",
        },
    },
    {
        "keywords": ["print", "cetak", "அச்சு", "pdf", "save pdf", "download"],
        "responses": {
            "en": "On quizzes and reports there's a 'Print / Save PDF' button 📄 — it opens the print dialog and hides the menus, so you get a clean sheet. Choose 'Save as PDF' to keep a digital copy.",
            "ms": "Pada kuiz dan laporan ada butang 'Cetak / Simpan PDF' 📄 — ia buka dialog cetak dan sorok menu untuk helaian yang kemas. Pilih 'Save as PDF' untuk simpan salinan digital.",
            "ta": "வினாத்தாள் மற்றும் அறிக்கையில் 'அச்சிடு / PDF சேமி' பொத்தான் உள்ளது 📄 — சுத்தமான அச்சு கிடைக்கும்.",
        },
    },
    {
        "keywords": ["kpm", "sukatan", "syllabus", "kurikulum", "standard", "dslp"],
        "responses": {
            "en": "Yep, the quiz generator follows the UASA (KPM) exam style 🎓 — objective (Section A) and structured/subjective (Section B) questions with KBAT-style wording, in English, BM and Tamil.",
            "ms": "Ya, penjana kuiz ikut gaya peperiksaan UASA (KPM) 🎓 — soalan objektif (Bahagian A) dan struktur/subjektif (Bahagian B) dengan gaya KBAT, dalam BI, BM dan Tamil.",
            "ta": "ஆம், வினா உருவாக்கி UASA (KPM) தேர்வு பாணியில் உள்ளது 🎓 — பல்தேர்வு மற்றும் விளக்க வகை வினாக்கள்.",
        },
    },
    {
        "keywords": ["help", "bantuan", "உதவி", "tolong", "cara guna", "how to use", "guide"],
        "responses": {
            "en": "I'm all yours! 😊 I can walk you through quizzes, lesson plans, grading, attendance, timetable, reports, parents, documents, settings, printing and login. What would you like?",
            "ms": "Saya sedia membantu! 😊 Saya boleh pandu anda tentang kuiz, rancangan pengajaran, pemarkahan, kehadiran, jadual, laporan, ibu bapa, dokumen, tetapan, cetakan dan log masuk. Apa yang anda nak?",
            "ta": "நான் தயார்! 😊 வினா, பாடத்திட்டம், தரமிடல், வருகை, கால அட்டவணை, அறிக்கை, பெற்றோர், ஆவணங்கள், அமைப்புகள் பற்றி வழிகாட்டுகிறேன்.",
        },
    },
]

FALLBACK = {
    "en": "Hmm, that one's a bit outside my notes. 🤔 But ask me about the system and I'm your guy — quiz, lesson plan, grading, attendance, reports, parents, documents, settings, printing, login. Pick one!",
    "ms": "Hmm, soalan tu di luar nota saya. 🤔 Tapi tanya pasal sistem dan saya sedia bantu — kuiz, rancangan pengajaran, pemarkahan, kehadiran, laporan, ibu bapa, dokumen, tetapan, cetakan, log masuk. Pilih satu!",
    "ta": "அது என் குறிப்புகளுக்கு வெளியே உள்ளது. 🤔 ஆனால் அமைப்பு பற்றிக் கேளுங்கள் — வினா, பாடத்திட்டம், தரமிடல், வருகை, அறிக்கை, பெற்றோர், ஆவணங்கள். ஏதாவது ஒன்றைத் தேர்ந்தெடுங்கள்!",
}


def respond(message, lang="en"):
    m = (message or "").lower()
    for intent in INTENTS:
        for kw in intent["keywords"]:
            if _match(m, kw):
                return intent["responses"].get(lang) or intent["responses"]["en"]
    return FALLBACK.get(lang, FALLBACK["en"])


# --------------------------------------------------------------------------
# Optional real-AI layer (activates when an API key is configured)
# --------------------------------------------------------------------------
def ai_respond(message, lang="en"):
    key = os.environ.get("OPENAI_API_KEY") or os.environ.get("TEACHFLOW_AI_KEY")
    if not key:
        return None
    base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    lang_name = {"en": "English", "ms": "Bahasa Malaysia", "ta": "Tamil"}.get(lang, "English")
    from persona import SYSTEM_PROMPT
    system = SYSTEM_PROMPT + "\n\nCurrent user language: " + lang_name + ". Respond in this language."
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": message},
        ],
        "max_tokens": 400,
    }
    try:
        import json
        import urllib.request
        req = urllib.request.Request(
            base.rstrip("/") + "/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + key},
        )
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"].strip()
    except Exception:
        return None
