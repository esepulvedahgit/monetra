"""Integration tests for the USD API child blueprint."""
import hashlib
from datetime import date
from uuid import uuid4

import pytest

from app import db
from app.models import ApiToken, User, UsdCategory, UsdTransaction


def _login(client, email='test@example.com', password='Password123!'):
    response = client.post('/api/v1/login', json={'email': email, 'password': password})
    assert response.status_code == 200, response.data
    return response.get_json()


def _auth_headers(token):
    return {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}


def _make_api_key(app, user_id, raw='mntr_usdapitesttoken'):
    with app.app_context():
        ApiToken.query.filter_by(user_id=user_id).delete()
        db.session.add(ApiToken(
            user_id=user_id,
            token_hash=hashlib.sha256(raw.encode()).hexdigest(),
            prefix=raw[:12],
        ))
        db.session.commit()
    return raw


def _make_usd_category(app, user_id, name='Servicios'):
    with app.app_context():
        category = UsdCategory(
            user_id=user_id,
            name=f'{name}-{uuid4().hex}',
            color='#00C896',
        )
        db.session.add(category)
        db.session.commit()
        return category.id, category.name


def _make_other_users_usd_transaction(app):
    with app.app_context():
        suffix = uuid4().hex
        other_user = User(username=f'other-{suffix}', email=f'other-{suffix}@example.com')
        other_user.set_password('Password123!')
        db.session.add(other_user)
        db.session.flush()
        category = UsdCategory(user_id=other_user.id, name=f'Otro-{suffix}', color='#FF0000')
        db.session.add(category)
        db.session.flush()
        transaction = UsdTransaction(
            user_id=other_user.id,
            category_id=category.id,
            amount='7.50',
            date=date(2026, 9, 4),
            description='ajeno',
        )
        db.session.add(transaction)
        db.session.commit()
        return category.id, transaction.id


def _usd_payload(category_id, **overrides):
    payload = {
        'amount': '24.99',
        'date': '2026-09-04',
        'category_id': category_id,
        'description': 'Suscripción',
    }
    payload.update(overrides)
    return payload


class TestUsdCategories:
    def test_list_returns_only_authenticated_users_categories(self, app, client, user):
        category_id, category_name = _make_usd_category(app, user)
        foreign_category_id, _ = _make_other_users_usd_transaction(app)

        response = client.get(
            '/api/v1/usd/categories',
            headers=_auth_headers(_login(client)['access_token']),
        )

        assert response.status_code == 200
        categories = response.get_json()
        assert {
            'id': category_id,
            'name': category_name,
            'color': '#00C896',
            'is_demo': False,
        } in categories
        assert foreign_category_id not in [category['id'] for category in categories]

    def test_same_persistent_token_authenticates_main_and_usd_routes(self, app, client, user):
        token = _make_api_key(app, user, raw='mntr_sharedusdtoken')
        _make_usd_category(app, user)

        main_response = client.get('/api/v1/transactions', headers=_auth_headers(token))
        usd_response = client.get('/api/v1/usd/categories', headers=_auth_headers(token))

        assert main_response.status_code == 200
        assert usd_response.status_code == 200

    def test_rejects_missing_token(self, client):
        response = client.get('/api/v1/usd/categories')

        assert response.status_code == 401


