"""
Real API blueprint: thin handlers that call services and report queries.

* One database connection per request (``g.db``), closed in teardown.
* Identity and role are derived from the server-side session, never from client headers.
* Every response is the contract envelope ``{ok, message, data, error, inspector}``.
* State-changing requests must carry ``X-Requested-With: HospitalApp`` (CSRF defence).
"""
import sqlite3

from flask import Blueprint, Response, current_app, g, jsonify, request

import config
import services as svc
from db.connection import get_connection
from db.reset_demo import reset_demo

from errors import BusinessRuleError, error_payload, map_sqlite_error
from inspector import Capture, build_inspector

from auth import (
    authenticate_user, create_session, create_user, get_user_from_session,
    init_auth_tables, invalidate_session, list_users, validate_password_strength,
    validate_username
)

from queries import get_report, get_reports_catalogue
from validation import clamp_limit

api_bp = Blueprint('api', __name__)

ROLES = list(config.ROLE_USERNAMES)
SAFE_METHODS = ('GET', 'HEAD', 'OPTIONS')


# --------------------------------------------------------------------------- role permissions
# Which roles may call each state-changing endpoint (keyed by view-function name).
# Admin may do everything. Sensitive reads and all writes use explicit role rules.
FRONT_DESK = ('Receptionist', 'Triage Nurse')
CLINICAL = ('Doctor',)
WRITE_PERMISSIONS = {
    # registration and scheduling
    'create_patient': FRONT_DESK, 'update_patient': FRONT_DESK,
    'book': FRONT_DESK, 'cancel': FRONT_DESK, 'emergency': FRONT_DESK,
    # beds
    'bed_status': FRONT_DESK + CLINICAL, 'allot_bed': FRONT_DESK + CLINICAL,
    # treatment and pharmacy
    'start_treatment': CLINICAL, 'discharge': CLINICAL,
    'add_prescription': CLINICAL, 'delete_prescription': CLINICAL,
    'restock': CLINICAL,
    # billing
    'generate_bill': ('Billing',), 'pay_bill': ('Billing',),
    # administration (Admin only)
    'delete_patient': (), 'create_doctor': (), 'update_doctor': (), 'create_medicine': (),
    'create_bed': (), 'tamper_test': (), 'reset': (),
}


READ_PERMISSIONS = {
    # Sensitive data is not available to every authenticated role.
    'list_patients': ('Receptionist', 'Triage Nurse', 'Doctor'),
    'patient_history': ('Receptionist', 'Triage Nurse', 'Doctor'),
    'list_visits': ('Receptionist', 'Triage Nurse', 'Doctor'),
    'visit_summary': ('Receptionist', 'Triage Nurse', 'Doctor'),
    'list_prescriptions': ('Doctor',),
    'list_bills': ('Billing',),
    'pending_bills': ('Billing',),
    'reports': ('Billing',),
    'report': ('Billing',),
    'audit': (),
    'get_users': (),
}

def _role_allowed(endpoint, role, method='POST'):
    """Enforce explicit role rules; unknown writes are admin-only by default."""
    if role == 'Admin':
        return True
    if method in SAFE_METHODS:
        allowed = READ_PERMISSIONS.get(endpoint)
        return True if allowed is None else role in allowed
    allowed = WRITE_PERMISSIONS.get(endpoint)
    return role in allowed if allowed is not None else False


class BadRequest(Exception):
    """Malformed input -> HTTP 400 envelope."""

    def __init__(self, message, code='BAD_REQUEST'):
        super().__init__(message)
        self.message, self.code = message, code


# --------------------------------------------------------------------------- envelope

def envelope(ok, message, data=None, error=None, inspector=None, status=200):
    resp = jsonify({'ok': ok, 'message': message, 'data': data, 'error': error, 'inspector': inspector})
    resp.status_code = status
    return resp


def fail(message, kind, code, detail=None, constraint=None, inspector=None, status=200):
    err = {'kind': kind, 'code': code, 'constraint': constraint, 'detail': detail or message}
    return envelope(False, message, None, err, inspector, status)


