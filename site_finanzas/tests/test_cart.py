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
        TelegramLink.query.filter_by(chat_id=CHAT_ID).update(
            {'pending_type': None, 'state_updated_at': None, 'usd_enabled': False})
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
            cart = svc.start_cart(cart_user_id, 'Lider')
            svc.add_item(cart, 'Leche', Decimal(1290))
            svc.add_item(cart, 'Yogurt', Decimal(1980), qty=2)
            assert cart.total == Decimal(3270)
            assert cart.item_count == 2
            assert cart.items[1].unit_price == Decimal(990)

            removed = svc.remove_last_item(cart)
            assert removed.name == 'Yogurt'
            assert cart.total == Decimal(1290)
            assert cart.item_count == 1

    def test_store_name_required_to_create(self, app, cart_user_id):
        with app.app_context():
            for bad in (None, '', '   ', '1290', '/carrito'):
                with pytest.raises(svc.CartError) as exc:
                    svc.start_cart(cart_user_id, bad)
                assert exc.value.code == 'store_name_required'
            cart = svc.start_cart(cart_user_id, '  Santa   Isabel ')
            assert cart.store_name == 'Santa Isabel'
            # Con un carrito abierto no se exige nombre: se devuelve el existente.
            assert svc.start_cart(cart_user_id, None).id == cart.id

    def test_only_one_open_cart(self, app, cart_user_id):
        with app.app_context():
            first = svc.start_cart(cart_user_id, 'Lider')
            assert svc.start_cart(cart_user_id, 'Lider').id == first.id

    def test_set_item_qty_keeps_unit_price(self, app, cart_user_id):
        with app.app_context():
            cart = svc.start_cart(cart_user_id, 'Lider')
            item = svc.add_item(cart, 'Yogurt', Decimal(990))
            svc.add_item(cart, 'Pan', Decimal(2500))
            svc.set_item_qty(cart, item, 4)
            assert item.qty == 4 and item.line_total == Decimal(3960)
            assert cart.total == Decimal(6460)
            for bad in (0, -1, 'x', 10000):
                with pytest.raises(svc.CartError):
                    svc.set_item_qty(cart, item, bad)

    def test_rejects_invalid_amounts(self, app, cart_user_id):
        with app.app_context():
            cart = svc.start_cart(cart_user_id, 'Lider')
            for bad in (0, -5, 'abc', Decimal(99999999999)):
                with pytest.raises(svc.CartError):
                    svc.add_item(cart, 'X', bad)

    def test_finalize_save_only_then_register_with_checkout_amount(self, app, cart_user_id):
        with app.app_context():
            cart = svc.start_cart(cart_user_id, 'Lider')
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
            cart = svc.start_cart(cart_user_id, 'Lider')
            svc.add_item(cart, 'Arroz', Decimal(1500))
            tx = svc.finalize(cart, register=True)
            _db.session.commit()
            assert tx.amount == Decimal(1500)
            _db.session.delete(tx)
            _db.session.commit()

    def test_cannot_finalize_empty_cart(self, app, cart_user_id):
        with app.app_context():
            cart = svc.start_cart(cart_user_id, 'Lider')
            with pytest.raises(svc.CartError) as exc:
                svc.finalize(cart)
            assert exc.value.code == 'cart_empty'

    def test_register_requires_owned_expense_category(self, app, cart_user_id, other_user_id):
        with app.app_context():
            foreign = Category(name='Ajena', type='expense', user_id=other_user_id)
            _db.session.add(foreign)
            cart = svc.start_cart(cart_user_id, 'Lider')
            svc.add_item(cart, 'Pan', Decimal(2500))
            svc.finalize(cart)
            with pytest.raises(svc.CartError) as exc:
                svc.register_movement(cart, category_id=foreign.id)
            assert exc.value.code == 'invalid_category'
            _db.session.rollback()

    def test_stale_cart_is_saved_automatically(self, app, cart_user_id):
        with app.app_context():
            cart = svc.start_cart(cart_user_id, 'Lider')
            svc.add_item(cart, 'Pan', Decimal(2500))
            cart.updated_at = datetime.now(timezone.utc) - timedelta(hours=7)
            _db.session.commit()
            closed = svc.close_stale_cart(cart_user_id)
            assert closed is not None and closed.status == 'finalized'
            assert svc.get_open_cart(cart_user_id) is None


