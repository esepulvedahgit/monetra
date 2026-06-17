import hashlib
import hmac
import logging
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timezone, timedelta

from flask import current_app, jsonify, request
from flask_login import current_user, login_required

from app import csrf, db, limiter
from app.audit.events import TELEGRAM_LINK, TELEGRAM_UNLINK
from app.audit.logger import log_event
from app.models import TelegramLink, TelegramLinkCode, TelegramPendingTx
from app.telegram import telegram_bp
from app.telegram.handlers import process_update
from app.telegram.service import _webhook_path

_log = logging.getLogger(__name__)

# #10 — Throttle por chat_id (in-process, para single-worker Gunicorn)
# Permite hasta 20 mensajes por chat en 60 segundos antes de descartarlos silenciosamente.
_CHAT_TIMESTAMPS: dict[int, deque] = defaultdict(lambda: deque(maxlen=20))
_CHAT_RATE_WINDOW = 60
_CHAT_RATE_LIMIT  = 20


def _is_chat_rate_limited(chat_id: int) -> bool:
    now = time.monotonic()
    dq = _CHAT_TIMESTAMPS[chat_id]
    while dq and now - dq[0] > _CHAT_RATE_WINDOW:
        dq.popleft()
    if len(dq) >= _CHAT_RATE_LIMIT:
        return True
    dq.append(now)
    return False


def _chat_id_from_update(update: dict) -> int | None:
    if 'message' in update:
        return update['message'].get('chat', {}).get('id')
    if 'callback_query' in update:
        return update['callback_query'].get('message', {}).get('chat', {}).get('id')
    return None


# #7 — CSRF exento solo en el webhook (no en generate-code / toggle-usd / unlink)
@telegram_bp.route('/telegram/webhook/<webhook_path>', methods=['POST'])
@csrf.exempt
@limiter.limit("60 per minute")
def webhook(webhook_path: str):
    """Receive Telegram updates. Validates secret path + header before dispatching."""
    secret = current_app.config.get('TELEGRAM_WEBHOOK_SECRET') or ''

    if not secret:
        return jsonify({'ok': False}), 403

    expected_path = _webhook_path(secret)
    if not hmac.compare_digest(webhook_path, expected_path):
        _log.warning("Invalid webhook path received")
        return jsonify({'ok': False}), 403

    header_secret = request.headers.get('X-Telegram-Bot-Api-Secret-Token', '')
    if not hmac.compare_digest(header_secret, secret):
        _log.warning("Invalid X-Telegram-Bot-Api-Secret-Token")
        return jsonify({'ok': False}), 403

    update = request.get_json(silent=True)
    if update:
        # #10 — Throttle por chat_id antes de procesar
        chat_id = _chat_id_from_update(update)
        if chat_id and _is_chat_rate_limited(chat_id):
            _log.warning("Per-chat rate limit exceeded for chat_id=%s, dropping update", chat_id)
            return jsonify({'ok': True}), 200  # siempre 200 a Telegram

        try:
            process_update(update)
        except Exception as exc:
            _log.error("Webhook dispatch error: %s", exc, exc_info=True)

    return jsonify({'ok': True}), 200


@telegram_bp.route('/telegram/status', methods=['GET'])
@login_required
def status():
    """Return current Telegram link status for the authenticated user."""
    bot_configured = bool(current_app.config.get('TELEGRAM_BOT_TOKEN'))
    link = TelegramLink.query.filter_by(user_id=current_user.id).first()
    return jsonify({
        'bot_configured': bot_configured,
        'linked': bool(link and link.enabled),
        'chat_id': link.chat_id if (link and link.enabled) else None,
        'linked_at': link.linked_at.isoformat() if (link and link.linked_at) else None,
    })


@telegram_bp.route('/telegram/generate-code', methods=['POST'])
@login_required
@limiter.limit("5 per 10 minute")
def generate_code():
    """Generate a one-time linking code and return the Telegram deep link."""
    if not current_app.config.get('TELEGRAM_BOT_TOKEN'):
        return jsonify({'error': 'Bot not configured'}), 503

    from app.email_service import resolve_ai_config
    if resolve_ai_config(current_user) is None:
        return jsonify({'error': 'ai_required'}), 403

    now = datetime.now(timezone.utc)
    TelegramLinkCode.query.filter(
        TelegramLinkCode.user_id == current_user.id,
        TelegramLinkCode.used_at.is_(None),
    ).delete()

    raw_code = secrets.token_urlsafe(24)
    code_hash = hashlib.sha256(raw_code.encode()).hexdigest()
    expires_at = now + timedelta(minutes=10)

    db.session.add(TelegramLinkCode(
        user_id=current_user.id,
        code_hash=code_hash,
        expires_at=expires_at,
    ))
    db.session.commit()

    bot_username = current_app.config.get('TELEGRAM_BOT_USERNAME', '')
    deep_link = f"https://t.me/{bot_username}?start={raw_code}" if bot_username else None

    return jsonify({
        'code': raw_code,
        'deep_link': deep_link,
        'expires_in_minutes': 10,
    })


@telegram_bp.route('/telegram/toggle-usd', methods=['POST'])
@login_required
def toggle_usd():
    """Activar/desactivar el modo USD para el bot de Telegram del usuario actual."""
    link = TelegramLink.query.filter_by(user_id=current_user.id, enabled=True).first()
    if not link:
        return jsonify({'error': 'No linked account'}), 400

    data = request.get_json(silent=True) or {}
    enabled = bool(data.get('enabled', False))
    link.usd_enabled = enabled
    if not enabled:
        link.pending_type = None
        link.state_updated_at = None
    db.session.commit()
    return jsonify({'usd_enabled': link.usd_enabled})


@telegram_bp.route('/telegram/unlink', methods=['POST'])
@login_required
def unlink():
    """Unlink the current user's Telegram account."""
    link = TelegramLink.query.filter_by(user_id=current_user.id).first()
    if not link:
        return jsonify({'unlinked': False, 'message': 'No linked account'}), 200

    chat_id = link.chat_id
    TelegramPendingTx.query.filter_by(chat_id=chat_id).delete()
    db.session.delete(link)

    log_event(TELEGRAM_UNLINK, user_id=current_user.id, description=f"chat_id={chat_id}", request=request)
    db.session.commit()

    return jsonify({'unlinked': True})