def body():
    """JSON object body (empty body -> {}); anything else is a 400."""
    if not request.data:
        return {}
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise BadRequest('Request body must be a JSON object')
    return data


# --------------------------------------------------------------------------- request lifecycle

def _extract_token():
    # The same-origin application uses an HttpOnly cookie. Do not accept session
    # credentials from JavaScript-readable storage or arbitrary request headers.
    return request.cookies.get(config.SESSION_COOKIE_NAME)


@api_bp.before_request
def open_connection():
    if request.method == 'OPTIONS':
        return Response('', status=204)

    if request.method not in SAFE_METHODS:
        if request.headers.get(config.CSRF_HEADER) != config.CSRF_VALUE:
            return fail('Missing X-Requested-With header (CSRF protection)', 'validation',
                        'CSRF_REQUIRED', status=403)

    g.db = get_connection(current_app.config['DB_PATH'])
    init_auth_tables(g.db)

    # Session / user lookup
    token = _extract_token()
    g.user = get_user_from_session(g.db, token) if token else None

    # Check route authorization
    is_public = request.path in ('/api/auth/login', '/api/auth/logout', '/api/auth/me')
    auth_enforced = current_app.config.get('AUTH_REQUIRED', True)

    if not is_public and auth_enforced and not g.user:
        return fail('Authentication required', 'authentication', 'UNAUTHORIZED',
                    'Please log in with valid credentials to access this resource', status=401)

    # Public auth endpoints must remain reachable before a session exists.
    if is_public and not g.user:
        g.role = config.DEFAULT_ROLE
        g.username = 'ANONYMOUS'
        return None

    # Resolve identity and role only from a verified session. Role simulation is
    # available solely in explicit test configurations with auth disabled.
    if g.user:
        g.role = g.user.get('role', config.DEFAULT_ROLE)
        g.username = g.user.get('username') or config.ROLE_USERNAMES.get(g.role, 'UNKNOWN')
    elif not auth_enforced and (current_app.testing or current_app.config.get('ROLE_SIMULATION_ENABLED', False)):
        requested_role = request.headers.get('X-Role', config.DEFAULT_ROLE)
        if requested_role not in config.ROLE_USERNAMES:
            return fail('Invalid role', 'validation', 'INVALID_ROLE',
                        f'Role must be one of: {", ".join(ROLES)}', status=400)
        g.role = requested_role
        g.username = config.ROLE_USERNAMES[requested_role]
    else:
        return fail('Authentication required', 'authentication', 'UNAUTHORIZED', status=401)

    endpoint = (request.endpoint or '').rsplit('.', 1)[-1]
    if endpoint not in ('auth_login', 'auth_logout', 'auth_me') and not _role_allowed(endpoint, g.role, request.method):
        return fail(f'The {g.role} role is not permitted to access this resource', 'authorization',
                    'FORBIDDEN', f'Your role ({g.role}) does not have permission for this operation', status=403)

    g.db.execute('INSERT OR IGNORE INTO app_session (id, username) VALUES (1, ?)', (g.username,))
    g.db.execute('UPDATE app_session SET username = ? WHERE id = 1', (g.username,))



@api_bp.teardown_request
def close_connection(exc):
    db = g.pop('db', None)
    if db is not None:
        try:
            if db.in_transaction:
                db.execute('ROLLBACK')
        finally:
            db.close()


@api_bp.errorhandler(BadRequest)
def _bad_request(e):
    return fail(e.message, 'validation', e.code, status=400)


# --------------------------------------------------------------------------- runner

def component(name, ctype='procedure', oracle='N/A'):
    return {'name': name, 'type': ctype, 'oracle_equivalent': oracle}


