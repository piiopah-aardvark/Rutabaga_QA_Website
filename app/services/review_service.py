"""
Service for handling review actions (skip, flag, draft, submit).
"""
from datetime import datetime
from typing import Dict, Any, Optional
from flask import current_app
from app import db
from app.models import (
    ResponseQueue, Review, ReviewAuditLog, ReviewSession,
    RereviewRequest, ProductionUpdate
)


class ReviewService:
    """Handles review workflow logic."""

    @staticmethod
    def get_next_response(intent: str, reviewer_id: int) -> Optional[ResponseQueue]:
        """
        Get next unreviewed response for the given intent and reviewer.

        Priority:
        1. Re-review requests for this reviewer (approved)
        2. Unreviewed responses (no review exists)

        Args:
            intent: Intent to get response for
            reviewer_id: Current reviewer ID

        Returns:
            ResponseQueue object or None
        """
        # Priority 1: Pending re-review requests for this reviewer
        rereview = db.session.query(ResponseQueue).join(
            RereviewRequest,
            RereviewRequest.response_queue_id == ResponseQueue.id
        ).filter(
            ResponseQueue.intent == intent,
            RereviewRequest.requested_by == reviewer_id,
            RereviewRequest.status == 'approved',
            ResponseQueue.status == 'pending'
        ).first()

        if rereview:
            return rereview

        # Priority 2: Unreviewed responses
        unreviewed = db.session.query(ResponseQueue).filter(
            ResponseQueue.intent == intent,
            ResponseQueue.status == 'pending'
        ).outerjoin(
            Review,
            Review.response_queue_id == ResponseQueue.id
        ).filter(
            Review.id.is_(None)  # No review exists
        ).first()

        return unreviewed

    @staticmethod
    def skip_response(response_id: int, reviewer_id: int, session_id: int) -> bool:
        """
        Skip a response without reviewing.

        Args:
            response_id: Response queue ID
            reviewer_id: Current reviewer ID
            session_id: Current session ID

        Returns:
            Success boolean
        """
        try:
            # Update session
            session = db.session.get(ReviewSession, session_id)
            if session:
                session.reviews_skipped += 1

            # Log skip action (no review record created)
            audit = ReviewAuditLog(
                review_id=None,
                reviewer_id=reviewer_id,
                action='skipped',
                previous_status=None,
                new_status=None,
                changes={'response_id': response_id}
            )
            db.session.add(audit)
            db.session.commit()

            return True
        except Exception as e:
            current_app.logger.error(f"Error skipping response: {e}")
            db.session.rollback()
            return False

    @staticmethod
    def flag_response(
        response_id: int,
        reviewer_id: int,
        session_id: int,
        flag_reason: str,
        segment_scores: Dict[str, Any],
        overall_notes: Optional[str] = None
    ) -> bool:
        """
        Flag a response for admin review.

        Args:
            response_id: Response queue ID
            reviewer_id: Current reviewer ID
            session_id: Current session ID
            flag_reason: Reason for flagging
            segment_scores: Scores and suggestions for segments
            overall_notes: Additional notes

        Returns:
            Success boolean
        """
        try:
            # Create review record
            review = Review(
                response_queue_id=response_id,
                reviewer_id=reviewer_id,
                segment_scores=segment_scores,
                overall_notes=overall_notes,
                flag_reason=flag_reason,
                status='flagged',
                created_at=datetime.utcnow()
            )
            db.session.add(review)
            db.session.flush()  # Get review ID

            # Update response queue
            response = db.session.get(ResponseQueue, response_id)
            response.status = 'flagged'

            # Update session
            session = db.session.get(ReviewSession, session_id)
            if session:
                session.reviews_flagged += 1

            # Update reviewer stats
            from app.models import Reviewer
            reviewer = db.session.get(Reviewer, reviewer_id)
            reviewer.total_reviews_flagged += 1

            # Audit log
            audit = ReviewAuditLog(
                review_id=review.id,
                reviewer_id=reviewer_id,
                action='flagged',
                previous_status='pending',
                new_status='flagged',
                changes={'reason': flag_reason}
            )
            db.session.add(audit)

            db.session.commit()
            return True

        except Exception as e:
            current_app.logger.error(f"Error flagging response: {e}")
            db.session.rollback()
            return False

    @staticmethod
    def save_draft(
        response_id: int,
        reviewer_id: int,
        session_id: int,
        segment_scores: Dict[str, Any],
        overall_notes: Optional[str] = None
    ) -> bool:
        """
        Save review as draft.

        Args:
            response_id: Response queue ID
            reviewer_id: Current reviewer ID
            session_id: Current session ID
            segment_scores: Scores and suggestions for segments
            overall_notes: Additional notes

        Returns:
            Success boolean
        """
        try:
            # Check if draft already exists
            existing_draft = Review.query.filter_by(
                response_queue_id=response_id,
                reviewer_id=reviewer_id,
                status='draft'
            ).first()

            if existing_draft:
                # Update existing draft
                existing_draft.segment_scores = segment_scores
                existing_draft.overall_notes = overall_notes
                review = existing_draft
            else:
                # Create new draft
                review = Review(
                    response_queue_id=response_id,
                    reviewer_id=reviewer_id,
                    segment_scores=segment_scores,
                    overall_notes=overall_notes,
                    status='draft',
                    created_at=datetime.utcnow()
                )
                db.session.add(review)
                db.session.flush()

            # Update response queue
            response = db.session.get(ResponseQueue, response_id)
            response.status = 'draft'

            # Update session
            session = db.session.get(ReviewSession, session_id)
            if session:
                session.reviews_drafted += 1

            # Update reviewer stats
            from app.models import Reviewer
            reviewer = db.session.get(Reviewer, reviewer_id)
            reviewer.total_drafts_saved += 1

            # Audit log
            audit = ReviewAuditLog(
                review_id=review.id,
                reviewer_id=reviewer_id,
                action='saved_draft',
                previous_status='pending',
                new_status='draft'
            )
            db.session.add(audit)

            db.session.commit()
            return True

        except Exception as e:
            current_app.logger.error(f"Error saving draft: {e}")
            db.session.rollback()
            return False

    @staticmethod
    def submit_review(
        response_id: int,
        reviewer_id: int,
        session_id: int,
        segment_scores: Dict[str, Any],
        overall_notes: Optional[str] = None
    ) -> bool:
        """
        Submit review and update production database.

        Args:
            response_id: Response queue ID
            reviewer_id: Current reviewer ID
            session_id: Current session ID
            segment_scores: Scores and suggestions for segments
            overall_notes: Additional notes

        Returns:
            Success boolean
        """
        try:
            # Create review record
            review = Review(
                response_queue_id=response_id,
                reviewer_id=reviewer_id,
                segment_scores=segment_scores,
                overall_notes=overall_notes,
                status='submitted',
                created_at=datetime.utcnow(),
                submitted_at=datetime.utcnow()
            )
            db.session.add(review)
            db.session.flush()  # Get review ID

            # Update response queue
            response = db.session.get(ResponseQueue, response_id)
            response.status = 'submitted'

            # Update session
            session = db.session.get(ReviewSession, session_id)
            if session:
                session.reviews_completed += 1

            # Update reviewer stats
            from app.models import Reviewer
            reviewer = db.session.get(Reviewer, reviewer_id)
            reviewer.total_reviews_submitted += 1

            # Audit log
            audit = ReviewAuditLog(
                review_id=review.id,
                reviewer_id=reviewer_id,
                action='submitted',
                previous_status='pending',
                new_status='submitted'
            )
            db.session.add(audit)

            # TODO: Update production tables (Phase 5)
            # For now, just log what would be updated
            current_app.logger.info(
                f"Review {review.id} submitted. Production update pending implementation."
            )

            db.session.commit()
            return True

        except Exception as e:
            current_app.logger.error(f"Error submitting review: {e}")
            db.session.rollback()
            return False
