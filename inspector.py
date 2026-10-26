"""
Transaction Inspector for Smart Hospital Management System.
Builds inspector objects with SQL trace, before/after snapshots, trigger/function info.
"""
import sqlite3
from typing import Dict, List, Any, Optional, Set
from datetime import datetime
from db.connection import get_trace_data, snapshot_table


# Track which tables were modified during a transaction
_modified_tables: Dict[str, Set[int]] = {}  # table -> set of PKs


def track_table_access(table: str, pk_values: List[Any] = None):
    """Called by services to track which tables/PKs were accessed."""
    if table not in _modified_tables:
        _modified_tables[table] = set()
    if pk_values:
        _modified_tables[table].update(pk_values)


def clear_tracking():
    """Clear the tracking for a new transaction."""
    _modified_tables.clear()


def build_inspector(conn: sqlite3.Connection, operation: str, 
                    component: Dict = None, tables: List[str] = None,
                    functions_used: List[Dict] = None,
                    error: Exception = None,
                    operation_type: str = "procedure") -> Dict:
    """
    Build an inspector object for the API response.
    
    Args:
        conn: Database connection
        operation: Human-readable operation name
        component: Dict with name, type, oracle_equivalent
        tables: List of table names touched (if None, uses tracked tables)
        functions_used: List of function info dicts
        error: Exception if operation failed
        operation_type: 'procedure', 'cursor', 'query', 'trigger', etc.
    
    Returns:
        Inspector dict for API envelope
    """
    # Get trace data (SQL statements, triggers fired)
    trace = get_trace_data()
    
    # Determine tables touched
    if tables is None:
        tables = list(_modified_tables.keys())
    
    # Build before/after snapshots
    before = {}
    after = {}
    
    if tables:
        for table in tables:
            pk_col = _get_pk_column(conn, table)
            pk_values = _modified_tables.get(table, set())
            
            if pk_values:
                # We don't have "before" snapshots easily, but we can get current state
                after[table] = snapshot_table(conn, table, pk_col, list(pk_values))
                # For before, we'd need to capture before the operation
                # This is a simplified version
                before[table] = []
    
    # Build inspector
    inspector = {
        "operation": operation,
        "component": component or {"name": operation, "type": operation_type, "oracle_equivalent": "N/A"},
        "tables": tables,
        "functions_used": functions_used or [],
        "triggers_fired": trace.get('triggers_fired', []),
        "sql": trace.get('sql', []),
        "before": before,
        "after": after,
        "viva": _build_viva(operation, tables, component, functions_used, trace, error),
        "elapsed_ms": 0  # Would need timing
    }
    
    # Clear tracking for next transaction
    clear_tracking()
    
    return inspector


def _get_pk_column(conn: sqlite3.Connection, table: str) -> str:
    """Get primary key column name for a table."""
    cols = conn.execute(f'PRAGMA table_info({table})').fetchall()
    for c in cols:
        if c['pk'] == 1:
            return c['name']
    return 'id'


def _build_viva(operation: str, tables: List[str], component: Dict, 
                functions_used: List[Dict], trace: Dict, error: Exception = None) -> Dict:
    """Build the viva explanation fields."""
    
    # Determine what the operation did
    if error:
        result = f"Failed: {error}"
    else:
        result = f"{operation} completed successfully"
    
    # Build effect description
    effects = []
    if 'visit' in tables and 'patient' in tables:
        effects.append("visit and patient tables modified")
    elif 'visit' in tables:
        effects.append("visit table modified")
    elif 'prescription' in tables and 'medicine' in tables:
        effects.append("prescription inserted; medicine stock reduced via trigger")
    elif 'bill' in tables:
        effects.append("bill generated with computed charges")
    elif 'audit_log' in tables:
        effects.append("audit row written")
    
    if not effects:
        effects.append(f"{', '.join(tables) if tables else 'no tables'} modified")
    
    return {
        "operation": operation,
        "tables": ", ".join(tables) if tables else "none",
        "component": component.get('name', operation) if component else operation,
        "effect": "; ".join(effects) if effects else "no effect",
        "result": result
    }


def register_table_modification(table: str, pk_values: List[Any]):
    """Register that a table was modified with given PK values (call from services)."""
    track_table_access(table, pk_values)


# For use by services to track modifications
def register_insert(table: str, pk_value: Any):
    track_table_access(table, [pk_value])


def register_update(table: str, pk_value: Any):
    track_table_access(table, [pk_value])


def register_delete(table: str, pk_value: Any):
    track_table_access(table, [pk_value])