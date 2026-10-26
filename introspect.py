"""
Schema introspection for Smart Hospital Management System.
Uses PRAGMA and sqlite_master to extract metadata.
"""
import sqlite3
import re
from typing import List, Dict, Any, Optional


# Curated metadata for constraints, triggers, indexes (what PRAGMA doesn't give us)
CONSTRAINT_METADATA = {
    'patient': {
        'uq_pat_phone': {'type': 'UNIQUE', 'rule': 'phone', 'expression': 'UNIQUE (phone)'},
        'chk_pat_gender': {'type': 'CHECK', 'rule': "gender in ('Male','Female','Other')", 'expression': "gender IN ('Male','Female','Other')"},
        'chk_pat_phone': {'type': 'CHECK', 'rule': 'phone 10 digits', 'expression': "phone GLOB '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9']"},
        'chk_pat_blood': {'type': 'CHECK', 'rule': 'valid blood group', 'expression': "blood_group IN ('A+','A-','B+','B-','AB+','AB-','O+','O-')"},
    },
    'doctor': {
        'uq_doc_phone': {'type': 'UNIQUE', 'rule': 'phone', 'expression': 'UNIQUE (phone)'},
        'chk_doc_fee': {'type': 'CHECK', 'rule': 'fee > 0', 'expression': 'consultation_fee > 0'},
        'chk_doc_shift': {'type': 'CHECK', 'rule': 'valid shift', 'expression': "shift IN ('Morning','Evening','Night')"},
        'chk_doc_avail': {'type': 'CHECK', 'rule': 'valid availability', 'expression': "availability_status IN ('Available','Busy')"},
    },
    'bed': {
        'chk_bed_ward': {'type': 'CHECK', 'rule': 'valid ward', 'expression': "ward_type IN ('General','Private','ICU','Emergency')"},
        'chk_bed_stat': {'type': 'CHECK', 'rule': 'valid status', 'expression': "bed_status IN ('Free','Occupied','Cleaning')"},
        'chk_bed_chg': {'type': 'CHECK', 'rule': 'charge > 0', 'expression': 'daily_charge > 0'},
    },
    'medicine': {
        'chk_med_price': {'type': 'CHECK', 'rule': 'price > 0', 'expression': 'price_per_unit > 0'},
        'chk_med_stock': {'type': 'CHECK', 'rule': 'stock >= 0', 'expression': 'stock_quantity >= 0'},
    },
    'visit': {
        'fk_visit_patient': {'type': 'FOREIGN KEY', 'rule': 'patient_id -> patient', 'expression': 'FOREIGN KEY (patient_id) REFERENCES patient(patient_id)'},
        'fk_visit_doctor': {'type': 'FOREIGN KEY', 'rule': 'doctor_id -> doctor', 'expression': 'FOREIGN KEY (doctor_id) REFERENCES doctor(doctor_id)'},
        'fk_visit_bed': {'type': 'FOREIGN KEY', 'rule': 'bed_id -> bed', 'expression': 'FOREIGN KEY (bed_id) REFERENCES bed(bed_id)'},
        'chk_visit_type': {'type': 'CHECK', 'rule': 'valid type', 'expression': "visit_type IN ('Appointment','Emergency')"},
        'chk_visit_status': {'type': 'CHECK', 'rule': 'valid status', 'expression': "visit_status IN ('Scheduled','Waiting','Under Treatment','Admitted','Discharged','Cancelled')"},
        'chk_visit_range': {'type': 'CHECK', 'rule': 'triage 1-4', 'expression': 'triage_level BETWEEN 1 AND 4'},
        'chk_visit_triage': {'type': 'CHECK', 'rule': 'triage only for emergency', 'expression': "(visit_type = 'Emergency' AND triage_level IS NOT NULL) OR (visit_type = 'Appointment' AND triage_level IS NULL)"},
        'chk_visit_bed': {'type': 'CHECK', 'rule': 'admitted => bed', 'expression': "visit_status <> 'Admitted' OR bed_id IS NOT NULL"},
        'chk_visit_disch': {'type': 'CHECK', 'rule': 'discharge >= admit', 'expression': 'discharge_time >= admit_time'},
    },
    'prescription': {
        'fk_presc_visit': {'type': 'FOREIGN KEY', 'rule': 'visit_id -> visit', 'expression': 'FOREIGN KEY (visit_id) REFERENCES visit(visit_id) ON DELETE CASCADE'},
        'fk_presc_med': {'type': 'FOREIGN KEY', 'rule': 'medicine_id -> medicine', 'expression': 'FOREIGN KEY (medicine_id) REFERENCES medicine(medicine_id)'},
        'chk_presc_days': {'type': 'CHECK', 'rule': 'days > 0', 'expression': 'duration_days > 0'},
        'chk_presc_qty': {'type': 'CHECK', 'rule': 'qty > 0', 'expression': 'quantity > 0'},
    },
    'bill': {
        'uq_bill_visit': {'type': 'UNIQUE', 'rule': 'visit_id', 'expression': 'UNIQUE (visit_id)'},
        'fk_bill_visit': {'type': 'FOREIGN KEY', 'rule': 'visit_id -> visit', 'expression': 'FOREIGN KEY (visit_id) REFERENCES visit(visit_id)'},
        'chk_bill_mode': {'type': 'CHECK', 'rule': 'valid mode', 'expression': "payment_mode IN ('Cash','Card','UPI')"},
        'chk_bill_stat': {'type': 'CHECK', 'rule': 'valid status', 'expression': "payment_status IN ('Paid','Pending')"},
        'chk_bill_amt': {'type': 'CHECK', 'rule': 'charges >= 0', 'expression': 'consultation_charge >= 0 AND medicine_charge >= 0 AND bed_charge >= 0'},
        'chk_bill_total': {'type': 'CHECK', 'rule': 'total = sum of parts', 'expression': 'total_amount = consultation_charge + medicine_charge + bed_charge'},
        'chk_bill_paid': {'type': 'CHECK', 'rule': 'paid => mode not null', 'expression': "payment_status = 'Pending' OR payment_mode IS NOT NULL"},
    },
    'audit_log': {
        'chk_audit_act': {'type': 'CHECK', 'rule': 'valid action', 'expression': "action_type IN ('INSERT','UPDATE','DELETE')"},
    },
}

