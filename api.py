"""
Real API blueprint — thin handlers that call services, queries, introspect, demo.
Each handler sets app_session.username from role at start of request.
"""
from flask import Blueprint, request, jsonify, g, current_app
import sqlite3

api_bp = Blueprint('api', __name__)


# Import services and other modules
from services import (
    register_patient, update_patient, delete_patient, patient_history,
    book_appointment, cancel_appointment, start_treatment,
    register_emergency, emergency_queue,
    add_prescription, delete_prescription, restock_medicine,
    allot_bed, set_bed_status, discharge_patient,
    generate_bill, pay_bill,
    get_patients, get_doctors, create_doctor, update_doctor,
    get_medicines, create_medicine, get_low_stock_medicines,
    get_beds, create_bed,
    get_visits, get_visit_summary,
    get_bills, get_pending_bills,
    get_lookups, get_dashboard,
)
from queries import (
    get_reports, get_report, get_reports_catalogue
)
from introspect import (
    get_schema_overview, get_tables, get_table, get_relationships,
    get_constraints, get_indexes, get_triggers, get_functions,
    get_ddl, get_er, get_violations, run_violation, run_trigger_demo,
    execute_sql
)
from demo import get_demo_steps, get_demo_state, run_demo_step, reset_demo
from inspector import build_inspector
from errors import BusinessRuleError, make_error_envelope, map_sqlite_error


@api_bp.before_request
def set_role():
    """Set app_session.username from role header or default to ADMIN."""
    # Skip in stub mode - no database connection
    if current_app.config.get('FLASK_API_MODE') == 'stub':
        return
    
    role = request.headers.get('X-Role', 'Admin')
    role_map = {
        'Admin': 'ADMIN',
        'Receptionist': 'RECEPTION1',
        'Triage Nurse': 'TRIAGE_NURSE',
        'Doctor': 'DR_AMENON',
        'Billing': 'BILLING1',
    }
    username = role_map.get(role, 'ADMIN')
    g.db.execute("UPDATE app_session SET username = ? WHERE id = 1", (username,))
    g.current_role = role
    g.current_username = username


def _envelope(ok, message, data=None, error=None, inspector=None):
    """Build the standard API envelope."""
    return jsonify({
        'ok': ok,
        'message': message,
        'data': data,
        'error': error,
        'inspector': inspector
    })


def _handle_error(e, operation: str = "Operation"):
    """Convert exception to error envelope with inspector."""
    if isinstance(e, BusinessRuleError):
        return _envelope(
            False,
            e.message,
            error={'kind': 'business_rule', 'code': e.code, 'constraint': None, 'detail': str(e)},
            inspector=build_inspector(g.db, operation, error=e)
        ), 200
    elif isinstance(e, sqlite3.IntegrityError):
        code, msg = map_sqlite_error(e)
        return _envelope(
            False,
            msg,
            error={'kind': 'constraint', 'code': code, 'constraint': code, 'detail': str(e)},
            inspector=build_inspector(g.db, operation, error=e)
        ), 200
    else:
        current_app.logger.exception(f"API error in {operation}")
        return _envelope(
            False,
            "Internal server error",
            error={'kind': 'internal', 'code': 'INTERNAL_ERROR', 'constraint': None, 'detail': str(e)},
            inspector=build_inspector(g.db, operation, error=e)
        ), 500


# ===== Session and Meta =====

@api_bp.route('/meta', methods=['GET'])
def meta():
    try:
        data = get_dashboard(g.db)
        return _envelope(True, "Dashboard data retrieved", data)
    except Exception as e:
        return _handle_error(e, "meta")


