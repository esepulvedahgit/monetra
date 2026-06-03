"""API endpoint tests: auth (JWT + API key), transactions."""
import hashlib
import pytest

from app import db
from app.models import ApiToken


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

    def test_login_bad_password(self, client, user):
        r = client.post('/api/v1/login', json={'email': 'test@example.com', 'password': 'wrong'})
        assert r.status_code == 401

    def test_refresh_returns_new_access_token(self, client, user):
        tokens = _login(client)
        r = client.post('/api/v1/refresh',
                        headers={'Authorization': f"Bearer {tokens['refresh_token']}"})
        assert r.status_code == 200
        assert 'access_token' in r.get_json()

    def test_me_with_jwt(self, client, user):
        tokens = _login(client)
        r = client.get('/api/v1/me', headers=_auth_headers(tokens['access_token']))
        assert r.status_code == 200
        assert r.get_json()['email'] == 'test@example.com'

    def test_me_without_token_returns_401(self, client):
        r = client.get('/api/v1/me')
        assert r.status_code == 401


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
