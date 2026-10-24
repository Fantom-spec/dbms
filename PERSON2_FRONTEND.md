# Person 2: Frontend (Flask pages, UI, documentation)

You own everything the examiner sees: the web UI, the Transaction Inspector display, the Schema Explorer, the Guided Demo page, screenshots and half of the report. Person 1 owns the database and the JSON API; you never touch the database.

Read `ARCHITECTURE.md` first. It is the source of truth (especially sections 7, 8, 10, 11, 12); this file is your work order.

---

## 1. What you deliver

| # | Deliverable | File(s) |
|---|---|---|
| 1 | Page routes + base layout, nav, role switcher, toasts | `views.py`, `templates/base.html`, `static/css/app.css` |
| 2 | Shared JS: API helper, inspector, tables, charts | `static/js/api.js`, `inspector.js`, `tables.js`, `charts.js`, `toast.js` |
| 3 | Vendored libraries | `static/vendor/` (bootstrap, icons, chart.js, mermaid) |
| 4 | 12 pages (templates + page scripts) | `templates/*.html`, `static/js/pages/*.js` |
| 5 | Schema Explorer (7 tabs) | `schema.html`, `pages/schema.js` |
| 6 | Guided Demo | `demo.html`, `pages/demo.js` |
| 7 | UI test checklist run + screenshots | `docs/screenshots/` |
| 8 | Report sections 1, 2, 3, 7, 9, 10 | `docs/report/` |

