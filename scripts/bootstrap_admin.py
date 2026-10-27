#!/usr/bin/env python3
"""
Secure Administrator Bootstrap CLI.

Usage:
  Interactive mode:
    python scripts/bootstrap_admin.py

  Non-interactive mode (e.g. Docker, CI/CD, deployment scripts):
    HOSPITAL_ADMIN_USER=admin HOSPITAL_ADMIN_PASSWORD=StrongPass123! python scripts/bootstrap_admin.py

  Optional username can be provided with --username. Passwords should be entered
  interactively or supplied through a protected deployment secret environment variable.
"""
import argparse
import getpass
import os
import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import config
from auth import create_user, init_auth_tables, validate_password_strength, validate_username
from db.connection import get_connection


def bootstrap_admin(username=None, password=None, role="Admin", full_name="System Administrator", db_path=None):
    target_db = db_path or config.DB_PATH
    print(f"[*] Initializing database connection: {target_db}")
    conn = get_connection(target_db)

    try:
        init_auth_tables(conn)

        # Check if environment variables provided
        if not username:
            username = os.environ.get("HOSPITAL_ADMIN_USER") or os.environ.get("ADMIN_USERNAME")
        if not password:
            password = os.environ.get("HOSPITAL_ADMIN_PASSWORD") or os.environ.get("ADMIN_PASSWORD")

        # Interactive prompts if still missing and running in interactive TTY
        if not username:
            if sys.stdin.isatty():
                while True:
                    username_in = input("Enter administrator username [default: admin]: ").strip()
                    username = username_in if username_in else "admin"
                    ok, msg = validate_username(username)
                    if ok:
                        break
                    print(f"[-] Invalid username: {msg}")
            else:
                print("[-] Error: Username must be provided via argument or HOSPITAL_ADMIN_USER environment variable.", file=sys.stderr)
                return 1

        # Check if user already exists
        existing = conn.execute("SELECT user_id, role FROM user_account WHERE username = ?", (username,)).fetchone()
        if existing:
            print(f"[!] User '{username}' already exists with role '{existing['role']}'.")
            return 0

        if not password:
            if sys.stdin.isatty():
                while True:
                    pwd1 = getpass.getpass("Enter administrator password (min 8 chars, letters & numbers): ")
                    pwd2 = getpass.getpass("Confirm administrator password: ")
                    if pwd1 != pwd2:
                        print("[-] Passwords do not match. Try again.")
                        continue
                    ok, msg = validate_password_strength(pwd1)
                    if not ok:
                        print(f"[-] Password too weak: {msg}")
                        continue
                    password = pwd1
                    break
            else:
                print("[-] Error: Password must be provided via argument or HOSPITAL_ADMIN_PASSWORD environment variable.", file=sys.stderr)
                return 1

        user = create_user(conn, username=username, password=password, role=role, full_name=full_name)
        print(f"[+] Successfully created {role} user '{username}' (User ID: {user['user_id']}).")
        return 0

    except Exception as e:
        print(f"[-] Bootstrap failed: {e}", file=sys.stderr)
        return 1
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Bootstrap Administrator Account for Hospital Management System")
    parser.add_argument("-u", "--username", help="Administrator username")
    parser.add_argument("-r", "--role", default="Admin", help="Role (default: Admin)")
    parser.add_argument("--name", default="System Administrator", help="Full name")
    parser.add_argument("--db", help="Path to database file")

    args = parser.parse_args()
    return bootstrap_admin(username=args.username, role=args.role,
                           full_name=args.name, db_path=args.db)


if __name__ == "__main__":
    sys.exit(main())
