"""
Tests for service layer: all service functions with happy paths and error codes.
"""
import os
import pytest
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
import uuid

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from services import (
    register_patient, update_patient, delete_patient, patient_history, get_patients,
    get_doctors, create_doctor, update_doctor,
    get_medicines, create_medicine, restock_medicine, get_low_stock_medicines,
    get_beds, create_bed, set_bed_status,
    get_visits, get_visit_summary, book_appointment, cancel_appointment, start_treatment,
    register_emergency, emergency_queue,
    allot_bed, discharge_patient,
    get_prescriptions, add_prescription, delete_prescription,
    generate_bill, get_bills, get_pending_bills, pay_bill,
    get_lookups, get_dashboard,
)
from errors import BusinessRuleError, map_sqlite_error
from db.connection import get_connection
from config import DB_PATH


@pytest.fixture(scope="session")
def db_conn():
    """Get a fresh database connection for testing."""
    from db.init_db import init_database
    init_database()
    
    conn = get_connection(DB_PATH)
    yield conn
    conn.close()


def unique_phone() -> str:
    """Generate a unique 10-digit phone number for testing."""
    return f'98765{uuid.uuid4().int % 100000:05d}'


def unique_phone_suffix(suffix: str) -> str:
    """Generate a unique phone with a suffix for debugging."""
    return f'98765{suffix}{uuid.uuid4().int % 10000:04d}'


@pytest.fixture
def transaction_conn(db_conn):
    """Provide a connection for a single test with automatic rollback."""
    db_conn.execute('BEGIN IMMEDIATE')
    yield db_conn
    db_conn.execute('ROLLBACK')


# ===== Error Mapping Tests =====

class TestErrorMapping:
    """Test map_sqlite_error function."""
    
    def test_unique_patient_phone(self, db_conn):
        """Duplicate phone maps to UQ_PATIENT_PHONE."""
        # First insert a patient
        db_conn.execute('BEGIN IMMEDIATE')
        db_conn.execute(
            'INSERT INTO patient (patient_name, phone, gender, date_of_birth) VALUES (?, ?, ?, ?)',
            ('Test', '9876500999', 'Male', '2000-01-01')
        )
        db_conn.execute('COMMIT')
        
        # Try duplicate
        db_conn.execute('BEGIN IMMEDIATE')
        try:
            db_conn.execute(
                'INSERT INTO patient (patient_name, phone, gender, date_of_birth) VALUES (?, ?, ?, ?)',
                ('Test2', '9876500999', 'Male', '2000-01-01')
            )
            db_conn.execute('COMMIT')
        except sqlite3.IntegrityError as e:
            db_conn.execute('ROLLBACK')
            code, msg = map_sqlite_error(e)
            assert code == 'UQ_PATIENT_PHONE'
            assert 'Phone number already registered' in msg
    
    def test_check_patient_gender(self, db_conn):
        """Invalid gender maps to CHK_PAT_GENDER."""
        db_conn.execute('BEGIN IMMEDIATE')
        try:
            db_conn.execute(
                'INSERT INTO patient (patient_name, phone, gender, date_of_birth) VALUES (?, ?, ?, ?)',
                ('Test', '9876500998', 'Invalid', '2000-01-01')
            )
            db_conn.execute('COMMIT')
        except sqlite3.IntegrityError as e:
            db_conn.execute('ROLLBACK')
            code, msg = map_sqlite_error(e)
            assert code == 'CHK_PAT_GENDER'
    
    def test_check_patient_phone_format(self, db_conn):
        """Invalid phone format maps to CHK_PAT_PHONE."""
        db_conn.execute('BEGIN IMMEDIATE')
        try:
            db_conn.execute(
                'INSERT INTO patient (patient_name, phone, gender, date_of_birth) VALUES (?, ?, ?, ?)',
                ('Test', '98765ABCDE', 'Male', '2000-01-01')
            )
            db_conn.execute('COMMIT')
        except sqlite3.IntegrityError as e:
            db_conn.execute('ROLLBACK')
            code, msg = map_sqlite_error(e)
            assert code == 'CHK_PAT_PHONE'
    
    def test_foreign_key_visit_patient(self, db_conn):
        """Missing patient for visit maps to FK_VIOLATION (generic FK error)."""
        db_conn.execute('BEGIN IMMEDIATE')
        try:
            db_conn.execute(
                'INSERT INTO visit (patient_id, doctor_id, visit_type, visit_datetime, visit_status) VALUES (?, ?, ?, ?, ?)',
                (999, 201, 'Appointment', '2026-12-31 10:00:00', 'Scheduled')
            )
            db_conn.execute('COMMIT')
        except sqlite3.IntegrityError as e:
            db_conn.execute('ROLLBACK')
            code, msg = map_sqlite_error(e)
            # SQLite FK errors don't include table info, so we get generic FK_VIOLATION
            assert code in ('FK_VISIT_PATIENT', 'FK_VIOLATION'), f'Got {code}'
    
    def test_trigger_insufficient_stock(self, db_conn):
        """Trigger stock error maps to INSUFFICIENT_STOCK."""
        db_conn.execute('BEGIN IMMEDIATE')
        try:
            # Create visit
            db_conn.execute(
                'INSERT INTO visit (patient_id, doctor_id, visit_type, visit_datetime, visit_status) VALUES (?, ?, ?, ?, ?)',
                (101, 201, 'Appointment', '2026-12-31 10:00:00', 'Scheduled')
            )
            visit_id = db_conn.execute('SELECT last_insert_rowid()').fetchone()[0]
            
            # Try to prescribe ORS Sachet (stock 0)
            db_conn.execute(
                'INSERT INTO prescription (visit_id, medicine_id, dosage, duration_days, quantity) VALUES (?, ?, ?, ?, ?)',
                (visit_id, 512, '1-0-0', 5, 5)
            )
            db_conn.execute('COMMIT')
        except sqlite3.IntegrityError as e:
            db_conn.execute('ROLLBACK')
            code, msg = map_sqlite_error(e)
            assert code == 'INSUFFICIENT_STOCK'
            assert 'Insufficient stock' in msg
    
    def test_trigger_audit_protection(self, db_conn):
        """Trigger audit protection maps to AUDIT_PROTECTED."""
        db_conn.execute('BEGIN IMMEDIATE')
        try:
            db_conn.execute('UPDATE audit_log SET description = ? WHERE log_id = 1', ('Tampered',))
            db_conn.execute('COMMIT')
        except sqlite3.IntegrityError as e:
            db_conn.execute('ROLLBACK')
            code, msg = map_sqlite_error(e)
            assert code == 'AUDIT_PROTECTED'


