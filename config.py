"""
Configuration for Rutabaga QA Review Website.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration."""

    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'

    # Database (shared with Rutabaga backend)
    DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://rutabaga_user:rutabaga_dev_password@localhost:5432/rutabaga')
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 3600,
        'pool_pre_ping': True
    }

    # Google OAuth
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
    GOOGLE_REDIRECT_URI = os.environ.get('GOOGLE_REDIRECT_URI', 'http://localhost:9000/login/callback')

    # Answer Service
    ANSWER_SERVICE_URL = os.environ.get('ANSWER_SERVICE_URL', 'http://localhost:8000/v2/answer')
    ANSWER_SERVICE_API_KEY = os.environ.get('ANSWER_SERVICE_API_KEY')  # Optional

    # Session
    SESSION_COOKIE_SECURE = os.environ.get('FLASK_ENV') == 'production'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 86400  # 24 hours

    # Pre-approved reviewer emails
    APPROVED_EMAILS = [
        'stephen.dominick@gmail.com',
        'manandhar001@gmail.com'
    ]


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    TESTING = False


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True


# Config dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
