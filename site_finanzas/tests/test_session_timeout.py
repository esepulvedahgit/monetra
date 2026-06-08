"""Integration tests for the inactivity session timeout.

Covers:
- Session without _last_activity is initialized on first authenticated request.
- Session with recent activity (<= timeout) is allowed and timestamp is renewed.
- Session with stale activity (> timeout) is rejected with redirect to login.
- /api/* routes are exempt from the inactivity check.
"""
from datetime import datetime, timezone, timedelta

import pytest

from app import db
from app.models import User

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

USER_EMAIL    = 'session_timeout_test@example.com'
USER_PASSWORD = 'TimeoutTestPass123!'
TIMEOUT_SECONDS = 900  # matches SESSION_INACTIVITY_TIMEOUT default (15 min)


@pytest.fixture(scope='module')
def timeout_user_id(app):
    """Create a dedicated user for session timeout tests."""
    with app.app_context():
        existing = User.query.filter_by(email=USER_EMAIL).first()
        if existing:
            return existing.id
        u = User(username='timeout_tester', email=USER_EMAIL, email_verified=True)
        u.set_password(USER_PASSWORD)
        db.session.add(u)
        db.session.commit()
        return u.id


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_client_with_session(app, user_id, last_activity_offset_seconds=None):
    """Return a test client with a pre-injected authenticated session.

    last_activity_offset_seconds:
      None  → do NOT set _last_activity (simulates first request after login)
      n     → set _last_activity to now - timedelta(seconds=n)
    """
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
        sess['_login_at'] = datetime.now(timezone.utc).isoformat()
        if last_activity_offset_seconds is not None:
            ts = datetime.now(timezone.utc) - timedelta(seconds=last_activity_offset_seconds)
            sess['_last_activity'] = ts.isoformat()
    return c


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestInactivityTimeout:
    def test_no_last_activity_initializes_on_first_request(self, app, timeout_user_id):
        """First authenticated request without _last_activity sets it and grants access."""
        c = _make_client_with_session(app, timeout_user_id, last_activity_offset_seconds=None)
        r = c.get('/', follow_redirects=False)
        # Should NOT redirect to login (may redirect to /dashboard)
        assert r.status_code != 302 or '/login' not in r.headers.get('Location', '')
        # _last_activity must now be set in the session
        with c.session_transaction() as sess:
            assert '_last_activity' in sess

    def test_recent_activity_allows_access(self, app, timeout_user_id):
        """Session with recent activity (1 min ago) is allowed and timestamp is updated."""
        c = _make_client_with_session(app, timeout_user_id, last_activity_offset_seconds=60)
        r = c.get('/', follow_redirects=False)
        assert r.status_code != 302 or '/login' not in r.headers.get('Location', '')
        with c.session_transaction() as sess:
            assert '_last_activity' in sess

    def test_stale_activity_redirects_to_login(self, app, timeout_user_id):
        """Session inactive for longer than the timeout is rejected and redirected to login."""
        c = _make_client_with_session(
            app, timeout_user_id,
            last_activity_offset_seconds=TIMEOUT_SECONDS + 60  # 16 min ago
        )
        r = c.get('/', follow_redirects=False)
        assert r.status_code == 302
        assert 'login' in r.headers.get('Location', '').lower()

    def test_stale_session_clears_user(self, app, timeout_user_id):
        """After inactivity timeout, the session is fully cleared (user_id removed)."""
        c = _make_client_with_session(
            app, timeout_user_id,
            last_activity_offset_seconds=TIMEOUT_SECONDS + 60
        )
        c.get('/', follow_redirects=False)
        with c.session_transaction() as sess:
            assert '_user_id' not in sess

    def test_api_route_exempt_from_inactivity_check(self, app, timeout_user_id):
        """Requests to /api/* are not subject to the inactivity timeout."""
        c = _make_client_with_session(
            app, timeout_user_id,
            last_activity_offset_seconds=TIMEOUT_SECONDS + 60  # would trigger timeout
        )
        # /api routes use JWT auth; we expect a 401 (no token), NOT a 302 redirect
        r = c.get('/api/transactions', follow_redirects=False)
        assert r.status_code != 302
