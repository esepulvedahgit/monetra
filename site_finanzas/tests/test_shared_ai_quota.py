"""Tests for consume_shared_ai_quota (security fix #2 — shared-AI daily cap).

Verifies:
- Allows scans up to AI_SHARED_DAILY_LIMIT per day per user.
- Blocks the next scan once the limit is reached (without incrementing further).
- Resets the counter when the date changes (new calendar day).
- Works on first use (shared_ai_scans_date is None).

Uses a real Flask app context (from conftest) to avoid patching local imports,
but mocks out db.session.commit so no DB writes are needed.
"""
import pytest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Fixture: a minimal mock User with only the quota fields
# ---------------------------------------------------------------------------

def _quota_user(scans_date=None, scans_count=0):
    u = MagicMock()
    u.shared_ai_scans_date = scans_date
    u.shared_ai_scans_count = scans_count
    return u


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _call(app_fixture, user, limit=5):
    """Run consume_shared_ai_quota inside the test app context with limit."""
    with app_fixture.app_context():
        app_fixture.config['AI_SHARED_DAILY_LIMIT'] = limit
        from app import db
        from app.email_service import consume_shared_ai_quota
        with patch.object(db.session, 'commit'):
            result = consume_shared_ai_quota(user)
    return result


# ---------------------------------------------------------------------------
# First use / reset
# ---------------------------------------------------------------------------

def test_first_use_allowed(app):
    """When scans_date is None, the first scan should be allowed."""
    user = _quota_user(scans_date=None, scans_count=0)
    result = _call(app, user, limit=5)
    assert result is True
    assert user.shared_ai_scans_count == 1
    assert user.shared_ai_scans_date == date.today()


def test_new_day_resets_counter(app):
    """Counter resets when the stored date is not today."""
    yesterday = date.today() - timedelta(days=1)
    user = _quota_user(scans_date=yesterday, scans_count=99)
    result = _call(app, user, limit=5)
    assert result is True
    assert user.shared_ai_scans_count == 1
    assert user.shared_ai_scans_date == date.today()


# ---------------------------------------------------------------------------
# Within-day allowance
# ---------------------------------------------------------------------------

def test_below_limit_allowed(app):
    """Scans below the daily limit are allowed."""
    user = _quota_user(scans_date=date.today(), scans_count=3)
    result = _call(app, user, limit=5)
    assert result is True
    assert user.shared_ai_scans_count == 4


def test_exactly_at_limit_allowed(app):
    """The scan that brings the count exactly to the limit is still allowed."""
    user = _quota_user(scans_date=date.today(), scans_count=4)
    result = _call(app, user, limit=5)
    assert result is True
    assert user.shared_ai_scans_count == 5


# ---------------------------------------------------------------------------
# Limit enforcement
# ---------------------------------------------------------------------------

def test_over_limit_blocked(app):
    """Scans beyond the daily limit are blocked; counter is NOT incremented."""
    user = _quota_user(scans_date=date.today(), scans_count=5)
    result = _call(app, user, limit=5)
    assert result is False
    assert user.shared_ai_scans_count == 5  # unchanged


def test_well_over_limit_blocked(app):
    """Verify blocking when count is already well above the limit."""
    user = _quota_user(scans_date=date.today(), scans_count=100)
    result = _call(app, user, limit=5)
    assert result is False
    assert user.shared_ai_scans_count == 100  # unchanged


def test_default_limit_25(app):
    """The 25th scan is still allowed; the 26th is blocked."""
    # Scan 25 — allowed
    user = _quota_user(scans_date=date.today(), scans_count=24)
    result = _call(app, user, limit=25)
    assert result is True
    assert user.shared_ai_scans_count == 25

    # Scan 26 — blocked
    result2 = _call(app, user, limit=25)
    assert result2 is False
    assert user.shared_ai_scans_count == 25  # still 25
