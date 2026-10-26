"""
Temporary views.py — placeholder for Person 2's routes.
This allows the app to boot in Phase 1 before Person 2 implements the real views.
"""
from flask import Blueprint, render_template

views_bp = Blueprint('views', __name__)


@views_bp.route('/')
def index():
    return render_template('base.html')  # Will fail until Person 2 creates templates


@views_bp.route('/patients')
def patients():
    return "Patients page - placeholder"


@views_bp.route('/appointments')
def appointments():
    return "Appointments page - placeholder"


@views_bp.route('/emergency')
def emergency():
    return "Emergency page - placeholder"


@views_bp.route('/beds')
def beds():
    return "Beds page - placeholder"


@views_bp.route('/pharmacy')
def pharmacy():
    return "Pharmacy page - placeholder"


@views_bp.route('/billing')
def billing():
    return "Billing page - placeholder"


@views_bp.route('/reports')
def reports():
    return "Reports page - placeholder"


@views_bp.route('/audit')
def audit():
    return "Audit page - placeholder"


@views_bp.route('/demo')
def demo():
    return "Demo page - placeholder"


@views_bp.route('/schema')
def schema():
    return "Schema page - placeholder"


@views_bp.route('/admin')
def admin():
    return "Admin page - placeholder"