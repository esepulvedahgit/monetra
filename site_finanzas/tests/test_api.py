"""API endpoint tests: auth (JWT + API key), transactions."""
import hashlib
import os
from datetime import datetime, timedelta, timezone
import pytest
import pyotp
from cryptography.fernet import Fernet

from app import db
from app.email_service import encrypt_mfa_secret
from app.models import ApiToken, Budget, Category, PasswordResetToken, Transaction, User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _login(client, email='test@example.com', password='Password123!'):
    r = client.post('/api/v1/login', json={'email': email, 'password': password})
    assert r.status_code == 200, r.data
    return r.get_json()


def _auth_headers(token):
    return {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}


def _tx_payload(category_id, **overrides):
    payload = {
        'type': 'expense',
        'amount': 10.0,
        'date': '2026-06-03',
        'description': 'test',
        'category_id': category_id,
    }
    payload.update(overrides)
    return payload


def _make_api_key(app, user_id, raw='mntr_testtoken00001'):
    """Insert an ApiToken directly and return the raw token string."""
    h = hashlib.sha256(raw.encode()).hexdigest()
    with app.app_context():
        ApiToken.query.filter_by(user_id=user_id).delete()
        db.session.add(ApiToken(user_id=user_id, token_hash=h, prefix=raw[:12]))
        db.session.commit()
    return raw


# ---------------------------------------------------------------------------
# Auth: JWT flow
# ---------------------------------------------------------------------------

class TestJWTAuth:
    def test_login_returns_tokens(self, client, user):
        data = _login(client)
        assert 'access_token' in data
        assert 'refresh_token' in data
        assert 'user' in data
        assert data['user']['name'] == 'testuser'
        assert data['user']['mfa_enabled'] is False

    def test_login_bad_password(self, client, user):
        r = client.post('/api/v1/login', json={'email': 'test@example.com', 'password': 'wrong'})
        assert r.status_code == 401

    def test_login_enforces_existing_account_lockout(self, app, client):
        with app.app_context():
            account = User(username='mobile_lockout', email='lockout@example.com', email_verified=True)
            account.set_password('Password123!')
            db.session.add(account)
            db.session.commit()

        for _ in range(3):
            response = client.post('/api/v1/login', json={
                'email': 'lockout@example.com', 'password': 'wrong'
            })
        assert response.status_code == 401

        locked = client.post('/api/v1/login', json={
            'email': 'lockout@example.com', 'password': 'Password123!'
        })
        assert locked.status_code == 429
        assert locked.get_json()['code'] == 'account_locked'

    def test_login_rejects_suspended_account(self, app, client, user):
        """A suspended account must not obtain a mobile session."""
        with app.app_context():
            account = db.session.get(User, user)
            account.is_suspended = True
            db.session.commit()

        r = client.post('/api/v1/login', json={
            'email': 'test@example.com', 'password': 'Password123!'
        })

        assert r.status_code == 403
        assert r.get_json()['code'] == 'account_suspended'

        with app.app_context():
            account = db.session.get(User, user)
            account.is_suspended = False
            db.session.commit()

    def test_refresh_returns_new_access_token(self, client, user):
        tokens = _login(client)
        r = client.post('/api/v1/refresh',
                        headers={'Authorization': f"Bearer {tokens['refresh_token']}"})
        assert r.status_code == 200
        refreshed = r.get_json()
        assert 'access_token' in refreshed
        assert 'refresh_token' in refreshed

        replay = client.post('/api/v1/refresh', headers={
            'Authorization': f"Bearer {tokens['refresh_token']}"
        })
        assert replay.status_code == 401

    def test_logout_revokes_mobile_tokens(self, client, user):
        tokens = _login(client)
        response = client.post('/api/v1/logout', headers={
            'Authorization': f"Bearer {tokens['refresh_token']}"
        })
        assert response.status_code == 200

        me = client.get('/api/v1/me', headers=_auth_headers(tokens['access_token']))
        assert me.status_code == 401

    def test_me_with_jwt(self, client, user):
        tokens = _login(client)
        r = client.get('/api/v1/me', headers=_auth_headers(tokens['access_token']))
        assert r.status_code == 200
        assert r.get_json()['email'] == 'test@example.com'

    def test_me_without_token_returns_401(self, client):
        r = client.get('/api/v1/me')
        assert r.status_code == 401

    def test_forgot_password_has_generic_mobile_response(self, client, user):
        known = client.post('/api/v1/forgot-password', json={'email': 'test@example.com'})
        unknown = client.post('/api/v1/forgot-password', json={'email': 'missing@example.com'})

        assert known.status_code == 202
        assert unknown.status_code == 202
        assert known.get_json() == unknown.get_json()

    def test_existing_jwt_is_rejected_after_account_suspension(self, app, client, user):
        """Suspension must take effect before the access token naturally expires."""
        token = _login(client)['access_token']
        with app.app_context():
            account = db.session.get(User, user)
            account.is_suspended = True
            db.session.commit()

        response = client.get('/api/v1/me', headers=_auth_headers(token))

        assert response.status_code == 403
        assert response.get_json()['code'] == 'account_suspended'

        with app.app_context():
            account = db.session.get(User, user)
            account.is_suspended = False
            db.session.commit()