@api_bp.route('/role', methods=['POST'])
def set_role_endpoint():
    try:
        data = request.get_json() or {}
        role = data.get('role')
        if role not in ['Admin', 'Receptionist', 'Triage Nurse', 'Doctor', 'Billing']:
            return _envelope(False, "Invalid role", error={
                'kind': 'validation', 'code': 'INVALID_ROLE', 'constraint': None, 'detail': 'Role must be one of: Admin, Receptionist, Triage Nurse, Doctor, Billing'
            }), 200
        
        role_map = {
            'Admin': 'ADMIN',
            'Receptionist': 'RECEPTION1',
            'Triage Nurse': 'TRIAGE_NURSE',
            'Doctor': 'DR_AMENON',
            'Billing': 'BILLING1',
        }
        username = role_map[role]
        g.db.execute("UPDATE app_session SET username = ? WHERE id = 1", (username,))
        return _envelope(True, f"Role switched to {role}", {'role': role, 'username': username})
    except Exception as e:
        return _handle_error(e, "set_role")


@api_bp.route('/reset', methods=['POST'])
def reset():
    try:
        return reset_demo(g.db)
    except Exception as e:
        return _handle_error(e, "reset")


@api_bp.route('/lookups', methods=['GET'])
def lookups():
    try:
        data = get_lookups(g.db)
        return _envelope(True, "Lookups retrieved", data)
    except Exception as e:
        return _handle_error(e, "lookups")


@api_bp.route('/dashboard', methods=['GET'])
def dashboard():
    try:
        data = get_dashboard(g.db)
        return _envelope(True, "Dashboard data retrieved", data)
    except Exception as e:
        return _handle_error(e, "dashboard")


# ===== Patients =====

@api_bp.route('/patients', methods=['GET'])
def list_patients():
    try:
        q = request.args.get('q', '')
        data = get_patients(g.db, q)
        return _envelope(True, "Patients retrieved", data)
    except Exception as e:
        return _handle_error(e, "list_patients")


@api_bp.route('/patients', methods=['POST'])
def create_patient():
    try:
        data = request.get_json() or {}
        result = register_patient(g.db, data)
        return _envelope(True, f"Patient registered. Patient ID {result['patient_id']}", result,
                        inspector=build_inspector(g.db, "register_patient"))
    except Exception as e:
        return _handle_error(e, "create_patient")


@api_bp.route('/patients/<int:patient_id>', methods=['PUT'])
def update_patient_endpoint(patient_id):
    try:
        data = request.get_json() or {}
        result = update_patient(g.db, patient_id, data)
        return _envelope(True, f"Patient updated. Patient ID {patient_id}", result,
                        inspector=build_inspector(g.db, "update_patient"))
    except Exception as e:
        return _handle_error(e, "update_patient")


@api_bp.route('/patients/<int:patient_id>', methods=['DELETE'])
def delete_patient_endpoint(patient_id):
    try:
        result = delete_patient(g.db, patient_id)
        return _envelope(True, f"Patient deleted. Patient ID {patient_id}", result,
                        inspector=build_inspector(g.db, "delete_patient"))
    except Exception as e:
        return _handle_error(e, "delete_patient")


@api_bp.route('/patients/<int:patient_id>/history', methods=['GET'])
def patient_history_endpoint(patient_id):
    try:
        data = patient_history(g.db, patient_id)
        return _envelope(True, "Patient history retrieved", data)
    except Exception as e:
        return _handle_error(e, "patient_history")


# ===== Doctors =====

@api_bp.route('/doctors', methods=['GET'])
def list_doctors():
    try:
        data = get_doctors(g.db)
        return _envelope(True, "Doctors retrieved", data)
    except Exception as e:
        return _handle_error(e, "list_doctors")


@api_bp.route('/doctors', methods=['POST'])
def create_doctor():
    try:
        data = request.get_json() or {}
        result = create_doctor(g.db, data)
        return _envelope(True, f"Doctor created. Doctor ID {result['doctor_id']}", result,
                        inspector=build_inspector(g.db, "create_doctor"))
    except Exception as e:
        return _handle_error(e, "create_doctor")


@api_bp.route('/doctors/<int:doctor_id>', methods=['PUT'])
def update_doctor_endpoint(doctor_id):
    try:
        data = request.get_json() or {}
        result = update_doctor(g.db, doctor_id, data)
        return _envelope(True, f"Doctor updated. Doctor ID {doctor_id}", result,
                        inspector=build_inspector(g.db, "update_doctor"))
    except Exception as e:
        return _handle_error(e, "update_doctor")


