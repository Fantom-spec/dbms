"""
Service layer for Smart Hospital Management System.
Each function runs as one atomic transaction (BEGIN IMMEDIATE, COMMIT, ROLLBACK on error).
"""
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any

from errors import (
    BusinessRuleError, ValidationError, NotFoundError, map_sqlite_error,
    MEDICINE_NOT_FOUND, BED_NOT_FOUND, BILL_NOT_FOUND, PRESCRIPTION_NOT_FOUND, BED_IN_USE,
    VISIT_NOT_FOUND, PATIENT_NOT_FOUND, DOCTOR_NOT_FOUND,
    SLOT_IN_PAST, SLOT_TAKEN, BAD_TRIAGE, NO_EMERGENCY_DOCTOR,
    VISIT_CLOSED, ALREADY_HAS_BED, NO_FREE_BED, BED_TAKEN,
    BAD_STATUS, AUDIT_PROTECTED, INSUFFICIENT_STOCK,
    BILL_EXISTS, NOT_DISCHARGED,
    UQ_DOCTOR_SLOT
)

from validation import (
    req_int, req_number, req_str, opt_str, req_choice, normalize_timestamp,
)
from db.connection import parse_timestamp


# ===== Helper Functions =====

def _read(conn: sqlite3.Connection, operations: callable) -> Any:
    """Run a read-only operation (no write lock, no transaction of its own)."""
    return operations(conn)


def _execute_in_transaction(conn: sqlite3.Connection, operations: callable) -> Any:
    """
    Execute operations within a transaction.
    
    Args:
        conn: Database connection
        operations: Function that takes connection and performs operations
        
    Returns:
        Result from operations function
        
    Raises:
        BusinessRuleError: On business rule violations or constraint violations
        sqlite3.Error: On other database errors
    """
    # Check if we're already in a transaction
    in_transaction = conn.in_transaction
    
    if not in_transaction:
        conn.execute('BEGIN IMMEDIATE')
    
    try:
        result = operations(conn)
        if not in_transaction:
            conn.execute('COMMIT')
        return result
    except BusinessRuleError:
        if not in_transaction:
            conn.execute('ROLLBACK')
        raise
    except sqlite3.IntegrityError as e:
        # Convert constraint violations to BusinessRuleError
        if not in_transaction:
            conn.execute('ROLLBACK')
        code, msg = map_sqlite_error(e)
        raise BusinessRuleError(code, msg, kind='constraint')
    except sqlite3.Error as e:
        if not in_transaction:
            conn.execute('ROLLBACK')
        raise
    except Exception as e:
        if not in_transaction:
            conn.execute('ROLLBACK')
        raise


def _get_current_user(conn: sqlite3.Connection) -> str:
    """Get current username from app_session."""
    row = conn.execute('SELECT username FROM app_session WHERE id = 1').fetchone()
    return row['username'] if row else 'UNKNOWN'


def _require_patient(conn: sqlite3.Connection, patient_id: int) -> Dict:
    """Verify patient exists, return patient row."""
    row = conn.execute(
        'SELECT * FROM patient WHERE patient_id = ?', (patient_id,)
    ).fetchone()
    if not row:
        raise NotFoundError(PATIENT_NOT_FOUND, f'Patient {patient_id} not found')
    return dict(row)


def _require_doctor(conn: sqlite3.Connection, doctor_id: int) -> Dict:
    """Verify doctor exists, return doctor row."""
    row = conn.execute(
        'SELECT * FROM doctor WHERE doctor_id = ?', (doctor_id,)
    ).fetchone()
    if not row:
        raise NotFoundError(DOCTOR_NOT_FOUND, f'Doctor {doctor_id} not found')
    return dict(row)


def _require_visit(conn: sqlite3.Connection, visit_id: int) -> Dict:
    """Verify visit exists, return visit row."""
    row = conn.execute(
        'SELECT * FROM visit WHERE visit_id = ?', (visit_id,)
    ).fetchone()
    if not row:
        raise NotFoundError(VISIT_NOT_FOUND, f'Visit {visit_id} not found')
    return dict(row)


def _require_medicine(conn: sqlite3.Connection, medicine_id: int) -> Dict:
    """Verify medicine exists, return medicine row."""
    row = conn.execute(
        'SELECT * FROM medicine WHERE medicine_id = ?', (medicine_id,)
    ).fetchone()
    if not row:
        raise NotFoundError(MEDICINE_NOT_FOUND, f'Medicine {medicine_id} not found')
    return dict(row)


def _require_bed(conn: sqlite3.Connection, bed_id: int) -> Dict:
    """Verify bed exists, return bed row."""
    row = conn.execute(
        'SELECT * FROM bed WHERE bed_id = ?', (bed_id,)
    ).fetchone()
    if not row:
        raise NotFoundError(BED_NOT_FOUND, f'Bed {bed_id} not found')
    return dict(row)


def _parse_datetime(dt_str: str) -> datetime:
    """Parse a timestamp string; raises ValidationError if it is not a valid date/time."""
    parsed = parse_timestamp(dt_str)
    if parsed is None:
        raise ValidationError(f'Invalid date/time: {dt_str!r}')
    return parsed


def _now_str() -> str:
    """Current timestamp as string."""
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _today_str() -> str:
    """Current date as string."""
    return datetime.now().strftime('%Y-%m-%d')


# ===== Patient Services =====

def _text(value):
    """Phone numbers may arrive as JSON numbers; store them as text."""
    return str(value) if isinstance(value, int) and not isinstance(value, bool) else value


