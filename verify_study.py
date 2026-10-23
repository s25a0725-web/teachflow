# -*- coding: utf-8 -*-
"""Verify Study Studio: notebooks, sources, chat, and all generation kinds."""
import io
import os
import tempfile

os.chdir(os.path.dirname(os.path.abspath(__file__)))
os.environ["TEACHFLOW_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")
os.environ["TEACHFLOW_UPLOAD_ROOT"] = tempfile.mkdtemp()

from app import app  # noqa: E402
from db import get_db  # noqa: E402

CONTENT = ("Photosynthesis is the process by which plants make food using sunlight. "
           "Chlorophyll is the green pigment in leaves. "
           "Plants take in carbon dioxide and release oxygen. "
           "Photosynthesis happens in the chloroplasts of plant cells.")

c = app.test_client()
c.post("/register", data={"email": "s@x.com", "name": "S", "password": "secret123"})
c.post("/login", data={"email": "s@x.com", "password": "secret123"})

# notebook
r = c.post("/study/notebooks", data={"name": "Science Notes"}, follow_redirects=True)
assert r.status_code == 200
db = get_db()
nbid = db.execute("SELECT id FROM notebooks").fetchone()["id"]
db.close()

# source upload
r = c.post(f"/study/notebooks/{nbid}/sources",
           data={"file": (io.BytesIO(CONTENT.encode()), "notes.txt")},
           content_type="multipart/form-data", follow_redirects=True)
assert r.status_code == 200
d = c.get(f"/study/notebook/{nbid}").get_json()
assert len(d["sources"]) == 1, d
print("source uploaded OK:", d["sources"][0]["name"], d["sources"][0]["kind"])

# chat
r = c.post("/study/chat", json={"notebook_id": nbid, "question": "What is photosynthesis?", "lang": "en"})
d = r.get_json()
assert d["answer"] and d["citations"], d
assert "photosynthesis" in d["answer"].lower()
print("chat OK:", d["answer"][:50], "| citations:", len(d["citations"]))

# summary
r = c.post("/study/generate", json={"notebook_id": nbid, "kind": "summary", "lang": "en", "level": "medium", "length": "short"})
d = r.get_json()
assert d["payload"]["summary"] and d["links"], d
print("summary OK:", d["payload"]["summary"][:60])

# quiz + save to bank
r = c.post("/study/generate", json={"notebook_id": nbid, "kind": "quiz", "lang": "en", "level": "medium", "length": "short"})
d = r.get_json()
qs = d["payload"]["questions"]
assert qs, d
print("quiz OK, questions:", len(qs))
r = c.post("/study/save-quiz", json={"title": "Photosynthesis Quiz", "questions": qs, "lang": "en", "subject": "Science"})
assert r.get_json()["ok"]
db = get_db()
assert db.execute("SELECT COUNT(*) c FROM quizzes").fetchone()["c"] >= 1
db.close()
print("save to quiz bank OK")

# flashcards
r = c.post("/study/generate", json={"notebook_id": nbid, "kind": "flashcards", "lang": "en", "level": "medium", "length": "short"})
d = r.get_json()
assert d["payload"]["cards"], d
assert c.get(f"/study/flashcards/{d['item_id']}").status_code == 200
print("flashcards OK, cards:", len(d["payload"]["cards"]))

# mindmap / booklet / infographic / audio
for k in ["mindmap", "booklet", "infographic"]:
    r = c.post("/study/generate", json={"notebook_id": nbid, "kind": k, "lang": "en", "level": "medium", "length": "short"})
    d = r.get_json()
    assert d["links"], (k, d)
    print(f"{k} OK")

r = c.post("/study/generate", json={"notebook_id": nbid, "kind": "audio", "lang": "en", "level": "medium", "length": "short"})
d = r.get_json()
assert d.get("audio_url"), d
print("audio generate OK")

# delete item / source / notebook
iid = d["item_id"]
c.post(f"/study/items/{iid}/delete")
src_id = c.get(f"/study/notebook/{nbid}").get_json()["sources"][0]["id"]
c.post(f"/study/sources/{src_id}/delete")
c.post(f"/study/notebooks/{nbid}/delete")
print("\nSTUDY OK")
