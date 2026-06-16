import hashlib
import html
import logging
import re
from datetime import datetime, timezone, timedelta, date as _date
from decimal import Decimal, InvalidOperation

from flask import current_app

from app import db
from app.audit.events import TELEGRAM_LINK, TELEGRAM_UNLINK, TELEGRAM_TX_CREATE
from app.audit.logger import log_event
from app.models import (
    TelegramLink, TelegramLinkCode, TelegramPendingTx,
    Transaction, Category, UsdTransaction, UsdCategory, UserAIConfig, User,
)
from app.money import format_money, format_money_for_user, parse_amount, parse_amount_for_user
from app.telegram.messages import t
from app.telegram.service import (
    answer_callback_query,
    download_file,
    edit_message_reply_markup,
    send_message,
    send_message_with_buttons,
)

_log = logging.getLogger(__name__)

# Color fijo para la categoría USD auto-creada (azul Telegram)
_USD_CATEGORY_COLOR = '#2AABEE'

# Convención de dólar (consistente con la sección USD de la app: US$, 2 decimales, '.' decimal)
_USD_LOCALE = 'en_US'
_USD_CODE   = 'USD'
_USD_SYMBOL = 'US$'


def _parse_amount_for_tx(token: str, tx_type: str, user) -> Decimal:
    """Parsea un monto respetando la convención de la moneda del tipo de transacción.

    - USD → locale en_US (punto decimal, coma miles), precisión 2 dec.
    - Principal → locale/código del usuario (respeta su moneda configurada).
    """
    if tx_type == 'usd':
        return parse_amount(token, locale=_USD_LOCALE, code=_USD_CODE)
    return parse_amount_for_user(token, user)


def _format_amount_for_tx(amount, tx_type: str, user) -> str:
    """Formatea un monto según la convención de la moneda del tipo de transacción."""
    if tx_type == 'usd':
        return format_money(amount, code=_USD_CODE, locale=_USD_LOCALE, symbol=_USD_SYMBOL)
    return format_money_for_user(amount, user)


def _lang_of(user) -> str | None:
    """Idioma preferido del usuario (None → español por defecto en t())."""
    return user.language if user else None


# ── Estado conversacional ─────────────────────────────────────────────────────

def _state_active(link: TelegramLink) -> bool:
    """Devuelve True si hay un pending_type activo con TTL < 1h.

    Si el estado expiró lo limpia y persiste (sin commit: el llamador hace commit
    junto a sus propios cambios o simplemente no lo necesita para el flujo de control).
    """
    if not link.pending_type:
        return False
    if link.state_updated_at is None:
        link.pending_type = None
        return False
    updated_at = link.state_updated_at
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    if (datetime.now(timezone.utc) - updated_at).total_seconds() > 3600:
        link.pending_type = None
        link.state_updated_at = None
        return False
    return True


def _clear_state(link: TelegramLink) -> None:
    """Limpia el estado conversacional del link."""
    link.pending_type = None
    link.state_updated_at = None


def _usd_default_category(user_id: int) -> UsdCategory:
    """Obtiene o crea la categoría USD 'Telegram' para el usuario."""
    cat = UsdCategory.query.filter_by(user_id=user_id, name='Telegram').first()
    if not cat:
        cat = UsdCategory(user_id=user_id, name='Telegram', color=_USD_CATEGORY_COLOR)
        db.session.add(cat)
        db.session.flush()   # genera cat.id antes del commit del llamador
    return cat


# ── Entry point ───────────────────────────────────────────────────────────────

def process_update(update: dict) -> None:
    """Main dispatcher — called from the webhook route."""
    try:
        if 'message' in update:
            _handle_message(update['message'])
        elif 'callback_query' in update:
            _handle_callback(update['callback_query'])
    except Exception as exc:
        _log.error("process_update error: %s", exc, exc_info=True)
        db.session.rollback()


# ── Message handler ───────────────────────────────────────────────────────────