# ===== Patient Services Tests =====

class TestPatientServices:
    """Test patient CRUD operations."""
    
    def test_register_patient_happy_path(self, transaction_conn):
        """Register a new patient successfully."""
        phone = unique_phone()
        result = register_patient(transaction_conn, {
            'patient_name': 'Test Patient',
            'gender': 'Male',
            'date_of_birth': '2000-01-01',
            'phone': phone,
            'address': 'Test Address',
            'blood_group': 'A+',
            'emergency_contact': '9876500888'
        })
        assert 'patient_id' in result
        assert result['patient_id'] > 112  # After seed
    
    def test_register_patient_missing_fields(self, transaction_conn):
        """Register patient fails with missing required fields."""
        with pytest.raises(BusinessRuleError) as exc:
            register_patient(transaction_conn, {
                'patient_name': 'Test',
                'gender': 'Male'
                # missing date_of_birth, phone
            })
        assert exc.value.code == 'VALIDATION_ERROR'
    
    def test_register_patient_duplicate_phone(self, transaction_conn):
        """Register patient fails with duplicate phone."""
        phone = unique_phone()
        register_patient(transaction_conn, {
            'patient_name': 'Test1',
            'gender': 'Male',
            'date_of_birth': '2000-01-01',
            'phone': phone
        })
        
        with pytest.raises(BusinessRuleError) as exc:
            register_patient(transaction_conn, {
                'patient_name': 'Test2',
                'gender': 'Male',
                'date_of_birth': '2000-01-01',
                'phone': phone
            })
        assert exc.value.code == 'UQ_PATIENT_PHONE'
    
    def test_update_patient_happy_path(self, transaction_conn):
        """Update patient details successfully."""
        # First register
        phone = unique_phone()
        result = register_patient(transaction_conn, {
            'patient_name': 'Original Name',
            'gender': 'Male',
            'date_of_birth': '2000-01-01',
            'phone': phone
        })
        patient_id = result['patient_id']
        
        # Update
        update_patient(transaction_conn, patient_id, {
            'patient_name': 'Updated Name',
            'address': 'New Address'
        })
        
        # Verify
        patient = transaction_conn.execute(
            'SELECT * FROM patient WHERE patient_id = ?', (patient_id,)
        ).fetchone()
        assert patient['patient_name'] == 'Updated Name'
        assert patient['address'] == 'New Address'
    
    def test_update_patient_not_found(self, transaction_conn):
        """Update non-existent patient fails."""
        with pytest.raises(BusinessRuleError) as exc:
            update_patient(transaction_conn, 999, {'patient_name': 'Test'})
        assert exc.value.code == 'PATIENT_NOT_FOUND'
    
    def test_delete_patient_happy_path(self, transaction_conn):
        """Delete patient with no visits succeeds."""
        phone = unique_phone()
        result = register_patient(transaction_conn, {
            'patient_name': 'To Delete',
            'gender': 'Male',
            'date_of_birth': '2000-01-01',
            'phone': phone
        })
        patient_id = result['patient_id']
        
        delete_patient(transaction_conn, patient_id)
        
        # Verify deleted
        row = transaction_conn.execute(
            'SELECT * FROM patient WHERE patient_id = ?', (patient_id,)
        ).fetchone()
        assert row is None
    
    def test_delete_patient_with_visits_blocked(self, transaction_conn):
        """Delete patient with visits fails due to FK."""
        # Patient 101 has visits in seed data
        with pytest.raises(BusinessRuleError) as exc:
            delete_patient(transaction_conn, 101)
        # SQLite FK errors don't include table info, so we get generic FK_VIOLATION
        assert exc.value.code in ('FK_VISIT_PATIENT', 'FK_VIOLATION')
    
    def test_patient_history(self, transaction_conn):
        """Get patient history with visits."""
        # Register new patient and book appointment
        phone = unique_phone()
        result = register_patient(transaction_conn, {
            'patient_name': 'History Test',
            'gender': 'Female',
            'date_of_birth': '1990-01-01',
            'phone': phone
        })
        patient_id = result['patient_id']
        
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
        book_appointment(transaction_conn, patient_id, 201, tomorrow, 'Test')
        
        history = patient_history(transaction_conn, patient_id)
        assert history['patient']['patient_id'] == patient_id
        assert len(history['visits']) >= 1
        assert 'doctor_name' in history['visits'][0]
    
    def test_patient_history_not_found(self, transaction_conn):
        """History for non-existent patient fails."""
        with pytest.raises(BusinessRuleError) as exc:
            patient_history(transaction_conn, 999)
        assert exc.value.code == 'PATIENT_NOT_FOUND'
    
    def test_get_patients(self, transaction_conn):
        """List all patients with visit count."""
        patients = get_patients(transaction_conn)
        assert len(patients) >= 12  # Seed has 12
        for p in patients:
            assert 'visit_count' in p
            assert 'patient_name' in p


