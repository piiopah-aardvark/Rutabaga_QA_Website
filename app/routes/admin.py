"""
Admin routes for QA website.
"""
from flask import Blueprint, render_template, abort
from flask_login import login_required, current_user
from functools import wraps

admin_bp = Blueprint('admin', __name__)


def admin_required(f):
    """Decorator to require admin role."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    """Admin dashboard."""
    return render_template('admin/dashboard.html')
