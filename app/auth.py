"""
Google OAuth authentication for QA Review Website.
"""
from flask import Blueprint, redirect, url_for, session, flash, current_app, request
from flask_login import login_user, logout_user, login_required
from authlib.integrations.flask_client import OAuth
from datetime import datetime
from app import db
from app.models import Reviewer, ReviewSession

auth_bp = Blueprint('auth', __name__)
oauth = OAuth()


def init_oauth(app):
    """Initialize OAuth with app configuration."""
    oauth.init_app(app)
    oauth.register(
        name='google',
        client_id=app.config['GOOGLE_CLIENT_ID'],
        client_secret=app.config['GOOGLE_CLIENT_SECRET'],
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={'scope': 'openid email profile'}
    )


@auth_bp.record_once
def on_load(state):
    """Initialize OAuth when blueprint is registered."""
    init_oauth(state.app)


@auth_bp.route('/')
def index():
    """Landing page - redirect to login or review based on auth status."""
    from flask_login import current_user
    if current_user.is_authenticated:
        return redirect(url_for('review.review_page'))
    return redirect(url_for('auth.login'))


@auth_bp.route('/login')
def login():
    """Show login page or initiate Google OAuth login."""
    from flask_login import current_user

    # If already authenticated, redirect to review page
    if current_user.is_authenticated:
        return redirect(url_for('review.review_page'))

    # If 'start' query param, begin OAuth flow
    if request.args.get('start'):
        redirect_uri = url_for('auth.callback', _external=True)
        return oauth.google.authorize_redirect(redirect_uri)

    # Otherwise, show login page
    from flask import render_template
    return render_template('login.html')


@auth_bp.route('/login/callback')
def callback():
    """Handle Google OAuth callback."""
    try:
        # Get token and user info from Google
        token = oauth.google.authorize_access_token()
        user_info = token.get('userinfo')

        if not user_info:
            flash('Failed to get user information from Google.', 'error')
            return redirect(url_for('auth.login'))

        email = user_info.get('email')
        google_id = user_info.get('sub')
        name = user_info.get('name', email)

        # Check if email is pre-approved
        if email not in current_app.config['APPROVED_EMAILS']:
            flash(f'Access denied. Email {email} is not authorized.', 'error')
            return redirect(url_for('auth.login'))

        # Find or update reviewer
        reviewer = Reviewer.query.filter_by(email=email).first()

        if not reviewer:
            flash(f'Access denied. Email {email} is not in the reviewers list.', 'error')
            return redirect(url_for('auth.login'))

        # Check if active
        if not reviewer.is_active:
            flash('Your account has been deactivated. Please contact an administrator.', 'error')
            return redirect(url_for('auth.login'))

        # Update google_id if it was pending
        if reviewer.google_id == 'pending' or reviewer.google_id != google_id:
            reviewer.google_id = google_id

        # Update login timestamp
        reviewer.last_login = datetime.utcnow()

        # Update full name if changed
        if reviewer.full_name != name:
            reviewer.full_name = name

        db.session.commit()

        # Create new review session
        review_session = ReviewSession(reviewer_id=reviewer.id)
        db.session.add(review_session)
        db.session.commit()

        # Log in user
        login_user(reviewer, remember=True)
        session['review_session_id'] = review_session.id

        flash(f'Welcome back, {reviewer.full_name}!', 'success')
        return redirect(url_for('review.review_page'))

    except Exception as e:
        current_app.logger.error(f'OAuth callback error: {e}')
        flash('An error occurred during login. Please try again.', 'error')
        return redirect(url_for('auth.login'))


@auth_bp.route('/logout')
@login_required
def logout():
    """Log out current user."""
    from flask_login import current_user

    # End current review session
    session_id = session.get('review_session_id')
    if session_id:
        review_session = db.session.get(ReviewSession, session_id)
        if review_session and not review_session.session_end:
            review_session.session_end = datetime.utcnow()
            db.session.commit()

    # Clear session
    session.clear()

    # Log out
    logout_user()

    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))