# ===== Medicines =====

@api_bp.route('/medicines', methods=['GET'])
def list_medicines():
    try:
        data = get_medicines(g.db)
        return _envelope(True, "Medicines retrieved", data)
    except Exception as e:
        return _handle_error(e, "list_medicines")


@api_bp.route('/medicines', methods=['POST'])
def create_medicine():
    try:
        data = request.get_json() or {}
        result = create_medicine(g.db, data)
        return _envelope(True, f"Medicine created. Medicine ID {result['medicine_id']}", result,
                        inspector=build_inspector(g.db, "create_medicine"))
    except Exception as e:
        return _handle_error(e, "create_medicine")


@api_bp.route('/medicines/<int:medicine_id>/restock', methods=['POST'])
def restock_medicine_endpoint(medicine_id):
    try:
        data = request.get_json() or {}
        quantity = data.get('quantity')
        if quantity is None:
            return _envelope(False, "Missing quantity", error={
                'kind': 'validation', 'code': 'MISSING_QUANTITY', 'constraint': None, 'detail': 'quantity is required'
            }), 200
        result = restock_medicine(g.db, medicine_id, quantity)
        return _envelope(True, f"Medicine restocked. Medicine ID {medicine_id}, new stock: {result['stock_quantity']}", result,
                        inspector=build_inspector(g.db, "restock_medicine"))
    except Exception as e:
        return _handle_error(e, "restock_medicine")


@api_bp.route('/medicines/low-stock', methods=['GET'])
def low_stock_medicines():
    try:
        threshold = request.args.get('threshold', 20, type=int)
        data = get_low_stock_medicines(g.db, threshold)
        return _envelope(True, "Low stock medicines retrieved", data)
    except Exception as e:
        return _handle_error(e, "low_stock_medicines")


# ===== Beds =====

@api_bp.route('/beds', methods=['GET'])
def list_beds():
    try:
        data = get_beds(g.db)
        return _envelope(True, "Beds retrieved", data)
    except Exception as e:
        return _handle_error(e, "list_beds")


@api_bp.route('/beds', methods=['POST'])
def create_bed():
    try:
        data = request.get_json() or {}
        ward_type = data.get('ward_type')
        daily_charge = data.get('daily_charge')
        if not ward_type or daily_charge is None:
            return _envelope(False, "Missing ward_type or daily_charge", error={
                'kind': 'validation', 'code': 'MISSING_FIELDS', 'constraint': None, 'detail': 'ward_type and daily_charge are required'
            }), 200
        result = create_bed(g.db, ward_type, daily_charge)
        return _envelope(True, f"Bed created. Bed ID {result['bed_id']}", result,
                        inspector=build_inspector(g.db, "create_bed"))
    except Exception as e:
        return _handle_error(e, "create_bed")


@api_bp.route('/beds/<int:bed_id>/status', methods=['POST'])
def set_bed_status_endpoint(bed_id):
    try:
        data = request.get_json() or {}
        status = data.get('status')
        if not status:
            return _envelope(False, "Missing status", error={
                'kind': 'validation', 'code': 'MISSING_STATUS', 'constraint': None, 'detail': 'status is required'
            }), 200
        result = set_bed_status(g.db, bed_id, status)
        return _envelope(True, f"Bed status updated. Bed ID {bed_id}, status: {result['bed_status']}", result,
                        inspector=build_inspector(g.db, "set_bed_status"))
    except Exception as e:
        return _handle_error(e, "set_bed_status")


# ===== Visits =====

@api_bp.route('/visits', methods=['GET'])
def list_visits():
    try:
        status = request.args.get('status', '')
        type = request.args.get('type', '')
        patient_id = request.args.get('patient_id', type=int)
        data = get_visits(g.db, status, type, patient_id)
        return _envelope(True, "Visits retrieved", data)
    except Exception as e:
        return _handle_error(e, "list_visits")


