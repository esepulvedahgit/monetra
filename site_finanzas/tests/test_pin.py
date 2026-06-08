"""Integration tests for the PIN de acceso rápido feature.

Covers:
- /pin/set  : set PIN with correct/wrong password, trivial/invalid PINs, email alert
- /pin/login: success (device cookie), wrong PIN, lockout, invalid/expired cookie, MFA redirect
- /pin/delete: delete with correct/wrong password, email alert
"""
import hashlib
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from app import db
from app.models import User, UserPinDevice


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PIN_EMAIL    = 'pin_test@example.com'
PIN_PASSWORD = 'PinTestPass123!'
VALID_PIN    = '47283915'   # 8 digits, non-trivial, non-sequential

SET_URL    = '/pin/set'
DELETE_URL = '/pin/delete'
LOGIN_URL  = '/pin/login'
COOKIE_NAME = 'monetra_pin_device'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _web_login(app, email=PIN_EMAIL, password=PIN_PASSWORD):
    """Authenticate via the web login form. Returns a logged-in test client."""
    c = app.test_client()
    r = c.post('/login', data={'email': email, 'password': password})
    assert r.status_code == 302 and '/login' not in r.headers.get('Location', ''), (
        f'Login failed for {email}: status={r.status_code} '
        f'loc={r.headers.get("Location")}'
    )
    return c


def _force_login(app, user_id):
    """Log in a user by injecting the Flask-Login session directly.

    Used when the user has MFA enabled, so the web login form would redirect
    to /mfa-verify instead of completing authentication.

    Sets _login_at so _enforce_session_validity (which validates sessions
    against sessions_valid_after after a DB restore) doesn't reject the session.
    """
    from datetime import datetime, timezone
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
        sess['_login_at'] = datetime.now(timezone.utc).isoformat()
    return c


def _plant_device_cookie(client, raw_token: str):
    """Write the device cookie into the test client's cookie jar.

    Uses path='/' so Python's http.cookiejar sends the cookie for any path
    (including /pin/login). The restrictive /pin path is enforced server-side
    on Set-Cookie responses; testing that here would duplicate browser policy,
    not server logic.
    """
    client.set_cookie(COOKIE_NAME, raw_token, path='/')


# ---------------------------------------------------------------------------
# Module-scoped fixture: a fresh user just for PIN tests
# ---------------------------------------------------------------------------

@pytest.fixture(scope='module')
def pin_user_id(app):
    """Create a user for PIN tests; cleaned up after the module."""
    with app.app_context():
        u = User(username='pin_tester', email=PIN_EMAIL,
                 role='user', email_verified=True)
        u.set_password(PIN_PASSWORD)
        db.session.add(u)
        db.session.commit()
        uid = u.id
    yield uid
    with app.app_context():
        u = User.query.get(uid)
        if u:
            db.session.delete(u)
            db.session.commit()


# ---------------------------------------------------------------------------
# POST /pin/set
# ---------------------------------------------------------------------------