# ---------------------------------------------------------------------------
# Auth: persistent API key flow
# ---------------------------------------------------------------------------

class TestApiKey:
    def test_api_key_access_me(self, app, client, user):
        raw = _make_api_key(app, user)
        r = client.get('/api/v1/me', headers=_auth_headers(raw))
        assert r.status_code == 200

    def test_api_key_updates_last_used(self, app, client, user):
        raw = _make_api_key(app, user)
        client.get('/api/v1/me', headers=_auth_headers(raw))
        with app.app_context():
            tok = ApiToken.query.filter_by(user_id=user).first()
            assert tok.last_used_at is not None

    def test_invalid_mntr_token_returns_401(self, client):
        r = client.get('/api/v1/me', headers=_auth_headers('mntr_invalidsignature'))
        assert r.status_code == 401

    def test_malformed_token_returns_401(self, client):
        r = client.get('/api/v1/me', headers=_auth_headers('not_a_valid_token'))
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------

class TestTransactions:
    def test_create_transaction_with_jwt(self, client, user, category_id):
        tokens = _login(client)
        r = client.post('/api/v1/transactions',
                        headers=_auth_headers(tokens['access_token']),
                        json=_tx_payload(category_id))
        assert r.status_code == 201
        data = r.get_json()
        assert float(data['amount']) == 10.0
        assert data['type'] == 'expense'

    def test_create_transaction_with_api_key(self, app, client, user, category_id):
        raw = _make_api_key(app, user, raw='mntr_agenttesttoken0')
        r = client.post('/api/v1/transactions',
                        headers=_auth_headers(raw),
                        json=_tx_payload(category_id, amount=25.5, description='agente'))
        assert r.status_code == 201
        assert float(r.get_json()['amount']) == 25.5

    def test_list_transactions(self, client, user):
        tokens = _login(client)
        r = client.get('/api/v1/transactions', headers=_auth_headers(tokens['access_token']))
        assert r.status_code == 200
        assert 'transactions' in r.get_json()

    def test_create_transaction_invalid_type(self, client, user, category_id):
        tokens = _login(client)
        r = client.post('/api/v1/transactions',
                        headers=_auth_headers(tokens['access_token']),
                        json=_tx_payload(category_id, type='unknown'))
        assert r.status_code == 400

    def test_create_transaction_missing_amount(self, client, user):
        tokens = _login(client)
        r = client.post('/api/v1/transactions',
                        headers=_auth_headers(tokens['access_token']),
                        json={'type': 'expense', 'date': '2026-06-03'})
        assert r.status_code == 400

    def test_create_transaction_invalid_date(self, client, user, category_id):
        tokens = _login(client)
        r = client.post('/api/v1/transactions',
                        headers=_auth_headers(tokens['access_token']),
                        json=_tx_payload(category_id, date='not-a-date'))
        assert r.status_code == 400

    def test_delete_transaction(self, client, user, category_id):
        tokens = _login(client)
        r = client.post('/api/v1/transactions',
                        headers=_auth_headers(tokens['access_token']),
                        json=_tx_payload(category_id, amount=5.0))
        assert r.status_code == 201
        tx_id = r.get_json()['id']
        r2 = client.delete(f'/api/v1/transactions/{tx_id}',
                           headers=_auth_headers(tokens['access_token']))
        assert r2.status_code == 200


