"""Flujo de "Mi Carrito" en el bot de Telegram.

Mientras el usuario tiene un carrito abierto, todo texto o foto que envía se
interpreta como un producto: se muestra una tarjeta de confirmación y, al
confirmar, se agrega al carrito y se informa el total acumulado. El carrito vive
en BD (no en memoria del proceso), así que sobrevive a reinicios del servidor.

Los callbacks llevan el id del carrito o del producto pendiente y siempre se
validan contra el usuario vinculado al chat, para que un botón viejo no actúe
sobre otro carrito.
"""
import html
import logging
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from flask import request as flask_request

from app import db
from app.audit.events import CART_FINALIZE, CART_MOVEMENT
from app.audit.logger import log_event
from app.cart import service as cart_svc
from app.models import CartPendingItem, Category, TelegramLink, User
from app.money import format_money_for_user, parse_amount_for_user
from app.telegram.messages import t
from app.telegram.service import (
    answer_callback_query,
    edit_message_reply_markup,
    send_message,
    send_message_with_buttons,
)

_log = logging.getLogger(__name__)

_PENDING_TTL_SECONDS = 3600
_SUMMARY_MAX_LINES = 40
_AMOUNT_TOKEN_MAX_LEN = 20

# Números con separadores de miles/decimales (p. ej. 1.290, 1.290,50, 12500).
_AMOUNT_RE = re.compile(r'\d+(?:[.,]\d+)*')
# Cantidad tipo "2 x", "3x", "2 ×" seguida de un número: "2 x 990 yogurt", "yogurt 2x990".
_QTY_RE = re.compile(r'(?<![\d.,])(\d{1,3})\s*[x×*]\s*(?=\d)', re.IGNORECASE)

CART_COMMANDS = ('/carrito', '/cart')
CALLBACK_PREFIX = 'cart'


def _lang_of(user) -> str | None:
    return user.language if user else None


def _money(amount, user) -> str:
    return format_money_for_user(amount or 0, user)


def _fmt_qty(qty) -> str:
    return f"{Decimal(qty).normalize():f}"


def is_cart_command(text: str) -> bool:
    command = (text or '').split(maxsplit=1)[0].split('@', 1)[0].lower() if text else ''
    return command in CART_COMMANDS


# ── Entradas desde el dispatcher ──────────────────────────────────────────────

def active_cart(chat_id: int, user: User):
    """Carrito abierto del usuario, cerrando antes uno inactivo (y avisando)."""
    lang = _lang_of(user)
    stale = cart_svc.close_stale_cart(user.id)
    if stale is not None:
        CartPendingItem.query.filter_by(cart_id=stale.id).delete()
        db.session.commit()
        send_message(chat_id, t('cart_stale_saved', lang).format(total=_money(stale.total, user)))
        return None
    db.session.commit()
    return cart_svc.get_open_cart(user.id)


def start(chat_id: int, user: User) -> None:
    """Inicia un carrito o recuerda el que está en curso."""
    lang = _lang_of(user)
    cart = active_cart(chat_id, user)
    if cart is not None:
        send_message_with_buttons(
            chat_id,
            t('cart_resumed', lang).format(total=_money(cart.total, user), count=cart.item_count),
            _cart_buttons(cart, lang),
        )
        return
    cart_svc.start_cart(user.id, source='telegram')
    link = TelegramLink.query.filter_by(chat_id=chat_id, enabled=True).first()
    if link:
        # El carrito reemplaza la elección Principal/USD pendiente.
        link.pending_type = None
        link.state_updated_at = None
    db.session.commit()
    send_message(chat_id, t('cart_started', lang))