class TestPinSet:

    @pytest.fixture(autouse=True)
    def _enable_mfa(self, app, pin_user_id):
        """pin_set now requires MFA — enable it before each test, restore after."""
        with app.app_context():
            u = db.session.get(User, pin_user_id)
            u.mfa_enabled = True
            db.session.commit()
        yield
        with app.app_context():
            u = db.session.get(User, pin_user_id)
            u.mfa_enabled = False
            db.session.commit()

    def test_set_pin_requires_mfa(self, app, pin_user_id):
        """pin_set must return 403 with an MFA-specific message when MFA is off."""
        # Temporarily override the autouse fixture's setup
        with app.app_context():
            u = db.session.get(User, pin_user_id)
            u.mfa_enabled = False
            db.session.commit()
        c = _web_login(app)
        r = c.post(SET_URL, json={'password': PIN_PASSWORD, 'pin': VALID_PIN},
                   content_type='application/json')
        assert r.status_code == 403
        assert 'MFA' in r.get_json().get('error', '')

    @patch('app.auth.pin_routes.send_security_alert_email')
    def test_set_pin_ok(self, mock_alert, app, pin_user_id):
        c = _force_login(app, pin_user_id)
        r = c.post(SET_URL, json={'password': PIN_PASSWORD, 'pin': VALID_PIN},
                   content_type='application/json')
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('ok') is True
        # A device cookie must be set in the response
        assert COOKIE_NAME in r.headers.get('Set-Cookie', '')
        # Verify DB state
        with app.app_context():
            u = User.query.get(pin_user_id)
            assert u.has_pin
            assert UserPinDevice.query.filter_by(user_id=pin_user_id).count() >= 1
        # Security alert must have been sent
        mock_alert.assert_called_once()
        assert 'activó' in mock_alert.call_args[0][1]

    def test_set_pin_wrong_password(self, app, pin_user_id):
        c = _force_login(app, pin_user_id)
        r = c.post(SET_URL, json={'password': 'wrongpassword', 'pin': VALID_PIN},
                   content_type='application/json')
        assert r.status_code == 403
        assert 'error' in r.get_json()

    def test_set_pin_trivial_all_same_rejected(self, app, pin_user_id):
        c = _force_login(app, pin_user_id)
        for bad in ('00000000', '11111111', '99999999'):
            r = c.post(SET_URL, json={'password': PIN_PASSWORD, 'pin': bad},
                       content_type='application/json')
            assert r.status_code == 400, f'Expected 400 for trivial PIN {bad!r}'

    def test_set_pin_trivial_sequence_rejected(self, app, pin_user_id):
        c = _force_login(app, pin_user_id)
        for bad in ('12345678', '87654321', '01234567'):
            r = c.post(SET_URL, json={'password': PIN_PASSWORD, 'pin': bad},
                       content_type='application/json')
            assert r.status_code == 400, f'Expected 400 for sequential PIN {bad!r}'

    def test_set_pin_wrong_length_rejected(self, app, pin_user_id):
        c = _force_login(app, pin_user_id)
        for bad in ('1234', '123456', '1234567', 'abcdefgh', ''):
            r = c.post(SET_URL, json={'password': PIN_PASSWORD, 'pin': bad},
                       content_type='application/json')
            assert r.status_code == 400, f'Expected 400 for invalid PIN {bad!r}'

    def test_set_pin_unauthenticated_redirected(self, app):
        c = app.test_client()
        r = c.post(SET_URL, json={'password': PIN_PASSWORD, 'pin': VALID_PIN},
                   content_type='application/json')
        assert r.status_code in (302, 401)


# ---------------------------------------------------------------------------
# POST /pin/login
# ---------------------------------------------------------------------------

_KNOWN_RAW_TOKEN = 'test-raw-token-known-device-x1'


