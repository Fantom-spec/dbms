"""
Tests for database schema: row counts, constraints, indexes, and violation statements.
"""
import os
import pytest
import sqlite3
from pathlib import Path


@pytest.fixture(scope="session")
def db_connection():
    """Create a fresh database for testing."""
    # Initialize database
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from db.init_db import init_database
    init_database()
    
    db_path = Path(__file__).parent.parent / 'hospital.db'
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    conn.execute('PRAGMA busy_timeout = 5000')
    
    yield conn
    conn.close()


class TestSchemaRowCounts:
    """Test that fresh database has golden row counts."""
    
    EXPECTED_COUNTS = {
        'patient': 12,
        'doctor': 10,
        'bed': 12,
        'medicine': 12,
        'visit': 20,
        'prescription': 22,
        'bill': 11,
        'audit_log': 12,
    }
    
    def test_row_counts(self, db_connection):
        for table, expected in self.EXPECTED_COUNTS.items():
            count = db_connection.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
            assert count == expected, f'{table}: expected {expected}, got {count}'


class TestAutoincrementValues:
    """Test that autoincrement sequences start at correct values after seed."""
    
    EXPECTED_SEQ = {
        'patient': 113,
        'visit': 421,
        'prescription': 623,
        'bill': 712,
        'audit_log': 13,
    }
    
    def test_next_ids(self, db_connection):
        for table, expected in self.EXPECTED_SEQ.items():
            seq = db_connection.execute(
                'SELECT seq FROM sqlite_sequence WHERE name = ?', (table,)
            ).fetchone()
            actual = seq[0] + 1 if seq else 1
            assert actual == expected, f'{table}: expected next id {expected}, got {actual}'