# ── Telegram ──────────────────────────────────────────────────────────────────

def _text(text, message_id=None):
    msg = {'chat': {'id': CHAT_ID, 'type': 'private'}, 'text': text}
    if message_id:
        msg['message_id'] = message_id
    return {'message': msg}


def _photo(message_id=None, caption=None):
    msg = {'chat': {'id': CHAT_ID, 'type': 'private'}, 'photo': [{'file_id': 'f1', 'file_size': 10}]}
    if message_id:
        msg['message_id'] = message_id
    if caption is not None:
        msg['caption'] = caption
    return {'message': msg}


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
        run(_text('/carrito Lider'))
        assert 'Carrito iniciado' in buttons.call_args.args[1]

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

    def test_cart_command_asks_store_name(self, app, cart_user_id, tg):
        run, _send, buttons = tg
        run(_text('/carrito'))
        assert '¿En qué supermercado estás?' in buttons.call_args.args[1]
        assert 'cartnostart:0' in _buttons(buttons)
        with app.app_context():
            assert svc.get_open_cart(cart_user_id) is None
            assert TelegramLink.query.filter_by(chat_id=CHAT_ID).one().pending_type == 'cartname'

        run(_text('Lider Vespucio'))
        assert 'Carrito iniciado en Lider Vespucio' in buttons.call_args.args[1]
        with app.app_context():
            assert svc.get_open_cart(cart_user_id).store_name == 'Lider Vespucio'
            assert TelegramLink.query.filter_by(chat_id=CHAT_ID).one().pending_type is None

        # Lo siguiente ya es un producto.
        run(_text('Leche 1290'))
        with app.app_context():
            assert CartPendingItem.query.filter_by(chat_id=CHAT_ID).one().name == 'Leche'

    def test_store_name_rejects_photo_and_numbers(self, app, cart_user_id, tg):
        run, _send, buttons = tg
        run(_text('/carrito'))
        run(_photo())
        assert 'Necesito el nombre del supermercado' in buttons.call_args.args[1]
        run(_text('1290'))
        assert 'Necesito el nombre del supermercado' in buttons.call_args.args[1]
        with app.app_context():
            assert svc.get_open_cart(cart_user_id) is None
        run(_text('Jumbo'))
        with app.app_context():
            assert svc.get_open_cart(cart_user_id).store_name == 'Jumbo'

    def test_recent_store_button(self, app, cart_user_id, tg):
        run, _send, buttons = tg
        with app.app_context():
            previous = svc.start_cart(cart_user_id, 'Unimarc')
            svc.add_item(previous, 'Pan', Decimal(2500))
            svc.finalize(previous)
            _db.session.commit()
            previous_id = previous.id
        run(_text('/carrito'))
        assert f'cartstore:{previous_id}' in _buttons(buttons)
        run(_callback(f'cartstore:{previous_id}'))
        with app.app_context():
            cart = svc.get_open_cart(cart_user_id)
            assert cart.store_name == 'Unimarc' and cart.id != previous_id

    def test_new_store_button_with_recent_stores(self, app, cart_user_id, tg):
        run, _send, buttons = tg
        with app.app_context():
            previous = svc.start_cart(cart_user_id, 'Unimarc')
            svc.add_item(previous, 'Pan', Decimal(2500))
            svc.finalize(previous)
            _db.session.commit()
        run(_text('/carrito'))
        assert 'Nuevo supermercado' in buttons.call_args.args[1]
        assert 'cartnewstore:0' in _buttons(buttons)

        run(_callback('cartnewstore:0'))
        assert 'Escribe el nombre del supermercado' in buttons.call_args.args[1]
        assert _buttons(buttons) == ['cartnostart:0']
        run(_text('Tottus'))
        with app.app_context():
            assert svc.get_open_cart(cart_user_id).store_name == 'Tottus'

    def test_no_new_store_button_without_recent_stores(self, app, cart_user_id, tg):
        run, _send, buttons = tg
        run(_text('/carrito'))
        assert _buttons(buttons) == ['cartnostart:0']

    def test_cancel_store_prompt(self, app, cart_user_id, tg):
        run, send, _buttons_mock = tg
        run(_text('/carrito'))
        run(_callback('cartnostart:0'))
        assert 'No se creó el carrito' in send.call_args.args[1]
        with app.app_context():
            assert svc.get_open_cart(cart_user_id) is None
            assert TelegramLink.query.filter_by(chat_id=CHAT_ID).one().pending_type is None

    def test_expired_store_prompt_does_not_leak_into_usd_flow(self, app, cart_user_id, tg):
        run, _send, _buttons_mock = tg
        with app.app_context():
            link = TelegramLink.query.filter_by(chat_id=CHAT_ID).one()
            link.usd_enabled = True
            link.pending_type = 'cartname'
            link.state_updated_at = datetime.now(timezone.utc) - timedelta(hours=2)
            _db.session.commit()
        with patch('app.telegram.handlers.send_message_with_buttons') as type_buttons:
            run(_text('Café 3000'))
        # La espera venció: se pregunta Principal/USD en vez de tomarlo como supermercado.
        assert 'settype:principal' in _buttons(type_buttons)
        with app.app_context():
            assert svc.get_open_cart(cart_user_id) is None
            assert TelegramLink.query.filter_by(chat_id=CHAT_ID).one().pending_type is None

    def test_save_with_movement(self, app, cart_user_id, tg):
        run, _send, _buttons_mock = tg
        with app.app_context():
            cart = svc.start_cart(cart_user_id, 'Lider')
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
        run(_text('/carrito Lider'))
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
        run(_text('/carrito Lider'))
        with patch('app.telegram.handlers._load_photo_for_ai', return_value=(object(), b'img', 'image/jpeg')), \
                patch('app.telegram.providers.extract_price_tag', side_effect=ValueError('no price')):
            run(_photo())
        assert 'No pude leer el precio' in send.call_args.args[1]
        with app.app_context():
            assert CartPendingItem.query.count() == 0

    def test_old_button_cannot_touch_new_cart(self, app, cart_user_id, tg):
        run, _send, _buttons_mock = tg
        with app.app_context():
            old = svc.start_cart(cart_user_id, 'Lider')
            svc.add_item(old, 'Pan', Decimal(2500))
            svc.finalize(old)
            new = svc.start_cart(cart_user_id, 'Lider')
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
            cart = svc.start_cart(cart_user_id, 'Lider')
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
        run(_text('/carrito Lider'))
        run(_text('hola'))
        assert 'Escribe el producto y su precio' in send.call_args.args[1]

    def test_double_tap_on_add_adds_once(self, app, cart_user_id, tg):
        run, _send, _buttons_mock = tg
        run(_text('/carrito Lider'))
        run(_text('Leche 1290'))
        with app.app_context():
            pending_id = CartPendingItem.query.filter_by(chat_id=CHAT_ID).one().id
        run(_callback(f'cartok:{pending_id}'))
        run(_callback(f'cartok:{pending_id}'))
        with app.app_context():
            assert svc.get_open_cart(cart_user_id).item_count == 1


