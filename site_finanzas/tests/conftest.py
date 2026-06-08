import os
import pytest

os.environ.setdefault('SECRET_KEY', 'test-secret-key')
os.environ.setdefault('JWT_SECRET_KEY', 'test-jwt-secret-key')
os.environ.setdefault('FLASK_DEBUG', '1')

from sqlalchemy.pool import StaticPool

from app import create_app, db as _db
from app.models import User, Category


class TestConfig:
    TESTING = True
    # StaticPool forces all connections to use the same in-memory SQLite DB so
    # data committed in fixtures is visible inside test-client request contexts.
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_ENGINE_OPTIONS = {
        'connect_args': {'check_same_thread': False},
        'poolclass': StaticPool,
    }
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
    CORS_ORIGINS = ['*']
    RATELIMIT_ENABLED = False


@pytest.fixture(scope='session')
def app():
    application = create_app(TestConfig)
    # Create tables once, then POP the context so each test request gets its
    # own fresh app context (and therefore a fresh g._login_user).  With
    # StaticPool the in-memory SQLite connection — and its data — persists for
    # the lifetime of the engine even when no app context is active.
    with application.app_context():
        _db.create_all()
    yield application
    with application.app_context():
        _db.session.remove()
        _db.drop_all()


@pytest.fixture(scope='session')
def client(app):
    return app.test_client()


@pytest.fixture(scope='session')
def seeded_data(app):
    """Create a test user and a default category. Returns (user_id, category_id)."""
    with app.app_context():
        u = User(username='testuser', email='test@example.com', role='user', email_verified=True)
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


@pytest.fixture(scope='session')
def admin_user_id(app):
    """First-admin user: role='admin', is_first_admin=True. Created once per session."""
    with app.app_context():
        from app.models import AppConfig
        if not AppConfig.query.first():
            _db.session.add(AppConfig(allow_registration=True))
            _db.session.commit()
        u = User(
            username='admin_backup_test',
            email='admin_backup@example.com',
            role='admin',
            is_first_admin=True,
            email_verified=True,
        )
        u.set_password('AdminPass123!')
        _db.session.add(u)
        _db.session.commit()
        return u.id


@pytest.fixture(scope='session')
def regular_user_id(app):
    """Non-admin user. Created once per session."""
    with app.app_context():
        u = User(
            username='regular_backup_test',
            email='regular_backup@example.com',
            role='user',
            is_first_admin=False,
            email_verified=True,
        )
        u.set_password('RegPass123!')
        _db.session.add(u)
        _db.session.commit()
        return u.id
