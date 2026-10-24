"""Tests de la API de Mi Carrito (/api/v1/carts)."""
import hashlib
import io
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from app import db
from app.cart import service as svc
from app.models import ApiToken, Cart, CartItem, Category, Transaction, User


def _make_user(app, currency='CLP'):
    with app.app_context():
        suffix = uuid4().hex[:10]
        user = User(username=f'cartapi-{suffix}', email=f'cartapi-{suffix}@example.com',
                    role='user', email_verified=True, currency_code=currency, currency_locale='es_CL')
        user.set_password('Password123!')
        db.session.add(user)
        if not Category.query.filter_by(name='Alimentación', user_id=None).first():
            db.session.add(Category(name='Alimentación', type='expense', user_id=None))
        db.session.commit()
        raw = f'mntr_cart{suffix}'
        db.session.add(ApiToken(user_id=user.id, token_hash=hashlib.sha256(raw.encode()).hexdigest(),
                                prefix=raw[:12]))
        db.session.commit()
        return user.id, {'Authorization': f'Bearer {raw}'}


@pytest.fixture
def api_user(app):
    user_id, headers = _make_user(app)
    yield user_id, headers
    with app.app_context():
        for cart in Cart.query.filter_by(user_id=user_id).all():
            db.session.delete(cart)
        Transaction.query.filter_by(user_id=user_id).delete()
        db.session.commit()


def _start(client, headers, **body):
    body.setdefault('store_name', 'Lider')
    r = client.post('/api/v1/carts', json=body, headers=headers)
    assert r.status_code in (200, 201), r.data
    return r.get_json()


def _add(client, headers, cart_id, **body):
    return client.post(f'/api/v1/carts/{cart_id}/items', json=body, headers=headers)