# ===== Doctor Services Tests =====

class TestDoctorServices:
    """Test doctor CRUD operations."""
    
    def test_get_doctors(self, transaction_conn):
        """List all doctors."""
        doctors = get_doctors(transaction_conn)
        assert len(doctors) >= 10
        for d in doctors:
            assert 'doctor_name' in d
            assert 'department' in d
    
    def test_create_doctor_happy_path(self, transaction_conn):
        """Create a new doctor."""
        result = create_doctor(transaction_conn, {
            'doctor_name': 'Dr. Test',
            'department': 'Test Dept',
            'consultation_fee': 500,
            'shift': 'Morning'
        })
        assert 'doctor_id' in result
    
    def test_create_doctor_missing_fields(self, transaction_conn):
        """Create doctor fails with missing fields."""
        with pytest.raises(BusinessRuleError) as exc:
            create_doctor(transaction_conn, {
                'doctor_name': 'Dr. Test'
                # missing department, fee, shift
            })
        assert exc.value.code == 'VALIDATION_ERROR'
    
    def test_update_doctor(self, transaction_conn):
        """Update doctor details."""
        # Create first
        result = create_doctor(transaction_conn, {
            'doctor_name': 'Dr. Original',
            'department': 'Test',
            'consultation_fee': 500,
            'shift': 'Morning'
        })
        doctor_id = result['doctor_id']
        
        update_doctor(transaction_conn, doctor_id, {
            'doctor_name': 'Dr. Updated',
            'consultation_fee': 600
        })
        
        doctor = transaction_conn.execute(
            'SELECT * FROM doctor WHERE doctor_id = ?', (doctor_id,)
        ).fetchone()
        assert doctor['doctor_name'] == 'Dr. Updated'
        assert doctor['consultation_fee'] == 600


# ===== Medicine Services Tests =====

class TestMedicineServices:
    """Test medicine operations."""
    
    def test_get_medicines(self, transaction_conn):
        """List all medicines."""
        medicines = get_medicines(transaction_conn)
        assert len(medicines) >= 12
        for m in medicines:
            assert 'medicine_name' in m
            assert 'stock_quantity' in m
    
    def test_create_medicine(self, transaction_conn):
        """Create a new medicine."""
        result = create_medicine(transaction_conn, {
            'medicine_name': 'Test Medicine',
            'manufacturer': 'Test Pharma',
            'price_per_unit': 10.00,
            'stock_quantity': 100
        })
        assert 'medicine_id' in result
    
    def test_restock_medicine(self, transaction_conn):
        """Restock medicine increases stock."""
        # ORS Sachet (512) has stock 0
        result = restock_medicine(transaction_conn, 512, 50)
        assert result['stock_quantity'] == 50
        
        # Restock again
        result = restock_medicine(transaction_conn, 512, 25)
        assert result['stock_quantity'] == 75
    
    def test_restock_invalid_quantity(self, transaction_conn):
        """Restock with negative quantity fails."""
        with pytest.raises(BusinessRuleError) as exc:
            restock_medicine(transaction_conn, 512, -10)
        assert exc.value.code == 'VALIDATION_ERROR'
    
    def test_get_low_stock_medicines(self, transaction_conn):
        """Get medicines below threshold."""
        low_stock = get_low_stock_medicines(transaction_conn, threshold=20)
        # Should include ORS Sachet (0), Sumatriptan (5), Azithromycin (8)
        assert len(low_stock) >= 3
        names = [m['medicine_name'] for m in low_stock]
        assert 'ORS Sachet' in names