def register_patient(conn: sqlite3.Connection, data: Dict) -> Dict:
    """
    Register a new patient.
    
    Args:
        conn: Database connection
        data: Dict with patient_name, gender, date_of_birth, phone, 
              address, blood_group, emergency_contact
        
    Returns:
        Dict with patient_id
    """
    def _ops(c):
        if not isinstance(data, dict):
            raise ValidationError('Request body must be a JSON object')
        name = req_str(data.get('patient_name'), 'patient_name', 100)
        gender = req_str(data.get('gender'), 'gender', 20)
        dob = req_str(data.get('date_of_birth'), 'date_of_birth', 10)
        phone = req_str(_text(data.get('phone')), 'phone', 20)
        cur = c.execute('''
            INSERT INTO patient (patient_name, gender, date_of_birth, phone, 
                               address, blood_group, emergency_contact)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            name, gender, dob, phone,
            opt_str(data.get('address'), 'address', 200),
            opt_str(data.get('blood_group'), 'blood_group', 5),     # '' -> NULL (CHECK would reject '')
            opt_str(_text(data.get('emergency_contact')), 'emergency_contact', 20),
        ))
        patient_id = cur.lastrowid
        return {'patient_id': patient_id}
    
    return _execute_in_transaction(conn, _ops)


def update_patient(conn: sqlite3.Connection, patient_id: int, data: Dict) -> Dict:
    """
    Update patient details.
    
    Args:
        conn: Database connection
        patient_id: Patient ID
        data: Dict with fields to update
        
    Returns:
        Dict with patient_id
    """
    def _ops(c):
        _require_patient(c, patient_id)
        if not isinstance(data, dict):
            raise ValidationError('Request body must be a JSON object')
        required_fields = ['patient_name', 'gender', 'date_of_birth', 'phone']
        optional_fields = ['address', 'blood_group', 'emergency_contact']
        updates = []
        values = []
        for field in required_fields:
            if field in data:
                updates.append(f'{field} = ?')
                values.append(req_str(_text(data[field]), field, 100))
        for field in optional_fields:
            if field in data:
                updates.append(f'{field} = ?')
                values.append(opt_str(_text(data[field]), field, 200))   # '' -> NULL
        
        if not updates:
            raise BusinessRuleError('VALIDATION_ERROR', 'No valid fields to update')
        
        values.append(patient_id)
        c.execute(f'UPDATE patient SET {", ".join(updates)} WHERE patient_id = ?', values)
        return {'patient_id': patient_id}
    
    return _execute_in_transaction(conn, _ops)


def delete_patient(conn: sqlite3.Connection, patient_id: int) -> Dict:
    """
    Delete a patient. Fails if patient has visits (FK constraint).
    
    Args:
        conn: Database connection
        patient_id: Patient ID
        
    Returns:
        Dict with patient_id
    """
    def _ops(c):
        _require_patient(c, patient_id)
        c.execute('DELETE FROM patient WHERE patient_id = ?', (patient_id,))
        return {'patient_id': patient_id}
    
    return _execute_in_transaction(conn, _ops)


def patient_history(conn: sqlite3.Connection, patient_id: int) -> Dict:
    """
    Get patient history with visits and doctors (3-table JOIN).
    
    Args:
        conn: Database connection
        patient_id: Patient ID
        
    Returns:
        Dict with patient and visits
    """
    def _ops(c):
        patient = _require_patient(c, patient_id)
        
        visits = c.execute('''
            SELECT v.visit_id, v.visit_datetime AS visit_time, v.visit_type, v.visit_status,
                   d.doctor_name, v.complaint
            FROM visit v
            JOIN doctor d ON d.doctor_id = v.doctor_id
            WHERE v.patient_id = ?
            ORDER BY v.visit_datetime
        ''', (patient_id,)).fetchall()
        
        return {
            'patient': patient,
            'visits': [dict(v) for v in visits]
        }
    
    return _read(conn, _ops)


def get_patients(conn: sqlite3.Connection, query: str = '') -> List[Dict]:
    """
    List patients with optional search, include visit count.
    
    Args:
        conn: Database connection
        query: Optional search query (name or phone)
        
    Returns:
        List of patient dicts with visit_count
    """
    def _ops(c):
        if query:
            like = '%' + str(query).replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
            rows = c.execute('''
                SELECT p.*, COUNT(v.visit_id) as visit_count
                FROM patient p
                LEFT JOIN visit v ON v.patient_id = p.patient_id
                WHERE p.patient_name LIKE ? ESCAPE '\\' OR p.phone LIKE ? ESCAPE '\\'
                GROUP BY p.patient_id
                ORDER BY p.patient_name
            ''', (like, like)).fetchall()
        else:
            rows = c.execute('''
                SELECT p.*, COUNT(v.visit_id) as visit_count
                FROM patient p
                LEFT JOIN visit v ON v.patient_id = p.patient_id
                GROUP BY p.patient_id
                ORDER BY p.patient_name
            ''').fetchall()
        return [dict(r) for r in rows]
    
    return _read(conn, _ops)


# ===== Doctor Services =====

def get_doctors(conn: sqlite3.Connection) -> List[Dict]:
    """List all doctors."""
    def _ops(c):
        rows = c.execute('SELECT * FROM doctor ORDER BY doctor_id').fetchall()
        return [dict(r) for r in rows]
    return _read(conn, _ops)


def create_doctor(conn: sqlite3.Connection, data: Dict) -> Dict:
    """Create a new doctor."""
    def _ops(c):
        if not isinstance(data, dict):
            raise ValidationError('Request body must be a JSON object')
        name = req_str(data.get('doctor_name'), 'doctor_name', 100)
        dept = req_str(data.get('department'), 'department', 100)
        fee = req_number(data.get('consultation_fee') if data.get('consultation_fee') not in ('', None)
                         else None, 'consultation_fee')
        shift = req_str(data.get('shift'), 'shift', 20)
        cur = c.execute('''
            INSERT INTO doctor (doctor_name, department, specialization, phone,
                               consultation_fee, shift, availability_status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            name, dept,
            opt_str(data.get('specialization'), 'specialization', 100),
            opt_str(_text(data.get('phone')), 'phone', 20),
            fee, shift,
            opt_str(data.get('availability_status'), 'availability_status', 20) or 'Available',
        ))
        doctor_id = cur.lastrowid
        return {'doctor_id': doctor_id}
    return _execute_in_transaction(conn, _ops)


