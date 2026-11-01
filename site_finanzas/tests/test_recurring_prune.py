"""Finalizing/deactivating a recurring rule must drop its pre-generated future transactions."""
from datetime import date, datetime, timedelta, timezone

import pytest

from app import db
from app.models import RecurringTransaction, Transaction, User
from app.services.finance import prune_recurring_after_end

EMAIL = 'recurring_prune@example.com'
PASSWORD = 'Password123!'


@pytest.fixture(scope='module')
def user(app):
    # Own user so these rows never leak into tests sharing the default user.
    with app.app_context():
        u = User(username='recurring_prune', email=EMAIL, role='user', email_verified=True)
        u.set_password(PASSWORD)
        db.session.add(u)
        db.session.commit()
        user_id = u.id
    yield user_id
    with app.app_context():
        Transaction.query.filter_by(user_id=user_id).delete()
        RecurringTransaction.query.filter_by(user_id=user_id).delete()
        db.session.commit()


def _login(client, email=EMAIL, password=PASSWORD):
    r = client.post('/api/v1/login', json={'email': email, 'password': password})
    assert r.status_code == 200, r.data
    return r.get_json()


def _auth_headers(token):
    return {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}


def _make_rule_with_txs(user_id, category_id, tx_dates):
    rec = RecurringTransaction(
        user_id=user_id, category_id=category_id, type='expense', amount=100,
        day_of_month=5, is_active=True, created_at=datetime.now(timezone.utc),
    )
    db.session.add(rec)
    db.session.commit()
    for d in tx_dates:
        db.session.add(Transaction(
            user_id=user_id, category_id=category_id, type='expense',
            amount=100, date=d, recurring_id=rec.id,
        ))
    db.session.commit()
    return rec


def _remaining_dates(rec_id):
    return sorted(t.date for t in Transaction.query.filter_by(recurring_id=rec_id).all())


def test_prune_keeps_history_and_drops_entries_after_end_date(app, user, category_id):
    with app.app_context():
        rec = _make_rule_with_txs(user, category_id, [
            date(2026, 3, 5), date(2026, 6, 5), date(2026, 11, 5), date(2026, 12, 5),
        ])
        rec.end_date = date(2026, 10, 31)
        rec.is_active = False

        removed = prune_recurring_after_end(rec, today=date(2026, 10, 31))
        db.session.commit()

        assert removed == 2
        assert _remaining_dates(rec.id) == [date(2026, 3, 5), date(2026, 6, 5)]


def test_prune_uses_today_for_deactivated_rule_without_end_date(app, user, category_id):
    with app.app_context():
        rec = _make_rule_with_txs(user, category_id, [date(2026, 9, 5), date(2026, 12, 5)])
        rec.is_active = False

        removed = prune_recurring_after_end(rec, today=date(2026, 10, 31))
        db.session.commit()

        assert removed == 1
        assert _remaining_dates(rec.id) == [date(2026, 9, 5)]


def test_prune_is_noop_for_active_rule_without_end_date(app, user, category_id):
    with app.app_context():
        rec = _make_rule_with_txs(user, category_id, [date(2026, 12, 5)])

        assert prune_recurring_after_end(rec, today=date(2026, 10, 31)) == 0


def test_api_finalize_removes_future_generated_transactions(app, user, category_id):
    # Fresh client: the session-wide one may carry cookies from earlier web tests.
    client = app.test_client()
    today = date.today()
    past, future = today - timedelta(days=10), today + timedelta(days=40)
    with app.app_context():
        rec_id = _make_rule_with_txs(user, category_id, [past, future]).id

    token = _login(client)['access_token']
    r = client.post(f'/api/v1/recurring/{rec_id}/finalize', headers=_auth_headers(token))
    assert r.status_code == 200, r.data

    with app.app_context():
        assert _remaining_dates(rec_id) == [past]