@api_bp.route('/visits/<int:visit_id>/summary', methods=['GET'])
def visit_summary(visit_id):
    try:
        data = get_visit_summary(g.db, visit_id)
        return _envelope(True, "Visit summary retrieved", data)
    except Exception as e:
        return _handle_error(e, "visit_summary")


@api_bp.route('/appointments', methods=['POST'])
def create_appointment():
    try:
        data = request.get_json() or {}
        required = ['patient_id', 'doctor_id', 'slot', 'complaint']
        for field in required:
            if not data.get(field):
                return _envelope(False, f"Missing required field: {field}", error={
                    'kind': 'validation', 'code': 'MISSING_FIELD', 'constraint': None, 'detail': f'{field} is required'
                }), 200
        result = book_appointment(g.db, data['patient_id'], data['doctor_id'], data['slot'], data['complaint'])
        return _envelope(True, f"Appointment booked. Visit ID {result['visit_id']}", result,
                        inspector=build_inspector(g.db, "book_appointment"))
    except Exception as e:
        return _handle_error(e, "create_appointment")


@api_bp.route('/visits/<int:visit_id>/cancel', methods=['POST'])
def cancel_appointment_endpoint(visit_id):
    try:
        result = cancel_appointment(g.db, visit_id)
        return _envelope(True, f"Appointment cancelled. Visit ID {visit_id}", result,
                        inspector=build_inspector(g.db, "cancel_appointment"))
    except Exception as e:
        return _handle_error(e, "cancel_appointment")


@api_bp.route('/visits/<int:visit_id>/start-treatment', methods=['POST'])
def start_treatment_endpoint(visit_id):
    try:
        result = start_treatment(g.db, visit_id)
        return _envelope(True, f"Treatment started. Visit ID {visit_id}, status: {result['visit_status']}", result,
                        inspector=build_inspector(g.db, "start_treatment"))
    except Exception as e:
        return _handle_error(e, "start_treatment")


# ===== Emergency =====

@api_bp.route('/emergency', methods=['POST'])
def create_emergency():
    try:
        data = request.get_json() or {}
        required = ['patient_id', 'complaint', 'triage_level']
        for field in required:
            if data.get(field) is None:
                return _envelope(False, f"Missing required field: {field}", error={
                    'kind': 'validation', 'code': 'MISSING_FIELD', 'constraint': None, 'detail': f'{field} is required'
                }), 200
        arrival = data.get('arrival')
        result = register_emergency(g.db, data['patient_id'], data['complaint'], data['triage_level'], arrival)
        return _envelope(True, f"Emergency registered. Visit ID {result['visit_id']}, Doctor: {result['doctor_name']} ({result['doctor_id']})", result,
                        inspector=build_inspector(g.db, "register_emergency"))
    except Exception as e:
        return _handle_error(e, "create_emergency")


@api_bp.route('/emergency/queue', methods=['GET'])
def emergency_queue():
    try:
        data = emergency_queue(g.db)
        return _envelope(True, "Emergency queue retrieved", data,
                        inspector=build_inspector(g.db, "emergency_queue", operation_type="cursor"))
    except Exception as e:
        return _handle_error(e, "emergency_queue")


# ===== Bed Allotment =====

@api_bp.route('/visits/<int:visit_id>/allot-bed', methods=['POST'])
def allot_bed_endpoint(visit_id):
    try:
        data = request.get_json() or {}
        ward_type = data.get('ward_type')
        if not ward_type:
            return _envelope(False, "Missing ward_type", error={
                'kind': 'validation', 'code': 'MISSING_WARD_TYPE', 'constraint': None, 'detail': 'ward_type is required'
            }), 200
        result = allot_bed(g.db, visit_id, ward_type)
        return _envelope(True, f"ICU bed allotted. Bed ID {result['bed_id']}", result,
                        inspector=build_inspector(g.db, "allot_bed"))
    except Exception as e:
        return _handle_error(e, "allot_bed")