def run(operation, fn, message, comp=None, functions=None, inspect=True):
    """
    Run ``fn()``; wrap the outcome in the envelope.

    ``message`` is a string or a callable(result)->str.  When ``inspect`` is true the
    inspector captures the SQL, the real row changes and the inferred triggers.
    """
    cap = Capture(g.db).start() if inspect else None
    try:
        try:
            result = fn()
        finally:
            if cap:
                cap.finish()
    except BusinessRuleError as e:
        return fail(e.message, e.kind, e.code, detail=e.message, constraint=_constraint_of(e),
                    inspector=_insp(cap, operation, comp, functions, {'code': e.code, 'detail': e.message}))
    except sqlite3.IntegrityError as e:
        code, msg = map_sqlite_error(e)
        payload = error_payload(code, str(e), 'constraint')
        return envelope(False, msg, None, payload,
                        _insp(cap, operation, comp, functions, {'code': code, 'detail': str(e)}))
    except sqlite3.OperationalError as e:
        if 'locked' in str(e).lower() or 'busy' in str(e).lower():
            return fail('The database is busy; please retry', 'internal', 'DB_BUSY', status=503)
        raise
    text = message(result) if callable(message) else message
    return envelope(True, text, result, None,
                    _insp(cap, operation, comp, functions, None) if inspect else None)


def _constraint_of(e):
    return e.code if getattr(e, 'kind', '') == 'constraint' else None


def _insp(cap, operation, comp, functions, error):
    return build_inspector(cap, operation, component=comp, functions_used=functions, error=error)


def read(fn, message):
    """Plain lookup: no inspector."""
    return run('read', fn, message, inspect=False)


def _int_arg(name, default=None):
    raw = request.args.get(name)
    if raw in (None, ''):
        return default
    try:
        return int(raw)
    except ValueError:
        raise BadRequest(f'Query parameter {name} must be a whole number')


def _float_arg(name, default=None):
    raw = request.args.get(name)
    if raw in (None, ''):
        return default
    try:
        return float(raw)
    except ValueError:
        raise BadRequest(f'Query parameter {name} must be a number')


# --------------------------------------------------------------------------- authentication

@api_bp.route('/auth/login', methods=['POST'])
def auth_login():
    data = body()
    username = data.get('username', '').strip() if isinstance(data.get('username'), str) else ''
    password = data.get('password', '') if isinstance(data.get('password'), str) else ''
    if not username or not password:
        return fail('Username and password are required', 'validation', 'MISSING_CREDENTIALS', status=400)

    # Do not trust client-supplied forwarding headers; configure a trusted proxy explicitly if needed.
    client_ip = request.remote_addr or '127.0.0.1'
    user, err = authenticate_user(g.db, username, password, client_ip=client_ip)
    if err:
        return fail(err, 'authentication', 'INVALID_CREDENTIALS', status=401)

    token, expires = create_session(g.db, user)

    g.user = user
    g.role = user['role']
    g.username = user['username']
    g.db.execute('UPDATE app_session SET username = ? WHERE id = 1', (g.username,))

    resp = envelope(True, f"Welcome back, {user.get('full_name') or user['username']}!", {
        'expires_at': expires.strftime('%Y-%m-%d %H:%M:%S'),
        'user': user
    })
    resp.set_cookie(
        config.SESSION_COOKIE_NAME,
        token,
        httponly=config.SESSION_COOKIE_HTTPONLY,
        samesite=config.SESSION_COOKIE_SAMESITE,
        secure=config.SESSION_COOKIE_SECURE,
        max_age=config.SESSION_LIFETIME_HOURS * 3600,
        path='/'
    )
    return resp


@api_bp.route('/auth/logout', methods=['POST'])
def auth_logout():
    token = _extract_token()
    if token:
        invalidate_session(g.db, token)
    g.user = None
    resp = envelope(True, 'Logged out successfully', None)
    resp.delete_cookie(config.SESSION_COOKIE_NAME, path='/')
    return resp


@api_bp.route('/auth/me', methods=['GET'])
def auth_me():
    if getattr(g, 'user', None):
        return envelope(True, 'Session active', {'authenticated': True, 'user': g.user})
    return envelope(True, 'Not authenticated', {'authenticated': False, 'user': None})


@api_bp.route('/auth/users', methods=['GET'])
def get_users():
    if not g.user or g.user.get('role') != 'Admin':
        return fail('Administrator privileges required', 'authorization', 'FORBIDDEN', status=403)
    return read(lambda: list_users(g.db), 'User accounts retrieved')