def handle_text(chat_id: int, user: User, cart, text: str) -> None:
    lang = _lang_of(user)
    text = text[:4096]

    qty = Decimal(1)
    qty_match = _QTY_RE.search(text)
    if qty_match:
        qty = Decimal(qty_match.group(1))
        text = (text[:qty_match.start()] + ' ' + text[qty_match.end():]).strip()

    matches = list(_AMOUNT_RE.finditer(text))
    if not matches or qty <= 0:
        send_message(chat_id, t('cart_text_help', lang))
        return
    last = matches[-1]
    token = last.group(0)
    if len(token) > _AMOUNT_TOKEN_MAX_LEN:
        send_message(chat_id, t('cart_text_help', lang))
        return
    try:
        amount = parse_amount_for_user(token, user)
    except ValueError:
        send_message(chat_id, t('cart_text_help', lang))
        return
    if amount <= 0 or amount * qty > cart_svc.MAX_AMOUNT:
        send_message(chat_id, t('cart_text_help', lang))
        return

    name = (text[:last.start()] + text[last.end():]).strip(' -–—,.:$')
    # Con cantidad, el monto escrito es el precio unitario; sin ella, es el total de la línea.
    _save_pending(chat_id, user, cart, name=name, line_total=amount * qty, qty=qty, source='text')


def handle_photo(chat_id: int, user: User, cart, photos: list) -> None:
    from app.telegram.handlers import _load_photo_for_ai
    from app.telegram.providers import extract_price_tag

    lang = _lang_of(user)
    loaded = _load_photo_for_ai(chat_id, user.id, photos, lang)
    if loaded is None:
        return
    ai_config, image_bytes, mime_type = loaded

    try:
        result = extract_price_tag(ai_config, image_bytes, mime_type)
    except ValueError as exc:
        _log.warning("Price tag extraction error for chat_id=%s: %s", chat_id, exc)
        send_message(chat_id, t('cart_price_not_found', lang))
        return
    except Exception as exc:
        _log.error("Price tag extraction unexpected error for chat_id=%s: %s", chat_id, exc, exc_info=True)
        send_message(chat_id, t('cart_price_not_found', lang))
        return

    price = _coerce_amount(result.get('price'), user)
    offer = _coerce_amount(result.get('offer_price'), user)
    if price is None and offer is not None:
        price, offer = offer, None
    if price is None:
        send_message(chat_id, t('cart_price_not_found', lang))
        return
    if offer is not None and offer >= price:
        offer = None

    note = None
    if (result.get('unit') or '').lower() == 'kg':
        note = t('cart_note_per_kg', lang)
    offer_text = result.get('offer_text') if offer is not None else None

    _save_pending(chat_id, user, cart, name=result.get('name') or '', line_total=price,
                  qty=Decimal(1), source='photo', alt_line_total=offer,
                  note=note, offer_text=offer_text)


def _coerce_amount(value, user) -> Decimal | None:
    """Convierte el precio devuelto por la IA (número o texto) a Decimal válido."""
    if value is None or isinstance(value, bool):
        return None
    try:
        if isinstance(value, str):
            amount = parse_amount_for_user(value, user)
        else:
            amount = Decimal(str(value))
    except (ValueError, InvalidOperation):
        return None
    if not amount.is_finite() or amount <= 0 or amount > cart_svc.MAX_AMOUNT:
        return None
    return amount.quantize(Decimal('0.01'))


# ── Producto pendiente ────────────────────────────────────────────────────────

def _save_pending(chat_id: int, user: User, cart, *, name: str, line_total: Decimal, qty: Decimal,
                  source: str, alt_line_total: Decimal | None = None, note: str | None = None,
                  offer_text: str | None = None) -> None:
    lang = _lang_of(user)
    CartPendingItem.query.filter_by(chat_id=chat_id).delete()
    pending = CartPendingItem(
        chat_id=chat_id,
        user_id=user.id,
        cart_id=cart.id,
        name=(name or '').strip()[:200] or t('cart_default_item', lang),
        qty=qty,
        line_total=Decimal(line_total).quantize(Decimal('0.01')),
        alt_line_total=alt_line_total,
        note=(offer_text or '')[:200] or None,
        source=source,
    )
    db.session.add(pending)
    db.session.commit()

    extra = ''
    if qty != 1:
        extra += t('cart_qty_line', lang).format(
            qty=_fmt_qty(qty), unit=_money(pending.line_total / qty, user))
    if alt_line_total is not None:
        offer_suffix = f" — {html.escape(pending.note)}" if pending.note else ''
        extra += t('cart_offer_line', lang).format(amount=_money(alt_line_total, user), text=offer_suffix)
    if note:
        extra += t('cart_note_line', lang).format(note=html.escape(note))

    text = t('cart_item_card', lang).format(
        name=html.escape(pending.name), amount=_money(pending.line_total, user), extra=extra)
    first_row = [{'text': t('btn_cart_add', lang), 'callback_data': f'cartok:{pending.id}'}]
    if alt_line_total is not None:
        first_row.append({'text': t('btn_cart_add_offer', lang).format(amount=_money(alt_line_total, user)),
                          'callback_data': f'cartoffer:{pending.id}'})
    buttons = [
        first_row,
        [
            {'text': t('btn_cart_fix', lang), 'callback_data': f'cartfix:{pending.id}'},
            {'text': t('btn_cart_skip', lang), 'callback_data': f'cartskip:{pending.id}'},
        ],
    ]
    send_message_with_buttons(chat_id, text, buttons)


