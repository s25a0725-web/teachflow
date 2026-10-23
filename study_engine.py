# -*- coding: utf-8 -*-
"""Study Studio engine v2: BM25 retrieval, extractive answers, NotebookLM-style generation.

Everything here is offline (no API key required). If an API key is present the
ai_* hooks upgrade the quality further.
"""
import json
import math
import os
import random
import re
import urllib.request
from collections import Counter
from pathlib import Path

# --------------------------------------------------------------------------
# Tokenization / stopwords
# --------------------------------------------------------------------------
STOP = set("""
a an the and or but of to in on for with is are was were be been being has have had
it its as at by from into over under up down out about this that these those
what why when where which who whom how does do did can could will would should shall
tell me explain describe define list state name give show us we you your my i am
about around between during before after because so if then than too very also just
dan atau untuk yang di ke pada ialah adalah itu ini daripada kepada akan telah
dengan tanpa tidak juga serta jika kerana sebab maka lagi bukan dan yang apa mengapa
bagaimana bila di mana siapa berapa beritahu terangkan jelaskan huraikan nyatakan beri
ஒரு ஒன்று இது அது மற்றும் அல்லது என உள்ள ஆக இருந்த ஆகும் என்பது அந்த இந்த
என்ன ஏன் எப்படி எப்போது எங்கே யார் கூறு விளக்கு விவரி
""".split())


def tokenize(text):
    return [w for w in re.findall(r"[a-zA-Z0-9\u0B80-\u0BFF]+", (text or "").lower())
            if len(w) > 2 and w not in STOP]


def _sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?।])\s+|\n+", (text or "")) if s.strip()]


def chunk_text(text, size=500, overlap=100):
    """Paragraph-aware chunking; splits overlong paragraphs at sentence boundaries."""
    sents = _sentences(text)
    chunks, cur, curlen = [], [], 0
    for s in sents:
        if curlen + len(s) > size and cur:
            chunks.append(" ".join(cur))
            tail = cur[-1] if cur and len(cur[-1]) < overlap else ""
            cur = [tail] if tail else []
            curlen = len(tail)
        cur.append(s)
        curlen += len(s)
    if cur:
        chunks.append(" ".join(cur))
    return chunks


