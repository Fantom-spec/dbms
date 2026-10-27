"""
Test isolation.

The suite NEVER touches the project's ``hospital.db``.  Before any application module
is imported, ``HOSPITAL_DB_PATH`` is pointed at a throw-away database in a temporary
directory.  ``assert_safe_db`` is used by the fixtures as a second line of defence.
"""
import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

_TMP_DIR = tempfile.mkdtemp(prefix='hospital-tests-')
atexit.register(shutil.rmtree, _TMP_DIR, ignore_errors=True)
os.environ['HOSPITAL_DB_PATH'] = str(Path(_TMP_DIR) / 'test_hospital.db')
os.environ.pop('FLASK_API_MODE', None)          # tests choose the mode explicitly

REAL_DB = (PROJECT_DIR / 'hospital.db').resolve()


def assert_safe_db(path):
    """Refuse to run against the project's demonstration database."""
    if Path(path).resolve() == REAL_DB:
        raise RuntimeError('Refusing to run tests against the real hospital.db')


def pytest_sessionstart(session):
    import config
    assert_safe_db(config.DB_PATH)