def _cart_buttons(cart, lang) -> list:
    return [
        [
            {'text': t('btn_cart_more', lang), 'callback_data': f'cartmore:{cart.id}'},
            {'text': t('btn_cart_undo', lang), 'callback_data': f'cartundo:{cart.id}'},
        ],
        [{'text': t('btn_cart_finish', lang), 'callback_data': f'cartend:{cart.id}'}],
    ]


# ── Callbacks ─────────────────────────────────────────────────────────────────

def handles(data: str) -> bool:
    return data.startswith(CALLBACK_PREFIX)


def handle_callback(chat_id: int, message_id: int, callback_id: str, data: str) -> None:
    action, _, raw_id = data.partition(':')
    try:
        obj_id = int(raw_id)
    except ValueError:
        answer_callback_query(callback_id)
        return

    link = TelegramLink.query.filter_by(chat_id=chat_id, enabled=True).first()
    user = db.session.get(User, link.user_id) if link else None
    if user is None:
        answer_callback_query(callback_id)
        return

    handler = _CALLBACKS.get(action)
    if handler is None:
        answer_callback_query(callback_id)
        return
    handler(chat_id, message_id, callback_id, user, obj_id)


def _pending_or_expire(chat_id, message_id, callback_id, user, pending_id):
    lang = _lang_of(user)
    pending = CartPendingItem.query.filter_by(id=pending_id, chat_id=chat_id, user_id=user.id).first()
    expired = pending is None or pending.cart is None or pending.cart.status != 'open'
    if pending is not None and not expired:
        created_at = pending.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        expired = (datetime.now(timezone.utc) - created_at).total_seconds() > _PENDING_TTL_SECONDS
    if expired:
        if pending is not None:
            db.session.delete(pending)
            db.session.commit()
        answer_callback_query(callback_id, t('toast_expired', lang))
        edit_message_reply_markup(chat_id, message_id, {})
        send_message(chat_id, t('cart_not_active', lang))
        return None
    return pending


def _open_cart_or_expire(chat_id, message_id, callback_id, user, cart_id):
    cart = cart_svc.get_user_cart(user.id, cart_id)
    if cart is None or cart.status != 'open':
        lang = _lang_of(user)
        answer_callback_query(callback_id, t('toast_expired', lang))
        edit_message_reply_markup(chat_id, message_id, {})
        send_message(chat_id, t('cart_not_active', lang))
        return None
    return cart


def _confirm(chat_id, message_id, callback_id, user, pending_id, use_offer=False):
    lang = _lang_of(user)
    pending = _pending_or_expire(chat_id, message_id, callback_id, user, pending_id)
    if pending is None:
        return
    cart = pending.cart
    line_total = pending.alt_line_total if use_offer and pending.alt_line_total else pending.line_total
    try:
        item = cart_svc.add_item(cart, pending.name, line_total, qty=pending.qty, source=pending.source)
    except cart_svc.CartError as exc:
        db.session.rollback()
        answer_callback_query(callback_id, t('toast_error', lang))
        send_message(chat_id, t('cart_full' if exc.code == 'cart_full' else 'cart_text_help', lang))
        return
    db.session.delete(pending)
    db.session.commit()

    answer_callback_query(callback_id, t('toast_saved', lang))
    edit_message_reply_markup(chat_id, message_id, {})
    send_message_with_buttons(
        chat_id,
        t('cart_added', lang).format(name=html.escape(item.name), amount=_money(item.line_total, user),
                                     total=_money(cart.total, user), count=cart.item_count),
        _cart_buttons(cart, lang),
    )


