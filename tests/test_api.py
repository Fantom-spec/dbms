"""API integration tests (Flask test client, temporary database, real mode)."""
import json
import sqlite3
from pathlib import Path

import pytest

from conftest import assert_safe_db
import app as app_module

H = {'X-Requested-With': 'HospitalApp'}


@pytest.fixture()
def api(tmp_path):
    db = tmp_path / 'api_test.db'
    application = app_module.create_app({'TESTING': True, 'DB_PATH': str(db), 'FLASK_API_MODE': 'real'})
    assert_safe_db(db)
    client = application.test_client()

    class Api:
        path = db

        def call(self, method, url, body=None, role='Admin', headers=None):
            hdr = {**H, 'X-Role': role, **(headers or {})}
            r = client.open(url, method=method, json=body, headers=hdr) if body is not None \
                else client.open(url, method=method, headers=hdr)
            return r.status_code, r.get_json()

        def get(self, url, **kw): return self.call('GET', url, **kw)
        def post(self, url, body=None, **kw): return self.call('POST', url, {} if body is None else body, **kw)
        def raw(self): return sqlite3.connect(str(db))
    return Api()


def assert_envelope(js):
    assert set(js) >= {'ok', 'message', 'data', 'error', 'inspector'}
    if js['ok']:
        assert js['error'] is None
    else:
        assert js['data'] is None
        assert {'kind', 'code', 'constraint', 'detail'} <= set(js['error'])
        assert js['error']['kind'] in ('constraint', 'business_rule', 'not_found', 'validation', 'internal')


def test_database_created_when_missing(api):
    assert api.path.exists()
    s, js = api.get('/api/meta')
    assert s == 200 and js['data']['counts']['patient'] == 12 and js['data']['role'] == 'Admin'


GETS = ['/api/meta', '/api/lookups', '/api/dashboard', '/api/patients', '/api/patients/107/history', '/api/doctors',
        '/api/medicines', '/api/medicines/low-stock', '/api/beds', '/api/visits', '/api/visits/407/summary',
        '/api/emergency/queue', '/api/visits/407/prescriptions', '/api/bills', '/api/bills/pending', '/api/reports',
        '/api/audit',
        '/api/demo/steps', '/api/demo/state'] + [f'/api/reports/q{i:02d}' for i in range(1, 20)]


@pytest.mark.parametrize('url', GETS)
def test_get_endpoints(api, url):
    s, js = api.get(url)
    assert s == 200 and js['ok'], js
    assert_envelope(js)


def test_unknown_endpoint_and_ids_are_enveloped(api):
    s, js = api.get('/api/nope')
    assert s == 404 and js['ok'] is False
    for url, code in [('/api/patients/9999/history', 'PATIENT_NOT_FOUND'), ('/api/visits/9999/summary', 'VISIT_NOT_FOUND'),
                      ('/api/reports/q99', 'REPORT_NOT_FOUND')]:
        s, js = api.get(url)
        assert s == 200 and js['error']['code'] == code and js['error']['kind'] == 'not_found', (url, js)


def test_csrf_header_required(api):
    s, js = api.call('POST', '/api/patients', {'patient_name': 'x'}, headers={'X-Requested-With': ''})
    assert s == 403 and js['error']['code'] == 'CSRF_REQUIRED'
    assert api.raw().execute('SELECT COUNT(*) FROM patient').fetchone()[0] == 12


def test_bad_json_is_400_envelope(api):
    import app as a
    c = a.create_app({'TESTING': True, 'DB_PATH': str(api.path)}).test_client()
    r = c.post('/api/patients', data='[1,2', headers={**H, 'Content-Type': 'application/json'})
    assert r.status_code == 400 and r.get_json()['ok'] is False
    r = c.post('/api/patients', data='[1]', headers={**H, 'Content-Type': 'application/json'})
    assert r.status_code == 400


def test_unknown_role_rejected(api):
    s, js = api.get('/api/meta', role='Hacker')
    assert s == 400 and js['error']['code'] == 'INVALID_ROLE'


PATIENT = {'patient_name': 'Test Person', 'gender': 'Male', 'date_of_birth': '1990-01-01', 'phone': '9000000001'}


