#!/usr/bin/env python3
"""
Database initialization script for Smart Hospital Management System.
Deletes existing hospital.db and rebuilds from schema.sql -> seed.sql -> triggers.sql.

Usage: python -m db.init_db
"""
import os
import sys
import sqlite3
from pathlib import Path


def get_db_path() -> Path:
    """Get the database file path."""
    base_dir = Path(__file__).parent.parent
    return base_dir / 'hospital.db'


def get_sql_dir() -> Path:
    """Get the directory containing SQL files."""
    return Path(__file__).parent


def run_sql_file(conn: sqlite3.Connection, filepath: Path, description: str) -> None:
    """Execute a SQL file using execscript for proper handling of triggers."""
    print(f'  Running {description}...')
    sql = filepath.read_text()
    try:
        conn.executescript(sql)
    except sqlite3.Error as e:
        print(f'    ERROR in {filepath.name}: {e}')
        raise
    print(f'  {description} done.')


def init_database() -> None:
    """Initialize the database from scratch."""
    db_path = get_db_path()
    sql_dir = get_sql_dir()
    
    # Delete existing database
    if db_path.exists():
        print(f'Deleting existing database: {db_path}')
        db_path.unlink()
    
    # Create new database
    print('Creating new database...')
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    conn.execute('PRAGMA busy_timeout = 5000')
    
    try:
        # Run schema.sql
        run_sql_file(conn, sql_dir / 'schema.sql', 'schema.sql')
        
        # Run seed.sql
        run_sql_file(conn, sql_dir / 'seed.sql', 'seed.sql')
        
        # Run triggers.sql
        run_sql_file(conn, sql_dir / 'triggers.sql', 'triggers.sql')
        
        # Verify row counts (golden values from ARCHITECTURE.md section 9)
        print('\nVerifying row counts...')
        tables = [
            'patient', 'doctor', 'bed', 'medicine', 
            'visit', 'prescription', 'bill', 'audit_log'
        ]
        expected = {
            'patient': 12,
            'doctor': 10,
            'bed': 12,
            'medicine': 12,
            'visit': 20,
            'prescription': 22,
            'bill': 11,
            'audit_log': 12
        }
        
        all_ok = True
        for table in tables:
            count = conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
            expected_count = expected.get(table, 0)
            status = 'OK' if count == expected_count else 'MISMATCH'
            if count != expected_count:
                all_ok = False
            print(f'  {table}: {count} (expected {expected_count}) [{status}]')
        
        # Verify next autoincrement values (sqlite_sequence)
        print('\nVerifying next autoincrement values...')
        seq_expected = {
            'patient': 113,
            'visit': 421,
            'prescription': 623,
            'bill': 712,
            'audit_log': 13
        }
        for table, expected_seq in seq_expected.items():
            try:
                seq = conn.execute(
                    'SELECT seq FROM sqlite_sequence WHERE name = ?', (table,)
                ).fetchone()
                actual_seq = seq[0] + 1 if seq else 1
                status = 'OK' if actual_seq == expected_seq else 'MISMATCH'
                if actual_seq != expected_seq:
                    all_ok = False
                print(f'  {table}: next id = {actual_seq} (expected {expected_seq}) [{status}]')
            except sqlite3.Error:
                print(f'  {table}: no sequence (OK if no inserts yet)')
        
        print('\n' + ('=' * 50))
        if all_ok:
            print('SUCCESS: Database initialized with golden values!')
        else:
            print('WARNING: Some counts/sequences do not match golden values!')
        print('=' * 50)
        
    finally:
        conn.close()


if __name__ == '__main__':
    init_database()