# Interview Prep Question Rotator

Adaptive interview practice: store Q&A cards, rate your confidence (1–5) after each answer, and the app shows low-confidence questions more often.

Built with GitHub Copilot as an AI-assisted development course project. See `project-report.md` for the full development write-up.

## Requirements
- Python 3.10+ (standard library only, no packages to install)

## Run the app
Browser (recommended):
```bash
python3 -m interview_rotator web
```
Then open http://127.0.0.1:8000 (stop with Ctrl+C). Use `--port 8080` for another port.

Terminal:
```bash
python3 -m interview_rotator
```
Choose **7** to load 12 sample questions, then **1** to practice. Both modes accept `--data path/to/file.json` to use another data file.

## Run the tests
```bash
python3 -m unittest discover -v
```

## Project structure
```
interview_rotator/
  core/
    models.py       # Card data model                 (Module A)
    cards.py        # CardService: CRUD, practice, stats (Module A)
    rotation.py     # weighted next-card selection    (Module B)
    storage.py      # JSON file storage, safe save/recovery (Module C)
    validation.py   # input rules                     (Module E)
  cli.py            # terminal menu                   (Module D)
  web/
    server.py       # pages, routing, http.server     (Module F)
    templates/      # HTML layout
    static/         # CSS
  sample_cards.py   # 12 sample interview questions
  main.py           # entry point: cli or web mode
  __main__.py       # python3 -m interview_rotator
tests/              # unittest tests (73)
```

Cards are stored in `data/cards.json` (created automatically). Set `INTERVIEW_ROTATOR_DATA` to use another file.

## Status
| Module | Status |
|---|---|
| A – Card Management | ✅ done |
| B – Adaptive Rotation Engine | ✅ done |
| C – Data Persistence (JSON) | ✅ done |
| D – CLI Interface | ✅ done |
| E – Validation & Testing | ✅ done |
| F – Web UI | ✅ done |