def test_create_patient_audit_user_follows_role(api):
    s, js = api.post('/api/patients', PATIENT, role='Receptionist')
    assert js['ok'] and js['data']['patient_id'] == 113
    insp = js['inspector']
    assert insp['tables'] == ['patient', 'audit_log']
    assert [t['name'] for t in insp['triggers_fired']] == ['trg_audit_patient__insert']
    assert insp['after']['patient'][0]['patient_name'] == 'Test Person' and insp['before']['patient'] == []
    assert any('INSERT INTO patient' in q for q in insp['sql'])
    row = api.raw().execute("SELECT changed_by FROM audit_log WHERE table_name='PATIENT' ORDER BY log_id DESC").fetchone()
    assert row[0] == 'RECEPTION1'


def test_validation_and_constraints_roll_back(api):
    s, js = api.post('/api/patients', {**PATIENT, 'patient_name': ''})
    assert s == 200 and js['error']['code'] == 'VALIDATION_ERROR' and js['inspector']['tables'] == []
    s, js = api.post('/api/patients', {**PATIENT, 'phone': '123'})
    assert not js['ok'] and js['error']['kind'] == 'constraint'
    s, js = api.post('/api/patients', {**PATIENT, 'blood_group': ''})       # blank optional -> NULL
    assert js['ok'], js
    s, js = api.post('/api/patients', {**PATIENT, 'phone': '9000000001'})   # duplicate phone
    assert js['error']['code'] == 'UQ_PATIENT_PHONE'
    s, js = api.post('/api/patients', {**PATIENT, 'phone': '9000000002', 'patient_name': 'x' * 5000})
    assert js['error']['code'] == 'VALIDATION_ERROR'
    assert api.raw().execute('SELECT COUNT(*) FROM patient').fetchone()[0] == 13


def test_xss_payload_is_stored_verbatim_not_executed(api):
    name = '<img src=x onerror=alert(1)>'
    s, js = api.post('/api/patients', {**PATIENT, 'patient_name': name})
    assert js['ok']
    s, js = api.get('/api/patients?q=img')
    assert js['data'][0]['patient_name'] == name          # escaping is the frontend's job (tested in the browser)


def test_like_wildcards_are_literal(api):
    s, js = api.get('/api/patients?q=%25')
    assert js['ok'] and js['data'] == []


def test_appointment_rules(api):
    ok = {'patient_id': 101, 'doctor_id': 205, 'slot': '2030-01-01 10:00', 'complaint': 'x'}
    s, js = api.post('/api/appointments', ok)
    assert js['ok'] and js['data']['visit_id'] == 421
    s, js = api.post('/api/appointments', ok)
    assert js['error']['code'] == 'SLOT_TAKEN'
    s, js = api.post('/api/appointments', {**ok, 'slot': '2001-01-01 10:00'})
    assert js['error']['code'] == 'SLOT_IN_PAST'
    s, js = api.post('/api/appointments', {**ok, 'slot': 'garbage'})
    assert js['error']['code'] == 'VALIDATION_ERROR'
    s, js = api.post('/api/appointments', {**ok, 'patient_id': 'abc'})
    assert js['error']['code'] == 'VALIDATION_ERROR'
    s, js = api.post('/api/appointments', {**ok, 'patient_id': 99999, 'slot': '2030-02-01 10:00'})
    assert js['error']['code'] == 'PATIENT_NOT_FOUND'


def test_emergency_and_prescription_stock_trigger(api):
    s, js = api.post('/api/emergency', {'patient_id': 109, 'complaint': 'Chest pain', 'triage_level': 1})
    assert js['ok']
    vid = js['data']['visit_id']
    s, js = api.post('/api/emergency', {'patient_id': 109, 'complaint': 'x', 'triage_level': 7})
    assert js['error']['code'] == 'BAD_TRIAGE'
    api.post(f'/api/visits/{vid}/start-treatment')
    s, js = api.post('/api/prescriptions', {'visit_id': vid, 'medicine_id': 501, 'dosage': '1-0-0', 'duration_days': 3, 'quantity': 3})
    assert js['ok'] and 'trg_reduce_stock__insert' in [t['name'] for t in js['inspector']['triggers_fired']]
    stock = js['data']['stock_after']
    s, js = api.post('/api/prescriptions', {'visit_id': vid, 'medicine_id': 512, 'dosage': '1-0-0', 'duration_days': 3, 'quantity': 5})
    assert js['error']['code'] == 'INSUFFICIENT_STOCK'
    assert api.raw().execute('SELECT stock_quantity FROM medicine WHERE medicine_id=501').fetchone()[0] == stock


