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
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

# Optional PostgreSQL support via psycopg (v3)
try:
    import psycopg
    from psycopg import Connection as PgConnection
    from psycopg.rows import dict_row
except Exception:
    psycopg = None
    PgConnection = None
    dict_row = None

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


def get_connection(db_path: PathLike, *, read_only: bool = False) -> Union[HospitalConnection, PgConnection]:
    """Create a database connection.

    If Supabase/PostgreSQL environment variables are present, a PostgreSQL
    connection (via psycopg) is returned. Otherwise the original SQLite
    connection is created.
    """
    # Detect Supabase connection parameters
    pg_url = os.getenv('DATABASE_URL') or os.getenv('SUPABASE_DB_URL')
    if pg_url and psycopg:
        # PostgreSQL path – ignore read_only (psycopg default is read/write)
        conn = psycopg.connect(pg_url, row_factory=dict_row, isolation_level="read committed")
        # Ensure UTC timestamps for consistency
        conn.execute('SET TIME ZONE UTC')
        return conn

    # Fallback to SQLite (existing behavior)
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


def register_udfs(conn) -> None:
    """Register user‑defined functions for SQLite.
    For PostgreSQL the equivalents are defined in ``db/schema_pg.sql`` and
    therefore no registration is needed. This function simply returns when a
    PostgreSQL connection is supplied.
    """
    # If this is a psycopg connection, skip registration – functions are already
    # present in the database.
    if psycopg and PgConnection is not None and isinstance(conn, PgConnection):
        return

    # SQLite path – unchanged implementation
    def fn_days_stayed(visit_id) -> int:
        row = conn.execute(
            'SELECT admit_time, discharge_time FROM visit WHERE visit_id = ?', (visit_id,)
        ).fetchone()
        if not row:
            return 0
        admit = parse_timestamp(row[0])
        if admit is None:
            return 0
        end = parse_timestamp(row[1]) or datetime.now()
        return max((end.date() - admit.date()).days, 1)

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
