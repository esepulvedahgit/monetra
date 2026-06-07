"""Integration tests for the backup PIN feature (contextual Face ID fallback).

Covers:
- /auth/pin/set  : set PIN with correct/wrong password, trivial PINs
- /auth/pin/login: success, no biometric marker, stale marker, wrong PIN,
                   lockout after 5 failures, invalid/expired cookie, MFA redirect
- /auth/pin/delete: delete with correct/wrong password
"""
import hashlib
from datetime import datetime, timedelta

import pytest

from app import db
from app.models import User, UserPinDevice


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PIN_EMAIL    = 'pin_test@example.com'
PIN_PASSWORD = 'PinTestPass123!'
VALID_PIN    = '472839'   # Non-trivial, non-sequential

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


def _set_biometric_marker(client, minutes_ago=0):
    """Inject biometric_attempt_at into the session (simulates a recent Face ID attempt)."""
    ts = (datetime.utcnow() - timedelta(minutes=minutes_ago)).isoformat()
    with client.session_transaction() as sess:
        sess['biometric_attempt_at'] = ts


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
# POST /auth/pin/set
# ---------------------------------------------------------------------------

class TestPinSet:

    def test_set_pin_ok(self, app, pin_user_id):
        c = _web_login(app)
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

    def test_set_pin_wrong_password(self, app, pin_user_id):
        c = _web_login(app)
        r = c.post(SET_URL, json={'password': 'wrongpassword', 'pin': VALID_PIN},
                   content_type='application/json')
        assert r.status_code == 403
        assert 'error' in r.get_json()

    def test_set_pin_trivial_all_same_rejected(self, app, pin_user_id):
        c = _web_login(app)
        for bad in ('000000', '111111', '999999'):
            r = c.post(SET_URL, json={'password': PIN_PASSWORD, 'pin': bad},
                       content_type='application/json')
            assert r.status_code == 400, f'Expected 400 for trivial PIN {bad!r}'

    def test_set_pin_trivial_sequence_rejected(self, app, pin_user_id):
        c = _web_login(app)
        for bad in ('123456', '654321', '012345'):
            r = c.post(SET_URL, json={'password': PIN_PASSWORD, 'pin': bad},
                       content_type='application/json')
            assert r.status_code == 400, f'Expected 400 for sequential PIN {bad!r}'

    def test_set_pin_wrong_length_rejected(self, app, pin_user_id):
        c = _web_login(app)
        for bad in ('1234', '12345', '1234567', 'abcdef'):
            r = c.post(SET_URL, json={'password': PIN_PASSWORD, 'pin': bad},
                       content_type='application/json')
            assert r.status_code == 400, f'Expected 400 for invalid PIN {bad!r}'

    def test_set_pin_unauthenticated_redirected(self, app):
        c = app.test_client()
        r = c.post(SET_URL, json={'password': PIN_PASSWORD, 'pin': VALID_PIN},
                   content_type='application/json')
        assert r.status_code in (302, 401)


# ---------------------------------------------------------------------------
# POST /auth/pin/login
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
        _set_biometric_marker(c)
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

    def test_login_no_biometric_marker_rejected(self, app, pin_user_id):
        c = app.test_client()
        # No biometric_attempt_at in session → 403
        _plant_device_cookie(c, _KNOWN_RAW_TOKEN)
        r = c.post(LOGIN_URL, json={'pin': VALID_PIN},
                   content_type='application/json')
        assert r.status_code == 403

    def test_login_stale_biometric_marker_rejected(self, app, pin_user_id):
        c = app.test_client()
        _set_biometric_marker(c, minutes_ago=10)   # 10 min ago > 5-min window
        _plant_device_cookie(c, _KNOWN_RAW_TOKEN)
        r = c.post(LOGIN_URL, json={'pin': VALID_PIN},
                   content_type='application/json')
        assert r.status_code == 403

    def test_login_wrong_pin_increments_counter(self, app, pin_user_id):
        c = app.test_client()
        _set_biometric_marker(c)
        _plant_device_cookie(c, _KNOWN_RAW_TOKEN)
        r = c.post(LOGIN_URL, json={'pin': '000001'},
                   content_type='application/json')
        assert r.status_code == 403
        with app.app_context():
            u = User.query.get(pin_user_id)
            assert u.pin_failed_attempts == 1

    def test_lockout_after_5_failures(self, app, pin_user_id):
        c = app.test_client()
        for _ in range(5):
            _set_biometric_marker(c)
            _plant_device_cookie(c, _KNOWN_RAW_TOKEN)
            resp = c.post(LOGIN_URL, json={'pin': '000001'},
                          content_type='application/json')
            assert resp.status_code == 403

        # 6th attempt — even with correct PIN — should return 429 (locked)
        _set_biometric_marker(c)
        _plant_device_cookie(c, _KNOWN_RAW_TOKEN)
        r = c.post(LOGIN_URL, json={'pin': VALID_PIN},
                   content_type='application/json')
        assert r.status_code == 429
        with app.app_context():
            u = User.query.get(pin_user_id)
            assert u.pin_is_locked

    def test_invalid_cookie_rejected(self, app, pin_user_id):
        c = app.test_client()
        _set_biometric_marker(c)
        _plant_device_cookie(c, 'completely-bogus-token-xyz')
        r = c.post(LOGIN_URL, json={'pin': VALID_PIN},
                   content_type='application/json')
        assert r.status_code == 403

    def test_no_cookie_rejected(self, app, pin_user_id):
        c = app.test_client()
        _set_biometric_marker(c)
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
        _set_biometric_marker(c)
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
        _set_biometric_marker(c)
        _plant_device_cookie(c, _KNOWN_RAW_TOKEN)
        r = c.post(LOGIN_URL, json={'pin': VALID_PIN},
                   content_type='application/json')
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('ok') is True
        assert 'mfa' in data.get('redirect', '').lower()


# ---------------------------------------------------------------------------
# POST /auth/pin/delete
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

    def test_delete_pin_ok(self, app, pin_user_id):
        c = _web_login(app)
        r = c.post(DELETE_URL, json={'password': PIN_PASSWORD},
                   content_type='application/json')
        assert r.status_code == 200
        assert r.get_json().get('ok') is True
        with app.app_context():
            u = User.query.get(pin_user_id)
            assert not u.has_pin
            assert UserPinDevice.query.filter_by(user_id=pin_user_id).count() == 0

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
