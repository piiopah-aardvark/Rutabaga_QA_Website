"""
API routes for AJAX/HTMX requests.
"""
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from app import db
from app.models import ResponseQueue, Review, ReviewSession

api_bp = Blueprint('api', __name__)


@api_bp.route('/next-response')
@login_required
def get_next_response():
    """Get next unreviewed response for specified intent."""
    intent = request.args.get('intent', 'interaction')

    # TODO: Implement priority logic (re-reviews first, then unreviewed)
    response = ResponseQueue.query.filter_by(
        intent=intent,
        status='pending'
    ).first()

    if not response:
        return jsonify({'found': False}), 200

    return jsonify({
        'found': True,
        'response': {
            'id': response.id,
            'query_text': response.query_text,
            'segments': response.segments,
            'slots': response.slots
        }
    }), 200


@api_bp.route('/session/stats')
@login_required
def session_stats():
    """Get current session and all-time stats."""
    from flask import session

    session_id = session.get('review_session_id')
    session_count = 0

    if session_id:
        review_session = db.session.get(ReviewSession, session_id)
        if review_session:
            session_count = review_session.reviews_completed

    return jsonify({
        'session_reviews': session_count,
        'total_reviews': current_user.total_reviews_submitted
    }), 200
