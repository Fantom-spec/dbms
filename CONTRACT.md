# API Contract — Living Document

This file mirrors **ARCHITECTURE.md sections 8–11** and serves as the single source of truth for the API contract between Person 1 (Backend) and Person 2 (Frontend).

> **Rule:** Any change to a URL, field name, step id, or response shape is written here **first**, announced to the other person, **then** coded. Log every change at the bottom with date and initials.

---

## 8. API Contract (from ARCHITECTURE.md §8)

### 8.1 Envelope (every `/api/*` response)

```json
{ "ok": true,  "message": "Appointment booked. Visit ID 421", "data": { }, "inspector": { } }
{ "ok": false, "message": "Doctor 202 already has an appointment at that time",
  "error": {"kind": "business_rule", "code": "SLOT_TAKEN", "constraint": null, "detail": "raw message"},
  "data": null, "inspector": { } }
```

- `error.kind`: `constraint | business_rule | not_found | validation | internal`
- HTTP status: 200 for every handled outcome (including `ok:false`), 400 for malformed input (still an envelope), 500 for unexpected errors (still an envelope)
- `inspector` is `null` for plain lookups (lists, lookups, meta)
- Field names snake_case; timestamps `"YYYY-MM-DD HH:MM:SS"`; dates `"YYYY-MM-DD"`; money as numbers; missing values `null`
- Entity endpoints return lists of objects. Report/query-style endpoints return `columns: [..]` and `rows: [[..]]` to preserve column order
- **Test endpoints** (sandbox, violations, tamper tests): `ok:true` with `data.blocked:true` when the database rejected the bad statement (the protection worked), plus `data.error`. `ok:false` only if the endpoint itself broke

### 8.2 Endpoint Catalogue

#### Session and Meta

| Method | Path | Body / query | `data` |
|---|---|---|---|
| GET | `/api/meta` | | `{role, username, roles[], sqlite_version, db_path, counts{table:n}}` |
| POST | `/api/role` | `{role}` (Admin, Receptionist, Triage Nurse, Doctor, Billing) | `{role, username}` |
| POST | `/api/reset` | | `{counts{}}` rebuilds DB and clears demo state |
| GET | `/api/lookups` | | `{patients[{id,name}], doctors[{id,name,department,fee}], medicines[{id,name,stock,price}], wards[], departments[]}` |
| GET | `/api/dashboard` | | `{kpis{patients,active_visits,free_beds,pending_amount,pending_bills,waiting_emergency,low_stock_count}, bed_occupancy[], triage[], low_stock[], recent_audit[]}` |

Role to username (written to `app_session` at the start of every request): Admin `ADMIN`, Receptionist `RECEPTION1`, Triage Nurse `TRIAGE_NURSE`, Doctor `DR_AMENON`, Billing `BILLING1`.

#### Patients and Master Data

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

#### Visits

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

#### Pharmacy and Billing

| Method | Path | Body / query | `data` |
|---|---|---|---|
| GET | `/api/visits/<id>/prescriptions` | | `[prescription + medicine_name, price]` |
| POST | `/api/prescriptions` | `{visit_id, medicine_id, dosage, duration_days, quantity}` | `{prescription_id, stock_after}` |
| DELETE | `/api/prescriptions/<id>` | | `{prescription_id, stock_after}` |
| POST | `/api/visits/<id>/bill` | | `{bill_id, consultation_charge, medicine_charge, bed_charge, total_amount}` |
| GET | `/api/bills` | `?status=` | `[bill + patient_name]` |
| GET | `/api/bills/pending` | `?min_amount=0` | `{rows[], console_lines[], count, total}` (cursor) |
| POST | `/api/bills/<id>/pay` | `{payment_mode}` | `{bill_id, payment_status}` |

#### Reports, Audit, Schema

> **Status:** the `/api/schema/*` and `/api/sql` endpoints listed below were removed from the real API. They are kept here for reference and are still served from fixtures in stub mode only.

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

#### Demo

| Method | Path | `data` |
|---|---|---|
| GET | `/api/demo/steps` | `[{transaction:"T1", title, goal, steps:[{id:"T1.1", title, narration, role, expect[]}]}]` |
| GET | `/api/demo/state` | `{completed[step ids], context{}}` |
| POST | `/api/demo/<step_id>/run` | `{step_id, title, narration, role, checks[{label, passed, detail}], artifacts{}}` + inspector. Refuses if a prerequisite step is missing (`error.code = "STEP_ORDER"`). |

### 8.3 Stub Mode

`FLASK_API_MODE=stub` makes `api_stub.py` serve every endpoint above from `fixtures/<METHOD>_<path>.json` (for example `GET_api_patients.json`, `POST_api_appointments.json`, `GET_api_patients_{id}_history.json`), in the exact envelope format. Person 1 pushes stubs in the **first hour** so Person 2 never waits. Real mode is `FLASK_API_MODE=real` (default).

---

## 9. Report Catalogue (from ARCHITECTURE.md §9)

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

### Golden Values on a Freshly Seeded Database

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

## 10. Schema Explorer (from ARCHITECTURE.md §10)

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

## 11. Guided Demo: Six Transactions (from ARCHITECTURE.md §11)

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

## Change Log

| Date | By | Change |
|---|---|---|
| 2026-10-27 | both | **Security & Frontend Repair**: XSS escaping (escapeHtml in all JS), double-submit prevention (preventDoubleSubmit utility), modal/listener fixes, accessibility labels (aria-label on icon-only buttons), Schema page live ER diagram (removed missing er_diagram.png, uses /api/schema/er), Inspector trigger inference note (triggers_fired inferred from row changes), browser smoke tests (tests/smoke_test.py + tests/smoke_test.sh), updated README with security notes & test checklist |
| 2026-10-26 | P1 | Initial contract created from ARCHITECTURE.md sections 8-11 |