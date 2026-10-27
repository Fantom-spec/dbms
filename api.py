"""
Real API blueprint: thin handlers that call services / queries / introspect / demo.

* One database connection per request (``g.db``), closed in teardown.
* Role simulation: the ``X-Role`` header selects a username which is written to
  ``app_session`` at the start of every request (the audit triggers read it).
  This is NOT authentication - see docs/SECURITY.md.
* Every response is the contract envelope ``{ok, message, data, error, inspector}``.
* State-changing requests must carry ``X-Requested-With: HospitalApp`` (CSRF defence).
"""
import sqlite3

from flask import Blueprint, Response, current_app, g, jsonify, request

import config
import services as svc
from db.connection import get_connection
from demo import get_demo_state, get_demo_steps, reset_demo, run_demo_step
from errors import BusinessRuleError, error_payload, map_sqlite_error
from inspector import Capture, build_inspector
from introspect import (
    execute_sql, get_constraints, get_ddl, get_er, get_functions, get_indexes,
    get_relationships, get_schema_overview, get_table, get_tables, get_triggers,
    get_violations, run_trigger_demo, run_violation,
)
from queries import get_report, get_reports_catalogue
from validation import clamp_limit

api_bp = Blueprint('api', __name__)

ROLES = list(config.ROLE_USERNAMES)
SAFE_METHODS = ('GET', 'HEAD', 'OPTIONS')


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

@api_bp.before_request
def open_connection():
    if request.method not in SAFE_METHODS:
        if request.headers.get(config.CSRF_HEADER) != config.CSRF_VALUE:
            return fail('Missing X-Requested-With header (CSRF protection)', 'validation',
                        'CSRF_REQUIRED', status=403)
    role = request.headers.get('X-Role') or config.DEFAULT_ROLE
    if role not in config.ROLE_USERNAMES:
        return fail(f'Unknown role: {role[:40]!r}', 'validation', 'INVALID_ROLE',
                    f'Role must be one of: {", ".join(ROLES)}', status=400)
    g.db = get_connection(current_app.config['DB_PATH'])
    g.role = role
    g.username = config.ROLE_USERNAMES[role]
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
    data = body()
    role = data.get('role')
    if role not in config.ROLE_USERNAMES:
        return fail('Invalid role', 'validation', 'INVALID_ROLE', f'Role must be one of: {", ".join(ROLES)}')
    username = config.ROLE_USERNAMES[role]
    g.db.execute('UPDATE app_session SET username = ? WHERE id = 1', (username,))
    return envelope(True, f'Role switched to {role}', {'role': role, 'username': username})


@api_bp.route('/reset', methods=['POST'])
def reset():
    data = body()
    if data.get('confirm') is not True:
        return fail('Reset needs confirmation: send {"confirm": true}', 'validation', 'CONFIRM_REQUIRED')
    g.db.close()
    try:
        info = reset_demo(current_app.config['DB_PATH'])
    finally:
        g.db = get_connection(current_app.config['DB_PATH'])
        g.db.execute('UPDATE app_session SET username = ? WHERE id = 1', (g.username,))
    return envelope(True, 'Database restored to the seeded demo state', {'counts': info['counts']})


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


# --------------------------------------------------------------------------- schema explorer

def _schema(name, fn, message):
    @api_bp.route(f'/schema/{name}', methods=['GET'], endpoint=f'schema_{name}')
    def _view():
        return read(lambda: fn(g.db), message)


_schema('overview', get_schema_overview, 'Schema overview retrieved')
_schema('tables', get_tables, 'Tables retrieved')
_schema('relationships', get_relationships, 'Relationships retrieved')
_schema('constraints', get_constraints, 'Constraints retrieved')
_schema('indexes', get_indexes, 'Indexes retrieved')
_schema('triggers', get_triggers, 'Triggers retrieved')
_schema('functions', get_functions, 'Functions retrieved')
_schema('er', get_er, 'ER diagram retrieved')
_schema('violations', get_violations, 'Violation tests retrieved')


@api_bp.route('/schema/tables/<table_name>', methods=['GET'])
def schema_table(table_name):
    preview = max(1, min(_int_arg('preview', 10), 100))
    return read(lambda: get_table(g.db, table_name, preview), 'Table retrieved')


@api_bp.route('/schema/ddl', methods=['GET'])
def schema_ddl():
    if request.args.get('download') in ('1', 'true'):
        return Response(get_ddl(g.db)['ddl'], mimetype='text/plain',
                        headers={'Content-Disposition': 'attachment; filename=schema.sql'})
    return read(lambda: get_ddl(g.db), 'DDL retrieved')


@api_bp.route('/schema/violations/<violation_id>/run', methods=['POST'])
def violation_run(violation_id):
    return run(f'violation_{violation_id}', lambda: run_violation(g.db, violation_id),
               lambda r: 'Blocked by the database' if r['blocked'] else 'NOT blocked (rolled back by the test)',
               component(f'violation_{violation_id}', 'constraint', 'constraint violation test'))


@api_bp.route('/schema/triggers/<logical_name>/demo', methods=['POST'])
def trigger_demo(logical_name):
    return run(f'trigger_demo_{logical_name}', lambda: run_trigger_demo(g.db, logical_name),
               'Trigger demo executed (rolled back)',
               component(logical_name, 'trigger', f'TRIGGER {logical_name}'))


@api_bp.route('/sql', methods=['POST'])
def sql_console():
    data = body()
    return read(lambda: execute_sql(current_app.config['DB_PATH'], data.get('sql')), 'SQL query executed')


# --------------------------------------------------------------------------- guided demo

@api_bp.route('/demo/steps', methods=['GET'])
def demo_steps():
    return read(lambda: get_demo_steps(g.db)['data'], 'Demo steps retrieved')


@api_bp.route('/demo/state', methods=['GET'])
def demo_state():
    return read(lambda: get_demo_state(g.db)['data'], 'Demo state retrieved')


@api_bp.route('/demo/<step_id>/run', methods=['POST'])
def demo_run(step_id):
    # Each guided-demo step runs as the role the script assigns to it (audit_log.changed_by).
    from demo import DEMO_STEPS
    step = next((st for t in DEMO_STEPS for st in t['steps'] if st['id'] == step_id), None)
    if step and step.get('role') in config.ROLE_USERNAMES:
        g.role, g.username = step['role'], config.ROLE_USERNAMES[step['role']]
        g.db.execute('UPDATE app_session SET username = ? WHERE id = 1', (g.username,))
    return run(f'demo_{step_id}', lambda: run_demo_step(g.db, step_id)['data'],
               lambda r: f"Demo step {step_id} {'passed' if all(c['passed'] for c in r['checks']) else 'FAILED'}",
               component(f'demo_{step_id}', 'procedure', 'guided demo step'))