def update_doctor(conn: sqlite3.Connection, doctor_id: int, data: Dict) -> Dict:
    """Update doctor details."""
    def _ops(c):
        _require_doctor(c, doctor_id)
        
        if not isinstance(data, dict):
            raise ValidationError('Request body must be a JSON object')
        updates = []
        values = []
        for field in ['doctor_name', 'department', 'shift', 'availability_status']:
            if field in data:
                updates.append(f'{field} = ?')
                values.append(req_str(data[field], field, 100))
        for field in ['specialization', 'phone']:
            if field in data:
                updates.append(f'{field} = ?')
                values.append(opt_str(_text(data[field]), field, 100))
        if 'consultation_fee' in data:
            updates.append('consultation_fee = ?')
            values.append(req_number(data['consultation_fee'], 'consultation_fee'))
        
        if not updates:
            raise BusinessRuleError('VALIDATION_ERROR', 'No valid fields to update')
        
        values.append(doctor_id)
        c.execute(f'UPDATE doctor SET {", ".join(updates)} WHERE doctor_id = ?', values)
        return {'doctor_id': doctor_id}
    return _execute_in_transaction(conn, _ops)


# ===== Medicine Services =====

def get_medicines(conn: sqlite3.Connection) -> List[Dict]:
    """List all medicines."""
    def _ops(c):
        rows = c.execute('SELECT * FROM medicine ORDER BY medicine_id').fetchall()
        return [dict(r) for r in rows]
    return _read(conn, _ops)


def create_medicine(conn: sqlite3.Connection, data: Dict) -> Dict:
    """Create a new medicine."""
    def _ops(c):
        if not isinstance(data, dict):
            raise ValidationError('Request body must be a JSON object')
        name = req_str(data.get('medicine_name'), 'medicine_name', 100)
        price = req_number(data.get('price_per_unit'), 'price_per_unit')
        stock = req_int(data.get('stock_quantity'), 'stock_quantity')
        cur = c.execute('''
            INSERT INTO medicine (medicine_name, manufacturer, price_per_unit, stock_quantity)
            VALUES (?, ?, ?, ?)
        ''', (name, opt_str(data.get('manufacturer'), 'manufacturer', 100), price, stock))
        medicine_id = cur.lastrowid
        return {'medicine_id': medicine_id}
    return _execute_in_transaction(conn, _ops)


def restock_medicine(conn: sqlite3.Connection, medicine_id: int, quantity: int) -> Dict:
    """Increase medicine stock."""
    def _ops(c):
        _require_medicine(c, medicine_id)
        quantity_ = req_int(quantity, 'quantity', minimum=1, maximum=1_000_000)
        c.execute(
            'UPDATE medicine SET stock_quantity = stock_quantity + ? WHERE medicine_id = ?',
            (quantity_, medicine_id)
        )
        row = c.execute('SELECT stock_quantity FROM medicine WHERE medicine_id = ?', (medicine_id,)).fetchone()
        return {'medicine_id': medicine_id, 'stock_quantity': row['stock_quantity']}
    return _execute_in_transaction(conn, _ops)


def get_low_stock_medicines(conn: sqlite3.Connection, threshold: int = 20) -> List[Dict]:
    """Get medicines with stock below threshold."""
    def _ops(c):
        rows = c.execute(
            'SELECT * FROM medicine WHERE stock_quantity < ? ORDER BY stock_quantity',
            (threshold,)
        ).fetchall()
        return [dict(r) for r in rows]
    return _read(conn, _ops)


# ===== Bed Services =====

def get_beds(conn: sqlite3.Connection) -> Dict:
    """Get beds grouped by ward with patient info for occupied beds."""
    def _ops(c):
        rows = c.execute('''
            SELECT b.*, v.visit_id, v.patient_id, p.patient_name
            FROM bed b
            LEFT JOIN visit v ON v.bed_id = b.bed_id AND v.visit_status = 'Admitted'
            LEFT JOIN patient p ON p.patient_id = v.patient_id
            ORDER BY b.ward_type, b.bed_id
        ''').fetchall()
        
        result = {}
        for row in rows:
            ward = row['ward_type']
            if ward not in result:
                result[ward] = []
            result[ward].append(dict(row))
        return result
    return _read(conn, _ops)


def create_bed(conn: sqlite3.Connection, ward_type: str, daily_charge: float) -> Dict:
    """Create a new bed."""
    def _ops(c):
        cur = c.execute(
            'INSERT INTO bed (ward_type, daily_charge) VALUES (?, ?)',
            (req_str(ward_type, 'ward_type', 20), req_number(daily_charge, 'daily_charge'))
        )
        bed_id = cur.lastrowid
        return {'bed_id': bed_id}
    return _execute_in_transaction(conn, _ops)


