"""
Flask application factory for Rutabaga QA Review Website.
"""
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import config

# Initialize extensions
db = SQLAlchemy()
login_manager = LoginManager()


def create_app(config_name=None):
    """
    Create and configure the Flask application.

    Args:
        config_name: Configuration name ('development', 'production', or None for env var)

    Returns:
        Configured Flask application
    """
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access the QA review portal.'

    # Register blueprints
    from app.auth import auth_bp
    app.register_blueprint(auth_bp)

    from app.routes.review import review_bp
    app.register_blueprint(review_bp)

    from app.routes.admin import admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')

    from app.routes.api import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')

    # User loader for Flask-Login
    from app.models import Reviewer

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(Reviewer, int(user_id))

    # Health check endpoint
    @app.route('/health')
    def health():
        return {'status': 'healthy', 'service': 'qa-review-website'}, 200

    return app
