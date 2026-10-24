# Smart Hospital Management System: Final Architecture (Review III)

Course: BCSE302L Database Systems | Stack: Python + Flask + SQLite | Team: 2 people
Status: **FINAL**. Any change goes into `CONTRACT.md` first (see section 17).

Companion files: `PERSON1_BACKEND.md` (database, services, API) and `PERSON2_FRONTEND.md` (web UI).

---

## 1. Goals and grading map

Review III (10 marks) asks for an integrated system, at least 5 real transactions, visible SQL/PL-SQL interaction, reports, documentation and a viva. The guideline flow is:

> User Operation -> SQL/PL-SQL -> Database Processing -> Database Update/Retrieval -> Result

For every transaction we must explain: **what operation, which tables, which component, how the DB changed, what result.** The whole architecture is built so the UI can show those five answers automatically (the **Transaction Inspector**, section 7).

| Marks | Component | Delivered by |
|---|---|---|
| 2 | Integrated database operation | One Flask app, one SQLite DB, one service layer behind every screen |
| 3 | 5+ real-world transactions | **Guided Demo** page, 6 scripted transactions T1-T6 (section 11) |
| 2 | SQL/PLSQL interaction | Inspector shows service/function/cursor/trigger/constraint used per action |
| 1 | Output and reports | Reports page, all 19 Review II queries + charts |
| 1 | Report and documentation | Section 18 |
| 1 | Viva | Section 20 |

---

## 2. Tech stack

| Layer | Choice | Notes |
|---|---|---|
| Language | Python 3.10+ | |
| Web framework | Flask 3.x | Jinja2 templates, one API blueprint |
| Database | SQLite 3.25+ (built into Python) | Window functions (RANK) need 3.25+. Check `sqlite3.sqlite_version`. |
| DB access | Plain `sqlite3`, no ORM | The SQL must be visible and explainable in the viva |
| UI | Bootstrap 5.3, Bootstrap Icons, Chart.js 4, Mermaid 10+ | **Vendored into `static/vendor/`**, so the demo works without internet |
| JS | Vanilla ES modules + `fetch` | No build step, no framework |
| Tests | pytest | |

`requirements.txt`: `Flask>=3.0`, `pytest`. Nothing else.

---

## 3. System overview

```
 Browser (Bootstrap pages, vanilla JS, Chart.js, Mermaid)
        |  fetch() JSON, one envelope format everywhere
        v
 Flask app (app.py)
   |-- views.py     page routes: render templates only, NO database access      [Person 2]
   |-- api.py       /api/* blueprint: thin handlers, no SQL, calls services      [Person 1]
   |-- api_stub.py  same URLs served from fixtures/ (FLASK_API_MODE=stub)        [Person 1]
        |
        v
 Service layer (services.py)  = the "procedures": one atomic transaction each
   |-- inspector.py   captures SQL, triggers fired, before/after rows
   |-- errors.py      maps sqlite errors to friendly messages and codes
   |-- queries.py     the 19 report queries, cursor-style loops
   |-- introspect.py + metadata.py   schema explorer data
   |-- demo.py        T1-T6 runners with self-checks
        |
        v
 SQLite (hospital.db)
   tables + CHECK/UNIQUE/FK + partial unique indexes
   15 triggers (6 logical)  +  3 registered Python functions
```

Rules that keep the layers honest:

1. `views.py` and templates never touch the DB; they only call `/api/*`.
2. `api.py` never contains SQL; it calls `services.py`, `queries.py`, `introspect.py`, `demo.py`.
3. Business rules that must hold even against hand-written SQL live **in the database** (constraints, indexes, triggers). The service layer adds friendly validation and orchestration on top.

---

## 4. Repository layout and ownership