def set_bed_status(conn: sqlite3.Connection, bed_id: int, status: str) -> Dict:
    """Update bed status."""
    def _ops(c):
        _require_bed(c, bed_id)
        new_status = req_choice(status, 'status', ['Free', 'Occupied', 'Cleaning'])
        # A bed that holds an admitted patient must stay Occupied; and Occupied is only
        # meaningful for a bed with an admitted patient (allot_bed sets it).
        admitted = c.execute(
            "SELECT visit_id FROM visit WHERE bed_id = ? AND visit_status = 'Admitted'", (bed_id,)
        ).fetchone()
        if admitted and new_status != 'Occupied':
            raise BusinessRuleError(BED_IN_USE,
                f'Bed {bed_id} holds admitted visit {admitted["visit_id"]}; discharge the patient first')
        if not admitted and new_status == 'Occupied':
            raise BusinessRuleError(BAD_STATUS,
                f'Bed {bed_id} has no admitted patient; use "Allot bed" on a visit instead')
        c.execute('UPDATE bed SET bed_status = ? WHERE bed_id = ?', (new_status, bed_id))
        row = c.execute('SELECT bed_id, bed_status FROM bed WHERE bed_id = ?', (bed_id,)).fetchone()
        return {'bed_id': row['bed_id'], 'bed_status': row['bed_status']}
    return _execute_in_transaction(conn, _ops)


# ===== Visit/Appointment Services =====

def get_visits(conn: sqlite3.Connection, status: str = '', type: str = '', 
               patient_id: int = None) -> List[Dict]:
    """List visits with optional filters."""
    def _ops(c):
        conditions = []
        params = []
        
        if status:
            statuses = [s.strip() for s in str(status).split(',') if s.strip()]
            conditions.append('v.visit_status IN (%s)' % ','.join('?' * len(statuses)))
            params.extend(statuses)
        if type:
            conditions.append('v.visit_type = ?')
            params.append(type)
        if patient_id:
            conditions.append('v.patient_id = ?')
            params.append(patient_id)
        
        where = 'WHERE ' + ' AND '.join(conditions) if conditions else ''
        
        rows = c.execute(f'''
            SELECT v.*, p.patient_name, d.doctor_name, b.bill_id
            FROM visit v
            JOIN patient p ON p.patient_id = v.patient_id
            JOIN doctor d ON d.doctor_id = v.doctor_id
            LEFT JOIN bill b ON b.visit_id = v.visit_id
            {where}
            ORDER BY v.visit_datetime DESC
        ''', params).fetchall()
        return [dict(r) for r in rows]
    return _read(conn, _ops)


def get_visit_summary(conn: sqlite3.Connection, visit_id: int) -> Dict:
    """Get complete visit summary with patient, doctor, bed, prescriptions, costs."""
    def _ops(c):
        visit = _require_visit(c, visit_id)
        
        patient = _require_patient(c, visit['patient_id'])
        doctor = _require_doctor(c, visit['doctor_id'])
        
        bed = None
        if visit['bed_id']:
            bed = _require_bed(c, visit['bed_id'])
        
        prescriptions = c.execute('''
            SELECT pr.*, m.medicine_name, m.price_per_unit
            FROM prescription pr
            JOIN medicine m ON m.medicine_id = pr.medicine_id
            WHERE pr.visit_id = ?
        ''', (visit_id,)).fetchall()
        
        # Get medicine cost and days stayed via UDFs
        medicine_cost_row = c.execute('SELECT fn_medicine_cost(?) as cost', (visit_id,)).fetchone()
        medicine_cost = medicine_cost_row['cost'] if medicine_cost_row else 0
        
        days_stayed_row = c.execute('SELECT fn_days_stayed(?) as days', (visit_id,)).fetchone()
        days_stayed = days_stayed_row['days'] if days_stayed_row else 0
        
        bill = c.execute('SELECT * FROM bill WHERE visit_id = ?', (visit_id,)).fetchone()
        
        return {
            'visit': visit,
            'patient': patient,
            'doctor': doctor,
            'bed': dict(bed) if bed else None,
            'prescriptions': [dict(p) for p in prescriptions],
            'medicine_cost': medicine_cost,
            'days_stayed': days_stayed,
            'bill': dict(bill) if bill else None
        }
    return _read(conn, _ops)


def book_appointment(conn: sqlite3.Connection, patient_id: int, doctor_id: int, 
                     slot: str, complaint: str) -> Dict:
    """
    Book an appointment.
    
    Args:
        conn: Database connection
        patient_id: Patient ID
        doctor_id: Doctor ID
        slot: Appointment datetime string "YYYY-MM-DD HH:MM:SS"
        complaint: Complaint text
        
    Returns:
        Dict with visit_id
    """
    def _ops(c):
        pid = req_int(patient_id, 'patient_id')
        did = req_int(doctor_id, 'doctor_id')
        slot_n = normalize_timestamp(slot, 'slot')
        complaint_n = req_str(complaint, 'complaint', 300)
        _require_patient(c, pid)
        _require_doctor(c, did)
        slot_dt = _parse_datetime(slot_n)
        if slot_dt <= datetime.now():
            raise BusinessRuleError(SLOT_IN_PAST, 'Appointment must be in the future')
        
        # Check for conflict (service-level check, DB also enforces via uq_doctor_slot)
        existing = c.execute('''
            SELECT visit_id FROM visit 
            WHERE doctor_id = ? AND visit_datetime = ? AND visit_status <> 'Cancelled'
        ''', (did, slot_n)).fetchone()
        if existing:
            raise BusinessRuleError(SLOT_TAKEN, 
                f'Doctor {did} already has an appointment at that time')
        
        cur = c.execute('''
            INSERT INTO visit (patient_id, doctor_id, visit_type, visit_datetime, 
                              complaint, visit_status)
            VALUES (?, ?, 'Appointment', ?, ?, 'Scheduled')
        ''', (pid, did, slot_n, complaint_n))
        visit_id = cur.lastrowid
        return {'visit_id': visit_id}
    
    try:
        return _execute_in_transaction(conn, _ops)
    except sqlite3.IntegrityError as e:
        code, msg = map_sqlite_error(e)
        if code == UQ_DOCTOR_SLOT:
            raise BusinessRuleError(SLOT_TAKEN, 'Doctor already has an appointment at that time')
        raise


