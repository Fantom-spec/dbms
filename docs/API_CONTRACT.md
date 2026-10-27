# Smart Hospital Management System — API Contract

All real API responses use the envelope `{ ok, message, data, error, inspector }`. Errors include `kind`, `code`, `constraint`, and `detail`. Protected endpoints require a valid server-side session cookie by default. State-changing API requests must include `X-Requested-With: HospitalApp`. Roles are derived from the authenticated server-side account, not from `X-Role`.

## Authentication

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/auth/login` | Authenticate credentials and set an HttpOnly session cookie |
| POST | `/api/auth/logout` | Invalidate the session and clear the cookie |
| GET | `/api/auth/me` | Return current session status |
| GET | `/api/auth/users` | Administrator-only account list |
| POST | `/api/auth/users` | Administrator-only account creation |

The login response does not expose the session token in JSON. The browser relies on the HttpOnly cookie.

## Hospital endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/meta` | Application/database summary counts |
| GET | `/api/lookups` | Dropdown lookup data |
| GET | `/api/dashboard` | Dashboard metrics |
| GET/POST | `/api/patients` | List/search or register patients |
| GET/PUT/DELETE | `/api/patients/{id}` | Read/update/delete patient record (methods depend on route) |
| GET | `/api/patients/{id}/history` | Patient history |
| GET/POST | `/api/doctors` | List or create doctors |
| PUT | `/api/doctors/{id}` | Update a doctor |
| GET/POST | `/api/medicines` | List or create medicines |
| GET | `/api/medicines/low-stock` | Low-stock report |
| POST | `/api/medicines/{id}/restock` | Restock medicine |
| GET/POST | `/api/beds` | List or create beds |
| POST | `/api/beds/{id}/status` | Change bed status |
| GET | `/api/visits` | List visits |
| GET | `/api/visits/{id}/summary` | Visit summary |
| POST | `/api/appointments` | Book an appointment |
| POST | `/api/visits/{id}/cancel` | Cancel a visit |
| POST | `/api/visits/{id}/start-treatment` | Start treatment |
| POST | `/api/emergency` | Register an emergency arrival |
| GET | `/api/emergency/queue` | View emergency queue |
| POST | `/api/visits/{id}/allot-bed` | Allot a bed |
| POST | `/api/visits/{id}/discharge` | Discharge a visit |
| GET | `/api/visits/{id}/prescriptions` | List visit prescriptions |
| POST | `/api/prescriptions` | Create a prescription |
| DELETE | `/api/prescriptions/{id}` | Delete a prescription |
| POST | `/api/visits/{id}/bill` | Generate a bill |
| GET | `/api/bills` | List bills (Billing/Admin) |
| GET | `/api/bills/pending` | List pending bills (Billing/Admin) |
| POST | `/api/bills/{id}/pay` | Record payment |
| GET | `/api/reports` | Report catalogue |
| GET | `/api/reports/{report_id}` | Execute a report |
| GET | `/api/audit` | Administrator-only audit history |
| POST | `/api/audit/tamper-test` | Administrator-only audit integrity demonstration |
| POST | `/api/reset` | Administrator-only maintenance reset of the SQLite demo database; not linked in the UI |

The old schema viewer, SQL playground, schema introspection endpoints, and interactive guided-demo endpoints have been removed. Use [`docs/DEMO.md`](docs/DEMO.md) for the written demonstration walkthrough.

## Database status

The application uses SQLite (`hospital.db`).
