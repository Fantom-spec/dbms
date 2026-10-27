"""
Smart Hospital Management System - Flask application factory.

    python app.py                 # http://127.0.0.1:5000  (creates hospital.db if missing)
    flask --app app run

Everything is configurable through environment variables (see config.py); tests call
``create_app({...})`` with a temporary database so they can never touch hospital.db.
"""
import os
import sys
from pathlib import Path

from flask import Flask, jsonify, request

import config as default_config

_CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; "
        "base-uri 'self'; form-action 'self'; frame-ancestors 'none'")


def _envelope_error(message, kind, code, status, detail=None):
    resp = jsonify({'ok': False, 'message': message, 'data': None,
                    'error': {'kind': kind, 'code': code, 'constraint': None, 'detail': detail or message},
                    'inspector': None})
    resp.status_code = status
    return resp


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=default_config.SECRET_KEY,
        DB_PATH=default_config.DB_PATH,
        FLASK_API_MODE=default_config.FLASK_API_MODE,
        TRUSTED_HOSTS=default_config.TRUSTED_HOSTS,
        MAX_CONTENT_LENGTH=256 * 1024,
        JSON_SORT_KEYS=False,
    )
    if test_config:
        app.config.update(test_config)
    if app.config['FLASK_API_MODE'] not in ('real', 'stub'):
        raise RuntimeError("FLASK_API_MODE must be 'real' or 'stub'")
    app.json.sort_keys = False

    # ---- database: create it if it does not exist (never overwrite an existing one) ----
    if app.config['FLASK_API_MODE'] == 'real':
        db_file = Path(app.config['DB_PATH'])
        if not db_file.exists():
            from db.init_db import init_database
            init_database(db_file)

    # ---- API blueprint ----
    if app.config['FLASK_API_MODE'] == 'stub':
        from api_stub import api_stub_bp
        app.register_blueprint(api_stub_bp, url_prefix='/api')
    else:
        from api import api_bp
        app.register_blueprint(api_bp, url_prefix='/api')

    from views import views_bp
    app.register_blueprint(views_bp)

    # ---- security headers ----
    @app.after_request
    def security_headers(resp):
        resp.headers.setdefault('Content-Security-Policy', _CSP)
        resp.headers.setdefault('X-Content-Type-Options', 'nosniff')
        resp.headers.setdefault('X-Frame-Options', 'DENY')
        resp.headers.setdefault('Referrer-Policy', 'no-referrer')
        if request.path.startswith('/api/'):
            resp.headers['Cache-Control'] = 'no-store'
        return resp

    # ---- errors: /api/* always answers with the JSON envelope ----
    @app.errorhandler(404)
    def not_found(e):
        if request.path.startswith('/api/'):
            return _envelope_error('Endpoint not found', 'not_found', 'ENDPOINT_NOT_FOUND', 404)
        return ('<h1>404 - Page not found</h1><p><a href="/">Back to dashboard</a></p>', 404)

    @app.errorhandler(405)
    def method_not_allowed(e):
        if request.path.startswith('/api/'):
            return _envelope_error('Method not allowed', 'validation', 'METHOD_NOT_ALLOWED', 405)
        return ('Method not allowed', 405)

    @app.errorhandler(413)
    def too_large(e):
        return _envelope_error('Request body too large', 'validation', 'PAYLOAD_TOO_LARGE', 413)

    @app.errorhandler(400)
    def bad_request(e):
        if request.path.startswith('/api/'):
            return _envelope_error('Malformed request', 'validation', 'BAD_REQUEST', 400, getattr(e, 'description', None))
        return ('Bad request', 400)

    @app.errorhandler(Exception)
    def unexpected(e):
        from werkzeug.exceptions import HTTPException
        if isinstance(e, HTTPException):
            return e
        app.logger.exception('Unhandled error')
        if request.path.startswith('/api/'):
            # No exception text is leaked to the client; it is in the server log.
            return _envelope_error('Internal server error', 'internal', 'INTERNAL_ERROR', 500,
                                   'See the server log for details')
        return ('Internal server error', 500)

    return app


def main():
    host = os.environ.get('HOSPITAL_HOST', '127.0.0.1')
    port = int(os.environ.get('PORT', '5000'))
    app = create_app()
    print(f'Smart Hospital Management System -> http://{host}:{port}  '
          f'(mode={app.config["FLASK_API_MODE"]}, db={app.config["DB_PATH"]})', file=sys.stderr)
    app.run(host=host, port=port, debug=default_config.DEBUG)


if __name__ == '__main__':
    main()