def cancel_appointment(conn: sqlite3.Connection, visit_id: int) -> Dict:
    """Cancel a scheduled appointment."""
    def _ops(c):
        visit = _require_visit(c, visit_id)
        if visit['visit_status'] != 'Scheduled':
            raise BusinessRuleError(BAD_STATUS, 'Only Scheduled visits can be cancelled')
        c.execute('UPDATE visit SET visit_status = ? WHERE visit_id = ?', ('Cancelled', visit_id))
        return {'visit_id': visit_id}
    return _execute_in_transaction(conn, _ops)


def start_treatment(conn: sqlite3.Connection, visit_id: int) -> Dict:
    """Start treatment: Waiting/Scheduled -> Under Treatment."""
    def _ops(c):
        visit = _require_visit(c, visit_id)
        if visit['visit_status'] not in ('Waiting', 'Scheduled'):
            raise BusinessRuleError(BAD_STATUS, 
                f'Cannot start treatment from status {visit["visit_status"]}')
        c.execute('UPDATE visit SET visit_status = ? WHERE visit_id = ?', 
                 ('Under Treatment', visit_id))
        row = c.execute('SELECT visit_id, visit_status FROM visit WHERE visit_id = ?', 
                       (visit_id,)).fetchone()
        return {'visit_id': row['visit_id'], 'visit_status': row['visit_status']}
    return _execute_in_transaction(conn, _ops)


# ===== Emergency Services =====

def register_emergency(conn: sqlite3.Connection, patient_id: int, complaint: str, 
                       triage: int, arrival: str = None) -> Dict:
    """
    Register emergency visit. Assigns Emergency doctor with fewest active cases.
    
    Args:
        conn: Database connection
        patient_id: Patient ID
        complaint: Complaint text
        triage: Triage level (1-4)
        arrival: Optional arrival datetime (defaults to now)
        
    Returns:
        Dict with visit_id, doctor_id, doctor_name
    """
    def _ops(c):
        pid = req_int(patient_id, 'patient_id')
        _require_patient(c, pid)
        try:
            triage_n = req_int(triage, 'triage_level')
        except ValidationError:
            raise BusinessRuleError(BAD_TRIAGE, 'Triage level must be a whole number between 1 and 4')
        if not 1 <= triage_n <= 4:
            raise BusinessRuleError(BAD_TRIAGE, 'Triage level must be between 1 and 4')
        complaint_n = req_str(complaint, 'complaint', 300)
        arrival_dt = normalize_timestamp(arrival, 'arrival') if arrival else _now_str()
        
        # Find Emergency doctor with fewest Waiting/Under Treatment visits
        doctor_row = c.execute('''
            SELECT d.doctor_id, d.doctor_name,
                   COUNT(v.visit_id) as active_count
            FROM doctor d
            LEFT JOIN visit v ON v.doctor_id = d.doctor_id 
                AND v.visit_status IN ('Waiting', 'Under Treatment')
            WHERE d.department = 'Emergency'
            GROUP BY d.doctor_id, d.doctor_name
            ORDER BY active_count, d.doctor_id
            LIMIT 1
        ''').fetchone()
        
        if not doctor_row:
            raise BusinessRuleError(NO_EMERGENCY_DOCTOR, 'No emergency doctor available')
        
        doctor_id = doctor_row['doctor_id']
        doctor_name = doctor_row['doctor_name']
        
        cur = c.execute('''
            INSERT INTO visit (patient_id, doctor_id, visit_type, visit_datetime, 
                              complaint, triage_level, visit_status)
            VALUES (?, ?, 'Emergency', ?, ?, ?, 'Waiting')
        ''', (pid, doctor_id, arrival_dt, complaint_n, triage_n))
        visit_id = cur.lastrowid
        
        return {
            'visit_id': visit_id,
            'doctor_id': doctor_id,
            'doctor_name': doctor_name
        }
    
    return _execute_in_transaction(conn, _ops)


def emergency_queue(conn: sqlite3.Connection) -> Dict:
    """Get emergency waiting queue with cursor-style output."""
    def _ops(c):
        rows = c.execute('''
            SELECT v.visit_id, v.patient_id, p.patient_name, v.triage_level, v.complaint,
                   d.doctor_name, v.visit_datetime, v.visit_status
            FROM visit v
            JOIN patient p ON p.patient_id = v.patient_id
            JOIN doctor d ON d.doctor_id = v.doctor_id
            WHERE v.visit_type = 'Emergency' AND v.visit_status = 'Waiting'
            ORDER BY v.triage_level, v.visit_datetime
        ''').fetchall()
        
        # Build console_lines like Oracle DBMS_OUTPUT
        console_lines = [
            'EMERGENCY WAITING LIST (highest priority first)',
            '-' * 70
        ]
        for i, row in enumerate(rows, 1):
            triage_label = c.execute('SELECT fn_triage_label(?) as label', (row['triage_level'],)).fetchone()['label']
            console_lines.append(
                f"{i}. [T{row['triage_level']}] {triage_label:<11} | "
                f"Visit {row['visit_id']} | {row['patient_name']} | "
                f"arrived {row['visit_datetime'][11:16]}"
            )
            console_lines.append(
                f"      Complaint: {row['complaint']} | {row['doctor_name']}"
            )
        
        if not rows:
            console_lines.append('No emergency patient is waiting.')
        
        return {
            'rows': [dict(r) for r in rows],
            'console_lines': console_lines
        }
    return _read(conn, _ops)


# ===== Bed Allotment =====

