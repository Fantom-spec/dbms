"""
Stub API blueprint — serves fixture JSON files for every endpoint.
Enabled by FLASK_API_MODE=stub (set in config.py).
"""
import os
import json
from pathlib import Path
from flask import Blueprint, request, jsonify, current_app

api_stub_bp = Blueprint('api_stub', __name__)

FIXTURE_DIR = Path(__file__).parent / 'fixtures'


def _fixture_path(method: str, path: str) -> Path:
    """Convert HTTP method + path to fixture filename.
    Examples:
      GET /api/meta -> GET_api_meta.json
      POST /api/appointments -> POST_api_appointments.json
      GET /api/patients/107/history -> GET_api_patients_107_history.json
    """
    # Normalize path: replace /<id> with _<id>, keep /api/ prefix
    norm = path
    # Replace path parameters like /123 with _123
    import re
    norm = re.sub(r'/(\d+)', r'_\1', norm)
    norm = norm.replace('/', '_')
    # Remove leading underscore if path started with /
    if norm.startswith('_'):
        norm = norm[1:]
    filename = f"{method}_{norm}.json"
    return FIXTURE_DIR / filename


def _load_fixture(method: str, path: str) -> dict:
    """Load fixture JSON, with fallbacks."""
    # Check for _fail=1 query parameter to trigger error fixtures
    if '?_fail=1' in path or '&_fail=1' in path:
        # Try error fixture first
        base_path = path.split('?')[0]
        norm = base_path
        import re
        norm = re.sub(r'/(\d+)', r'_\1', norm)
        norm = norm.replace('/', '_')
        if norm.startswith('_'):
            norm = norm[1:]
        err_filename = f"{method}_{norm}_error.json"
        err_fp = FIXTURE_DIR / err_filename
        if err_fp.exists():
            with open(err_fp) as f:
                return json.load(f)
    
    # Try exact match first
    fp = _fixture_path(method, path)
    if fp.exists():
        with open(fp) as f:
            return json.load(f)

    # Fallback: try without query string
    if '?' in path:
        path_no_qs = path.split('?')[0]
        fp = _fixture_path(method, path_no_qs)
        if fp.exists():
            with open(fp) as f:
                return json.load(f)

    # Fallback: try generic error fixture for write endpoints
    if method in ('POST', 'PUT', 'DELETE'):
        err_fp = FIXTURE_DIR / f"{method}_error.json"
        if err_fp.exists():
            with open(err_fp) as f:
                return json.load(f)

    # Ultimate fallback
    return {
        "ok": False,
        "message": f"No fixture for {method} {path}",
        "error": {"kind": "internal", "code": "FIXTURE_MISSING", "constraint": None, "detail": ""},
        "data": None,
        "inspector": None
    }


@api_stub_bp.before_app_request
def _check_stub_mode():
    """Only serve stubs when FLASK_API_MODE=stub."""
    if current_app.config.get('FLASK_API_MODE', 'real') != 'stub':
        from flask import abort
        abort(404)  # Let real API handle it


@api_stub_bp.route('/<path:subpath>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
@api_stub_bp.route('/', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
def stub_handler(subpath=''):
    """Catch-all handler for /api/* routes in stub mode."""
    method = request.method
    full_path = f"/api/{subpath}" if subpath else "/api/"
    if subpath == 'sql' or subpath.startswith('schema/') or subpath.startswith('demo/'):
        return jsonify({"ok": False, "message": "Endpoint not found", "data": None,
                        "error": {"kind": "not_found", "code": "ENDPOINT_NOT_FOUND", "constraint": None, "detail": "This feature was removed. See docs/DEMO.md for the written walkthrough."},
                        "inspector": None}), 404
    # Include query string for _fail=1 detection
    if request.query_string:
        full_path += '?' + request.query_string.decode('utf-8')

    fixture = _load_fixture(method, full_path)

    return jsonify(fixture)