```
hospital_app/
|-- app.py                  P1  app factory, registers blueprints, per-request DB connection + role
|-- config.py               P1  DB_PATH, SECRET_KEY, FLASK_API_MODE
|-- requirements.txt        P1
|-- CONTRACT.md             P1  living copy of sections 8-11 (changes logged here)
|-- db/
|   |-- schema.sql          P1  tables, constraints, indexes
|   |-- seed.sql            P1  Review II sample data
|   |-- triggers.sql        P1  15 native triggers
|   |-- connection.py       P1  PRAGMAs, UDF registration, trace hook
|   `-- init_db.py          P1  rebuild DB: delete file, run schema -> seed -> triggers
|-- services.py             P1
|-- errors.py               P1
|-- inspector.py            P1
|-- queries.py              P1
|-- introspect.py           P1
|-- metadata.py             P1  curated descriptions: constraints, triggers, relationships
|-- demo.py                 P1
|-- api.py                  P1
|-- api_stub.py             P1
|-- fixtures/               P1  one JSON per endpoint, for stub mode
|-- tests/                  P1  pytest
|-- views.py                P2  12 page routes
|-- templates/              P2  base.html, partials/, 12 pages
|-- static/
|   |-- css/app.css         P2
|   |-- js/                 P2  api.js, inspector.js, tables.js, charts.js, pages/*.js
|   |-- vendor/             P2  bootstrap, icons, chart.js, mermaid (committed)
|   `-- img/er_diagram.png  P1 draws, P2 displays
`-- docs/
    |-- reference/DBMS_Review2_Hospital_Management_System.sql   (Oracle source of truth)
    |-- screenshots/        P2
    `-- report/             split, see section 18
```

---

## 5. Database layer

### 5.1 Principle

The **design is unchanged from Review II** (same 8 tables, columns, constraints, sample data, business rules). Only the Oracle PL/SQL layer is re-expressed for SQLite. Keep the Oracle script and Review II screenshots as evidence of the original.

### 5.2 Tables (domain: 8, plus 1 technical)

`patient`, `doctor`, `bed`, `medicine`, `visit`, `prescription`, `bill`, `audit_log` (exactly as in Review I/II), plus **`app_session`** (1 row: `id=1, username`), a technical table so triggers know who made a change (SQLite has no `USER`). `app_session` is not part of the ER diagram or the "8 tables" count; say so in the viva.

### 5.3 Type and format rules

| Oracle | SQLite | Rule |
|---|---|---|
| `NUMBER` PK | `INTEGER PRIMARY KEY AUTOINCREMENT` | Seed inserts explicit ids; SQLite then continues from max+1. Next ids after seed: patient 113, visit 421, prescription 623, bill 712, audit_log 13 (matches Review II sequences). |
| `NUMBER(8,2)` | `NUMERIC` | Integer values stay integers (`6015`), decimals stay real (`797.5`). Round to 2 dp in Python. |
| `VARCHAR2(n)` | `TEXT` | Keep `CHECK` lists. |
| `DATE` | `TEXT 'YYYY-MM-DD'` | |
| `TIMESTAMP` | `TEXT 'YYYY-MM-DD HH:MM:SS'` | ISO text sorts and compares correctly. |
| `SYSDATE`/`SYSTIMESTAMP` default | `DEFAULT (date('now','localtime'))` / `(strftime('%Y-%m-%d %H:%M:%S','now','localtime'))` | |
| `DEFAULT USER` (`changed_by`) | trigger reads `app_session.username` | |
| `REGEXP_LIKE(phone,'^[0-9]{10}$')` | `CHECK (phone GLOB '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]')` | |
| Function-based unique indexes | **Partial unique indexes** | see 5.5 |

Every connection must run `PRAGMA foreign_keys = ON` (otherwise FKs are silently ignored) and `PRAGMA busy_timeout = 5000`. Use `isolation_level=None` and control transactions manually.

### 5.4 Constraints

Carry over every constraint from the Review II script, with the same names (`pk_*`, `uq_pat_phone`, `chk_pat_gender`, `chk_visit_triage`, `chk_visit_bed`, `chk_visit_disch`, `chk_bill_total`, `chk_bill_paid`, ...). Names matter: the Schema Explorer and error messages display them.

### 5.5 Indexes

```sql
CREATE UNIQUE INDEX uq_doctor_slot ON visit(doctor_id, visit_datetime) WHERE visit_status <> 'Cancelled';
CREATE UNIQUE INDEX uq_active_bed  ON visit(bed_id) WHERE visit_status = 'Admitted';
CREATE INDEX idx_visit_patient ON visit(patient_id);
CREATE INDEX idx_visit_doctor  ON visit(doctor_id);
CREATE INDEX idx_presc_visit   ON prescription(visit_id);
```

### 5.6 Triggers (6 logical = 15 physical)

SQLite triggers are single-event, so each Oracle trigger becomes one per event. Naming: `trg_<logical>__<event>`. The Schema Explorer groups by the part before `__`.

| Logical (Review II) | Physical SQLite triggers | Behaviour |
|---|---|---|
| `trg_reduce_stock` | `__insert` (BEFORE INSERT prescription), `__delete` (AFTER DELETE prescription) | Insert: `RAISE(ABORT,'Insufficient stock for <name>: available X, requested Y')` if stock < qty, else reduce stock. Delete: restore stock. |
| `trg_audit_visit` | `__insert`, `__update`, `__delete` (AFTER, on visit) | Writes `audit_log` rows: `New <type> visit for patient N`, `Status A -> B`, `Visit deleted (patient N)` |
| `trg_audit_bill` | `__insert`, `__update`, `__delete` (on bill) | `Bill generated: total T (Pending)`, `Payment status A -> B`, `Bill deleted` |
| `trg_audit_patient` | `__insert`, `__update`, `__delete` (on patient) | `New patient registered`, `Patient details updated`, `Patient record deleted` |
| `trg_doctor_status` | `__insert` (visit inserted as Under Treatment), `__update` (UPDATE OF visit_status) | Busy when a visit becomes Under Treatment; Available when it leaves Under Treatment |
| `trg_protect_audit` | `__update`, `__delete` (BEFORE, on audit_log) | `RAISE(ABORT,'AUDIT_LOG entries cannot be modified or deleted')` |

All audit triggers insert with `changed_by = (SELECT username FROM app_session WHERE id=1)`. Audit text must not show `.0` on whole amounts (store amounts as NUMERIC, see 5.3).

Example:

```sql
CREATE TRIGGER trg_reduce_stock__insert BEFORE INSERT ON prescription
BEGIN
  SELECT RAISE(ABORT, 'Insufficient stock for ' || m.medicine_name ||
         ': available ' || m.stock_quantity || ', requested ' || NEW.quantity)
  FROM medicine m WHERE m.medicine_id = NEW.medicine_id AND m.stock_quantity < NEW.quantity;
  UPDATE medicine SET stock_quantity = stock_quantity - NEW.quantity
  WHERE medicine_id = NEW.medicine_id;
END;
```

### 5.7 Functions (registered with `create_function`, callable inside SQL)

| Function | Behaviour (same as Review II) |
|---|---|
| `fn_days_stayed(visit_id)` | 0 if never admitted; else date difference between admit and discharge (or now if not discharged), minimum 1 |
| `fn_medicine_cost(visit_id)` | `SUM(quantity * price_per_unit)` for the visit, 0 if none |
| `fn_triage_label(level)` | 1 Critical, 2 Very urgent, 3 Urgent, 4 Minor, else "Not triaged" (`deterministic=True`) |

### 5.8 Init order

`init_db.py` deletes `hospital.db`, then runs `schema.sql` -> `seed.sql` -> `triggers.sql`. **Triggers go last** so the seed does not generate extra audit rows or reduce stock (the seed already contains the final stock and the 12 historical audit rows). `app_session` row is inserted in `schema.sql`. Reset = delete the file and rebuild (never `DELETE FROM audit_log`, the protection trigger blocks it).

### 5.9 Oracle to SQLite mapping (use this table in the report and viva)

| Review II (Oracle) | Review III (SQLite) | Why |
|---|---|---|
| Stored procedures `sp_*` | Python functions in `services.py`, each in `BEGIN IMMEDIATE ... COMMIT/ROLLBACK` | SQLite has no stored procedures |
| `SELECT ... FOR UPDATE` | `BEGIN IMMEDIATE` (database write lock) | SQLite locks the whole DB, not rows |
| PL/SQL functions | `create_function` UDFs | Still callable from SQL |
| Explicit cursors | `cur.execute()` + `fetchone()` loops | Same row-by-row processing |
| `DBMS_OUTPUT` | `console_lines` array returned by the API | |
| Sequences | `AUTOINCREMENT` | |
| Function-based unique index | Partial unique index (`WHERE`) | |
| Multi-event triggers | One trigger per event | SQLite limitation |
| `RAISE_APPLICATION_ERROR` | `RAISE(ABORT, ...)` in triggers, exceptions in services | |
| `DEFAULT USER` | `app_session.username` | |

---

## 6. Service layer (`services.py`)

Each function takes a connection, runs as **one atomic transaction** (`BEGIN IMMEDIATE`, `COMMIT`, `ROLLBACK` on any error), and returns plain data. On rule failure it raises `BusinessRuleError(code, message)`. The API wrapper adds the inspector (section 7).

| Function | Review II origin / FR | Behaviour |
|---|---|---|
| `register_patient(data)` | FR1 | INSERT patient; UNIQUE phone and CHECKs enforced by DB |
| `update_patient(id, data)` | FR1 | UPDATE |
| `delete_patient(id)` | demo | DELETE; FK blocks if visits exist |
| `patient_history(id)` | FR2 | 3-table JOIN (patient, visit, doctor) |
| `book_appointment(patient_id, doctor_id, slot, complaint)` | `sp_book_appointment`, FR4 | Patient exists, doctor exists, slot in future, no clash; INSERT Scheduled; unique-index violation also mapped to SLOT_TAKEN |
| `cancel_appointment(visit_id)` | FR5 | Only Scheduled visits; set Cancelled |
| `register_emergency(patient_id, complaint, triage, arrival=None)` | `sp_register_emergency`, FR6 | Triage 1-4; patient exists; assign Emergency-department doctor with fewest Waiting/Under Treatment visits (tie: lowest id); INSERT Waiting |
| `start_treatment(visit_id)` | FR8 | Waiting/Scheduled -> Under Treatment (fires doctor Busy) |
| `add_prescription(visit_id, medicine_id, dosage, duration_days, quantity)` | FR9 | Reject Cancelled visits; INSERT (trigger reduces stock) |
| `delete_prescription(id)` | | DELETE (trigger restores stock) |
| `restock_medicine(medicine_id, qty)` | | stock += qty |
| `allot_bed(visit_id, ward_type)` | `sp_allot_bed`, FR13 | Visit exists and not Cancelled/Discharged and has no bed; lowest-numbered Free bed in ward else NO_FREE_BED; bed -> Occupied; visit gets bed, `admit_time=now`, status Admitted |
| `set_bed_status(bed_id, status)` | | e.g. Cleaning -> Free |
| `discharge_patient(visit_id)` | `sp_discharge_patient`, FR14 | Only Waiting/Under Treatment/Admitted; status Discharged; if bed: `discharge_time=now`, bed -> Cleaning |
| `generate_bill(visit_id)` | `sp_generate_bill` (promised in FR17, **new**) | Visit must be Discharged and have no bill. consultation = doctor fee; medicine = `fn_medicine_cost`; bed = daily_charge x `fn_days_stayed` (0 if no bed); total = sum; status Pending |
| `pay_bill(bill_id, payment_mode)` | FR18 | mode Cash/Card/UPI; Pending -> Paid |

**Business error codes** (mirror the Review II `RAISE_APPLICATION_ERROR` numbers):

| Code | Oracle | Meaning |
|---|---|---|
| VISIT_NOT_FOUND | -20001/-20020/-20030 | Visit does not exist |
| PATIENT_NOT_FOUND | -20002 | Patient not registered |
| DOCTOR_NOT_FOUND | -20003 | Doctor does not exist |
| SLOT_IN_PAST | -20004 | Appointment must be in the future |
| SLOT_TAKEN | -20005 | Doctor already booked at that time |
| BAD_TRIAGE | -20010 | Triage must be 1-4 |
| NO_EMERGENCY_DOCTOR | -20011 | No Emergency doctor |
| VISIT_CLOSED | -20021 | Visit already Cancelled/Discharged |
| ALREADY_HAS_BED | -20022 | Visit already has a bed |
| NO_FREE_BED | -20023 | No Free bed in ward |
| BED_TAKEN | -20024 | Bed taken concurrently |
| BAD_STATUS | -20031 | Action not allowed from current status |
| AUDIT_PROTECTED | -20050 | Audit log is read-only |
| INSUFFICIENT_STOCK | -20060 | Not enough stock |
| BILL_EXISTS / NOT_DISCHARGED | new | Billing preconditions |

Database-level failures are mapped by `errors.py` using the constraint name in the SQLite message (`UNIQUE constraint failed: patient.phone` -> `UQ_PATIENT_PHONE`, `CHECK constraint failed: chk_visit_triage` -> `CHK_VISIT_TRIAGE`, `FOREIGN KEY constraint failed` -> `FK_VIOLATION`, trigger messages -> their codes).

---

## 7. Transaction Inspector

Every state-changing call (and every report, cursor call and sandbox run) returns an `inspector` object that the UI renders as a panel. It answers the five viva questions on screen.

Implementation (`inspector.py`):
- `conn.set_trace_callback(fn)` collects executed SQL. Statements run inside triggers appear as `-- TRIGGER <name>` lines; parse those to build `triggers_fired`. Fallback if a SQLite build does not emit them: diff `audit_log` and the touched tables.
- Each service declares which rows it touches; the inspector snapshots them **before** and **after** (by primary key).
- `viva` block is filled from per-operation text defined next to each service.

Shape (also in section 8):

```json
"inspector": {
  "operation": "Book appointment",
  "component": {"name": "services.book_appointment", "type": "procedure", "oracle_equivalent": "sp_book_appointment"},
  "tables": ["visit", "audit_log"],
  "functions_used": [],
  "triggers_fired": [{"name": "trg_audit_visit", "event": "AFTER INSERT", "effect": "audit_log row 14 written"}],
  "sql": ["BEGIN IMMEDIATE", "INSERT INTO visit (...) VALUES (...)", "COMMIT"],
  "before": {"visit": []},
  "after":  {"visit": [{"visit_id": 421}], "audit_log": [{"log_id": 14}]},
  "viva": {
    "operation": "Book an appointment for patient 113 with Dr. Priya Nair",
    "tables": "visit (insert), audit_log (insert via trigger)",
    "component": "Procedure sp_book_appointment (Python service) + trigger trg_audit_visit",
    "effect": "One new Scheduled visit; one audit row",
    "result": "Visit 421 booked"
  },
  "elapsed_ms": 4.2
}
```

`component.type` is one of `procedure | function | cursor | trigger | constraint | query | index`.

---

## 8. API contract

### 8.1 Envelope (every `/api/*` response)

```json
{ "ok": true,  "message": "Appointment booked. Visit ID 421", "data": { }, "inspector": { } }
{ "ok": false, "message": "Doctor 202 already has an appointment at that time",
  "error": {"kind": "business_rule", "code": "SLOT_TAKEN", "constraint": null, "detail": "raw message"},
  "data": null, "inspector": { } }
```

- `error.kind`: `constraint | business_rule | not_found | validation | internal`.
- HTTP status: 200 for every handled outcome (including `ok:false`), 400 for malformed input (still an envelope), 500 for unexpected errors (still an envelope). The frontend always parses the envelope.
- `inspector` is `null` for plain lookups (lists, lookups, meta).
- Field names snake_case; timestamps `"YYYY-MM-DD HH:MM:SS"`; dates `"YYYY-MM-DD"`; money as numbers; missing values `null`.
- Entity endpoints return lists of objects. Report/query-style endpoints return `columns: [..]` and `rows: [[..]]` to preserve column order.
- **Test endpoints** (sandbox, violations, tamper tests): `ok:true` with `data.blocked:true` when the database rejected the bad statement (the protection worked), plus `data.error`. `ok:false` only if the endpoint itself broke.

### 8.2 Endpoint catalogue

**Session and meta**

| Method | Path | Body / query | `data` |
|---|---|---|---|
| GET | `/api/meta` | | `{role, username, roles[], sqlite_version, db_path, counts{table:n}}` |
| POST | `/api/role` | `{role}` (Admin, Receptionist, Triage Nurse, Doctor, Billing) | `{role, username}` |
| POST | `/api/reset` | | `{counts{}}` rebuilds DB and clears demo state |
| GET | `/api/lookups` | | `{patients[{id,name}], doctors[{id,name,department,fee}], medicines[{id,name,stock,price}], wards[], departments[]}` |
| GET | `/api/dashboard` | | `{kpis{patients,active_visits,free_beds,pending_amount,pending_bills,waiting_emergency,low_stock_count}, bed_occupancy[], triage[], low_stock[], recent_audit[]}` |

Role to username (written to `app_session` at the start of every request): Admin `ADMIN`, Receptionist `RECEPTION1`, Triage Nurse `TRIAGE_NURSE`, Doctor `DR_AMENON`, Billing `BILLING1`.

**Patients and master data**

| Method | Path | Body / query | `data` |
|---|---|---|---|
| GET | `/api/patients` | `?q=` | `[patient + visit_count]` |
| POST | `/api/patients` | patient fields | `{patient_id}` |
| PUT | `/api/patients/<id>` | fields to change | `{patient_id}` |
| DELETE | `/api/patients/<id>` | | `{patient_id}` or FK error |
| GET | `/api/patients/<id>/history` | | `{patient, visits[{visit_id,visit_time,visit_type,doctor_name,complaint,visit_status}]}` |
| GET / POST / PUT | `/api/doctors`, `/api/doctors/<id>` | doctor fields | list / `{doctor_id}` |
| GET / POST | `/api/medicines` | medicine fields | list / `{medicine_id}` |
| POST | `/api/medicines/<id>/restock` | `{quantity}` | `{medicine_id, stock_quantity}` |
| GET | `/api/medicines/low-stock` | `?threshold=20` | `[medicine]` |
| GET | `/api/beds` | | beds grouped by ward `{ward_type: [bed{bed_id,bed_status,daily_charge,visit_id,patient_name}]}` |
| POST | `/api/beds` | `{ward_type, daily_charge}` | `{bed_id}` |
| POST | `/api/beds/<id>/status` | `{status}` (Free/Occupied/Cleaning) | `{bed_id, bed_status}` |

**Visits**

| Method | Path | Body / query | `data` |
|---|---|---|---|
| GET | `/api/visits` | `?status=&type=&patient_id=` | `[visit + patient_name, doctor_name]` |
| GET | `/api/visits/<id>/summary` | | `{visit, patient, doctor, bed, prescriptions[], medicine_cost, days_stayed, bill}` |
| POST | `/api/appointments` | `{patient_id, doctor_id, slot, complaint}` slot `"YYYY-MM-DD HH:MM:SS"` | `{visit_id}` |
| POST | `/api/visits/<id>/cancel` | | `{visit_id}` |
| POST | `/api/visits/<id>/start-treatment` | | `{visit_id, visit_status}` |
| POST | `/api/emergency` | `{patient_id, complaint, triage_level}` | `{visit_id, doctor_id, doctor_name}` |
| GET | `/api/emergency/queue` | | `{rows[], console_lines[]}` (cursor output), inspector type `cursor` |
| POST | `/api/visits/<id>/allot-bed` | `{ward_type}` | `{bed_id}` |
| POST | `/api/visits/<id>/discharge` | | `{visit_id, bed_id, days_stayed}` |

**Pharmacy and billing**

| Method | Path | Body / query | `data` |
|---|---|---|---|
| GET | `/api/visits/<id>/prescriptions` | | `[prescription + medicine_name, price]` |
| POST | `/api/prescriptions` | `{visit_id, medicine_id, dosage, duration_days, quantity}` | `{prescription_id, stock_after}` |
| DELETE | `/api/prescriptions/<id>` | | `{prescription_id, stock_after}` |
| POST | `/api/visits/<id>/bill` | | `{bill_id, consultation_charge, medicine_charge, bed_charge, total_amount}` |
| GET | `/api/bills` | `?status=` | `[bill + patient_name]` |
| GET | `/api/bills/pending` | `?min_amount=0` | `{rows[], console_lines[], count, total}` (cursor) |
| POST | `/api/bills/<id>/pay` | `{payment_mode}` | `{bill_id, payment_status}` |

**Reports, audit, schema**

| Method | Path | Body / query | `data` |
|---|---|---|---|
| GET | `/api/reports` | | `[{id, label, title, concept, chart}]` |
| GET | `/api/reports/<id>` | optional `?param=` | `{id, title, concept, sql, columns[], rows[[]], chart{type, label_col, value_cols[]}}` |
| GET | `/api/audit` | `?table=&action=&limit=100` | `[audit_log row]` |
| POST | `/api/audit/tamper-test` | `{mode: "update"\|"delete"}` | `{blocked, error}` |
| GET | `/api/schema/overview` | | `{tables, triggers, functions, indexes counts}` |
| GET | `/api/schema/tables` | | `[{name, rows, columns}]` |
| GET | `/api/schema/tables/<name>` | `?preview=10` | `{columns[{name,type,pk,notnull,default,unique,fk,checks[]}], row_count, preview{columns,rows}}` |
| GET | `/api/schema/relationships` | | `[{from_table, from_col, to_table, to_col, cardinality, note}]` |
| GET | `/api/schema/constraints` | | `[{table, name, type, rule, expression}]` |
| GET | `/api/schema/indexes` | | `[{name, table, unique, partial_where, purpose}]` |
| GET | `/api/schema/triggers` | | `[{logical_name, physical[], timing, events[], table, purpose, sql}]` |
| GET | `/api/schema/functions` | | `[{name, signature, purpose, oracle_equivalent}]` |
| GET | `/api/schema/ddl` | `?download=1` | `{ddl}` (or file) |
| GET | `/api/schema/er` | | `{mermaid}` live ER text from `PRAGMA foreign_key_list` |
| GET | `/api/schema/violations` | | `[{id, title, rule, enforced_by, sql}]` |
| POST | `/api/schema/violations/<id>/run` | | `{blocked, error, attempted_sql}` (always rolled back) |
| POST | `/api/schema/triggers/<logical_name>/demo` | | `{effect}` + inspector with before/after (always rolled back) |
| POST | `/api/sql` | `{sql}` | `{columns[], rows[[]], row_count, elapsed_ms}` SELECT/WITH only |

**Demo**

| Method | Path | `data` |
|---|---|---|
| GET | `/api/demo/steps` | `[{transaction:"T1", title, goal, steps:[{id:"T1.1", title, narration, role, expect[]}]}]` |
| GET | `/api/demo/state` | `{completed[step ids], context{}}` |
| POST | `/api/demo/<step_id>/run` | `{step_id, title, narration, role, checks[{label, passed, detail}], artifacts{}}` + inspector. Refuses if a prerequisite step is missing (`error.code = "STEP_ORDER"`). |

### 8.3 Stub mode

`FLASK_API_MODE=stub` makes `api_stub.py` serve every endpoint above from `fixtures/<METHOD>_<path>.json` (for example `GET_api_patients.json`, `POST_api_appointments.json`, `GET_api_patients_{id}_history.json`), in the exact envelope format. Person 1 pushes stubs in the **first hour** so Person 2 never waits. Real mode is `FLASK_API_MODE=real` (default).

---

## 9. Report catalogue

`GET /api/reports` lists the 19 Review II queries (translated to SQLite: `TO_CHAR` -> `strftime`, `LOCALTIMESTAMP` -> `datetime('now','localtime')`).

| Id | Review II | Title | Concept tag | Chart |
|---|---|---|---|---|
| q01 | A | Visit history of a patient (`?param=` name, default Aakash Gupta) | 3-table JOIN | none |
| q02 | B | Visits per doctor | LEFT JOIN, GROUP BY | bar |
| q03 | C | Emergency cases by triage | CASE, GROUP BY | pie |
| q04 | D | Departments with 3+ visits | JOIN, HAVING | bar |
| q05 | E | Low-stock medicines (<20) | WHERE, ORDER BY | none |
| q06 | F | Free beds per ward | Aggregate on filtered set | bar |
| q07 | G | Bed occupancy % per ward | Conditional aggregation | bar |
| q08 | H | Bills by payment status | SUM/COUNT, GROUP BY | pie |
| q09 | I | Monthly billing summary | strftime in GROUP BY | stacked bar |
| q10 | J | Pending bills | 4-table JOIN | none |
| q11 | K | Patients with no emergency visit | NOT EXISTS (correlated) | none |
| q12 | L | Doctors above average fee | Scalar subquery | none |
| q13 | M | Top 3 billed patients | Subquery + RANK() window | bar |
| q14 | N | Prescription statistics per medicine | JOIN, HAVING, computed aggregate | bar |
| q15 | O | Currently admitted patients | Multi-table JOIN | none |
| q16 | P | Emergency waiting queue | ORDER BY two columns | none |
| q17 | Q | Average and highest bill by visit type | AVG, ROUND, MAX | bar |
| q18 | R | Doctors who prescribed Aspirin | Nested IN subquery | none |
| q19 | S | Patients with more than one visit | HAVING, MIN/MAX dates | none |

**Golden values on a freshly seeded database** (used by tests and as a manual check before the demo):

| Check | Expected |
|---|---|
| Row counts | patient 12, doctor 10, bed 12, medicine 12, visit 20, prescription 22, bill 11, audit_log 12 |
| q01 | 2 rows (visits 401, 411) |
| q02 | 10 rows; Dr. Arvind Menon first with 4 |
| q03 | levels 1/2/3/4 -> 3/2/1/1 |
| q04 | Emergency 7, General Medicine 4, Cardiology 3 |
| q05 | 3 rows: ORS Sachet 0, Sumatriptan 5, Azithromycin 8 |
| q06 | Emergency 3, General 3, ICU 1, Private 1 |
| q07 | ICU 50%, Private 50%, Emergency 0%, General 0% |
| q08 | Paid 7 bills = 19783; Pending 4 bills = 7260.5 |
| q09 | 2026-09: 4 bills, 2469; 2026-10: 7 bills, 24574.5 |
| q10 | 4 rows: 4273 (Sunita Patil), 1115, 1075, 797.5 |
| q11 | 6 patients (101, 102, 105, 107, 108, 109) |
| q12 | 5 doctors (average fee 730) |
| q13 | Rahul Verma 16161, Sunita Patil 4273, Aakash Gupta 1646 |
| q14 | 7 rows; Aspirin 75mg first (3 prescriptions, 50 units) |
| q15 | 2 rows (visit 413 Private, visit 414 ICU) |
| q16 | visits 418 (T1), 416 (T2), 417 (T4) |
| q17 | Appointment 9 bills avg 734.39 max 1115; Emergency 2 bills avg 10217 max 16161 |
| q18 | doctors 201 and 203 |
| q19 | 8 patients |

Cursor-style screens: **emergency queue** (q16 logic) and **pending bills** are produced by an explicit `cur.execute()` + `fetchone()` loop that also builds `console_lines`, reproducing the Review II `DBMS_OUTPUT` text.

---

## 10. Schema Explorer

Data comes from `introspect.py` (PRAGMA: `table_info`, `foreign_key_list`, `index_list`, `index_info`, `sqlite_master` for DDL and triggers) merged with curated text in `metadata.py` (purposes, cardinalities, which business rule each constraint enforces, Oracle equivalents). CHECK expressions come from the curated list, not regex parsing.

**Seven tabs:** ER diagram, Tables, Relationships, Constraints and indexes, Triggers and functions, Raw DDL, SQL console.

**Violation sandbox.** Each test runs the offending statement inside `BEGIN ... ROLLBACK` (always rolled back, even if it unexpectedly succeeds), so the database is never changed:

| Id | Attempt | Enforced by |
|---|---|---|
| v01 | Insert patient with an existing phone | `uq_pat_phone` (UNIQUE) |
| v02 | Insert appointment with a triage level | `chk_visit_triage` (CHECK) |
| v03 | Second active visit for same doctor and time | `uq_doctor_slot` (partial unique index) |
| v04 | Second admitted patient on the same bed | `uq_active_bed` (partial unique index) |
| v05 | Discharge time before admit time | `chk_visit_disch` (CHECK) |
| v06 | Medicine with price 0 | `chk_med_price` (CHECK) |
| v07 | Bill marked Paid without payment mode | `chk_bill_paid` (CHECK) |
| v08 | Delete a patient who has visits | `fk_visit_patient` (FOREIGN KEY) |
| v09 | Prescribe more than the stock | `trg_reduce_stock__insert` (trigger) |
| v10 | UPDATE/DELETE an audit_log row | `trg_protect_audit` (trigger) |
| v11 | Phone number with letters | `chk_pat_phone` (CHECK) |

**Trigger demos** (`/api/schema/triggers/<logical_name>/demo`): six small sandbox runs (also rolled back) that perform the triggering action and return before/after rows: reduce_stock, audit_visit, audit_bill, audit_patient, doctor_status, protect_audit.

**SQL console safety:** separate connection with `PRAGMA query_only = ON`, accept a single statement starting with `SELECT` or `WITH`, reject `;` followed by more text, cap at 500 rows, abort after about 3 seconds (progress handler).

---

## 11. Guided Demo: six transactions

Run on a fresh seed. Each step sets its role, so the audit log shows different users. Steps depend on earlier ones; `/api/demo/<step_id>/run` checks prerequisites. Each run returns `checks[]` (green ticks on the UI) plus the inspector.

| Step | Role | Action | Expected |
|---|---|---|---|
| **T1 Register patient and book appointment** | Receptionist | | |
| T1.1 | | Register "Sanjay Rao", phone 9876500113 | patient 113; audit row 13 |
| T1.2 | | Book patient 113 with Dr. Priya Nair (202), tomorrow 10:00 | visit 421 Scheduled; audit row 14 |
| T1.3 | | Book patient 101 with doctor 202 at the same slot | fails `SLOT_TAKEN`; nothing inserted |
| **T2 Emergency arrival and triage** | Triage Nurse | | |
| T2.1 | | Show queue (cursor) | 418 (T1), 416 (T2), 417 (T4) |
| T2.2 | | Register emergency: patient 109 (Vivek Joshi), "Chest pain", triage 1 | visit 422, doctor 203 (tie on 2 active cases, lowest id); audit row 15 |
| T2.3 | | Triage level 7 | rejected `BAD_TRIAGE` |
| T2.4 | | Show queue again | new visit ahead of 416 (T2) and 417 (T4); labels via `fn_triage_label` |
| **T3 Consultation and prescription** | Doctor | | |
| T3.1 | | Start treatment on visit 422 | status Under Treatment; doctor 203 Busy; audit row 16 |
| T3.2 | | Prescribe Aspirin 75mg (506), qty 10 | prescription 623; stock 550 -> 540 |
| T3.3 | | Prescribe ORS Sachet (512), qty 2 | rejected `INSUFFICIENT_STOCK` (available 0, requested 2) |
| **T4 Admission and bed allotment** | Doctor | | |
| T4.1 | | Show free ICU beds | bed 307 only |
| T4.2 | | Allot ICU bed to visit 422 | bed 307 Occupied; visit Admitted; doctor 203 Available again; audit row 17 |
| T4.3 | | Allot ICU bed to visit 416 | rejected `NO_FREE_BED` |
| T4.4 | | Sandbox: force bed 308 onto visit 416 as Admitted | blocked by `uq_active_bed` |
| **T5 Discharge, billing and payment** | Billing | | |
| T5.1 | | Discharge visit 422 | Discharged; bed 307 -> Cleaning; audit row 18 |
| T5.2 | | Show `fn_days_stayed` and `fn_medicine_cost` for 422 | days 1, medicine cost 15 |
| T5.3 | | Generate bill | bill 712: 1000 + 15 + 5000 = **6015**, Pending; audit row 19 |
| T5.4 | | Pay by UPI | Paid; audit row 20 |
| T5.5 | | Pending bills (cursor) | the 4 seeded pending bills remain |
| **T6 Audit and integrity** | Admin | | |
| T6.1 | | Show audit trail | rows 13-20 with RECEPTION1, TRIAGE_NURSE, DR_AMENON, BILLING1 |
| T6.2 | | Try to UPDATE/DELETE an audit row | blocked `AUDIT_PROTECTED` |
| T6.3 | | Delete patient 101 | blocked by foreign key |
| T6.4 | | Rollback demo: in one transaction prescribe Paracetamol (501) x3 (ok), then ORS (512) x5 (fails) | whole transaction rolled back; Paracetamol stock still 480 |

Demo context (ids created during the run) is stored server-side in a dict reset by `/api/reset`.

---

## 12. Frontend architecture

- Server-rendered shell + client-side data: each page template extends `base.html` and its page script (`static/js/pages/<page>.js`) fetches `/api/*` and renders.
- Shared modules: `api.js` (`callApi(method, url, body)` returns the envelope, never throws on `ok:false`), `inspector.js` (`renderInspector(inspector, container)`), `tables.js` (`renderTable(columns, rows, options)`), `charts.js` (Chart.js helpers), `toast.js`.
- Global header: role switcher (calls `POST /api/role`), "Reset demo database", "Always show inspector" switch.
- Page routes (all in `views.py`): `/` dashboard, `/patients`, `/appointments`, `/emergency`, `/beds`, `/pharmacy`, `/billing`, `/reports`, `/audit`, `/demo`, `/schema`, `/admin`.
- Colour code: triage 1 red, 2 orange, 3 yellow, 4 green; bed Free green, Occupied red, Cleaning amber; bill Paid green, Pending amber.

Full page specs are in `PERSON2_FRONTEND.md`.

---

## 13. Roles

Roles exist to make `changed_by` meaningful and to match Review I users. The UI hides irrelevant nav items per role (Person 2). API-level enforcement is optional (stretch):

| Role | Pages |
|---|---|
| Admin | everything, including Admin master data and Schema |
| Receptionist / Triage Nurse | Patients, Appointments, Emergency, Beds (view) |
| Doctor | Emergency, Beds, Pharmacy |
| Billing | Billing, Reports |

Demo and Schema pages are visible to all roles (presentation tools).

---

## 14. Security and robustness

- All SQL uses bound parameters; never string-format user input into SQL.
- SQL console: read-only connection (section 10).
- Every service is atomic; errors roll back and return an envelope, never a stack trace (unexpected errors log server-side and return `kind: "internal"`).
- One DB connection per request (stored on `flask.g`, closed on teardown), PRAGMAs applied on open.
- Flask dev server is enough (single presenter machine). No authentication; roles are a simulation, state this in the limitations.

---

## 15. Testing

| File | Covers |
|---|---|
| `test_schema.py` | Row counts, the 11 violation tests raise the expected errors, partial indexes allow rebooking a cancelled slot |
| `test_triggers.py` | Stock reduce/restore, audit rows with correct `changed_by`, doctor Busy/Available, audit protection |
| `test_services.py` | Each service happy path and each error code |
| `test_reports.py` | The golden values in section 9 |
| `test_api.py` | Envelope shape for every endpoint via Flask test client (`ok`, `message`, `data`, `inspector` keys) |
| `test_demo.py` | Runs T1.1 to T6.4 in order on a fresh DB and asserts every `check` passes and ids/amounts match section 11 |

Manual: `PERSON2_FRONTEND.md` contains the UI test checklist. Before the review, run the demo twice end to end, once on each person's laptop.

---

## 16. Running and offline use

```
pip install -r requirements.txt
python -m db.init_db                    # builds hospital.db from schema + seed + triggers
flask --app app run --debug             # http://127.0.0.1:5000
FLASK_API_MODE=stub flask --app app run # UI against fixtures (Person 2 early work)
pytest
```

Vendor all front-end libraries into `static/vendor/` and commit them. Keep a copy of the project and a backup `hospital.db` on a USB drive.

---

## 17. Collaboration and sync points

- Git: `main` + branches `backend` (P1) and `frontend` (P2). Merge to `main` at each sync point. Do not edit the other person's files without telling them.
- `CONTRACT.md` mirrors sections 8-11. **Any change to a URL, field or step is written in `CONTRACT.md` and announced before it is coded.** Log it at the bottom with date and initials.

| When | P1 delivers | P2 delivers |
|---|---|---|
| Day 0 (together, 30 min) | `app.py`, `config.py`, `CONTRACT.md` | `views.py` with 12 routes and placeholder templates so the app boots |
| Hour 1 | `api_stub.py` + fixtures for every endpoint | `base.html`, CSS, `api.js` |
| Day 1 end (Sync 1) | schema, seed, triggers, UDFs, services; real patient/appointment endpoints | base layout, inspector component, Dashboard, Patients, Appointments |
| Day 2 end (Sync 2) | all services and endpoints, reports, inspector, introspection | Emergency, Beds, Pharmacy, Billing, Reports, Audit pages on real API |
| Day 3 | demo runners, tests green, ER image, bug fixes | Schema Explorer, Guided Demo, polish |
| Day 4 | report sections, rehearsal | report sections, screenshots, rehearsal (swap drivers) |

---

## 18. Documentation (report)

| Section (course guideline) | Owner |
|---|---|
| 1 Title and team, 2 Introduction, 3 Functional requirements (FR1-FR20 mapped to screens), 10 Conclusion and limitations | P2 |
| 4 ER diagram, 5 Relational schema, 6 Table creation and constraints (+ Oracle to SQLite table) | P1 |
| 7 SQL queries and outputs (screenshots from Reports page) | P2 |
| 8 Procedures, functions, cursor, triggers (+ mapping table) | P1 |
| 9 Real-world transaction demonstrations T1-T6 (Guided Demo screenshots with inspector) | P2 |

Mention that Review I listed three members and Review II two; the report must list the people actually presenting.

---

## 19. Definition of done and demo-day checklist

- [ ] Fresh `init_db` gives the golden counts and values in section 9
- [ ] `pytest` all green
- [ ] Every page works on the real API with no console errors
- [ ] Guided Demo T1-T6 runs start to finish with all checks green, twice in a row (with reset between)
- [ ] Schema Explorer: all 11 violations show blocked; all 6 trigger demos show before/after
- [ ] Inspector appears on every action and shows operation, tables, component, effect, result
- [ ] Works offline (airplane mode test)
- [ ] Screenshots captured, report complete
- [ ] Backup: project copy on USB, short screen recording of a full demo run
- [ ] Both members can start the app, reset, and run the demo unaided

---

## 20. Viva questions to prepare (both members)

1. Why SQLite when Review II used Oracle, and what changed? (section 5.9)
2. Why `BEGIN IMMEDIATE`? (write lock replaces row-level `FOR UPDATE`)
3. How are double booking and double bed allocation prevented? (partial unique indexes; the DB enforces it, not the app)
4. Why triggers for stock and audit instead of app code? (they hold even for direct SQL)
5. Why has `audit_log` no foreign key? (it must outlive deleted records)
6. Why is there an `app_session` table? (SQLite has no `USER`)
7. Why are there 15 triggers when Review II had 6? (one event per trigger in SQLite)
8. What happens if `generate_bill` fails halfway? (atomic rollback, T6.4)
9. Normal form of the schema, and why is department stored on DOCTOR?
10. How does a prescription change the bill? (`fn_medicine_cost` in `generate_bill`)
11. Which parts are SQL, which are procedural, which are the application?
12. What are the limitations? (single user, no real login, no insurance/lab as in scope)

Split presenting, not understanding: P1 explains schema, triggers, services and mapping; P2 explains user flows, the inspector, reports and demo. Do a 30-minute walkthrough of your half for the other person before the review.

---

## Change log (append here)

| Date | By | Change |
|---|---|---|
| 2026-10-24 | both | Initial final architecture |