**Do not edit** `db/`, `services.py`, `api.py`, `queries.py`, `demo.py`, `tests/` (Person 1's). If an API response is missing something you need, ask Person 1 and agree it in `CONTRACT.md`.

---

## 2. Ground rules

1. **No database access.** `views.py` only renders templates. Never import `sqlite3`. Everything dynamic comes from `fetch('/api/...')`.
2. **One envelope, always.** `callApi()` returns `{ok, message, data, error, inspector}`; it never throws for `ok:false`. Show `message` (and `error.code`/`error.constraint` as small text) in a red alert/toast; success in a green toast.
3. **Inspector everywhere.** After every write action, call `renderInspector(envelope.inspector, container)` (see 4.2). An "Always show inspector" switch in the header keeps it open.
4. **Offline.** Bootstrap, Bootstrap Icons, Chart.js and Mermaid are downloaded once into `static/vendor/` and committed. No CDN links.
5. **Develop against stubs first.** `FLASK_API_MODE=stub flask --app app run` serves fixture data for every endpoint; switch to real after Sync 1.
6. **Consistent look.** Bootstrap 5.3, left sidebar, one accent colour, cards with light borders. Must be readable on a projector (font size at least 15px, high contrast).
7. Colour code: triage 1 red, 2 orange, 3 yellow, 4 green; bed Free green / Occupied red / Cleaning amber; bill Paid green / Pending amber; visit status badges per status.

---

## 3. Phases

### Phase 0: Day 0, with Person 1 (30 min)
Create `views.py` with the 12 routes and placeholder templates extending `base.html`, so the app boots:

| Route | Template | Script |
|---|---|---|
| `/` | `dashboard.html` | `pages/dashboard.js` |
| `/patients` | `patients.html` | `pages/patients.js` |
| `/appointments` | `appointments.html` | `pages/appointments.js` |
| `/emergency` | `emergency.html` | `pages/emergency.js` |
| `/beds` | `beds.html` | `pages/beds.js` |
| `/pharmacy` | `pharmacy.html` | `pages/pharmacy.js` |
| `/billing` | `billing.html` | `pages/billing.js` |
| `/reports` | `reports.html` | `pages/reports.js` |
| `/audit` | `audit.html` | `pages/audit.js` |
| `/demo` | `demo.html` | `pages/demo.js` |
| `/schema` | `schema.html` | `pages/schema.js` |
| `/admin` | `admin.html` | `pages/admin.js` |

### Phase 1: Hour 1, foundation (about 3 h)
- `base.html`: sidebar nav (icons), top bar with role dropdown, "Reset demo database" button, "Always show inspector" switch, toast container.
- `app.css`, vendored libraries, `api.js`, `toast.js`, `tables.js`.
- **Acceptance:** every route loads with the layout; role switch calls `POST /api/role` and the badge updates; the nav hides items per role (ARCHITECTURE 13).

### Phase 2: Inspector component (about 3 h) - build this early, everything depends on it
See 4.2. **Acceptance:** with stub data, an inspector renders for `POST /api/appointments` with all tabs working and changed cells highlighted.

### Phase 3: First pages (about 6 h)
Dashboard, Patients, Appointments. **Acceptance:** works on stubs; on real API after Sync 1.

### Phase 4: Operational pages (about 8 h)
Emergency, Beds, Pharmacy, Billing, Audit, Reports, Admin. **Acceptance:** each page works end to end on the real API (Sync 2); errors display nicely.

### Phase 5: Schema Explorer and Guided Demo (about 7 h)
**Acceptance:** all 7 tabs work; all 11 violations show "Blocked" with the error; Guided Demo runs T1.1-T6.4 with green checks.

### Phase 6: Polish, screenshots, report (about 5 h)
Responsive check, empty states, loading spinners, keyboard focus, screenshots, report sections, two full rehearsals (swap who drives).

---

## 4. Shared components

### 4.1 `api.js`

```js
export async function callApi(method, url, body) {
  // returns the parsed envelope; on network failure returns
  // {ok:false, message:'Cannot reach server', error:{kind:'internal'}, data:null, inspector:null}
}
export const get  = (url) => callApi('GET', url);
export const post = (url, body) => callApi('POST', url, body);
```
A helper `handle(envelope, {successToast:true, inspectorEl})` shows toast, renders inspector when `envelope.inspector` exists, and returns `envelope.ok`.

### 4.2 Inspector (`inspector.js` + `partials/_inspector.html`)

Input: the envelope's `inspector` object (ARCHITECTURE section 7). Layout (a card, collapsible, auto-open when the header switch is on):

1. **Five-box header** from `inspector.viva`: **Operation | Tables | Component | Database effect | Result**. This is what the examiner asks for in the viva, so make it prominent. Show `component.type` as a badge (procedure, function, cursor, trigger, constraint, query) and `elapsed_ms`.
2. Tabs:
   - **SQL executed**: monospaced list from `sql[]`, trigger lines (`-- TRIGGER ...`) styled differently, copy button.
   - **Triggers and functions**: `triggers_fired[]` as cards (name, event, effect) and `functions_used[]`; "none" state.
   - **Before / After**: for each table in `before`/`after`, two small tables side by side; **highlight changed cells** (green for new/changed, red for removed rows).
   - **Raw JSON**: pretty-printed.
3. For failed actions (`ok:false`) still render the inspector if present, with the `error.code` and `error.constraint` in a red banner (this is how constraint/trigger enforcement is shown).

### 4.3 `tables.js`

`renderTable(container, columns, rows, {badgeColumns, formatters, onRowClick})` supports both object-rows and array-rows (reports). Right-align numbers, format money with two decimals, `null` as a dim dash, sticky header, empty state "No rows". "Export CSV" button (client side).

### 4.4 `charts.js`

`barChart`, `pieChart`, `stackedBar` wrappers around Chart.js using the chart hint from `/api/reports/<id>` (`chart.type`, `label_col`, `value_cols`). Destroy the old chart before drawing a new one.

---

## 5. Page specs

Each page: purpose, data it loads, actions, acceptance. After every action: toast + inspector + refresh the table.

### Dashboard `/`
- Load `GET /api/dashboard`. KPI cards: patients, active visits, free beds, waiting emergency, pending bills (count and amount), low-stock count.
- Charts: bed occupancy per ward (bar), triage distribution (pie).
- Lists: low-stock medicines, last 5 audit entries.
- A "Start guided demo" button linking to `/demo`.

### Patients `/patients`
- Table from `GET /api/patients?q=`; live search box.
- **Register patient** form (name, gender, DOB, phone, address, blood group, emergency contact). Duplicate phone and bad phone format show the constraint message.
- Row actions: **Edit** (PUT), **History** (modal with `GET /api/patients/<id>/history`, labelled "3-table JOIN"), **Delete** (DELETE; blocked for patients with visits, showing the foreign key error).
- Acceptance: duplicate phone error shown with `uq_pat_phone`; delete of patient 101 shows FK error.

### Appointments `/appointments`
- Form: patient (dropdown from `/api/lookups`), doctor (shows department and fee), date-time picker, complaint -> `POST /api/appointments` (send slot as `YYYY-MM-DD HH:MM:SS`).
- Table of visits (`GET /api/visits?type=Appointment`) with status badges; row actions: **Cancel** (`POST /api/visits/<id>/cancel`), **Start treatment** (`POST /api/visits/<id>/start-treatment`).
- Button "Try the same slot again" re-submits the last booking to show the clash error.
- Acceptance: double-booking shows `SLOT_TAKEN`; cancelled slot can be booked again.

### Emergency `/emergency`
- Form: patient, complaint, triage level (1-4 with labels Critical/Very urgent/Urgent/Minor) -> `POST /api/emergency`; result shows the auto-assigned doctor.
- **Live queue** (`GET /api/emergency/queue`), colour-coded rows by triage, plus a collapsible "Cursor output" box printing `console_lines` in a terminal style. Refresh button + auto refresh every 10 s.
- Row actions: Start treatment, Discharge.
- Acceptance: new critical patient appears above minor ones; inspector type shows `cursor`.

### Beds `/beds`
- Ward-grouped grid of bed tiles (Free/Occupied/Cleaning) from `GET /api/beds`, with daily charge.
- **Allot bed**: choose a visit and ward -> `POST /api/visits/<id>/allot-bed`. **Discharge**: `POST /api/visits/<id>/discharge`. Cleaning tile has "Mark free" (`POST /api/beds/<id>/status`).
- Admitted patients list with days stayed.
- Acceptance: allotting an ICU bed when none is free shows `NO_FREE_BED`; a tile changes colour after each action.

### Pharmacy `/pharmacy`
- Medicine table with stock; low stock (<20) highlighted; **Restock** action.
- **Add prescription**: visit, medicine, dosage, days, quantity -> `POST /api/prescriptions`; show stock before/after in the inspector. Insufficient stock shows the trigger message.
- Per-visit prescription list (`GET /api/visits/<id>/prescriptions`) with delete (restores stock).
- Acceptance: prescribing ORS Sachet shows `INSUFFICIENT_STOCK`; deleting a prescription restores stock.

### Billing `/billing`
- Select a discharged visit -> **Generate bill** (`POST /api/visits/<id>/bill`), showing an itemised card: consultation + medicines + bed (days x daily charge) = total, with the functions used (`fn_medicine_cost`, `fn_days_stayed`).
- Bills table with filter (Paid/Pending); **Record payment** with mode Cash/Card/UPI (`POST /api/bills/<id>/pay`).
- **Pending bills (cursor)** panel: `GET /api/bills/pending?min_amount=` with `console_lines` and totals.
- Acceptance: second bill for the same visit shows the UNIQUE error; paying without a mode is prevented in the form.

### Reports `/reports`
- Dropdown from `GET /api/reports` (grouped by concept tag), search box.
- On select: show title, concept badge, **SQL** (syntax-highlighted block with copy), result table, and a chart when `chart` is present. Query q01 has a patient-name input.
- Acceptance: all 19 queries run; values match ARCHITECTURE 9 on a fresh DB.

### Audit `/audit`
- Table from `GET /api/audit` with filters (table, action) and user column (`changed_by`).
- **Tamper test** buttons: "Try to edit a log entry" / "Try to delete a log entry" -> `POST /api/audit/tamper-test`; show a big "Blocked by trg_protect_audit" panel with the error.

### Admin `/admin`
- Tabs: Doctors (add/edit: department, specialization, fee, shift), Medicines (add), Beds (add, status). Uses the doctor/medicine/bed endpoints.
- Constraint errors (fee <= 0, bad shift) display cleanly.

### Schema Explorer `/schema` (the "showcase schema" feature)
Seven tabs; fetch lazily on tab open.
1. **ER diagram**: static image `static/img/er_diagram.png` (zoomable) and a "Live from database" Mermaid ER rendered from `GET /api/schema/er`.
2. **Tables**: left list of tables with row counts, right panel with columns table (name, type, badges PK / FK / NOT NULL / UNIQUE / CHECK / DEFAULT) and a 10-row data preview (`/api/schema/tables/<name>`).
3. **Relationships**: table from `/api/schema/relationships` (1:N, M:N via PRESCRIPTION, 1:1 via BILL) plus a small diagram of the same.
4. **Constraints and indexes**: grouped lists from `/api/schema/constraints` and `/indexes`; each rule that has a violation test shows a **"Try to violate it"** button -> `POST /api/schema/violations/<id>/run`; show attempted SQL, the **Blocked** badge and the database error text. A "Run all 11" button.
5. **Triggers and functions**: cards per logical trigger (timing, events, table, purpose, SQL in a collapsible block, physical triggers listed) with a **Demonstrate** button -> `POST /api/schema/triggers/<logical_name>/demo` rendering the inspector before/after; functions list with signature and Oracle equivalent.
6. **Raw DDL**: `GET /api/schema/ddl` in a code block with Copy and Download.
7. **SQL console**: textarea, sample-query dropdown (include a few of the 19), Run (Ctrl+Enter) -> `POST /api/sql`; results table, row count, time; errors in red. Only SELECT works; show a note.

### Guided Demo `/demo` (the star of the review)
- Left: stepper listing T1-T6 and their steps from `GET /api/demo/steps`, with status (pending / done / failed) from `GET /api/demo/state`.
- Main panel for the current step: title, narration, role badge (the app also switches the header role), "Expected" list, **Run step** button (`POST /api/demo/<step_id>/run`), then the result: message, `checks[]` as green/red ticks, and the full inspector below. **Next** button advances. "Run all" with a pause between steps (toggle).
- "Reset demo" calls `POST /api/reset` and clears the stepper.
- Steps that must fail (T1.3, T2.3, T3.3, T4.3, T4.4, T6.2, T6.3) show a red "Blocked as expected" banner, not an error toast.
- Optional presenter view: large fonts, hides the sidebar.
- Acceptance: T1.1-T6.4 run in order on a fresh DB with every check green; refresh of the page restores progress from `/api/demo/state`.

---

## 6. Role-based navigation

Use the table in ARCHITECTURE section 13. The role comes from `GET /api/meta`; on change call `POST /api/role`, then reload the nav. This is only presentation; do not claim it is real security.

---

## 7. UI test checklist (run before each sync and before the review)

- [ ] All 12 routes load without console errors (stub and real mode)
- [ ] Every write action shows a toast and an inspector
- [ ] Every error (duplicate phone, slot taken, no free bed, insufficient stock, FK delete, audit tamper) displays a readable message with the code/constraint
- [ ] Tables handle empty results and long text
- [ ] Reports: all 19 run; charts render
- [ ] Schema Explorer: 7 tabs; Run all 11 violations -> all Blocked; trigger demos show before/after
- [ ] Guided Demo T1-T6 passes twice with a reset in between
- [ ] Works offline (disconnect Wi-Fi, hard refresh)
- [ ] Readable at 1366x768 and on a projector; keyboard focus visible; no horizontal scroll at 1024px

---

## 8. Documentation you write

| Section | Content |
|---|---|
| 1 Title and team | Project title, the names of the people actually presenting (Review I listed three, Review II two) |
| 2 Introduction | Problem statement (from Review I), objectives, users, scope, technology |
| 3 Functional requirements | FR1-FR20 table with a new column "Screen / API endpoint" |
| 7 SQL queries and outputs | 19 queries: SQL + screenshot of the Reports page result + one-line explanation of the concept |
| 9 Transaction demonstrations | T1-T6: for each step, screenshot of the Guided Demo with the inspector, plus the five viva answers (operation, tables, component, DB effect, result) |
| 10 Conclusion | What was achieved, limitations (no real authentication, single user, no insurance or lab), future work |

Screenshot naming: `docs/screenshots/<section>_<id>.png` (for example `q13_top_billed.png`, `T5_3_generate_bill.png`).

---

## 9. Viva topics you must be able to explain

The user flow for each role; for each screen which table and component it uses; the inspector (five answers); how reports map to SQL concepts; how the Schema Explorer proves constraints work; why the UI never touches the database; what the API contract is; limitations. Also read Person 1's section on triggers and procedures so you can answer follow-ups.

---

## 10. Prompts for Claude (Claude Code or chat)

Put `ARCHITECTURE.md` and `PERSON2_FRONTEND.md` in the repo first. Person 1 provides stub fixtures in the first hour; until then build layout and helpers. Paste the master prompt, then one phase prompt at a time and review each result.

### Master prompt

````text
You are helping me build the FRONTEND (Person 2) of a two-person DBMS course project: a Smart Hospital Management System in Python + Flask + SQLite. My teammate builds the database, services and JSON API. I build the web UI that showcases everything for the final review.

First read these files completely before writing anything:
1. ARCHITECTURE.md (design, API contract in section 8, inspector in section 7, schema explorer in section 10, demo script in section 11)
2. PERSON2_FRONTEND.md (my scope, page specs, phases, acceptance criteria)

Rules:
- I own: views.py, templates/, static/css, static/js, static/vendor, docs/screenshots, docs/report (my sections). Do NOT create or edit db/, services.py, api.py, queries.py, demo.py, inspector.py, tests/ or any Python outside views.py. views.py must never import sqlite3 or access the database; it only renders templates.
- Everything dynamic comes from fetch() to the /api endpoints exactly as listed in ARCHITECTURE.md section 8, using the response envelope {ok, message, data, error, inspector}. Never invent endpoints or field names; if something is missing, tell me so I can ask my teammate to add it to CONTRACT.md.
- Vanilla JavaScript (ES modules), Bootstrap 5.3, Bootstrap Icons, Chart.js 4, Mermaid. No frameworks and no build step. Vendor all libraries into static/vendor/ (download them once and commit; no CDN links) so it works offline.
- Every write action must show a toast and render the Transaction Inspector (five-box header: Operation, Tables, Component, Database effect, Result; tabs: SQL executed, Triggers and functions, Before/After with changed cells highlighted, Raw JSON). Failed actions (ok:false) must still show the error code, the constraint name and the inspector if present.
- Colour codes: triage 1 red, 2 orange, 3 yellow, 4 green; bed Free green, Occupied red, Cleaning amber; bill Paid green, Pending amber. The UI must be readable on a projector.
- Develop against stub mode (FLASK_API_MODE=stub) until my teammate says the real API is ready.
- Work one phase at a time (PERSON2_FRONTEND.md section 3). After each phase give me a short list of what was built, how to see it, and any doubts about the contract, then STOP and wait for my go-ahead.

Start with Phase 1 (foundation) now.
````

### Phase prompts

````text
PHASE 1 - Foundation. Create views.py (12 routes from PERSON2_FRONTEND.md Phase 0 table rendering templates), templates/base.html (sidebar navigation with icons, top bar with role dropdown calling POST /api/role, "Reset demo database" button calling POST /api/reset, "Always show inspector" switch, toast container), static/css/app.css, static/js/api.js (callApi returning the envelope, never throwing on ok:false, plus handle() helper), toast.js, tables.js (renderTable for object rows and array rows, money formatting, empty state, CSV export). Download and commit Bootstrap, Bootstrap Icons, Chart.js and Mermaid into static/vendor/. Navigation items hide per role as in ARCHITECTURE section 13. Create placeholder templates for all 12 pages.
````

````text
PHASE 2 - Inspector. Create static/js/inspector.js and templates/partials/_inspector.html implementing PERSON2_FRONTEND.md section 4.2: five-box header from inspector.viva, component type badge, elapsed_ms, tabs for SQL executed (trigger lines styled differently, copy button), Triggers and functions (cards), Before/After (side-by-side tables with changed cells highlighted green and removed rows red), Raw JSON. Handle ok:false with a red error banner. Build a small dev page or console helper so I can test it with the stub response of POST /api/appointments.
````

````text
PHASE 3 - Dashboard, Patients, Appointments. Build these three pages per PERSON2_FRONTEND.md section 5 using stub mode: KPI cards and Chart.js charts on the dashboard; patient table with live search, register form, edit, history modal, delete; appointment form, visits table, cancel, start treatment, and a "try the same slot again" button. Every action shows a toast and the inspector.
````

````text
PHASE 4 - Operational pages. Build Emergency (form, colour-coded queue, cursor console output box, auto refresh), Beds (ward-grouped tile grid, allot, discharge, mark free, admitted list), Pharmacy (stock table with low-stock highlight, restock, prescription form, per-visit list with delete), Billing (generate bill with itemised card, bills table, payment, pending-bills cursor panel), Reports (19-query dropdown, SQL block, result table, chart), Audit (filters, tamper-test buttons with a 'Blocked by trg_protect_audit' panel) and Admin (doctors, medicines, beds tabs) per PERSON2_FRONTEND.md section 5.
````

````text
PHASE 5 - Schema Explorer and Guided Demo. Build schema.html with the 7 tabs exactly as specified (live Mermaid ER from /api/schema/er plus the static ER image, tables with constraint badges and data preview, relationships, constraints and indexes with 'Try to violate it' buttons and 'Run all 11', triggers and functions with Demonstrate buttons that render the before/after inspector, raw DDL with copy and download, read-only SQL console with Ctrl+Enter). Then build demo.html: stepper for T1-T6 from /api/demo/steps and /api/demo/state, narration, role badge, expected list, Run step, green/red checks, full inspector, Next, Run all with pauses, Reset, a 'Blocked as expected' banner for steps designed to fail, and an optional presenter mode with large fonts.
````

````text
PHASE 6 - Polish and checklist. Go through the UI test checklist in PERSON2_FRONTEND.md section 7 and fix every item: empty states, loading spinners, long text, keyboard focus, projector readability, responsive layout at 1024px, offline run with all vendor files. List anything that still fails. Do not change the API contract.
````
