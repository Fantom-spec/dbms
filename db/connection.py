"""
Database connection utilities for the Smart Hospital Management System.

Provides connection set-up (PRAGMAs, row factory) and registration of the SQL
user-defined functions that mirror the Review II PL/SQL functions.

There is deliberately NO module-level mutable state here: transaction-inspector
state lives on the connection object itself (``HospitalConnection.insp``), so
concurrent requests handled by different threads can never see each other's SQL
trace or row changes.
"""
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

PathLike = Union[str, Path]

_TS_FORMATS = ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d')


class HospitalConnection(sqlite3.Connection):
    """A sqlite3.Connection that may carry transaction-inspector state."""
    insp = None


def parse_timestamp(value: Optional[str]) -> Optional[datetime]:
    """Parse the timestamp formats used by the schema; None if empty/unparseable."""
    if not value:
        return None
    text = str(value).strip().replace('T', ' ')
    for fmt in _TS_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def get_connection(db_path: PathLike, *, read_only: bool = False) -> HospitalConnection:
    """
    Open a configured connection.

    * ``isolation_level=None`` -> transactions are controlled explicitly (BEGIN/COMMIT).
    * ``row_factory=sqlite3.Row`` -> rows can be read by column name.
    * ``PRAGMA foreign_keys=ON`` (must be set per connection, SQLite default is OFF).
    * ``PRAGMA busy_timeout=5000`` -> wait up to 5 s for a competing writer.
    * UDFs fn_days_stayed / fn_medicine_cost / fn_triage_label are registered.
    * ``read_only=True`` opens the file with ``mode=ro`` (writes are impossible).
    """
    if read_only:
        uri = Path(db_path).resolve().as_uri() + '?mode=ro'
        conn = sqlite3.connect(uri, uri=True, isolation_level=None,
                               factory=HospitalConnection, check_same_thread=True)
    else:
        conn = sqlite3.connect(str(db_path), isolation_level=None,
                               factory=HospitalConnection, check_same_thread=True)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    conn.execute('PRAGMA busy_timeout = 5000')
    register_udfs(conn)
    return conn


def register_udfs(conn: sqlite3.Connection) -> None:
    """
    Register the SQL functions (mirroring the Oracle PL/SQL functions of Review II):

    * fn_days_stayed(visit_id)  - 0 if never admitted, else whole days between admit and
                                  discharge (or now), minimum 1
    * fn_medicine_cost(visit_id) - SUM(quantity * price_per_unit) of the visit's prescriptions
    * fn_triage_label(level)    - 1 Critical, 2 Very urgent, 3 Urgent, 4 Minor, else Not triaged
    """

    def fn_days_stayed(visit_id) -> int:
        row = conn.execute(
            'SELECT admit_time, discharge_time FROM visit WHERE visit_id = ?', (visit_id,)
        ).fetchone()
        if not row:
            return 0
        admit = parse_timestamp(row[0])
        if admit is None:
            return 0                      # never admitted
        end = parse_timestamp(row[1]) or datetime.now()
        return max((end.date() - admit.date()).days, 1)   # at least one day is charged

    def fn_medicine_cost(visit_id) -> float:
        row = conn.execute(
            '''SELECT COALESCE(SUM(p.quantity * m.price_per_unit), 0)
               FROM prescription p JOIN medicine m ON m.medicine_id = p.medicine_id
               WHERE p.visit_id = ?''', (visit_id,)
        ).fetchone()
        return float(row[0]) if row and row[0] is not None else 0.0

    def fn_triage_label(level) -> str:
        return {1: 'Critical', 2: 'Very urgent', 3: 'Urgent', 4: 'Minor'}.get(level, 'Not triaged')

    conn.create_function('fn_days_stayed', 1, fn_days_stayed)
    conn.create_function('fn_medicine_cost', 1, fn_medicine_cost)
    conn.create_function('fn_triage_label', 1, fn_triage_label, deterministic=True)