def _confirm_offer(chat_id, message_id, callback_id, user, pending_id):
    _confirm(chat_id, message_id, callback_id, user, pending_id, use_offer=True)


def _discard_pending(chat_id, message_id, callback_id, user, pending_id, fix=False):
    lang = _lang_of(user)
    pending = CartPendingItem.query.filter_by(id=pending_id, chat_id=chat_id, user_id=user.id).first()
    cart = pending.cart if pending else None
    if pending is not None:
        db.session.delete(pending)
        db.session.commit()
    answer_callback_query(callback_id, t('toast_cancelled', lang))
    edit_message_reply_markup(chat_id, message_id, {})
    if fix:
        send_message(chat_id, t('cart_fix_prompt', lang))
    elif cart is not None and cart.status == 'open':
        send_message_with_buttons(
            chat_id,
            t('cart_item_skipped', lang) + '\n\n' + t('cart_status', lang).format(
                total=_money(cart.total, user), count=cart.item_count),
            _cart_buttons(cart, lang),
        )
    else:
        send_message(chat_id, t('cart_item_skipped', lang))


def _skip(chat_id, message_id, callback_id, user, pending_id):
    _discard_pending(chat_id, message_id, callback_id, user, pending_id)


def _fix(chat_id, message_id, callback_id, user, pending_id):
    _discard_pending(chat_id, message_id, callback_id, user, pending_id, fix=True)


def _more(chat_id, message_id, callback_id, user, cart_id):
    if _open_cart_or_expire(chat_id, message_id, callback_id, user, cart_id) is None:
        return
    answer_callback_query(callback_id)
    edit_message_reply_markup(chat_id, message_id, {})
    send_message(chat_id, t('cart_prompt_next', _lang_of(user)))


def _undo(chat_id, message_id, callback_id, user, cart_id):
    lang = _lang_of(user)
    cart = _open_cart_or_expire(chat_id, message_id, callback_id, user, cart_id)
    if cart is None:
        return
    item = cart_svc.remove_last_item(cart)
    db.session.commit()
    answer_callback_query(callback_id)
    edit_message_reply_markup(chat_id, message_id, {})
    if item is None:
        send_message(chat_id, t('cart_nothing_to_undo', lang))
        return
    send_message_with_buttons(
        chat_id,
        t('cart_undone', lang).format(name=html.escape(item.name), amount=_money(item.line_total, user))
        + '\n\n' + t('cart_status', lang).format(total=_money(cart.total, user), count=cart.item_count),
        _cart_buttons(cart, lang),
    )


def _finish(chat_id, message_id, callback_id, user, cart_id):
    """Muestra el resumen y las dos formas de guardar el carrito."""
    lang = _lang_of(user)
    cart = _open_cart_or_expire(chat_id, message_id, callback_id, user, cart_id)
    if cart is None:
        return
    answer_callback_query(callback_id)
    edit_message_reply_markup(chat_id, message_id, {})
    if not cart.items:
        send_message(chat_id, t('cart_empty_finish', lang))
        return

    lines = [
        t('cart_line', lang).format(
            name=html.escape(i.name if i.qty == 1 else f"{_fmt_qty(i.qty)} × {i.name}"),
            amount=_money(i.line_total, user))
        for i in cart.items[:_SUMMARY_MAX_LINES]
    ]
    if len(cart.items) > _SUMMARY_MAX_LINES:
        lines.append(t('cart_more_lines', lang).format(n=len(cart.items) - _SUMMARY_MAX_LINES))

    text = t('cart_finish_summary', lang).format(
        lines='\n'.join(lines), total=_money(cart.total, user), count=cart.item_count)
    buttons = [
        [{'text': t('btn_cart_save_movement', lang), 'callback_data': f'cartmov:{cart.id}'}],
        [{'text': t('btn_cart_save_only', lang), 'callback_data': f'cartsave:{cart.id}'}],
        [
            {'text': t('btn_cart_continue', lang), 'callback_data': f'cartmore:{cart.id}'},
            {'text': t('btn_cart_discard', lang), 'callback_data': f'cartdrop:{cart.id}'},
        ],
    ]
    send_message_with_buttons(chat_id, text, buttons)