class TestTelegramCartCancel:
    def test_cancel_command_deletes_empty_cart(self, app, cart_user_id, tg):
        run, send, _buttons_mock = tg
        run(_text('/carrito Lider'))
        run(_text('/cancelar'))
        assert 'Carrito descartado' in send.call_args.args[1]
        with app.app_context():
            assert svc.get_open_cart(cart_user_id) is None
            assert Cart.query.filter_by(user_id=cart_user_id).count() == 0

    def test_cancel_command_asks_before_discarding_products(self, app, cart_user_id, tg):
        run, _send, buttons = tg
        with app.app_context():
            cart = svc.start_cart(cart_user_id, 'Lider')
            svc.add_item(cart, 'Pan', Decimal(2500))
            _db.session.commit()
            cart_id = cart.id
        run(_text('/cancel'))
        assert '¿Descartar el carrito con 1 productos' in buttons.call_args.args[1]
        assert _buttons(buttons) == [f'cartdropok:{cart_id}', f'cartkeep:{cart_id}']

        run(_callback(f'cartkeep:{cart_id}'))
        assert 'Total del carrito' in buttons.call_args.args[1]
        assert f'cartdrop:{cart_id}' in _buttons(buttons)
        with app.app_context():
            assert _db.session.get(Cart, cart_id) is not None

        run(_callback(f'cartdropok:{cart_id}'))
        with app.app_context():
            assert _db.session.get(Cart, cart_id) is None

    def test_finish_empty_cart_offers_cancel(self, app, cart_user_id, tg):
        run, send, buttons = tg
        with app.app_context():
            cart_id = svc.start_cart(cart_user_id, 'Lider').id
            _db.session.commit()
        run(_callback(f'cartend:{cart_id}'))
        assert 'El carrito está vacío' in buttons.call_args.args[1]
        assert _buttons(buttons) == [f'cartdrop:{cart_id}']
        run(_callback(f'cartdrop:{cart_id}'))
        assert 'Carrito descartado' in send.call_args.args[1]
        with app.app_context():
            assert _db.session.get(Cart, cart_id) is None

    def test_cancel_while_asking_store_name(self, app, cart_user_id, tg):
        run, send, _buttons_mock = tg
        run(_text('/carrito'))
        run(_text('/cancelar'))
        assert 'No se creó el carrito' in send.call_args.args[1]
        with app.app_context():
            assert TelegramLink.query.filter_by(chat_id=CHAT_ID).one().pending_type is None

    def test_cancel_without_cart(self, app, cart_user_id, tg):
        run, send, _buttons_mock = tg
        run(_text('/cancelar'))
        assert 'No tienes un carrito abierto' in send.call_args.args[1]

    def test_old_cancel_button_shows_open_cart(self, app, cart_user_id, tg):
        run, send, buttons = tg
        with app.app_context():
            cart_id = svc.start_cart(cart_user_id, 'Lider').id
            _db.session.commit()
        send.reset_mock()
        run(_callback('cartnostart:0'))
        assert not any('No se creó' in call.args[1] for call in send.call_args_list)
        assert 'Tienes un carrito en curso' in buttons.call_args.args[1]
        with app.app_context():
            assert _db.session.get(Cart, cart_id) is not None

    def test_help_explains_how_to_leave(self, app, cart_user_id, tg):
        run, send, _buttons_mock = tg
        run(_text('/carrito Lider'))
        run(_text('Hola'))
        assert '/cancelar para descartar el carrito' in send.call_args.args[1]


