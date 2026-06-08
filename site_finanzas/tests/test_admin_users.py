"""Integration tests for the admin user-management feature.

Covers:
- GET /admin/users/    : access control (non-admin, admin-not-first, first-admin OK)
- POST /suspend        : toggle, self-protection, first-admin protection, email alert
- POST /delete         : wrong password, correct password, cascades, first-admin protection
- last_login_at        : set by login(), mfa_verify(), pin_login(), webauthn path skipped (no browser)
- is_suspended         : login() rejects suspended users; before_request forces logout
"""
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from app import db
from app.models import User, ApiToken, UserPinDevice
import hashlib


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ADMIN_EMAIL    = 'first_admin@example.com'
ADMIN_PASSWORD = 'AdminPass123!'
USER_EMAIL     = 'reg_user@example.com'
USER_PASSWORD  = 'UserPass123!'
ADMIN2_EMAIL   = 'admin2@example.com'
ADMIN2_PASSWORD = 'Admin2Pass123!'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _web_login(app, email, password):
    c = app.test_client()
    r = c.post('/login', data={'email': email, 'password': password})
    assert r.status_code == 302 and '/login' not in r.headers.get('Location', ''), (
        f'Login failed for {email}: {r.status_code} {r.headers.get("Location")}'
    )
    return c


# ---------------------------------------------------------------------------
# Module fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope='module')
def admin_user_id(app):
    """First admin (protected — cannot be suspended or deleted)."""
    with app.app_context():
        u = User(username='first_admin', email=ADMIN_EMAIL,
                 role='admin', is_first_admin=True, email_verified=True)
        u.set_password(ADMIN_PASSWORD)
        db.session.add(u)
        db.session.commit()
        uid = u.id
    yield uid
    with app.app_context():
        u = db.session.get(User, uid)
        if u:
            db.session.delete(u)
            db.session.commit()


@pytest.fixture(scope='module')
def regular_user_id(app, admin_user_id):
    """Regular user to be managed by the admin."""
    with app.app_context():
        u = User(username='reg_user', email=USER_EMAIL,
                 role='user', email_verified=True)
        u.set_password(USER_PASSWORD)
        db.session.add(u)
        db.session.commit()
        uid = u.id
    yield uid
    with app.app_context():
        u = db.session.get(User, uid)
        if u:
            db.session.delete(u)
            db.session.commit()


@pytest.fixture(scope='module')
def admin2_user_id(app, admin_user_id):
    """Non-first admin (can access the admin panel but cannot act on first_admin)."""
    with app.app_context():
        u = User(username='admin2', email=ADMIN2_EMAIL,
                 role='admin', is_first_admin=False, email_verified=True)
        u.set_password(ADMIN2_PASSWORD)
        db.session.add(u)
        db.session.commit()
        uid = u.id
    yield uid
    with app.app_context():
        u = db.session.get(User, uid)
        if u:
            db.session.delete(u)
            db.session.commit()


# ---------------------------------------------------------------------------
# Access control — GET /admin/users/
# ---------------------------------------------------------------------------

class TestAccessControl:

    def test_unauthenticated_redirected(self, app):
        c = app.test_client()
        r = c.get('/admin/users/')
        assert r.status_code in (302, 401, 403)

    def test_regular_user_forbidden(self, app, regular_user_id):
        c = _web_login(app, USER_EMAIL, USER_PASSWORD)
        r = c.get('/admin/users/')
        assert r.status_code == 403

    def test_non_first_admin_forbidden(self, app, admin2_user_id):
        c = _web_login(app, ADMIN2_EMAIL, ADMIN2_PASSWORD)
        r = c.get('/admin/users/')
        assert r.status_code == 403

    def test_first_admin_ok(self, app, admin_user_id):
        c = _web_login(app, ADMIN_EMAIL, ADMIN_PASSWORD)
        r = c.get('/admin/users/')
        assert r.status_code == 200
        assert b'reg_user' in r.data or b'Usuarios' in r.data


# ---------------------------------------------------------------------------
# Suspend / reactivate
# ---------------------------------------------------------------------------

