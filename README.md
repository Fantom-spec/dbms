# Smart Hospital Management System

A Flask + SQLite hospital-management application for the BCSE302L Database Systems course project (Review III). It covers patient and visit workflows, appointments, an emergency triage queue, bed management, pharmacy, billing, 19 report queries, an audit log, and a transaction inspector that shows the SQL behind every action.

## Quick start

Requires Python 3.10+.

```bash
python -m venv .venv
# Windows PowerShell:  .venv\Scripts\Activate.ps1
# Linux/macOS:         source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # Windows: copy .env.example .env
```

Edit `.env` and set a unique `SECRET_KEY`. Then:
python3 -c "import secrets; print(secrets.token_hex(32))"

```bash
python app.py
```

Open <http://127.0.0.1:5000> and log in.

### First run options

| Goal | Command |
|---|---|
| Ship-ready DB already included (`hospital.db`) | just run `python app.py` |
| Create a fresh empty-with-sample DB | `python -m db.init_db --db ./fresh.db` then set `HOSPITAL_DB_PATH=./fresh.db` |
| Create the first administrator | `python scripts/bootstrap_admin.py` |
| Add showcase patients, visits, beds, medicines and staff logins | `python scripts/seed_showcase_data.py` |

`seed_showcase_data.py` makes a timestamped `.bak` backup first and is safe to re-run. It prints the staff credentials it creates (receptionist, triage nurse, doctor, billing). Those are local sample passwords only.

## Project structure

```text
app.py                  Flask app factory and entry point
config.py               Settings read from environment / .env
views.py                HTML page routes
api.py                  JSON API and role-based authorization
auth.py                 Password hashing, accounts, sessions
services.py             Business logic (admit, discharge, billing, ...)
queries.py              The 19 report queries
inspector.py            SQL / row-change transaction inspector
validation.py, errors.py  Input validation and DB-error mapping
api_stub.py, fixtures/  Fixture-backed stub API (FLASK_API_MODE=stub)
db/                     schema.sql, seed.sql, triggers.sql, connection, init_db,
                        reset_demo
scripts/                bootstrap_admin.py, seed_showcase_data.py
templates/              Jinja page templates
static/                 css/, js/ (api.js, app.js, pages/*.js), vendor/
tests/                  pytest suite and smoke test
docs/                   API_CONTRACT.md, DEMO.md
hospital.db             SQLite database with showcase data
```

## Pages and roles

Dashboard, Patients, Appointments, Emergency, Beds, Pharmacy, Billing, Reports, Audit Log and System Admin. Access is enforced server-side by role: Admin, Receptionist, Triage Nurse, Doctor, Billing. Each page script in `static/js/pages/` loads its own data when the page opens.

## Testing

```bash
python -m compileall -q .
pytest -q
bash tests/smoke_test.sh      # needs a running server
```

## Troubleshooting

- **A page shows no data:** hard-refresh with Ctrl+Shift+R (cached JavaScript), then check the browser console.
- **`ModuleNotFoundError: bcrypt`:** run `pip install -r requirements.txt` inside the virtual environment.
- **Locked out after failed logins:** wait 15 minutes, or restart the server.

## Security notes

- Keep secrets in `.env` only; it is git-ignored.
- Use `HOSPITAL_COOKIE_SECURE=1` behind HTTPS.
- All patient data in the bundled database is fictional.