@api_bp.route('/auth/users', methods=['POST'])
def add_user():
    if not g.user or g.user.get('role') != 'Admin':
        return fail('Administrator privileges required', 'authorization', 'FORBIDDEN', status=403)
    data = body()
    try:
        new_user = create_user(
            g.db,
            username=data.get('username'),
            password=data.get('password'),
            role=data.get('role', 'Receptionist'),
            full_name=data.get('full_name')
        )
        return envelope(True, f"User {new_user['username']} created successfully", new_user)
    except ValueError as e:
        return fail(str(e), 'validation', 'VALIDATION_ERROR', status=400)


# --------------------------------------------------------------------------- session / meta

@api_bp.route('/meta', methods=['GET'])

def meta():
    def _meta():
        counts = {t: g.db.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
                  for t in ('patient', 'doctor', 'bed', 'medicine', 'visit', 'prescription', 'bill', 'audit_log')}
        return {'role': g.role, 'username': g.username, 'roles': ROLES,
                'sqlite_version': sqlite3.sqlite_version,
                'db_path': _display_db_path(), 'counts': counts}
    return read(_meta, 'Meta information retrieved')


def _display_db_path():
    from pathlib import Path
    return Path(current_app.config['DB_PATH']).name


@api_bp.route('/role', methods=['POST'])
def set_role():
    if not g.user or g.user.get('role') != 'Admin' or not current_app.config.get('ROLE_SIMULATION_ENABLED', False):
        return fail('Role simulation is disabled', 'authorization', 'FORBIDDEN', status=403)
    data = body()
    role = data.get('role')
    if role not in config.ROLE_USERNAMES:
        return fail('Invalid role', 'validation', 'INVALID_ROLE', f'Role must be one of: {", ".join(ROLES)}')
    username = config.ROLE_USERNAMES[role]
    g.db.execute('UPDATE app_session SET username = ? WHERE id = 1', (username,))
    return envelope(True, f'Role switched to {role}', {'role': role, 'username': username})


@api_bp.route('/reset', methods=['POST'])
def reset():
    """Admin-only maintenance reset; intentionally not linked from the website."""
    data = body()
    if data.get('confirm') is not True:
        return fail('Reset needs confirmation: send {\"confirm\": true}', 'validation', 'CONFIRM_REQUIRED')
    g.db.close()
    try:
        info = reset_demo(current_app.config['DB_PATH'])
    finally:
        g.db = get_connection(current_app.config['DB_PATH'])
        g.db.execute('UPDATE app_session SET username = ? WHERE id = 1', (g.username,))
    return envelope(True, 'Database restored to the seeded state', {'counts': info['counts']})


@api_bp.route('/lookups', methods=['GET'])
def lookups():
    return read(lambda: svc.get_lookups(g.db), 'Lookups retrieved')


@api_bp.route('/dashboard', methods=['GET'])
def dashboard():
    return read(lambda: svc.get_dashboard(g.db), 'Dashboard data retrieved')


# --------------------------------------------------------------------------- patients

@api_bp.route('/patients', methods=['GET'])
def list_patients():
    return read(lambda: svc.get_patients(g.db, request.args.get('q', '')), 'Patients retrieved')


@api_bp.route('/patients', methods=['POST'])
def create_patient():
    data = body()
    return run('register_patient', lambda: svc.register_patient(g.db, data),
               lambda r: f"Patient registered. Patient ID {r['patient_id']}",
               component('register_patient', 'procedure', 'PROCEDURE register_patient'))


@api_bp.route('/patients/<int:patient_id>', methods=['PUT'])
def update_patient(patient_id):
    data = body()
    return run('update_patient', lambda: svc.update_patient(g.db, patient_id, data),
               f'Patient updated. Patient ID {patient_id}',
               component('update_patient', 'procedure', 'UPDATE on patient'))


@api_bp.route('/patients/<int:patient_id>', methods=['DELETE'])
def delete_patient(patient_id):
    return run('delete_patient', lambda: svc.delete_patient(g.db, patient_id),
               f'Patient deleted. Patient ID {patient_id}',
               component('fk_visit_patient', 'constraint', 'FOREIGN KEY visit.patient_id'))