class TestUsdTransactions:
    def test_create_serializes_fixed_usd_expense_fields(self, app, client, user):
        category_id, category_name = _make_usd_category(app, user)

        response = client.post(
            '/api/v1/usd/transactions',
            headers=_auth_headers(_login(client)['access_token']),
            json=_usd_payload(category_id),
        )

        assert response.status_code == 201
        assert response.get_json() == {
            'id': response.get_json()['id'],
            'type': 'expense',
            'currency': 'USD',
            'amount': 24.99,
            'description': 'Suscripción',
            'date': '2026-09-04',
            'category_id': category_id,
            'category_name': category_name,
            'is_demo': False,
            'created_at': response.get_json()['created_at'],
        }

    def test_list_filters_by_period_and_category_in_descending_date_order(self, app, client, user):
        category_id, _ = _make_usd_category(app, user)
        headers = _auth_headers(_login(client)['access_token'])
        first = client.post('/api/v1/usd/transactions', headers=headers,
                            json=_usd_payload(category_id, date='2026-09-01')).get_json()
        second = client.post('/api/v1/usd/transactions', headers=headers,
                             json=_usd_payload(category_id, date='2026-09-15')).get_json()

        response = client.get(
            f'/api/v1/usd/transactions?year=2026&month=9&category_id={category_id}',
            headers=headers,
        )

        assert response.status_code == 200
        assert response.get_json()['total'] == 2
        assert [transaction['id'] for transaction in response.get_json()['transactions']] == [
            second['id'], first['id'],
        ]

    def test_update_and_delete_owned_transaction(self, app, client, user):
        first_category_id, _ = _make_usd_category(app, user, 'Primera')
        second_category_id, second_category_name = _make_usd_category(app, user, 'Segunda')
        headers = _auth_headers(_login(client)['access_token'])
        create_response = client.post('/api/v1/usd/transactions', headers=headers,
                                      json=_usd_payload(first_category_id))
        assert create_response.status_code == 201
        created = create_response.get_json()

        updated = client.put(
            f"/api/v1/usd/transactions/{created['id']}",
            headers=headers,
            json={'amount': '9.50', 'category_id': second_category_id, 'description': 'Actualizada'},
        )
        deleted = client.delete(f"/api/v1/usd/transactions/{created['id']}", headers=headers)

        assert updated.status_code == 200
        assert updated.get_json()['amount'] == 9.5
        assert updated.get_json()['category_name'] == second_category_name
        assert updated.get_json()['description'] == 'Actualizada'
        assert deleted.status_code == 200
        assert deleted.get_json() == {'message': 'Eliminada'}

    @pytest.mark.parametrize('overrides', [
        {'amount': 0},
        {'amount': '-1'},
        {'amount': '1.001'},
        {'amount': 'NaN'},
        {'amount': '10000000000'},
        {'date': 'invalid-date'},
        {'description': 'x' * 201},
        {'description': 42},
    ])
    def test_rejects_invalid_create_payload(self, app, client, user, overrides):
        category_id, _ = _make_usd_category(app, user)

        response = client.post(
            '/api/v1/usd/transactions',
            headers=_auth_headers(_login(client)['access_token']),
            json=_usd_payload(category_id, **overrides),
        )

        assert response.status_code == 400

    def test_rejects_missing_json_or_foreign_category(self, app, client, user):
        foreign_category_id, _ = _make_other_users_usd_transaction(app)
        headers = _auth_headers(_login(client)['access_token'])

        no_json = client.post('/api/v1/usd/transactions', headers=headers)
        foreign_category = client.post('/api/v1/usd/transactions', headers=headers,
                                       json=_usd_payload(foreign_category_id))

        assert no_json.status_code == 400
        assert foreign_category.status_code == 400

    @pytest.mark.parametrize('update_payload', [
        {'amount': '1.001'},
        {'amount': 'NaN'},
        {'date': 'invalid-date'},
        {'description': 'x' * 201},
        {'description': 42},
        {'category_id': None},
    ])
    def test_rejects_invalid_partial_update(self, app, client, user, update_payload):
        category_id, _ = _make_usd_category(app, user)
        headers = _auth_headers(_login(client)['access_token'])
        created = client.post('/api/v1/usd/transactions', headers=headers,
                              json=_usd_payload(category_id)).get_json()

        response = client.put(f"/api/v1/usd/transactions/{created['id']}",
                              headers=headers, json=update_payload)

        assert response.status_code == 400

    def test_rejects_update_without_json_or_with_foreign_category(self, app, client, user):
        category_id, _ = _make_usd_category(app, user)
        foreign_category_id, _ = _make_other_users_usd_transaction(app)
        headers = _auth_headers(_login(client)['access_token'])
        created = client.post('/api/v1/usd/transactions', headers=headers,
                              json=_usd_payload(category_id)).get_json()

        no_json = client.put(f"/api/v1/usd/transactions/{created['id']}", headers=headers)
        foreign_category = client.put(
            f"/api/v1/usd/transactions/{created['id']}",
            headers=headers,
            json={'category_id': foreign_category_id},
        )

        assert no_json.status_code == 400
        assert foreign_category.status_code == 400

    def test_cannot_read_or_mutate_another_users_transaction(self, app, client, user):
        _, transaction_id = _make_other_users_usd_transaction(app)
        headers = _auth_headers(_login(client)['access_token'])

        update = client.put(f'/api/v1/usd/transactions/{transaction_id}', headers=headers,
                            json={'amount': '99.00'})
        delete = client.delete(f'/api/v1/usd/transactions/{transaction_id}', headers=headers)

        assert update.status_code == 404
        assert delete.status_code == 404
