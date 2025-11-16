"""
API routes for AJAX/HTMX requests.
"""
from flask import Blueprint, jsonify, request, render_template, session as flask_session
from flask_login import login_required, current_user
from app import db
from app.models import ResponseQueue, Review, ReviewSession
from app.services.review_service import ReviewService

api_bp = Blueprint('api', __name__)


@api_bp.route('/next-response')
@login_required
def get_next_response():
    """Get next unreviewed response for specified intent."""
    intent = request.args.get('intent', 'interaction')

    # Use ReviewService to get next response
    response = ReviewService.get_next_response(intent, current_user.id)

    if not response:
        return render_template('partials/empty_state.html', intent=intent), 200

    # Render review form partial
    return render_template(
        'partials/review_form.html',
        response=response,
        intent=intent
    ), 200


@api_bp.route('/session/stats')
@login_required
def session_stats():
    """Get current session and all-time stats."""
    session_id = flask_session.get('review_session_id')
    session_count = 0

    if session_id:
        review_session = db.session.get(ReviewSession, session_id)
        if review_session:
            session_count = review_session.reviews_completed

    return jsonify({
        'session_reviews': session_count,
        'total_reviews': current_user.total_reviews_submitted
    }), 200


@api_bp.route('/review/skip', methods=['POST'])
@login_required
def skip_review():
    """Skip current response."""
    data = request.json
    response_id = data.get('response_id')
    session_id = flask_session.get('review_session_id')

    if not response_id or not session_id:
        return jsonify({'success': False, 'error': 'Missing data'}), 400

    success = ReviewService.skip_response(response_id, current_user.id, session_id)

    return jsonify({'success': success}), 200 if success else 500


@api_bp.route('/review/flag', methods=['POST'])
@login_required
def flag_review():
    """Flag response for admin review."""
    data = request.json
    response_id = data.get('response_id')
    flag_reason = data.get('flag_reason')
    segment_scores = data.get('segment_scores', {})
    overall_notes = data.get('overall_notes')
    session_id = flask_session.get('review_session_id')

    if not response_id or not flag_reason or not session_id:
        return jsonify({'success': False, 'error': 'Missing data'}), 400

    success = ReviewService.flag_response(
        response_id, current_user.id, session_id,
        flag_reason, segment_scores, overall_notes
    )

    return jsonify({'success': success}), 200 if success else 500


@api_bp.route('/review/draft', methods=['POST'])
@login_required
def save_draft():
    """Save review as draft."""
    data = request.json
    response_id = data.get('response_id')
    segment_scores = data.get('segment_scores', {})
    overall_notes = data.get('overall_notes')
    session_id = flask_session.get('review_session_id')

    if not response_id or not session_id:
        return jsonify({'success': False, 'error': 'Missing data'}), 400

    success = ReviewService.save_draft(
        response_id, current_user.id, session_id,
        segment_scores, overall_notes
    )

    return jsonify({'success': success}), 200 if success else 500


@api_bp.route('/review/submit', methods=['POST'])
@login_required
def submit_review():
    """Submit review and update production database."""
    data = request.json
    response_id = data.get('response_id')
    segment_scores = data.get('segment_scores', {})
    overall_notes = data.get('overall_notes')
    session_id = flask_session.get('review_session_id')

    if not response_id or not session_id:
        return jsonify({'success': False, 'error': 'Missing data'}), 400

    success = ReviewService.submit_review(
        response_id, current_user.id, session_id,
        segment_scores, overall_notes
    )

    return jsonify({
        'success': success,
        'message': 'Review submitted successfully!' if success else 'Error submitting review'
    }), 200 if success else 500
