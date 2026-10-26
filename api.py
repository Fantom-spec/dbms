"""
Real API blueprint — thin handlers that call services, queries, introspect, demo.
Each handler sets app_session.username from role at start of request.
"""
from flask import Blueprint, request, jsonify, g, current_app
import sqlite3

api_bp = Blueprint('api', __name__)


# Import services and other modules (will be implemented in later phases)
# from services import (
#     register_patient, update_patient, delete_patient, patient_history,
#     book_appointment, cancel_appointment, start_treatment,
#     register_emergency, emergency_queue,
#     add_prescription, delete_prescription, restock_medicine,
#     allot_bed, set_bed_status, discharge_patient,
#     generate_bill, pay_bill,
#     get_patients, get_doctors, create_doctor, update_doctor,
#     get_medicines, create_medicine, get_low_stock,
#     get_beds, create_bed,
#     get_visits, get_visit_summary,
#     get_bills, get_pending_bills,
# )
# from queries import get_reports, get_report, get_reports_catalogue
# from introspect import (
#     get_schema_overview, get_tables, get_table, get_relationships,
#     get_constraints, get_indexes, get_triggers, get_functions,
#     get_ddl, get_er, get_violations, run_violation, run_trigger_demo,
#     execute_sql
# )
# from demo import get_demo_steps, get_demo_state, run_demo_step, reset_demo
# from inspector import build_inspector
# from errors import BusinessRuleError, map_error


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


# ===== Session and Meta =====

@api_bp.route('/meta', methods=['GET'])
def meta():
    # TODO: implement
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


@api_bp.route('/role', methods=['POST'])
def set_role_endpoint():
    # TODO: implement
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


@api_bp.route('/reset', methods=['POST'])
def reset():
    # TODO: implement
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


@api_bp.route('/lookups', methods=['GET'])
def lookups():
    # TODO: implement
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


@api_bp.route('/dashboard', methods=['GET'])
def dashboard():
    # TODO: implement
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


# ===== Patients =====

@api_bp.route('/patients', methods=['GET'])
def list_patients():
    # TODO: implement
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


@api_bp.route('/patients', methods=['POST'])
def create_patient():
    # TODO: implement
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


@api_bp.route('/patients/<int:patient_id>', methods=['PUT'])
def update_patient_endpoint(patient_id):
    # TODO: implement
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


@api_bp.route('/patients/<int:patient_id>', methods=['DELETE'])
def delete_patient_endpoint(patient_id):
    # TODO: implement
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


@api_bp.route('/patients/<int:patient_id>/history', methods=['GET'])
def patient_history_endpoint(patient_id):
    # TODO: implement
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


# ===== Doctors =====

@api_bp.route('/doctors', methods=['GET'])
def list_doctors():
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


@api_bp.route('/doctors', methods=['POST'])
def create_doctor():
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


@api_bp.route('/doctors/<int:doctor_id>', methods=['PUT'])
def update_doctor_endpoint(doctor_id):
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


# ===== Medicines =====

@api_bp.route('/medicines', methods=['GET'])
def list_medicines():
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


@api_bp.route('/medicines', methods=['POST'])
def create_medicine():
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


@api_bp.route('/medicines/<int:medicine_id>/restock', methods=['POST'])
def restock_medicine_endpoint(medicine_id):
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


@api_bp.route('/medicines/low-stock', methods=['GET'])
def low_stock_medicines():
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


# ===== Beds =====

@api_bp.route('/beds', methods=['GET'])
def list_beds():
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


@api_bp.route('/beds', methods=['POST'])
def create_bed():
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


@api_bp.route('/beds/<int:bed_id>/status', methods=['POST'])
def set_bed_status_endpoint(bed_id):
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


# ===== Visits =====

@api_bp.route('/visits', methods=['GET'])
def list_visits():
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


@api_bp.route('/visits/<int:visit_id>/summary', methods=['GET'])
def visit_summary(visit_id):
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