def _handle_message(msg: dict) -> None:
    chat_id = msg.get('chat', {}).get('id')
    if not chat_id:
        return

    text = msg.get('text', '').strip()

    # /start <code>
    if text.startswith('/start'):
        parts = text.split(maxsplit=1)
        code = parts[1].strip() if len(parts) > 1 else ''
        _handle_start(chat_id, code)
        return

    # Require linked account for everything else
    link = TelegramLink.query.filter_by(chat_id=chat_id, enabled=True).first()
    if not link:
        send_message(chat_id, t('not_linked'))
        return

    user = User.query.get(link.user_id)
    lang = _lang_of(user)

    # ── Modo USD activo: pedir tipo antes de recibir el gasto ────────────────
    if link.usd_enabled:
        if not _state_active(link):
            # Sin estado → preguntar tipo de transacción
            db.session.commit()  # persistir limpieza de estado expirado si ocurrió
            name = html.escape(user.username) if user else ''
            buttons = [[
                {'text': t('btn_type_principal', lang), 'callback_data': 'settype:principal'},
                {'text': t('btn_type_usd', lang), 'callback_data': 'settype:usd'},
            ]]
            send_message_with_buttons(chat_id, t('ask_type', lang).format(name=name), buttons)
            return
        # Estado activo → procesar el gasto con el tipo elegido
        tx_type = link.pending_type
    else:
        tx_type = 'principal'

    # Photo message
    photos = msg.get('photo')
    if photos:
        _handle_photo(chat_id, link.user_id, photos, lang, tx_type, link)
        return

    # Text message (expense entry)
    if text:
        _handle_text(chat_id, link.user_id, text, lang, tx_type, link)
        return


# ── /start handler (linking) ──────────────────────────────────────────────────

def _handle_start(chat_id: int, code: str) -> None:
    # Already linked?
    existing = TelegramLink.query.filter_by(chat_id=chat_id, enabled=True).first()
    if existing:
        user = User.query.get(existing.user_id)
        name = html.escape(user.username) if user else ''
        send_message(chat_id, t('already_linked', _lang_of(user)).format(name=name))
        return

    if not code:
        send_message(chat_id, t('welcome_unlinked'))
        return

    code_hash = hashlib.sha256(code.encode()).hexdigest()
    now = datetime.now(timezone.utc)

    link_code = TelegramLinkCode.query.filter_by(code_hash=code_hash, used_at=None).first()
    if not link_code:
        send_message(chat_id, t('code_invalid'))
        return

    expires_at = link_code.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if now > expires_at:
        send_message(chat_id, t('code_invalid'))
        return

    # Consume code
    link_code.used_at = now

    # Create or update link
    tg_link = TelegramLink.query.filter_by(user_id=link_code.user_id).first()
    if tg_link:
        tg_link.chat_id = chat_id
        tg_link.enabled = True
        tg_link.linked_at = now
    else:
        tg_link = TelegramLink(
            user_id=link_code.user_id,
            chat_id=chat_id,
            enabled=True,
            linked_at=now,
        )
        db.session.add(tg_link)

    log_event(TELEGRAM_LINK, user_id=link_code.user_id, description=f"chat_id={chat_id}")
    db.session.commit()

    user = User.query.get(link_code.user_id)
    name = html.escape(user.username) if user else ''
    send_message(chat_id, t('linked_ok', _lang_of(user)).format(name=name))


# ── Photo handler ─────────────────────────────────────────────────────────────

def _handle_photo(
    chat_id: int,
    user_id: int,
    photos: list,
    lang: str | None,
    tx_type: str,
    link: TelegramLink,
) -> None:
    from app.email_service import resolve_ai_config
    _tg_user = User.query.get(user_id)
    ai_config = resolve_ai_config(_tg_user) if _tg_user else None
    if not ai_config:
        send_message(chat_id, t('ai_not_configured', lang))
        return

    # Take the largest photo (last in the list has highest resolution)
    best = max(photos, key=lambda p: p.get('file_size', 0))
    file_id = best.get('file_id')
    if not file_id:
        send_message(chat_id, t('extract_error', lang))
        return

    image_bytes = download_file(file_id)
    if not image_bytes:
        send_message(chat_id, t('extract_error', lang))
        return

    # Validate + normalize
    try:
        from app.scanner.image_utils import validate_and_normalize_image
        image_bytes, mime_type = validate_and_normalize_image(image_bytes)
    except ValueError as exc:
        _log.warning("Image validation error for chat_id=%s: %s", chat_id, exc)
        send_message(chat_id, t('extract_error', lang))
        return
    except Exception as exc:
        _log.error("Image validation unexpected error for chat_id=%s: %s", chat_id, exc, exc_info=True)
        send_message(chat_id, t('extract_error', lang))
        return

    # Extract with AI
    try:
        from app.scanner.providers import extract_receipt
        result = extract_receipt(ai_config, image_bytes, mime_type)
    except ValueError as exc:
        _log.warning("Receipt extraction error for chat_id=%s: %s", chat_id, exc)
        send_message(chat_id, t('extract_error', lang))
        return
    except Exception as exc:
        _log.error("Receipt extraction unexpected error for chat_id=%s: %s", chat_id, exc, exc_info=True)
        send_message(chat_id, t('extract_error', lang))
        return

    _save_pending_and_confirm(chat_id, user_id, result, lang, tx_type, link)


# ── Text handler ──────────────────────────────────────────────────────────────

