# Smart Hospital Management System

A Flask + SQLite hospital management system for BCSE302L Database Systems course project (Review III).

## Features

- **12 Web Pages**: Dashboard, Patients, Appointments, Emergency, Beds, Pharmacy, Billing, Reports, Audit Log, Guided Demo, Schema Explorer, Admin
- **Full API Integration**: All pages connect to `/api/*` endpoints with standard envelope format
- **Transaction Inspector**: Shows SQL executed, triggers fired (inferred from row changes), before/after row changes, viva answers for every write operation
- **Guided Demo**: 6 scripted transactions (T1–T6) demonstrating complete hospital workflow
- **Schema Explorer**: 7 tabs (ER Diagram, Tables, Relationships, Constraints/Indexes, Triggers/Functions, Raw DDL, SQL Console)
- **Reports**: 19 Review II queries with SQL display, results tables, and Chart.js visualizations
- **Role-based Navigation**: Admin, Receptionist, Triage Nurse, Doctor, Billing
- **Offline-Ready**: All vendor libraries (Bootstrap, Chart.js, Mermaid) committed to `static/vendor/`
- **Security Hardened**: XSS protection via HTML escaping, CSRF protection via `X-Requested-With` header, double-submit prevention, input validation
- **Accessibility**: ARIA labels on icon-only buttons, proper form labels, semantic HTML

## Quick Start

### Prerequisites
- Python 3.10+
- pip

### Installation

```bash
# Clone and enter project
cd Smart-Hospital-Management-System

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Initialize database (creates hospital.db with schema, seed data, triggers)
python -m db.init_db

# Run development server
flask --app app run --debug
```

Visit `http://127.0.0.1:5000`

### Stub Mode (Frontend Development)

Run against fixture data without database:

```bash
FLASK_API_MODE=stub flask --app app run --debug
```

## Project Structure

```
hospital_app/
├── app.py                 # Flask app factory
├── config.py              # Configuration (DB_PATH, SECRET_KEY, FLASK_API_MODE)
├── views.py               # Page routes (Person 2 - Frontend)
├── api.py                 # API blueprint (Person 1 - Backend)
├── api_stub.py            # Stub API serving fixtures
├── services.py            # Business logic (atomic transactions)
├── queries.py             # 19 report queries
├── inspector.py           # Transaction inspector (SQL, triggers, before/after)
├── errors.py              # Error mapping (SQLite → friendly codes)
├── introspect.py          # Schema introspection
├── metadata.py            # Curated schema metadata
├── demo.py                # Guided demo runners (T1–T6)
├── requirements.txt
├── CONTRACT.md            # Living API contract
├── db/
│   ├── schema.sql         # Tables, constraints, indexes
│   ├── seed.sql           # Sample data
│   ├── triggers.sql       # 15 triggers (6 logical)
│   ├── connection.py      # PRAGMAs, UDF registration
│   └── init_db.py         # Database initialization
├── fixtures/              # JSON fixtures for stub mode
├── tests/                 # pytest test suite (189 tests)
├── templates/             # Jinja2 templates (base.html + 12 pages)
├── static/
│   ├── css/app.css        # Custom styles
│   ├── js/                # Vanilla ES modules
│   │   ├── api.js         # API helper
│   │   ├── app.js         # Global UI
│   │   ├── inspector.js   # Transaction Inspector
│   │   ├── tables.js      # Table rendering
│   │   ├── charts.js      # Chart.js wrappers
│   │   └── pages/         # Page-specific scripts
│   ├── vendor/            # Vendored libraries (offline)
│   └── img/               # Static images (ER diagram)
└── docs/
    ├── ARCHITECTURE.md    # System architecture
    ├── PERSON1_BACKEND.md # Backend scope
    ├── PERSON2_FRONTEND.md# Frontend scope
    └── README.md
```

## Key Endpoints

| Category | Endpoints |
|----------|-----------|
| Meta | `GET /api/meta`, `POST /api/role`, `POST /api/reset`, `GET /api/lookups`, `GET /api/dashboard` |
| Patients | `GET/POST/PUT/DELETE /api/patients`, `GET /api/patients/<id>/history` |
| Visits | `GET /api/visits`, `GET /api/visits/<id>/summary`, `POST /api/appointments`, `POST /api/visits/<id>/cancel`, `POST /api/visits/<id>/start-treatment` |
| Emergency | `POST /api/emergency`, `GET /api/emergency/queue` |
| Beds | `GET/POST /api/beds`, `POST /api/beds/<id>/status`, `POST /api/visits/<id>/allot-bed`, `POST /api/visits/<id>/discharge` |
| Pharmacy | `GET/POST /api/medicines`, `POST /api/medicines/<id>/restock`, `GET /api/medicines/low-stock`, `GET/POST/DELETE /api/prescriptions` |
| Billing | `POST /api/visits/<id>/bill`, `GET /api/bills`, `GET /api/bills/pending`, `POST /api/bills/<id>/pay` |
| Reports | `GET /api/reports`, `GET /api/reports/<id>` |
| Audit | `GET /api/audit`, `POST /api/audit/tamper-test` |
| Schema | `GET /api/schema/*`, `POST /api/schema/violations/<id>/run`, `POST /api/schema/triggers/<name>/demo`, `POST /api/sql` |
| Demo | `GET /api/demo/steps`, `GET /api/demo/state`, `POST /api/demo/<step_id>/run` |

## API Response Envelope

Every `/api/*` response follows this format:

