# Interview Prep Question Rotator
AI-Assisted Development – Exam Project · Author: [Your Name] · November 2026

## Overview
This document describes a small software project built with AI assistance (GitHub Copilot). The project is called **Interview Prep Question Rotator**. It stores interview Q&A cards and rotates questions using an adaptive confidence-based order.

## Choose Your Own Project Topic
### Selected Topic
**Interview Prep Question Rotator**: a small Python mini-app for adaptive interview practice, with a lightweight web interface (built on Python's standard-library `http.server`) and a command-line (CLI) interface that share the same core logic.

### The Idea
Preparing for technical or behavioral interviews often means going over the same list of questions again and again. Classic flashcards show questions in a fixed or random order, so the user spends as much time on questions they already know as on the ones they struggle with. This wastes time and makes it easy to skip weak areas.

The Interview Prep Question Rotator solves this with **adaptive practice order**. The user stores interview questions as Q&A cards. After answering a card, the user rates their confidence from 1 (not confident) to 5 (very confident). The app uses these ratings to choose the next question. Cards with lower confidence get a higher selection weight, so they come up more often. Cards with higher confidence still come up, just less often, so the user keeps reviewing them without overpracticing them.

This creates a simple learning loop: **practice → self-evaluate → adapt**. Over time, the user's weakest topics improve first, and the progress statistics show how preparation is going.

**Target users:** students, junior developers, and anyone preparing for job interviews.

**Example usage scenario:**
1. The user opens the web app in a browser and adds 15 questions about Java, SQL, and soft skills.
2. The user starts a practice session. The app shows a question, and the user thinks of an answer and then clicks "Show answer".
3. The user rates their confidence by clicking a button from 1 to 5. The app saves the rating and adjusts which questions come next.
4. After the session, the user opens the Progress page to see the average confidence, the weak cards left, and a confidence bar for each topic.

### System Requirements

**Functional requirements**
- **FR1 – Create cards:** The user can add a card with a question, an answer, an optional topic/tag, and an initial confidence score (default: 1).
- **FR2 – Manage cards:** The user can list all cards, filter them by topic, edit a card, and delete a card.
- **FR3 – Adaptive practice:** The system picks the next question with weighted random selection. Lower confidence means a higher probability of being picked, and the same card is not shown twice in a row.
- **FR4 – Answer reveal & rating:** During practice, the answer stays hidden until the user asks to see it. After that, the user updates the confidence score (1–5).
- **FR5 – Progress statistics:** The system shows the total number of cards, the average confidence, the number of low-confidence cards (score ≤ 2), and the total number of practice attempts.
- **FR6 – Persistence:** All cards and statistics are saved to a local JSON file and loaded automatically on startup.
- **FR7 – Web interface:** A browser UI provides three pages: **Cards** (add, edit, delete, filter), **Practice** (question → show answer → rate 1–5), and **Progress** (statistics and confidence bars per topic). The CLI offers the same core features from a terminal.

**Non-functional requirements**
- **NFR1 – Simplicity:** The app runs locally with Python 3 only. It uses no third-party packages, external services or databases.
- **NFR2 – Validation:** Empty questions or answers and confidence values outside 1–5 are rejected with clear error messages.
- **NFR3 – Reliability:** If the data file is missing, it is created automatically. If the file is corrupted, the app shows a warning and does not crash.
- **NFR4 – Performance:** Selecting the next question and loading data respond instantly for up to several hundred cards.
- **NFR5 – Maintainability:** The core logic (cards, rotation, storage, validation) is independent of the interface, so the web UI and CLI reuse it without duplicated code. The core logic and web routes are covered by automated tests.
- **NFR6 – Usability:** The web pages are clean and work on desktop and mobile screens. The CLI commands and prompts are short and clear.

**Out of scope (for this version):** user accounts and authentication, cloud sync and online deployment, and AI-generated answers.

## System Architecture - Modules
The module breakdown was produced with GitHub Copilot Chat. I described the idea, the requirements (FR1–FR7) and the planned technology (Python, JSON storage, a web interface), and asked Copilot to split the system into technological modules with clear responsibilities and dependencies. I reviewed the proposal and kept a **layered design**: a shared core (Modules A–C, E) with no knowledge of any user interface, and two thin interfaces on top of it (Module D – CLI, Module F – Web UI). This means the adaptive logic is written and tested once and reused by both interfaces. Because of this layering, the later switch from Flask and pytest to the Python standard library (see *Challenges*) only affected the outer layers.

**Prompt used:** *"Break the Interview Prep Question Rotator down into technological modules. For each module give its responsibility, main functions/classes, inputs/outputs and dependencies. Suggest a folder structure that keeps the core logic independent from the CLI and the web UI."*

**Dependency overview:**
```
  Web UI (F)        CLI (D)
       \            /
     Card Management (A) ──► Validation (E)
       /            \
Rotation Engine (B)  Persistence (C) ──► data/cards.json
```

**Folder structure (proposed by Copilot):**
```
interview_rotator/
  core/
    models.py        # Card data model (Module A)
    cards.py         # CardService: CRUD + stats (Module A)
    rotation.py      # weighted next-card selection (Module B)
    storage.py       # JSON load/save (Module C)
    validation.py    # input rules (Module E)
  cli.py             # terminal interface (Module D)
  main.py            # entry point: cli or web mode
  sample_cards.py    # 12 sample interview questions
  web/
    server.py        # http.server routes (Module F)
    templates/       # HTML pages
    static/          # CSS
tests/               # unittest tests (Module E)
```

### Module A: Card Management
- **Responsibility:** the `Card` data model (id, question, answer, topic, confidence, times practiced, last practiced) and a `CardService` with create, list/filter, edit, delete, rate-after-practice and progress statistics (FR1, FR2, FR5).
- **Inputs/Outputs:** card data from the UI → validated, stored `Card` objects and statistics.
- **Depends on:** Validation (E), Persistence (C).
- **How AI assisted:** proposed the data model fields and service method signatures, and suggested adding `times_practiced` and `last_practiced` fields, which the statistics need.

### Module B: Adaptive Rotation Engine
- **Responsibility:** choose the next card to practice (FR3). Each card gets the weight `6 − confidence` (confidence 1 → weight 5, confidence 5 → weight 1), and a card is picked with weighted random selection. The previously shown card is excluded unless it is the only card.
- **Inputs/Outputs:** list of cards + id of the last shown card → next `Card` (or none if the list is empty).
- **Depends on:** nothing. It is a pure function, which makes it easy to test.
- **How AI assisted:** compared three strategies: always lowest confidence first (predictable, but high-confidence cards never appear), weighted random, and spaced repetition (too complex for this scope). Weighted random was chosen as the best balance.

### Module C: Data Persistence Layer
- **Responsibility:** save and load cards to and from `data/cards.json` (FR6). Creates the file if it is missing, handles a corrupted file safely (NFR3), and writes to a temporary file first so a crash cannot leave a half-written data file.
- **Inputs/Outputs:** list of `Card` objects ↔ JSON file.
- **Depends on:** Card model (A).
- **How AI assisted:** generated the serialization code and suggested the write-to-temp-then-rename approach and backing up the corrupted file before resetting it.

### Module D: CLI Interface
- **Responsibility:** a terminal menu (add, list, practice, stats, exit) that calls `CardService` and the rotation engine. It is a thin layer with no business logic.
- **Inputs/Outputs:** keyboard input → printed questions, answers and statistics.
- **Depends on:** A, B.
- **How AI assisted:** suggested the menu structure and clear, consistent messages for success and errors.

### Module E: Validation and Testing
- **Responsibility:** input rules (non-empty question and answer, confidence must be a whole number 1–5, topic length limit) used by every interface (NFR2), plus the automated `unittest` suite for all modules (NFR5).
- **Inputs/Outputs:** raw user input → cleaned values or a clear `ValidationError` message. Tests → pass/fail report.
- **Depends on:** nothing (validation). The tests depend on all modules.
- **How AI assisted:** listed edge cases (whitespace-only text, confidence of `"3"`, `0`, `6`, `3.5`) and suggested a statistical test for the rotation engine.

### Module F: Web UI
- **Responsibility:** three pages: **Cards** (add/edit/delete/filter), **Practice** (question → "Show answer" → rate 1–5) and **Progress** (statistics + confidence bar per topic) (FR7). It uses the same `CardService` and rotation engine as the CLI.
- **Inputs/Outputs:** HTTP requests and form posts → HTML pages.
- **Depends on:** A, B.
- **How AI assisted:** proposed the routes (`/cards`, `/practice`, `/practice/<id>/rate`, `/progress`), and the Post/Redirect/Get pattern so that refreshing the page doesn't submit a rating twice.

## Development Process per Module

### Module A: Card Management
#### Approach & reasoning
I started with card management because every other module depends on the `Card` model. The goal was a stable data model and one `CardService` class that both interfaces call. The service receives its storage through a small `CardStorage` interface (`load()` / `save()`) instead of creating it itself. This made it possible to build and test Module A **before** the JSON layer existed, using an in-memory fake storage. Validation rules were placed in a separate `validation.py` (part of Module E) so that the CLI and the web UI share exactly the same rules.

#### Step-by-step workflow
1. Asked Copilot to generate the `Card` dataclass and a `CardService` with create, list/filter, edit, delete, practice-rating and statistics methods.
2. Asked for validation helpers and an in-memory fake storage for testing, then reviewed the generated code. I accepted the "validate all fields first, then apply" approach in `update_card`, so an invalid edit never leaves a card half-changed.
3. Ran the tests. One failed: filtering treated "SQL" and "sql" as the same topic, but the topic list and statistics showed them as two different topics. I asked Copilot to fix this, and it added one shared case-insensitive topic-label helper that keeps the first spelling.
4. Result: `models.py`, `cards.py`, `validation.py`, and 17 passing unit tests.

#### Testing strategy
- Automated `unittest` tests for every operation (FR1, FR2, FR4, FR5), using the in-memory storage to check that each change is saved.
- Edge cases: empty and whitespace-only text, confidence `0`, `6`, `3.5`, `True`, `"abc"`, numeric strings such as `" 4 "` (sent by web forms), unknown card ids, and an invalid edit.
- Statistics checked against hand-calculated values, including cards without a topic ("General").

#### AI tool choice
- Tool used: GitHub Copilot (Chat in IntelliJ IDEA, agent mode).
- Why: it could generate the model, service, validation and tests together, run the tests in the terminal, and fix failures in the same conversation.

#### Key prompts or interactions (2-3 examples)
1. *"Set up the project skeleton and build Module A: a Card dataclass and a CardService with create, list/filter by topic, edit, delete, record practice and progress statistics. Inject the storage so it can be tested without files."*
2. *"Add validation: question and answer cannot be empty, confidence must be a whole number 1–5 and also accept numeric strings from forms. An invalid edit must not change the card."*
3. *"The topic test fails: 'SQL' and 'sql' appear as two topics, but filtering treats them as one. Make topics case-insensitive everywhere."*

### Module B: Adaptive Rotation Engine
#### Approach & reasoning
This module is the core idea of the project. Copilot compared three strategies. **Lowest confidence first** is predictable, but well-known cards would never come up again. **Spaced repetition** (as in Anki) is powerful but too complex for this scope. **Weighted random selection** was chosen: each card gets the weight `6 − confidence`, so a card rated 1 is five times as likely to be picked as a card rated 5, while strong cards still appear sometimes. The card just shown is excluded so the user never sees the same question twice in a row. The engine is a set of pure functions (no files, no UI), and a random generator can be passed in, so tests can use a fixed seed and get repeatable results.

#### Step-by-step workflow
1. Asked Copilot to implement `card_weight()`, `pick_next_card()` and `selection_probabilities()` in `rotation.py`, using Python's `random.choices` with weights.
2. Reviewed the code and kept two additions from Copilot: confidence values are clamped to 1–5, so damaged data can never produce a zero or negative weight, and the "no repeat" rule is skipped when only one card exists.
3. Added `CardService.next_card()` with an optional topic filter, so the CLI and web UI can say "practice only SQL" with one call.
4. Result: `rotation.py` and 11 new tests. 28/28 tests pass in total.

#### Testing strategy
- **Exact checks:** weights 5-4-3-2-1 and probabilities 5/9, 3/9 and 1/9 for cards rated 1, 3 and 5.
- **Simulation test:** 1,000 seeded picks gave **542 / 343 / 115** for cards rated 1 / 3 / 5, against an expected ~556 / 333 / 111. This confirms that weak cards appear most often and strong cards still appear.
- **Behavior checks:** 500 consecutive picks with no immediate repeat. Equal confidence gives roughly equal picks. Raising a card's rating from 1 to 5 lowers its chance from 50% to 17%.
- **Edge cases:** an empty list returns no card, and a single card is still returned.

#### AI tool choice
- Tool used: GitHub Copilot (Chat in IntelliJ IDEA, agent mode).
- Why: it was useful for comparing algorithm options before coding and for suggesting a statistical test, which is hard to design for random behavior without guidance.

#### Key prompts or interactions (2-3 examples)
1. *"Compare ways to choose the next flashcard based on a 1–5 confidence score: lowest-first, weighted random and spaced repetition. Which fits a small project best?"*
2. *"Implement weighted random selection with weight 6 − confidence, never repeat the last shown card, and allow a seeded random generator for testing."*
3. *"Write a simulation test with 1,000 picks that checks low-confidence cards are chosen more often, but high-confidence cards still appear."*

### Module C: Data Persistence Layer
#### Approach & reasoning
A single JSON file (`data/cards.json`) is enough for a personal app with a few hundred cards. It needs no database server, is readable by humans, and is easy to back up. The file stores a format version (`{"version": 1, "cards": [...]}`) so the format can change later. The main risk is **losing the user's progress**, so the design focuses on safety. A missing file is created automatically. A damaged file is backed up, and the app keeps the valid cards and shows a warning instead of crashing (NFR3). Saving writes to a temporary file and then replaces the real file in one step, so a crash or a full disk can never leave a half-written file. `JsonStorage` implements the same `load()`/`save()` interface as the test fake from Module A, so `CardService` needed no changes.

#### Step-by-step workflow
1. Asked Copilot for a `JsonStorage` class with `load()`/`save()` that handles a missing file and stores non-English text readably (`ensure_ascii=False`).
2. Asked for recovery from corrupted data. Copilot suggested three levels: invalid JSON, wrong structure, and individual invalid cards. Invalid cards are skipped, and the rest of the user's data is kept.
3. Asked for atomic saving (temporary file + `os.replace`) with cleanup of the temporary file on failure.
4. While reviewing, I noticed that two recoveries within the same second would give the backup the same name, so the second would overwrite the first and lose the original data. Copilot fixed this with a numbered suffix and added a test.
5. Result: `storage.py` and 9 new tests. 37/37 tests pass in total.

#### Testing strategy
- **Round trip:** save → load keeps every field, including Bulgarian (Cyrillic) text. A `CardService` "restart" keeps confidence scores and practice counts (FR6).
- **Recovery:** invalid JSON, wrong structure (`[1,2,3]`, `{"cards": "oops"}`), and a file with 1 valid + 4 invalid cards (only the valid card is loaded, and a backup and warning are created).
- **Failure simulation:** `unittest.mock` makes `json.dump` raise "disk full" during saving. The old file stays unchanged and no temporary files are left.
- All tests use a temporary folder, so they never touch real data.

#### AI tool choice
- Tool used: GitHub Copilot (Chat in IntelliJ IDEA, agent mode).
- Why: file handling has many failure cases that are easy to forget. Copilot listed them and generated tests for each, including the mock-based "disk full" simulation.

#### Key prompts or interactions (2-3 examples)
1. *"Create a JsonStorage class with load() and save() for the cards. Create the file if it is missing and keep non-English text readable in the file."*
2. *"If the JSON file is corrupted, back it up, keep any valid cards, show a warning and don't crash. Save atomically so a crash can't leave a half-written file."*
3. *"Two recoveries in the same second create the same backup name. Make backup names unique and add a test."*

### Module D: CLI Interface
#### Approach & reasoning
The CLI is the first part a user can actually run (`python3 -m interview_rotator`). It is a **thin layer**: it only asks for input, calls `CardService`, and prints results. All rules, such as validation and which card comes next, stay in the core modules. A numbered menu was chosen instead of typed commands because it is easier for new users and gives clean screenshots. To make the CLI testable, the `Cli` class receives its input and output functions as parameters, so tests can run a full scripted session and check the printed text. A built-in set of 12 sample interview questions (Python, SQL, Web, Behavioral) lets the app be tried right away.

#### Step-by-step workflow
1. Asked Copilot for a menu-driven `Cli` class: practice, add, list, edit, delete, progress, load samples, exit. The practice flow is question → Enter → answer → rating 1–5, with an optional topic filter and a session summary.
2. Asked for a progress screen with text bars (`█████░░░`) per topic and a "Focus next on" list of the three weakest cards.
3. The first test run **hung**. Copilot found the cause: `input_fn=input` as a default argument captures the real `input` when the module loads, so the end-to-end test's patched `input` was ignored and the program waited for the keyboard. The fix looks up `input`/`print` when called. Tests are now run with a timeout and no keyboard input, so a hang fails fast instead of blocking.
4. Ran the real app with piped input and noticed that the menu line (about 130 characters) wrapped in a normal terminal, so it was split into two lines.
5. Result: `cli.py`, `sample_cards.py`, `__main__.py` and 19 new tests. 56/56 tests pass in total.

#### Testing strategy
- **Scripted sessions:** every menu action with valid and invalid input, such as an empty question, rating `abc`, rating `8`, an unknown card ID, and cancelling a delete.
- **Practice behavior:** the rating is saved, the topic filter shows only that topic, and 21 consecutive questions never repeat the same card.
- **Exiting:** `0`, `q`, and Ctrl+D (end of input) all exit cleanly with "Your progress is saved."
- **End-to-end:** `main()` with a real temporary JSON file. Samples loaded in the first run are still there in the second run.
- **Manual check:** a real run with piped input to review the screen layout.

#### AI tool choice
- Tool used: GitHub Copilot (Chat in IntelliJ IDEA, agent mode).
- Why: it generated the many small input/output paths quickly. When the tests hung, it diagnosed the default-argument problem, a subtle Python behavior that is hard to spot without experience.

#### Key prompts or interactions (2-3 examples)
1. *"Build a menu-driven CLI on top of CardService: practice with topic filter (question → Enter → answer → rate 1–5), add, list, edit, delete, progress with text bars, load sample questions. Make input/output injectable for tests."*
2. *"The test run hangs. Why does mock.patch('builtins.input') not work in the end-to-end test?"*
3. *"The menu wraps in a normal terminal window. Split it into two aligned lines."*

### Module E: Validation and Testing
#### Approach & reasoning
All input rules are in one module, `validation.py`, and are applied inside `CardService`. Because of this, the CLI, the web UI and even data loaded from the JSON file go through exactly the same checks (NFR2). Testing was not left for the end: each module was built together with its tests, and the **full suite was run after every change**, so a new module could not silently break an old one. Every test is independent of the outside world. An in-memory fake replaces the JSON file, a seeded random generator makes the rotation repeatable, temporary folders protect real data, `unittest.mock` simulates failures such as a full disk, and the CLI and web UI receive scripted input instead of a keyboard or browser.

#### Step-by-step workflow
1. Asked Copilot for validation rules and a list of edge cases for every field. One surprising case it found: in Python, `True` is an `int` equal to `1`, so it would pass a naive range check. It is now rejected explicitly.
2. Asked for test helpers that make tests independent of files, keyboard input and randomness (the in-memory storage, a seeded RNG, injectable input/output).
3. After each module, ran the full suite and asked Copilot to explain any failure **before** fixing it. This caught the topic-casing bug (Module A) and the hanging CLI test (Module D).
4. Result: **73 tests in 5 files, all passing in about 0.6 seconds**: cards 17, rotation 11, storage 9, CLI 19 and web 17.

#### Testing strategy
- **Boundary values:** confidence `0`, `1`, `5`, `6`, plus `3.5`, `"abc"`, `" 4 "`, `True` and `None`. Text that is empty, whitespace only, or too long.
- **Statistical test** for random behavior (1,000 seeded picks) instead of only testing single picks.
- **Failure paths:** corrupted files, a simulated full disk, unknown card ids, cross-site form posts, and HTML/JavaScript inside user text.
- **Levels:** unit tests (core) → scripted sessions (CLI) → page tests (`WebApp`) → a real HTTP server test.
- Tests run with `timeout 90` and no keyboard input, so a hanging test fails instead of blocking.

#### AI tool choice
- Tool used: GitHub Copilot (Chat in IntelliJ IDEA, agent mode).
- Why: Copilot was strongest at listing edge cases I would not have thought of, and at writing the repetitive test code. Agent mode could also run the tests itself and react to the results.

#### Key prompts or interactions (2-3 examples)
1. *"List the edge cases for validating a 1–5 confidence score that can come from a terminal, an HTML form or a JSON file."*
2. *"Make the tests independent of real files, keyboard input and randomness."*
3. *"Run the full test suite and explain the failure before changing any code."*

### Module F: Web UI
#### Approach & reasoning
Flask could not be installed (see *Challenges*), so the web UI uses only the standard library: `http.server` for HTTP, `string.Template` for the page layout, and `html.escape` for safe output. To keep it testable, all page logic is in a `WebApp` class whose `handle(method, path, form)` method returns a `Response` object. Most tests call it directly, with no network. A thin `http.server` handler connects it to real browser requests. The UI has three pages: **Practice**, **Cards** and **Progress**. "Show answer" uses the HTML `<details>` element, so the answer stays hidden until clicked **without any JavaScript**, and the five colored rating buttons appear only after the answer is revealed. Every form uses **Post/Redirect/Get** (HTTP 303), so refreshing the page never submits a rating twice. The **Progress** page also shows each card's *chance to come up next*, which makes the adaptive algorithm visible.

#### Step-by-step workflow
1. Asked Copilot to design the routes (`/practice`, `/practice/<id>`, `/practice/<id>/rate`, `/cards`, `/cards/<id>/edit`, `/cards/<id>/delete`, `/samples`, `/progress`) and to write `WebApp` using Python's `match` statement for routing.
2. Asked for a clean, responsive stylesheet: a card-style layout, topic "pills", confidence colors from red (1) to green (5), and CSS progress bars.
3. Asked Copilot to review the security of the web layer. It added HTML escaping of all user text, a check that blocks form posts from other websites (`Origin` must match `Host`), listening only on `127.0.0.1` by default, and a request size limit.
4. Moved `main()` into its own `main.py`, so `python3 -m interview_rotator web` starts the browser UI and `python3 -m interview_rotator` still starts the CLI.
5. Fixed a compatibility issue: a backslash inside an f-string expression only works on Python 3.12+, but the project supports 3.10+.
6. Result: `web/server.py`, `templates/base.html`, `static/style.css` and 17 new tests. **73/73 tests pass in 0.6 s.**

#### Testing strategy
- **Page tests via `WebApp.handle()`:** the empty state, loading samples, practice flow (question → hidden answer → rating → a different next card), topic filter kept in the URL, add/edit/delete, invalid input (HTTP 400 with the error and the user's text kept), and 404/405 pages.
- **Security tests:** `<script>` in a question is shown as text, not executed, and a cross-site POST is rejected with 403.
- **Real HTTP test:** the server is started on a random free port in a background thread, and `urllib` loads a page, posts a form (with non-ASCII text, "Über-Frage?"), follows the 303 redirect and downloads the CSS.
- **Manual test:** ran the server and called every page with `curl`, then checked the layout in the browser.

#### AI tool choice
- Tool used: GitHub Copilot (Chat in IntelliJ IDEA, agent mode).
- Why: without a framework, a lot of HTTP plumbing must be written by hand (routing, form parsing, redirects, escaping). Copilot generated it quickly and also pointed out security issues I would not have thought of, such as cross-site form posts.

#### Key prompts or interactions (2-3 examples)
1. *"Create a web UI using only the Python standard library: pages Practice, Cards and Progress that reuse CardService. Keep the page logic testable without starting a server."*
2. *"Make the answer hidden until 'Show answer' is clicked without JavaScript, then show five colored rating buttons. Use Post/Redirect/Get so refreshing doesn't rate twice."*
3. *"Review the web layer for security problems and fix them: escaping, cross-site form posts, request size, listening address."*

## Challenges & Tool Comparison
### The biggest challenges you encountered
- **Blocked package installation:** on my work laptop, pip is configured to use a company package mirror, and the mirror had no Flask or pytest. Instead of bypassing the company configuration, I asked Copilot to switch the project to the Python standard library only: `unittest` instead of pytest, and `http.server` instead of Flask. Thanks to the layered design, only the tests and the planned web layer were affected, not the core logic. A side benefit is that the app now runs anywhere Python 3 is installed, with no setup.
- **A test run that hung:** the CLI tests froze instead of failing, because a default argument (`input_fn=input`) bypassed the test's fake keyboard input. Copilot found the cause from the symptoms. Since then, tests always run with a timeout and no keyboard input, so a hang can't block the terminal again.
- **Bugs that only tests or review revealed:** case-sensitive topics ("SQL" vs "sql"), backup files overwriting each other, and a menu too wide for a normal terminal. AI-generated code looked correct at first sight in all three cases. The lesson: generated code needs tests and a real run before it can be trusted.

### Which tool helped you the most and why
I used **GitHub Copilot Chat in IntelliJ IDEA (agent mode)** for the whole project. It helped most in three ways:
- **It worked with the real project.** It read the existing modules before writing new ones, so new code fit the existing interfaces. For example, `JsonStorage` matched the storage interface from Module A without any changes to `CardService`.
- **It closed the feedback loop.** Agent mode ran the tests in the terminal and reacted to the results, so the work became a *generate → test → fix* cycle instead of just generating code.
- **It explained, not only coded.** It compared algorithms (Module B), diagnosed the hanging test (Module D) and reviewed the web layer for security problems (Module F).

Its weak points: some generated code looked correct but had subtle bugs (three were found by tests or review), long multi-line terminal commands were sometimes garbled, and it needed clear constraints (for example, "standard library only") to stay on track. The biggest value was not faster typing but a faster feedback loop and a second pair of eyes.

### What you would improve if you continued working on the project
- **Smarter rotation:** add a time factor, so cards that have not been practiced for a long time slowly gain weight (a lightweight step towards spaced repetition).
- **Practice history:** store every attempt, not only counters, and show a chart of confidence over time.
- **Import/export:** load and share question sets as CSV or Markdown.
- **Better web UX:** keyboard shortcuts (Space = show answer, 1–5 = rate) and dark mode.
- **Online version:** with a normal package setup, move the web layer to Flask and add user accounts, so the app could be deployed for several users.

## Working System Evidence
The screenshots were taken from the running application (`python3 -m interview_rotator web`) with the 12 sample questions loaded.

![Figure 1 – Practice page: question, revealed answer and the five colored rating buttons](screenshots/practice.png)

![Figure 2 – Progress page: summary tiles, confidence by topic and each card's chance to come up next](screenshots/progress.png)

**Terminal version:** real output of the CLI progress screen after a short practice session (two Python questions rated 2 and 4):
```
== Progress ==
Total cards:          12
Average confidence:   █████░░░░░░░░░░░░░░░ 1.33/5
Weak cards (1-2):     11
Practice attempts:    2

Confidence by topic:
  Behavioral     ████░░░░░░░░░░░░░░░░ 1.00
  Python         █████████░░░░░░░░░░░ 2.33
  SQL            ████░░░░░░░░░░░░░░░░ 1.00
  Web            ████░░░░░░░░░░░░░░░░ 1.00
```

**Automated tests:** `python3 -m unittest discover`
```
Ran 73 tests in 0.565s

OK
```

## Repository
- GitHub repository: [add link after publishing]
- Requirements: Python 3.10+ only, nothing to install.
- Start the web UI: `python3 -m interview_rotator web`, then open http://127.0.0.1:8000
- Start the terminal version: `python3 -m interview_rotator`
- Run the tests: `python3 -m unittest discover -v`

## Submission Format
- Final output: Google Drive Document (shared: anyone with the link can view)
- Total size: typically 3-6 pages

## Final Checklist
- [ ] Project idea + requirements section is complete (up to 1 page).
- [ ] Architecture is split into clear technological modules.
- [ ] Each module includes: approach, workflow, testing, tool choice, key prompts.
- [ ] Challenges and tool comparison are complete.
- [ ] At least two screenshots are inserted and explained.
- [ ] Repository link is included.
- [ ] Final document is around 3-6 pages (slightly over is acceptable) and shared correctly.