@api_bp.route('/visits/<int:visit_id>/discharge', methods=['POST'])
def discharge_patient_endpoint(visit_id):
    try:
        result = discharge_patient(g.db, visit_id)
        return _envelope(True, f"Patient discharged. Visit ID {visit_id}, Bed ID {result['bed_id']}, Days stayed: {result['days_stayed']}", result,
                        inspector=build_inspector(g.db, "discharge_patient"))
    except Exception as e:
        return _handle_error(e, "discharge_patient")


# ===== Pharmacy =====

@api_bp.route('/visits/<int:visit_id>/prescriptions', methods=['GET'])
def list_prescriptions(visit_id):
    try:
        data = get_prescriptions(g.db, visit_id)
        return _envelope(True, "Prescriptions retrieved", data)
    except Exception as e:
        return _handle_error(e, "list_prescriptions")


@api_bp.route('/prescriptions', methods=['POST'])
def add_prescription_endpoint():
    try:
        data = request.get_json() or {}
        required = ['visit_id', 'medicine_id', 'dosage', 'duration_days', 'quantity']
        for field in required:
            if data.get(field) is None:
                return _envelope(False, f"Missing required field: {field}", error={
                    'kind': 'validation', 'code': 'MISSING_FIELD', 'constraint': None, 'detail': f'{field} is required'
                }), 200
        result = add_prescription(g.db, data['visit_id'], data['medicine_id'],
                                 data['dosage'], data['duration_days'], data['quantity'])
        return _envelope(True, f"Prescription added. Prescription ID {result['prescription_id']}, stock after: {result['stock_after']}", result,
                        inspector=build_inspector(g.db, "add_prescription"))
    except Exception as e:
        return _handle_error(e, "add_prescription")


@api_bp.route('/prescriptions/<int:prescription_id>', methods=['DELETE'])
def delete_prescription_endpoint(prescription_id):
    try:
        result = delete_prescription(g.db, prescription_id)
        return _envelope(True, f"Prescription deleted. Prescription ID {prescription_id}, stock after: {result['stock_after']}", result,
                        inspector=build_inspector(g.db, "delete_prescription"))
    except Exception as e:
        return _handle_error(e, "delete_prescription")


# ===== Billing =====

@api_bp.route('/visits/<int:visit_id>/bill', methods=['POST'])
def generate_bill_endpoint(visit_id):
    try:
        result = generate_bill(g.db, visit_id)
        return _envelope(True, f"Bill generated. Bill ID {result['bill_id']}: consultation {result['consultation_charge']} + medicine {result['medicine_charge']} + bed {result['bed_charge']} = {result['total_amount']}, Pending", result,
                        inspector=build_inspector(g.db, "generate_bill"))
    except Exception as e:
        return _handle_error(e, "generate_bill")


@api_bp.route('/bills', methods=['GET'])
def list_bills():
    try:
        status = request.args.get('status', '')
        data = get_bills(g.db, status)
        return _envelope(True, "Bills retrieved", data)
    except Exception as e:
        return _handle_error(e, "list_bills")


@api_bp.route('/bills/pending', methods=['GET'])
def pending_bills():
    try:
        min_amount = request.args.get('min_amount', 0, type=float)
        data = get_pending_bills(g.db, min_amount)
        return _envelope(True, "Pending bills retrieved", data,
                        inspector=build_inspector(g.db, "pending_bills", operation_type="cursor"))
    except Exception as e:
        return _handle_error(e, "pending_bills")


@api_bp.route('/bills/<int:bill_id>/pay', methods=['POST'])
def pay_bill_endpoint(bill_id):
    try:
        data = request.get_json() or {}
        payment_mode = data.get('payment_mode')
        if not payment_mode:
            return _envelope(False, "Missing payment_mode", error={
                'kind': 'validation', 'code': 'MISSING_PAYMENT_MODE', 'constraint': None, 'detail': 'payment_mode is required'
            }), 200
        result = pay_bill(g.db, bill_id, payment_mode)
        return _envelope(True, f"Bill paid. Bill ID {bill_id}, status: {result['payment_status']}", result,
                        inspector=build_inspector(g.db, "pay_bill"))
    except Exception as e:
        return _handle_error(e, "pay_bill")


