"""
API routes for AJAX/HTMX requests.
"""
from flask import Blueprint, jsonify, request, render_template, session as flask_session
from flask_login import login_required, current_user
from app import db
from app.models import ResponseQueue, Review, ReviewSession
from app.services.review_service import ReviewService
from app.services.production_update_service import ProductionUpdateService

api_bp = Blueprint('api', __name__)


@api_bp.route('/next-response')
@login_required
def get_next_response():
    """Get next unreviewed response for specified intent."""
    from app.models import RereviewRequest

    intent = request.args.get('intent', 'interaction')

    # Use ReviewService to get next response
    response = ReviewService.get_next_response(intent, current_user.id)

    if not response:
        return render_template('partials/empty_state.html', intent=intent), 200

    # Check if this is a re-review
    previous_review = None
    rereview_request = None

    # Check for previous reviews by this user
    prev_review = db.session.query(Review).filter(
        Review.response_queue_id == response.id,
        Review.reviewer_id == current_user.id,
        Review.status == 'submitted'
    ).order_by(Review.submitted_at.desc()).first()

    if prev_review:
        # Get re-review request
        rereview_request = db.session.query(RereviewRequest).filter(
            RereviewRequest.response_queue_id == response.id,
            RereviewRequest.requested_by == current_user.id,
            RereviewRequest.status == 'approved'
        ).order_by(RereviewRequest.created_at.desc()).first()

        # Calculate avg score from previous review
        scores = prev_review.segment_scores.values()
        avg_score = sum(s.get('score', 0) for s in scores) / len(scores) if scores else 0

        previous_review = {
            'submitted_at': prev_review.submitted_at.isoformat() if prev_review.submitted_at else None,
            'avg_score': round(avg_score, 1),
            'version': prev_review.version,
            'segment_scores': prev_review.segment_scores,
            'overall_notes': prev_review.overall_notes,
            'rereview_reason': rereview_request.reason if rereview_request else None
        }

    # Construct Phase 1 subject based on intent
    phase1_subject = _construct_phase1_subject(intent, response.slots)

    # Render review form partial
    return render_template(
        'partials/review_form.html',
        response=response,
        intent=intent,
        phase1_subject=phase1_subject,
        previous_review=previous_review
    ), 200


def _construct_phase1_subject(intent: str, slots: dict) -> str:
    """
    Construct Phase 1 subject (the part that segments complete).

    Args:
        intent: Intent name
        slots: Slot values

    Returns:
        Phase 1 subject string
    """
    if intent == 'interaction':
        drug_a = slots.get('drug_a', 'Drug A')
        drug_b = slots.get('drug_b', 'Drug B')
        return f"The interaction between {drug_a} and {drug_b}"

    elif intent in ['dosing', 'drug_dose_rsi']:
        drug = slots.get('drug', 'the drug')
        indication = slots.get('indication', '')
        if indication:
            return f"The dose of {drug} for {indication}"
        return f"The dose of {drug}"

    elif intent == 'contraindication':
        drug = slots.get('drug', 'the drug')
        return f"Contraindications for {drug}"

    elif intent == 'pregnancy':
        drug = slots.get('drug', 'the drug')
        return f"Use of {drug} in pregnancy"

    elif intent == 'lactation':
        drug = slots.get('drug', 'the drug')
        return f"Use of {drug} during lactation"

    elif intent == 'renal_dosing':
        drug = slots.get('drug', 'the drug')
        return f"Renal dosing for {drug}"

    elif intent == 'hepatic_dosing':
        drug = slots.get('drug', 'the drug')
        return f"Hepatic dosing for {drug}"

    elif intent == 'pediatric_dosing':
        drug = slots.get('drug', 'the drug')
        return f"Pediatric dosing for {drug}"

    elif intent == 'iv_compatibility':
        drug_a = slots.get('drug_a', 'Drug A')
        drug_b = slots.get('drug_b', 'Drug B')
        return f"IV compatibility of {drug_a} with {drug_b}"

    elif intent == 'bp_target':
        condition = slots.get('condition', 'this condition')
        return f"Blood pressure target for {condition}"

    elif intent == 'calculator':
        calc_type = slots.get('calculator_type', 'calculation')
        return f"The {calc_type} result"

    else:
        return "The response"


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