@api_bp.route('/patients/<int:patient_id>/history', methods=['GET'])
def patient_history(patient_id):
    return read(lambda: svc.patient_history(g.db, patient_id), 'Patient history retrieved')


# --------------------------------------------------------------------------- doctors

@api_bp.route('/doctors', methods=['GET'])
def list_doctors():
    return read(lambda: svc.get_doctors(g.db), 'Doctors retrieved')


@api_bp.route('/doctors', methods=['POST'])
def create_doctor():
    data = body()
    return run('create_doctor', lambda: svc.create_doctor(g.db, data),
               lambda r: f"Doctor created. Doctor ID {r['doctor_id']}",
               component('create_doctor', 'procedure', 'INSERT into doctor'))


@api_bp.route('/doctors/<int:doctor_id>', methods=['PUT'])
def update_doctor(doctor_id):
    data = body()
    return run('update_doctor', lambda: svc.update_doctor(g.db, doctor_id, data),
               f'Doctor updated. Doctor ID {doctor_id}',
               component('update_doctor', 'procedure', 'UPDATE on doctor'))


# --------------------------------------------------------------------------- medicines

@api_bp.route('/medicines', methods=['GET'])
def list_medicines():
    return read(lambda: svc.get_medicines(g.db), 'Medicines retrieved')


@api_bp.route('/medicines', methods=['POST'])
def create_medicine():
    data = body()
    return run('create_medicine', lambda: svc.create_medicine(g.db, data),
               lambda r: f"Medicine created. Medicine ID {r['medicine_id']}",
               component('create_medicine', 'procedure', 'INSERT into medicine'))


@api_bp.route('/medicines/<int:medicine_id>/restock', methods=['POST'])
def restock(medicine_id):
    data = body()
    return run('restock_medicine', lambda: svc.restock_medicine(g.db, medicine_id, data.get('quantity')),
               lambda r: f"Medicine restocked. Medicine ID {medicine_id}, new stock: {r['stock_quantity']}",
               component('restock_medicine', 'procedure', 'PROCEDURE restock_medicine'))


@api_bp.route('/medicines/low-stock', methods=['GET'])
def low_stock():
    return read(lambda: svc.get_low_stock_medicines(g.db, _int_arg('threshold', 20)),
                'Low stock medicines retrieved')


# --------------------------------------------------------------------------- beds

@api_bp.route('/beds', methods=['GET'])
def list_beds():
    return read(lambda: svc.get_beds(g.db), 'Beds retrieved')


@api_bp.route('/beds', methods=['POST'])
def create_bed():
    data = body()
    return run('create_bed', lambda: svc.create_bed(g.db, data.get('ward_type'), data.get('daily_charge')),
               lambda r: f"Bed created. Bed ID {r['bed_id']}",
               component('create_bed', 'procedure', 'INSERT into bed'))


@api_bp.route('/beds/<int:bed_id>/status', methods=['POST'])
def bed_status(bed_id):
    data = body()
    return run('set_bed_status', lambda: svc.set_bed_status(g.db, bed_id, data.get('status')),
               lambda r: f"Bed status updated. Bed ID {bed_id}, status: {r['bed_status']}",
               component('set_bed_status', 'procedure', 'UPDATE bed.bed_status'))


# --------------------------------------------------------------------------- visits

@api_bp.route('/visits', methods=['GET'])
def list_visits():
    return read(lambda: svc.get_visits(g.db, request.args.get('status', ''), request.args.get('type', ''),
                                       _int_arg('patient_id')), 'Visits retrieved')


@api_bp.route('/visits/<int:visit_id>/summary', methods=['GET'])
def visit_summary(visit_id):
    return read(lambda: svc.get_visit_summary(g.db, visit_id), 'Visit summary retrieved')


