# Person 1: Backend (database, services, API)

You own everything that touches data: SQLite schema, triggers, functions, the service layer ("procedures"), the 19 reports, schema introspection, the demo runners and the JSON API. Person 2 builds the web UI on top of your API and never touches the database.

Read `ARCHITECTURE.md` first. It is the source of truth; this file is your work order. Oracle source of truth for schema, data, queries and rules: `docs/reference/DBMS_Review2_Hospital_Management_System.sql`.

---

## 1. What you deliver

| # | Deliverable | File(s) |
|---|---|---|
| 1 | App skeleton and per-request DB + role handling | `app.py`, `config.py`, `requirements.txt` |
| 2 | SQLite schema, seed, triggers, rebuild script | `db/schema.sql`, `db/seed.sql`, `db/triggers.sql`, `db/init_db.py` |
| 3 | Connection setup, 3 SQL functions, trace hook | `db/connection.py` |
| 4 | Service layer (the "procedures") | `services.py`, `errors.py` |
| 5 | Transaction Inspector | `inspector.py` |
| 6 | 19 report queries + cursor loops | `queries.py` |
| 7 | Schema introspection + violation sandbox + trigger demos | `introspect.py`, `metadata.py` |
| 8 | Guided demo T1-T6 with self-checks | `demo.py` |
| 9 | JSON API (real) and stub API with fixtures | `api.py`, `api_stub.py`, `fixtures/` |
| 10 | Living contract | `CONTRACT.md` |
| 11 | Tests | `tests/` |
| 12 | ER diagram and relational schema images | `static/img/er_diagram.png` (you draw, Person 2 displays) |
| 13 | Report sections 4, 5, 6, 8 | `docs/report/` |

