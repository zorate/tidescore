Welcome to the TideScore codebase — these instructions help AI coding agents make productive, correct edits quickly.

High-level architecture (what to read first)
- Entry point: `app.py` — Flask app, route definitions, admin guard (`admin_required`), blueprint registration for `auth`.
- Auth & session: `auth.py` — signup/login flows, bcrypt password hashing, reset-token flow (uses `db` methods).
- Persistence: `models.py` — thin MongoDB wrapper (`Database` class) used as `db`. Important: it uses `pymongo`, stores objects as dicts and returns `Application`-style objects via helper constructors.
- Core business logic: `scoring_algorithm.py` — the TideScore calculation and suggestions. This is where scoring rules live; avoid changing semantics without adding tests and migration notes.

Why things are structured this way
- The app is a single-process Flask server serving HTML templates (Jinja2) and simple JSON endpoints. The database layer is intentionally simple (MongoDB via `pymongo`) to keep data modeling flexible.
- `scoring_algorithm.py` is decoupled from web handlers — routes call `calculate_tidescore(...)` with verified/aggregated data. Keep domain logic here.

Key files to consult when editing
- `app.py` — routing, file uploads (`uploads/`), admin verification flow, `calculate_score` and `submit_application` endpoints.
- `models.py` — all DB operations: user management, application CRUD, verification history, and utility index creation. Any data-shape changes must update these methods.
- `scoring_algorithm.py` — scoring rules, breakdown keys (e.g. "Airtime & Data", "Bill Payments"). Tests should assert shape of returned dict: {scaled_score, risk_level, breakdown, suggestions}.
- `config.py` — environment-driven config. `Config.validate_config()` raises if required vars missing; tests and local dev must set `MONGODB_URI` and `SECRET_KEY` or expect an exception.
- `requirements.txt` — pinned packages used by runtime.

Developer workflows & commands
- Run locally (development): set environment variables and run `app.py` directly. Example (PowerShell):
```powershell
$env:FLASK_ENV = 'development'; $env:MONGODB_URI = '<your_mongodb_uri>'; python .\app.py
```
- DB connectivity: `models.py` prints connection progress. When debugging connection failures, use the included `verify_connection.py` snippet pattern to test the same URI and network.
- Static & uploads: static files live in `static/`; user-uploaded files are written to `uploads/` relative to repo root. When editing upload logic in `app.py`, preserve allowed extensions check.

Project-specific conventions
- Sessions: session keys use `session['user']` dict with keys `id`, `email`, `name`, `is_admin`. Keep this shape when writing login/dev-login logic.
- IDs: users are created with string IDs (e.g. `user-<hex>` or `dev-user-<hex>`). DB methods expect string `_id` fields and `ObjectId` conversions for applications; do not change user id type without updating all DB callers.
- Files stored in `uploads/` use unique filenames: `<user_id>_<file_type>_<uuid>.<ext>` — maintain this pattern for readability and to avoid collisions.
- Flash UI: templates rely on flashed messages categories like `error`, `success`, `info`. Use those categories consistently.

Testing & quality gates
- There are no automated tests in the repo. Before changing scoring logic, add small unit tests that import `calculate_tidescore` and assert the returned keys and expected bucketed score behavior.
- Basic checks to run locally:
  - Ensure environment vars: `MONGODB_URI`, `SECRET_KEY` are set.
  - Run `python app.py` and visit `/dev_login` when `FLASK_ENV=development` to create test sessions quickly.

Integration & external dependencies
- MongoDB Atlas: `MONGODB_URI` (seen in `config.py`). `models.py` expects the DB name in the URI; when missing it falls back to `tidescore`.
- Optional/unused: Auth0 and Supabase config keys are present but not wired up; avoid adding production integrations without updating `config.py` and validation.

Safe edit guidelines for AI agents
- Small change contract (inputs/outputs): edits to routing or scoring must preserve HTTP response shapes used by templates and AJAX endpoints. Example: `calculate_score` expects a JSON result with `scaled_score` and `breakdown`.
- Edge cases to check: missing `session['user']`, `db` connection is None (many DB methods guard this), absent files in `uploads/`, invalid file extensions.
- When touching `models.py`, prefer additive changes: add new DB fields in a backward-compatible way and migrate reads to handle missing keys (use `.get(...)`).

Examples from the codebase
- Use `session['user']['is_admin']` to gate admin routes (see `admin_required` in `app.py`).
- File upload allowed extensions: `['pdf', 'png', 'jpg', 'jpeg', 'doc', 'docx']` (see `submit_application` in `app.py`).
- Score result shape: `{'scaled_score': int, 'risk_level': str, 'breakdown': dict, 'suggestions': list}` (see `scoring_algorithm.py`).

What not to change without discussion
- Global data shapes (user id type, application dict structure in DB)
- Scoring semantics (unless you add unit tests and a changelog entry in a new commit)
- Config validation behavior in `Config.validate_config()` — CI/automation relies on this failing fast for missing env vars.

If you need more context
- Read `templates/` to see how handlers are consumed (form names, flash categories, expected routes).
- Look at `simple_test.py` for any quick scripts (it can show common usage patterns).

Done — please review these instructions and tell me if you want more examples, unit-test templates, or a short developer README to be added.