def test_bed_status_safety(api):
    s, js = api.post('/api/beds/305/status', {'status': 'Free'})      # bed 305 holds admitted visit 413
    assert js['error']['code'] == 'BED_IN_USE'
    s, js = api.post('/api/beds/301/status', {'status': 'Occupied'})
    assert not js['ok']
    s, js = api.post('/api/beds/301/status', {'status': 'bogus'})
    assert js['error']['code'] == 'VALIDATION_ERROR'
    s, js = api.post('/api/beds/9999/status', {'status': 'Free'})
    assert js['error']['code'] == 'BED_NOT_FOUND'


def test_delete_patient_fk_blocked(api):
    s, js = api.call('DELETE', '/api/patients/101')
    assert not js['ok'] and js['error']['code'] in ('FK_VISIT_PATIENT', 'FK_VIOLATION')
    assert api.raw().execute('SELECT COUNT(*) FROM patient WHERE patient_id=101').fetchone()[0] == 1


def test_restock_validation(api):
    for q in (-5, 0, 'x', None, 1.5):
        s, js = api.post('/api/medicines/501/restock', {'quantity': q})
        assert js['error']['code'] == 'VALIDATION_ERROR', q
    s, js = api.post('/api/medicines/9999/restock', {'quantity': 5})
    assert js['error']['code'] == 'MEDICINE_NOT_FOUND'





def test_audit_tamper(api):
    for mode in ('update', 'delete'):
        s, js = api.post('/api/audit/tamper-test', {'mode': mode})
        assert js['ok'] and js['data']['blocked'] is True
    assert api.post('/api/audit/tamper-test', {'mode': 'x'})[1]['ok'] is False


def test_reset_needs_confirm_and_restores_data(api):
    api.post('/api/patients', PATIENT)
    s, js = api.post('/api/reset', {})
    assert not js['ok'] and js['error']['code'] == 'CONFIRM_REQUIRED'
    assert api.raw().execute('SELECT COUNT(*) FROM patient').fetchone()[0] == 13
    s, js = api.post('/api/reset', {'confirm': True})
    assert js['ok'] and js['data']['counts']['patient'] == 12
    assert Path(str(api.path) + '.pre-reset.bak').exists()
    assert api.get('/api/meta')[1]['data']['counts']['patient'] == 12


def test_full_guided_demo(api):
    s, js = api.get('/api/demo/steps')
    ids = [st['id'] for t in js['data'] for st in t['steps']]
    s, r = api.post(f'/api/demo/{ids[3]}/run')                       # skipping prerequisites
    s, r = api.post('/api/demo/T3.2/run')
    assert r['error']['code'] == 'STEP_ORDER'
    for sid in ids:
        s, r = api.post(f'/api/demo/{sid}/run')
        assert r['ok'], (sid, r)
        failed = [c for c in r['data']['checks'] if not c['passed']]
        assert not failed, (sid, failed)
    assert set(api.get('/api/demo/state')[1]['data']['completed']) == set(ids)
    assert api.post('/api/demo/T9.9/run')[1]['error']['code'] == 'STEP_NOT_FOUND'
    api.post('/api/reset', {'confirm': True})
    assert api.get('/api/demo/state')[1]['data']['completed'] == []


def test_no_exception_text_leaks(api, monkeypatch):
    import services
    def boom(*a, **k): raise RuntimeError('secret internal path /etc/passwd')
    monkeypatch.setattr(services, 'get_patients', boom)
    app_module  # noqa
    s, js = api.get('/api/patients')
    assert s == 500 and js['ok'] is False and 'secret' not in json.dumps(js)


PAGES = ['/', '/patients', '/appointments', '/emergency', '/beds', '/pharmacy', '/billing', '/reports', '/audit',
         '/admin']


@pytest.mark.parametrize('url', PAGES)
def test_pages_render_without_cdn(api, url):
    import app as a
    c = a.create_app({'TESTING': True, 'DB_PATH': str(api.path)}).test_client()
    r = c.get(url)
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'http://' not in html.replace('http://www.w3.org', '') and 'cdn.' not in html
    assert 'Content-Security-Policy' in r.headers


# --------------------------------------------------------------------------- role permissions