def _item_id(app, cart_id):
    with app.app_context():
        return _db.session.get(Cart, cart_id).items[-1].id


def _read_label(result):
    return (patch('app.telegram.handlers._load_photo_for_ai', return_value=(object(), b'img', 'image/jpeg')),
            patch('app.telegram.providers.extract_price_tag', return_value=result))


class TestTelegramCartQuantity:
    def test_caption_quantity(self):
        from app.telegram.cart_flow import caption_qty
        for caption in ('3', 'x3', '3x', ' 3 unidades ', '×3'):
            assert caption_qty(caption) == 3
        for caption in (None, '', 'hola', '0', 'leche 3 litros', '1000'):
            assert caption_qty(caption) == 1

    def test_auto_photo_with_caption_adds_units(self, app, cart_user_id, tg):
        run, _send, buttons = tg
        _start_cart(run, buttons, 'auto')
        loader, extract = _read_label({'name': 'Yogurt', 'price': 990, 'offer_price': 890, 'unit': 'unit'})
        with loader, extract:
            run(_photo(message_id=60, caption='3'))
        text = buttons.call_args.args[1]
        assert '3 × $990' in text and 'Total del carrito: $2.970' in text
        assert 'Oferta: <b>$2.670</b>' in text
        with app.app_context():
            item = svc.get_open_cart(cart_user_id).items[0]
            assert item.qty == 3 and item.unit_price == Decimal(990) and item.line_total == Decimal(2970)

    def test_manual_photo_with_caption_shows_units_on_card(self, app, cart_user_id, tg):
        run, _send, buttons = tg
        run(_text('/carrito Lider'))
        loader, extract = _read_label({'name': 'Yogurt', 'price': 990, 'unit': 'unit'})
        with loader, extract:
            run(_photo(caption='x2'))
        assert '2 × $990' in buttons.call_args.args[1]
        with app.app_context():
            pending = CartPendingItem.query.filter_by(chat_id=CHAT_ID).one()
            assert pending.qty == 2 and pending.line_total == Decimal(1980)

    def test_quantity_button_changes_last_item(self, app, cart_user_id, tg):
        run, _send, buttons = tg
        _start_cart(run, buttons, 'auto')
        run(_text('Leche 1290', message_id=70))
        with app.app_context():
            cart_id = svc.get_open_cart(cart_user_id).id
        item_id = _item_id(app, cart_id)

        run(_callback(f'cartqty:{item_id}'))
        assert '¿Cuántas unidades de <b>Leche</b>' in buttons.call_args.args[1]
        assert _buttons(buttons) == [f'cartq{n}:{item_id}' for n in (1, 2, 3, 4, 5, 6)] + [f'cartqmore:{item_id}']

        run(_callback(f'cartq3:{item_id}'))
        assert '3 × Leche' in buttons.call_args.args[1] and 'Total del carrito: $3.870' in buttons.call_args.args[1]

        run(_callback(f'cartqmore:{item_id}'))
        assert _buttons(buttons) == [f'cartq{n}:{item_id}' for n in (7, 8, 9, 10, 12, 15, 20, 24)]
        run(_callback(f'cartq12:{item_id}'))
        with app.app_context():
            cart = _db.session.get(Cart, cart_id)
            assert cart.items[0].qty == 12 and cart.total == Decimal(15480)

    def test_quantity_button_of_closed_cart_does_nothing(self, app, cart_user_id, tg):
        run, send, _buttons_mock = tg
        with app.app_context():
            cart = svc.start_cart(cart_user_id, 'Lider')
            item = svc.add_item(cart, 'Pan', Decimal(2500))
            svc.finalize(cart)
            _db.session.commit()
            item_id, cart_id = item.id, cart.id
        run(_callback(f'cartq2:{item_id}'))
        assert 'ya no está en un carrito abierto' in send.call_args.args[1]
        with app.app_context():
            assert _db.session.get(Cart, cart_id).total == Decimal(2500)