# ===== Bed Services Tests =====

class TestBedServices:
    """Test bed operations."""
    
    def test_get_beds(self, transaction_conn):
        """Get beds grouped by ward."""
        beds = get_beds(transaction_conn)
        assert 'General' in beds
        assert 'Private' in beds
        assert 'ICU' in beds
        assert 'Emergency' in beds
        
        for ward, bed_list in beds.items():
            for bed in bed_list:
                assert 'bed_id' in bed
                assert 'bed_status' in bed
                assert 'daily_charge' in bed
    
    def test_create_bed(self, transaction_conn):
        """Create a new bed."""
        result = create_bed(transaction_conn, 'General', 600)
        assert 'bed_id' in result
    
    def test_set_bed_status(self, transaction_conn):
        """Update bed status."""
        # Bed 304 is Cleaning, change to Free
        result = set_bed_status(transaction_conn, 304, 'Free')
        assert result['bed_status'] == 'Free'
        
        # Change back
        result = set_bed_status(transaction_conn, 304, 'Cleaning')
        assert result['bed_status'] == 'Cleaning'
    
    def test_set_bed_status_invalid(self, transaction_conn):
        """Invalid bed status fails."""
        with pytest.raises(BusinessRuleError) as exc:
            set_bed_status(transaction_conn, 304, 'Invalid')
        assert exc.value.code == 'VALIDATION_ERROR'


# ===== Visit/Appointment Services Tests =====

class TestVisitServices:
    """Test visit and appointment operations."""
    
    def test_get_visits(self, transaction_conn):
        """List visits with filters."""
        visits = get_visits(transaction_conn)
        assert len(visits) >= 20
        
        # Filter by status
        scheduled = get_visits(transaction_conn, status='Scheduled')
        assert all(v['visit_status'] == 'Scheduled' for v in scheduled)
        
        # Filter by type
        emergencies = get_visits(transaction_conn, type='Emergency')
        assert all(v['visit_type'] == 'Emergency' for v in emergencies)
        
        # Filter by patient
        patient_visits = get_visits(transaction_conn, patient_id=101)
        assert all(v['patient_id'] == 101 for v in patient_visits)
    
    def test_get_visit_summary(self, transaction_conn):
        """Get complete visit summary."""
        # Use visit 407 from seed (has bed, prescriptions, bill)
        summary = get_visit_summary(transaction_conn, 407)
        assert 'visit' in summary
        assert 'patient' in summary
        assert 'doctor' in summary
        assert 'bed' in summary
        assert 'prescriptions' in summary
        assert 'medicine_cost' in summary
        assert 'days_stayed' in summary
        assert 'bill' in summary
        
        # Check specific values for visit 407
        assert summary['visit']['visit_id'] == 407
        assert summary['patient']['patient_name'] == 'Rahul Verma'
        assert summary['doctor']['doctor_name'] == 'Dr. Arvind Menon'
        assert summary['bed']['bed_id'] == 307
        assert len(summary['prescriptions']) >= 1
        assert summary['days_stayed'] > 0
        assert summary['bill'] is not None
    
    def test_get_visit_summary_not_found(self, transaction_conn):
        """Summary for non-existent visit fails."""
        with pytest.raises(BusinessRuleError) as exc:
            get_visit_summary(transaction_conn, 99999)
        assert exc.value.code == 'VISIT_NOT_FOUND'


# ===== Appointment Services Tests =====