class TestPinLogin:
    """Each test gets a fresh PIN state via the autouse fixture."""

    @pytest.fixture(autouse=True)
    def _fresh_pin(self, app, pin_user_id):
        """Reset user to: has PIN, no lockout, one known device."""
        with app.app_context():
            u = User.query.get(pin_user_id)
            u.set_pin(VALID_PIN)
            u.pin_failed_attempts = 0
            u.pin_locked_until = None
            u.mfa_enabled = False
            UserPinDevice.query.filter_by(user_id=pin_user_id).delete()
            db.session.add(UserPinDevice(
                user_id=pin_user_id,
                token_hash=_hash(_KNOWN_RAW_TOKEN),
                device_name='Test Device',
                expires_at=datetime.utcnow() + timedelta(days=90),
            ))
            db.session.commit()

    def test_login_ok(self, app, pin_user_id):
        c = app.test_client()
        _plant_device_cookie(c, _KNOWN_RAW_TOKEN)
        r = c.post(LOGIN_URL, json={'pin': VALID_PIN},
                   content_type='application/json')
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('ok') is True
        assert 'redirect' in data
        # Token rotation: old hash must be gone from DB
        with app.app_context():
            old = UserPinDevice.query.filter_by(
                token_hash=_hash(_KNOWN_RAW_TOKEN)).first()
            assert old is None, 'Old token should have been rotated out'

    def test_login_wrong_pin_increments_counter(self, app, pin_user_id):
        c = app.test_client()
        _plant_device_cookie(c, _KNOWN_RAW_TOKEN)
        r = c.post(LOGIN_URL, json={'pin': '00000001'},
                   content_type='application/json')
        assert r.status_code == 403
        with app.app_context():
            u = User.query.get(pin_user_id)
            assert u.pin_failed_attempts == 1

    def test_lockout_after_5_failures(self, app, pin_user_id):
        c = app.test_client()
        for _ in range(5):
            _plant_device_cookie(c, _KNOWN_RAW_TOKEN)
            resp = c.post(LOGIN_URL, json={'pin': '00000001'},
                          content_type='application/json')
            assert resp.status_code == 403

        # 6th attempt — even with correct PIN — should return 429 (locked)
        _plant_device_cookie(c, _KNOWN_RAW_TOKEN)
        r = c.post(LOGIN_URL, json={'pin': VALID_PIN},
                   content_type='application/json')
        assert r.status_code == 429
        with app.app_context():
            u = User.query.get(pin_user_id)
            assert u.pin_is_locked

    def test_invalid_cookie_rejected(self, app, pin_user_id):
        c = app.test_client()
        _plant_device_cookie(c, 'completely-bogus-token-xyz')
        r = c.post(LOGIN_URL, json={'pin': VALID_PIN},
                   content_type='application/json')
        assert r.status_code == 403

    def test_no_cookie_rejected(self, app, pin_user_id):
        c = app.test_client()
        # No device cookie at all
        r = c.post(LOGIN_URL, json={'pin': VALID_PIN},
                   content_type='application/json')
        assert r.status_code == 403

    def test_expired_device_rejected(self, app, pin_user_id):
        with app.app_context():
            d = UserPinDevice.query.filter_by(user_id=pin_user_id).first()
            d.expires_at = datetime.utcnow() - timedelta(days=1)
            db.session.commit()
        c = app.test_client()
        _plant_device_cookie(c, _KNOWN_RAW_TOKEN)
        r = c.post(LOGIN_URL, json={'pin': VALID_PIN},
                   content_type='application/json')
        assert r.status_code == 403

    def test_mfa_user_redirected_to_mfa_verify(self, app, pin_user_id):
        with app.app_context():
            u = User.query.get(pin_user_id)
            u.mfa_enabled = True
            db.session.commit()
        c = app.test_client()
        _plant_device_cookie(c, _KNOWN_RAW_TOKEN)
        r = c.post(LOGIN_URL, json={'pin': VALID_PIN},
                   content_type='application/json')
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('ok') is True
        assert 'mfa' in data.get('redirect', '').lower()

    def test_unverified_email_does_not_desync_device(self, app, pin_user_id):
        """Regression for bug A1: gate rejection must NOT rotate the device token.

        Before the fix, pin_login rotated the token (committed) before checking
        email_verified, so the 403 response had no Set-Cookie → browser kept the
        old token while DB only had the new hash → device permanently unusable.
        """
        with app.app_context():
            u = db.session.get(User, pin_user_id)
            u.email_verified = False
            db.session.commit()

        c = app.test_client()
        _plant_device_cookie(c, _KNOWN_RAW_TOKEN)
        r = c.post(LOGIN_URL, json={'pin': VALID_PIN}, content_type='application/json')
        assert r.status_code == 403
        assert 'activada' in r.get_json().get('error', '')

        # Restore email_verified — the same original cookie must still work
        with app.app_context():
            u = db.session.get(User, pin_user_id)
            u.email_verified = True
            db.session.commit()

        c2 = app.test_client()
        _plant_device_cookie(c2, _KNOWN_RAW_TOKEN)
        r2 = c2.post(LOGIN_URL, json={'pin': VALID_PIN}, content_type='application/json')
        assert r2.status_code == 200, 'Device should still be valid after email-unverified rejection'
        assert r2.get_json().get('ok') is True

    def test_suspended_user_pin_rejected_device_reusable(self, app, pin_user_id):
        """Suspended user gets explicit 403; device token must NOT rotate."""
        with app.app_context():
            u = db.session.get(User, pin_user_id)
            u.is_suspended = True
            db.session.commit()

        c = app.test_client()
        _plant_device_cookie(c, _KNOWN_RAW_TOKEN)
        r = c.post(LOGIN_URL, json={'pin': VALID_PIN}, content_type='application/json')
        assert r.status_code == 403
        assert 'suspendida' in r.get_json().get('error', '')

        # Reactivate — the same original cookie must still work
        with app.app_context():
            u = db.session.get(User, pin_user_id)
            u.is_suspended = False
            db.session.commit()

        c2 = app.test_client()
        _plant_device_cookie(c2, _KNOWN_RAW_TOKEN)
        r2 = c2.post(LOGIN_URL, json={'pin': VALID_PIN}, content_type='application/json')
        assert r2.status_code == 200, 'Device should still be valid after suspension rejection'
        assert r2.get_json().get('ok') is True