class TestConstraints:
    """Test that constraints are properly defined and enforced."""
    
    def test_unique_phone(self, db_connection):
        """uq_pat_phone: phone must be unique."""
        with pytest.raises(sqlite3.IntegrityError) as exc:
            db_connection.execute(
                'INSERT INTO patient (patient_name, phone, gender, date_of_birth) VALUES (?, ?, ?, ?)',
                ('Test', '9876500101', 'Male', '2000-01-01')
            )
        assert 'UNIQUE' in str(exc.value) or 'uq_pat_phone' in str(exc.value)
    
    def test_patient_gender_check(self, db_connection):
        """chk_pat_gender: gender must be Male, Female, or Other."""
        with pytest.raises(sqlite3.IntegrityError) as exc:
            db_connection.execute(
                'INSERT INTO patient (patient_name, phone, gender, date_of_birth) VALUES (?, ?, ?, ?)',
                ('Test', '9876500999', 'Invalid', '2000-01-01')
            )
        assert 'CHECK' in str(exc.value) or 'chk_pat_gender' in str(exc.value)
    
    def test_patient_phone_format(self, db_connection):
        """chk_pat_phone: phone must be 10 digits."""
        with pytest.raises(sqlite3.IntegrityError) as exc:
            db_connection.execute(
                'INSERT INTO patient (patient_name, phone, gender, date_of_birth) VALUES (?, ?, ?, ?)',
                ('Test', '98765ABCDE', 'Male', '2000-01-01')
            )
        assert 'CHECK' in str(exc.value) or 'chk_pat_phone' in str(exc.value)
    
    def test_patient_blood_group(self, db_connection):
        """chk_pat_blood: blood group must be valid."""
        with pytest.raises(sqlite3.IntegrityError) as exc:
            db_connection.execute(
                'INSERT INTO patient (patient_name, phone, gender, date_of_birth, blood_group) VALUES (?, ?, ?, ?, ?)',
                ('Test', '9876500999', 'Male', '2000-01-01', 'X+')
            )
        assert 'CHECK' in str(exc.value) or 'chk_pat_blood' in str(exc.value)
    
    def test_doctor_fee_positive(self, db_connection):
        """chk_doc_fee: consultation_fee > 0."""
        with pytest.raises(sqlite3.IntegrityError) as exc:
            db_connection.execute(
                'INSERT INTO doctor (doctor_name, department, consultation_fee, shift) VALUES (?, ?, ?, ?)',
                ('Test', 'Test', 0, 'Morning')
            )
        assert 'CHECK' in str(exc.value) or 'chk_doc_fee' in str(exc.value)
    
    def test_doctor_shift(self, db_connection):
        """chk_doc_shift: shift must be Morning, Evening, or Night."""
        with pytest.raises(sqlite3.IntegrityError) as exc:
            db_connection.execute(
                'INSERT INTO doctor (doctor_name, department, consultation_fee, shift) VALUES (?, ?, ?, ?)',
                ('Test', 'Test', 500, 'Invalid')
            )
        assert 'CHECK' in str(exc.value) or 'chk_doc_shift' in str(exc.value)
    
    def test_doctor_availability(self, db_connection):
        """chk_doc_avail: availability_status must be Available or Busy."""
        with pytest.raises(sqlite3.IntegrityError) as exc:
            db_connection.execute(
                'INSERT INTO doctor (doctor_name, department, consultation_fee, shift, availability_status) VALUES (?, ?, ?, ?, ?)',
                ('Test', 'Test', 500, 'Morning', 'Invalid')
            )
        assert 'CHECK' in str(exc.value) or 'chk_doc_avail' in str(exc.value)
    
    def test_bed_ward_type(self, db_connection):
        """chk_bed_ward: ward_type must be valid."""
        with pytest.raises(sqlite3.IntegrityError) as exc:
            db_connection.execute(
                'INSERT INTO bed (ward_type, bed_status, daily_charge) VALUES (?, ?, ?)',
                ('Invalid', 'Free', 500)
            )
        assert 'CHECK' in str(exc.value) or 'chk_bed_ward' in str(exc.value)
    
    def test_bed_status(self, db_connection):
        """chk_bed_stat: bed_status must be Free, Occupied, or Cleaning."""
        with pytest.raises(sqlite3.IntegrityError) as exc:
            db_connection.execute(
                'INSERT INTO bed (ward_type, bed_status, daily_charge) VALUES (?, ?, ?)',
                ('General', 'Invalid', 500)
            )
        assert 'CHECK' in str(exc.value) or 'chk_bed_stat' in str(exc.value)
    
    def test_bed_charge_positive(self, db_connection):
        """chk_bed_chg: daily_charge > 0."""
        with pytest.raises(sqlite3.IntegrityError) as exc:
            db_connection.execute(
                'INSERT INTO bed (ward_type, bed_status, daily_charge) VALUES (?, ?, ?)',
                ('General', 'Free', 0)
            )
        assert 'CHECK' in str(exc.value) or 'chk_bed_chg' in str(exc.value)
    
    def test_medicine_price_positive(self, db_connection):
        """chk_med_price: price_per_unit > 0."""
        with pytest.raises(sqlite3.IntegrityError) as exc:
            db_connection.execute(
                'INSERT INTO medicine (medicine_name, price_per_unit, stock_quantity) VALUES (?, ?, ?)',
                ('Test', 0, 10)
            )
        assert 'CHECK' in str(exc.value) or 'chk_med_price' in str(exc.value)
    
    def test_medicine_stock_nonnegative(self, db_connection):
        """chk_med_stock: stock_quantity >= 0."""
        with pytest.raises(sqlite3.IntegrityError) as exc:
            db_connection.execute(
                'INSERT INTO medicine (medicine_name, price_per_unit, stock_quantity) VALUES (?, ?, ?)',
                ('Test', 5.00, -1)
            )
        assert 'CHECK' in str(exc.value) or 'chk_med_stock' in str(exc.value)
    
    def test_visit_type(self, db_connection):
        """chk_visit_type: visit_type must be Appointment or Emergency."""
        with pytest.raises(sqlite3.IntegrityError) as exc:
            db_connection.execute(
                '''INSERT INTO visit (patient_id, doctor_id, visit_type, visit_datetime, visit_status) 
                   VALUES (?, ?, ?, ?, ?)''',
                (101, 201, 'Invalid', '2026-10-27 10:00:00', 'Scheduled')
            )
        assert 'CHECK' in str(exc.value) or 'chk_visit_type' in str(exc.value)
    
    def test_visit_status(self, db_connection):
        """chk_visit_status: visit_status must be valid."""
        with pytest.raises(sqlite3.IntegrityError) as exc:
            db_connection.execute(
                '''INSERT INTO visit (patient_id, doctor_id, visit_type, visit_datetime, visit_status) 
                   VALUES (?, ?, ?, ?, ?)''',
                (101, 201, 'Appointment', '2026-10-27 10:00:00', 'Invalid')
            )
        assert 'CHECK' in str(exc.value) or 'chk_visit_status' in str(exc.value)
    
    def test_visit_triage_range(self, db_connection):
        """chk_visit_range: triage_level must be 1-4."""
        with pytest.raises(sqlite3.IntegrityError) as exc:
            db_connection.execute(
                '''INSERT INTO visit (patient_id, doctor_id, visit_type, visit_datetime, triage_level, visit_status) 
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (101, 203, 'Emergency', '2026-10-27 10:00:00', 5, 'Waiting')
            )
        assert 'CHECK' in str(exc.value) or 'chk_visit_range' in str(exc.value)
    
    def test_visit_triage_match(self, db_connection):
        """chk_visit_triage: triage required for Emergency, NULL for Appointment."""
        # Appointment with triage should fail
        with pytest.raises(sqlite3.IntegrityError) as exc:
            db_connection.execute(
                '''INSERT INTO visit (patient_id, doctor_id, visit_type, visit_datetime, triage_level, visit_status) 
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (101, 201, 'Appointment', '2026-10-27 10:00:00', 1, 'Scheduled')
            )
        assert 'CHECK' in str(exc.value) or 'chk_visit_triage' in str(exc.value)
        
        # Emergency without triage should fail
        with pytest.raises(sqlite3.IntegrityError) as exc:
            db_connection.execute(
                '''INSERT INTO visit (patient_id, doctor_id, visit_type, visit_datetime, triage_level, visit_status) 
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (101, 203, 'Emergency', '2026-10-27 10:00:00', None, 'Waiting')
            )
        assert 'CHECK' in str(exc.value) or 'chk_visit_triage' in str(exc.value)
    
    def test_visit_admitted_requires_bed(self, db_connection):
        """chk_visit_bed: Admitted visits must have bed_id."""
        with pytest.raises(sqlite3.IntegrityError) as exc:
            db_connection.execute(
                '''INSERT INTO visit (patient_id, doctor_id, visit_type, visit_datetime, visit_status, bed_id) 
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (101, 201, 'Appointment', '2026-10-27 10:00:00', 'Admitted', None)
            )
        assert 'CHECK' in str(exc.value) or 'chk_visit_bed' in str(exc.value)
    
    def test_visit_discharge_after_admit(self, db_connection):
        """chk_visit_disch: discharge_time >= admit_time."""
        with pytest.raises(sqlite3.IntegrityError) as exc:
            db_connection.execute(
                '''INSERT INTO visit (patient_id, doctor_id, visit_type, visit_datetime, visit_status, 
                   admit_time, discharge_time) VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (101, 201, 'Appointment', '2026-10-27 10:00:00', 'Discharged',
                 '2026-10-27 12:00:00', '2026-10-27 10:00:00')
            )
        assert 'CHECK' in str(exc.value) or 'chk_visit_disch' in str(exc.value)
    
    def test_prescription_days_positive(self, db_connection):
        """chk_presc_days: duration_days > 0."""
        with pytest.raises(sqlite3.IntegrityError) as exc:
            db_connection.execute(
                'INSERT INTO prescription (visit_id, medicine_id, dosage, duration_days, quantity) VALUES (?, ?, ?, ?, ?)',
                (401, 501, '1-0-0', 0, 5)
            )
        assert 'CHECK' in str(exc.value) or 'chk_presc_days' in str(exc.value)
    
    def test_prescription_qty_positive(self, db_connection):
        """chk_presc_qty: quantity > 0."""
        with pytest.raises(sqlite3.IntegrityError) as exc:
            db_connection.execute(
                'INSERT INTO prescription (visit_id, medicine_id, dosage, duration_days, quantity) VALUES (?, ?, ?, ?, ?)',
                (401, 501, '1-0-0', 5, 0)
            )
        assert 'CHECK' in str(exc.value) or 'chk_presc_qty' in str(exc.value)
    
    def test_bill_payment_mode(self, db_connection):
        """chk_bill_mode: payment_mode must be Cash, Card, or UPI."""
        with pytest.raises(sqlite3.IntegrityError) as exc:
            db_connection.execute(
                '''INSERT INTO bill (visit_id, total_amount, payment_mode, payment_status) 
                   VALUES (?, ?, ?, ?)''',
                (401, 500, 'Invalid', 'Paid')
            )
        assert 'CHECK' in str(exc.value) or 'chk_bill_mode' in str(exc.value)
    
    def test_bill_payment_status(self, db_connection):
        """chk_bill_stat: payment_status must be Paid or Pending."""
        with pytest.raises(sqlite3.IntegrityError) as exc:
            db_connection.execute(
                '''INSERT INTO bill (visit_id, total_amount, payment_mode, payment_status) 
                   VALUES (?, ?, ?, ?)''',
                (401, 500, 'Cash', 'Invalid')
            )
        assert 'CHECK' in str(exc.value) or 'chk_bill_stat' in str(exc.value)
    
    def test_bill_amounts_nonnegative(self, db_connection):
        """chk_bill_amt: charges >= 0."""
        with pytest.raises(sqlite3.IntegrityError) as exc:
            db_connection.execute(
                '''INSERT INTO bill (visit_id, consultation_charge, medicine_charge, bed_charge, total_amount, payment_status) 
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (401, -100, 0, 0, -100, 'Pending')
            )
        assert 'CHECK' in str(exc.value) or 'chk_bill_amt' in str(exc.value)
    
    def test_bill_total_matches_sum(self, db_connection):
        """chk_bill_total: total = consultation + medicine + bed."""
        with pytest.raises(sqlite3.IntegrityError) as exc:
            db_connection.execute(
                '''INSERT INTO bill (visit_id, consultation_charge, medicine_charge, bed_charge, total_amount, payment_status) 
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (401, 500, 50, 0, 600, 'Pending')  # 500+50+0 != 600
            )
        assert 'CHECK' in str(exc.value) or 'chk_bill_total' in str(exc.value)
    
    def test_bill_paid_requires_mode(self, db_connection):
        """chk_bill_paid: Paid bills must have payment_mode."""
        with pytest.raises(sqlite3.IntegrityError) as exc:
            db_connection.execute(
                '''INSERT INTO bill (visit_id, total_amount, payment_mode, payment_status) 
                   VALUES (?, ?, ?, ?)''',
                (401, 500, None, 'Paid')
            )
        assert 'CHECK' in str(exc.value) or 'chk_bill_paid' in str(exc.value)
    
    def test_audit_action_type(self, db_connection):
        """chk_audit_act: action_type must be INSERT, UPDATE, or DELETE."""
        with pytest.raises(sqlite3.IntegrityError) as exc:
            db_connection.execute(
                'INSERT INTO audit_log (table_name, action_type, record_id, changed_by) VALUES (?, ?, ?, ?)',
                ('TEST', 'INVALID', 1, 'TEST')
            )
        assert 'CHECK' in str(exc.value) or 'chk_audit_act' in str(exc.value)


class TestForeignKeys:
    """Test foreign key constraints."""
    
    def test_visit_patient_fk(self, db_connection):
        """fk_visit_patient: patient must exist."""
        with pytest.raises(sqlite3.IntegrityError) as exc:
            db_connection.execute(
                '''INSERT INTO visit (patient_id, doctor_id, visit_type, visit_datetime, visit_status) 
                   VALUES (?, ?, ?, ?, ?)''',
                (999, 201, 'Appointment', '2026-10-27 10:00:00', 'Scheduled')
            )
        assert 'FOREIGN KEY' in str(exc.value) or 'fk_visit_patient' in str(exc.value)
    
    def test_visit_doctor_fk(self, db_connection):
        """fk_visit_doctor: doctor must exist."""
        with pytest.raises(sqlite3.IntegrityError) as exc:
            db_connection.execute(
                '''INSERT INTO visit (patient_id, doctor_id, visit_type, visit_datetime, visit_status) 
                   VALUES (?, ?, ?, ?, ?)''',
                (101, 999, 'Appointment', '2026-10-27 10:00:00', 'Scheduled')
            )
        assert 'FOREIGN KEY' in str(exc.value) or 'fk_visit_doctor' in str(exc.value)
    
    def test_visit_bed_fk(self, db_connection):
        """fk_visit_bed: bed must exist if provided."""
        with pytest.raises(sqlite3.IntegrityError) as exc:
            db_connection.execute(
                '''INSERT INTO visit (patient_id, doctor_id, bed_id, visit_type, visit_datetime, visit_status) 
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (101, 201, 999, 'Appointment', '2026-10-27 10:00:00', 'Scheduled')
            )
        assert 'FOREIGN KEY' in str(exc.value) or 'fk_visit_bed' in str(exc.value)
    
    def test_prescription_visit_fk(self, db_connection):
        """fk_presc_visit: visit must exist."""
        with pytest.raises(sqlite3.IntegrityError) as exc:
            db_connection.execute(
                'INSERT INTO prescription (visit_id, medicine_id, dosage, duration_days, quantity) VALUES (?, ?, ?, ?, ?)',
                (999, 501, '1-0-0', 5, 5)
            )
        assert 'FOREIGN KEY' in str(exc.value) or 'fk_presc_visit' in str(exc.value)
    
    def test_prescription_medicine_fk(self, db_connection):
        """fk_presc_med: medicine must exist."""
        with pytest.raises(sqlite3.IntegrityError) as exc:
            db_connection.execute(
                'INSERT INTO prescription (visit_id, medicine_id, dosage, duration_days, quantity) VALUES (?, ?, ?, ?, ?)',
                (401, 999, '1-0-0', 5, 5)
            )
        assert 'FOREIGN KEY' in str(exc.value) or 'fk_presc_med' in str(exc.value)
    
    def test_bill_visit_fk(self, db_connection):
        """fk_bill_visit: visit must exist."""
        with pytest.raises(sqlite3.IntegrityError) as exc:
            db_connection.execute(
                '''INSERT INTO bill (visit_id, consultation_charge, medicine_charge, bed_charge, total_amount, payment_status) 
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (999, 500, 0, 0, 500, 'Pending')
            )
        assert 'FOREIGN KEY' in str(exc.value) or 'fk_bill_visit' in str(exc.value)
    
    def test_delete_patient_with_visits_blocked(self, db_connection):
        """v08: Cannot delete patient who has visits (fk_visit_patient)."""
        with pytest.raises(sqlite3.IntegrityError) as exc:
            db_connection.execute('DELETE FROM patient WHERE patient_id = 101')
        assert 'FOREIGN KEY' in str(exc.value) or 'fk_visit_patient' in str(exc.value)


class TestPartialUniqueIndexes:
    """Test partial unique indexes."""
    
    def test_uq_doctor_slot_allows_cancelled_rebooking(self, db_connection):
        """uq_doctor_slot: Cancelled appointments don't block the slot."""
        # First, book an appointment
        db_connection.execute(
            '''INSERT INTO visit (patient_id, doctor_id, visit_type, visit_datetime, visit_status)
               VALUES (?, ?, ?, ?, ?)''',
            (101, 201, 'Appointment', '2026-10-27 10:00:00', 'Scheduled')
        )
        visit_id = db_connection.execute('SELECT last_insert_rowid()').fetchone()[0]
        
        # Try to book same doctor at same time - should fail
        with pytest.raises(sqlite3.IntegrityError) as exc:
            db_connection.execute(
                '''INSERT INTO visit (patient_id, doctor_id, visit_type, visit_datetime, visit_status)
                   VALUES (?, ?, ?, ?, ?)''',
                (102, 201, 'Appointment', '2026-10-27 10:00:00', 'Scheduled')
            )
        assert 'UNIQUE' in str(exc.value) or 'uq_doctor_slot' in str(exc.value)
        
        # Cancel the first appointment
        db_connection.execute('UPDATE visit SET visit_status = ? WHERE visit_id = ?', ('Cancelled', visit_id))
        
        # Now booking same slot should succeed
        db_connection.execute(
            '''INSERT INTO visit (patient_id, doctor_id, visit_type, visit_datetime, visit_status)
               VALUES (?, ?, ?, ?, ?)''',
            (102, 201, 'Appointment', '2026-10-27 10:00:00', 'Scheduled')
        )
        # Should not raise
    
    def test_uq_active_bed_prevents_double_allotment(self, db_connection):
        """uq_active_bed: Only one admitted patient per bed."""
        # Visit 413 is already admitted to bed 305
        # Try to admit another visit to same bed
        with pytest.raises(sqlite3.IntegrityError) as exc:
            db_connection.execute(
                'UPDATE visit SET bed_id = ?, visit_status = ? WHERE visit_id = ?',
                (305, 'Admitted', 414)
            )
        assert 'UNIQUE' in str(exc.value) or 'uq_active_bed' in str(exc.value)


class TestIndexesExist:
    """Test that required indexes exist."""
    
    def test_indexes(self, db_connection):
        indexes = {
            'uq_doctor_slot': 'visit',
            'uq_active_bed': 'visit',
            'idx_visit_patient': 'visit',
            'idx_visit_doctor': 'visit',
            'idx_presc_visit': 'prescription',
        }
        for idx_name, table in indexes.items():
            result = db_connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='index' AND name=?", (idx_name,)
            ).fetchone()
            assert result is not None, f'Index {idx_name} on {table} not found'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])