class TestAppointmentServices:
    """Test appointment booking and cancellation."""
    
    def test_book_appointment_happy_path(self, transaction_conn):
        """Book appointment successfully."""
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
        
        result = book_appointment(transaction_conn, 101, 201, tomorrow, 'Test complaint')
        assert 'visit_id' in result
        assert result['visit_id'] > 420  # After seed
        
        # Verify visit created
        visit = transaction_conn.execute(
            'SELECT * FROM visit WHERE visit_id = ?', (result['visit_id'],)
        ).fetchone()
        assert visit['visit_type'] == 'Appointment'
        assert visit['visit_status'] == 'Scheduled'
        assert visit['visit_datetime'] == tomorrow
    
    def test_book_appointment_patient_not_found(self, transaction_conn):
        """Book appointment fails for non-existent patient."""
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
        
        with pytest.raises(BusinessRuleError) as exc:
            book_appointment(transaction_conn, 99999, 201, tomorrow, 'Test')
        assert exc.value.code == 'PATIENT_NOT_FOUND'
    
    def test_book_appointment_doctor_not_found(self, transaction_conn):
        """Book appointment fails for non-existent doctor."""
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
        
        with pytest.raises(BusinessRuleError) as exc:
            book_appointment(transaction_conn, 101, 99999, tomorrow, 'Test')
        assert exc.value.code == 'DOCTOR_NOT_FOUND'
    
    def test_book_appointment_slot_in_past(self, transaction_conn):
        """Book appointment in past fails."""
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
        
        with pytest.raises(BusinessRuleError) as exc:
            book_appointment(transaction_conn, 101, 201, yesterday, 'Test')
        assert exc.value.code == 'SLOT_IN_PAST'
    
    def test_book_appointment_slot_taken(self, transaction_conn):
        """Book appointment with taken slot fails."""
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
        
        # First booking
        book_appointment(transaction_conn, 101, 201, tomorrow, 'First')
        
        # Second booking same doctor, same time
        with pytest.raises(BusinessRuleError) as exc:
            book_appointment(transaction_conn, 102, 201, tomorrow, 'Second')
        assert exc.value.code == 'SLOT_TAKEN'
    
    def test_cancel_appointment_happy_path(self, transaction_conn):
        """Cancel scheduled appointment."""
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
        
        result = book_appointment(transaction_conn, 101, 201, tomorrow, 'Test')
        visit_id = result['visit_id']
        
        cancel_appointment(transaction_conn, visit_id)
        
        visit = transaction_conn.execute(
            'SELECT visit_status FROM visit WHERE visit_id = ?', (visit_id,)
        ).fetchone()
        assert visit['visit_status'] == 'Cancelled'
    
    def test_cancel_appointment_not_scheduled_fails(self, transaction_conn):
        """Cancel non-scheduled visit fails."""
        # Visit 401 is Discharged
        with pytest.raises(BusinessRuleError) as exc:
            cancel_appointment(transaction_conn, 401)
        assert exc.value.code == 'BAD_STATUS'
    
    def test_cancel_appointment_not_found(self, transaction_conn):
        """Cancel non-existent visit fails."""
        with pytest.raises(BusinessRuleError) as exc:
            cancel_appointment(transaction_conn, 99999)
        assert exc.value.code == 'VISIT_NOT_FOUND'
    
    def test_start_treatment_happy_path(self, transaction_conn):
        """Start treatment from Waiting/Scheduled."""
        # Create a scheduled visit
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
        result = book_appointment(transaction_conn, 101, 201, tomorrow, 'Test')
        visit_id = result['visit_id']
        
        result = start_treatment(transaction_conn, visit_id)
        assert result['visit_status'] == 'Under Treatment'
        
        # Doctor should be Busy now
        doctor = transaction_conn.execute(
            'SELECT availability_status FROM doctor WHERE doctor_id = 201'
        ).fetchone()
        assert doctor['availability_status'] == 'Busy'
    
    def test_start_treatment_from_scheduled(self, transaction_conn):
        """Start treatment from Scheduled also works."""
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
        result = book_appointment(transaction_conn, 101, 202, tomorrow, 'Test')
        visit_id = result['visit_id']
        
        result = start_treatment(transaction_conn, visit_id)
        assert result['visit_status'] == 'Under Treatment'
    
    def test_start_treatment_wrong_status_fails(self, transaction_conn):
        """Start treatment from Discharged fails."""
        with pytest.raises(BusinessRuleError) as exc:
            start_treatment(transaction_conn, 401)  # Discharged
        assert exc.value.code == 'BAD_STATUS'


# ===== Emergency Services Tests =====

class TestEmergencyServices:
    """Test emergency registration and queue."""
    
    def test_register_emergency_happy_path(self, transaction_conn):
        """Register emergency successfully."""
        result = register_emergency(transaction_conn, 101, 'Chest pain', 1)
        assert 'visit_id' in result
        assert 'doctor_id' in result
        assert 'doctor_name' in result
        assert result['doctor_id'] in [203, 207]  # Emergency doctors
    
    def test_register_emergency_patient_not_found(self, transaction_conn):
        """Emergency for non-existent patient fails."""
        with pytest.raises(BusinessRuleError) as exc:
            register_emergency(transaction_conn, 99999, 'Chest pain', 1)
        assert exc.value.code == 'PATIENT_NOT_FOUND'
    
    def test_register_emergency_bad_triage(self, transaction_conn):
        """Emergency with invalid triage fails."""
        with pytest.raises(BusinessRuleError) as exc:
            register_emergency(transaction_conn, 101, 'Chest pain', 5)
        assert exc.value.code == 'BAD_TRIAGE'
        
        with pytest.raises(BusinessRuleError) as exc:
            register_emergency(transaction_conn, 101, 'Chest pain', 0)
        assert exc.value.code == 'BAD_TRIAGE'
    
    def test_emergency_queue(self, transaction_conn):
        """Get emergency queue with cursor output."""
        queue = emergency_queue(transaction_conn)
        assert 'rows' in queue
        assert 'console_lines' in queue
        assert len(queue['console_lines']) > 0
        
        # Queue should be ordered by triage then datetime
        for i in range(len(queue['rows']) - 1):
            curr = queue['rows'][i]
            next_row = queue['rows'][i + 1]
            if curr['triage_level'] != next_row['triage_level']:
                assert curr['triage_level'] < next_row['triage_level']
            else:
                assert curr['visit_datetime'] <= next_row['visit_datetime']


