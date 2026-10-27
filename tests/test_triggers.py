"""
Tests for database triggers: stock reduce/restore, audit rows, doctor status, audit protection.
"""
import os
import pytest
import sqlite3
from pathlib import Path


# Use a fixed future timestamp that won't conflict with seed data
TEST_DATETIME = '2026-12-31 10:00:00'
TEST_DATETIME_2 = '2026-12-31 11:00:00'
TEST_DATETIME_3 = '2026-12-31 12:00:00'
TEST_DATETIME_4 = '2026-12-31 13:00:00'
TEST_DATETIME_5 = '2026-12-31 14:00:00'
TEST_DATETIME_6 = '2026-12-31 15:00:00'

# Use doctors not in seed data conflicts for specific tests
# Doctor 209 (Dr. Suresh Babu) has fewer visits in seed
# Doctor 210 (Dr. Anita Desai) also has fewer visits
TEST_DOCTOR_1 = 209  # Dr. Suresh Babu
TEST_DOCTOR_2 = 210  # Dr. Anita Desai
TEST_DOCTOR_3 = 208  # Dr. Meena Pillai

TEST_PHONE = '9876500999'
TEST_PHONE_2 = '9876500998'
TEST_PHONE_3 = '9876500997'


@pytest.fixture(scope="session")
def db_connection():
    """Create a fresh database for testing."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from db.init_db import init_database
    init_database(force=True, backup=False)
    
    from config import DB_PATH as _DBP; from conftest import assert_safe_db; assert_safe_db(_DBP); db_path = Path(_DBP)
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    conn.execute('PRAGMA busy_timeout = 5000')
    
    yield conn
    conn.close()


class TestTrgReduceStock:
    """Test trg_reduce_stock: reduce stock on insert, restore on delete."""
    
    def test_insert_reduces_stock(self, db_connection):
        """Inserting prescription reduces medicine stock."""
        # Get initial stock of Aspirin 75mg (medicine_id=506)
        initial = db_connection.execute(
            'SELECT stock_quantity FROM medicine WHERE medicine_id = 506'
        ).fetchone()['stock_quantity']
        
        # Insert prescription for visit 422 (will be created later) - use a valid visit
        # First create a visit for testing
        db_connection.execute(
            '''INSERT INTO visit (patient_id, doctor_id, visit_type, visit_datetime, visit_status)
               VALUES (?, ?, ?, ?, ?)''',
            (101, 201, 'Appointment', TEST_DATETIME, 'Scheduled')
        )
        visit_id = db_connection.execute('SELECT last_insert_rowid()').fetchone()[0]
        
        # Add prescription for Aspirin 75mg (506), qty 10
        db_connection.execute(
            'INSERT INTO prescription (visit_id, medicine_id, dosage, duration_days, quantity) VALUES (?, ?, ?, ?, ?)',
            (visit_id, 506, '1-0-0', 5, 10)
        )
        
        # Check stock reduced
        after = db_connection.execute(
            'SELECT stock_quantity FROM medicine WHERE medicine_id = 506'
        ).fetchone()['stock_quantity']
        
        assert after == initial - 10, f'Expected {initial - 10}, got {after}'
    
    def test_insert_insufficient_stock_raises(self, db_connection):
        """Inserting prescription with qty > stock raises error."""
        # ORS Sachet (512) has stock 0
        # First create a visit
        db_connection.execute(
            '''INSERT INTO visit (patient_id, doctor_id, visit_type, visit_datetime, visit_status)
               VALUES (?, ?, ?, ?, ?)''',
            (101, 201, 'Appointment', TEST_DATETIME_2, 'Scheduled')
        )
        visit_id = db_connection.execute('SELECT last_insert_rowid()').fetchone()[0]
        
        with pytest.raises(sqlite3.IntegrityError) as exc:
            db_connection.execute(
                'INSERT INTO prescription (visit_id, medicine_id, dosage, duration_days, quantity) VALUES (?, ?, ?, ?, ?)',
                (visit_id, 512, '1-0-0', 5, 5)
            )
        assert 'Insufficient stock' in str(exc.value)
    
    def test_delete_restores_stock(self, db_connection):
        """Deleting prescription restores medicine stock."""
        # Get initial stock
        initial = db_connection.execute(
            'SELECT stock_quantity FROM medicine WHERE medicine_id = 506'
        ).fetchone()['stock_quantity']
        
        # Create visit and prescription
        db_connection.execute(
            '''INSERT INTO visit (patient_id, doctor_id, visit_type, visit_datetime, visit_status)
               VALUES (?, ?, ?, ?, ?)''',
            (101, 201, 'Appointment', TEST_DATETIME_3, 'Scheduled')
        )
        visit_id = db_connection.execute('SELECT last_insert_rowid()').fetchone()[0]
        
        db_connection.execute(
            'INSERT INTO prescription (visit_id, medicine_id, dosage, duration_days, quantity) VALUES (?, ?, ?, ?, ?)',
            (visit_id, 506, '1-0-0', 5, 10)
        )
        
        # Get prescription_id
        presc_id = db_connection.execute(
            'SELECT prescription_id FROM prescription WHERE visit_id = ? AND medicine_id = 506',
            (visit_id,)
        ).fetchone()['prescription_id']
        
        # Delete prescription
        db_connection.execute('DELETE FROM prescription WHERE prescription_id = ?', (presc_id,))
        
        # Check stock restored
        after = db_connection.execute(
            'SELECT stock_quantity FROM medicine WHERE medicine_id = 506'
        ).fetchone()['stock_quantity']
        
        assert after == initial, f'Expected {initial}, got {after}'


class TestTrgAuditVisit:
    """Test trg_audit_visit: audit_log entries for visit INSERT/UPDATE/DELETE."""
    
    def test_insert_creates_audit(self, db_connection):
        """INSERT visit creates audit_log entry."""
        initial_count = db_connection.execute('SELECT COUNT(*) FROM audit_log').fetchone()[0]
        
        db_connection.execute(
            '''INSERT INTO visit (patient_id, doctor_id, visit_type, visit_datetime, visit_status)
               VALUES (?, ?, ?, ?, ?)''',
            (101, 201, 'Appointment', TEST_DATETIME_4, 'Scheduled')
        )
        visit_id = db_connection.execute('SELECT last_insert_rowid()').fetchone()[0]
        
        # Check audit log
        audit = db_connection.execute(
            'SELECT * FROM audit_log WHERE table_name = ? AND record_id = ? ORDER BY log_id DESC LIMIT 1',
            ('VISIT', visit_id)
        ).fetchone()
        
        assert audit is not None
        assert audit['action_type'] == 'INSERT'
        assert 'New Appointment visit for patient 101' in audit['description']
        assert audit['changed_by'] == 'ADMIN'  # Default session username
    
    def test_update_creates_audit(self, db_connection):
        """UPDATE visit status creates audit_log entry."""
        # Create visit
        db_connection.execute(
            '''INSERT INTO visit (patient_id, doctor_id, visit_type, visit_datetime, visit_status)
               VALUES (?, ?, ?, ?, ?)''',
            (101, 201, 'Appointment', TEST_DATETIME_5, 'Scheduled')
        )
        visit_id = db_connection.execute('SELECT last_insert_rowid()').fetchone()[0]
        
        # Update status
        db_connection.execute(
            'UPDATE visit SET visit_status = ? WHERE visit_id = ?',
            ('Cancelled', visit_id)
        )
        
        # Check audit log
        audit = db_connection.execute(
            'SELECT * FROM audit_log WHERE table_name = ? AND record_id = ? ORDER BY log_id DESC LIMIT 1',
            ('VISIT', visit_id)
        ).fetchone()
        
        assert audit is not None
        assert audit['action_type'] == 'UPDATE'
        assert 'Status Scheduled -> Cancelled' in audit['description']
    
    def test_delete_creates_audit(self, db_connection):
        """DELETE visit creates audit_log entry (if no FK blocks)."""
        # Create a visit with no dependencies
        db_connection.execute(
            '''INSERT INTO visit (patient_id, doctor_id, visit_type, visit_datetime, visit_status)
               VALUES (?, ?, ?, ?, ?)''',
            (101, 201, 'Appointment', TEST_DATETIME_6, 'Scheduled')
        )
        visit_id = db_connection.execute('SELECT last_insert_rowid()').fetchone()[0]
        
        # Delete it
        db_connection.execute('DELETE FROM visit WHERE visit_id = ?', (visit_id,))
        
        # Check audit log
        audit = db_connection.execute(
            'SELECT * FROM audit_log WHERE table_name = ? AND record_id = ? ORDER BY log_id DESC LIMIT 1',
            ('VISIT', visit_id)
        ).fetchone()
        
        assert audit is not None
        assert audit['action_type'] == 'DELETE'
        assert f'Visit deleted (patient 101)' in audit['description']


class TestTrgAuditBill:
    """Test trg_audit_bill: audit_log entries for bill INSERT/UPDATE/DELETE."""
    
    def test_insert_creates_audit(self, db_connection):
        """INSERT bill creates audit_log entry."""
        # Need a discharged visit without a bill
        db_connection.execute(
            '''INSERT INTO visit (patient_id, doctor_id, visit_type, visit_datetime, visit_status)
               VALUES (?, ?, ?, ?, ?)''',
            (101, TEST_DOCTOR_1, 'Appointment', TEST_DATETIME_4, 'Discharged')
        )
        visit_id = db_connection.execute('SELECT last_insert_rowid()').fetchone()[0]
        
        db_connection.execute(
            '''INSERT INTO bill (visit_id, consultation_charge, medicine_charge, bed_charge, total_amount, payment_status)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (visit_id, 500, 50, 0, 550, 'Pending')
        )
        bill_id = db_connection.execute('SELECT last_insert_rowid()').fetchone()[0]
        
        audit = db_connection.execute(
            'SELECT * FROM audit_log WHERE table_name = ? AND record_id = ? ORDER BY log_id DESC LIMIT 1',
            ('BILL', bill_id)
        ).fetchone()
        
        assert audit is not None
        assert audit['action_type'] == 'INSERT'
        assert 'Bill generated: total 550 (Pending)' in audit['description']
    
    def test_update_payment_creates_audit(self, db_connection):
        """UPDATE bill payment_status creates audit_log entry."""
        # Create bill
        db_connection.execute(
            '''INSERT INTO visit (patient_id, doctor_id, visit_type, visit_datetime, visit_status)
               VALUES (?, ?, ?, ?, ?)''',
            (101, TEST_DOCTOR_2, 'Appointment', TEST_DATETIME_5, 'Discharged')
        )
        visit_id = db_connection.execute('SELECT last_insert_rowid()').fetchone()[0]
        
        db_connection.execute(
            '''INSERT INTO bill (visit_id, consultation_charge, medicine_charge, bed_charge, total_amount, payment_status)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (visit_id, 500, 50, 0, 550, 'Pending')
        )
        bill_id = db_connection.execute('SELECT last_insert_rowid()').fetchone()[0]
        
        # Update to Paid
        db_connection.execute(
            'UPDATE bill SET payment_mode = ?, payment_status = ? WHERE bill_id = ?',
            ('Cash', 'Paid', bill_id)
        )
        
        audit = db_connection.execute(
            'SELECT * FROM audit_log WHERE table_name = ? AND record_id = ? ORDER BY log_id DESC LIMIT 1',
            ('BILL', bill_id)
        ).fetchone()
        
        assert audit is not None
        assert audit['action_type'] == 'UPDATE'
        assert 'Payment status Pending -> Paid' in audit['description']


class TestTrgAuditPatient:
    """Test trg_audit_patient: audit_log entries for patient INSERT/UPDATE/DELETE."""
    
    def test_insert_creates_audit(self, db_connection):
        """INSERT patient creates audit_log entry."""
        db_connection.execute(
            'INSERT INTO patient (patient_name, phone, gender, date_of_birth) VALUES (?, ?, ?, ?)',
            ('Test Patient', TEST_PHONE, 'Male', '2000-01-01')
        )
        patient_id = db_connection.execute('SELECT last_insert_rowid()').fetchone()[0]
        
        audit = db_connection.execute(
            'SELECT * FROM audit_log WHERE table_name = ? AND record_id = ? ORDER BY log_id DESC LIMIT 1',
            ('PATIENT', patient_id)
        ).fetchone()
        
        assert audit is not None
        assert audit['action_type'] == 'INSERT'
        assert audit['description'] == 'New patient registered'
    
    def test_update_creates_audit(self, db_connection):
        """UPDATE patient creates audit_log entry."""
        db_connection.execute(
            'INSERT INTO patient (patient_name, phone, gender, date_of_birth) VALUES (?, ?, ?, ?)',
            ('Test Patient', TEST_PHONE_2, 'Male', '2000-01-01')
        )
        patient_id = db_connection.execute('SELECT last_insert_rowid()').fetchone()[0]
        
        db_connection.execute(
            'UPDATE patient SET patient_name = ? WHERE patient_id = ?',
            ('Updated Name', patient_id)
        )
        
        audit = db_connection.execute(
            'SELECT * FROM audit_log WHERE table_name = ? AND record_id = ? ORDER BY log_id DESC LIMIT 1',
            ('PATIENT', patient_id)
        ).fetchone()
        
        assert audit is not None
        assert audit['action_type'] == 'UPDATE'
        assert audit['description'] == 'Patient details updated'
    
    def test_delete_creates_audit(self, db_connection):
        """DELETE patient creates audit_log entry (if no FK blocks)."""
        # Create patient with no visits
        db_connection.execute(
            'INSERT INTO patient (patient_name, phone, gender, date_of_birth) VALUES (?, ?, ?, ?)',
            ('Test Patient', TEST_PHONE_3, 'Male', '2000-01-01')
        )
        patient_id = db_connection.execute('SELECT last_insert_rowid()').fetchone()[0]
        
        db_connection.execute('DELETE FROM patient WHERE patient_id = ?', (patient_id,))
        
        audit = db_connection.execute(
            'SELECT * FROM audit_log WHERE table_name = ? AND record_id = ? ORDER BY log_id DESC LIMIT 1',
            ('PATIENT', patient_id)
        ).fetchone()
        
        assert audit is not None
        assert audit['action_type'] == 'DELETE'
        assert audit['description'] == 'Patient record deleted'


class TestTrgDoctorStatus:
    """Test trg_doctor_status: doctor availability changes with visit status."""
    
    def test_under_treatment_sets_busy(self, db_connection):
        """Visit status Under Treatment sets doctor to Busy."""
        # Ensure doctor is Available
        db_connection.execute(
            'UPDATE doctor SET availability_status = ? WHERE doctor_id = ?',
            ('Available', TEST_DOCTOR_1)
        )
        
        # Create visit
        db_connection.execute(
            '''INSERT INTO visit (patient_id, doctor_id, visit_type, visit_datetime, visit_status)
               VALUES (?, ?, ?, ?, ?)''',
            (101, TEST_DOCTOR_1, 'Appointment', TEST_DATETIME_2, 'Scheduled')
        )
        visit_id = db_connection.execute('SELECT last_insert_rowid()').fetchone()[0]
        
        # Change to Under Treatment
        db_connection.execute(
            'UPDATE visit SET visit_status = ? WHERE visit_id = ?',
            ('Under Treatment', visit_id)
        )
        
        # Check doctor status
        status = db_connection.execute(
            'SELECT availability_status FROM doctor WHERE doctor_id = ?',
            (TEST_DOCTOR_1,)
        ).fetchone()['availability_status']
        
        assert status == 'Busy'
    
    def test_leaving_under_treatment_sets_available(self, db_connection):
        """Visit leaving Under Treatment sets doctor to Available."""
        # Create visit already Under Treatment with a bed (required for Admitted)
        db_connection.execute(
            '''INSERT INTO visit (patient_id, doctor_id, bed_id, visit_type, visit_datetime, visit_status)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (101, TEST_DOCTOR_2, 307, 'Appointment', TEST_DATETIME_3, 'Under Treatment')
        )
        visit_id = db_connection.execute('SELECT last_insert_rowid()').fetchone()[0]
        
        # Ensure doctor is Busy
        db_connection.execute(
            'UPDATE doctor SET availability_status = ? WHERE doctor_id = ?',
            ('Busy', TEST_DOCTOR_2)
        )
        
        # Change to Admitted (leaves Under Treatment)
        db_connection.execute(
            'UPDATE visit SET visit_status = ? WHERE visit_id = ?',
            ('Admitted', visit_id)
        )
        
        # Check doctor status
        status = db_connection.execute(
            'SELECT availability_status FROM doctor WHERE doctor_id = ?',
            (TEST_DOCTOR_2,)
        ).fetchone()['availability_status']
        
        assert status == 'Available'
    
    def test_insert_under_treatment_sets_busy(self, db_connection):
        """Inserting visit with Under Treatment sets doctor to Busy."""
        db_connection.execute(
            'UPDATE doctor SET availability_status = ? WHERE doctor_id = ?',
            ('Available', TEST_DOCTOR_3)
        )
        
        db_connection.execute(
            '''INSERT INTO visit (patient_id, doctor_id, visit_type, visit_datetime, visit_status)
               VALUES (?, ?, ?, ?, ?)''',
            (101, TEST_DOCTOR_3, 'Appointment', TEST_DATETIME_4, 'Under Treatment')
        )
        
        status = db_connection.execute(
            'SELECT availability_status FROM doctor WHERE doctor_id = ?',
            (TEST_DOCTOR_3,)
        ).fetchone()['availability_status']
        
        assert status == 'Busy'


class TestTrgProtectAudit:
    """Test trg_protect_audit: audit_log cannot be modified or deleted."""
    
    def test_update_blocked(self, db_connection):
        """UPDATE audit_log is blocked."""
        with pytest.raises(sqlite3.IntegrityError) as exc:
            db_connection.execute(
                'UPDATE audit_log SET description = ? WHERE log_id = ?',
                ('Tampered', 1)
            )
        assert 'AUDIT_LOG entries cannot be modified or deleted' in str(exc.value)
    
    def test_delete_blocked(self, db_connection):
        """DELETE audit_log is blocked."""
        with pytest.raises(sqlite3.IntegrityError) as exc:
            db_connection.execute('DELETE FROM audit_log WHERE log_id = 1')
        assert 'AUDIT_LOG entries cannot be modified or deleted' in str(exc.value)
    
    def test_tamper_test_endpoint_style(self, db_connection):
        """Test the tamper-test pattern: BEGIN, attempt, ROLLBACK."""
        # This simulates what /api/audit/tamper-test does
        db_connection.execute('BEGIN')
        try:
            db_connection.execute('UPDATE audit_log SET description = ? WHERE log_id = ?', ('x', 1))
            db_connection.execute('ROLLBACK')
            blocked = False
        except sqlite3.IntegrityError:
            db_connection.execute('ROLLBACK')
            blocked = True
        
        assert blocked
        
        # Verify data unchanged
        desc = db_connection.execute('SELECT description FROM audit_log WHERE log_id = 1').fetchone()['description']
        assert desc == 'New patient registered'


class TestChangedByFromAppSession:
    """Test that audit triggers use app_session.username for changed_by."""
    
    def test_changed_by_matches_session(self, db_connection):
        """changed_by should match app_session.username."""
        # Default is ADMIN
        db_connection.execute(
            'INSERT INTO patient (patient_name, phone, gender, date_of_birth) VALUES (?, ?, ?, ?)',
            ('Test', '9876500996', 'Male', '2000-01-01')
        )
        patient_id = db_connection.execute('SELECT last_insert_rowid()').fetchone()[0]
        
        audit = db_connection.execute(
            'SELECT changed_by FROM audit_log WHERE table_name = ? AND record_id = ? ORDER BY log_id DESC LIMIT 1',
            ('PATIENT', patient_id)
        ).fetchone()
        
        assert audit['changed_by'] == 'ADMIN'
    
    def test_changed_by_updates_with_session(self, db_connection):
        """changing app_session.username affects subsequent audit rows."""
        # Change session username
        db_connection.execute("UPDATE app_session SET username = 'TEST_USER' WHERE id = 1")
        
        db_connection.execute(
            'INSERT INTO patient (patient_name, phone, gender, date_of_birth) VALUES (?, ?, ?, ?)',
            ('Test2', '9876500995', 'Male', '2000-01-01')
        )
        patient_id = db_connection.execute('SELECT last_insert_rowid()').fetchone()[0]
        
        audit = db_connection.execute(
            'SELECT changed_by FROM audit_log WHERE table_name = ? AND record_id = ? ORDER BY log_id DESC LIMIT 1',
            ('PATIENT', patient_id)
        ).fetchone()
        
        assert audit['changed_by'] == 'TEST_USER'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])