"""Tests de Mi Carrito: servicio, flujo del bot de Telegram y vistas web."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

import pytest

from app import db as _db
from app.cart import service as svc
from app.models import (
    Cart,
    CartItem,
    CartPendingItem,
    Category,
    TelegramLink,
    Transaction,
    User,
)
from app.telegram.handlers import process_update

CART_EMAIL = 'cart_user@example.com'
CART_PASSWORD = 'CartPass123!'
OTHER_EMAIL = 'cart_other@example.com'
CHAT_ID = 555001


@pytest.fixture(scope='module')
def cart_user_id(app):
    with app.app_context():
        u = User(username='cart_user', email=CART_EMAIL, role='user', email_verified=True,
                 currency_code='CLP', currency_locale='es_CL', currency_symbol='$')
        u.set_password(CART_PASSWORD)
        _db.session.add(u)
        if not Category.query.filter_by(name='Alimentación', user_id=None).first():
            _db.session.add(Category(name='Alimentación', type='expense', user_id=None))
        _db.session.commit()
        _db.session.add(TelegramLink(user_id=u.id, chat_id=CHAT_ID, enabled=True))
        _db.session.commit()
        return u.id


@pytest.fixture(scope='module')
def other_user_id(app):
    with app.app_context():
        u = User(username='cart_other', email=OTHER_EMAIL, role='user', email_verified=True)
        u.set_password(CART_PASSWORD)
        _db.session.add(u)
        _db.session.commit()
        return u.id


@pytest.fixture(autouse=True)
def _clean_carts(app):
    yield
    with app.app_context():
        CartPendingItem.query.delete()
        CartItem.query.delete()
        Cart.query.delete()
        _db.session.commit()


def _login(app, email=CART_EMAIL):
    c = app.test_client()
    r = c.post('/login', data={'email': email, 'password': CART_PASSWORD})
    assert r.status_code == 302 and '/login' not in r.headers.get('Location', '')
    return c


# ── Servicio ──────────────────────────────────────────────────────────────────

class TestCartService:
    def test_add_items_and_running_total(self, app, cart_user_id):
        with app.app_context():
            cart = svc.start_cart(cart_user_id)
            svc.add_item(cart, 'Leche', Decimal(1290))
            svc.add_item(cart, 'Yogurt', Decimal(1980), qty=2)
            assert cart.total == Decimal(3270)
            assert cart.item_count == 2
            assert cart.items[1].unit_price == Decimal(990)

            removed = svc.remove_last_item(cart)
            assert removed.name == 'Yogurt'
            assert cart.total == Decimal(1290)
            assert cart.item_count == 1

    def test_only_one_open_cart(self, app, cart_user_id):
        with app.app_context():
            first = svc.start_cart(cart_user_id)
            assert svc.start_cart(cart_user_id).id == first.id

    def test_rejects_invalid_amounts(self, app, cart_user_id):
        with app.app_context():
            cart = svc.start_cart(cart_user_id)
            for bad in (0, -5, 'abc', Decimal(99999999999)):
                with pytest.raises(svc.CartError):
                    svc.add_item(cart, 'X', bad)

    def test_finalize_save_only_then_register_with_checkout_amount(self, app, cart_user_id):
        with app.app_context():
            cart = svc.start_cart(cart_user_id)
            svc.add_item(cart, 'Pan', Decimal(2500))
            assert svc.finalize(cart) is None
            assert cart.status == 'finalized'
            assert cart.transaction_id is None

            # En caja el total fue distinto: se registra con el monto real.
            tx = svc.register_movement(cart, amount=Decimal(2300))
            _db.session.commit()
            assert tx.amount == Decimal(2300)
            assert tx.type == 'expense'
            assert cart.transaction_id == tx.id
            assert _db.session.get(Category, tx.category_id).name == 'Alimentación'

            with pytest.raises(svc.CartError) as exc:
                svc.register_movement(cart)
            assert exc.value.code == 'already_registered'
            _db.session.delete(tx)
            _db.session.commit()

    def test_finalize_with_movement(self, app, cart_user_id):
        with app.app_context():
            cart = svc.start_cart(cart_user_id)
            svc.add_item(cart, 'Arroz', Decimal(1500))
            tx = svc.finalize(cart, register=True)
            _db.session.commit()
            assert tx.amount == Decimal(1500)
            _db.session.delete(tx)
            _db.session.commit()

    def test_cannot_finalize_empty_cart(self, app, cart_user_id):
        with app.app_context():
            cart = svc.start_cart(cart_user_id)
            with pytest.raises(svc.CartError) as exc:
                svc.finalize(cart)
            assert exc.value.code == 'cart_empty'

    def test_register_requires_owned_expense_category(self, app, cart_user_id, other_user_id):
        with app.app_context():
            foreign = Category(name='Ajena', type='expense', user_id=other_user_id)
            _db.session.add(foreign)
            cart = svc.start_cart(cart_user_id)
            svc.add_item(cart, 'Pan', Decimal(2500))
            svc.finalize(cart)
            with pytest.raises(svc.CartError) as exc:
                svc.register_movement(cart, category_id=foreign.id)
            assert exc.value.code == 'invalid_category'
            _db.session.rollback()

    def test_stale_cart_is_saved_automatically(self, app, cart_user_id):
        with app.app_context():
            cart = svc.start_cart(cart_user_id)
            svc.add_item(cart, 'Pan', Decimal(2500))
            cart.updated_at = datetime.now(timezone.utc) - timedelta(hours=7)
            _db.session.commit()
            closed = svc.close_stale_cart(cart_user_id)
            assert closed is not None and closed.status == 'finalized'
            assert svc.get_open_cart(cart_user_id) is None


# ── Telegram ──────────────────────────────────────────────────────────────────

def _text(text):
    return {'message': {'chat': {'id': CHAT_ID, 'type': 'private'}, 'text': text}}


def _photo():
    return {'message': {'chat': {'id': CHAT_ID, 'type': 'private'},
                        'photo': [{'file_id': 'f1', 'file_size': 10}]}}


def _callback(data):
    return {'callback_query': {'id': 'cb', 'data': data,
                               'message': {'message_id': 1, 'chat': {'id': CHAT_ID, 'type': 'private'}}}}


def _buttons(mock_buttons):
    """callback_data de los botones del último mensaje con teclado."""
    rows = mock_buttons.call_args.args[2]
    return [b['callback_data'] for row in rows for b in row]


@pytest.fixture
def tg(app, cart_user_id):
    """Mockea la API de Telegram y ejecuta updates dentro de un request context."""
    with patch('app.telegram.cart_flow.send_message') as send, \
            patch('app.telegram.cart_flow.send_message_with_buttons') as buttons, \
            patch('app.telegram.cart_flow.answer_callback_query'), \
            patch('app.telegram.cart_flow.edit_message_reply_markup'), \
            patch('app.telegram.handlers.send_message'), \
            patch('app.telegram.handlers.send_message_with_buttons'):

        def run(update):
            with app.test_request_context('/telegram/webhook/x', method='POST'):
                process_update(update)

        yield run, send, buttons


class TestTelegramCartFlow:
    def test_full_flow_save_only(self, app, cart_user_id, tg):
        run, send, buttons = tg
        run(_text('/carrito'))
        assert 'Carrito iniciado' in send.call_args.args[1]

        run(_text('Leche entera 1290'))
        with app.app_context():
            pending = CartPendingItem.query.filter_by(chat_id=CHAT_ID).one()
            assert pending.name == 'Leche entera'
            assert pending.line_total == Decimal(1290)
            pending_id = pending.id
        assert f'cartok:{pending_id}' in _buttons(buttons)

        run(_callback(f'cartok:{pending_id}'))
        assert 'Total del carrito' in buttons.call_args.args[1]

        run(_text('2 x 990 yogurt'))
        with app.app_context():
            pending = CartPendingItem.query.filter_by(chat_id=CHAT_ID).one()
            assert pending.qty == 2 and pending.line_total == Decimal(1980)
            pending_id = pending.id
        run(_callback(f'cartok:{pending_id}'))

        with app.app_context():
            cart = svc.get_open_cart(cart_user_id)
            assert cart.total == Decimal(3270)
            assert cart.item_count == 2
            cart_id = cart.id

        run(_callback(f'cartend:{cart_id}'))
        assert {f'cartsave:{cart_id}', f'cartmov:{cart_id}'} <= set(_buttons(buttons))

        run(_callback(f'cartsave:{cart_id}'))
        with app.app_context():
            cart = _db.session.get(Cart, cart_id)
            assert cart.status == 'finalized'
            assert cart.transaction_id is None
        assert 'Compra guardada' in send.call_args.args[1]

    def test_save_with_movement(self, app, cart_user_id, tg):
        run, _send, _buttons_mock = tg
        with app.app_context():
            cart = svc.start_cart(cart_user_id)
            svc.add_item(cart, 'Pan', Decimal(2500))
            _db.session.commit()
            cart_id = cart.id
        run(_callback(f'cartmov:{cart_id}'))
        with app.app_context():
            cart = _db.session.get(Cart, cart_id)
            assert cart.status == 'finalized'
            tx = _db.session.get(Transaction, cart.transaction_id)
            assert tx.amount == Decimal(2500)
            _db.session.delete(tx)
            _db.session.commit()

    def test_photo_uses_price_tag_extraction_and_offer(self, app, cart_user_id, tg):
        run, _send, buttons = tg
        run(_text('/carrito'))
        with patch('app.telegram.handlers._load_photo_for_ai', return_value=(object(), b'img', 'image/jpeg')), \
                patch('app.telegram.providers.extract_price_tag', return_value={
                    'name': 'Aceite Belmont 1L', 'price': 3990, 'offer_price': 3490,
                    'offer_text': 'Con tarjeta', 'unit': 'unit',
                }):
            run(_photo())
        with app.app_context():
            pending = CartPendingItem.query.filter_by(chat_id=CHAT_ID).one()
            assert pending.source == 'photo'
            assert pending.line_total == Decimal(3990)
            assert pending.alt_line_total == Decimal(3490)
            pending_id = pending.id
        assert f'cartoffer:{pending_id}' in _buttons(buttons)

        run(_callback(f'cartoffer:{pending_id}'))
        with app.app_context():
            cart = svc.get_open_cart(cart_user_id)
            assert cart.total == Decimal(3490)
            assert cart.items[0].source == 'photo'

    def test_photo_without_price_asks_to_retry(self, app, cart_user_id, tg):
        run, send, _buttons_mock = tg
        run(_text('/carrito'))
        with patch('app.telegram.handlers._load_photo_for_ai', return_value=(object(), b'img', 'image/jpeg')), \
                patch('app.telegram.providers.extract_price_tag', side_effect=ValueError('no price')):
            run(_photo())
        assert 'No pude leer el precio' in send.call_args.args[1]
        with app.app_context():
            assert CartPendingItem.query.count() == 0

    def test_old_button_cannot_touch_new_cart(self, app, cart_user_id, tg):
        run, _send, _buttons_mock = tg
        with app.app_context():
            old = svc.start_cart(cart_user_id)
            svc.add_item(old, 'Pan', Decimal(2500))
            svc.finalize(old)
            new = svc.start_cart(cart_user_id)
            svc.add_item(new, 'Leche', Decimal(1290))
            _db.session.commit()
            old_id, new_id = old.id, new.id
        run(_callback(f'cartundo:{old_id}'))
        run(_callback(f'cartdropok:{old_id}'))
        with app.app_context():
            assert _db.session.get(Cart, old_id) is not None
            assert _db.session.get(Cart, new_id).item_count == 1

    def test_discard_cart(self, app, cart_user_id, tg):
        run, _send, _buttons_mock = tg
        with app.app_context():
            cart = svc.start_cart(cart_user_id)
            svc.add_item(cart, 'Pan', Decimal(2500))
            _db.session.commit()
            cart_id = cart.id
        run(_callback(f'cartdrop:{cart_id}'))
        with app.app_context():
            assert _db.session.get(Cart, cart_id) is not None
        run(_callback(f'cartdropok:{cart_id}'))
        with app.app_context():
            assert _db.session.get(Cart, cart_id) is None

    def test_unparseable_text_shows_help(self, app, cart_user_id, tg):
        run, send, _buttons_mock = tg
        run(_text('/carrito'))
        run(_text('hola'))
        assert 'Escribe el producto y su precio' in send.call_args.args[1]


# ── Web ───────────────────────────────────────────────────────────────────────

class TestCartWeb:
    def test_web_flow_and_manual_movement(self, app, cart_user_id):
        c = _login(app)
        assert c.get('/carrito/').status_code == 200

        r = c.post('/carrito/nuevo', data={'store_name': 'Lider'})
        assert r.status_code == 302
        with app.app_context():
            cart_id = svc.get_open_cart(cart_user_id).id

        c.post(f'/carrito/{cart_id}/items', data={'name': 'Leche', 'amount': '1290', 'qty': '2'})
        r = c.get(f'/carrito/{cart_id}')
        assert r.status_code == 200
        assert 'Leche' in r.get_data(as_text=True)

        c.post(f'/carrito/{cart_id}/finalizar', data={'register': '0'})
        with app.app_context():
            cart = _db.session.get(Cart, cart_id)
            assert cart.status == 'finalized' and cart.total == Decimal(2580)
            assert cart.transaction_id is None
            category_id = svc.default_category(cart_user_id).id

        c.post(f'/carrito/{cart_id}/registrar', data={
            'amount': '2490', 'category_id': category_id, 'date': '2026-10-20', 'description': 'Lider',
        })
        with app.app_context():
            cart = _db.session.get(Cart, cart_id)
            tx = _db.session.get(Transaction, cart.transaction_id)
            assert tx.amount == Decimal(2490)
            assert tx.date.isoformat() == '2026-10-20'
            _db.session.delete(tx)
            _db.session.commit()

        assert c.get('/carrito/').status_code == 200

    def test_compare_two_carts(self, app, cart_user_id):
        with app.app_context():
            ids = []
            for price in ('1290', '1390'):
                cart = svc.start_cart(cart_user_id)
                svc.add_item(cart, 'Leche Colún', Decimal(price))
                svc.finalize(cart)
                _db.session.commit()
                ids.append(cart.id)
        c = _login(app)
        r = c.get(f'/carrito/comparar?a={ids[0]}&b={ids[1]}')
        assert r.status_code == 200
        assert '+7.8%' in r.get_data(as_text=True)
        # Con 2+ compras el historial muestra el gráfico de evolución.
        r = c.get('/carrito/')
        assert r.status_code == 200 and 'cartChart' in r.get_data(as_text=True)

    def test_other_user_cannot_see_cart(self, app, cart_user_id, other_user_id):
        with app.app_context():
            cart = svc.start_cart(cart_user_id)
            _db.session.commit()
            cart_id = cart.id
        c = _login(app, OTHER_EMAIL)
        assert c.get(f'/carrito/{cart_id}').status_code == 404
        assert c.post(f'/carrito/{cart_id}/eliminar').status_code == 404