# ===== Bed Allotment Tests =====

class TestBedAllotment:
    """Test bed allotment and discharge."""
    
    def test_allot_bed_happy_path(self, transaction_conn):
        """Allot bed to visit."""
        # Create a waiting visit
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
        result = book_appointment(transaction_conn, 101, 201, tomorrow, 'Test')
        visit_id = result['visit_id']
        
        # Start treatment first (required for admission flow)
        start_treatment(transaction_conn, visit_id)
        
        # Allot ICU bed (bed 307 is free)
        result = allot_bed(transaction_conn, visit_id, 'ICU')
        assert 'bed_id' in result
        assert result['bed_id'] == 307
        
        # Verify visit updated
        visit = transaction_conn.execute(
            'SELECT * FROM visit WHERE visit_id = ?', (visit_id,)
        ).fetchone()
        assert visit['bed_id'] == 307
        assert visit['visit_status'] == 'Admitted'
        assert visit['admit_time'] is not None
        
        # Bed should be Occupied
        bed = transaction_conn.execute(
            'SELECT bed_status FROM bed WHERE bed_id = 307'
        ).fetchone()
        assert bed['bed_status'] == 'Occupied'
        
        # Doctor should be Available (left Under Treatment)
        doctor = transaction_conn.execute(
            'SELECT availability_status FROM doctor WHERE doctor_id = 201'
        ).fetchone()
        assert doctor['availability_status'] == 'Available'
    
    def test_allot_bed_visit_not_found(self, transaction_conn):
        """Allot bed for non-existent visit fails."""
        with pytest.raises(BusinessRuleError) as exc:
            allot_bed(transaction_conn, 99999, 'ICU')
        assert exc.value.code == 'VISIT_NOT_FOUND'
    
    def test_allot_bed_closed_visit_fails(self, transaction_conn):
        """Allot bed for cancelled visit fails."""
        with pytest.raises(BusinessRuleError) as exc:
            allot_bed(transaction_conn, 412, 'ICU')  # Cancelled
        assert exc.value.code == 'VISIT_CLOSED'
    
    def test_allot_bed_already_has_bed_fails(self, transaction_conn):
        """Allot bed when visit already has bed fails."""
        with pytest.raises(BusinessRuleError) as exc:
            allot_bed(transaction_conn, 413, 'Private')  # Already has bed 305
        assert exc.value.code == 'ALREADY_HAS_BED'
    
    def test_allot_bed_no_free_bed_fails(self, transaction_conn):
        """Allot bed when no free beds fails."""
        # ICU bed 307 is free, 308 is occupied
        # Book two visits with different times to use both
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
        tomorrow_2 = (datetime.now() + timedelta(days=1, hours=1)).strftime('%Y-%m-%d %H:%M:%S')
        
        result1 = book_appointment(transaction_conn, 101, 201, tomorrow, 'Test1')
        start_treatment(transaction_conn, result1['visit_id'])
        allot_bed(transaction_conn, result1['visit_id'], 'ICU')  # Gets 307
        
        result2 = book_appointment(transaction_conn, 102, 201, tomorrow_2, 'Test2')
        start_treatment(transaction_conn, result2['visit_id'])
        
        with pytest.raises(BusinessRuleError) as exc:
            allot_bed(transaction_conn, result2['visit_id'], 'ICU')
        assert exc.value.code == 'NO_FREE_BED'
    
    def test_discharge_patient_happy_path(self, transaction_conn):
        """Discharge patient successfully."""
        # Create and admit a visit
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
        result = book_appointment(transaction_conn, 101, 201, tomorrow, 'Test')
        visit_id = result['visit_id']
        
        start_treatment(transaction_conn, visit_id)
        allot_bed(transaction_conn, visit_id, 'ICU')
        
        # Discharge
        result = discharge_patient(transaction_conn, visit_id)
        assert result['visit_id'] == visit_id
        assert result['bed_id'] == 307
        assert result['days_stayed'] >= 1
        
        # Verify visit discharged
        visit = transaction_conn.execute(
            'SELECT * FROM visit WHERE visit_id = ?', (visit_id,)
        ).fetchone()
        assert visit['visit_status'] == 'Discharged'
        assert visit['discharge_time'] is not None
        
        # Bed should be Cleaning
        bed = transaction_conn.execute(
            'SELECT bed_status FROM bed WHERE bed_id = 307'
        ).fetchone()
        assert bed['bed_status'] == 'Cleaning'
    
    def test_discharge_patient_wrong_status_fails(self, transaction_conn):
        """Discharge from Scheduled fails."""
        with pytest.raises(BusinessRuleError) as exc:
            discharge_patient(transaction_conn, 419)  # Scheduled
        assert exc.value.code == 'BAD_STATUS'


# ===== Pharmacy Tests =====