# ---------------------------------------------------------------------------
# POST /pin/delete
# ---------------------------------------------------------------------------

_DELETE_RAW_TOKEN = 'test-raw-token-delete-device-x1'


class TestPinDelete:

    @pytest.fixture(autouse=True)
    def _setup_pin(self, app, pin_user_id):
        """Set a PIN and one device before each delete test."""
        with app.app_context():
            u = User.query.get(pin_user_id)
            u.set_pin(VALID_PIN)
            u.pin_failed_attempts = 0
            u.pin_locked_until = None
            u.mfa_enabled = False   # reset in case a prior test left it True
            UserPinDevice.query.filter_by(user_id=pin_user_id).delete()
            db.session.add(UserPinDevice(
                user_id=pin_user_id,
                token_hash=_hash(_DELETE_RAW_TOKEN),
                device_name='Test Device',
                expires_at=datetime.utcnow() + timedelta(days=90),
            ))
            db.session.commit()

    @patch('app.auth.pin_routes.send_security_alert_email')
    def test_delete_pin_ok(self, mock_alert, app, pin_user_id):
        c = _web_login(app)
        r = c.post(DELETE_URL, json={'password': PIN_PASSWORD},
                   content_type='application/json')
        assert r.status_code == 200
        assert r.get_json().get('ok') is True
        with app.app_context():
            u = User.query.get(pin_user_id)
            assert not u.has_pin
            assert UserPinDevice.query.filter_by(user_id=pin_user_id).count() == 0
        # Security alert must have been sent
        mock_alert.assert_called_once()
        assert 'desactivó' in mock_alert.call_args[0][1]

    def test_delete_pin_wrong_password(self, app, pin_user_id):
        c = _web_login(app)
        r = c.post(DELETE_URL, json={'password': 'wrongpass'},
                   content_type='application/json')
        assert r.status_code == 403
        assert 'error' in r.get_json()
        # PIN must still be there
        with app.app_context():
            u = User.query.get(pin_user_id)
            assert u.has_pin

    def test_delete_pin_unauthenticated_redirected(self, app):
        c = app.test_client()
        r = c.post(DELETE_URL, json={'password': PIN_PASSWORD},
                   content_type='application/json')
        assert r.status_code in (302, 401)


# ---------------------------------------------------------------------------
# Hardening #8 — Disabling MFA must revoke an existing PIN
# ---------------------------------------------------------------------------

MFA_DISABLE_URL = '/configurar/mfa-disable'
_MFA_DEVICE_TOKEN = 'test-raw-token-mfa-disable-x1'