def allot_bed(conn: sqlite3.Connection, visit_id: int, ward_type: str) -> Dict:
    """
    Allot bed to visit. Updates bed and visit in same transaction.
    
    Args:
        conn: Database connection
        visit_id: Visit ID
        ward_type: Ward type (General, Private, ICU, Emergency)
        
    Returns:
        Dict with bed_id
    """
    def _ops(c):
        visit = _require_visit(c, visit_id)
        
        if visit['visit_status'] in ('Cancelled', 'Discharged'):
            raise BusinessRuleError(VISIT_CLOSED, 
                f'Visit {visit_id} is already {visit["visit_status"]}')
        if visit['bed_id'] is not None:
            raise BusinessRuleError(ALREADY_HAS_BED, f'Visit {visit_id} already has a bed')
        
        # Find lowest-numbered free bed in ward
        bed = c.execute('''
            SELECT bed_id FROM bed 
            WHERE ward_type = ? AND bed_status = 'Free'
            ORDER BY bed_id LIMIT 1
        ''', (ward_type,)).fetchone()
        
        if not bed:
            raise BusinessRuleError(NO_FREE_BED, f'No free bed in the {ward_type} ward')
        
        bed_id = bed['bed_id']
        
        # Update bed status
        updated = c.execute(
            'UPDATE bed SET bed_status = ? WHERE bed_id = ? AND bed_status = ?',
            ('Occupied', bed_id, 'Free')
        ).rowcount
        if updated == 0:
            raise BusinessRuleError(BED_TAKEN, f'Bed {bed_id} was taken, try again')
        
        # Update visit with bed, admit_time, and status
        admit_time = _now_str()
        c.execute('''
            UPDATE visit SET bed_id = ?, admit_time = ?, visit_status = ?
            WHERE visit_id = ?
        ''', (bed_id, admit_time, 'Admitted', visit_id))
        
        return {'bed_id': bed_id}
    
    return _execute_in_transaction(conn, _ops)


def discharge_patient(conn: sqlite3.Connection, visit_id: int) -> Dict:
    """
    Discharge patient. Sets visit to Discharged, bed to Cleaning.
    
    Args:
        conn: Database connection
        visit_id: Visit ID
        
    Returns:
        Dict with visit_id, bed_id, days_stayed
    """
    def _ops(c):
        visit = _require_visit(c, visit_id)
        
        if visit['visit_status'] not in ('Waiting', 'Under Treatment', 'Admitted'):
            raise BusinessRuleError(BAD_STATUS, 
                f'Visit {visit_id} cannot be discharged from status {visit["visit_status"]}')
        
        bed_id = visit['bed_id']
        discharge_time = _now_str()
        
        # Update visit
        c.execute('''
            UPDATE visit SET visit_status = ?, discharge_time = ?
            WHERE visit_id = ?
        ''', ('Discharged', discharge_time, visit_id))
        
        # Update bed if was admitted
        if bed_id:
            c.execute('UPDATE bed SET bed_status = ? WHERE bed_id = ?', ('Cleaning', bed_id))
        
        # Calculate days stayed
        days_row = c.execute('SELECT fn_days_stayed(?) as days', (visit_id,)).fetchone()
        days_stayed = days_row['days'] if days_row else 0
        
        return {'visit_id': visit_id, 'bed_id': bed_id, 'days_stayed': days_stayed}
    
    return _execute_in_transaction(conn, _ops)


# ===== Pharmacy Services =====

def get_prescriptions(conn: sqlite3.Connection, visit_id: int) -> List[Dict]:
    """Get prescriptions for a visit with medicine details."""
    def _ops(c):
        rows = c.execute('''
            SELECT pr.*, m.medicine_name, m.price_per_unit
            FROM prescription pr
            JOIN medicine m ON m.medicine_id = pr.medicine_id
            WHERE pr.visit_id = ?
            ORDER BY pr.prescription_id
        ''', (visit_id,)).fetchall()
        return [dict(r) for r in rows]
    return _read(conn, _ops)


def add_prescription(conn: sqlite3.Connection, visit_id: int, medicine_id: int,
                     dosage: str, duration_days: int, quantity: int) -> Dict:
    """
    Add prescription. Trigger reduces stock.
    
    Args:
        conn: Database connection
        visit_id: Visit ID
        medicine_id: Medicine ID
        dosage: Dosage string
        duration_days: Duration in days
        quantity: Quantity
        
    Returns:
        Dict with prescription_id and stock_after
    """
    def _ops(c):
        vid = req_int(visit_id, 'visit_id')
        mid = req_int(medicine_id, 'medicine_id')
        days = req_int(duration_days, 'duration_days')
        qty = req_int(quantity, 'quantity')
        dosage_n = opt_str(dosage, 'dosage', 100)
        visit = _require_visit(c, vid)
        if visit['visit_status'] == 'Cancelled':
            raise BusinessRuleError(VISIT_CLOSED, 'Cannot prescribe for cancelled visit')
        
        _require_medicine(c, mid)

        # Friendly, specific message. The trg_reduce_stock trigger still enforces this at the
        # database level, but SQLite's RAISE() only accepts a literal message.
        med = c.execute(
            'SELECT medicine_name, stock_quantity FROM medicine WHERE medicine_id = ?', (mid,)
        ).fetchone()
        if med and med['stock_quantity'] < qty:
            raise BusinessRuleError(
                INSUFFICIENT_STOCK,
                f"Insufficient stock for {med['medicine_name']}: "
                f"available {med['stock_quantity']}, requested {qty}")

        cur = c.execute('''
            INSERT INTO prescription (visit_id, medicine_id, dosage, duration_days, quantity)
            VALUES (?, ?, ?, ?, ?)
        ''', (vid, mid, dosage_n, days, qty))
        
        prescription_id = cur.lastrowid
        
        # Get updated stock
        stock_row = c.execute(
            'SELECT stock_quantity FROM medicine WHERE medicine_id = ?', (mid,)
        ).fetchone()
        
        return {
            'prescription_id': prescription_id,
            'stock_after': stock_row['stock_quantity']
        }
    
    try:
        return _execute_in_transaction(conn, _ops)
    except sqlite3.IntegrityError as e:
        code, msg = map_sqlite_error(e)
        if code == INSUFFICIENT_STOCK:
            raise BusinessRuleError(INSUFFICIENT_STOCK, msg)
        raise