class TestPharmacyServices:
    """Test prescription operations."""
    
    def test_get_prescriptions(self, transaction_conn):
        """Get prescriptions for a visit."""
        prescriptions = get_prescriptions(transaction_conn, 407)
        assert len(prescriptions) >= 2  # Visit 407 has 2 prescriptions
        for p in prescriptions:
            assert 'medicine_name' in p
            assert 'price_per_unit' in p
    
    def test_add_prescription_happy_path(self, transaction_conn):
        """Add prescription reduces stock."""
        # Create a visit
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
        result = book_appointment(transaction_conn, 101, 201, tomorrow, 'Test')
        visit_id = result['visit_id']
        
        # Get initial stock of Aspirin 75mg (506)
        initial_stock = transaction_conn.execute(
            'SELECT stock_quantity FROM medicine WHERE medicine_id = 506'
        ).fetchone()['stock_quantity']
        
        # Add prescription
        result = add_prescription(transaction_conn, visit_id, 506, '1-0-0', 10, 10)
        assert 'prescription_id' in result
        assert result['stock_after'] == initial_stock - 10
    
    def test_add_prescription_insufficient_stock(self, transaction_conn):
        """Add prescription with insufficient stock fails."""
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
        result = book_appointment(transaction_conn, 101, 201, tomorrow, 'Test')
        visit_id = result['visit_id']
        
        # ORS Sachet (512) has stock 0
        with pytest.raises(BusinessRuleError) as exc:
            add_prescription(transaction_conn, visit_id, 512, '1-0-0', 5, 5)
        assert exc.value.code == 'INSUFFICIENT_STOCK'
    
    def test_add_prescription_cancelled_visit_fails(self, transaction_conn):
        """Add prescription to cancelled visit fails."""
        with pytest.raises(BusinessRuleError) as exc:
            add_prescription(transaction_conn, 412, 506, '1-0-0', 10, 10)  # Cancelled
        assert exc.value.code == 'VISIT_CLOSED'
    
    def test_delete_prescription_happy_path(self, transaction_conn):
        """Delete prescription restores stock."""
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
        result = book_appointment(transaction_conn, 101, 201, tomorrow, 'Test')
        visit_id = result['visit_id']
        
        # Add prescription
        add_result = add_prescription(transaction_conn, visit_id, 506, '1-0-0', 10, 10)
        prescription_id = add_result['prescription_id']
        stock_after_add = add_result['stock_after']
        
        # Delete it
        del_result = delete_prescription(transaction_conn, prescription_id)
        assert del_result['stock_after'] == stock_after_add + 10


# ===== Billing Tests =====

class TestBillingServices:
    """Test billing operations."""
    
    def test_generate_bill_happy_path(self, transaction_conn):
        """Generate bill for discharged visit."""
        # Create, admit, discharge a visit
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
        result = book_appointment(transaction_conn, 101, 201, tomorrow, 'Test')
        visit_id = result['visit_id']
        
        start_treatment(transaction_conn, visit_id)
        allot_bed(transaction_conn, visit_id, 'ICU')
        discharge_patient(transaction_conn, visit_id)
        
        # Generate bill
        result = generate_bill(transaction_conn, visit_id)
        assert 'bill_id' in result
        assert result['consultation_charge'] == 800  # Dr. Rajesh Kumar fee
        assert result['medicine_charge'] >= 0
        assert result['bed_charge'] > 0  # ICU daily_charge * days
        assert result['total_amount'] == (
            result['consultation_charge'] + result['medicine_charge'] + result['bed_charge']
        )
        
        # Verify bill in database
        bill = transaction_conn.execute(
            'SELECT * FROM bill WHERE visit_id = ?', (visit_id,)
        ).fetchone()
        assert bill['payment_status'] == 'Pending'
    
    def test_generate_bill_not_discharged_fails(self, transaction_conn):
        """Generate bill for non-discharged visit fails."""
        with pytest.raises(BusinessRuleError) as exc:
            generate_bill(transaction_conn, 419)  # Scheduled
        assert exc.value.code == 'NOT_DISCHARGED'
    
    def test_generate_bill_duplicate_fails(self, transaction_conn):
        """Generate bill for visit that already has bill fails."""
        with pytest.raises(BusinessRuleError) as exc:
            generate_bill(transaction_conn, 401)  # Already has bill 701
        assert exc.value.code == 'BILL_EXISTS'
    
    def test_get_bills(self, transaction_conn):
        """List bills with optional status filter."""
        all_bills = get_bills(transaction_conn)
        assert len(all_bills) >= 11
        
        pending = get_bills(transaction_conn, status='Pending')
        assert all(b['payment_status'] == 'Pending' for b in pending)
        
        paid = get_bills(transaction_conn, status='Paid')
        assert all(b['payment_status'] == 'Paid' for b in paid)
    
    def test_get_pending_bills(self, transaction_conn):
        """Get pending bills with cursor output."""
        result = get_pending_bills(transaction_conn)
        assert 'rows' in result
        assert 'console_lines' in result
        assert 'count' in result
        assert 'total' in result
        assert result['count'] >= 4  # Seed has 4 pending
        assert len(result['console_lines']) > 0
    
    def test_pay_bill_happy_path(self, transaction_conn):
        """Pay bill successfully."""
        # Use pending bill 706 (visit 406)
        result = pay_bill(transaction_conn, 706, 'Cash')
        assert result['bill_id'] == 706
        assert result['payment_status'] == 'Paid'
        
        bill = transaction_conn.execute(
            'SELECT * FROM bill WHERE bill_id = 706'
        ).fetchone()
        assert bill['payment_mode'] == 'Cash'
        assert bill['payment_status'] == 'Paid'
    
    def test_pay_bill_invalid_mode_fails(self, transaction_conn):
        """Pay bill with invalid mode fails."""
        with pytest.raises(BusinessRuleError) as exc:
            pay_bill(transaction_conn, 706, 'Invalid')
        assert exc.value.code == 'VALIDATION_ERROR'
    
    def test_pay_bill_already_paid_fails(self, transaction_conn):
        """Pay already paid bill fails."""
        with pytest.raises(BusinessRuleError) as exc:
            pay_bill(transaction_conn, 701, 'Cash')  # Already paid
        assert exc.value.code == 'BAD_STATUS'


