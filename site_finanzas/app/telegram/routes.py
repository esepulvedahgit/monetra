import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timezone, timedelta

from flask import current_app, jsonify, request
from flask_login import current_user, login_required

from app import db, limiter
from app.audit.events import TELEGRAM_LINK, TELEGRAM_UNLINK
from app.audit.logger import log_event
from app.models import TelegramLink, TelegramLinkCode, TelegramPendingTx
from app.telegram import telegram_bp
from app.telegram.handlers import process_update
from app.telegram.service import _webhook_path

_log = logging.getLogger(__name__)


@telegram_bp.route('/telegram/webhook/<webhook_path>', methods=['POST'])
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

    # Expire any existing unused codes for this user
    now = datetime.now(timezone.utc)
    TelegramLinkCode.query.filter(
        TelegramLinkCode.user_id == current_user.id,
        TelegramLinkCode.used_at.is_(None),
    ).delete()

    # Generate new code
    raw_code = secrets.token_urlsafe(24)
    code_hash = hashlib.sha256(raw_code.encode()).hexdigest()
    expires_at = now + timedelta(minutes=10)

    db.session.add(TelegramLinkCode(
        user_id=current_user.id,
        code_hash=code_hash,
        expires_at=expires_at,
    ))
    db.session.commit()

    # Build deep link — requires TELEGRAM_BOT_USERNAME; returns null if not configured
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
        # Limpiar estado conversacional al desactivar
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

    # Delete pending transactions for this chat
    TelegramPendingTx.query.filter_by(chat_id=chat_id).delete()

    # Delete the link
    db.session.delete(link)

    log_event(TELEGRAM_UNLINK, user_id=current_user.id, description=f"chat_id={chat_id}", request=request)
    db.session.commit()

    return jsonify({'unlinked': True})
