"""
Test that all API endpoints have corresponding fixtures in stub mode.
"""
import os
import pytest

# Set stub mode BEFORE importing app
os.environ['FLASK_API_MODE'] = 'stub'

from app import create_app


@pytest.fixture
def client():
    app = create_app()
    with app.test_client() as client:
        yield client


# All endpoints from ARCHITECTURE.md section 8.2
ENDPOINTS = [
    # Session and Meta
    ('GET', '/api/meta'),
    ('POST', '/api/role'),
    ('POST', '/api/reset'),
    ('GET', '/api/lookups'),
    ('GET', '/api/dashboard'),
    
    # Patients
    ('GET', '/api/patients'),
    ('POST', '/api/patients'),
    ('PUT', '/api/patients/101'),
    ('DELETE', '/api/patients/101'),
    ('GET', '/api/patients/107/history'),
    
    # Doctors
    ('GET', '/api/doctors'),
    ('POST', '/api/doctors'),
    ('PUT', '/api/doctors/201'),
    
    # Medicines
    ('GET', '/api/medicines'),
    ('POST', '/api/medicines'),
    ('POST', '/api/medicines/512/restock'),
    ('GET', '/api/medicines/low-stock'),
    
    # Beds
    ('GET', '/api/beds'),
    ('POST', '/api/beds'),
    ('POST', '/api/beds/304/status'),
    
    # Visits
    ('GET', '/api/visits'),
    ('GET', '/api/visits/407/summary'),
    ('POST', '/api/appointments'),
    ('POST', '/api/visits/421/cancel'),
    ('POST', '/api/visits/422/start-treatment'),
    ('POST', '/api/emergency'),
    ('GET', '/api/emergency/queue'),
    ('POST', '/api/visits/422/allot-bed'),
    ('POST', '/api/visits/422/discharge'),
    
    # Pharmacy
    ('GET', '/api/visits/407/prescriptions'),
    ('POST', '/api/prescriptions'),
    ('DELETE', '/api/prescriptions/623'),
    
    # Billing
    ('POST', '/api/visits/422/bill'),
    ('GET', '/api/bills'),
    ('GET', '/api/bills/pending'),
    ('POST', '/api/bills/712/pay'),
    
    # Reports
    ('GET', '/api/reports'),
    ('GET', '/api/reports/q01'),
    ('GET', '/api/reports/q02'),
    ('GET', '/api/reports/q03'),
    
    # Audit
    ('GET', '/api/audit'),
    ('POST', '/api/audit/tamper-test'),
    
    # Schema
    ('GET', '/api/schema/overview'),
    ('GET', '/api/schema/tables'),
    ('GET', '/api/schema/tables/patient'),
    ('GET', '/api/schema/relationships'),
    ('GET', '/api/schema/constraints'),
    ('GET', '/api/schema/indexes'),
    ('GET', '/api/schema/triggers'),
    ('GET', '/api/schema/functions'),
    ('GET', '/api/schema/ddl'),
    ('GET', '/api/schema/er'),
    ('GET', '/api/schema/violations'),
    ('POST', '/api/schema/violations/v01/run'),
    ('POST', '/api/schema/triggers/trg_reduce_stock/demo'),
    ('POST', '/api/sql'),
    
    # Demo
    ('GET', '/api/demo/steps'),
    ('GET', '/api/demo/state'),
    ('POST', '/api/demo/T1.1/run'),
]


@pytest.mark.parametrize("method,path", ENDPOINTS)
def test_endpoint_has_fixture(client, method, path):
    """Test that each endpoint returns a valid envelope in stub mode."""
    if method == 'GET':
        resp = client.get(path)
    elif method == 'POST':
        resp = client.post(path, json={})
    elif method == 'PUT':
        resp = client.put(path, json={})
    elif method == 'DELETE':
        resp = client.delete(path)
    else:
        pytest.fail(f"Unknown method: {method}")
    
    # Should return 200 (even for ok:false)
    assert resp.status_code == 200, f"{method} {path}: status {resp.status_code}"
    
    # Should have envelope structure
    data = resp.get_json()
    assert 'ok' in data, f"{method} {path}: missing 'ok' field"
    assert 'message' in data, f"{method} {path}: missing 'message' field"
    assert 'data' in data, f"{method} {path}: missing 'data' field"
    assert 'error' in data, f"{method} {path}: missing 'error' field"
    assert 'inspector' in data, f"{method} {path}: missing 'inspector' field"
    
    # For write endpoints, should have inspector (can be null for read-only)
    if method in ('POST', 'PUT', 'DELETE'):
        # Inspector can be null for some, but should be present
        pass


def test_error_fixtures_work(client):
    """Test that _fail=1 triggers error fixtures for write endpoints."""
    # Test patient duplicate phone error
    resp = client.post('/api/patients?_fail=1', json={'patient_name': 'Test', 'phone': '9876500101'})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['ok'] is False
    assert data['error']['code'] == 'UQ_PATIENT_PHONE'
    assert data['inspector'] is not None
    
    # Test appointment slot taken error
    resp = client.post('/api/appointments?_fail=1', json={'patient_id': 101, 'doctor_id': 202, 'slot': '2026-10-27 10:00:00', 'complaint': 'Fever'})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['ok'] is False
    assert data['error']['code'] == 'SLOT_TAKEN'
    assert data['inspector'] is not None
    
    # Test emergency bad triage error
    resp = client.post('/api/emergency?_fail=1', json={'patient_id': 109, 'complaint': 'Chest pain', 'triage_level': 7})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['ok'] is False
    assert data['error']['code'] == 'BAD_TRIAGE'
    assert data['inspector'] is not None


def test_real_mode_falls_back():
    """Test that real mode returns not-implemented (since DB not initialized).
    This test is skipped in Phase 1 because the real API requires database initialization
    which happens in Phase 2. The stub mode is the focus of Phase 1.
    """
    pytest.skip("Real mode testing requires database initialization (Phase 2)")