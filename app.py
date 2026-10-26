from flask import Flask, g
import sqlite3
import os
import sys

from config import DB_PATH, SECRET_KEY, FLASK_API_MODE


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = SECRET_KEY
    app.config['DB_PATH'] = DB_PATH
    app.config['FLASK_API_MODE'] = FLASK_API_MODE

    @app.before_request
    def before_request():
        # Skip DB setup in stub mode
        if app.config.get('FLASK_API_MODE') == 'stub':
            return

        g.db = sqlite3.connect(DB_PATH, isolation_level=None)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON')
        g.db.execute('PRAGMA busy_timeout = 5000')

        # Register UDFs
        try:
            from db.connection import register_udfs
            register_udfs(g.db)
        except ImportError:
            pass  # Will be implemented in Phase 2

        # Set up trace callback for inspector
        try:
            from inspector import install_trace
            install_trace(g.db)
        except ImportError:
            pass  # Will be implemented in Phase 4

        # Ensure app_session exists and set default role
        g.db.execute('''
            INSERT OR IGNORE INTO app_session (id, username) VALUES (1, 'ADMIN')
        ''')
        g.db.execute("UPDATE app_session SET username = 'ADMIN' WHERE id = 1")

    @app.teardown_request
    def teardown_request(exception):
        db = g.pop('db', None)
        if db is not None:
            db.close()

    # Register blueprints based on mode
    if app.config.get('FLASK_API_MODE') == 'stub':
        from api_stub import api_stub_bp
        app.register_blueprint(api_stub_bp, url_prefix='/api')
    else:
        from api import api_bp
        app.register_blueprint(api_bp, url_prefix='/api')

    # Import views (Person 2's routes)
    try:
        from views import views_bp
        app.register_blueprint(views_bp)
    except ImportError:
        # Temporary fallback if views.py doesn't exist yet
        @app.route('/')
        def index():
            return {'message': 'Smart Hospital Management System - Backend running', 'mode': FLASK_API_MODE}

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)