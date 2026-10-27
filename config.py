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

# Simulated roles (NOT real authentication - see docs/SECURITY.md).
# role name -> username written to app_session and therefore to audit_log.changed_by
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
