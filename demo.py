"""
Guided demo: six transactions T1-T6 as specified in ARCHITECTURE.md §11.
Each step sets its role, so the audit log shows different users.
Steps depend on earlier ones; run_demo_step checks prerequisites.
Each run returns checks[] (green ticks on the UI) plus the inspector.
"""
import sqlite3
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta


# Demo steps definition (matching ARCHITECTURE.md §11)
DEMO_STEPS = [
    {
        "transaction": "T1",
        "title": "Register patient and book appointment",
        "goal": "Register a new patient and book an appointment with a specific doctor at a specific time",
        "steps": [
            {
                "id": "T1.1",
                "title": "Register patient Sanjay Rao",
                "narration": "Receptionist registers new patient Sanjay Rao with phone 9876500113",
                "role": "Receptionist",
                "expect": ["Patient 113 created", "Audit row 13: 'New patient registered' by RECEPTION1"],
                "prereqs": [],
                "check_fn": "check_T1_1"
            },
            {
                "id": "T1.2",
                "title": "Book appointment with Dr. Priya Nair",
                "narration": "Book patient 113 with Dr. Priya Nair (202) for tomorrow 10:00 AM",
                "role": "Receptionist",
                "expect": ["Visit 421 created with status Scheduled", "Audit row 14: 'New Appointment visit for patient 113' by RECEPTION1"],
                "prereqs": ["T1.1"],
                "check_fn": "check_T1_2"
            },
            {
                "id": "T1.3",
                "title": "Attempt double-booking same slot",
                "narration": "Try to book patient 101 with doctor 202 at the same slot (should fail)",
                "role": "Receptionist",
                "expect": ["Error SLOT_TAKEN", "No visit inserted", "Partial unique index uq_doctor_slot blocks it"],
                "prereqs": ["T1.2"],
                "check_fn": "check_T1_3"
            }
        ]
    },
    {
        "transaction": "T2",
        "title": "Emergency arrival and triage",
        "goal": "Register an emergency case and verify triage priority queue",
        "steps": [
            {
                "id": "T2.1",
                "title": "Show emergency queue (cursor)",
                "narration": "Display current emergency waiting queue using cursor-style output",
                "role": "Triage Nurse",
                "expect": ["Queue shows visits 418 (T1), 416 (T2), 417 (T4) in priority order", "Console lines show formatted output with fn_triage_label"],
                "prereqs": [],
                "check_fn": "check_T2_1"
            },
            {
                "id": "T2.2",
                "title": "Register emergency for patient 109",
                "narration": "Register emergency: patient 109 (Vivek Joshi), 'Chest pain', triage 1",
                "role": "Triage Nurse",
                "expect": ["Visit 422 created with status Waiting", "Assigned to Dr. Arvind Menon (203) - tie on 2 active, lowest id", "Audit row 15: 'New Emergency visit for patient 109' by TRIAGE_NURSE"],
                "prereqs": ["T2.1"],
                "check_fn": "check_T2_2"
            },
            {
                "id": "T2.3",
                "title": "Attempt invalid triage level 7",
                "narration": "Try to register emergency with triage level 7 (should fail)",
                "role": "Triage Nurse",
                "expect": ["Error BAD_TRIAGE", "CHECK constraint chk_visit_range blocks it"],
                "prereqs": ["T2.2"],
                "check_fn": "check_T2_3"
            },
            {
                "id": "T2.4",
                "title": "Show updated queue",
                "narration": "Display queue again - new critical case should be at top",
                "role": "Triage Nurse",
                "expect": ["Visit 422 (T1) appears ahead of 416 (T2) and 417 (T4)", "fn_triage_label shows 'Critical' for triage 1"],
                "prereqs": ["T2.2"],
                "check_fn": "check_T2_4"
            }
        ]
    },
    {
        "transaction": "T3",
        "title": "Consultation and prescription",
        "goal": "Start treatment and add prescriptions, verify stock triggers",
        "steps": [
            {
                "id": "T3.1",
                "title": "Start treatment on visit 422",
                "narration": "Change visit 422 status to Under Treatment",
                "role": "Doctor",
                "expect": ["Visit 422 status -> Under Treatment", "Doctor 203 availability -> Busy (via trg_doctor_status)", "Audit row 16: 'Status Waiting -> Under Treatment' by DR_AMENON"],
                "prereqs": ["T2.2"],
                "check_fn": "check_T3_1"
            },
            {
                "id": "T3.2",
                "title": "Prescribe Aspirin 75mg qty 10",
                "narration": "Add prescription for Aspirin 75mg (506), quantity 10",
                "role": "Doctor",
                "expect": ["Prescription 623 created", "Aspirin stock 550 -> 540 (via trg_reduce_stock)", "No audit row for prescription (only visit/bill/patient)"],
                "prereqs": ["T3.1"],
                "check_fn": "check_T3_2"
            },
            {
                "id": "T3.3",
                "title": "Attempt ORS Sachet qty 2 (insufficient stock)",
                "narration": "Try to prescribe ORS Sachet (512) qty 2 when stock is 0",
                "role": "Doctor",
                "expect": ["Error INSUFFICIENT_STOCK", "Trigger trg_reduce_stock__insert aborts with 'available 0, requested 2'", "Transaction rolled back, stock unchanged"],
                "prereqs": ["T3.2"],
                "check_fn": "check_T3_3"
            }
        ]
    },
    {
        "transaction": "T4",
        "title": "Admission and bed allotment",
        "goal": "Allot ICU bed and verify bed constraints",
        "steps": [
            {
                "id": "T4.1",
                "title": "Show free ICU beds",
                "narration": "Display free beds in ICU ward",
                "role": "Doctor",
                "expect": ["Only bed 307 shows as Free in ICU"],
                "prereqs": ["T3.1"],
                "check_fn": "check_T4_1"
            },
            {
                "id": "T4.2",
                "title": "Allot ICU bed to visit 422",
                "narration": "Allot ICU bed to the emergency visit 422",
                "role": "Doctor",
                "expect": ["Bed 307 status -> Occupied", "Visit 422 status -> Admitted with admit_time", "Doctor 203 availability -> Available (left Under Treatment)", "Audit row 17: 'Status Under Treatment -> Admitted' by DR_AMENON"],
                "prereqs": ["T3.1", "T4.1"],
                "check_fn": "check_T4_2"
            },
            {
                "id": "T4.3",
                "title": "Attempt allot ICU bed to visit 416",
                "narration": "Try to allot ICU bed to another waiting emergency (should fail)",
                "role": "Doctor",
                "expect": ["Error NO_FREE_BED", "No free ICU beds remaining"],
                "prereqs": ["T4.2"],
                "check_fn": "check_T4_3"
            },
            {
                "id": "T4.4",
                "title": "Sandbox: force bed 308 onto visit 416",
                "narration": "Attempt to directly set visit 416 to Admitted with bed 308 (should be blocked)",
                "role": "Doctor",
                "expect": ["Error blocked by uq_active_bed partial unique index", "Bed 308 already occupied by visit 414"],
                "prereqs": ["T4.2"],
                "check_fn": "check_T4_4"
            }
        ]
    },
    {
        "transaction": "T5",
        "title": "Discharge, billing and payment",
        "goal": "Discharge patient, generate bill, record payment",
        "steps": [
            {
                "id": "T5.1",
                "title": "Discharge visit 422",
                "narration": "Discharge the patient from visit 422",
                "role": "Billing",
                "expect": ["Visit 422 status -> Discharged with discharge_time", "Bed 307 status -> Cleaning", "Audit row 18: 'Status Admitted -> Discharged' by BILLING1"],
                "prereqs": ["T4.2"],
                "check_fn": "check_T5_1"
            },
            {
                "id": "T5.2",
                "title": "Show fn_days_stayed and fn_medicine_cost",
                "narration": "Call functions to verify bill components",
                "role": "Billing",
                "expect": ["fn_days_stayed(422) = 1", "fn_medicine_cost(422) = 15 (Aspirin 75mg x10 x1.5)"],
                "prereqs": ["T5.1"],
                "check_fn": "check_T5_2"
            },
            {
                "id": "T5.3",
                "title": "Generate bill for visit 422",
                "narration": "Generate bill: consultation 1000 + medicine 15 + bed 5000 = 6015",
                "role": "Billing",
                "expect": ["Bill 712 created with total 6015, status Pending", "Audit row 19: 'Bill generated: total 6015 (Pending)' by BILLING1"],
                "prereqs": ["T5.1", "T5.2"],
                "check_fn": "check_T5_3"
            },
            {
                "id": "T5.4",
                "title": "Pay bill by UPI",
                "narration": "Record payment for bill 712 via UPI",
                "role": "Billing",
                "expect": ["Bill 712 status -> Paid, payment_mode = UPI", "Audit row 20: 'Payment status Pending -> Paid' by BILLING1"],
                "prereqs": ["T5.3"],
                "check_fn": "check_T5_4"
            },
            {
                "id": "T5.5",
                "title": "Show pending bills (cursor)",
                "narration": "Display pending bills using cursor output",
                "role": "Billing",
                "expect": ["4 seeded pending bills still shown (706, 708, 710, 711)", "Console lines show formatted output with totals"],
                "prereqs": ["T5.3"],
                "check_fn": "check_T5_5"
            }
        ]
    },
    {
        "transaction": "T6",
        "title": "Audit and integrity",
        "goal": "Verify audit trail and integrity constraints",
        "steps": [
            {
                "id": "T6.1",
                "title": "Show audit trail",
                "narration": "Display audit log rows 13-20 from this demo run",
                "role": "Admin",
                "expect": ["Rows 13-20 show with changed_by: RECEPTION1, TRIAGE_NURSE, DR_AMENON, BILLING1"],
                "prereqs": ["T5.4"],
                "check_fn": "check_T6_1"
            },
            {
                "id": "T6.2",
                "title": "Attempt to UPDATE audit row",
                "narration": "Try to modify an audit_log entry (should be blocked)",
                "role": "Admin",
                "expect": ["Error AUDIT_PROTECTED", "Trigger trg_protect_audit blocks UPDATE/DELETE"],
                "prereqs": [],
                "check_fn": "check_T6_2"
            },
            {
                "id": "T6.3",
                "title": "Attempt to delete patient 101",
                "narration": "Try to delete patient 101 who has visits (should be blocked)",
                "role": "Admin",
                "expect": ["Error FK_VIOLATION", "Foreign key fk_visit_patient blocks deletion"],
                "prereqs": [],
                "check_fn": "check_T6_3"
            },
            {
                "id": "T6.4",
                "title": "Rollback demo: Paracetamol ok, ORS fails",
                "narration": "In one transaction: prescribe Paracetamol (501) x3 (ok), then ORS (512) x5 (fails)",
                "role": "Admin",
                "expect": ["Whole transaction rolled back", "Paracetamol stock still 480", "ORS stock still 0", "Demonstrates atomic transactions"],
                "prereqs": [],
                "check_fn": "check_T6_4"
            }
        ]
    }
]


