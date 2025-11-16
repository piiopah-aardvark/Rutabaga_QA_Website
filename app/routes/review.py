"""
Review routes for QA website.
"""
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user

review_bp = Blueprint('review', __name__)


@review_bp.route('/review')
@login_required
def review_page():
    """Main review page."""
    return render_template('review.html')


@review_bp.route('/my-reviews')
@login_required
def my_reviews():
    """My reviews page."""
    return render_template('my_reviews.html')
