"""Tests for consume_shared_ai_quota (security fix — shared-AI daily cap).

Verifies:
- Allows scans up to AI_SHARED_DAILY_LIMIT per day per user.
- Blocks the next scan once the limit is reached (without incrementing further).
- Resets the counter when the date changes (new calendar day).
- Works on first use (shared_ai_scans_date is None).

Uses real ORM User objects in the in-memory SQLite test DB so that the atomic
SQL UPDATE in consume_shared_ai_quota executes correctly.
"""
import pytest
from datetime import date, timedelta

from app import db as _db
from app.models import User
from app.email_service import consume_shared_ai_quota

_counter = [0]


def _make_user(app, scans_date=None, scans_count=0):
    """Create and persist a real User with the given quota state."""
    _counter[0] += 1
    with app.app_context():
        u = User(
            username=f'quota_test_{_counter[0]}',
            email=f'quota_test_{_counter[0]}@example.com',
            role='user',
            email_verified=True,
            shared_ai_scans_date=scans_date,
            shared_ai_scans_count=scans_count,
        )
        u.set_password('Passw0rd!')
        _db.session.add(u)
        _db.session.commit()
        return u.id


def _call(app, user_id, limit=5):
    """Run consume_shared_ai_quota inside the test app context with given limit."""
    with app.app_context():
        app.config['AI_SHARED_DAILY_LIMIT'] = limit
        u = _db.session.get(User, user_id)
        result = consume_shared_ai_quota(u)
        # Refresh to read committed state
        _db.session.refresh(u)
        return result, u.shared_ai_scans_count, u.shared_ai_scans_date


# ---------------------------------------------------------------------------
# First use / reset
# ---------------------------------------------------------------------------

def test_first_use_allowed(app):
    """When scans_date is None, the first scan should be allowed."""
    uid = _make_user(app, scans_date=None, scans_count=0)
    result, count, d = _call(app, uid, limit=5)
    assert result is True
    assert count == 1
    assert d == date.today()


def test_new_day_resets_counter(app):
    """Counter resets when the stored date is not today."""
    yesterday = date.today() - timedelta(days=1)
    uid = _make_user(app, scans_date=yesterday, scans_count=99)
    result, count, d = _call(app, uid, limit=5)
    assert result is True
    assert count == 1
    assert d == date.today()


# ---------------------------------------------------------------------------
# Within-day allowance
# ---------------------------------------------------------------------------

def test_below_limit_allowed(app):
    """Scans below the daily limit are allowed."""
    uid = _make_user(app, scans_date=date.today(), scans_count=3)
    result, count, _ = _call(app, uid, limit=5)
    assert result is True
    assert count == 4


def test_exactly_at_limit_allowed(app):
    """The scan that brings the count exactly to the limit is still allowed."""
    uid = _make_user(app, scans_date=date.today(), scans_count=4)
    result, count, _ = _call(app, uid, limit=5)
    assert result is True
    assert count == 5


# ---------------------------------------------------------------------------
# Limit enforcement
# ---------------------------------------------------------------------------

def test_over_limit_blocked(app):
    """Scans beyond the daily limit are blocked; counter is NOT incremented."""
    uid = _make_user(app, scans_date=date.today(), scans_count=5)
    result, count, _ = _call(app, uid, limit=5)
    assert result is False
    assert count == 5  # unchanged


def test_well_over_limit_blocked(app):
    """Verify blocking when count is already well above the limit."""
    uid = _make_user(app, scans_date=date.today(), scans_count=100)
    result, count, _ = _call(app, uid, limit=5)
    assert result is False
    assert count == 100  # unchanged


def test_default_limit_25(app):
    """The 25th scan is still allowed; the 26th is blocked."""
    uid = _make_user(app, scans_date=date.today(), scans_count=24)

    result, count, _ = _call(app, uid, limit=25)
    assert result is True
    assert count == 25

    result2, count2, _ = _call(app, uid, limit=25)
    assert result2 is False
    assert count2 == 25  # still 25