class TestMfaDisableRevokesPin:
    """Disabling MFA removes the PIN and all authorized devices (#8)."""

    @pytest.fixture(autouse=True)
    def _setup(self, app, pin_user_id):
        """Set user to: MFA enabled, PIN set, one authorized device."""
        with app.app_context():
            u = db.session.get(User, pin_user_id)
            u.mfa_enabled = True
            u.set_pin(VALID_PIN)
            u.pin_failed_attempts = 0
            u.pin_locked_until = None
            u.pin_lock_cycles = 0
            UserPinDevice.query.filter_by(user_id=pin_user_id).delete()
            db.session.add(UserPinDevice(
                user_id=pin_user_id,
                token_hash=_hash(_MFA_DEVICE_TOKEN),
                device_name='Test Device',
                expires_at=datetime.utcnow() + timedelta(days=90),
            ))
            db.session.commit()
        yield
        with app.app_context():
            u = db.session.get(User, pin_user_id)
            u.mfa_enabled = False
            u.pin_hash = None
            u.pin_lock_cycles = 0
            UserPinDevice.query.filter_by(user_id=pin_user_id).delete()
            db.session.commit()

    @patch('app.main.routes.decrypt_mfa_secret', return_value='JBSWY3DPEHPK3PXP')
    @patch('pyotp.TOTP.verify', return_value=True)
    @patch('app.main.routes.send_security_alert_email')
    def test_mfa_disable_revokes_pin(self, mock_alert, mock_verify, mock_decrypt, app, pin_user_id):
        """Disabling MFA clears pin_hash and all UserPinDevice records."""
        c = _force_login(app, pin_user_id)
        r = c.post(MFA_DISABLE_URL, json={'code': '000000'},
                   content_type='application/json')
        assert r.status_code == 200
        assert r.get_json().get('ok') is True
        with app.app_context():
            u = db.session.get(User, pin_user_id)
            assert not u.mfa_enabled
            assert not u.has_pin, 'PIN should be revoked when MFA is disabled'
            assert UserPinDevice.query.filter_by(user_id=pin_user_id).count() == 0, \
                'All UserPinDevice records should be deleted'
            assert u.pin_lock_cycles == 0

    @patch('app.main.routes.decrypt_mfa_secret', return_value='JBSWY3DPEHPK3PXP')
    @patch('pyotp.TOTP.verify', return_value=True)
    @patch('app.main.routes.send_security_alert_email')
    def test_mfa_disable_without_pin_is_ok(self, mock_alert, mock_verify, mock_decrypt, app, pin_user_id):
        """Disabling MFA when there is no PIN should still succeed cleanly."""
        with app.app_context():
            u = db.session.get(User, pin_user_id)
            u.pin_hash = None
            UserPinDevice.query.filter_by(user_id=pin_user_id).delete()
            db.session.commit()
        c = _force_login(app, pin_user_id)
        r = c.post(MFA_DISABLE_URL, json={'code': '000000'},
                   content_type='application/json')
        assert r.status_code == 200
        assert r.get_json().get('ok') is True


# ---------------------------------------------------------------------------
# Hardening #4 — Repeated lockout cycles revoke the PIN
# ---------------------------------------------------------------------------

_CYCLE_RAW_TOKEN = 'test-raw-token-cycle-device-x1'


class TestPinLockoutCycles:
    """After MAX_LOCK_CYCLES lockout cycles the PIN is permanently revoked (#4)."""

    @pytest.fixture(autouse=True)
    def _fresh(self, app, pin_user_id):
        """Reset to: has PIN, no lockout, one known device, mfa_enabled=False."""
        with app.app_context():
            u = db.session.get(User, pin_user_id)
            u.set_pin(VALID_PIN)
            u.pin_failed_attempts = 0
            u.pin_locked_until = None
            u.pin_lock_cycles = 0
            u.mfa_enabled = False
            UserPinDevice.query.filter_by(user_id=pin_user_id).delete()
            db.session.add(UserPinDevice(
                user_id=pin_user_id,
                token_hash=_hash(_CYCLE_RAW_TOKEN),
                device_name='Test Device',
                expires_at=datetime.utcnow() + timedelta(days=90),
            ))
            db.session.commit()

    @patch('app.auth.pin_routes.send_security_alert_email')
    def test_repeated_lockout_revokes_pin(self, mock_alert, app, pin_user_id):
        """MAX_LOCK_CYCLES * MAX_FAILS wrong attempts (with inter-cycle resets) revoke the PIN."""
        from app.auth.pin_routes import MAX_FAILS, MAX_LOCK_CYCLES

        last_resp = None
        for cycle_idx in range(MAX_LOCK_CYCLES):
            # Between cycles: simulate time passing by resetting the lockout timer,
            # but leave pin_lock_cycles intact (it accumulates).
            with app.app_context():
                u = db.session.get(User, pin_user_id)
                u.pin_failed_attempts = 0
                u.pin_locked_until = None
                db.session.commit()

            c = app.test_client()
            _plant_device_cookie(c, _CYCLE_RAW_TOKEN)
            for _ in range(MAX_FAILS):
                last_resp = c.post(LOGIN_URL, json={'pin': '00000001'},
                                   content_type='application/json')

        # After MAX_LOCK_CYCLES the PIN must be revoked.
        with app.app_context():
            u = db.session.get(User, pin_user_id)
            assert not u.has_pin, 'PIN should be revoked after MAX_LOCK_CYCLES'
            assert UserPinDevice.query.filter_by(user_id=pin_user_id).count() == 0

        # The final failure response should signal pin_unavailable.
        assert last_resp is not None
        assert last_resp.status_code == 403
        assert last_resp.get_json().get('pin_unavailable') is True

    @patch('app.auth.pin_routes.send_security_alert_email')
    def test_successful_login_resets_lock_cycles(self, mock_alert, app, pin_user_id):
        """A successful PIN login resets pin_lock_cycles to 0."""
        from app.auth.pin_routes import MAX_FAILS

        # Trigger one partial lockout cycle (but not MAX_LOCK_CYCLES)
        with app.app_context():
            u = db.session.get(User, pin_user_id)
            u.pin_lock_cycles = 1   # already had one cycle
            u.pin_failed_attempts = 0
            u.pin_locked_until = None
            db.session.commit()

        # Now log in successfully
        c = app.test_client()
        _plant_device_cookie(c, _CYCLE_RAW_TOKEN)
        r = c.post(LOGIN_URL, json={'pin': VALID_PIN},
                   content_type='application/json')
        assert r.status_code == 200
        with app.app_context():
            u = db.session.get(User, pin_user_id)
            assert u.pin_lock_cycles == 0, 'Successful login should reset pin_lock_cycles'