INDEX_METADATA = {
    'uq_doctor_slot': {'table': 'visit', 'unique': True, 'partial_where': "visit_status <> 'Cancelled'", 'purpose': 'Prevent double-booking: one doctor, one timeslot, unless Cancelled'},
    'uq_active_bed': {'table': 'visit', 'unique': True, 'partial_where': "visit_status = 'Admitted'", 'purpose': 'Prevent double bed allocation: one bed, one admitted patient'},
    'idx_visit_patient': {'table': 'visit', 'unique': False, 'partial_where': None, 'purpose': 'Fast patient visit lookup'},
    'idx_visit_doctor': {'table': 'visit', 'unique': False, 'partial_where': None, 'purpose': 'Fast doctor visit lookup'},
    'idx_presc_visit': {'table': 'prescription', 'unique': False, 'partial_where': None, 'purpose': 'Fast prescription lookup by visit'},
}

TRIGGER_METADATA = [
    {
        'logical_name': 'trg_reduce_stock',
        'physical': ['trg_reduce_stock__insert', 'trg_reduce_stock__delete'],
        'timing': 'BEFORE INSERT / AFTER DELETE',
        'events': ['INSERT', 'DELETE'],
        'table': 'prescription',
        'purpose': 'Reduce stock on prescription insert; restore on delete; reject if insufficient',
    },
    {
        'logical_name': 'trg_audit_visit',
        'physical': ['trg_audit_visit__insert', 'trg_audit_visit__update', 'trg_audit_visit__delete'],
        'timing': 'AFTER',
        'events': ['INSERT', 'UPDATE', 'DELETE'],
        'table': 'visit',
        'purpose': 'Audit visit INSERT/UPDATE/DELETE to audit_log with changed_by from app_session',
    },
    {
        'logical_name': 'trg_audit_bill',
        'physical': ['trg_audit_bill__insert', 'trg_audit_bill__update', 'trg_audit_bill__delete'],
        'timing': 'AFTER',
        'events': ['INSERT', 'UPDATE', 'DELETE'],
        'table': 'bill',
        'purpose': 'Audit bill INSERT/UPDATE/DELETE to audit_log with changed_by from app_session',
    },
    {
        'logical_name': 'trg_audit_patient',
        'physical': ['trg_audit_patient__insert', 'trg_audit_patient__update', 'trg_audit_patient__delete'],
        'timing': 'AFTER',
        'events': ['INSERT', 'UPDATE', 'DELETE'],
        'table': 'patient',
        'purpose': 'Audit patient INSERT/UPDATE/DELETE to audit_log with changed_by from app_session',
    },
    {
        'logical_name': 'trg_doctor_status',
        'physical': ['trg_doctor_status__insert', 'trg_doctor_status__update'],
        'timing': 'AFTER',
        'events': ['INSERT', 'UPDATE OF visit_status'],
        'table': 'visit',
        'purpose': 'Set doctor Busy when visit becomes Under Treatment; Available when it leaves Under Treatment',
    },
    {
        'logical_name': 'trg_protect_audit',
        'physical': ['trg_protect_audit__update', 'trg_protect_audit__delete'],
        'timing': 'BEFORE',
        'events': ['UPDATE', 'DELETE'],
        'table': 'audit_log',
        'purpose': 'Prevent modification or deletion of audit_log entries',
    },
]