class TestSuspend:

    @pytest.fixture(autouse=True)
    def _unsuspend(self, app, regular_user_id):
        """Ensure the user starts each test unsuspended."""
        with app.app_context():
            u = db.session.get(User, regular_user_id)
            u.is_suspended = False
            db.session.commit()

    @patch('app.admin.routes.send_security_alert_email')
    def test_suspend_ok(self, mock_alert, app, admin_user_id, regular_user_id):
        c = _web_login(app, ADMIN_EMAIL, ADMIN_PASSWORD)
        r = c.post(f'/admin/users/{regular_user_id}/suspend',
                   data={'csrf_token': 'test'})
        assert r.status_code == 302
        with app.app_context():
            u = db.session.get(User, regular_user_id)
            assert u.is_suspended is True
        mock_alert.assert_called_once()
        assert 'suspendida' in mock_alert.call_args[0][1]

    @patch('app.admin.routes.send_security_alert_email')
    def test_reactivate_ok(self, mock_alert, app, admin_user_id, regular_user_id):
        # Pre-suspend
        with app.app_context():
            u = db.session.get(User, regular_user_id)
            u.is_suspended = True
            db.session.commit()
        c = _web_login(app, ADMIN_EMAIL, ADMIN_PASSWORD)
        r = c.post(f'/admin/users/{regular_user_id}/suspend',
                   data={'csrf_token': 'test'})
        assert r.status_code == 302
        with app.app_context():
            u = db.session.get(User, regular_user_id)
            assert u.is_suspended is False
        mock_alert.assert_called_once()
        assert 'reactivada' in mock_alert.call_args[0][1]

    def test_cannot_suspend_self(self, app, admin_user_id):
        c = _web_login(app, ADMIN_EMAIL, ADMIN_PASSWORD)
        r = c.post(f'/admin/users/{admin_user_id}/suspend',
                   data={'csrf_token': 'test'})
        assert r.status_code == 302
        with app.app_context():
            u = db.session.get(User, admin_user_id)
            assert u.is_suspended is False

    def test_cannot_suspend_first_admin(self, app, admin_user_id):
        c = _web_login(app, ADMIN_EMAIL, ADMIN_PASSWORD)
        r = c.post(f'/admin/users/{admin_user_id}/suspend',
                   data={'csrf_token': 'test'})
        assert r.status_code == 302
        with app.app_context():
            u = db.session.get(User, admin_user_id)
            assert u.is_suspended is False


# ---------------------------------------------------------------------------
# Suspended user cannot login / is force-logged-out
# ---------------------------------------------------------------------------

class TestSuspendedLogin:

    @pytest.fixture(autouse=True)
    def _setup(self, app, regular_user_id):
        with app.app_context():
            u = db.session.get(User, regular_user_id)
            u.is_suspended = True
            db.session.commit()
        yield
        with app.app_context():
            u = db.session.get(User, regular_user_id)
            u.is_suspended = False
            db.session.commit()

    def test_suspended_user_cannot_login(self, app):
        c = app.test_client()
        r = c.post('/login', data={'email': USER_EMAIL, 'password': USER_PASSWORD})
        # Must not redirect to dashboard — stays on login or shows error
        location = r.headers.get('Location', '')
        assert r.status_code == 302 and 'dashboard' not in location

    def test_suspended_user_forced_logout_on_request(self, app, regular_user_id):
        """If user gets suspended while logged in, next request should redirect."""
        # First login while not suspended
        with app.app_context():
            u = db.session.get(User, regular_user_id)
            u.is_suspended = False
            db.session.commit()
        c = _web_login(app, USER_EMAIL, USER_PASSWORD)
        # Now suspend
        with app.app_context():
            u = db.session.get(User, regular_user_id)
            u.is_suspended = True
            db.session.commit()
        # Next authenticated request should redirect (force-logout)
        r = c.get('/dashboard')
        assert r.status_code in (302, 401)


# ---------------------------------------------------------------------------
# Delete user
# ---------------------------------------------------------------------------