**Do not edit** `templates/`, `static/js`, `static/css`, `views.py` (Person 2's). Exception: you put the ER image in `static/img/`.

---

## 2. Phases

### Phase 0: Day 0, together with Person 2 (30 min)
- Create the repo, branches `backend` and `frontend`, copy the Review II script to `docs/reference/`.
- You write `app.py` (app factory registering `api` blueprint and `views.views_bp`), `config.py`, `requirements.txt`, `CONTRACT.md` (copy sections 8-11 of the architecture).
- Person 2 writes `views.py` + placeholder templates so the app boots.

### Phase 1: Hour 1, stubs (do this before anything else)
- `api_stub.py` + `fixtures/`: every endpoint in ARCHITECTURE section 8.2 returns a realistic envelope from `fixtures/<METHOD>_<path>.json`. `FLASK_API_MODE=stub` switches it on.
- Fixtures must include realistic `inspector` objects on write endpoints and `ok:false` examples on a few (for example `POST_api_appointments_error.json` plus a way to trigger it, such as `?_fail=1`).
- **Acceptance:** Person 2 can load every page against stubs. Push and tell them.

### Phase 2: Database port (about 5 h)
Tasks:
1. `schema.sql`: 8 tables + `app_session`, all Review II constraints with the same names, the 2 partial unique indexes and 3 normal indexes. Follow the type rules in ARCHITECTURE 5.3.
2. `seed.sql`: Review II data exactly (12/10/12/12/20/22/11/12 rows). Convert `DATE '...'`/`TIMESTAMP '...'` literals to plain ISO strings.
3. `triggers.sql`: the 15 physical triggers (ARCHITECTURE 5.6).
4. `db/connection.py`: open connection with `isolation_level=None`, `row_factory=sqlite3.Row`, `PRAGMA foreign_keys=ON`, `PRAGMA busy_timeout=5000`; register `fn_days_stayed`, `fn_medicine_cost`, `fn_triage_label`.
5. `init_db.py`: delete DB file, run schema -> seed -> triggers, print row counts.

**Acceptance:** `python -m db.init_db` prints the golden counts; the 11 violation statements (ARCHITECTURE 10) each fail with the expected error; `tests/test_schema.py` and `tests/test_triggers.py` pass.

### Phase 3: Services (about 5 h)
Implement every function in ARCHITECTURE section 6 with `BEGIN IMMEDIATE`/`COMMIT`/`ROLLBACK`, plus `errors.py` mapping. See the behaviour notes in section 4 below.

**Acceptance:** `tests/test_services.py` passes: every happy path and every error code.

### Phase 4: Inspector + API (about 5 h)
- `inspector.py`: wrap each service call, collect SQL, triggers fired, before/after snapshots, viva block, elapsed time.
- `api.py`: all endpoints in ARCHITECTURE 8.2 as thin handlers returning the envelope. Handlers set `app_session.username` from the role at the start of each request.
- Push to `main` for **Sync 1** as soon as patients and appointments are real, then continue.

**Acceptance:** `tests/test_api.py` validates the envelope for every endpoint; with `FLASK_API_MODE=real` the stub fixtures and real responses have the same keys.

### Phase 5: Reports and schema (about 5 h)
- `queries.py`: 19 queries translated to SQLite with ids q01-q19, titles, concept tags, chart hints. Cursor loops for emergency queue and pending bills with `console_lines`.
- `introspect.py` + `metadata.py`: all `/api/schema/*` endpoints, the 11 violation tests (rolled back), 6 trigger demos (rolled back), read-only SQL console.
- ER diagram: draw the 8-entity diagram (draw.io or Graphviz), export `static/img/er_diagram.png`.

**Acceptance:** `tests/test_reports.py` matches every golden value in ARCHITECTURE 9; violation runs leave the DB unchanged (row counts identical before and after).

### Phase 6: Demo runners and polish (about 3 h)
- `demo.py`: T1.1 to T6.4 exactly as in ARCHITECTURE 11, each returning `checks[]`, role switching per step, prerequisite checks, state reset on `/api/reset`.
- `/api/reset` rebuilds the DB and clears demo state.

**Acceptance:** `tests/test_demo.py` runs the whole sequence on a fresh DB with all checks passing; audit rows 13-20 appear as in the plan; running reset then the sequence again gives the same result.

### Phase 7: Documentation and rehearsal
- Report sections 4, 5, 6 (with Oracle to SQLite table) and 8.
- Two full demo rehearsals with Person 2; fix contract mismatches immediately.

---

## 3. Contract obligations to Person 2

- Never change a URL, field name or step id without writing it in `CONTRACT.md` and telling Person 2 first.
- Always return the envelope, including for 400/500.
- Keep stub fixtures in sync with real responses (a test compares key sets).
- Respond to integration bugs the same day.

---

## 4. Implementation notes and gotchas

**Connections and transactions**
- PRAGMAs must be set per connection; `foreign_keys` cannot be changed inside a transaction.
- Use `isolation_level=None` and explicit `BEGIN IMMEDIATE`. Always `ROLLBACK` in the exception path.
- A UDF that queries data (`fn_medicine_cost`, `fn_days_stayed`) should use a **new cursor on the same connection**; test it inside a write transaction. If your SQLite build misbehaves, compute those values with a correlated subquery and keep the UDF as a thin wrapper.

**Seed and triggers**
- Triggers are created **after** the seed. Seed audit rows 1-12 already exist.
- After seed, the next ids must be patient 113, visit 421, prescription 623, bill 712, audit_log 13. Verify with `sqlite_sequence`.

**Audit text**
- Amounts as `NUMERIC` so `6015` prints as `6015`, not `6015.0`.
- `changed_by` comes from `(SELECT username FROM app_session WHERE id=1)`.

**Service behaviours that are easy to get wrong**
- `register_emergency`: count only `Waiting` and `Under Treatment` visits per Emergency-department doctor; tie goes to lowest id. On the seed, doctors 203 and 207 both have 2 active cases, so the demo assigns 203.
- `start_treatment`: allowed from Waiting or Scheduled; the update fires the doctor-status trigger.
- `allot_bed`: updates bed and visit in the same transaction; the visit `UPDATE` sets `bed_id`, `admit_time`, `visit_status='Admitted'` at once (one audit row). `OLD.visit_status = 'Under Treatment'` then turns the doctor Available.
- `discharge_patient`: `discharge_time` only if the visit had a bed (CASE as in Review II); bed becomes `Cleaning`.
- `generate_bill`: visit must be `Discharged`; one bill per visit (UNIQUE); `bed_charge = daily_charge * fn_days_stayed`; total must satisfy `chk_bill_total`; status Pending.
- `add_prescription`: reject only Cancelled visits (the rollback demo prescribes against a discharged visit).
- Cancelled bookings free their slot because the partial index excludes `Cancelled`; test it.
- `book_appointment`: map both the service pre-check and a unique-index violation to `SLOT_TAKEN`.

**Errors**
- Parse the constraint name out of SQLite messages. Named CHECKs report `CHECK constraint failed: <name>`; unique indexes may report `UNIQUE constraint failed: index 'uq_doctor_slot'` or a column list; handle both.
- Trigger messages come through as `sqlite3.IntegrityError`; map by message text.

**Inspector**
- Trace callback sees trigger bodies as `-- TRIGGER <name>` lines (verify on your SQLite version). Keep a fallback based on diffing `audit_log`.
- Reset the trace callback after each call.
- Truncate long SQL and cap snapshots to the touched primary keys.

**Sandbox runs (violations, trigger demos, tamper test)**
- Always `BEGIN`, execute, then `ROLLBACK` in a `finally`; assert row counts unchanged in a test.

**SQL console**
- Separate connection, `PRAGMA query_only=ON`, single statement, `SELECT`/`WITH` only, 500 row cap.

**Performance/robustness**
- Use bound parameters everywhere. One connection per request on `flask.g`.

---

## 5. Self-check before each sync

- [ ] `pytest` green
- [ ] Fresh DB golden counts and values match ARCHITECTURE 9
- [ ] Every endpoint returns the envelope in stub and real mode
- [ ] `CONTRACT.md` up to date and Person 2 informed of any change
- [ ] Demo T1-T6 passes from reset, twice

---

## 6. Viva topics you must be able to explain

Schema design and normalisation; every constraint and why; partial unique indexes vs Oracle function-based indexes; each trigger and why it is split by event; `BEGIN IMMEDIATE`; UDFs; the inspector (how triggers are detected); error mapping; the Oracle to SQLite mapping table; limitations.

---

## 7. Prompts for Claude (Claude Code or chat)

Put `ARCHITECTURE.md`, `PERSON1_BACKEND.md` and the Review II SQL in the repo first, then paste the master prompt. After that, paste one phase prompt at a time and review each result before moving on.

### Master prompt

````text
You are helping me build the BACKEND (Person 1) of a two-person DBMS course project: a Smart Hospital Management System in Python + Flask + SQLite. My teammate builds the web UI.

First read these files completely before writing anything:
1. ARCHITECTURE.md (source of truth for design, API contract, demo script, golden values)
2. PERSON1_BACKEND.md (my scope, phases, acceptance criteria)
3. docs/reference/DBMS_Review2_Hospital_Management_System.sql (the Oracle version: schema, seed data, 19 queries, procedures, functions, triggers; port it faithfully)

Rules:
- I own: app.py, config.py, requirements.txt, CONTRACT.md, db/, services.py, errors.py, inspector.py, queries.py, introspect.py, metadata.py, demo.py, api.py, api_stub.py, fixtures/, tests/. Do NOT create or edit templates/, static/js, static/css or views.py (my teammate owns them). You may add static/img/er_diagram.png.
- Follow the API contract in ARCHITECTURE.md section 8 exactly: URLs, field names, envelope {ok, message, data, error, inspector}. If you think the contract should change, stop and tell me instead of changing it.
- Use plain sqlite3 (no ORM), bound parameters only, PRAGMA foreign_keys=ON on every connection, isolation_level=None with explicit BEGIN IMMEDIATE / COMMIT / ROLLBACK in every service.
- Triggers are created after the seed. Use app_session for changed_by. Use the exact constraint, index and trigger names from ARCHITECTURE.md.
- The numbers in ARCHITECTURE.md section 9 (golden values) and section 11 (demo script: ids 113, 421, 422, 623, 712, audit rows 13-20, bill 6015) are acceptance tests. Write pytest tests for them.
- Work one phase at a time (phases in PERSON1_BACKEND.md section 2). After each phase: run pytest, show me the results, list any deviations or doubts, then STOP and wait for my go-ahead.

Start with Phase 1 (stub API + fixtures) now.
````

### Phase prompts

````text
PHASE 1 - Stubs. Create app.py (app factory, registers api blueprint and views.views_bp from views.py; if views.py does not exist yet, create a tiny temporary one and tell me), config.py, requirements.txt, CONTRACT.md (copy of ARCHITECTURE sections 8-11), api_stub.py and fixtures/ with one realistic JSON envelope per endpoint in ARCHITECTURE 8.2. FLASK_API_MODE=stub serves them. Include inspector objects on all write endpoints and a few ok:false examples. Use the seed ids from the demo script so fixtures look real. Add a test that every endpoint in the catalogue has a fixture.
````

````text
PHASE 2 - Database port. Create db/schema.sql, db/seed.sql, db/triggers.sql, db/connection.py, db/init_db.py following ARCHITECTURE section 5 and the Review II Oracle script. Register fn_days_stayed, fn_medicine_cost, fn_triage_label. Write tests/test_schema.py and tests/test_triggers.py: golden row counts, next ids (113/421/623/712/13), the 11 violation statements (v01-v11) each failing with the expected error, partial index lets a cancelled slot be rebooked, stock reduce/restore, audit rows with changed_by from app_session, doctor Busy/Available, audit protection. Run pytest and report.
````

````text
PHASE 3 - Services. Implement services.py (every function in ARCHITECTURE section 6) and errors.py (constraint and trigger message mapping to codes). Each service is one atomic transaction and raises BusinessRuleError(code, message) with the codes listed. Write tests/test_services.py covering every happy path and every error code. Run pytest and report.
````

````text
PHASE 4 - Inspector and API. Implement inspector.py (SQL capture via set_trace_callback including '-- TRIGGER name' lines, before/after snapshots by primary key, viva block, elapsed_ms) and api.py with the patient, doctor, medicine, bed, visit, appointment, emergency, prescription and billing endpoints plus /api/meta, /api/role, /api/lookups, /api/dashboard and /api/reset. Handlers are thin and never contain SQL. Set app_session.username from the role at the start of every request. Write tests/test_api.py validating the envelope for every implemented endpoint and that real and fixture responses have the same keys. Run pytest and report.
````

````text
PHASE 5 - Reports and schema. Implement queries.py (q01-q19 translated to SQLite with ids, titles, concept tags, chart hints; cursor loops with console_lines for the emergency queue and pending bills), introspect.py and metadata.py, and the /api/reports*, /api/audit*, /api/schema/* and /api/sql endpoints, including the 11 rolled-back violation tests, the 6 rolled-back trigger demos and the read-only SQL console. Write tests/test_reports.py against the golden values in ARCHITECTURE section 9, and a test that sandbox runs leave all table row counts unchanged. Run pytest and report.
````

````text
PHASE 6 - Demo runners. Implement demo.py and /api/demo/steps, /api/demo/state, /api/demo/<step_id>/run exactly as in ARCHITECTURE section 11 (roles per step, prerequisite checks with error code STEP_ORDER, checks[] on every run). Write tests/test_demo.py that runs T1.1 to T6.4 in order on a fresh DB, asserts every check passes and the ids/amounts match (patient 113, visit 421 and 422, doctor 203, prescription 623, bed 307, bill 712 total 6015, audit rows 13-20), then resets and runs it again with identical results. Run the full pytest suite and report.
````