def _save(chat_id, message_id, callback_id, user, cart_id, register=False):
    lang = _lang_of(user)
    cart = _open_cart_or_expire(chat_id, message_id, callback_id, user, cart_id)
    if cart is None:
        return
    CartPendingItem.query.filter_by(cart_id=cart.id).delete()
    try:
        cart_svc.finalize(cart)
    except cart_svc.CartError:
        db.session.rollback()
        answer_callback_query(callback_id)
        edit_message_reply_markup(chat_id, message_id, {})
        send_message(chat_id, t('cart_empty_finish', lang))
        return
    log_event(CART_FINALIZE, user_id=user.id,
              description=f"cart={cart.id} total={cart.total} items={cart.item_count}",
              request=flask_request)
    db.session.commit()

    answer_callback_query(callback_id, t('toast_saved', lang))
    edit_message_reply_markup(chat_id, message_id, {})
    total = _money(cart.total, user)

    if not register:
        send_message(chat_id, t('cart_saved_only', lang).format(total=total, count=cart.item_count))
        return

    # El carrito ya quedó guardado; si el movimiento falla no se pierde la compra.
    try:
        tx = cart_svc.register_movement(cart)
        log_event(CART_MOVEMENT, user_id=user.id, description=f"cart={cart.id} amount={tx.amount}",
                  request=flask_request)
        db.session.commit()
    except cart_svc.CartError as exc:
        db.session.rollback()
        _log.warning("Cart movement error for cart=%s: %s", cart.id, exc.code)
        send_message(chat_id, t('cart_movement_error', lang))
        return
    category = db.session.get(Category, tx.category_id)
    send_message(chat_id, t('cart_saved_movement', lang).format(
        total=total, category=html.escape(category.name if category else '')))


def _save_only(chat_id, message_id, callback_id, user, cart_id):
    _save(chat_id, message_id, callback_id, user, cart_id)


def _save_movement(chat_id, message_id, callback_id, user, cart_id):
    _save(chat_id, message_id, callback_id, user, cart_id, register=True)


def _drop(chat_id, message_id, callback_id, user, cart_id):
    lang = _lang_of(user)
    cart = _open_cart_or_expire(chat_id, message_id, callback_id, user, cart_id)
    if cart is None:
        return
    answer_callback_query(callback_id)
    edit_message_reply_markup(chat_id, message_id, {})
    send_message_with_buttons(
        chat_id,
        t('cart_discard_confirm', lang).format(count=cart.item_count, total=_money(cart.total, user)),
        [[
            {'text': t('btn_cart_discard_yes', lang), 'callback_data': f'cartdropok:{cart.id}'},
            {'text': t('btn_cart_discard_no', lang), 'callback_data': f'cartend:{cart.id}'},
        ]],
    )


def _drop_confirmed(chat_id, message_id, callback_id, user, cart_id):
    lang = _lang_of(user)
    cart = _open_cart_or_expire(chat_id, message_id, callback_id, user, cart_id)
    if cart is None:
        return
    cart_svc.discard(cart)
    db.session.commit()
    answer_callback_query(callback_id, t('toast_cancelled', lang))
    edit_message_reply_markup(chat_id, message_id, {})
    send_message(chat_id, t('cart_discarded', lang))


_CALLBACKS = {
    'cartok': _confirm,
    'cartoffer': _confirm_offer,
    'cartskip': _skip,
    'cartfix': _fix,
    'cartmore': _more,
    'cartundo': _undo,
    'cartend': _finish,
    'cartsave': _save_only,
    'cartmov': _save_movement,
    'cartdrop': _drop,
    'cartdropok': _drop_confirmed,
}