@api_bp.route('/appointments', methods=['POST'])
def book():
    data = body()
    return run('book_appointment',
               lambda: svc.book_appointment(g.db, data.get('patient_id'), data.get('doctor_id'),
                                            data.get('slot'), data.get('complaint')),
               lambda r: f"Appointment booked. Visit ID {r['visit_id']}",
               component('book_appointment', 'procedure', 'PROCEDURE book_appointment'))


@api_bp.route('/visits/<int:visit_id>/cancel', methods=['POST'])
def cancel(visit_id):
    return run('cancel_appointment', lambda: svc.cancel_appointment(g.db, visit_id),
               f'Appointment cancelled. Visit ID {visit_id}',
               component('cancel_appointment', 'procedure', 'PROCEDURE cancel_appointment'))


@api_bp.route('/visits/<int:visit_id>/start-treatment', methods=['POST'])
def start_treatment(visit_id):
    return run('start_treatment', lambda: svc.start_treatment(g.db, visit_id),
               lambda r: f"Treatment started. Visit ID {visit_id}, status: {r['visit_status']}",
               component('start_treatment', 'procedure', 'PROCEDURE start_treatment'))


@api_bp.route('/emergency', methods=['POST'])
def emergency():
    data = body()
    return run('register_emergency',
               lambda: svc.register_emergency(g.db, data.get('patient_id'), data.get('complaint'),
                                              data.get('triage_level'), data.get('arrival')),
               lambda r: (f"Emergency registered. Visit ID {r['visit_id']}, "
                          f"Doctor: {r['doctor_name']} ({r['doctor_id']})"),
               component('register_emergency', 'procedure', 'PROCEDURE register_emergency'),
               functions=[{'name': 'fn_triage_label', 'purpose': 'label of the triage level'}])


@api_bp.route('/emergency/queue', methods=['GET'])
def emergency_queue():
    return run('emergency_queue', lambda: svc.emergency_queue(g.db), 'Emergency queue retrieved',
               component('emergency_queue', 'cursor', 'CURSOR over waiting emergencies'),
               functions=[{'name': 'fn_triage_label', 'purpose': 'label of the triage level'}])


@api_bp.route('/visits/<int:visit_id>/allot-bed', methods=['POST'])
def allot_bed(visit_id):
    data = body()
    return run('allot_bed', lambda: svc.allot_bed(g.db, visit_id, data.get('ward_type')),
               lambda r: f"Bed allotted. Bed ID {r['bed_id']}",
               component('allot_bed', 'procedure', 'PROCEDURE allot_bed'))


@api_bp.route('/visits/<int:visit_id>/discharge', methods=['POST'])
def discharge(visit_id):
    return run('discharge_patient', lambda: svc.discharge_patient(g.db, visit_id),
               lambda r: (f"Patient discharged. Visit ID {visit_id}, Bed ID {r['bed_id']}, "
                          f"Days stayed: {r['days_stayed']}"),
               component('discharge_patient', 'procedure', 'PROCEDURE discharge_patient'),
               functions=[{'name': 'fn_days_stayed', 'purpose': 'whole days between admit and discharge'}])


# --------------------------------------------------------------------------- pharmacy

@api_bp.route('/visits/<int:visit_id>/prescriptions', methods=['GET'])
def list_prescriptions(visit_id):
    return read(lambda: svc.get_prescriptions(g.db, visit_id), 'Prescriptions retrieved')


@api_bp.route('/prescriptions', methods=['POST'])
def add_prescription():
    data = body()
    return run('add_prescription',
               lambda: svc.add_prescription(g.db, data.get('visit_id'), data.get('medicine_id'),
                                            data.get('dosage'), data.get('duration_days'), data.get('quantity')),
               lambda r: (f"Prescription added. Prescription ID {r['prescription_id']}, "
                          f"stock after: {r['stock_after']}"),
               component('trg_reduce_stock', 'trigger', 'TRIGGER trg_reduce_stock'))


@api_bp.route('/prescriptions/<int:prescription_id>', methods=['DELETE'])
def delete_prescription(prescription_id):
    return run('delete_prescription', lambda: svc.delete_prescription(g.db, prescription_id),
               lambda r: f"Prescription deleted. Prescription ID {prescription_id}, stock after: {r['stock_after']}",
               component('trg_reduce_stock', 'trigger', 'TRIGGER trg_reduce_stock'))