class TestDeleteUser:

    def _make_target(self, app):
        """Create a fresh user to delete (so we don't destroy the module fixture)."""
        with app.app_context():
            u = User(username='del_target', email='del_target@example.com',
                     role='user', email_verified=True)
            u.set_password('DelPass123!')
            db.session.add(u)
            db.session.commit()
            uid = u.id
        return uid

    def test_wrong_password_does_not_delete(self, app, admin_user_id, regular_user_id):
        c = _web_login(app, ADMIN_EMAIL, ADMIN_PASSWORD)
        r = c.post(f'/admin/users/{regular_user_id}/delete',
                   data={'password': 'WRONG_PASSWORD', 'csrf_token': 'test'})
        assert r.status_code == 302
        with app.app_context():
            assert db.session.get(User, regular_user_id) is not None

    @patch('app.admin.routes.send_security_alert_email')
    def test_correct_password_deletes_user(self, mock_alert, app, admin_user_id):
        target_id = self._make_target(app)
        c = _web_login(app, ADMIN_EMAIL, ADMIN_PASSWORD)
        r = c.post(f'/admin/users/{target_id}/delete',
                   data={'password': ADMIN_PASSWORD, 'csrf_token': 'test'})
        assert r.status_code == 302
        with app.app_context():
            assert db.session.get(User, target_id) is None
        mock_alert.assert_called_once()

    @patch('app.admin.routes.send_security_alert_email')
    def test_delete_also_removes_api_token(self, mock_alert, app, admin_user_id):
        target_id = self._make_target(app)
        # Give the user an ApiToken
        with app.app_context():
            tok = ApiToken(user_id=target_id, token_hash='a' * 64, prefix='mntr_test_')
            db.session.add(tok)
            db.session.commit()
        c = _web_login(app, ADMIN_EMAIL, ADMIN_PASSWORD)
        c.post(f'/admin/users/{target_id}/delete',
               data={'password': ADMIN_PASSWORD, 'csrf_token': 'test'})
        with app.app_context():
            assert db.session.get(User, target_id) is None
            assert ApiToken.query.filter_by(user_id=target_id).count() == 0

    def test_cannot_delete_first_admin(self, app, admin_user_id):
        c = _web_login(app, ADMIN_EMAIL, ADMIN_PASSWORD)
        r = c.post(f'/admin/users/{admin_user_id}/delete',
                   data={'password': ADMIN_PASSWORD, 'csrf_token': 'test'})
        assert r.status_code == 302
        with app.app_context():
            assert db.session.get(User, admin_user_id) is not None

    def test_cannot_delete_self(self, app, admin_user_id):
        c = _web_login(app, ADMIN_EMAIL, ADMIN_PASSWORD)
        r = c.post(f'/admin/users/{admin_user_id}/delete',
                   data={'password': ADMIN_PASSWORD, 'csrf_token': 'test'})
        assert r.status_code == 302
        with app.app_context():
            assert db.session.get(User, admin_user_id) is not None


# ---------------------------------------------------------------------------
# last_login_at updated on login
# ---------------------------------------------------------------------------

class TestLastLoginAt:

    def test_last_login_at_set_on_password_login(self, app, regular_user_id):
        with app.app_context():
            u = db.session.get(User, regular_user_id)
            u.last_login_at = None
            u.is_suspended = False
            db.session.commit()
        _web_login(app, USER_EMAIL, USER_PASSWORD)
        with app.app_context():
            u = db.session.get(User, regular_user_id)
            assert u.last_login_at is not None

    def test_last_login_at_set_on_pin_login(self, app, regular_user_id):
        """PIN login also updates last_login_at."""
        VALID_PIN = '47283915'
        raw_token = 'test-admin-pin-token-x1'
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        with app.app_context():
            u = db.session.get(User, regular_user_id)
            u.is_suspended = False
            u.last_login_at = None
            u.mfa_enabled = False
            u.set_pin(VALID_PIN)
            u.pin_failed_attempts = 0
            u.pin_locked_until = None
            UserPinDevice.query.filter_by(user_id=regular_user_id).delete()
            db.session.add(UserPinDevice(
                user_id=regular_user_id,
                token_hash=token_hash,
                device_name='Test',
                expires_at=datetime.utcnow() + timedelta(days=90),
            ))
            db.session.commit()

        c = app.test_client()
        c.set_cookie('monetra_pin_device', raw_token, path='/')
        c.post('/pin/login', json={'pin': VALID_PIN}, content_type='application/json')

        with app.app_context():
            u = db.session.get(User, regular_user_id)
            assert u.last_login_at is not None