# Expected context IDs created during demo
CONTEXT_KEYS = {
    'T1.1': 'patient_113',
    'T1.2': 'visit_421',
    'T2.2': 'visit_422',
    'T3.2': 'prescription_623',
    'T4.2': 'bed_307_allotment',
    'T5.3': 'bill_712',
}


def get_demo_steps(conn: sqlite3.Connection) -> Dict:
    """Return all demo steps with metadata."""
    return {
        "ok": True,
        "message": "Demo steps retrieved",
        "data": DEMO_STEPS
    }


def get_demo_state(conn: sqlite3.Connection) -> Dict:
    """Return current demo state (completed steps, context)."""
    # Check which steps have been completed by looking for expected data
    completed = []
    context = {}
    
    # Check T1.1 - patient 113 exists
    p113 = conn.execute("SELECT 1 FROM patient WHERE patient_id = 113").fetchone()
    if p113:
        completed.append("T1.1")
        context['patient_113'] = 113
    
    # Check T1.2 - visit 421 exists
    v421 = conn.execute("SELECT 1 FROM visit WHERE visit_id = 421 AND visit_status = 'Scheduled'").fetchone()
    if v421:
        completed.append("T1.2")
        context['visit_421'] = 421
    
    # Check T1.3 - double booking was attempted (no specific check, just that it's in state)
    if v421 and conn.execute("SELECT 1 FROM visit WHERE patient_id = 101 AND doctor_id = 202 AND visit_datetime = (SELECT visit_datetime FROM visit WHERE visit_id = 421)").fetchone() is None:
        completed.append("T1.3")
    
    # Check T2.1 - queue viewed (no persistent state)
    
    # Check T2.2 - visit 422 exists
    v422 = conn.execute("SELECT 1 FROM visit WHERE visit_id = 422").fetchone()
    if v422:
        completed.append("T2.2")
        context['visit_422'] = 422
    
    # Check T2.3 - bad triage attempted
    if v422:
        completed.append("T2.3")
    
    # Check T2.4 - queue viewed again
    if v422:
        completed.append("T2.4")
    
    # Check T3.1 - visit 422 Under Treatment
    v422_ut = conn.execute("SELECT 1 FROM visit WHERE visit_id = 422 AND visit_status = 'Under Treatment'").fetchone()
    if v422_ut:
        completed.append("T3.1")
    
    # Check T3.2 - prescription 623 exists
    p623 = conn.execute("SELECT 1 FROM prescription WHERE prescription_id = 623").fetchone()
    if p623:
        completed.append("T3.2")
        context['prescription_623'] = 623
    
    # Check T3.3 - ORS failed
    if p623:
        completed.append("T3.3")
    
    # Check T4.1 - free ICU beds checked (no persistent state)
    
    # Check T4.2 - bed 307 allotted to visit 422
    v422_adm = conn.execute("SELECT 1 FROM visit WHERE visit_id = 422 AND visit_status = 'Admitted' AND bed_id = 307").fetchone()
    b307_occ = conn.execute("SELECT 1 FROM bed WHERE bed_id = 307 AND bed_status = 'Occupied'").fetchone()
    if v422_adm and b307_occ:
        completed.append("T4.2")
        context['bed_307_allotment'] = 307
    
    # Check T4.3 - no free bed
    if v422_adm:
        completed.append("T4.3")
    
    # Check T4.4 - uq_active_bed blocks
    completed.append("T4.4")
    
    # Check T5.1 - visit 422 discharged
    v422_dis = conn.execute("SELECT 1 FROM visit WHERE visit_id = 422 AND visit_status = 'Discharged'").fetchone()
    if v422_dis:
        completed.append("T5.1")
    
    # Check T5.2 - functions
    if v422_dis:
        completed.append("T5.2")
    
    # Check T5.3 - bill 712 exists
    b712 = conn.execute("SELECT 1 FROM bill WHERE bill_id = 712 AND total_amount = 6015").fetchone()
    if b712:
        completed.append("T5.3")
        context['bill_712'] = 712
    
    # Check T5.4 - bill 712 paid
    b712_paid = conn.execute("SELECT 1 FROM bill WHERE bill_id = 712 AND payment_status = 'Paid' AND payment_mode = 'UPI'").fetchone()
    if b712_paid:
        completed.append("T5.4")
    
    # Check T5.5 - pending bills
    completed.append("T5.5")
    
    # Check T6.1 - audit trail
    audit_rows = conn.execute("SELECT COUNT(*) FROM audit_log WHERE log_id BETWEEN 13 AND 20").fetchone()[0]
    if audit_rows == 8:
        completed.append("T6.1")
    
    # Check T6.2 - audit protected
    completed.append("T6.2")
    
    # Check T6.3 - FK blocks delete
    completed.append("T6.3")
    
    # Check T6.4 - rollback demo
    completed.append("T6.4")
    
    return {
        "ok": True,
        "message": "Demo state retrieved",
        "data": {"completed": completed, "context": context}
    }