# --------------------------------------------------------------------------- billing

@api_bp.route('/visits/<int:visit_id>/bill', methods=['POST'])
def generate_bill(visit_id):
    return run('generate_bill', lambda: svc.generate_bill(g.db, visit_id),
               lambda r: (f"Bill generated. Bill ID {r['bill_id']}: consultation {r['consultation_charge']} + "
                          f"medicine {r['medicine_charge']} + bed {r['bed_charge']} = {r['total_amount']}, Pending"),
               component('generate_bill', 'procedure', 'PROCEDURE generate_bill'),
               functions=[{'name': 'fn_medicine_cost', 'purpose': 'sum of quantity x price of the visit'},
                          {'name': 'fn_days_stayed', 'purpose': 'days stayed in bed'}])


@api_bp.route('/bills', methods=['GET'])
def list_bills():
    return read(lambda: svc.get_bills(g.db, request.args.get('status', '')), 'Bills retrieved')


@api_bp.route('/bills/pending', methods=['GET'])
def pending_bills():
    return run('pending_bills', lambda: svc.get_pending_bills(g.db, _float_arg('min_amount', 0)),
               'Pending bills retrieved',
               component('pending_bills', 'cursor', 'CURSOR over pending bills'))


@api_bp.route('/bills/<int:bill_id>/pay', methods=['POST'])
def pay_bill(bill_id):
    data = body()
    return run('pay_bill', lambda: svc.pay_bill(g.db, bill_id, data.get('payment_mode')),
               lambda r: f"Bill paid. Bill ID {bill_id}, status: {r['payment_status']}",
               component('pay_bill', 'procedure', 'PROCEDURE pay_bill'))


# --------------------------------------------------------------------------- reports / audit

@api_bp.route('/reports', methods=['GET'])
def reports():
    return read(lambda: get_reports_catalogue(g.db), 'Reports catalogue retrieved')


@api_bp.route('/reports/<report_id>', methods=['GET'])
def report(report_id):
    return read(lambda: get_report(g.db, report_id, request.args.get('param')), 'Report executed')


@api_bp.route('/audit', methods=['GET'])
def audit():
    def _audit():
        query, params = 'SELECT * FROM audit_log WHERE 1=1', []
        if request.args.get('table'):
            query += ' AND table_name = ?'
            params.append(request.args['table'].upper())
        if request.args.get('action'):
            query += ' AND action_type = ?'
            params.append(request.args['action'].upper())
        query += ' ORDER BY log_id DESC LIMIT ?'
        params.append(clamp_limit(request.args.get('limit'), 100, 1000))
        return [dict(r) for r in g.db.execute(query, params).fetchall()]
    return read(_audit, 'Audit log retrieved')


@api_bp.route('/audit/tamper-test', methods=['POST'])
def tamper_test():
    data = body()
    mode = data.get('mode', 'update')
    if mode not in ('update', 'delete'):
        return fail('mode must be "update" or "delete"', 'validation', 'VALIDATION_ERROR')

    def _tamper():
        g.db.execute('BEGIN')
        try:
            if mode == 'update':
                g.db.execute("UPDATE audit_log SET description = 'tampered' WHERE log_id = 1")
            else:
                g.db.execute('DELETE FROM audit_log WHERE log_id = 1')
            blocked, error = False, None
        except sqlite3.Error as e:
            blocked, error = True, str(e)
        finally:
            if g.db.in_transaction:
                g.db.execute('ROLLBACK')       # whatever happened, nothing is kept
        return {'blocked': blocked, 'error': error}
    return run('audit_tamper_test', _tamper,
               lambda r: 'Tamper attempt blocked by trg_protect_audit' if r['blocked']
               else 'Tamper attempt was NOT blocked (rolled back by the test)',
               component('trg_protect_audit', 'trigger', 'TRIGGER trg_protect_audit'))


# --------------------------------------------------------------------------- transaction demonstration logic