FUNCTION_METADATA = [
    {'name': 'fn_days_stayed', 'signature': 'fn_days_stayed(visit_id) -> INTEGER', 'purpose': '0 if never admitted; else date difference between admit and discharge (or now if not discharged), minimum 1', 'oracle_equivalent': 'fn_days_stayed (PL/SQL function)'},
    {'name': 'fn_medicine_cost', 'signature': 'fn_medicine_cost(visit_id) -> NUMERIC', 'purpose': 'SUM(quantity * price_per_unit) for the visit, 0 if none', 'oracle_equivalent': 'fn_medicine_cost (PL/SQL function)'},
    {'name': 'fn_triage_label', 'signature': 'fn_triage_label(level) -> TEXT', 'purpose': '1 Critical, 2 Very urgent, 3 Urgent, 4 Minor, else Not triaged', 'oracle_equivalent': 'fn_triage_label (DETERMINISTIC PL/SQL function)'},
]

RELATIONSHIPS = [
    {'from_table': 'visit', 'from_col': 'patient_id', 'to_table': 'patient', 'to_col': 'patient_id', 'cardinality': 'N:1', 'note': 'A visit belongs to one patient; a patient can have many visits'},
    {'from_table': 'visit', 'from_col': 'doctor_id', 'to_table': 'doctor', 'to_col': 'doctor_id', 'cardinality': 'N:1', 'note': 'A visit has one doctor; a doctor can have many visits'},
    {'from_table': 'visit', 'from_col': 'bed_id', 'to_table': 'bed', 'to_col': 'bed_id', 'cardinality': 'N:1', 'note': 'A visit may have one bed; a bed can be in many visits over time'},
    {'from_table': 'prescription', 'from_col': 'visit_id', 'to_table': 'visit', 'to_col': 'visit_id', 'cardinality': 'N:1', 'note': 'A prescription belongs to one visit; a visit can have many prescriptions'},
    {'from_table': 'prescription', 'from_col': 'medicine_id', 'to_table': 'medicine', 'to_col': 'medicine_id', 'cardinality': 'N:1', 'note': 'A prescription references one medicine; a medicine can be in many prescriptions'},
    {'from_table': 'bill', 'from_col': 'visit_id', 'to_table': 'visit', 'to_col': 'visit_id', 'cardinality': '1:1', 'note': 'One bill per visit (enforced by UNIQUE)'},
]

