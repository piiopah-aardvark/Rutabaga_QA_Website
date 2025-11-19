"""
Admin routes for QA website.
"""
from flask import Blueprint, render_template, abort, jsonify, request
from flask_login import login_required, current_user
from functools import wraps
from sqlalchemy import func, desc
from app import db
from app.models import (
    ResponseQueue, Review, Reviewer, ReviewSession,
    ProductionUpdate, RereviewRequest
)

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


@admin_bp.route('/api/stats')
@login_required
@admin_required
def get_stats():
    """Get global statistics for admin dashboard."""

    # Total responses
    total_responses = db.session.query(func.count(ResponseQueue.id)).scalar() or 0

    # Response status counts
    pending_count = db.session.query(func.count(ResponseQueue.id)).filter(
        ResponseQueue.status == 'pending'
    ).scalar() or 0

    submitted_count = db.session.query(func.count(ResponseQueue.id)).filter(
        ResponseQueue.status == 'submitted'
    ).scalar() or 0

    flagged_count = db.session.query(func.count(ResponseQueue.id)).filter(
        ResponseQueue.status == 'flagged'
    ).scalar() or 0

    # Average scores by intent
    avg_scores_by_intent = db.session.query(
        ResponseQueue.intent,
        func.avg(
            func.cast(
                func.jsonb_extract_path_text(
                    Review.segment_scores,
                    'S1',
                    'score'
                ),
                db.Float
            )
        ).label('avg_score')
    ).join(
        Review, Review.response_queue_id == ResponseQueue.id
    ).filter(
        Review.status == 'submitted'
    ).group_by(
        ResponseQueue.intent
    ).all()

    intent_scores = {
        intent: round(score, 1) if score else 0.0
        for intent, score in avg_scores_by_intent
    }

    # Production updates count
    production_updates_count = db.session.query(func.count(ProductionUpdate.id)).scalar() or 0

    return jsonify({
        'success': True,
        'stats': {
            'total_responses': total_responses,
            'pending': pending_count,
            'submitted': submitted_count,
            'flagged': flagged_count,
            'avg_scores_by_intent': intent_scores,
            'production_updates': production_updates_count
        }
    }), 200


@admin_bp.route('/api/flagged')
@login_required
@admin_required
def get_flagged_items():
    """Get all flagged items."""

    flagged_reviews = db.session.query(Review).filter(
        Review.status == 'flagged'
    ).order_by(desc(Review.created_at)).all()

    flagged_data = []
    for review in flagged_reviews:
        response_queue = db.session.get(ResponseQueue, review.response_queue_id)
        reviewer = db.session.get(Reviewer, review.reviewer_id)

        flagged_data.append({
            'review_id': review.id,
            'response_queue_id': review.response_queue_id,
            'intent': response_queue.intent if response_queue else 'N/A',
            'query_text': response_queue.query_text if response_queue else 'N/A',
            'reviewer_name': reviewer.full_name if reviewer else 'Unknown',
            'flag_reason': review.flag_reason,
            'created_at': review.created_at.isoformat()
        })

    return jsonify({
        'success': True,
        'flagged_items': flagged_data
    }), 200


@admin_bp.route('/api/reviewers')
@login_required
@admin_required
def get_reviewers():
    """Get reviewer statistics."""

    reviewers = db.session.query(Reviewer).all()

    reviewer_stats = []
    for reviewer in reviewers:
        # Calculate average score for this reviewer
        avg_score_result = db.session.query(
            func.avg(
                func.cast(
                    func.jsonb_extract_path_text(
                        Review.segment_scores,
                        'S1',
                        'score'
                    ),
                    db.Float
                )
            )
        ).filter(
            Review.reviewer_id == reviewer.id,
            Review.status == 'submitted'
        ).scalar()

        avg_score = round(avg_score_result, 1) if avg_score_result else 0.0

        # Get last active session
        last_session = db.session.query(ReviewSession).filter(
            ReviewSession.reviewer_id == reviewer.id
        ).order_by(desc(ReviewSession.session_start)).first()

        last_active = None
        if last_session:
            last_active = last_session.session_start.isoformat()

        reviewer_stats.append({
            'id': reviewer.id,
            'name': reviewer.full_name,
            'email': reviewer.email,
            'specialization': reviewer.specialization,
            'is_active': reviewer.is_active,
            'role': reviewer.role,
            'total_submitted': reviewer.total_reviews_submitted,
            'total_flagged': reviewer.total_reviews_flagged,
            'total_drafts': reviewer.total_drafts_saved,
            'avg_score': avg_score,
            'last_active': last_active
        })

    return jsonify({
        'success': True,
        'reviewers': reviewer_stats
    }), 200


@admin_bp.route('/api/reviewer/<int:reviewer_id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_reviewer(reviewer_id):
    """Activate or deactivate a reviewer."""

    reviewer = db.session.get(Reviewer, reviewer_id)

    if not reviewer:
        return jsonify({'success': False, 'error': 'Reviewer not found'}), 404

    try:
        reviewer.is_active = not reviewer.is_active
        db.session.commit()

        return jsonify({
            'success': True,
            'is_active': reviewer.is_active
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