class TestCartApi:
    def test_requires_auth(self, client):
        assert client.get('/api/v1/carts').status_code == 401

    def test_full_flow_save_only_then_movement(self, client, api_user):
        _uid, headers = api_user
        r = client.post('/api/v1/carts', json={'store_name': 'Jumbo'}, headers=headers)
        assert r.status_code == 201
        cart = r.get_json()
        assert cart['status'] == 'open' and cart['store_name'] == 'Jumbo' and cart['items'] == []

        # Un segundo POST devuelve el mismo carrito abierto.
        again = client.post('/api/v1/carts', json={}, headers=headers)
        assert again.status_code == 200 and again.get_json()['id'] == cart['id']

        r = _add(client, headers, cart['id'], name='Leche', unit_price=1290, qty=2)
        assert r.status_code == 201
        body = r.get_json()
        assert body['item']['line_total'] == 2580 and body['item']['unit_price'] == 1290
        assert body['cart']['total'] == 2580

        r = _add(client, headers, cart['id'], name='Sandía', line_total='3125.50', qty='2.5')
        assert r.status_code == 201
        assert r.get_json()['item']['unit_price'] == 1250.2
        item_id = r.get_json()['item']['id']

        r = client.delete(f'/api/v1/carts/{cart["id"]}/items/{item_id}', headers=headers)
        assert r.status_code == 200 and r.get_json()['cart']['total'] == 2580

        current = client.get('/api/v1/carts/current', headers=headers).get_json()['cart']
        assert current['id'] == cart['id'] and len(current['items']) == 1

        r = client.post(f'/api/v1/carts/{cart["id"]}/finalize', json={}, headers=headers)
        assert r.status_code == 200
        assert r.get_json()['status'] == 'finalized' and r.get_json()['movement'] is None
        assert client.get('/api/v1/carts/current', headers=headers).get_json()['cart'] is None

        # Total distinto en caja.
        r = client.post(f'/api/v1/carts/{cart["id"]}/movement',
                        json={'amount': 2490, 'date': '2026-10-21'}, headers=headers)
        assert r.status_code == 201
        movement = r.get_json()['movement']
        assert movement['amount'] == 2490 and movement['date'] == '2026-10-21'
        assert movement['type'] == 'expense'

        r = client.post(f'/api/v1/carts/{cart["id"]}/movement', json={}, headers=headers)
        assert r.status_code == 409 and r.get_json()['code'] == 'already_registered'

        detail = client.get(f'/api/v1/carts/{cart["id"]}', headers=headers).get_json()
        assert detail['movement']['id'] == movement['id']
        assert detail['transaction_id'] == movement['id']

    def test_finalize_with_movement(self, client, api_user):
        _uid, headers = api_user
        cart = _start(client, headers)
        _add(client, headers, cart['id'], name='Pan', unit_price=2500)
        r = client.post(f'/api/v1/carts/{cart["id"]}/finalize',
                        json={'register_movement': True, 'amount': 2400}, headers=headers)
        assert r.status_code == 200
        assert r.get_json()['movement']['amount'] == 2400

    def test_validation_errors(self, client, api_user):
        _uid, headers = api_user
        cart = _start(client, headers)
        url = f'/api/v1/carts/{cart["id"]}/items'
        assert client.post(url, json={'name': 'X'}, headers=headers).status_code == 400
        assert client.post(url, json={'name': 'X', 'unit_price': 1, 'line_total': 1},
                           headers=headers).status_code == 400
        assert client.post(url, json={'name': '', 'unit_price': 10}, headers=headers).status_code == 400
        r = client.post(url, json={'name': 'X', 'unit_price': -5}, headers=headers)
        assert r.status_code == 400 and r.get_json()['code'] == 'invalid_amount'

        r = client.post(f'/api/v1/carts/{cart["id"]}/finalize', json={}, headers=headers)
        assert r.status_code == 409 and r.get_json()['code'] == 'cart_empty'
        r = client.post(f'/api/v1/carts/{cart["id"]}/movement', json={}, headers=headers)
        assert r.status_code == 409 and r.get_json()['code'] == 'cart_not_finalized'

    def test_store_name_is_required(self, client, api_user):
        _uid, headers = api_user
        for body in ({}, {'store_name': ''}, {'store_name': '   '}, {'store_name': '1290'}):
            r = client.post('/api/v1/carts', json=body, headers=headers)
            assert r.status_code == 400 and r.get_json()['code'] == 'store_name_required'
        assert client.get('/api/v1/carts/current', headers=headers).get_json()['cart'] is None

        cart = _start(client, headers, store_name='  Santa   Isabel ')
        assert cart['store_name'] == 'Santa Isabel'
        # Con un carrito abierto, POST lo devuelve aunque no venga el nombre.
        r = client.post('/api/v1/carts', json={}, headers=headers)
        assert r.status_code == 200 and r.get_json()['id'] == cart['id']

        r = client.patch(f'/api/v1/carts/{cart["id"]}', json={'store_name': ''}, headers=headers)
        assert r.status_code == 400 and r.get_json()['code'] == 'store_name_required'
        r = client.patch(f'/api/v1/carts/{cart["id"]}', json={'store_name': 'Jumbo'}, headers=headers)
        assert r.status_code == 200 and r.get_json()['store_name'] == 'Jumbo'

    def test_idempotent_item_creation(self, client, api_user):
        _uid, headers = api_user
        cart = _start(client, headers)
        retry_headers = {**headers, 'Idempotency-Key': 'item-abc-1'}
        first = _add(client, retry_headers, cart['id'], name='Leche', unit_price=1290)
        second = _add(client, retry_headers, cart['id'], name='Leche', unit_price=1290)
        assert first.status_code == 201 and second.status_code == 200
        assert first.get_json()['item']['id'] == second.get_json()['item']['id']
        assert second.get_json()['cart']['item_count'] == 1

    def test_list_and_compare(self, app, client, api_user):
        user_id, headers = api_user
        ids = []
        with app.app_context():
            for price in ('1000', '1100'):
                cart = svc.start_cart(user_id, 'Lider')
                svc.add_item(cart, 'Leche Colún', Decimal(price))
                svc.add_item(cart, 'Pan' if price == '1000' else 'Queso', Decimal(500))
                svc.finalize(cart)
                db.session.commit()
                ids.append(cart.id)

        r = client.get('/api/v1/carts?status=finalized&per_page=1', headers=headers)
        body = r.get_json()
        assert r.status_code == 200 and body['total'] == 2 and body['has_next'] is True
        assert len(body['carts']) == 1 and 'items' not in body['carts'][0]

        r = client.get(f'/api/v1/carts/compare?a={ids[1]}&b={ids[0]}', headers=headers)
        body = r.get_json()
        assert r.status_code == 200
        assert body['before']['id'] == ids[0]       # ordenado cronológicamente
        assert body['total_diff'] == 100
        leche = body['items'][0]
        assert leche['name'] == 'Leche Colún' and leche['unit_price_pct'] == 10.0
        names = {i['name']: i for i in body['items']}
        assert names['Pan']['after'] is None and names['Queso']['before'] is None

    def test_other_user_cannot_access(self, app, client, api_user):
        _uid, headers = api_user
        cart = _start(client, headers)
        _other_id, other_headers = _make_user(app)
        assert client.get(f'/api/v1/carts/{cart["id"]}', headers=other_headers).status_code == 404
        assert _add(client, other_headers, cart['id'], name='X', unit_price=1).status_code == 404
        assert client.delete(f'/api/v1/carts/{cart["id"]}', headers=other_headers).status_code == 404
        r = client.post(f'/api/v1/carts/{cart["id"]}/scan', headers=other_headers,
                        data={'image': (io.BytesIO(b'x'), 'p.jpg')}, content_type='multipart/form-data')
        assert r.status_code == 404

    def test_delete_cart(self, app, client, api_user):
        _uid, headers = api_user
        cart = _start(client, headers)
        _add(client, headers, cart['id'], name='Pan', unit_price=2500)
        assert client.delete(f'/api/v1/carts/{cart["id"]}', headers=headers).status_code == 200
        with app.app_context():
            assert db.session.get(Cart, cart['id']) is None
            assert CartItem.query.filter_by(cart_id=cart['id']).count() == 0