# --------------------------------------------------------------------------
# Extraction
# --------------------------------------------------------------------------
def fetch_url(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        html = r.read().decode("utf-8", "ignore")
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def ocr_image(path):
    try:
        import pytesseract
        from PIL import Image
        return pytesseract.image_to_string(Image.open(path))
    except Exception:
        return ""


def extract_pages(path, kind):
    if kind == "pdf":
        from pypdf import PdfReader
        rd = PdfReader(str(path))
        return [(i + 1, (p.extract_text() or "")) for i, p in enumerate(rd.pages)]
    if kind == "docx":
        from file_assistant import docx_to_text
        return [(1, docx_to_text(path))]
    if kind == "pptx":
        from pptx import Presentation
        prs = Presentation(str(path))
        return [(i + 1, "\n".join(sh.text_frame.text for sh in s.shapes if sh.has_text_frame))
                for i, s in enumerate(prs.slides)]
    if kind == "txt":
        return [(1, Path(path).read_text(encoding="utf-8", errors="ignore"))]
    if kind == "image":
        t = ocr_image(path)
        return [(1, t)] if t.strip() else []
    if kind == "url":
        t = fetch_url(path)
        return [(1, t)] if t else []
    return []


# --------------------------------------------------------------------------
# Retrieval: BM25 over the notebook's chunk collection
# --------------------------------------------------------------------------
def _bm25(query_tokens, doc_tokens, idf, avgdl, k1=1.5, b=0.75):
    tf = Counter(doc_tokens)
    dl = len(doc_tokens) or 1
    score = 0.0
    for w in set(query_tokens):
        if w in idf:
            f = tf.get(w, 0)
            score += idf[w] * (f * (k1 + 1)) / (f + k1 * (1 - b + b * dl / avgdl))
    return score


def retrieve(chunks, query, top_k=5):
    """chunks: list of dicts {text, source, page}. BM25-ranked."""
    q = tokenize(query)
    if not q or not chunks:
        return []
    docs = [tokenize(c["text"]) for c in chunks]
    n = len(docs)
    df = Counter()
    for d in docs:
        for w in set(d):
            df[w] += 1
    idf = {w: math.log((n - df[w] + 0.5) / (df[w] + 0.5) + 1.0) for w in df}
    avgdl = sum(len(d) for d in docs) / max(1, n)
    scored = [(_bm25(q, docs[i], idf, avgdl), chunks[i]) for i in range(n)]
    scored.sort(key=lambda x: -x[0])
    return [c for s, c in scored if s > 0][:top_k]


def answer(chunks, query, top_k=6, max_sents=3):
    """Extractive answer: top relevant sentences stitched together, with their chunks."""
    top = retrieve(chunks, query, top_k)
    q = set(tokenize(query))
    ranked = []
    for c in top:
        for s in _sentences(c["text"]):
            sw = tokenize(s)
            sc = len(q & set(sw))
            if sc > 0:
                ranked.append((sc, len(sw), s, c))
    ranked.sort(key=lambda x: (-x[0], x[1]))
    seen, parts, used = set(), [], []
    for sc, slen, s, c in ranked:
        if s in seen:
            continue
        seen.add(s)
        parts.append(s)
        if c not in used:
            used.append(c)
        if len(parts) >= max_sents:
            break
    if not parts:
        return {"found": False, "answer": "", "cites": []}
    return {"found": True, "answer": " ".join(parts), "cites": used}


# --------------------------------------------------------------------------
# Key terms & summarization (TextRank-lite)
# --------------------------------------------------------------------------
def key_terms(text, n=12):
    words = tokenize(text)
    freq = Counter(words)
    scored = [(freq[w], w) for w in freq]
    # bigrams (phrases)
    bigrams = [" ".join(bg) for bg in zip(words, words[1:]) if len(bg[0]) > 3 and len(bg[1]) > 3]
    bfreq = Counter(bigrams)
    scored += [(bfreq[b] * 2, b) for b in bfreq]
    # capitalized proper nouns
    for cap in set(re.findall(r"\b[A-Z][a-zA-Z]{2,}\b", text or "")):
        if cap.lower() not in STOP:
            scored.append((text.count(cap) * 3, cap))
    scored.sort(key=lambda x: -x[0])
    seen, out = set(), []
    for s, w in scored:
        if w in seen:
            continue
        seen.add(w)
        out.append(w)
        if len(out) >= n:
            break
    return out


def _sim(a, b):
    ta, tb = set(tokenize(a)), set(tokenize(b))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / (math.log(1 + len(ta)) + math.log(1 + len(tb)) + 1e-9)


def summarize(text, length="medium"):
    sents = _sentences(text)
    if not sents:
        return ""
    n = {"short": 4, "medium": 7, "long": 12}.get(length, 7)
    if len(sents) <= n:
        return " ".join(sents)
    scored = []
    for i, a in enumerate(sents):
        scored.append((sum(_sim(a, b) for j, b in enumerate(sents) if j != i), i, a))
    scored.sort(key=lambda x: -x[0])
    top = sorted(scored[:n], key=lambda x: x[1])
    return " ".join(a for _, _, a in top)


# --------------------------------------------------------------------------
# Quiz / flashcards / mindmap / booklet / infographic
# --------------------------------------------------------------------------
DEF_PAT = re.compile(r"\b(is|are|was|were|means|refers to|called|known as|ialah|adalah|merujuk|dikenali|என்பது)\b", re.I)


def _negate(sentence):
    m = re.search(r"\b(is|are|was|were|has|have|had|can|will|should)\b", sentence, re.I)
    if not m:
        return None
    return sentence[:m.start()] + m.group(0) + " not " + sentence[m.end():]


def _sent_for_term(sents, term):
    for s in sents:
        if term in s:
            return s
    return None


def _facts(sents):
    return [s for s in sents if DEF_PAT.search(s) and len(s) > 30]


def make_quiz(text, lang="en", level="medium", length="medium", n=6):
    sents = _sentences(text)
    terms = key_terms(text, 15)
    n = {"short": 4, "medium": 6, "long": 10}.get(length, 6)
    facts = _facts(sents)
    qs = []

    # 1) Cloze MCQs grounded in the source (strongest signal)
    for t in terms:
        if len(qs) >= n:
            break
        s = _sent_for_term(sents, t)
        if not s or len(s) > 250 or t not in s:
            continue
        stem = s.replace(t, "_____", 1)
        if stem == s:
            continue
        others = [x for x in terms if x != t and len(x) < 24]
        if len(others) < 3:
            continue
        opts = [t] + random.sample(others, 3)
        random.shuffle(opts)
        qs.append({"type": "mcq", "q": stem, "options": opts, "a": t})

    # 2) True / False from definitional facts
    for s in facts:
        if len(qs) >= n:
            break
        qs.append({"type": "tf", "q": s, "options": ["True", "False"], "a": "True"})
        neg = _negate(s)
        if neg and len(qs) < n:
            qs.append({"type": "tf", "q": neg, "options": ["True", "False"], "a": "False"})

    # 3) Short answer from KPM-style stems
    from generators import KPM_STEMS
    stems = KPM_STEMS.get(lang, KPM_STEMS["en"])
    topic = terms[0] if terms else "the topic"
    while len(qs) < n:
        qt, at = stems[len(qs) % len(stems)]
        qs.append({"type": "sub", "q": qt.format(topic=topic), "options": [], "a": at})
    return qs[:n]


def make_flashcards(text, n=10):
    sents = _sentences(text)
    terms = key_terms(text, n)
    cards, seen = [], set()
    for t in terms:
        s = _sent_for_term(sents, t)
        if not s:
            continue
        if t not in seen:
            seen.add(t)
            cards.append({"front": t, "back": s})
        cloze = s.replace(t, "_____", 1)
        if cloze != s and cloze not in seen:
            seen.add(cloze)
            cards.append({"front": cloze, "back": t})
        if len(cards) >= n:
            break
    return cards


def make_mindmap(title, text, n=10):
    terms = key_terms(text, n)
    sents = _sentences(text)
    mains = terms[:5]
    rest = terms[5:]
    branches = []
    for m in mains:
        leaves = []
        for t in rest:
            if any(m in s and t in s for s in sents):
                leaves.append(t)
        if not leaves:
            s = _sent_for_term(sents, m)
            if s:
                leaves.append(s[:60] + ("..." if len(s) > 60 else ""))
        branches.append({"node": m, "leaves": leaves[:4]})
    return {"central": title or "Topic", "branches": branches}


def make_booklet_content(title, text, lang="en", level="medium", length="medium"):
    sents = _sentences(text)
    terms = key_terms(text, 12)
    summ = summarize(text, length)
    quiz = make_quiz(text, lang, level, length, 6)
    T = {"en": ["Introduction", "Summary", "Exercises", "Glossary"],
         "ms": ["Pengenalan", "Ringkasan", "Latihan", "Glosari"],
         "ta": ["அறிமுகம்", "சுருக்கம்", "பயிற்சிகள்", "சொற்களஞ்சியம்"]}.get(lang)
    if not T:
        T = ["Introduction", "Summary", "Exercises", "Glossary"]
    sections = [{"heading": T[0], "bullets": [sents[0] if sents else "Introduction"]}]
    for t in terms[:6]:
        cs = [s for s in sents if t in s][:2]
        sections.append({"heading": t, "bullets": cs or [t]})
    sections.append({"heading": T[1], "bullets": _sentences(summ) or [summ]})
    sections.append({"heading": T[2], "bullets": [q["q"] for q in quiz]})
    gl = [f"{t}: {_sent_for_term(sents, t)}" for t in terms if _sent_for_term(sents, t)]
    sections.append({"heading": T[3], "bullets": gl[:6]})
    return {"title": title or "Study Booklet", "sections": sections,
            "contents": [s["heading"] for s in sections]}


def make_infographic(title, text, lang="en"):
    terms = key_terms(text, 8)
    summ = summarize(text, "short")
    sents = _sentences(text)
    stats = [("Ideas", len(terms)), ("Sentences", len(sents)), ("Words", len(tokenize(text)))]
    return {"title": title or "Infographic", "terms": terms, "summary": summ,
            "stats": stats, "lang": lang}


# --------------------------------------------------------------------------
# Optional AI (env-gated) — upgrades quality when a key is present
# --------------------------------------------------------------------------
def _ai_key():
    return os.environ.get("OPENAI_API_KEY") or os.environ.get("TEACHFLOW_AI_KEY")


def _ai_json(system, user, max_tokens=1800):
    key = _ai_key()
    if not key:
        return None
    base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    payload = {"model": model, "messages": [
        {"role": "system", "content": system}, {"role": "user", "content": user}], "max_tokens": max_tokens}
    try:
        req = urllib.request.Request(base.rstrip("/") + "/chat/completions",
                                     data=json.dumps(payload).encode("utf-8"),
                                     headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        text = data["choices"][0]["message"]["content"].strip().strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
        return json.loads(text)
    except Exception:
        return None


def ai_answer(question, chunks, lang):
    key = _ai_key()
    if not key:
        return None
    ctx = "\n\n".join(f"[{i + 1}] ({c['source']}, p.{c['page']}): {c['text']}"
                      for i, c in enumerate(chunks))
    lang_name = {"en": "English", "ms": "Bahasa Malaysia", "ta": "Tamil"}.get(lang, "English")
    system = ("You are a study assistant. Answer ONLY from the provided passages. "
              "Cite the passages using their [n] numbers inline. If the answer is not in the "
              "passages, say so clearly. Answer in " + lang_name + ".")
    data = _ai_json(system, f"Passages:\n{ctx}\n\nQuestion: {question}")
    return data if isinstance(data, dict) else {"answer": str(data) if data else ""}


def ai_generate(kind, text, lang, level, length):
    key = _ai_key()
    if not key:
        return None
    lang_name = {"en": "English", "ms": "Bahasa Malaysia", "ta": "Tamil"}.get(lang, "English")
    spec = {
        "quiz": '{"questions": [{"type": "mcq|tf|sub", "q": "...", "options": ["..."], "a": "..."}]}',
        "flashcards": '{"cards": [{"front": "...", "back": "..."}]}',
        "summary": '{"summary": "..."}',
        "mindmap": '{"central": "...", "branches": [{"node": "...", "leaves": ["..."]}]}',
        "booklet": '{"title": "...", "sections": [{"heading": "...", "bullets": ["..."]}]}',
        "infographic": '{"title": "...", "terms": ["..."], "summary": "...", "stats": [["Label", 0]]}',
    }.get(kind)
    if not spec:
        return None
    system = ("You are a teacher assistant. Generate the requested study material from the source "
              "text. Output ONLY valid JSON matching: " + spec + ". Write in " + lang_name + ".")
    return _ai_json(system, f"Level: {level}. Length: {length}.\n\nSource text:\n{text[:6000]}",
                    max_tokens=2200)
