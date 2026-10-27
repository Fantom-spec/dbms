"""
Frontend views for Smart Hospital Management System.
All dynamic data comes from /api/* endpoints via fetch().
"""
from flask import Blueprint, current_app, g, redirect, render_template, request, url_for

import config
from auth import get_user_from_session, init_auth_tables, invalidate_session
from db.connection import get_connection

views_bp = Blueprint('views', __name__)


@views_bp.before_request
def check_authentication():
    """Server-side route protection for web views."""
    # Allow public access to login page
    if request.endpoint in ('views.login', 'static'):
        return None

    # Check if authentication enforcement is enabled
    auth_enforced = current_app.config.get('AUTH_REQUIRED', True)
    if not auth_enforced:
        return None

    token = request.cookies.get(config.SESSION_COOKIE_NAME)
    if not token:
        return redirect(url_for('views.login', next=request.path))

    # Validate session token in database
    conn = get_connection(current_app.config['DB_PATH'])
    try:
        init_auth_tables(conn)
        user = get_user_from_session(conn, token)
        if not user:
            resp = redirect(url_for('views.login', next=request.path))
            resp.delete_cookie(config.SESSION_COOKIE_NAME, path='/')
            return resp
        g.user = user
    finally:
        conn.close()


@views_bp.app_context_processor
def inject_globals():
    """Inject current authenticated user into all templates."""
    return {
        'current_user': getattr(g, 'user', None),
    }



@views_bp.route('/login')
def login():
    token = request.cookies.get(config.SESSION_COOKIE_NAME)
    if token:
        conn = get_connection(current_app.config['DB_PATH'])
        try:
            init_auth_tables(conn)
            user = get_user_from_session(conn, token)
            if user:
                next_url = request.args.get('next') or url_for('views.dashboard')
                return redirect(next_url)
        finally:
            conn.close()
    return render_template('login.html', next=request.args.get('next', ''))


@views_bp.route('/logout')
def logout():
    token = request.cookies.get(config.SESSION_COOKIE_NAME)
    if token:
        conn = get_connection(current_app.config['DB_PATH'])
        try:
            init_auth_tables(conn)
            invalidate_session(conn, token)
        finally:
            conn.close()
    resp = redirect(url_for('views.login'))
    resp.delete_cookie(config.SESSION_COOKIE_NAME, path='/')
    return resp


@views_bp.route('/')
def dashboard():
    return render_template('dashboard.html')


@views_bp.route('/patients')
def patients():
    return render_template('patients.html')


@views_bp.route('/appointments')
def appointments():
    return render_template('appointments.html')


@views_bp.route('/emergency')
def emergency():
    return render_template('emergency.html')


@views_bp.route('/beds')
def beds():
    return render_template('beds.html')


@views_bp.route('/pharmacy')
def pharmacy():
    return render_template('pharmacy.html')


@views_bp.route('/billing')
def billing():
    return render_template('billing.html')


@views_bp.route('/reports')
def reports():
    return render_template('reports.html')


@views_bp.route('/audit')
def audit():
    return render_template('audit.html')


@views_bp.route('/admin')
def admin():
    return render_template('admin.html')