class TestCartScanApi:
    def _scan(self, client, headers, cart_id):
        return client.post(f'/api/v1/carts/{cart_id}/scan', headers=headers,
                           data={'image': (io.BytesIO(b'fake'), 'tag.jpg')},
                           content_type='multipart/form-data')

    def test_scan_suggests_without_adding(self, client, api_user):
        user_id, headers = api_user
        cart = _start(client, headers)
        with patch('app.email_service.resolve_ai_config', return_value=SimpleNamespace(user_id=user_id)), \
                patch('app.telegram.image_utils.validate_and_normalize_image', return_value=(b'img', 'image/jpeg')), \
                patch('app.telegram.providers.extract_price_tag', return_value={
                    'name': 'Aceite 1L', 'price': 3990, 'offer_price': 3490, 'offer_text': 'Con tarjeta',
                    'unit': 'unit',
                }):
            r = self._scan(client, headers, cart['id'])
        assert r.status_code == 200
        assert r.get_json() == {'name': 'Aceite 1L', 'price': 3990.0, 'offer_price': 3490.0,
                                'offer_text': 'Con tarjeta', 'unit': 'unit'}
        detail = client.get(f'/api/v1/carts/{cart["id"]}', headers=headers).get_json()
        assert detail['items'] == []

    def test_scan_without_ai_config(self, client, api_user):
        _uid, headers = api_user
        cart = _start(client, headers)
        with patch('app.email_service.resolve_ai_config', return_value=None):
            r = self._scan(client, headers, cart['id'])
        assert r.status_code == 403 and r.get_json()['code'] == 'ai_not_configured'

    def test_scan_shared_key_quota_exceeded(self, client, api_user):
        _uid, headers = api_user
        cart = _start(client, headers)
        with patch('app.email_service.resolve_ai_config', return_value=SimpleNamespace(user_id=-1)), \
                patch('app.email_service.consume_shared_ai_quota', return_value=False):
            r = self._scan(client, headers, cart['id'])
        assert r.status_code == 429 and r.get_json()['code'] == 'ai_quota_exceeded'

    def test_scan_no_price(self, client, api_user):
        user_id, headers = api_user
        cart = _start(client, headers)
        with patch('app.email_service.resolve_ai_config', return_value=SimpleNamespace(user_id=user_id)), \
                patch('app.telegram.image_utils.validate_and_normalize_image', return_value=(b'img', 'image/jpeg')), \
                patch('app.telegram.providers.extract_price_tag', side_effect=ValueError('no price')):
            r = self._scan(client, headers, cart['id'])
        assert r.status_code == 422 and r.get_json()['code'] == 'price_not_found'

    def test_scan_requires_image(self, client, api_user):
        _uid, headers = api_user
        cart = _start(client, headers)
        r = client.post(f'/api/v1/carts/{cart["id"]}/scan', headers=headers, data={},
                        content_type='multipart/form-data')
        assert r.status_code == 400