# Captura números con separadores de miles/decimales (p. ej. 1.670, 1.670,50, 12500).
# Intencionalmente amplio: el parseo locale-aware de Babel decide el valor real.
_AMOUNT_RE = re.compile(r'\d+(?:[.,]\d+)*')


def _handle_text(
    chat_id: int,
    user_id: int,
    text: str,
    lang: str | None,
    tx_type: str,
    link: TelegramLink,
) -> None:
    text = text[:4096]
    matches = list(_AMOUNT_RE.finditer(text))
    if not matches:
        send_message(chat_id, t('text_parse_help', lang))
        return

    # Último número del mensaje = monto (heurística "descripción monto")
    last_match = matches[-1]
    amount_token = last_match.group(0)

    user = User.query.get(user_id)
    try:
        amount = _parse_amount_for_tx(amount_token, tx_type, user)
    except ValueError:
        send_message(chat_id, t('text_parse_help', lang))
        return

    # Descripción: texto sin el token del monto elegido
    description = (text[:last_match.start()] + text[last_match.end():]).strip(' -–—,.')
    if not description:
        description = t('default_description', lang)

    result = {
        'total': amount,
        'description': description,
        'merchant': None,
        'date': None,
        'currency': None,
    }
    _save_pending_and_confirm(chat_id, user_id, result, lang, tx_type, link)


# ── Pending tx helpers ────────────────────────────────────────────────────────

def _save_pending_and_confirm(
    chat_id: int,
    user_id: int,
    result: dict,
    lang: str | None,
    tx_type: str,
    link: TelegramLink,
) -> None:
    # Delete previous pending transactions for this chat
    TelegramPendingTx.query.filter_by(chat_id=chat_id).delete()

    # Resolve fallback category (solo para Principal)
    category_id = None
    if tx_type == 'principal':
        fallback_cat = Category.query.filter_by(name='Telegram', user_id=None, type='expense').first()
        category_id = fallback_cat.id if fallback_cat else None

    amount = result.get('total')
    description = result.get('description') or result.get('merchant') or t('default_description', lang)
    merchant = result.get('merchant')
    currency = result.get('currency')

    # Parse date
    tx_date = None
    raw_date = result.get('date')
    if raw_date:
        for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'):
            try:
                tx_date = datetime.strptime(raw_date, fmt).date()
                break
            except (ValueError, TypeError):
                pass
    if tx_date is None:
        tx_date = _date.today()

    pending = TelegramPendingTx(
        chat_id=chat_id,
        user_id=user_id,
        amount=amount,
        description=description[:500] if description else None,
        merchant=merchant[:200] if merchant else None,
        tx_date=tx_date,
        currency=currency,
        category_id=category_id,
        tx_type=tx_type,
    )
    db.session.add(pending)

    # Limpiar estado conversacional — el tipo ya fue capturado en la pendiente
    _clear_state(link)
    db.session.commit()

    user = User.query.get(user_id)
    _send_confirmation(chat_id, pending, user)


def _send_confirmation(chat_id: int, pending: TelegramPendingTx, user) -> None:
    lang = _lang_of(user)
    tx_type = pending.tx_type or 'principal'
    amount_str = _format_amount_for_tx(pending.amount, tx_type, user) if pending.amount is not None else '?'
    desc = html.escape(pending.description or pending.merchant or t('default_description', lang))
    date_str = pending.tx_date.strftime('%d/%m/%Y') if pending.tx_date else '?'

    text = t('confirm_card', lang).format(desc=desc, amount=amount_str, date=date_str)
    buttons = [[
        {'text': t('btn_confirm', lang), 'callback_data': f'confirm:{pending.id}'},
        {'text': t('btn_cancel', lang), 'callback_data': f'cancel:{pending.id}'},
    ]]
    send_message_with_buttons(chat_id, text, buttons)


# ── Callback handler ──────────────────────────────────────────────────────────

def _handle_callback(callback: dict) -> None:
    callback_id = callback.get('id')
    data = callback.get('data', '')
    chat_id = callback.get('message', {}).get('chat', {}).get('id')
    message_id = callback.get('message', {}).get('message_id')

    if not chat_id or not data:
        return

    if data.startswith('settype:'):
        _do_set_type(chat_id, message_id, callback_id, data)
    elif data.startswith('confirm:'):
        _do_confirm(chat_id, message_id, callback_id, data)
    elif data.startswith('cancel:'):
        _do_cancel(chat_id, message_id, callback_id, data)
    else:
        answer_callback_query(callback_id)


