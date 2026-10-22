# TeachFlow

A bilingual (English + Bahasa Malaysia) web system that reduces teachers' workload.

## Features
- Lesson plan generator (from a topic)
- Quiz / worksheet generator (math is auto-generated; other subjects use question templates)
- Grading with auto-suggested feedback
- Attendance & timetable
- Student progress reports
- Parent messages generated from reports
- Documents: upload any file type, organize in personal folders,
  extractive summary, text editing, and e-signature (draw + request signatures via link)

## Run it
```
cd teachflow
.venv/Scripts/python -m pip install -r requirements.txt   # already done
.venv/Scripts/python app.py
```
Then open http://127.0.0.1:5000

The first account you register becomes admin; later accounts are teachers.
Each teacher only sees their own data and their own document folder.

## Notes
- No external API is needed; all generation is offline (rule/template based).
- Documents are stored under `uploads/documents/<teacher_id>/`.
- Signatures are stored as PNGs under `uploads/signatures/`.
- Set TEACHFLOW_SECRET env var in production to a long random string.
