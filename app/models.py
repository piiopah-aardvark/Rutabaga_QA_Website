"""
SQLAlchemy models for QA Review System.
Maps to qa_reviews schema in PostgreSQL.
"""
from datetime import datetime
from flask_login import UserMixin
from app import db


class Reviewer(UserMixin, db.Model):
    """Authorized reviewers (Google OAuth authenticated)."""

    __tablename__ = 'reviewers'
    __table_args__ = {'schema': 'qa_reviews'}

    id = db.Column(db.Integer, primary_key=True)
    google_id = db.Column(db.String(255), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    full_name = db.Column(db.String(255), nullable=False)
    specialization = db.Column(db.String(100))
    role = db.Column(db.String(50), default='reviewer', nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    total_reviews_submitted = db.Column(db.Integer, default=0)
    total_reviews_flagged = db.Column(db.Integer, default=0)
    total_drafts_saved = db.Column(db.Integer, default=0)

    # Relationships
    reviews = db.relationship('Review', backref='reviewer', lazy='dynamic')
    sessions = db.relationship('ReviewSession', backref='reviewer', lazy='dynamic')

    def is_admin(self):
        """Check if reviewer has admin role."""
        return self.role == 'admin'

    def get_active_session(self):
        """Get current active session (session_end is NULL)."""
        return ReviewSession.query.filter_by(
            reviewer_id=self.id,
            session_end=None
        ).first()

    def __repr__(self):
        return f'<Reviewer {self.email}>'


class ResponseQueue(db.Model):
    """Queue of responses to be reviewed."""

    __tablename__ = 'response_queue'
    __table_args__ = {'schema': 'qa_reviews'}

    id = db.Column(db.Integer, primary_key=True)
    intent = db.Column(db.String(100), nullable=False, index=True)
    query_text = db.Column(db.Text, nullable=False)
    slots = db.Column(db.JSON, nullable=False)

    # Response data
    response_data = db.Column(db.JSON, nullable=False)
    segments = db.Column(db.JSON, nullable=False)

    # Source tracking
    source_references = db.Column(db.JSON)
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)
    generated_by_service_version = db.Column(db.String(50))

    # Review status
    status = db.Column(db.String(50), default='pending', nullable=False, index=True)
    assigned_to = db.Column(db.Integer, db.ForeignKey('qa_reviews.reviewers.id'))

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_modified = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    reviews = db.relationship('Review', backref='response', lazy='dynamic')
    rereview_requests = db.relationship('RereviewRequest', backref='response', lazy='dynamic')

    def __repr__(self):
        return f'<ResponseQueue {self.id} - {self.intent}>'


class Review(db.Model):
    """Review records with segment scores and suggestions."""

    __tablename__ = 'reviews'
    __table_args__ = (
        db.UniqueConstraint('response_queue_id', 'reviewer_id', 'version'),
        {'schema': 'qa_reviews'}
    )

    id = db.Column(db.Integer, primary_key=True)
    response_queue_id = db.Column(db.Integer, db.ForeignKey('qa_reviews.response_queue.id'), nullable=False)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('qa_reviews.reviewers.id'), nullable=False)

    # Version tracking for re-reviews
    version = db.Column(db.Integer, default=1, nullable=False)
    is_current = db.Column(db.Boolean, default=True, nullable=False)

    # Review data
    segment_scores = db.Column(db.JSON, nullable=False)
    overall_notes = db.Column(db.Text)
    flag_reason = db.Column(db.Text)

    # Status
    status = db.Column(db.String(50), nullable=False, index=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    submitted_at = db.Column(db.DateTime)

    # Relationships
    audit_logs = db.relationship('ReviewAuditLog', backref='review', lazy='dynamic')
    production_updates = db.relationship('ProductionUpdate', backref='review', lazy='dynamic')

    def __repr__(self):
        return f'<Review {self.id} by {self.reviewer_id} v{self.version}>'


class ReviewAuditLog(db.Model):
    """Audit trail of all review actions."""

    __tablename__ = 'review_audit_log'
    __table_args__ = {'schema': 'qa_reviews'}

    id = db.Column(db.Integer, primary_key=True)
    review_id = db.Column(db.Integer, db.ForeignKey('qa_reviews.reviews.id'), nullable=False, index=True)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('qa_reviews.reviewers.id'), nullable=False, index=True)
    action = db.Column(db.String(50), nullable=False)
    previous_status = db.Column(db.String(50))
    new_status = db.Column(db.String(50))
    changes = db.Column(db.JSON)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f'<AuditLog {self.action} on Review {self.review_id}>'


class ProductionUpdate(db.Model):
    """Log of all updates to production tables from QA reviews."""

    __tablename__ = 'production_updates'
    __table_args__ = {'schema': 'qa_reviews'}

    id = db.Column(db.Integer, primary_key=True)
    review_id = db.Column(db.Integer, db.ForeignKey('qa_reviews.reviews.id'), nullable=False)
    intent = db.Column(db.String(100), nullable=False)

    # What was updated
    target_table = db.Column(db.String(255), nullable=False, index=True)
    target_record_id = db.Column(db.Integer)

    # Data tracking
    original_data = db.Column(db.JSON, nullable=False)
    updated_data = db.Column(db.JSON, nullable=False)

    # Metadata
    updated_by = db.Column(db.Integer, db.ForeignKey('qa_reviews.reviewers.id'), nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Rollback capability
    rolled_back = db.Column(db.Boolean, default=False, index=True)
    rollback_reason = db.Column(db.Text)

    def __repr__(self):
        return f'<ProductionUpdate {self.id} - {self.target_table}>'


class RereviewRequest(db.Model):
    """Requests to re-review previously submitted responses."""

    __tablename__ = 'rereview_requests'
    __table_args__ = {'schema': 'qa_reviews'}

    id = db.Column(db.Integer, primary_key=True)
    response_queue_id = db.Column(db.Integer, db.ForeignKey('qa_reviews.response_queue.id'), nullable=False)
    original_review_id = db.Column(db.Integer, db.ForeignKey('qa_reviews.reviews.id'), nullable=False)
    requested_by = db.Column(db.Integer, db.ForeignKey('qa_reviews.reviewers.id'), nullable=False)
    reason = db.Column(db.Text, nullable=False)

    # Auto-approved for now
    status = db.Column(db.String(50), default='approved', nullable=False, index=True)
    approved_by = db.Column(db.Integer, db.ForeignKey('qa_reviews.reviewers.id'))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime)

    def __repr__(self):
        return f'<RereviewRequest {self.id} - {self.status}>'


class ReviewSession(db.Model):
    """Session tracking for per-session counters in UI."""

    __tablename__ = 'review_sessions'
    __table_args__ = {'schema': 'qa_reviews'}

    id = db.Column(db.Integer, primary_key=True)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('qa_reviews.reviewers.id'), nullable=False, index=True)
    session_start = db.Column(db.DateTime, default=datetime.utcnow)
    session_end = db.Column(db.DateTime, index=True)
    reviews_completed = db.Column(db.Integer, default=0)
    reviews_flagged = db.Column(db.Integer, default=0)
    reviews_drafted = db.Column(db.Integer, default=0)
    reviews_skipped = db.Column(db.Integer, default=0)

    def __repr__(self):
        return f'<ReviewSession {self.id} - {self.reviewer_id}>'
