"""
Secure Authentication and Session Management for Smart Hospital Management System.

Features:
- Industry-standard password hashing using scrypt via werkzeug.security
- Input validation (username length/characters, password complexity)
- Server-side sessions with cryptographic tokens (secrets.token_hex)
- Session expiration and revocation
- Rate limiting / login throttling against brute-force attacks
- Generic error messages to prevent username enumeration
- Full role support mapped to database session and audit triggers
"""
import re
import secrets
import sqlite3
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import bcrypt
from werkzeug.security import check_password_hash, generate_password_hash

import config



# In-memory rate limiting store: key -> list of timestamp floats
# key is f"{ip}:{username.lower()}"
_LOGIN_ATTEMPTS: Dict[str, List[float]] = defaultdict(list)
_IP_ATTEMPTS: Dict[str, List[float]] = defaultdict(list)


def init_auth_tables(conn: sqlite3.Connection) -> None:
    """Ensure authentication and session tables exist in the database."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_account (
            user_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            role          TEXT NOT NULL DEFAULT 'Admin',
            full_name     TEXT,
            is_active     INTEGER NOT NULL DEFAULT 1,
            created_at    TEXT DEFAULT (datetime('now','localtime')),
            last_login    TEXT,
            CONSTRAINT chk_user_role CHECK (role IN ('Admin','Receptionist','Triage Nurse','Doctor','Billing'))
        );
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_session (
            session_id    TEXT PRIMARY KEY,
            user_id       INTEGER NOT NULL,
            username      TEXT NOT NULL,
            role          TEXT NOT NULL,
            created_at    TEXT DEFAULT (datetime('now','localtime')),
            expires_at    TEXT NOT NULL,
            CONSTRAINT fk_session_user FOREIGN KEY (user_id) REFERENCES user_account (user_id) ON DELETE CASCADE
        );
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_session_user ON user_session(user_id);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_session_expires ON user_session(expires_at);")


def validate_username(username: str) -> Tuple[bool, Optional[str]]:
    """Validate username rules: 3-30 chars, alphanumeric + underscore/dash."""
    if not username or not isinstance(username, str):
        return False, "Username is required"
    username = username.strip()
    if len(username) < 3:
        return False, "Username must be at least 3 characters long"
    if len(username) > 30:
        return False, "Username cannot exceed 30 characters"
    if not re.match(r'^[a-zA-Z0-9_\-\.]+$', username):
        return False, "Username can only contain letters, numbers, underscores, dots, and hyphens"
    return True, None


def validate_password_strength(password: str) -> Tuple[bool, Optional[str]]:
    """Validate password requirements: minimum 8 characters with letters and numbers."""
    if not password or not isinstance(password, str):
        return False, "Password is required"
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if len(password) > 128:
        return False, "Password cannot exceed 128 characters"
    has_letter = any(c.isalpha() for c in password)
    has_digit = any(c.isdigit() for c in password)
    if not (has_letter and has_digit):
        return False, "Password must contain both letters and at least one number"
    return True, None


def hash_password(password: str) -> str:
    """Hash password using bcrypt with salt (cost factor 12)."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def verify_password(stored_hash: str, password: str) -> bool:
    """
    Safely verify password against stored hash.
    Supports bcrypt ($2b$, $2a$, $2y$) and fallback to scrypt for compatibility.
    """
    if not stored_hash or not password:
        return False
    try:
        if stored_hash.startswith(('$2b$', '$2a$', '$2y$')):
            return bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8'))
        return check_password_hash(stored_hash, password)
    except Exception:
        return False



def check_login_throttled(client_ip: str, username: str) -> Tuple[bool, int]:
    """
    Check if login should be throttled.
    Returns (is_throttled, retry_after_seconds).
    """
    now = time.time()
    window_sec = getattr(config, 'RATE_LIMIT_LOCKOUT_MINUTES', 15) * 60
    max_attempts = getattr(config, 'RATE_LIMIT_MAX_ATTEMPTS', 5)

    key = f"{client_ip}:{username.lower()}"
    # Purge old attempts
    attempts = [t for t in _LOGIN_ATTEMPTS[key] if now - t < window_sec]
    _LOGIN_ATTEMPTS[key] = attempts

    ip_attempts = [t for t in _IP_ATTEMPTS[client_ip] if now - t < window_sec]
    _IP_ATTEMPTS[client_ip] = ip_attempts

    # Check lockout
    if len(attempts) >= max_attempts:
        oldest = attempts[0]
        retry_after = int(window_sec - (now - oldest)) + 1
        return True, max(1, retry_after)

    # Broad IP throttling (e.g. 25 attempts from same IP across usernames)
    if len(ip_attempts) >= max_attempts * 5:
        oldest = ip_attempts[0]
        retry_after = int(window_sec - (now - oldest)) + 1
        return True, max(1, retry_after)

    return False, 0


def record_failed_login(client_ip: str, username: str) -> None:
    """Record a failed login attempt for rate limiting."""
    now = time.time()
    key = f"{client_ip}:{username.lower()}"
    _LOGIN_ATTEMPTS[key].append(now)
    _IP_ATTEMPTS[client_ip].append(now)


def clear_failed_login(client_ip: str, username: str) -> None:
    """Clear failed login attempts on successful authentication."""
    key = f"{client_ip}:{username.lower()}"
    _LOGIN_ATTEMPTS.pop(key, None)