# ===== Reports =====

@api_bp.route('/reports', methods=['GET'])
def reports_catalogue():
    try:
        data = get_reports_catalogue(g.db)
        return _envelope(True, "Reports catalogue retrieved", data)
    except Exception as e:
        return _handle_error(e, "reports_catalogue")


@api_bp.route('/reports/<report_id>', methods=['GET'])
def get_report_endpoint(report_id):
    try:
        param = request.args.get('param')
        data = get_report(g.db, report_id, param)
        return _envelope(True, "Report executed", data)
    except Exception as e:
        return _handle_error(e, "get_report")


# ===== Audit =====

@api_bp.route('/audit', methods=['GET'])
def audit_log():
    try:
        table = request.args.get('table')
        action = request.args.get('action')
        limit = request.args.get('limit', 100, type=int)
        
        query = "SELECT * FROM audit_log WHERE 1=1"
        params = []
        if table:
            query += " AND table_name = ?"
            params.append(table.upper())
        if action:
            query += " AND action_type = ?"
            params.append(action.upper())
        query += " ORDER BY log_id DESC LIMIT ?"
        params.append(limit)
        
        rows = g.db.execute(query, params).fetchall()
        return _envelope(True, "Audit log retrieved", [dict(r) for r in rows])
    except Exception as e:
        return _handle_error(e, "audit_log")


@api_bp.route('/audit/tamper-test', methods=['POST'])
def audit_tamper_test():
    try:
        data = request.get_json() or {}
        mode = data.get('mode', 'update')
        
        g.db.execute('BEGIN')
        try:
            if mode == 'update':
                g.db.execute("UPDATE audit_log SET description = 'tampered' WHERE log_id = 1")
            else:
                g.db.execute("DELETE FROM audit_log WHERE log_id = 1")
            g.db.execute('COMMIT')
            blocked = False
            error = None
        except sqlite3.IntegrityError as e:
            g.db.execute('ROLLBACK')
            blocked = True
            error = str(e)
        
        return _envelope(True, "Tamper test executed", {'blocked': blocked, 'error': error},
                        inspector=build_inspector(g.db, "audit_tamper_test"))
    except Exception as e:
        return _handle_error(e, "audit_tamper_test")


# ===== Schema =====

@api_bp.route('/schema/overview', methods=['GET'])
def schema_overview():
    try:
        data = get_schema_overview(g.db)
        return _envelope(True, "Schema overview retrieved", data)
    except Exception as e:
        return _handle_error(e, "schema_overview")


@api_bp.route('/schema/tables', methods=['GET'])
def schema_tables():
    try:
        data = get_tables(g.db)
        return _envelope(True, "Schema tables retrieved", data)
    except Exception as e:
        return _handle_error(e, "schema_tables")


@api_bp.route('/schema/tables/<table_name>', methods=['GET'])
def schema_table(table_name):
    try:
        preview = request.args.get('preview', 10, type=int)
        data = get_table(g.db, table_name, preview)
        return _envelope(True, "Table details retrieved", data)
    except Exception as e:
        return _handle_error(e, "schema_table")


@api_bp.route('/schema/relationships', methods=['GET'])
def schema_relationships():
    try:
        data = get_relationships(g.db)
        return _envelope(True, "Schema relationships retrieved", data)
    except Exception as e:
        return _handle_error(e, "schema_relationships")


@api_bp.route('/schema/constraints', methods=['GET'])
def schema_constraints():
    try:
        data = get_constraints(g.db)
        return _envelope(True, "Schema constraints retrieved", data)
    except Exception as e:
        return _handle_error(e, "schema_constraints")


@api_bp.route('/schema/indexes', methods=['GET'])
def schema_indexes():
    try:
        data = get_indexes(g.db)
        return _envelope(True, "Schema indexes retrieved", data)
    except Exception as e:
        return _handle_error(e, "schema_indexes")