def delete_prescription(conn: sqlite3.Connection, prescription_id: int) -> Dict:
    """Delete prescription. Trigger restores stock."""
    def _ops(c):
        row = c.execute(
            'SELECT prescription_id, medicine_id FROM prescription WHERE prescription_id = ?',
            (prescription_id,)
        ).fetchone()
        if not row:
            raise NotFoundError(PRESCRIPTION_NOT_FOUND, f'Prescription {prescription_id} not found')
        
        medicine_id = row['medicine_id']
        c.execute('DELETE FROM prescription WHERE prescription_id = ?', (prescription_id,))
        
        # Get updated stock
        stock_row = c.execute(
            'SELECT stock_quantity FROM medicine WHERE medicine_id = ?', (medicine_id,)
        ).fetchone()
        
        return {'prescription_id': prescription_id, 'stock_after': stock_row['stock_quantity']}
    
    return _execute_in_transaction(conn, _ops)


# ===== Billing Services =====

def generate_bill(conn: sqlite3.Connection, visit_id: int) -> Dict:
    """
    Generate bill for discharged visit.
    
    Args:
        conn: Database connection
        visit_id: Visit ID
        
    Returns:
        Dict with bill_id, consultation_charge, medicine_charge, bed_charge, total_amount
    """
    def _ops(c):
        visit = _require_visit(c, visit_id)
        
        if visit['visit_status'] != 'Discharged':
            raise BusinessRuleError(NOT_DISCHARGED, 'Visit must be Discharged to generate bill')
        
        # Check if bill already exists
        existing = c.execute('SELECT bill_id FROM bill WHERE visit_id = ?', (visit_id,)).fetchone()
        if existing:
            raise BusinessRuleError(BILL_EXISTS, 'Bill already exists for this visit')
        
        doctor = _require_doctor(c, visit['doctor_id'])
        consultation_charge = doctor['consultation_fee']
        
        # Medicine cost via UDF
        medicine_row = c.execute('SELECT fn_medicine_cost(?) as cost', (visit_id,)).fetchone()
        medicine_charge = round(medicine_row['cost'], 2) if medicine_row else 0
        
        # Bed charge
        bed_charge = 0
        if visit['bed_id']:
            bed = _require_bed(c, visit['bed_id'])
            days_row = c.execute('SELECT fn_days_stayed(?) as days', (visit_id,)).fetchone()
            days_stayed = days_row['days'] if days_row else 0
            bed_charge = round(bed['daily_charge'] * days_stayed, 2)
        
        total_amount = round(consultation_charge + medicine_charge + bed_charge, 2)
        
        cur = c.execute('''
            INSERT INTO bill (visit_id, consultation_charge, medicine_charge, 
                             bed_charge, total_amount, payment_status)
            VALUES (?, ?, ?, ?, ?, 'Pending')
        ''', (visit_id, consultation_charge, medicine_charge, bed_charge, total_amount))
        
        bill_id = cur.lastrowid
        
        return {
            'bill_id': bill_id,
            'consultation_charge': consultation_charge,
            'medicine_charge': medicine_charge,
            'bed_charge': bed_charge,
            'total_amount': total_amount
        }
    
    return _execute_in_transaction(conn, _ops)


def get_bills(conn: sqlite3.Connection, status: str = '') -> List[Dict]:
    """List bills with optional status filter."""
    def _ops(c):
        if status:
            rows = c.execute('''
                SELECT b.*, p.patient_name
                FROM bill b
                JOIN visit v ON v.visit_id = b.visit_id
                JOIN patient p ON p.patient_id = v.patient_id
                WHERE b.payment_status = ?
                ORDER BY b.bill_date DESC, b.bill_id
            ''', (status,)).fetchall()
        else:
            rows = c.execute('''
                SELECT b.*, p.patient_name
                FROM bill b
                JOIN visit v ON v.visit_id = b.visit_id
                JOIN patient p ON p.patient_id = v.patient_id
                ORDER BY b.bill_date DESC, b.bill_id
            ''').fetchall()
        return [dict(r) for r in rows]
    return _read(conn, _ops)


def get_pending_bills(conn: sqlite3.Connection, min_amount: float = 0) -> Dict:
    """Get pending bills with cursor-style output."""
    def _ops(c):
        rows = c.execute('''
            SELECT b.bill_id, p.patient_name, b.bill_date, b.total_amount
            FROM bill b
            JOIN visit v ON v.visit_id = b.visit_id
            JOIN patient p ON p.patient_id = v.patient_id
            WHERE b.payment_status = 'Pending' AND b.total_amount >= ?
            ORDER BY b.bill_date, b.bill_id
        ''', (min_amount,)).fetchall()
        
        # Build console_lines like Oracle DBMS_OUTPUT
        console_lines = [
            f'PENDING BILLS (amount >= {min_amount})',
            '-' * 62
        ]
        total = 0
        for row in rows:
            console_lines.append(
                f"Bill {row['bill_id']} | {row['patient_name']:<18} | "
                f"{row['bill_date']} | Rs. {row['total_amount']:>10.2f}"
            )
            total += row['total_amount']
        
        console_lines.append('-' * 62)
        console_lines.append(f"{len(rows)} bill(s) pending, total Rs. {total:.2f}")
        
        return {
            'columns': ['bill_id', 'patient_name', 'bill_date', 'total_amount'],
            'rows': [list(r) for r in rows],  # Preserve column order
            'console_lines': console_lines,
            'count': len(rows),
            'total': total
        }
    return _read(conn, _ops)