# ===== Lookups and Dashboard Tests =====

class TestLookupsAndDashboard:
    """Test lookup and dashboard services."""
    
    def test_get_lookups(self, transaction_conn):
        """Get lookup data for forms."""
        lookups = get_lookups(transaction_conn)
        assert 'patients' in lookups
        assert 'doctors' in lookups
        assert 'medicines' in lookups
        assert 'wards' in lookups
        assert 'departments' in lookups
        
        assert len(lookups['patients']) >= 12
        assert len(lookups['doctors']) >= 10
        assert len(lookups['medicines']) >= 12
        assert len(lookups['wards']) == 4
        assert len(lookups['departments']) >= 8
    
    def test_get_dashboard(self, transaction_conn):
        """Get dashboard KPIs."""
        dashboard = get_dashboard(transaction_conn)
        assert 'kpis' in dashboard
        assert 'bed_occupancy' in dashboard
        assert 'triage' in dashboard
        assert 'low_stock' in dashboard
        assert 'recent_audit' in dashboard
        
        kpis = dashboard['kpis']
        assert kpis['patients'] >= 12
        assert kpis['free_beds'] >= 0
        assert isinstance(kpis['pending_amount'], (int, float))


# ===== Transaction Atomicity Tests =====

class TestTransactionAtomicity:
    """Test that operations are atomic and rollback on failure."""
    
    def test_appointment_rollback_on_conflict(self, transaction_conn):
        """Failed appointment booking rolls back."""
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
        
        # First booking succeeds
        book_appointment(transaction_conn, 101, 201, tomorrow, 'First')
        
        # Second booking fails, should rollback
        try:
            book_appointment(transaction_conn, 102, 201, tomorrow, 'Second')
        except BusinessRuleError:
            pass
        
        # Count visits for doctor 201 at that time
        count = transaction_conn.execute('''
            SELECT COUNT(*) FROM visit 
            WHERE doctor_id = 201 AND visit_datetime = ? AND visit_status <> 'Cancelled'
        ''', (tomorrow,)).fetchone()[0]
        
        # Only the first booking should exist
        assert count == 1
    
    def test_prescription_rollback_on_insufficient_stock(self, transaction_conn):
        """Failed prescription rolls back stock change."""
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
        result = book_appointment(transaction_conn, 101, 201, tomorrow, 'Test')
        visit_id = result['visit_id']
        
        # Get initial stock of ORS Sachet
        initial_stock = transaction_conn.execute(
            'SELECT stock_quantity FROM medicine WHERE medicine_id = 512'
        ).fetchone()['stock_quantity']
        
        # Try to prescribe more than stock
        try:
            add_prescription(transaction_conn, visit_id, 512, '1-0-0', 5, 5)
        except BusinessRuleError:
            pass
        
        # Stock should be unchanged
        final_stock = transaction_conn.execute(
            'SELECT stock_quantity FROM medicine WHERE medicine_id = 512'
        ).fetchone()['stock_quantity']
        assert final_stock == initial_stock
    
    def test_bill_generation_rollback(self, transaction_conn):
        """Failed bill generation rolls back."""
        # Use a discharged visit that already has a bill (401 -> bill 701)
        initial_bill_count = transaction_conn.execute(
            'SELECT COUNT(*) FROM bill'
        ).fetchone()[0]
        
        try:
            generate_bill(transaction_conn, 401)
        except BusinessRuleError:
            pass
        
        # Bill count should be unchanged
        final_bill_count = transaction_conn.execute(
            'SELECT COUNT(*) FROM bill'
        ).fetchone()[0]
        assert final_bill_count == initial_bill_count


if __name__ == '__main__':
    pytest.main([__file__, '-v'])