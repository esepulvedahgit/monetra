import os
import pytest

os.environ.setdefault('SECRET_KEY', 'test-secret-key')
os.environ.setdefault('JWT_SECRET_KEY', 'test-jwt-secret-key')
os.environ.setdefault('FLASK_DEBUG', '1')

from app import create_app, db as _db
from app.models import User, Category


class TestConfig:
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False
    SECRET_KEY = 'test-secret-key-32bytes-xxxxxxxxx'
    JWT_SECRET_KEY = 'test-jwt-secret-key-32bytes-xxxxx'
    JWT_ACCESS_TOKEN_EXPIRES = 900
    JWT_REFRESH_TOKEN_EXPIRES = 2592000
    BABEL_DEFAULT_LOCALE = 'es'
    BABEL_SUPPORTED_LOCALES = ['es', 'en']
    BABEL_TRANSLATION_DIRECTORIES = 'translations'
    MAX_CONTENT_LENGTH = 15 * 1024 * 1024
    WEBAUTHN_RP_ID = 'localhost'
    WEBAUTHN_RP_NAME = 'Monetra'
    WEBAUTHN_ORIGIN = 'http://localhost:5000'
    CORS_ORIGINS = ['*']
    RATELIMIT_ENABLED = False


@pytest.fixture(scope='session')
def app():
    application = create_app(TestConfig)
    with application.app_context():
        _db.create_all()
        yield application
        _db.session.remove()
        _db.drop_all()


@pytest.fixture(scope='session')
def client(app):
    return app.test_client()


@pytest.fixture(scope='session')
def seeded_data(app):
    """Create a test user and a default category. Returns (user_id, category_id)."""
    with app.app_context():
        u = User(username='testuser', email='test@example.com', role='user')
        u.set_password('Password123!')
        _db.session.add(u)
        cat = Category(name='Otros', type='expense', user_id=None)
        _db.session.add(cat)
        _db.session.commit()
        return u.id, cat.id


@pytest.fixture(scope='session')
def user(seeded_data):
    return seeded_data[0]


@pytest.fixture(scope='session')
def category_id(seeded_data):
    return seeded_data[1]


@pytest.fixture(autouse=True)
def reset_session(app):
    """Roll back any failed transactions so the session stays healthy between tests."""
    with app.app_context():
        _db.session.rollback()
    yield
    with app.app_context():
        _db.session.rollback()