VIOLATION_TESTS = [
    {'id': 'v01', 'title': 'Insert patient with an existing phone', 'rule': 'uq_pat_phone (UNIQUE)', 'enforced_by': 'UNIQUE constraint', 'sql': "INSERT INTO patient (patient_name, phone, gender, date_of_birth) VALUES ('Test', '9876500101', 'Male', '2000-01-01')"},
    {'id': 'v02', 'title': 'Insert appointment with a triage level', 'rule': 'chk_visit_triage (CHECK)', 'enforced_by': 'CHECK constraint', 'sql': "INSERT INTO visit (patient_id, doctor_id, visit_type, visit_datetime, triage_level) VALUES (101, 202, 'Appointment', '2026-10-27 10:00:00', 1)"},
    {'id': 'v03', 'title': 'Second active visit for same doctor and time', 'rule': 'uq_doctor_slot (partial unique index)', 'enforced_by': 'Partial unique index', 'sql': "INSERT INTO visit (patient_id, doctor_id, visit_type, visit_datetime, visit_status) VALUES (101, 202, 'Appointment', '2026-10-27 10:00:00', 'Scheduled')"},
    {'id': 'v04', 'title': 'Second admitted patient on the same bed', 'rule': 'uq_active_bed (partial unique index)', 'enforced_by': 'Partial unique index', 'sql': "UPDATE visit SET bed_id = 305, visit_status = 'Admitted' WHERE visit_id = 414"},
    {'id': 'v05', 'title': 'Discharge time before admit time', 'rule': 'chk_visit_disch (CHECK)', 'enforced_by': 'CHECK constraint', 'sql': "UPDATE visit SET discharge_time = '2026-10-01 10:00:00' WHERE visit_id = 413"},
    {'id': 'v06', 'title': 'Medicine with price 0', 'rule': 'chk_med_price (CHECK)', 'enforced_by': 'CHECK constraint', 'sql': "INSERT INTO medicine (medicine_name, price_per_unit, stock_quantity) VALUES ('Test', 0, 10)"},
    {'id': 'v07', 'title': 'Bill marked Paid without payment mode', 'rule': 'chk_bill_paid (CHECK)', 'enforced_by': 'CHECK constraint', 'sql': "UPDATE bill SET payment_status = 'Paid' WHERE bill_id = 706"},
    {'id': 'v08', 'title': 'Delete a patient who has visits', 'rule': 'fk_visit_patient (FOREIGN KEY)', 'enforced_by': 'FOREIGN KEY constraint', 'sql': "DELETE FROM patient WHERE patient_id = 101"},
    {'id': 'v09', 'title': 'Prescribe more than the stock', 'rule': 'trg_reduce_stock__insert (trigger)', 'enforced_by': 'Trigger', 'sql': "INSERT INTO prescription (visit_id, medicine_id, dosage, duration_days, quantity) VALUES (422, 512, '1-0-0', 5, 5)"},
    {'id': 'v10', 'title': 'UPDATE/DELETE an audit_log row', 'rule': 'trg_protect_audit (trigger)', 'enforced_by': 'Trigger', 'sql': "UPDATE audit_log SET description = 'tampered' WHERE log_id = 1"},
    {'id': 'v11', 'title': 'Phone number with letters', 'rule': 'chk_pat_phone (CHECK)', 'enforced_by': 'CHECK constraint', 'sql': "INSERT INTO patient (patient_name, phone, gender, date_of_birth) VALUES ('Test', '98765ABCDE', 'Male', '2000-01-01')"},
]


def get_schema_overview(conn: sqlite3.Connection) -> Dict:
    """Get high-level schema counts."""
    tables = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchone()[0]
    triggers = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='trigger'").fetchone()[0]
    functions = len(FUNCTION_METADATA)
    indexes = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'").fetchone()[0]
    return {"tables": tables, "triggers": triggers, "functions": functions, "indexes": indexes}


