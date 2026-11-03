# Prompt Log (GitHub Copilot Chat)

Record of key prompts used during development. Used to fill the
"Key prompts or interactions" parts of `project-report.md`.

| # | Date | Module | Prompt (short) | Result / what I changed |
|---|------|--------|----------------|-------------------------|
| 1 | 2026-11-03 | Planning | "Write a proper description of my Interview Prep Question Rotator idea and its system requirements, up to 1 page. It should have a web interface and a CLI." | Idea + FR1–FR7 (incl. web interface), NFR1–NFR6 written; reviewed and kept. |
| 2 | 2026-11-03 | Architecture | "Break the system down into technological modules with responsibilities, functions, inputs/outputs, dependencies and a folder structure." | Six modules in a layered design (shared core + CLI + Web UI); weighted formula `6 − confidence` chosen. |
| 3 | 2026-11-03 | Module A | "Set up the project skeleton and build Module A: Card dataclass + CardService (CRUD, filter, practice, stats) with injected storage." | Generated `models.py`, `cards.py`, `validation.py` and tests with an in-memory fake storage. |
| 4 | 2026-11-03 | Setup | (pip install failed: company mirror has no Flask/pytest) → chose "avoid external packages". | Switched to standard library: `unittest` instead of pytest; web UI will use `http.server` instead of Flask. |
| 5 | 2026-11-03 | Module A | "The topic test fails: 'SQL' and 'sql' appear as two topics, but filtering treats them as one. Make topics case-insensitive everywhere." | Added `_topic_labels()` helper used by `topics()` and `stats()`; 17/17 tests pass. |
| 6 | 2026-11-03 | Module B | "Compare lowest-first, weighted random and spaced repetition for choosing the next card." | Chose weighted random (`6 − confidence`) as best balance for a small project. |
| 7 | 2026-11-03 | Module B | "Implement weighted selection, never repeat the last card, allow a seeded RNG for tests." | `rotation.py` + `CardService.next_card()` with topic filter; confidence clamped to 1–5. |
| 8 | 2026-11-03 | Module B | "Write a 1,000-pick simulation test for the weighting." | Result 542/343/115 vs expected 556/333/111; 28/28 tests pass. |
| 9 | 2026-11-03 | Module C | "Create JsonStorage with load()/save(); create the file if missing; keep non-English text readable." | `storage.py` with versioned format `{"version": 1, "cards": [...]}`. |
| 10 | 2026-11-03 | Module C | "Recover from corrupted data without crashing; save atomically." | 3-level recovery (invalid JSON / wrong structure / invalid cards) + backup + warning; temp file + `os.replace`. |
| 11 | 2026-11-03 | Module C | "Two recoveries in the same second overwrite the backup. Make backup names unique and add a test." | Numbered suffix added; 37/37 tests pass. |
| 12 | 2026-11-03 | Module D | "Build a menu-driven CLI on top of CardService (practice with topic filter, add, list, edit, delete, progress bars, sample questions); make input/output injectable for tests." | `cli.py`, `sample_cards.py` (12 questions), `__main__.py`, 19 tests. |
| 13 | 2026-11-03 | Module D | "The test run hangs. Why does mock.patch('builtins.input') not work?" | Default argument `input_fn=input` bound the real `input` at import; now resolved at call time. Tests run with `timeout` and `< /dev/null`. |
| 14 | 2026-11-03 | Module D | "The menu wraps in a normal terminal. Split it into two lines." | Two aligned menu rows; 56/56 tests pass. |
| 15 | 2026-11-03 | Module F | "Create a web UI using only the standard library (Practice, Cards, Progress) reusing CardService; keep page logic testable without a server." | `WebApp.handle()` → `Response`; `match`-based routing; thin `http.server` adapter; `main.py` with `cli`/`web` modes. |
| 16 | 2026-11-03 | Module F | "Hide the answer until 'Show answer' without JavaScript; colored 1–5 rating buttons; Post/Redirect/Get." | `<details>` element + 303 redirects; responsive CSS; "chance to come up next" bars on Progress. |
| 17 | 2026-11-03 | Module F | "Review the web layer for security problems and fix them." | HTML escaping, Origin/Host check (403), 127.0.0.1 default, 100 KB body limit; f-string fixed for Python 3.10; 73/73 tests pass. |