@api_bp.route('/appointments', methods=['POST'])
def create_appointment():
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


@api_bp.route('/visits/<int:visit_id>/cancel', methods=['POST'])
def cancel_appointment_endpoint(visit_id):
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


@api_bp.route('/visits/<int:visit_id>/start-treatment', methods=['POST'])
def start_treatment_endpoint(visit_id):
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


@api_bp.route('/emergency', methods=['POST'])
def create_emergency():
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


@api_bp.route('/emergency/queue', methods=['GET'])
def emergency_queue():
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


@api_bp.route('/visits/<int:visit_id>/allot-bed', methods=['POST'])
def allot_bed_endpoint(visit_id):
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


@api_bp.route('/visits/<int:visit_id>/discharge', methods=['POST'])
def discharge_patient_endpoint(visit_id):
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


# ===== Pharmacy =====

@api_bp.route('/visits/<int:visit_id>/prescriptions', methods=['GET'])
def list_prescriptions(visit_id):
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


@api_bp.route('/prescriptions', methods=['POST'])
def add_prescription_endpoint():
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


@api_bp.route('/prescriptions/<int:prescription_id>', methods=['DELETE'])
def delete_prescription_endpoint(prescription_id):
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


# ===== Billing =====

@api_bp.route('/visits/<int:visit_id>/bill', methods=['POST'])
def generate_bill_endpoint(visit_id):
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


@api_bp.route('/bills', methods=['GET'])
def list_bills():
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


@api_bp.route('/bills/pending', methods=['GET'])
def pending_bills():
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


@api_bp.route('/bills/<int:bill_id>/pay', methods=['POST'])
def pay_bill_endpoint(bill_id):
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


# ===== Reports =====

@api_bp.route('/reports', methods=['GET'])
def reports_catalogue():
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


@api_bp.route('/reports/<report_id>', methods=['GET'])
def get_report_endpoint(report_id):
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


# ===== Audit =====

@api_bp.route('/audit', methods=['GET'])
def audit_log():
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


@api_bp.route('/audit/tamper-test', methods=['POST'])
def audit_tamper_test():
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


# ===== Schema =====

@api_bp.route('/schema/overview', methods=['GET'])
def schema_overview():
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


@api_bp.route('/schema/tables', methods=['GET'])
def schema_tables():
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


@api_bp.route('/schema/tables/<table_name>', methods=['GET'])
def schema_table(table_name):
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


@api_bp.route('/schema/relationships', methods=['GET'])
def schema_relationships():
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


@api_bp.route('/schema/constraints', methods=['GET'])
def schema_constraints():
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


@api_bp.route('/schema/indexes', methods=['GET'])
def schema_indexes():
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


@api_bp.route('/schema/triggers', methods=['GET'])
def schema_triggers():
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


@api_bp.route('/schema/functions', methods=['GET'])
def schema_functions():
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


@api_bp.route('/schema/ddl', methods=['GET'])
def schema_ddl():
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


@api_bp.route('/schema/er', methods=['GET'])
def schema_er():
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


@api_bp.route('/schema/violations', methods=['GET'])
def schema_violations():
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


@api_bp.route('/schema/violations/<violation_id>/run', methods=['POST'])
def run_violation_endpoint(violation_id):
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


@api_bp.route('/schema/triggers/<logical_name>/demo', methods=['POST'])
def run_trigger_demo_endpoint(logical_name):
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


@api_bp.route('/sql', methods=['POST'])
def execute_sql_endpoint():
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


# ===== Demo =====

@api_bp.route('/demo/steps', methods=['GET'])
def demo_steps():
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


@api_bp.route('/demo/state', methods=['GET'])
def demo_state():
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


@api_bp.route('/demo/<step_id>/run', methods=['POST'])
def demo_run_step(step_id):
    return _envelope(True, "Not implemented", {"error": "Not implemented in Phase 1"})


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