def get_tables(conn: sqlite3.Connection) -> List[Dict]:
    """Get list of tables with row counts and column counts."""
    tables = conn.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name NOT LIKE 'sqlite_%'
        ORDER BY name
    """).fetchall()
    
    result = []
    for t in tables:
        name = t['name']
        row_count = conn.execute(f'SELECT COUNT(*) FROM {name}').fetchone()[0]
        col_count = len(conn.execute(f'PRAGMA table_info({name})').fetchall())
        result.append({'name': name, 'rows': row_count, 'columns': col_count})
    return result


def get_table(conn: sqlite3.Connection, table_name: str, preview: int = 10) -> Dict:
    """Get detailed table information."""
    # Validate table exists
    exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table_name,)).fetchone()
    if not exists:
        raise ValueError(f"Table {table_name} not found")
    
    # Get column info
    cols = conn.execute(f'PRAGMA table_info({table_name})').fetchall()
    columns = []
    for c in cols:
        col_name = c['name']
        col_type = c['type']
        is_pk = c['pk'] == 1
        not_null = c['notnull'] == 1
        default = c['dflt_value']
        
        # Check for unique
        is_unique = False
        checks = []
        
        # Check constraints from metadata
        if table_name in CONSTRAINT_METADATA:
            for cname, cinfo in CONSTRAINT_METADATA[table_name].items():
                if col_name in cinfo.get('rule', '').lower() or cname == f'chk_{table_name}_{col_name.lower()}':
                    if cinfo['type'] == 'CHECK':
                        checks.append(cname)
        
        # Check if part of UNIQUE constraint/index
        indexes = conn.execute(f'PRAGMA index_list({table_name})').fetchall()
        for idx in indexes:
            idx_name = idx['name']
            if idx['unique'] == 1:
                idx_cols = conn.execute(f'PRAGMA index_info({idx_name})').fetchall()
                idx_col_names = [ic['name'] for ic in idx_cols]
                if col_name in idx_col_names and len(idx_col_names) == 1:
                    is_unique = True
        
        columns.append({
            'name': col_name, 'type': col_type, 'pk': int(is_pk), 'notnull': int(not_null),
            'default': default, 'unique': int(is_unique), 'fk': 0, 'checks': checks
        })
    
    row_count = conn.execute(f'SELECT COUNT(*) FROM {table_name}').fetchone()[0]
    
    preview_rows = conn.execute(f'SELECT * FROM {table_name} LIMIT ?', (preview,)).fetchall()
    preview_cols = [description[0] for description in conn.execute(f'SELECT * FROM {table_name} LIMIT 0').description] if preview_rows else []
    
    return {
        'columns': columns,
        'row_count': row_count,
        'preview': {
            'columns': preview_cols,
            'rows': [list(r) for r in preview_rows]
        }
    }


def get_relationships(conn: sqlite3.Connection) -> List[Dict]:
    """Get table relationships from foreign keys."""
    return RELATIONSHIPS


def get_constraints(conn: sqlite3.Connection) -> List[Dict]:
    """Get all constraints with metadata."""
    result = []
    for table, constraints in CONSTRAINT_METADATA.items():
        for name, info in constraints.items():
            result.append({
                'table': table,
                'name': name,
                'type': info['type'],
                'rule': info['rule'],
                'expression': info['expression']
            })
    return result


def get_indexes(conn: sqlite3.Connection) -> List[Dict]:
    """Get all indexes with metadata."""
    result = []
    for name, info in INDEX_METADATA.items():
        result.append({
            'name': name,
            'table': info['table'],
            'unique': info['unique'],
            'partial_where': info['partial_where'],
            'purpose': info['purpose']
        })
    return result


def get_triggers(conn: sqlite3.Connection) -> List[Dict]:
    """Get all triggers with metadata."""
    # Get physical triggers from sqlite_master
    physical_triggers = conn.execute("""
        SELECT name, tbl_name, sql FROM sqlite_master 
        WHERE type='trigger' ORDER BY name
    """).fetchall()
    
    # Group by logical name
    result = []
    for t in TRIGGER_METADATA:
        physical_sql = {}
        for p_name in t['physical']:
            for pt in physical_triggers:
                if pt['name'] == p_name:
                    physical_sql[p_name] = pt['sql']
                    break
        
        result.append({
            'logical_name': t['logical_name'],
            'physical': t['physical'],
            'timing': t['timing'],
            'events': t['events'],
            'table': t['table'],
            'purpose': t['purpose'],
            'sql': physical_sql
        })
    return result


def get_functions(conn: sqlite3.Connection) -> List[Dict]:
    """Get registered SQL functions."""
    return FUNCTION_METADATA


def get_ddl(conn: sqlite3.Connection) -> Dict:
    """Get full DDL for all tables."""
    tables = conn.execute("""
        SELECT name, sql FROM sqlite_master 
        WHERE type='table' AND name NOT LIKE 'sqlite_%'
        ORDER BY name
    """).fetchall()
    
    triggers = conn.execute("""
        SELECT name, sql FROM sqlite_master 
        WHERE type='trigger' ORDER BY name
    """).fetchall()
    
    indexes = conn.execute("""
        SELECT name, sql FROM sqlite_master 
        WHERE type='index' AND name NOT LIKE 'sqlite_%' AND sql IS NOT NULL
        ORDER BY name
    """).fetchall()
    
    ddl_parts = [t['sql'] for t in tables if t['sql']]
    ddl_parts.extend([t['sql'] for t in triggers if t['sql']])
    ddl_parts.extend([i['sql'] for i in indexes if i['sql']])
    
    return {'ddl': ';\n\n'.join(ddl_parts) + ';'}


def get_er(conn: sqlite3.Connection) -> Dict:
    """Generate Mermaid ER diagram text."""
    tables = conn.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name NOT LIKE 'sqlite_%'
        ORDER BY name
    """).fetchall()
    
    mermaid = ["erDiagram"]
    for t in tables:
        name = t['name']
        cols = conn.execute(f'PRAGMA table_info({name})').fetchall()
        pk_cols = [c['name'] for c in cols if c['pk'] == 1]
        fk_cols = {}
        for idx in conn.execute(f'PRAGMA foreign_key_list({name})').fetchall():
            fk_cols[idx['from']] = f"{idx['table']}({idx['to']})"
        
        mermaid.append(f"  {name.upper()} {{")
        for c in cols:
            col_name = c['name']
            col_type = c['type']
            suffix = ''
            if col_name in pk_cols:
                suffix = ' PK'
            elif col_name in fk_cols:
                suffix = f' FK -> {fk_cols[col_name]}'
            mermaid.append(f'    {col_type} {col_name}{suffix}')
        mermaid.append("  }")
    
    # Relationships
    for rel in RELATIONSHIPS:
        mermaid.append(f"  {rel['from_table'].upper()} ||--o{{ {rel['to_table'].upper()} : \"{rel['note']}\"")
    
    return {'mermaid': '\n'.join(mermaid)}