@api_bp.route('/source-data/<int:response_id>')
@login_required
def get_source_data(response_id):
    """Get source data from production database for the given response."""
    response = db.session.get(ResponseQueue, response_id)

    if not response:
        return jsonify({'success': False, 'error': 'Response not found'}), 404

    source_data = ProductionUpdateService.get_source_data(response)

    if source_data:
        return jsonify({
            'success': True,
            'intent': response.intent,
            'slots': response.slots,
            'source_data': source_data
        }), 200
    else:
        return jsonify({
            'success': False,
            'error': 'Source data not found or intent not supported'
        }), 404


@api_bp.route('/my-reviews')
@login_required
def get_my_reviews():
    """Get reviews for the current user, optionally filtered by status and intent."""
    status_filter = request.args.get('status')  # 'submitted', 'draft', 'flagged', or None for all
    intent_filter = request.args.get('intent')  # 'interaction', 'dosing', etc., or None for all

    # Build query
    query = Review.query.filter_by(reviewer_id=current_user.id)

    if status_filter:
        query = query.filter_by(status=status_filter)

    # Join with response_queue to get intent
    query = query.join(ResponseQueue, Review.response_queue_id == ResponseQueue.id)

    if intent_filter:
        query = query.filter(ResponseQueue.intent == intent_filter)

    # Order by most recent first
    reviews = query.order_by(Review.submitted_at.desc(), Review.created_at.desc()).all()

    # Format response
    reviews_data = []
    for review in reviews:
        response_queue = db.session.get(ResponseQueue, review.response_queue_id)

        # Calculate average score
        scores = review.segment_scores.values()
        avg_score = sum(s.get('score', 0) for s in scores) / len(scores) if scores else 0

        reviews_data.append({
            'id': review.id,
            'response_queue_id': review.response_queue_id,
            'query_text': response_queue.query_text if response_queue else 'N/A',
            'intent': response_queue.intent if response_queue else 'N/A',
            'status': review.status,
            'avg_score': round(avg_score, 1),
            'submitted_at': review.submitted_at.isoformat() if review.submitted_at else None,
            'created_at': review.created_at.isoformat(),
            'version': review.version,
            'is_current': review.is_current
        })

    return jsonify({
        'success': True,
        'reviews': reviews_data
    }), 200


@api_bp.route('/review/<int:review_id>')
@login_required
def get_review_detail(review_id):
    """Get detailed information about a specific review."""
    review = db.session.get(Review, review_id)

    if not review:
        return jsonify({'success': False, 'error': 'Review not found'}), 404

    # Check authorization (only reviewer or admin can view)
    if review.reviewer_id != current_user.id and not current_user.is_admin():
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    response_queue = db.session.get(ResponseQueue, review.response_queue_id)

    return jsonify({
        'success': True,
        'review': {
            'id': review.id,
            'response_queue_id': review.response_queue_id,
            'query_text': response_queue.query_text if response_queue else 'N/A',
            'intent': response_queue.intent if response_queue else 'N/A',
            'segments': response_queue.segments if response_queue else [],
            'segment_scores': review.segment_scores,
            'overall_notes': review.overall_notes,
            'flag_reason': review.flag_reason,
            'status': review.status,
            'version': review.version,
            'is_current': review.is_current,
            'submitted_at': review.submitted_at.isoformat() if review.submitted_at else None,
            'created_at': review.created_at.isoformat()
        }
    }), 200


@api_bp.route('/rereview/request', methods=['POST'])
@login_required
def request_rereview():
    """Request a re-review of a previously submitted review."""
    from app.models import RereviewRequest

    data = request.json
    review_id = data.get('review_id')
    reason = data.get('reason')

    if not review_id or not reason:
        return jsonify({'success': False, 'error': 'Missing review_id or reason'}), 400

    review = db.session.get(Review, review_id)

    if not review:
        return jsonify({'success': False, 'error': 'Review not found'}), 404

    # Check authorization
    if review.reviewer_id != current_user.id:
        return jsonify({'success': False, 'error': 'Can only re-review your own reviews'}), 403

    # Check if already submitted
    if review.status != 'submitted':
        return jsonify({'success': False, 'error': 'Can only re-review submitted reviews'}), 400

    try:
        # Create re-review request (auto-approved)
        rereview_req = RereviewRequest(
            response_queue_id=review.response_queue_id,
            original_review_id=review.id,
            requested_by=current_user.id,
            reason=reason,
            status='approved',  # Auto-approve
            approved_by=current_user.id
        )
        db.session.add(rereview_req)

        # Reset response_queue status to pending
        response_queue = db.session.get(ResponseQueue, review.response_queue_id)
        response_queue.status = 'pending'

        # Mark original review as not current
        review.is_current = False

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Re-review request created. Response added back to your queue.'
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error creating re-review request: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Failed to create re-review request'}), 500