def pay_bill(conn: sqlite3.Connection, bill_id: int, payment_mode: str) -> Dict:
    """Record payment for a bill."""
    def _ops(c):
        row = c.execute(
            'SELECT bill_id, payment_status FROM bill WHERE bill_id = ?', (bill_id,)
        ).fetchone()
        if not row:
            raise NotFoundError(BILL_NOT_FOUND, f'Bill {bill_id} not found')
        
        if row['payment_status'] == 'Paid':
            raise BusinessRuleError(BAD_STATUS, 'Bill already paid')
        
        if payment_mode not in ('Cash', 'Card', 'UPI'):
            raise BusinessRuleError('VALIDATION_ERROR', 'Payment mode must be Cash, Card, or UPI')
        
        c.execute('''
            UPDATE bill SET payment_mode = ?, payment_status = ? WHERE bill_id = ?
        ''', (payment_mode, 'Paid', bill_id))
        
        updated = c.execute(
            'SELECT bill_id, payment_status FROM bill WHERE bill_id = ?', (bill_id,)
        ).fetchone()
        
        return {'bill_id': updated['bill_id'], 'payment_status': updated['payment_status']}
    
    return _execute_in_transaction(conn, _ops)


# ===== Lookups and Meta =====

def get_lookups(conn: sqlite3.Connection) -> Dict:
    """Get lookup data for forms."""
    def _ops(c):
        patients = c.execute(
            'SELECT patient_id as id, patient_name as name FROM patient ORDER BY patient_name'
        ).fetchall()
        
        doctors = c.execute(
            'SELECT doctor_id as id, doctor_name as name, department, consultation_fee as fee '
            'FROM doctor ORDER BY doctor_name'
        ).fetchall()
        
        medicines = c.execute(
            'SELECT medicine_id as id, medicine_name as name, stock_quantity as stock, '
            'price_per_unit as price FROM medicine ORDER BY medicine_name'
        ).fetchall()
        
        wards = c.execute(
            'SELECT DISTINCT ward_type FROM bed ORDER BY ward_type'
        ).fetchall()
        
        departments = c.execute(
            'SELECT DISTINCT department FROM doctor ORDER BY department'
        ).fetchall()
        
        return {
            'patients': [dict(r) for r in patients],
            'doctors': [dict(r) for r in doctors],
            'medicines': [dict(r) for r in medicines],
            'wards': [r['ward_type'] for r in wards],
            'departments': [r['department'] for r in departments]
        }
    return _read(conn, _ops)


def get_dashboard(conn: sqlite3.Connection) -> Dict:
    """Get dashboard KPIs and charts data."""
    def _ops(c):
        # KPIs
        kpis = {}
        kpis['patients'] = c.execute('SELECT COUNT(*) FROM patient').fetchone()[0]
        kpis['active_visits'] = c.execute(
            "SELECT COUNT(*) FROM visit WHERE visit_status IN ('Waiting','Under Treatment','Admitted')"
        ).fetchone()[0]
        kpis['free_beds'] = c.execute(
            "SELECT COUNT(*) FROM bed WHERE bed_status = 'Free'"
        ).fetchone()[0]
        
        pending_bills = c.execute(
            "SELECT COUNT(*) as cnt, COALESCE(SUM(total_amount),0) as total "
            "FROM bill WHERE payment_status = 'Pending'"
        ).fetchone()
        kpis['pending_bills'] = pending_bills['cnt']
        kpis['pending_amount'] = pending_bills['total']
        
        kpis['waiting_emergency'] = c.execute(
            "SELECT COUNT(*) FROM visit WHERE visit_type = 'Emergency' AND visit_status = 'Waiting'"
        ).fetchone()[0]
        
        kpis['low_stock_count'] = c.execute(
            "SELECT COUNT(*) FROM medicine WHERE stock_quantity < 20"
        ).fetchone()[0]
        
        # Bed occupancy
        bed_occupancy = c.execute('''
            SELECT ward_type, COUNT(*) as total_beds,
                   SUM(CASE WHEN bed_status = 'Occupied' THEN 1 ELSE 0 END) as occupied,
                   ROUND(100.0 * SUM(CASE WHEN bed_status = 'Occupied' THEN 1 ELSE 0 END) / COUNT(*), 1) as occupancy_pct
            FROM bed GROUP BY ward_type ORDER BY ward_type
        ''').fetchall()
        
        # Triage distribution
        triage = c.execute('''
            SELECT triage_level, COUNT(*) as count
            FROM visit WHERE visit_type = 'Emergency'
            GROUP BY triage_level ORDER BY triage_level
        ''').fetchall()
        
        # Low stock medicines
        low_stock = c.execute(
            'SELECT * FROM medicine WHERE stock_quantity < 20 ORDER BY stock_quantity'
        ).fetchall()
        
        # Recent audit
        recent_audit = c.execute('''
            SELECT * FROM audit_log ORDER BY log_id DESC LIMIT 5
        ''').fetchall()
        
        return {
            'kpis': kpis,
            'bed_occupancy': [dict(r) for r in bed_occupancy],
            'triage': [dict(r) for r in triage],
            'low_stock': [dict(r) for r in low_stock],
            'recent_audit': [dict(r) for r in recent_audit]
        }
    return _read(conn, _ops)
