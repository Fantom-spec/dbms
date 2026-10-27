#!/usr/bin/env python3
"""
Safe database initialisation for the Smart Hospital Management System.

Builds a database from ``schema.sql -> seed.sql -> triggers.sql`` and verifies the
golden row counts from ARCHITECTURE.md / docs/API_CONTRACT.md section 9.

SAFETY (this replaced a script that unconditionally deleted ``hospital.db``):

* The new database is built in a temporary file next to the target and verified
  first. The target is only replaced (atomically, ``os.replace``) if the build
  succeeded, so a failure can never leave you without a database.
* If the target already exists the script REFUSES to run unless ``--force`` is
  given, and then it first copies the old file to ``<name>.bak-<timestamp>``
  (disable with ``--no-backup``).
* The target path is explicit (``--db PATH`` / ``HOSPITAL_DB_PATH``); tests always
  use a temporary path and never touch the project's ``hospital.db``.

Usage::

    python -m db.init_db                    # create hospital.db if it does not exist
    python -m db.init_db --db /tmp/demo.db  # create a different database
    python -m db.init_db --force            # rebuild, keeping a timestamped backup
"""
import argparse
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Union

SQL_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SQL_DIR.parent

PathLike = Union[str, os.PathLike]

# Golden values on a freshly seeded database.
GOLDEN_COUNTS: Dict[str, int] = {
    'patient': 12, 'doctor': 10, 'bed': 12, 'medicine': 12,
    'visit': 20, 'prescription': 22, 'bill': 11, 'audit_log': 12,
}
# sqlite_sequence value + 1 = id given to the next inserted row.
GOLDEN_NEXT_IDS: Dict[str, int] = {
    'patient': 113, 'visit': 421, 'prescription': 623, 'bill': 712, 'audit_log': 13,
}


class DatabaseExistsError(RuntimeError):
    """Raised when the target database exists and ``force`` was not requested."""


class DatabaseBuildError(RuntimeError):
    """Raised when the freshly built database fails verification."""


def default_db_path() -> Path:
    """The database used when no path is given (HOSPITAL_DB_PATH or ./hospital.db)."""
    return Path(os.environ.get('HOSPITAL_DB_PATH') or PROJECT_DIR / 'hospital.db')


def _run_sql_file(conn: sqlite3.Connection, name: str) -> None:
    conn.executescript((SQL_DIR / name).read_text(encoding='utf-8'))


def table_counts(conn: sqlite3.Connection) -> Dict[str, int]:
    """Row counts of the eight domain tables."""
    return {t: conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
            for t in GOLDEN_COUNTS}


def verify_golden(conn: sqlite3.Connection) -> list:
    """Return a list of human readable mismatches (empty list = all golden)."""
    problems = []
    for table, expected in GOLDEN_COUNTS.items():
        actual = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        if actual != expected:
            problems.append(f'{table}: {actual} rows (expected {expected})')
    for table, expected_next in GOLDEN_NEXT_IDS.items():
        row = conn.execute('SELECT seq FROM sqlite_sequence WHERE name = ?', (table,)).fetchone()
        actual_next = (row[0] + 1) if row else 1
        if actual_next != expected_next:
            problems.append(f'{table}: next id {actual_next} (expected {expected_next})')
    return problems