def _start_cart(run, buttons, mode):
    """Crea el carrito por el bot y elige el modo de ingreso."""
    run(_text('/carrito Lider'))
    choices = _buttons(buttons)
    assert len(choices) == 2 and choices[0].startswith('cartmanual:') and choices[1].startswith('cartauto:')
    run(_callback(choices[1] if mode == 'auto' else choices[0]))


class TestTelegramCartModes:
    def test_mode_defaults_to_manual_until_chosen(self, app, cart_user_id, tg):
        run, send, buttons = tg
        run(_text('/carrito Lider'))
        assert '¿Cómo quieres agregar los productos?' in buttons.call_args.args[1]
        with app.app_context():
            assert svc.get_open_cart(cart_user_id).entry_mode == 'manual'
        run(_text('Leche 1290'))
        with app.app_context():
            assert CartPendingItem.query.filter_by(chat_id=CHAT_ID).count() == 1
            cart_id = svc.get_open_cart(cart_user_id).id

        run(_callback(f'cartauto:{cart_id}'))
        assert 'Modo automático' in send.call_args.args[1]
        with app.app_context():
            assert _db.session.get(Cart, cart_id).entry_mode == 'auto'

    def test_auto_mode_adds_text_without_confirmation(self, app, cart_user_id, tg):
        run, _send, buttons = tg
        _start_cart(run, buttons, 'auto')

        run(_text('Leche entera 1290', message_id=10))
        text = buttons.call_args.args[1]
        assert 'Leche entera' in text and 'Total del carrito: $1.290' in text
        with app.app_context():
            cart = svc.get_open_cart(cart_user_id)
            cart_id = cart.id
            assert CartPendingItem.query.count() == 0
            assert cart.items[0].client_request_id == 'tg:10'
        item_id = _item_id(app, cart_id)
        assert _buttons(buttons) == [f'cartmore:{cart_id}', f'cartundo:{cart_id}', f'cartqty:{item_id}',
                                     f'cartend:{cart_id}', f'cartdrop:{cart_id}']

        run(_text('2 x 990 yogurt', message_id=11))
        assert 'Total del carrito: $3.270' in buttons.call_args.args[1]
        assert '2 productos' in buttons.call_args.args[1]

        run(_callback(f'cartundo:{cart_id}'))
        with app.app_context():
            cart = _db.session.get(Cart, cart_id)
            assert cart.total == Decimal(1290) and cart.item_count == 1

    def test_auto_mode_photo_adds_regular_price_and_reports_offer(self, app, cart_user_id, tg):
        run, _send, buttons = tg
        _start_cart(run, buttons, 'auto')
        with patch('app.telegram.handlers._load_photo_for_ai', return_value=(object(), b'img', 'image/jpeg')), \
                patch('app.telegram.providers.extract_price_tag', return_value={
                    'name': 'Aceite Belmont 1L', 'price': 3990, 'offer_price': 3490,
                    'offer_text': 'Con tarjeta', 'unit': 'unit',
                }):
            run(_photo(message_id=20))
        text = buttons.call_args.args[1]
        assert 'Oferta: <b>$3.490</b> — Con tarjeta' in text
        assert 'Total del carrito: $3.990' in text
        with app.app_context():
            item = svc.get_open_cart(cart_user_id).items[0]
            assert item.source == 'photo' and item.line_total == Decimal(3990)

    def test_auto_mode_ignores_retried_message(self, app, cart_user_id, tg):
        run, _send, buttons = tg
        _start_cart(run, buttons, 'auto')
        with patch('app.telegram.handlers._load_photo_for_ai', return_value=(object(), b'img', 'image/jpeg')), \
                patch('app.telegram.providers.extract_price_tag', return_value={
                    'name': 'Pan', 'price': 2500, 'unit': 'unit',
                }) as extract:
            run(_photo(message_id=30))
            run(_photo(message_id=30))
        assert extract.call_count == 1
        run(_text('Leche 1290', message_id=31))
        run(_text('Leche 1290', message_id=31))
        with app.app_context():
            cart = svc.get_open_cart(cart_user_id)
            assert cart.item_count == 2 and cart.total == Decimal(3790)

    def test_auto_mode_without_price_adds_nothing(self, app, cart_user_id, tg):
        run, send, buttons = tg
        _start_cart(run, buttons, 'auto')
        run(_text('hola', message_id=40))
        assert 'Escribe el producto y su precio' in send.call_args.args[1]
        with app.app_context():
            assert svc.get_open_cart(cart_user_id).item_count == 0

    def test_resume_offers_switching_mode(self, app, cart_user_id, tg):
        run, _send, buttons = tg
        _start_cart(run, buttons, 'auto')
        run(_text('/carrito'))
        assert 'modo ⚡ automático' in buttons.call_args.args[1]
        with app.app_context():
            cart_id = svc.get_open_cart(cart_user_id).id
        assert f'cartmanual:{cart_id}' in _buttons(buttons)
        run(_callback(f'cartmanual:{cart_id}'))
        run(_text('Leche 1290', message_id=50))
        with app.app_context():
            assert CartPendingItem.query.filter_by(chat_id=CHAT_ID).count() == 1
            assert _db.session.get(Cart, cart_id).item_count == 0

    def test_mode_button_of_closed_cart_does_nothing(self, app, cart_user_id, tg):
        run, send, _buttons_mock = tg
        with app.app_context():
            old = svc.start_cart(cart_user_id, 'Lider')
            svc.add_item(old, 'Pan', Decimal(2500))
            svc.finalize(old)
            _db.session.commit()
            old_id = old.id
        run(_callback(f'cartauto:{old_id}'))
        assert 'ya no está activo' in send.call_args.args[1]
        with app.app_context():
            assert _db.session.get(Cart, old_id).entry_mode == 'manual'


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

    def test_web_store_name_required_and_editable(self, app, cart_user_id):
        c = _login(app)
        c.post('/carrito/nuevo', data={'store_name': ''})
        with app.app_context():
            assert svc.get_open_cart(cart_user_id) is None
        c.post('/carrito/nuevo', data={'store_name': 'Tottus'})
        with app.app_context():
            cart_id = svc.get_open_cart(cart_user_id).id
        c.post(f'/carrito/{cart_id}/supermercado', data={'store_name': ''})
        with app.app_context():
            assert _db.session.get(Cart, cart_id).store_name == 'Tottus'
        c.post(f'/carrito/{cart_id}/supermercado', data={'store_name': 'Tottus Kennedy'})
        with app.app_context():
            assert _db.session.get(Cart, cart_id).store_name == 'Tottus Kennedy'

        # Carritos antiguos sin nombre muestran el aviso y el formulario para corregirlo.
        with app.app_context():
            _db.session.get(Cart, cart_id).store_name = None
            _db.session.commit()
        html_page = c.get(f'/carrito/{cart_id}').get_data(as_text=True)
        assert 'Sin supermercado' in html_page and f'/carrito/{cart_id}/supermercado' in html_page

    def test_history_lists_product_names_and_popup_entry(self, app, cart_user_id):
        with app.app_context():
            cart = svc.start_cart(cart_user_id, 'Lider')
            svc.add_item(cart, 'Leche Colún 1L', Decimal(1290))
            svc.add_item(cart, 'Pan amasado', Decimal(2580), qty=2)
            svc.finalize(cart)
            _db.session.commit()
            cart_id = cart.id
        c = _login(app)
        page = c.get('/carrito/').get_data(as_text=True)
        # Nombres en la columna Productos y detalle desplegable con cantidad × precio.
        assert 'Leche Colún 1L, Pan amasado' in page
        assert f'id="cart-items-{cart_id}"' in page
        assert '2 × $1.290' in page
        # El acceso está en el popup de Movimientos, no como enlace propio del menú.
        assert 'Compras de supermercado e historial' in page
        assert 'Mi Carrito' not in page

    def test_compare_two_carts(self, app, cart_user_id):
        with app.app_context():
            ids = []
            for price in ('1290', '1390'):
                cart = svc.start_cart(cart_user_id, 'Lider')
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
            cart = svc.start_cart(cart_user_id, 'Lider')
            _db.session.commit()
            cart_id = cart.id
        c = _login(app, OTHER_EMAIL)
        assert c.get(f'/carrito/{cart_id}').status_code == 404
        assert c.post(f'/carrito/{cart_id}/eliminar').status_code == 404