def _do_set_type(chat_id: int, message_id: int, callback_id: str, data: str) -> None:
    """Procesa la elección de tipo de transacción (Principal/USD)."""
    try:
        chosen = data.split(':', 1)[1]
    except IndexError:
        answer_callback_query(callback_id)
        return

    if chosen not in ('principal', 'usd'):
        answer_callback_query(callback_id)
        return

    link = TelegramLink.query.filter_by(chat_id=chat_id, enabled=True).first()
    if not link:
        answer_callback_query(callback_id)
        return

    user = User.query.get(link.user_id)
    lang = _lang_of(user)

    link.pending_type = chosen
    link.state_updated_at = datetime.now(timezone.utc)
    db.session.commit()

    answer_callback_query(callback_id)
    # Quitar botones del mensaje de selección
    edit_message_reply_markup(chat_id, message_id, {})
    # Invitar a escribir/adjuntar el gasto
    send_message(chat_id, t('prompt_expense', lang))


def _do_confirm(chat_id: int, message_id: int, callback_id: str, data: str) -> None:
    try:
        pending_id = int(data.split(':', 1)[1])
    except (ValueError, IndexError):
        answer_callback_query(callback_id, t('toast_error'))
        return

    pending = TelegramPendingTx.query.get(pending_id)
    if not pending or pending.chat_id != chat_id:
        answer_callback_query(callback_id, t('toast_expired'))
        send_message(chat_id, t('pending_expired'))
        return

    user = User.query.get(pending.user_id)
    lang = _lang_of(user)

    # C-1: Re-validate link ownership to guard against re-linking races
    link = TelegramLink.query.filter_by(chat_id=chat_id, enabled=True).first()
    if not link or link.user_id != pending.user_id:
        db.session.delete(pending)
        db.session.commit()
        answer_callback_query(callback_id, t('toast_expired', lang))
        send_message(chat_id, t('pending_expired', lang))
        return

    # H-1: Reject pending transactions older than 1 hour
    now = datetime.now(timezone.utc)
    created_at = pending.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    if (now - created_at).total_seconds() > 3600:
        db.session.delete(pending)
        db.session.commit()
        answer_callback_query(callback_id, t('toast_expired', lang))
        send_message(chat_id, t('pending_expired', lang))
        return

    tx_type = pending.tx_type or 'principal'

    if tx_type == 'usd':
        # ── Crear UsdTransaction ──────────────────────────────────────────────
        usd_cat = _usd_default_category(pending.user_id)
        tx_amount = pending.amount or 0
        tx = UsdTransaction(
            user_id=pending.user_id,
            category_id=usd_cat.id,
            amount=tx_amount,
            description=pending.description or '',
            date=pending.tx_date or _date.today(),
        )
        db.session.add(tx)
        log_event(
            TELEGRAM_TX_CREATE,
            user_id=pending.user_id,
            description=f"usd amount={pending.amount}",
        )
        db.session.delete(pending)
        db.session.commit()

        answer_callback_query(callback_id, t('toast_saved', lang))
        edit_message_reply_markup(chat_id, message_id, {})
        amount_str = _format_amount_for_tx(tx.amount or 0, 'usd', user)
        send_message(chat_id, t('saved', lang).format(
            description=html.escape(tx.description or ''), amount=amount_str
        ))
    else:
        # ── Crear Transaction (Principal) ─────────────────────────────────────
        tx = Transaction(
            user_id=pending.user_id,
            category_id=pending.category_id,
            type='expense',
            amount=pending.amount or 0,
            description=pending.description or '',
            date=pending.tx_date or _date.today(),
        )
        db.session.add(tx)
        log_event(
            TELEGRAM_TX_CREATE,
            user_id=pending.user_id,
            description=f"amount={pending.amount}",
        )
        db.session.delete(pending)
        db.session.commit()

        answer_callback_query(callback_id, t('toast_saved', lang))
        edit_message_reply_markup(chat_id, message_id, {})
        amount_str = format_money_for_user(tx.amount or 0, user)
        send_message(chat_id, t('saved', lang).format(
            description=html.escape(tx.description or ''), amount=amount_str
        ))


def _do_cancel(chat_id: int, message_id: int, callback_id: str, data: str) -> None:
    try:
        pending_id = int(data.split(':', 1)[1])
    except (ValueError, IndexError):
        answer_callback_query(callback_id)
        return

    pending = TelegramPendingTx.query.get(pending_id)
    if pending and pending.chat_id == chat_id:
        db.session.delete(pending)

    link = TelegramLink.query.filter_by(chat_id=chat_id, enabled=True).first()
    user = User.query.get(link.user_id) if link else None
    lang = _lang_of(user)

    # Limpiar estado conversacional al cancelar
    if link:
        _clear_state(link)

    db.session.commit()

    answer_callback_query(callback_id, t('toast_cancelled', lang))
    edit_message_reply_markup(chat_id, message_id, {})
    send_message(chat_id, t('cancelled', lang))