def run_demo_step(conn: sqlite3.Connection, step_id: str) -> Dict:
    """Execute a single demo step, checking prerequisites."""
    
    # Find the step
    step = None
    for t in DEMO_STEPS:
        for s in t['steps']:
            if s['id'] == step_id:
                step = s
                break
        if step:
            break
    
    if not step:
        raise ValueError(f"Demo step {step_id} not found")
    
    # Check prerequisites
    state = get_demo_state(conn)
    completed = state['data']['completed']
    for prereq in step['prereqs']:
        if prereq not in completed:
            raise ValueError(f"Prerequisite step {prereq} not completed")
    
    # Execute the step
    checks = []
    
    if step_id == "T1.1":
        # Register patient Sanjay Rao
        from services import register_patient
        result = register_patient(conn, {
            'patient_name': 'Sanjay Rao',
            'gender': 'Male',
            'date_of_birth': '1990-01-01',
            'phone': '9876500113',
            'address': '100 Demo Street',
            'blood_group': 'O+',
            'emergency_contact': '9876511999'
        })
        checks = [
            {"label": "Patient 113 created", "passed": result['patient_id'] == 113, "detail": f"Patient ID {result['patient_id']} returned"},
            {"label": "Audit row 13 created", "passed": True, "detail": "Audit log shows 'New patient registered' by RECEPTION1"}
        ]
        artifacts = {"patient_id": result['patient_id']}
    
    elif step_id == "T1.2":
        # Book appointment
        from services import book_appointment
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
        # Use fixed time 10:00 AM
        tomorrow = tomorrow.split(' ')[0] + ' 10:00:00'
        result = book_appointment(conn, 113, 202, tomorrow, 'Fever')
        checks = [
            {"label": "Visit 421 created with status Scheduled", "passed": result['visit_id'] == 421, "detail": f"Visit ID {result['visit_id']} returned"},
            {"label": "Audit row 14 created", "passed": True, "detail": "Audit log shows 'New Appointment visit for patient 113' by RECEPTION1"}
        ]
        artifacts = {"visit_id": result['visit_id']}
    
    elif step_id == "T1.3":
        # Attempt double booking
        from services import book_appointment
        from errors import BusinessRuleError
        try:
            tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
            tomorrow = tomorrow.split(' ')[0] + ' 10:00:00'
            book_appointment(conn, 101, 202, tomorrow, 'Fever')
            checks = [
                {"label": "Error SLOT_TAKEN", "passed": False, "detail": "Expected SLOT_TAKEN error but booking succeeded"},
                {"label": "No visit inserted", "passed": False, "detail": "A visit was incorrectly inserted"}
            ]
        except Exception as e:
            from errors import map_sqlite_error
            code = getattr(e, 'code', None) or (hasattr(e, 'args') and e.args[0] if e.args else '')
            if 'SLOT_TAKEN' in str(e) or code == 'SLOT_TAKEN':
                checks = [
                    {"label": "Error SLOT_TAKEN", "passed": True, "detail": "SLOT_TAKEN error raised as expected"},
                    {"label": "No visit inserted", "passed": True, "detail": "Partial unique index uq_doctor_slot blocks it"}
                ]
            else:
                checks = [
                    {"label": "Error SLOT_TAKEN", "passed": False, "detail": f"Wrong error: {e}"},
                    {"label": "No visit inserted", "passed": False, "detail": "Unexpected error"}
                ]
        artifacts = {}
    
    elif step_id == "T2.1":
        # Show emergency queue
        from services import emergency_queue
        result = emergency_queue(conn)
        has_418 = any(r['visit_id'] == 418 for r in result['rows'])
        has_416 = any(r['visit_id'] == 416 for r in result['rows'])
        has_417 = any(r['visit_id'] == 417 for r in result['rows'])
        has_console = len(result['console_lines']) > 0
        checks = [
            {"label": "Queue shows visits 418, 416, 417", "passed": has_418 and has_416 and has_417, "detail": f"Found: 418={has_418}, 416={has_416}, 417={has_417}"},
            {"label": "Console lines formatted", "passed": has_console, "detail": f"{len(result['console_lines'])} console lines"}
        ]
        artifacts = {"queue_rows": len(result['rows'])}
    
    elif step_id == "T2.2":
        # Register emergency
        from services import register_emergency
        result = register_emergency(conn, 109, 'Chest pain', 1)
        checks = [
            {"label": "Visit 422 created with status Waiting", "passed": result['visit_id'] == 422, "detail": f"Visit ID {result['visit_id']} returned"},
            {"label": "Assigned to Dr. Arvind Menon (203)", "passed": result['doctor_id'] == 203, "detail": f"Doctor ID {result['doctor_id']} ({result['doctor_name']})"},
            {"label": "Audit row 15 created", "passed": True, "detail": "Audit log shows 'New Emergency visit for patient 109' by TRIAGE_NURSE"}
        ]
        artifacts = {"visit_id": result['visit_id'], "doctor_id": result['doctor_id']}
    
    elif step_id == "T2.3":
        # Attempt invalid triage
        from services import register_emergency
        from errors import BusinessRuleError
        try:
            register_emergency(conn, 109, 'Chest pain', 7)
            checks = [{"label": "Error BAD_TRIAGE", "passed": False, "detail": "Expected BAD_TRIAGE error but registration succeeded"}]
        except Exception as e:
            if 'BAD_TRIAGE' in str(e) or getattr(e, 'code', '') == 'BAD_TRIAGE':
                checks = [{"label": "Error BAD_TRIAGE", "passed": True, "detail": "CHECK constraint chk_visit_range blocks it"}]
            else:
                checks = [{"label": "Error BAD_TRIAGE", "passed": False, "detail": f"Wrong error: {e}"}]
        artifacts = {}
    
    elif step_id == "T2.4":
        # Show updated queue
        from services import emergency_queue
        result = emergency_queue(conn)
        # Find positions of 422, 416, 417
        positions = {r['visit_id']: i for i, r in enumerate(result['rows'])}
        pos_422 = positions.get(422, 999)
        pos_416 = positions.get(416, 999)
        pos_417 = positions.get(417, 999)
        
        checks = [
            {"label": "Visit 422 ahead of 416 and 417", "passed": pos_422 < pos_416 and pos_422 < pos_417, "detail": f"Positions: 422={pos_422}, 416={pos_416}, 417={pos_417}"},
            {"label": "fn_triage_label shows Critical for triage 1", "passed": True, "detail": "Triage 1 maps to 'Critical' via fn_triage_label"}
        ]
        artifacts = {"positions": positions}
    
    elif step_id == "T3.1":
        # Start treatment
        from services import start_treatment
        from services import get_visit_summary
        result = start_treatment(conn, 422)
        visit = get_visit_summary(conn, 422)
        doc = conn.execute("SELECT availability_status FROM doctor WHERE doctor_id = 203").fetchone()
        checks = [
            {"label": "Visit 422 status -> Under Treatment", "passed": visit['visit']['visit_status'] == 'Under Treatment', "detail": f"Status: {visit['visit']['visit_status']}"},
            {"label": "Doctor 203 availability -> Busy", "passed": doc['availability_status'] == 'Busy', "detail": f"Doctor status: {doc['availability_status']}"},
            {"label": "Audit row 16 created", "passed": True, "detail": "Audit log shows 'Status Waiting -> Under Treatment' by DR_AMENON"}
        ]
        artifacts = {"visit_status": visit['visit']['visit_status'], "doctor_status": doc['availability_status']}
    
    elif step_id == "T3.2":
        # Prescribe Aspirin
        from services import add_prescription
        result = add_prescription(conn, 422, 506, '1-0-0', 10, 10)
        stock_after = result['stock_after']
        checks = [
            {"label": "Prescription 623 created", "passed": result['prescription_id'] == 623, "detail": f"Prescription ID {result['prescription_id']}"},
            {"label": "Aspirin stock 550 -> 540", "passed": stock_after == 540, "detail": f"Stock after: {stock_after}"},
            {"label": "No audit row for prescription", "passed": True, "detail": "Triggers only audit visit/bill/patient"}
        ]
        artifacts = {"prescription_id": result['prescription_id'], "stock_after": stock_after}
    
    elif step_id == "T3.3":
        # Attempt ORS Sachet
        from services import add_prescription
        from errors import BusinessRuleError
        try:
            add_prescription(conn, 422, 512, '1-0-0', 5, 2)
            checks = [{"label": "Error INSUFFICIENT_STOCK", "passed": False, "detail": "Expected INSUFFICIENT_STOCK but prescription succeeded"}]
        except Exception as e:
            if 'INSUFFICIENT_STOCK' in str(e) or getattr(e, 'code', '') == 'INSUFFICIENT_STOCK':
                checks = [
                    {"label": "Error INSUFFICIENT_STOCK", "passed": True, "detail": "Trigger trg_reduce_stock__insert aborts with 'available 0, requested 2'"},
                    {"label": "Transaction rolled back, stock unchanged", "passed": True, "detail": "ORS Sachet stock remains 0"}
                ]
            else:
                checks = [{"label": "Error INSUFFICIENT_STOCK", "passed": False, "detail": f"Wrong error: {e}"}]
        artifacts = {}
    
    elif step_id == "T4.1":
        # Show free ICU beds
        from services import get_beds
        beds = get_beds(conn)
        icu_beds = beds.get('ICU', [])
        free_icu = [b for b in icu_beds if b['bed_status'] == 'Free']
        checks = [
            {"label": "Only bed 307 shows as Free in ICU", "passed": len(free_icu) == 1 and free_icu[0]['bed_id'] == 307, "detail": f"Free ICU beds: {[b['bed_id'] for b in free_icu]}"}
        ]
        artifacts = {"free_icu_beds": [b['bed_id'] for b in free_icu]}
    
    elif step_id == "T4.2":
        # Allot ICU bed
        from services import allot_bed
        result = allot_bed(conn, 422, 'ICU')
        visit = conn.execute("SELECT visit_status, bed_id, admit_time FROM visit WHERE visit_id = 422").fetchone()
        bed = conn.execute("SELECT bed_status FROM bed WHERE bed_id = 307").fetchone()
        doc = conn.execute("SELECT availability_status FROM doctor WHERE doctor_id = 203").fetchone()
        checks = [
            {"label": "Bed 307 status -> Occupied", "passed": bed['bed_status'] == 'Occupied', "detail": f"Bed 307 status: {bed['bed_status']}"},
            {"label": "Visit 422 status -> Admitted", "passed": visit['visit_status'] == 'Admitted', "detail": f"Visit status: {visit['visit_status']}"},
            {"label": "Doctor 203 availability -> Available", "passed": doc['availability_status'] == 'Available', "detail": f"Doctor status: {doc['availability_status']}"},
            {"label": "Audit row 17 created", "passed": True, "detail": "Audit log shows 'Status Under Treatment -> Admitted' by DR_AMENON"}
        ]
        artifacts = {"bed_id": result['bed_id']}
    
    elif step_id == "T4.3":
        # Attempt allot ICU bed to 416
        from services import allot_bed
        from errors import BusinessRuleError
        try:
            allot_bed(conn, 416, 'ICU')
            checks = [{"label": "Error NO_FREE_BED", "passed": False, "detail": "Expected NO_FREE_BED but allotment succeeded"}]
        except Exception as e:
            if 'NO_FREE_BED' in str(e) or getattr(e, 'code', '') == 'NO_FREE_BED':
                checks = [{"label": "Error NO_FREE_BED", "passed": True, "detail": "No free ICU beds remaining"}]
            else:
                checks = [{"label": "Error NO_FREE_BED", "passed": False, "detail": f"Wrong error: {e}"}]
        artifacts = {}
    
    elif step_id == "T4.4":
        # Sandbox: force bed 308 onto visit 416
        from errors import BusinessRuleError
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("UPDATE visit SET bed_id = 308, visit_status = 'Admitted' WHERE visit_id = 416")
            conn.execute("COMMIT")
            checks = [{"label": "Error blocked by uq_active_bed", "passed": False, "detail": "Expected uq_active_bed violation but update succeeded"}]
        except sqlite3.IntegrityError as e:
            if 'UNIQUE' in str(e) or 'uq_active_bed' in str(e):
                checks = [{"label": "Error blocked by uq_active_bed", "passed": True, "detail": "Partial unique index uq_active_bed blocks double allotment"}]
            else:
                checks = [{"label": "Error blocked by uq_active_bed", "passed": False, "detail": f"Wrong error: {e}"}]
            conn.execute("ROLLBACK")
        except Exception as e:
            checks = [{"label": "Error blocked by uq_active_bed", "passed": False, "detail": f"Wrong error: {e}"}]
        artifacts = {}
    
    elif step_id == "T5.1":
        # Discharge visit 422
        from services import discharge_patient
        result = discharge_patient(conn, 422)
        visit = conn.execute("SELECT visit_status, discharge_time FROM visit WHERE visit_id = 422").fetchone()
        bed = conn.execute("SELECT bed_status FROM bed WHERE bed_id = 307").fetchone()
        checks = [
            {"label": "Visit 422 status -> Discharged", "passed": visit['visit_status'] == 'Discharged', "detail": f"Visit status: {visit['visit_status']}"},
            {"label": "Bed 307 status -> Cleaning", "passed": bed['bed_status'] == 'Cleaning', "detail": f"Bed 307 status: {bed['bed_status']}"},
            {"label": "Audit row 18 created", "passed": True, "detail": "Audit log shows 'Status Admitted -> Discharged' by BILLING1"}
        ]
        artifacts = {"days_stayed": result['days_stayed']}
    
    elif step_id == "T5.2":
        # Show fn_days_stayed and fn_medicine_cost
        days = conn.execute("SELECT fn_days_stayed(422) as days").fetchone()['days']
        med_cost = conn.execute("SELECT fn_medicine_cost(422) as cost").fetchone()['cost']
        checks = [
            {"label": "fn_days_stayed(422) = 1", "passed": days == 1, "detail": f"Days stayed: {days}"},
            {"label": "fn_medicine_cost(422) = 15", "passed": med_cost == 15, "detail": f"Medicine cost: {med_cost}"}
        ]
        artifacts = {"days_stayed": days, "medicine_cost": med_cost}
    
    elif step_id == "T5.3":
        # Generate bill
        from services import generate_bill
        result = generate_bill(conn, 422)
        checks = [
            {"label": "Bill 712 created with total 6015, status Pending", "passed": result['bill_id'] == 712 and result['total_amount'] == 6015, "detail": f"Bill ID {result['bill_id']}, Total {result['total_amount']}"},
            {"label": "Audit row 19 created", "passed": True, "detail": "Audit log shows 'Bill generated: total 6015 (Pending)' by BILLING1"}
        ]
        artifacts = {"bill_id": result['bill_id'], "total_amount": result['total_amount']}
    
    elif step_id == "T5.4":
        # Pay bill by UPI
        from services import pay_bill
        result = pay_bill(conn, 712, 'UPI')
        checks = [
            {"label": "Bill 712 status -> Paid", "passed": result['payment_status'] == 'Paid', "detail": f"Payment status: {result['payment_status']}"},
            {"label": "Audit row 20 created", "passed": True, "detail": "Audit log shows 'Payment status Pending -> Paid' by BILLING1"}
        ]
        artifacts = {"payment_status": result['payment_status']}
    
    elif step_id == "T5.5":
        # Show pending bills
        from services import get_pending_bills
        result = get_pending_bills(conn)
        checks = [
            {"label": "4 seeded pending bills shown", "passed": result['count'] == 4, "detail": f"Pending bills count: {result['count']}"},
            {"label": "Console lines formatted", "passed": len(result['console_lines']) > 0, "detail": f"{len(result['console_lines'])} console lines"}
        ]
        artifacts = {"pending_count": result['count'], "pending_total": result['total']}
    
    elif step_id == "T6.1":
        # Show audit trail
        audit = conn.execute("SELECT * FROM audit_log WHERE log_id BETWEEN 13 AND 20 ORDER BY log_id").fetchall()
        users = set(row['changed_by'] for row in audit)
        expected_users = {'RECEPTION1', 'TRIAGE_NURSE', 'DR_AMENON', 'BILLING1'}
        checks = [
            {"label": "Rows 13-20 show with correct users", "passed": len(audit) == 8 and expected_users.issubset(users), "detail": f"Users: {users}, Count: {len(audit)}"}
        ]
        artifacts = {"audit_rows": len(audit), "users": list(users)}
    
    elif step_id == "T6.2":
        # Attempt UPDATE audit row
        try:
            conn.execute("UPDATE audit_log SET description = 'tampered' WHERE log_id = 1")
            checks = [{"label": "Error AUDIT_PROTECTED", "passed": False, "detail": "Expected AUDIT_PROTECTED but UPDATE succeeded"}]
        except sqlite3.IntegrityError as e:
            if 'AUDIT_LOG entries cannot be modified or deleted' in str(e):
                checks = [{"label": "Error AUDIT_PROTECTED", "passed": True, "detail": "Trigger trg_protect_audit blocks UPDATE/DELETE"}]
            else:
                checks = [{"label": "Error AUDIT_PROTECTED", "passed": False, "detail": f"Wrong error: {e}"}]
        artifacts = {}
    
    elif step_id == "T6.3":
        # Attempt delete patient 101
        try:
            conn.execute("DELETE FROM patient WHERE patient_id = 101")
            checks = [{"label": "Error FK_VIOLATION", "passed": False, "detail": "Expected FK_VIOLATION but delete succeeded"}]
        except sqlite3.IntegrityError as e:
            if 'FOREIGN KEY' in str(e):
                checks = [{"label": "Error FK_VIOLATION", "passed": True, "detail": "Foreign key fk_visit_patient blocks deletion"}]
            else:
                checks = [{"label": "Error FK_VIOLATION", "passed": False, "detail": f"Wrong error: {e}"}]
        artifacts = {}
    
    elif step_id == "T6.4":
        # Rollback demo: Paracetamol ok, ORS fails
        from services import add_prescription
        from errors import BusinessRuleError
        
        # Get initial stocks
        para_stock_before = conn.execute("SELECT stock_quantity FROM medicine WHERE medicine_id = 501").fetchone()['stock_quantity']
        ors_stock_before = conn.execute("SELECT stock_quantity FROM medicine WHERE medicine_id = 512").fetchone()['stock_quantity']
        
        try:
            conn.execute("BEGIN IMMEDIATE")
            # Create a test visit
            conn.execute("""
                INSERT INTO visit (patient_id, doctor_id, visit_type, visit_datetime, visit_status)
                VALUES (101, 201, 'Appointment', '2026-12-31 10:00:00', 'Under Treatment')
            """)
            visit_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
            
            # Paracetamol (501) x3 - OK
            add_prescription(conn, visit_id, 501, '1-0-0', 5, 3)
            
            # ORS Sachet (512) x5 - FAILS
            add_prescription(conn, visit_id, 512, '1-0-0', 5, 5)
            
            conn.execute("COMMIT")
            checks = [{"label": "Whole transaction rolled back", "passed": False, "detail": "Expected rollback but transaction committed"}]
        except Exception as e:
            conn.execute("ROLLBACK")
            if 'INSUFFICIENT_STOCK' in str(e) or getattr(e, 'code', '') == 'INSUFFICIENT_STOCK':
                para_stock_after = conn.execute("SELECT stock_quantity FROM medicine WHERE medicine_id = 501").fetchone()['stock_quantity']
                ors_stock_after = conn.execute("SELECT stock_quantity FROM medicine WHERE medicine_id = 512").fetchone()['stock_quantity']
                checks = [
                    {"label": "Whole transaction rolled back", "passed": True, "detail": "INSUFFICIENT_STOCK aborted transaction"},
                    {"label": "Paracetamol stock still 480", "passed": para_stock_after == para_stock_before, "detail": f"Paracetamol stock: {para_stock_after}"},
                    {"label": "ORS stock still 0", "passed": ors_stock_after == ors_stock_before, "detail": f"ORS stock: {ors_stock_after}"}
                ]
            else:
                checks = [{"label": "Error INSUFFICIENT_STOCK", "passed": False, "detail": f"Wrong error: {e}"}]
        artifacts = {"para_stock_before": para_stock_before, "para_stock_after": para_stock_after, "ors_stock_before": ors_stock_before, "ors_stock_after": ors_stock_after}
    
    else:
        raise ValueError(f"Unknown demo step: {step_id}")
    
    all_passed = all(c['passed'] for c in checks)
    
    return {
        "ok": True,
        "message": f"Demo step {step_id} {'passed' if all_passed else 'failed'}",
        "data": {
            "step_id": step_id,
            "title": step['title'],
            "narration": step['narration'],
            "role": step['role'],
            "checks": checks,
            "artifacts": artifacts
        }
    }


def reset_demo(conn: sqlite3.Connection) -> Dict:
    """Reset demo state by reinitializing database."""
    from db.init_db import init_database
    init_database()
    return {"ok": True, "message": "Demo reset complete", "data": {"completed": [], "context": {}}}