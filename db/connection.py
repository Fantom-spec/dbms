"""
Database connection utilities for Smart Hospital Management System.
Provides connection setup, UDF registration, and trace hook for inspector.
"""
import sqlite3
from datetime import datetime
from typing import Optional, List, Tuple, Any


def get_connection(db_path: str) -> sqlite3.Connection:
    """
    Create a new SQLite connection with proper configuration.
    
    Args:
        db_path: Path to the SQLite database file
        
    Returns:
        Configured sqlite3.Connection with:
        - isolation_level=None (manual transaction control)
        - row_factory=sqlite3.Row (named column access)
        - PRAGMA foreign_keys=ON
        - PRAGMA busy_timeout=5000
        - UDFs registered (fn_days_stayed, fn_medicine_cost, fn_triage_label)
    """
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    
    # Enable foreign key enforcement (must be set per connection)
    conn.execute('PRAGMA foreign_keys = ON')
    # Wait up to 5 seconds for locked database
    conn.execute('PRAGMA busy_timeout = 5000')
    
    # Register user-defined functions
    register_udfs(conn)
    
    return conn


def register_udfs(conn: sqlite3.Connection) -> None:
    """
    Register SQLite user-defined functions (UDFs) that can be called from SQL.
    
    These mirror the Oracle PL/SQL functions from Review II:
    - fn_days_stayed(visit_id): days between admit and discharge (or now), min 1
    - fn_medicine_cost(visit_id): SUM(quantity * price_per_unit) for visit
    - fn_triage_label(level): 1=Critical, 2=Very urgent, 3=Urgent, 4=Minor, else Not triaged
    """
    
    def fn_days_stayed(visit_id: int) -> int:
        """Calculate days stayed for a visit. 0 if never admitted, minimum 1 if admitted."""
        cur = conn.cursor()
        cur.execute(
            'SELECT admit_time, discharge_time FROM visit WHERE visit_id = ?',
            (visit_id,)
        )
        row = cur.fetchone()
        if not row:
            return 0  # Visit not found
        
        admit_time = row['admit_time']
        discharge_time = row['discharge_time']
        
        if not admit_time:
            return 0  # Never admitted
        
        # Parse admit time
        try:
            admit_dt = datetime.strptime(admit_time, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            # Try date only format
            admit_dt = datetime.strptime(admit_time, '%Y-%m-%d')
        
        # Use discharge time or current time
        if discharge_time:
            try:
                disch_dt = datetime.strptime(discharge_time, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                disch_dt = datetime.strptime(discharge_time, '%Y-%m-%d')
        else:
            disch_dt = datetime.now()
        
        # Calculate day difference (date part only)
        days = (disch_dt.date() - admit_dt.date()).days
        return max(days, 1)  # At least 1 day charged
    
    def fn_medicine_cost(visit_id: int) -> float:
        """Calculate total medicine cost for a visit."""
        cur = conn.cursor()
        cur.execute('''
            SELECT COALESCE(SUM(p.quantity * m.price_per_unit), 0) as total
            FROM prescription p
            JOIN medicine m ON m.medicine_id = p.medicine_id
            WHERE p.visit_id = ?
        ''', (visit_id,))
        row = cur.fetchone()
        return float(row['total']) if row and row['total'] is not None else 0.0
    
    def fn_triage_label(level: Optional[int]) -> str:
        """Convert triage level to label."""
        if level is None:
            return 'Not triaged'
        labels = {
            1: 'Critical',
            2: 'Very urgent',
            3: 'Urgent',
            4: 'Minor'
        }
        return labels.get(level, 'Not triaged')
    
    # Register with SQLite (deterministic=True for fn_triage_label allows query optimization)
    conn.create_function('fn_days_stayed', 1, fn_days_stayed)
    conn.create_function('fn_medicine_cost', 1, fn_medicine_cost)
    conn.create_function('fn_triage_label', 1, fn_triage_label, deterministic=True)


# ===== Transaction Inspector Trace Hook =====

class SQLTracer:
    """Collects SQL statements executed during a transaction for the inspector."""
    
    def __init__(self):
        self.statements: List[str] = []
        self.triggers_fired: List[dict] = []
        self._in_trigger = False
    
    def callback(self, statement: str) -> None:
        """Trace callback invoked by SQLite for each SQL statement."""
        if not statement:
            return
        
        stmt = statement.strip()
        if not stmt:
            return
        
        # Detect trigger execution (SQLite emits -- TRIGGER name comments)
        if stmt.startswith('-- TRIGGER '):
            # Extract trigger name from comment
            trigger_name = stmt[11:].strip()
            self.triggers_fired.append({
                'name': trigger_name,
                'event': 'EXECUTED',  # We don't easily get BEFORE/AFTER/INSTEAD OF
                'effect': f'Trigger {trigger_name} fired'
            })
            self._in_trigger = True
            return
        
        # Skip trigger body statements (they come after the -- TRIGGER comment)
        if self._in_trigger and stmt.startswith('--'):
            return
        
        # Reset trigger flag on actual SQL statements
        if self._in_trigger and not stmt.startswith('--'):
            self._in_trigger = False
        
        # Collect the statement (skip transaction control for cleaner output)
        if not stmt.startswith(('BEGIN', 'COMMIT', 'ROLLBACK', 'SAVEPOINT', 'RELEASE')):
            # Truncate very long statements
            if len(stmt) > 500:
                stmt = stmt[:500] + '... [truncated]'
            self.statements.append(stmt)
    
    def get_data(self) -> dict:
        """Return collected trace data."""
        # Deduplicate triggers_fired by name
        seen = set()
        unique_triggers = []
        for t in self.triggers_fired:
            if t['name'] not in seen:
                seen.add(t['name'])
                unique_triggers.append(t)
        
        return {
            'sql': self.statements,
            'triggers_fired': unique_triggers
        }
    
    def reset(self) -> None:
        """Clear collected data for next transaction."""
        self.statements.clear()
        self.triggers_fired.clear()
        self._in_trigger = False


# Global tracer instance (one per request, stored on flask.g)
_tracer: Optional[SQLTracer] = None


def install_trace(conn: sqlite3.Connection) -> None:
    """Install the trace callback on a connection."""
    global _tracer
    _tracer = SQLTracer()
    conn.set_trace_callback(_tracer.callback)


def get_trace_data() -> dict:
    """Get collected trace data and reset tracer."""
    global _tracer
    if _tracer is None:
        return {'sql': [], 'triggers_fired': []}
    data = _tracer.get_data()
    _tracer.reset()
    return data


def snapshot_table(conn: sqlite3.Connection, table: str, pk_column: str, 
                   pk_values: List[Any]) -> List[dict]:
    """
    Snapshot rows from a table by primary key values.
    
    Args:
        conn: Database connection
        table: Table name
        pk_column: Primary key column name
        pk_values: List of primary key values to fetch
        
    Returns:
        List of row dictionaries
    """
    if not pk_values:
        return []
    
    placeholders = ','.join(['?'] * len(pk_values))
    query = f'SELECT * FROM {table} WHERE {pk_column} IN ({placeholders})'
    cur = conn.execute(query, pk_values)
    return [dict(row) for row in cur.fetchall()]


def snapshot_before_after(conn: sqlite3.Connection, 
                          tables_pks: dict) -> Tuple[dict, dict]:
    """
    Snapshot tables before and after an operation.
    
    Args:
        conn: Database connection
        tables_pks: Dict of {table: pk_column} for tables to snapshot
        
    Returns:
        Tuple of (before_dict, after_dict) where each dict maps table -> list of row dicts
    """
    # This is called by the service layer which knows what it will touch
    # The service should call snapshot before and after the operation
    pass