class TestMobileDashboardContract:
    def test_summary_includes_budget_and_colored_category_breakdown(self, app, client, user):
        """The mobile dashboard needs one complete monthly response."""
        with app.app_context():
            category = Category(name='Móvil', type='expense', user_id=user, color='#123456')
            db.session.add(category)
            db.session.flush()
            category_id = category.id
            db.session.add_all([
                Transaction(user_id=user, category_id=category.id, type='income', amount=300,
                            description='Ingreso', date=__import__('datetime').date(2026, 9, 2)),
                Transaction(user_id=user, category_id=category.id, type='expense', amount=100,
                            description='Gasto', date=__import__('datetime').date(2026, 9, 3)),
                Budget(user_id=user, year=2026, month=9, amount=200),
            ])
            db.session.commit()

        token = _login(client)['access_token']
        response = client.get('/api/v1/dashboard/summary?year=2026&month=9',
                              headers=_auth_headers(token))

        assert response.status_code == 200
        payload = response.get_json()
        assert payload['budget'] == {
            'limit': 200.0, 'spent': 100.0, 'remaining': 100.0, 'used_pct': 50.0,
            'days_remaining': payload['budget']['days_remaining'],
        }
        assert payload['expense_categories'] == [{
            'id': category_id, 'name': 'Móvil', 'color': '#123456', 'amount': 100.0,
            'percentage': 100.0,
        }]

    def test_categories_return_color_for_mobile_icons(self, app, client, user):
        """A missing color would force the client to invent category styling."""
        with app.app_context():
            category = Category(name='Color móvil', type='expense', user_id=user, color='#abcdef')
            db.session.add(category)
            db.session.commit()
            category_id = category.id

        token = _login(client)['access_token']
        response = client.get('/api/v1/categories?type=expense', headers=_auth_headers(token))

        assert response.status_code == 200
        assert {'id': category_id, 'name': 'Color móvil', 'type': 'expense',
                'is_global': False, 'color': '#abcdef'} in response.get_json()


class TestMobileProfile:
    def test_password_change_revokes_current_mobile_access(self, app, client):
        """Changing a password must force the mobile client to authenticate again."""
        with app.app_context():
            account = User(username='mobile_profile', email='profile@example.com', email_verified=True)
            account.set_password('Password123!')
            db.session.add(account)
            db.session.commit()

        tokens = _login(client, 'profile@example.com', 'Password123!')
        response = client.post('/api/v1/me/password', headers=_auth_headers(tokens['access_token']), json={
            'current_password': 'Password123!',
            'new_password': 'AnotherPass123!',
            'confirm_password': 'AnotherPass123!',
        })

        assert response.status_code == 200
        assert client.get('/api/v1/me', headers=_auth_headers(tokens['access_token'])).status_code == 401
        assert client.post('/api/v1/login', json={
            'email': 'profile@example.com', 'password': 'Password123!'
        }).status_code == 401
        assert client.post('/api/v1/login', json={
            'email': 'profile@example.com', 'password': 'AnotherPass123!'
        }).status_code == 200

    def test_web_password_reset_revokes_mobile_access(self, app, client):
        with app.app_context():
            account = User(username='mobile_reset', email='reset@example.com', email_verified=True)
            account.set_password('Password123!')
            db.session.add(account)
            db.session.flush()
            raw_token = 'mobile-reset-token'
            db.session.add(PasswordResetToken(
                user_id=account.id,
                token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
            ))
            db.session.commit()

        tokens = _login(client, 'reset@example.com', 'Password123!')
        reset = client.post(f'/reset-password/{raw_token}', data={
            'password': 'AnotherPass123!',
            'confirm_password': 'AnotherPass123!',
        })

        assert reset.status_code == 302
        assert client.get('/api/v1/me', headers=_auth_headers(tokens['access_token'])).status_code == 401


class TestMobileMfa:
    def test_login_requires_and_verifies_totp_for_mfa_account(self, app, client, monkeypatch):
        """A password alone must never create a mobile session for MFA users."""
        monkeypatch.setenv('FIELD_ENCRYPTION_KEY', Fernet.generate_key().decode())
        secret = pyotp.random_base32()
        with app.app_context():
            account = User(username='mobile_mfa', email='mfa@example.com', email_verified=True,
                           mfa_enabled=True, mfa_secret_encrypted=encrypt_mfa_secret(secret))
            account.set_password('Password123!')
            db.session.add(account)
            db.session.commit()

        login_response = client.post('/api/v1/login', json={
            'email': 'mfa@example.com', 'password': 'Password123!'
        })

        assert login_response.status_code == 202
        assert login_response.get_json()['status'] == 'mfa_required'
        assert 'access_token' not in login_response.get_json()
        verify_response = client.post('/api/v1/mfa/verify', json={
            'mfa_token': login_response.get_json()['mfa_token'],
            'code': pyotp.TOTP(secret).now(),
        })
        assert verify_response.status_code == 200
        assert 'access_token' in verify_response.get_json()
        reused_response = client.post('/api/v1/mfa/verify', json={
            'mfa_token': login_response.get_json()['mfa_token'],
            'code': pyotp.TOTP(secret).now(),
        })
        assert reused_response.status_code == 401