```json
{
  "ok": true,
  "message": "Operation successful",
  "data": { ... },
  "error": null,
  "inspector": { ... }
}
```

On failure (`ok: false`):
```json
{
  "ok": false,
  "message": "Error description",
  "data": null,
  "error": { "kind": "business_rule|constraint|not_found|validation|internal", "code": "ERROR_CODE", "constraint": "constraint_name", "detail": "raw error" },
  "inspector": { ... }
}
```

## Testing

```bash
# Run all tests
pytest -q

# Run specific test file
pytest tests/test_services.py -v
```

Expected: **189 passed, 1 skipped**

## Documentation

- `CONTRACT.md` - API contract (source of truth for frontend/backend)
- `docs/ARCHITECTURE.md` - Full system architecture
- `docs/PERSON1_BACKEND.md` - Backend scope and ownership
- `docs/PERSON2_FRONTEND.md` - Frontend scope and page specs

## Security Notes

**Roles are simulated, not real authentication.** The `X-Role` header selects a username written to `app_session` for audit trail purposes. There is no login, password hashing, session management, or authorization enforcement at the API level. This is a course project demonstrating database concepts, not a production-ready system.

**CSRF Protection**: State-changing requests require the `X-Requested-With: HospitalApp` header. This is a simple header check, not a full CSRF token implementation.

**XSS Protection**: All user-supplied data rendered in templates and JavaScript is HTML-escaped using a safe `escapeHtml` utility.

**SQL Injection Prevention**: All database queries use parameterized statements. The SQL console (`/api/sql`) is restricted to read-only `SELECT`/`WITH` queries on a separate connection with `PRAGMA query_only=ON`.

## Frontend Test Checklist

### Verified (Automated via Smoke Tests)
- [ ] All 12 pages load without console errors (`bash tests/smoke_test.sh` or `python tests/smoke_test.py`)
- [ ] All API endpoints return valid envelope responses
- [ ] Role switching updates navigation visibility
- [ ] Transaction Inspector appears on write operations

### Verified (Manual)
- [ ] Guided Demo T1–T6 runs end-to-end with all checks green (twice with reset between)
- [ ] Schema Explorer: all 11 violation tests show "Blocked", all 6 trigger demos show before/after
- [ ] Inspector shows operation, tables, component, effect, result for every action
- [ ] Reports page: all 19 queries execute, charts render where applicable
- [ ] Works offline (airplane mode test - all vendor libs local)

### Unverified / Known Limitations
- [ ] Real authentication (login, sessions, passwords)
- [ ] API-level role-based access control (only UI hides nav items)
- [ ] Concurrent user handling (SQLite is single-writer)
- [ ] Production deployment (HTTPS, WSGI server, reverse proxy)
- [ ] Audit log pagination for large datasets
- [ ] Mobile responsiveness on all pages

## Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-10-27 | 1.1.0 | **Security & Frontend Repair**: XSS escaping, double-submit prevention, modal fixes, accessibility labels, live ER diagram, trigger inference note, browser smoke tests |
| 2026-10-24 | 1.0.0 | Initial Review III submission |

## Repair Report (2026-10-27)

### Issues Fixed

1. **XSS Vulnerabilities**: User data rendered without escaping in multiple JS files (schema.js, beds.js, admin.js, patients.js, appointments.js). Fixed by importing and using `escapeHtml` from tables.js.

2. **Double Form Submissions**: No protection against rapid form submissions. Added `preventDoubleSubmit()` utility in api.js that disables submit button during async request.

3. **Modal/Listener Bugs**: Some event listeners not properly cleaned up; modal form handlers used inconsistent patterns. Standardized all form handlers to use `preventDoubleSubmit()`.

4. **Accessibility**: Icon-only buttons lacked `aria-label` attributes. Added labels to edit/delete/view buttons in patients.js, admin.js, appointments.js, pharmacy.js.

5. **Schema Page ER Diagram**: Static `er_diagram.png` was missing. Replaced with live Mermaid diagram from `/api/schema/er`.

6. **Inspector Trigger Inference**: The inspector now displays a note that triggers are inferred from row changes (SQLite trace callback doesn't report trigger names).

7. **Browser Smoke Tests**: Added automated smoke tests (Playwright + bash/curl) in `tests/smoke_test.py` and `tests/smoke_test.sh`.

### Files Modified

- `static/js/api.js` - Added `preventDoubleSubmit()` utility
- `static/js/tables.js` - Exported `escapeHtml` function
- `static/js/inspector.js` - Added trigger inference note display
- `static/js/pages/*.js` - All 12 page scripts updated for XSS, double-submit, accessibility
- `templates/schema.html` - Replaced static ER image with live Mermaid
- `tests/smoke_test.py` - New Playwright-based smoke test
- `tests/smoke_test.sh` - New curl-based quick smoke test

### Testing

- All existing pytest tests pass (189 passed, 1 skipped)
- Manual verification of all 12 pages
- Guided Demo T1–T6 runs successfully
- Schema Explorer violation sandbox and trigger demos work

## Demo Script (Guided Demo)

Run the 6 transactions in order:

1. **T1** - Register patient & book appointment (Receptionist)
2. **T2** - Emergency arrival & triage (Triage Nurse)
3. **T3** - Consultation & prescription (Doctor)
4. **T4** - Admission & bed allotment (Doctor)
5. **T5** - Discharge, billing & payment (Billing)
6. **T6** - Audit & integrity (Admin)

Each step shows expected outcome, runs via API, displays green/red checks, and renders the Transaction Inspector.

## License

Course project for BCSE302L Database Systems, VIT.