# ---------------------------------------------------------------------------
# Hardening #6 — pin_unavailable flag triggers localStorage cleanup
# ---------------------------------------------------------------------------

class TestPinUnavailableFlag:
    """Server flags pin_unavailable on device-level failures but not on wrong PIN (#6)."""

    @pytest.fixture(autouse=True)
    def _fresh(self, app, pin_user_id):
        """Reset to: has PIN, no lockout, one known device."""
        with app.app_context():
            u = db.session.get(User, pin_user_id)
            u.set_pin(VALID_PIN)
            u.pin_failed_attempts = 0
            u.pin_locked_until = None
            u.pin_lock_cycles = 0
            u.mfa_enabled = False
            UserPinDevice.query.filter_by(user_id=pin_user_id).delete()
            db.session.add(UserPinDevice(
                user_id=pin_user_id,
                token_hash=_hash(_KNOWN_RAW_TOKEN),
                device_name='Test Device',
                expires_at=datetime.utcnow() + timedelta(days=90),
            ))
            db.session.commit()

    def test_no_cookie_returns_pin_unavailable(self, app, pin_user_id):
        c = app.test_client()
        r = c.post(LOGIN_URL, json={'pin': VALID_PIN},
                   content_type='application/json')
        assert r.status_code == 403
        assert r.get_json().get('pin_unavailable') is True

    def test_unknown_device_returns_pin_unavailable(self, app, pin_user_id):
        c = app.test_client()
        _plant_device_cookie(c, 'completely-bogus-token-xyz')
        r = c.post(LOGIN_URL, json={'pin': VALID_PIN},
                   content_type='application/json')
        assert r.status_code == 403
        assert r.get_json().get('pin_unavailable') is True

    def test_expired_device_returns_pin_unavailable(self, app, pin_user_id):
        with app.app_context():
            d = UserPinDevice.query.filter_by(user_id=pin_user_id).first()
            d.expires_at = datetime.utcnow() - timedelta(days=1)
            db.session.commit()
        c = app.test_client()
        _plant_device_cookie(c, _KNOWN_RAW_TOKEN)
        r = c.post(LOGIN_URL, json={'pin': VALID_PIN},
                   content_type='application/json')
        assert r.status_code == 403
        assert r.get_json().get('pin_unavailable') is True

    def test_wrong_pin_does_not_return_pin_unavailable(self, app, pin_user_id):
        """Device is still valid after a wrong PIN — must NOT send pin_unavailable."""
        c = app.test_client()
        _plant_device_cookie(c, _KNOWN_RAW_TOKEN)
        r = c.post(LOGIN_URL, json={'pin': '00000001'},
                   content_type='application/json')
        assert r.status_code == 403
        data = r.get_json()
        assert not data.get('pin_unavailable'), \
            'pin_unavailable must not be set when the device is valid but PIN is wrong'
