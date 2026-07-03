"""Integration tests for account lockout on the password/MFA login flow.

Covers:
- /login      : lockout after LOGIN_MAX_FAILS wrong passwords, reset on success
- /mfa-verify : lockout after LOGIN_MAX_FAILS wrong TOTP codes, reset on success
- Audit trail (AUTH_ACCOUNT_LOCKED) and security alert email on lockout
"""
from unittest.mock import patch

import pytest

from app import db
from app.models import User, AuditLog
from app.audit import events as ev
from config import Config

LOCKOUT_EMAIL    = 'lockout_test@example.com'
LOCKOUT_PASSWORD = 'LockoutTestPass123!'

LOGIN_URL = '/login'
MFA_URL   = '/mfa-verify'

MAX_FAILS = Config.LOGIN_MAX_FAILS


def _post_login(c, email=LOCKOUT_EMAIL, password=LOCKOUT_PASSWORD):
    return c.post(LOGIN_URL, data={'email': email, 'password': password})


@pytest.fixture(scope='module')
def lockout_user_id(app):
    """Create a user for lockout tests; cleaned up after the module."""
    with app.app_context():
        u = User(username='lockout_tester', email=LOCKOUT_EMAIL,
                 role='user', email_verified=True)
        u.set_password(LOCKOUT_PASSWORD)
        db.session.add(u)
        db.session.commit()
        uid = u.id
    yield uid
    with app.app_context():
        u = User.query.get(uid)
        if u:
            db.session.delete(u)
            db.session.commit()


@pytest.fixture(autouse=True)
def _fresh_lockout_state(app, lockout_user_id):
    """Reset lockout counters, MFA state and audit log before each test."""
    with app.app_context():
        u = User.query.get(lockout_user_id)
        u.failed_login_attempts = 0
        u.login_locked_until = None
        u.mfa_enabled = False
        u.mfa_secret_encrypted = None
        AuditLog.query.filter_by(user_id=lockout_user_id).delete()
        db.session.commit()


# ---------------------------------------------------------------------------
# POST /login — password lockout
# ---------------------------------------------------------------------------

class TestPasswordLockout:

    def test_wrong_password_increments_counter(self, app, lockout_user_id):
        c = app.test_client()
        r = _post_login(c, password='wrong-password')
        assert r.status_code == 200
        assert 'incorrectos' in r.get_data(as_text=True)
        with app.app_context():
            u = User.query.get(lockout_user_id)
            assert u.failed_login_attempts == 1
            assert not u.login_is_locked

    @patch('app.auth.routes.send_security_alert_email_async')
    def test_lockout_after_max_fails(self, mock_alert, app, lockout_user_id):
        c = app.test_client()
        for _ in range(MAX_FAILS):
            r = _post_login(c, password='wrong-password')
            assert r.status_code == 200

        # One more attempt — even with the correct password — must stay blocked.
        r = _post_login(c)
        assert r.status_code == 200
        assert 'bloqueada' in r.get_data(as_text=True)
        with app.app_context():
            u = User.query.get(lockout_user_id)
            assert u.login_is_locked
        mock_alert.assert_called_once()
        assert 'inicio de sesión' in mock_alert.call_args[0][1]

    @patch('app.auth.routes.send_security_alert_email_async')
    def test_lockout_creates_audit_event(self, mock_alert, app, lockout_user_id):
        c = app.test_client()
        for _ in range(MAX_FAILS):
            _post_login(c, password='wrong-password')
        with app.app_context():
            events = AuditLog.query.filter_by(
                user_id=lockout_user_id, event_type=ev.AUTH_ACCOUNT_LOCKED).all()
            assert len(events) == 1

    def test_successful_login_resets_lockout(self, app, lockout_user_id):
        c = app.test_client()
        # A couple of failures, but below the lockout threshold.
        for _ in range(MAX_FAILS - 1):
            _post_login(c, password='wrong-password')
        with app.app_context():
            u = User.query.get(lockout_user_id)
            assert u.failed_login_attempts == MAX_FAILS - 1

        r = _post_login(c)
        assert r.status_code == 302
        with app.app_context():
            u = User.query.get(lockout_user_id)
            assert u.failed_login_attempts == 0
            assert u.login_locked_until is None


# ---------------------------------------------------------------------------
# POST /mfa-verify — TOTP lockout (same counter as password)
# ---------------------------------------------------------------------------

class TestMfaLockout:

    @pytest.fixture(autouse=True)
    def _enable_mfa(self, app, lockout_user_id):
        with app.app_context():
            u = User.query.get(lockout_user_id)
            u.mfa_enabled = True
            u.mfa_secret_encrypted = b'fake-encrypted-secret'
            db.session.commit()

    def _start_mfa_pending(self, app):
        """Password login succeeds and redirects to /mfa-verify, arming the pending session."""
        c = app.test_client()
        r = _post_login(c)
        assert r.status_code == 302
        assert '/mfa-verify' in r.headers.get('Location', '')
        return c

    @patch('app.auth.routes.decrypt_mfa_secret', return_value='JBSWY3DPEHPK3PXP')
    @patch('pyotp.TOTP.verify', return_value=False)
    @patch('app.auth.routes.send_security_alert_email_async')
    def test_lockout_after_max_mfa_fails(self, mock_alert, mock_verify, mock_decrypt, app, lockout_user_id):
        c = self._start_mfa_pending(app)
        for _ in range(MAX_FAILS):
            r = c.post(MFA_URL, data={'code': '000000'})
            assert r.status_code == 200

        with app.app_context():
            u = User.query.get(lockout_user_id)
            assert u.login_is_locked

        # Even a correct code must stay blocked once the account is locked.
        mock_verify.return_value = True
        r = c.post(MFA_URL, data={'code': '000000'})
        assert 'bloqueada' in r.get_data(as_text=True)
        mock_alert.assert_called_once()

    @patch('app.auth.routes.decrypt_mfa_secret', return_value='JBSWY3DPEHPK3PXP')
    @patch('pyotp.TOTP.verify', return_value=True)
    def test_successful_mfa_resets_lockout(self, mock_verify, mock_decrypt, app, lockout_user_id):
        c = self._start_mfa_pending(app)
        with app.app_context():
            u = User.query.get(lockout_user_id)
            u.failed_login_attempts = MAX_FAILS - 1
            db.session.commit()

        r = c.post(MFA_URL, data={'code': '123456'})
        assert r.status_code == 302
        with app.app_context():
            u = User.query.get(lockout_user_id)
            assert u.failed_login_attempts == 0
            assert u.login_locked_until is None