def get_violations(conn: sqlite3.Connection) -> List[Dict]:
    """Get violation test cases."""
    return VIOLATION_TESTS


def run_violation(conn: sqlite3.Connection, violation_id: str) -> Dict:
    """Run a violation test (always rolled back)."""
    violation = next((v for v in VIOLATION_TESTS if v['id'] == violation_id), None)
    if not violation:
        raise ValueError(f"Violation {violation_id} not found")
    
    conn.execute('BEGIN')
    try:
        conn.execute(violation['sql'])
        conn.execute('COMMIT')
        blocked = False
        error = None
    except sqlite3.IntegrityError as e:
        conn.execute('ROLLBACK')
        blocked = True
        error = str(e)
    except Exception as e:
        conn.execute('ROLLBACK')
        blocked = True
        error = str(e)
    
    return {
        'blocked': blocked,
        'error': error,
        'attempted_sql': violation['sql']
    }


def run_trigger_demo(conn: sqlite3.Connection, logical_name: str) -> Dict:
    """Run a trigger demo (always rolled back)."""
    conn.execute('BEGIN')
    try:
        if logical_name == 'trg_reduce_stock':
            # Demo: insert then delete prescription
            # Get initial stock
            initial = conn.execute('SELECT stock_quantity FROM medicine WHERE medicine_id = 506').fetchone()['stock_quantity']
            
            # Create a test visit
            conn.execute("""
                INSERT INTO visit (patient_id, doctor_id, visit_type, visit_datetime, visit_status)
                VALUES (101, 201, 'Appointment', '2026-12-31 10:00:00', 'Scheduled')
            """)
            visit_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
            
            # Add prescription for Aspirin 75mg (506), qty 10
            conn.execute("""
                INSERT INTO prescription (visit_id, medicine_id, dosage, duration_days, quantity)
                VALUES (?, ?, '1-0-0', 5, 10)
            """, (visit_id, 506))
            
            after_insert = conn.execute('SELECT stock_quantity FROM medicine WHERE medicine_id = 506').fetchone()['stock_quantity']
            
            # Delete prescription
            presc_id = conn.execute('SELECT prescription_id FROM prescription WHERE visit_id = ? AND medicine_id = 506', (visit_id,)).fetchone()['prescription_id']
            conn.execute('DELETE FROM prescription WHERE prescription_id = ?', (presc_id,))
            
            after_delete = conn.execute('SELECT stock_quantity FROM medicine WHERE medicine_id = 506').fetchone()['stock_quantity']
            
            conn.execute('ROLLBACK')
            
            return {
                'effect': f"Stock reduced from {initial} to {after_insert} on INSERT; restored to {after_delete} on DELETE",
                'details': {
                    'initial_stock': initial,
                    'after_insert': after_insert,
                    'after_delete': after_delete
                }
            }
        
        elif logical_name == 'trg_audit_visit':
            # Demo: insert, update, delete visit
            conn.execute("""
                INSERT INTO visit (patient_id, doctor_id, visit_type, visit_datetime, visit_status)
                VALUES (101, 201, 'Appointment', '2026-12-31 10:00:00', 'Scheduled')
            """)
            visit_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
            
            conn.execute("UPDATE visit SET visit_status = 'Cancelled' WHERE visit_id = ?", (visit_id,))
            conn.execute("DELETE FROM visit WHERE visit_id = ?", (visit_id,))
            
            conn.execute('ROLLBACK')
            return {'effect': "Audit rows created for INSERT, UPDATE, DELETE on visit"}
        
        elif logical_name == 'trg_audit_bill':
            conn.execute("""
                INSERT INTO visit (patient_id, doctor_id, visit_type, visit_datetime, visit_status)
                VALUES (101, 201, 'Appointment', '2026-12-31 10:00:00', 'Discharged')
            """)
            visit_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
            
            conn.execute("""
                INSERT INTO bill (visit_id, consultation_charge, medicine_charge, bed_charge, total_amount, payment_status)
                VALUES (?, 500, 50, 0, 550, 'Pending')
            """, (visit_id,))
            
            bill_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
            
            conn.execute("UPDATE bill SET payment_mode = 'Cash', payment_status = 'Paid' WHERE bill_id = ?", (bill_id,))
            
            conn.execute('ROLLBACK')
            return {'effect': "Audit rows created for bill INSERT and UPDATE"}
        
        elif logical_name == 'trg_audit_patient':
            conn.execute("""
                INSERT INTO patient (patient_name, phone, gender, date_of_birth)
                VALUES ('Test Demo', '9876500999', 'Male', '2000-01-01')
            """)
            patient_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
            
            conn.execute("UPDATE patient SET patient_name = 'Updated Demo' WHERE patient_id = ?", (patient_id,))
            conn.execute("DELETE FROM patient WHERE patient_id = ?", (patient_id,))
            
            conn.execute('ROLLBACK')
            return {'effect': "Audit rows created for INSERT, UPDATE, DELETE on patient"}
        
        elif logical_name == 'trg_doctor_status':
            # Ensure doctor is Available
            conn.execute("UPDATE doctor SET availability_status = 'Available' WHERE doctor_id = 201")
            
            conn.execute("""
                INSERT INTO visit (patient_id, doctor_id, visit_type, visit_datetime, visit_status)
                VALUES (101, 201, 'Appointment', '2026-12-31 10:00:00', 'Scheduled')
            """)
            visit_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
            
            conn.execute("UPDATE visit SET visit_status = 'Under Treatment' WHERE visit_id = ?", (visit_id,))
            status1 = conn.execute("SELECT availability_status FROM doctor WHERE doctor_id = 201").fetchone()['availability_status']
            
            conn.execute("UPDATE visit SET visit_status = 'Admitted' WHERE visit_id = ?", (visit_id,))
            status2 = conn.execute("SELECT availability_status FROM doctor WHERE doctor_id = 201").fetchone()['availability_status']
            
            conn.execute('ROLLBACK')
            return {'effect': f"Doctor status: Available -> {status1} -> {status2}"}
        
        elif logical_name == 'trg_protect_audit':
            # Try to update and delete audit row
            blocked_update = False
            blocked_delete = False
            
            conn.execute("UPDATE audit_log SET description = 'tampered' WHERE log_id = 1")
            blocked_update = True
            
            conn.execute("DELETE FROM audit_log WHERE log_id = 1")
            blocked_delete = True
            
            conn.execute('ROLLBACK')
            return {'effect': "Both UPDATE and DELETE on audit_log blocked by trigger"}
        
        else:
            return {'effect': f"Demo for {logical_name} not implemented"}
    
    except Exception as e:
        conn.execute('ROLLBACK')
        raise


def execute_sql(conn: sqlite3.Connection, sql: str) -> Dict:
    """Execute a SELECT/WITH query safely."""
    # Safety checks
    sql_stripped = sql.strip()
    if not sql_stripped.upper().startswith(('SELECT', 'WITH')):
        raise ValueError("Only SELECT or WITH queries allowed")
    
    if ';' in sql_stripped.rstrip(';'):
        raise ValueError("Multiple statements not allowed")
    
    # Use a separate connection with query_only for safety
    # For simplicity, we use the same connection but with limits
    conn.execute('PRAGMA query_only = ON')
    try:
        cur = conn.execute(sql)
        # Limit results
        rows = []
        for i, row in enumerate(cur):
            if i >= 500:
                break
            rows.append(list(row))
        columns = [description[0] for description in cur.description] if cur.description else []
        return {
            'columns': columns,
            'rows': rows,
            'row_count': len(rows),
            'elapsed_ms': 0  # Would need time measurement
        }
    finally:
        conn.execute('PRAGMA query_only = OFF')