def build_database(db_path: PathLike) -> Dict[str, int]:
    """
    Build a brand new database file at ``db_path`` (which must not exist yet) and
    verify golden values. Removes the partial file and raises on any failure.
    """
    db_path = Path(db_path)
    if db_path.exists():
        raise DatabaseExistsError(f'{db_path} already exists')
    conn = None
    try:
        conn = sqlite3.connect(str(db_path), isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys = ON')
        conn.execute('PRAGMA busy_timeout = 5000')
        _run_sql_file(conn, 'schema.sql')
        _run_sql_file(conn, 'seed.sql')       # before triggers: seed must not create audit rows
        _run_sql_file(conn, 'triggers.sql')
        problems = verify_golden(conn)
        if problems:
            raise DatabaseBuildError('golden value check failed: ' + '; '.join(problems))
        counts = table_counts(conn)
    except Exception:
        if conn is not None:
            conn.close()
            conn = None
        _remove_sqlite_files(db_path)
        raise
    finally:
        if conn is not None:
            conn.close()
    return counts


def _remove_sqlite_files(db_path: Path) -> None:
    for suffix in ('', '-journal', '-wal', '-shm'):
        p = Path(str(db_path) + suffix)
        if p.exists():
            p.unlink()


def backup_database(db_path: PathLike, backup_path: Optional[PathLike] = None) -> Path:
    """Copy ``db_path`` to a backup file and return the backup path."""
    db_path = Path(db_path)
    if backup_path is None:
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        backup_path = db_path.with_name(f'{db_path.name}.bak-{stamp}')
    backup_path = Path(backup_path)
    # Use the sqlite backup API so a database that is open elsewhere is copied consistently.
    src = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
    try:
        dst = sqlite3.connect(str(backup_path))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    return backup_path


def init_database(db_path: Optional[PathLike] = None, *, force: bool = False,
                  backup: Union[bool, str, os.PathLike] = True, quiet: bool = True) -> Dict[str, int]:
    """
    Create (or, with ``force=True``, rebuild) the database at ``db_path``.

    ``backup``: True -> timestamped copy ``<name>.bak-<ts>`` before replacing an existing file;
                False -> no backup; a path -> back up to exactly that file (overwritten).
    Returns the table row counts of the new database.
    """
    target = Path(db_path) if db_path else default_db_path()
    exists = target.exists()
    if exists and not force:
        raise DatabaseExistsError(
            f'{target} already exists. Refusing to overwrite it. '
            f'Re-run with --force to rebuild it (a backup copy is made first).')
    target.parent.mkdir(parents=True, exist_ok=True)

    tmp = target.with_name(f'{target.name}.build-{os.getpid()}.tmp')
    _remove_sqlite_files(tmp)
    counts = build_database(tmp)          # raises + cleans up on failure; target untouched

    try:
        if exists and backup:
            bpath = backup_database(target, None if backup is True else backup)
            if not quiet:
                print(f'Backed up existing database to {bpath}')
        os.replace(tmp, target)           # atomic on POSIX and Windows
    finally:
        _remove_sqlite_files(tmp)
    if not quiet:
        print(f'Database ready: {target}')
    return counts


def reset_in_place(db_path: PathLike) -> Dict[str, int]:
    """
    Restore the seeded data INSIDE the existing database file (used by the web UI).

    A fresh database is built and verified in a temporary file, the current file is
    copied to ONE rolling ``<name>.pre-reset.bak``, and then the fresh data is written
    over the live file with the SQLite backup API.  Unlike deleting/replacing the file
    this is safe while other connections have it open.
    """
    db_path = Path(db_path)
    tmp = db_path.with_name(f'{db_path.name}.reset-{os.getpid()}.tmp')
    _remove_sqlite_files(tmp)
    build_database(tmp)
    try:
        if db_path.exists():
            backup_database(db_path, db_path.with_name(db_path.name + '.pre-reset.bak'))
        src = sqlite3.connect(str(tmp))
        try:
            dst = sqlite3.connect(str(db_path), timeout=10)
            try:
                src.backup(dst)
                counts = table_counts(dst)
            finally:
                dst.close()
        finally:
            src.close()
    finally:
        _remove_sqlite_files(tmp)
    return counts


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='Initialise the Smart Hospital database safely.')
    ap.add_argument('--db', help='database file (default: HOSPITAL_DB_PATH or ./hospital.db)')
    ap.add_argument('--force', action='store_true',
                    help='rebuild even if the database exists (a backup copy is made first)')
    ap.add_argument('--no-backup', action='store_true', help='with --force: do not keep a backup copy')
    args = ap.parse_args(argv)
    target = Path(args.db) if args.db else default_db_path()
    try:
        counts = init_database(target, force=args.force, backup=not args.no_backup, quiet=False)
    except DatabaseExistsError as e:
        print(f'NOT CHANGED: {e}', file=sys.stderr)
        return 2
    except (DatabaseBuildError, sqlite3.Error, OSError) as e:
        print(f'FAILED: {e}', file=sys.stderr)
        return 1
    print('Row counts: ' + ', '.join(f'{k}={v}' for k, v in counts.items()))
    print('SUCCESS: golden values verified.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