class TestMobileTransactions:
    def test_transaction_creation_is_idempotent_with_a_client_key(self, client, user, category_id):
        token = _login(client)['access_token']
        headers = {
            **_auth_headers(token),
            'Idempotency-Key': '7e1b9933-2c36-4ac8-8bfd-2e2c3a098027',
        }

        first = client.post('/api/v1/transactions', headers=headers,
                            json=_tx_payload(category_id, description='Sólo una vez'))
        repeated = client.post('/api/v1/transactions', headers=headers,
                               json=_tx_payload(category_id, description='Sólo una vez'))

        assert first.status_code == 201
        assert repeated.status_code == 200
        assert repeated.get_json()['id'] == first.get_json()['id']
        listed = client.get('/api/v1/transactions', headers=_auth_headers(token)).get_json()
        assert sum(item['id'] == first.get_json()['id'] for item in listed['transactions']) == 1

    def test_transactions_support_paginated_mobile_lists(self, app, client):
        """Without pagination, a long financial history would freeze the mobile list."""
        with app.app_context():
            account = User(username='mobile_paging', email='paging@example.com', email_verified=True)
            account.set_password('Password123!')
            db.session.add(account)
            db.session.flush()
            category = Category(name='Paginación', type='expense', user_id=account.id)
            db.session.add(category)
            db.session.flush()
            db.session.add_all([
                Transaction(user_id=account.id, category_id=category.id, type='expense', amount=10,
                            description='Uno', date=__import__('datetime').date(2026, 9, 1)),
                Transaction(user_id=account.id, category_id=category.id, type='expense', amount=20,
                            description='Dos', date=__import__('datetime').date(2026, 9, 2)),
                Transaction(user_id=account.id, category_id=category.id, type='expense', amount=30,
                            description='Tres', date=__import__('datetime').date(2026, 9, 3)),
            ])
            db.session.commit()

        token = _login(client, 'paging@example.com', 'Password123!')['access_token']
        response = client.get('/api/v1/transactions?page=1&per_page=2',
                              headers=_auth_headers(token))

        assert response.status_code == 200
        assert response.get_json()['total'] == 3
        assert response.get_json()['pages'] == 2
        assert response.get_json()['has_next'] is True
        assert [item['description'] for item in response.get_json()['transactions']] == ['Tres', 'Dos']

    def test_patch_updates_a_transaction_for_mobile_editing(self, client, user, category_id):
        """Mobile edits use PATCH so omitted values remain unchanged."""
        token = _login(client)['access_token']
        created = client.post('/api/v1/transactions', headers=_auth_headers(token),
                              json=_tx_payload(category_id, description='Antes')).get_json()

        response = client.patch(f"/api/v1/transactions/{created['id']}",
                                headers=_auth_headers(token), json={'description': 'Después'})

        assert response.status_code == 200
        assert response.get_json()['description'] == 'Después'
        assert response.get_json()['amount'] == 10.0


# ---------------------------------------------------------------------------
# API key management (web routes)
# ---------------------------------------------------------------------------

class TestApiKeyManagement:
    def _web_login(self, client):
        return client.post('/login', data={
            'email': 'test@example.com',
            'password': 'Password123!',
        }, follow_redirects=True)

    def test_generate_creates_token_in_db(self, app, client, user):
        with app.app_context():
            ApiToken.query.filter_by(user_id=user).delete()
            db.session.commit()

        self._web_login(client)
        r = client.post('/configurar/generate-api-token')
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('token', '').startswith('mntr_')

        with app.app_context():
            assert ApiToken.query.filter_by(user_id=user).first() is not None

    def test_regenerate_replaces_existing(self, app, client, user):
        self._web_login(client)
        client.post('/configurar/generate-api-token')
        with app.app_context():
            tok1 = ApiToken.query.filter_by(user_id=user).first()
            hash1 = tok1.token_hash if tok1 else None

        client.post('/configurar/generate-api-token')
        with app.app_context():
            tokens = ApiToken.query.filter_by(user_id=user).all()
            assert len(tokens) == 1
            assert tokens[0].token_hash != hash1

    def test_revoke_removes_token(self, app, client, user):
        self._web_login(client)
        client.post('/configurar/generate-api-token')
        r = client.post('/configurar/revoke-api-token')
        assert r.status_code == 200
        with app.app_context():
            assert ApiToken.query.filter_by(user_id=user).first() is None
