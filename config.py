"""
Application configuration for the Smart Hospital Management System.

Everything here can be overridden with environment variables so that tests and
demonstrations never have to touch the real ``hospital.db`` file:

    HOSPITAL_DB_PATH        path of the SQLite file to use (default: ./hospital.db)
    FLASK_API_MODE          "real" (default) or "stub" (serve fixtures/, no database)
    SECRET_KEY              Flask secret key (random per process if not set)
    HOSPITAL_DEBUG          set to "1" to run ``python app.py`` with the Flask debugger
    HOSPITAL_TRUSTED_HOSTS  comma separated Host names accepted by the server
                            (default: localhost,127.0.0.1,[::1])
"""
import os
import secrets

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Load .env file into os.environ if present (without external dependencies)
_env_file = os.path.join(BASE_DIR, '.env')
if os.path.exists(_env_file):
    try:
        with open(_env_file, 'r', encoding='utf-8') as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith('#') and '=' in _line:
                    _k, _v = _line.split('=', 1)
                    _k, _v = _k.strip(), _v.strip().strip("'\"")
                    if _k and _k not in os.environ:
                        os.environ[_k] = _v
    except Exception:
        pass


# The demonstration database that ships with the project.
DEFAULT_DB_PATH = os.path.join(BASE_DIR, 'hospital.db')

DB_PATH = os.environ.get('HOSPITAL_DB_PATH') or DEFAULT_DB_PATH

# No hard-coded secret. The application does not use signed sessions or cookies,
# so a fresh random key per process is sufficient and nothing sensitive is committed.
SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)

FLASK_API_MODE = os.environ.get('FLASK_API_MODE', 'real')  # 'real' or 'stub'
if FLASK_API_MODE not in ('real', 'stub'):
    raise RuntimeError(f"FLASK_API_MODE must be 'real' or 'stub', got {FLASK_API_MODE!r}")

DEBUG = os.environ.get('HOSPITAL_DEBUG') == '1'

TRUSTED_HOSTS = [
    h.strip() for h in
    os.environ.get('HOSPITAL_TRUSTED_HOSTS', 'localhost,127.0.0.1,[::1]').split(',')
    if h.strip()
]

# Role names used for server-side authorization and isolated test role simulation.
# Production identity is always derived from the authenticated user account.
ROLE_USERNAMES = {
    'Admin': 'ADMIN',
    'Receptionist': 'RECEPTION1',
    'Triage Nurse': 'TRIAGE_NURSE',
    'Doctor': 'DR_AMENON',
    'Billing': 'BILLING1',
}
DEFAULT_ROLE = 'Admin'

# Header every state-changing API request must carry (simple CSRF defence: a
# cross-site page cannot add custom headers without a CORS preflight, which this
# server never grants).
CSRF_HEADER = 'X-Requested-With'
CSRF_VALUE = 'HospitalApp'

# Session and cookie configuration
SESSION_COOKIE_NAME = os.environ.get('HOSPITAL_SESSION_COOKIE', 'hospital_session')
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = os.environ.get('HOSPITAL_COOKIE_SAMESITE', 'Lax')
SESSION_COOKIE_SECURE = os.environ.get('HOSPITAL_COOKIE_SECURE', '0') == '1'
SESSION_LIFETIME_HOURS = int(os.environ.get('HOSPITAL_SESSION_HOURS', '12'))

# Rate limiting settings for authentication
RATE_LIMIT_MAX_ATTEMPTS = int(os.environ.get('AUTH_MAX_ATTEMPTS', '5'))
RATE_LIMIT_LOCKOUT_MINUTES = int(os.environ.get('AUTH_LOCKOUT_MINUTES', '15'))

# Authentication is enabled unless explicitly disabled for isolated tests.
AUTH_REQUIRED = os.getenv('AUTH_REQUIRED', '1').strip().lower() in ('1', 'true', 'yes', 'on')
# Role simulation is a development/testing convenience only; never enable in production.
ROLE_SIMULATION_ENABLED = os.getenv('ROLE_SIMULATION_ENABLED', '0').strip().lower() in ('1', 'true', 'yes', 'on')

# Allowed origins for explicitly enabled cross-origin clients
CORS_ALLOWED_ORIGINS = [
    o.strip() for o in
    os.environ.get(
        'CORS_ALLOWED_ORIGINS',
        'http://localhost:5000,http://127.0.0.1:5000'
    ).split(',')
    if o.strip()
]