# (role, method, url, body, allowed). "Allowed" means not blocked by role; the call may still
# fail a business rule (e.g. bill not found), which is fine - we only assert on FORBIDDEN here.
PERMISSION_CASES = [
    ('Receptionist', 'POST', '/api/bills/706/pay', {'payment_mode': 'Cash'}, False),
    ('Triage Nurse', 'POST', '/api/bills/706/pay', {'payment_mode': 'Cash'}, False),
    ('Doctor', 'POST', '/api/bills/706/pay', {'payment_mode': 'Cash'}, False),
    ('Billing', 'POST', '/api/bills/706/pay', {'payment_mode': 'Cash'}, True),
    ('Admin', 'POST', '/api/bills/706/pay', {'payment_mode': 'Cash'}, True),
    ('Receptionist', 'POST', '/api/visits/407/bill', {}, False),
    ('Billing', 'POST', '/api/visits/407/bill', {}, True),
    ('Receptionist', 'POST', '/api/medicines/501/restock', {'quantity': 5}, False),
    ('Billing', 'POST', '/api/medicines/501/restock', {'quantity': 5}, False),
    ('Doctor', 'POST', '/api/medicines/501/restock', {'quantity': 5}, True),
    ('Receptionist', 'POST', '/api/prescriptions', {'visit_id': 407, 'medicine_id': 501, 'quantity': 1}, False),
    ('Doctor', 'POST', '/api/prescriptions', {'visit_id': 407, 'medicine_id': 501, 'quantity': 1}, True),
    ('Receptionist', 'POST', '/api/visits/407/discharge', {}, False),
    ('Doctor', 'POST', '/api/visits/407/discharge', {}, True),
    ('Billing', 'POST', '/api/patients', PATIENT, False),
    ('Doctor', 'POST', '/api/patients', PATIENT, False),
    ('Receptionist', 'POST', '/api/patients', PATIENT, True),
    ('Triage Nurse', 'POST', '/api/emergency', {}, True),
    ('Billing', 'POST', '/api/emergency', {}, False),
    ('Receptionist', 'DELETE', '/api/patients/101', None, False),
    ('Receptionist', 'POST', '/api/reset', {'confirm': True}, False),
    ('Receptionist', 'POST', '/api/audit/tamper-test', {}, False),
    ('Receptionist', 'POST', '/api/doctors', {}, False),
    ('Doctor', 'POST', '/api/demo/T1.1/run', {}, False),
]


@pytest.mark.parametrize('case', PERMISSION_CASES)
def test_role_permissions(api, case):
    role, method, url, body, allowed = case
    s, js = api.call(method, url, body, role=role)
    forbidden = s == 403 and js['error']['code'] == 'FORBIDDEN'
    assert forbidden is (not allowed), (role, method, url, s, js)
    if forbidden:
        assert js['ok'] is False and js['error']['kind'] == 'authorization'


def test_forbidden_write_changes_nothing(api):
    before = api.raw().execute('SELECT payment_status FROM bill WHERE bill_id = 706').fetchone()
    s, js = api.post('/api/bills/706/pay', {'payment_mode': 'Cash'}, role='Receptionist')
    assert s == 403
    assert api.raw().execute('SELECT payment_status FROM bill WHERE bill_id = 706').fetchone() == before


def test_reads_are_open_to_every_role(api):
    for role in ('Receptionist', 'Triage Nurse', 'Doctor', 'Billing'):
        for url in ('/api/patients', '/api/bills', '/api/medicines', '/api/beds'):
            s, js = api.get(url, role=role)
            assert s == 200 and js['ok'], (role, url)


def test_logged_in_user_cannot_escalate_with_role_header(api):
    """A real Receptionist session must stay a Receptionist even if it sends X-Role: Admin."""
    import app as a
    import auth
    from db.connection import get_connection
    application = a.create_app({'TESTING': True, 'DB_PATH': str(api.path), 'AUTH_REQUIRED': True})
    conn = get_connection(str(api.path))
    auth.init_auth_tables(conn)
    auth.create_user(conn, 'frontdesk1', 'Str0ng!Passw0rd#9', role='Receptionist', full_name='Front Desk')
    conn.close()
    c = application.test_client()
    h = {'X-Requested-With': 'HospitalApp'}
    r = c.post('/api/auth/login', json={'username': 'frontdesk1', 'password': 'Str0ng!Passw0rd#9'}, headers=h)
    assert r.get_json()['ok'], r.get_json()
    r = c.post('/api/bills/706/pay', json={'payment_mode': 'Cash'}, headers={**h, 'X-Role': 'Admin'})
    assert r.status_code == 403 and r.get_json()['error']['code'] == 'FORBIDDEN'
    assert c.get('/api/meta', headers={**h, 'X-Role': 'Admin'}).get_json()['data']['role'] == 'Receptionist'