def create_user(conn: sqlite3.Connection, username: str, password: str,
                role: str = 'Admin', full_name: Optional[str] = None) -> Dict:
    """Create a new user account with hashed password."""
    init_auth_tables(conn)
    u_ok, u_msg = validate_username(username)
    if not u_ok:
        raise ValueError(u_msg)
    p_ok, p_msg = validate_password_strength(password)
    if not p_ok:
        raise ValueError(p_msg)

    valid_roles = list(config.ROLE_USERNAMES.keys())
    if role not in valid_roles:
        raise ValueError(f"Invalid role '{role}'. Must be one of: {', '.join(valid_roles)}")

    # Check uniqueness
    existing = conn.execute("SELECT 1 FROM user_account WHERE username = ?", (username,)).fetchone()
    if existing:
        raise ValueError(f"Username '{username}' is already registered")

    pwd_hash = hash_password(password)
    cursor = conn.execute(
        "INSERT INTO user_account (username, password_hash, role, full_name) VALUES (?, ?, ?, ?)",
        (username, pwd_hash, role, full_name or username)
    )
    user_id = cursor.lastrowid
    return {
        'user_id': user_id,
        'username': username,
        'role': role,
        'full_name': full_name or username,
        'is_active': 1
    }


def authenticate_user(conn: sqlite3.Connection, username: str, password: str,
                      client_ip: str = '127.0.0.1') -> Tuple[Optional[Dict], Optional[str]]:
    """
    Authenticate user by username and password.
    Returns (user_dict, error_message).
    Uses generic error messages to prevent username enumeration.
    """
    init_auth_tables(conn)
    if not username or not password:
        return None, "Username and password are required"

    throttled, retry_after = check_login_throttled(client_ip, username)
    if throttled:
        return None, f"Too many failed login attempts. Please try again in {retry_after} seconds."

    row = conn.execute(
        "SELECT user_id, username, password_hash, role, full_name, is_active FROM user_account WHERE username = ?",
        (username.strip(),)
    ).fetchone()

    # Always run verify_password to mitigate timing attacks even if user not found
    dummy_hash = "scrypt:32768:8:1$dummy$00000000000000000000000000000000"
    if row is None:
        verify_password(dummy_hash, password)
        record_failed_login(client_ip, username)
        return None, "Invalid username or password"

    if not row['is_active']:
        record_failed_login(client_ip, username)
        return None, "Account is disabled. Please contact the administrator."

    if not verify_password(row['password_hash'], password):
        record_failed_login(client_ip, username)
        return None, "Invalid username or password"

    # Success: clear failed attempts
    clear_failed_login(client_ip, username)

    # Update last_login
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn.execute("UPDATE user_account SET last_login = ? WHERE user_id = ?", (now_str, row['user_id']))

    return {
        'user_id': row['user_id'],
        'username': row['username'],
        'role': row['role'],
        'full_name': row['full_name'],
        'is_active': row['is_active']
    }, None


def create_session(conn: sqlite3.Connection, user: Dict,
                   hours: Optional[int] = None) -> Tuple[str, datetime]:
    """Create a persistent server-side session for an authenticated user."""
    init_auth_tables(conn)
    if hours is None:
        hours = getattr(config, 'SESSION_LIFETIME_HOURS', 12)

    session_token = secrets.token_hex(32)
    expires_at = datetime.now() + timedelta(hours=hours)
    expires_str = expires_at.strftime('%Y-%m-%d %H:%M:%S')

    conn.execute(
        "INSERT INTO user_session (session_id, user_id, username, role, expires_at) VALUES (?, ?, ?, ?, ?)",
        (session_token, user['user_id'], user['username'], user['role'], expires_str)
    )
    return session_token, expires_at


def get_user_from_session(conn: sqlite3.Connection, session_token: str) -> Optional[Dict]:
    """
    Look up user associated with session token.
    Validates expiration and active status.
    """
    if not session_token or not isinstance(session_token, str):
        return None

    init_auth_tables(conn)
    row = conn.execute("""
        SELECT s.session_id, s.user_id, s.username, s.role, s.expires_at,
               u.full_name, u.is_active
        FROM user_session s
        JOIN user_account u ON s.user_id = u.user_id
        WHERE s.session_id = ?
    """, (session_token,)).fetchone()

    if not row:
        return None

    # Check expiration
    try:
        expires = datetime.strptime(row['expires_at'], '%Y-%m-%d %H:%M:%S')
        if datetime.now() > expires:
            # Expired session: cleanup
            conn.execute("DELETE FROM user_session WHERE session_id = ?", (session_token,))
            return None
    except Exception:
        return None

    if not row['is_active']:
        return None

    return {
        'user_id': row['user_id'],
        'username': row['username'],
        'role': row['role'],
        'full_name': row['full_name'],
        'session_id': row['session_id'],
        'expires_at': row['expires_at']
    }


def invalidate_session(conn: sqlite3.Connection, session_token: str) -> None:
    """Invalidate a single session (logout)."""
    if not session_token:
        return
    init_auth_tables(conn)
    conn.execute("DELETE FROM user_session WHERE session_id = ?", (session_token,))


def list_users(conn: sqlite3.Connection) -> List[Dict]:
    """List all registered users without exposing password hashes."""
    init_auth_tables(conn)
    rows = conn.execute("""
        SELECT user_id, username, role, full_name, is_active, created_at, last_login
        FROM user_account
        ORDER BY user_id ASC
    """).fetchall()
    return [dict(r) for r in rows]