@api_bp.route('/schema/triggers', methods=['GET'])
def schema_triggers():
    try:
        data = get_triggers(g.db)
        return _envelope(True, "Schema triggers retrieved", data)
    except Exception as e:
        return _handle_error(e, "schema_triggers")


@api_bp.route('/schema/functions', methods=['GET'])
def schema_functions():
    try:
        data = get_functions(g.db)
        return _envelope(True, "Schema functions retrieved", data)
    except Exception as e:
        return _handle_error(e, "schema_functions")


@api_bp.route('/schema/ddl', methods=['GET'])
def schema_ddl():
    try:
        download = request.args.get('download', 0, type=int)
        data = get_ddl(g.db)
        if download:
            from flask import Response
            return Response(data['ddl'], mimetype='text/plain',
                          headers={'Content-Disposition': 'attachment; filename=schema.sql'})
        return _envelope(True, "DDL retrieved", data)
    except Exception as e:
        return _handle_error(e, "schema_ddl")


@api_bp.route('/schema/er', methods=['GET'])
def schema_er():
    try:
        data = get_er(g.db)
        return _envelope(True, "ER diagram retrieved", data)
    except Exception as e:
        return _handle_error(e, "schema_er")


@api_bp.route('/schema/violations', methods=['GET'])
def schema_violations():
    try:
        data = get_violations(g.db)
        return _envelope(True, "Violation tests retrieved", data)
    except Exception as e:
        return _handle_error(e, "schema_violations")


@api_bp.route('/schema/violations/<violation_id>/run', methods=['POST'])
def run_violation_endpoint(violation_id):
    try:
        data = run_violation(g.db, violation_id)
        return _envelope(True, "Violation test executed", data,
                        inspector=build_inspector(g.db, f"run_violation_{violation_id}"))
    except Exception as e:
        return _handle_error(e, f"run_violation_{violation_id}")


@api_bp.route('/schema/triggers/<logical_name>/demo', methods=['POST'])
def run_trigger_demo_endpoint(logical_name):
    try:
        data = run_trigger_demo(g.db, logical_name)
        return _envelope(True, "Trigger demo executed", data,
                        inspector=build_inspector(g.db, f"trigger_demo_{logical_name}"))
    except Exception as e:
        return _handle_error(e, f"trigger_demo_{logical_name}")


@api_bp.route('/sql', methods=['POST'])
def execute_sql_endpoint():
    try:
        data = request.get_json() or {}
        sql = data.get('sql')
        if not sql:
            return _envelope(False, "Missing SQL", error={
                'kind': 'validation', 'code': 'MISSING_SQL', 'constraint': None, 'detail': 'sql is required'
            }), 200
        result = execute_sql(g.db, sql)
        return _envelope(True, "SQL query executed", result)
    except Exception as e:
        return _handle_error(e, "execute_sql")


# ===== Demo =====

@api_bp.route('/demo/steps', methods=['GET'])
def demo_steps():
    try:
        data = get_demo_steps(g.db)
        return _envelope(True, "Demo steps retrieved", data)
    except Exception as e:
        return _handle_error(e, "demo_steps")


@api_bp.route('/demo/state', methods=['GET'])
def demo_state():
    try:
        data = get_demo_state(g.db)
        return _envelope(True, "Demo state retrieved", data)
    except Exception as e:
        return _handle_error(e, "demo_state")


@api_bp.route('/demo/<step_id>/run', methods=['POST'])
def demo_run_step(step_id):
    try:
        data = run_demo_step(g.db, step_id)
        return _envelope(True, f"Demo step {step_id} executed", data,
                        inspector=build_inspector(g.db, f"demo_{step_id}"))
    except Exception as e:
        return _handle_error(e, f"demo_{step_id}")


# Error handler for the blueprint
@api_bp.errorhandler(Exception)
def handle_error(e):
    current_app.logger.exception("API error")
    return _envelope(
        False,
        "Internal server error",
        error={"kind": "internal", "code": "INTERNAL_ERROR", "constraint": None, "detail": str(e)},
        inspector=None
    ), 500