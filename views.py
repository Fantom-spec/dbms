"""
Frontend views for Smart Hospital Management System.
All dynamic data comes from /api/* endpoints via fetch().
"""
from flask import Blueprint, render_template

views_bp = Blueprint('views', __name__)


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


@views_bp.route('/demo')
def demo():
    return render_template('demo.html')


@views_bp.route('/schema')
def schema():
    return render_template('schema.html')


@views_bp.route('/admin')
def admin():
    return render_template('admin.html')