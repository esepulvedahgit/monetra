import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timezone, timedelta

from flask import current_app, jsonify, request
from flask_limiter.util import get_remote_address
from flask_login import current_user, login_required

from app import csrf, db, limiter
from app.audit.events import TELEGRAM_LINK, TELEGRAM_UNLINK
from app.audit.logger import log_event
from app.models import TelegramLink, TelegramLinkCode, TelegramPendingTx
from app.telegram import telegram_bp
from app.telegram.handlers import process_update
from app.telegram.service import _webhook_path

_log = logging.getLogger(__name__)


def _chat_id_from_update(update: dict) -> int | None:
    if 'message' in update:
        return update['message'].get('chat', {}).get('id')
    if 'callback_query' in update:
        return update['callback_query'].get('message', {}).get('chat', {}).get('id')
    return None


def _is_start_command(update: dict) -> bool:
    """True si el update es un mensaje /start (handshake de vinculación)."""
    text = (update.get('message') or {}).get('text') or ''
    return text.strip().startswith('/start')


def _telegram_rate_limit_key() -> str:
    """Key del rate limit del webhook, scopeada por chat_id.

    Todos los updates de Telegram para todos los usuarios llegan desde el
    mismo pool pequeño de IPs de servidores de Telegram, así que usar
    get_remote_address (default de Flask-Limiter) crea UN bucket compartido
    por todo el tráfico del bot. Escopear por chat_id da a cada chat su
    propio presupuesto. Cae a la IP remota solo si no se puede parsear el
    chat_id — la autenticación real de esta ruta es el path secreto +
    header X-Telegram-Bot-Api-Secret-Token validados en webhook().
    """
    update = request.get_json(silent=True) or {}
    chat_id = _chat_id_from_update(update)
    return f"tg-chat:{chat_id}" if chat_id else f"tg-ip:{get_remote_address()}"


def _exempt_start_from_rate_limit() -> bool:
    """El /start que completa la vinculación nunca debe bloquearse."""
    update = request.get_json(silent=True) or {}
    return _is_start_command(update)


# #7 — CSRF exento solo en el webhook (no en generate-code / toggle-usd / unlink)
@telegram_bp.route('/telegram/webhook/<webhook_path>', methods=['POST'])
@csrf.exempt
@limiter.limit(
    lambda: current_app.config.get('TELEGRAM_WEBHOOK_RATE_LIMIT', '30 per minute'),
    key_func=_telegram_rate_limit_key,
    exempt_when=_exempt_start_from_rate_limit,
)
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
@limiter.limit(lambda: current_app.config.get('TELEGRAM_LINK_CODE_RATE_LIMIT', '5 per 10 minute'))
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

    # Strip whitespace and a leading '@' to tolerate common mis-configuration.
    bot_username = (current_app.config.get('TELEGRAM_BOT_USERNAME') or '').strip().lstrip('@')
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
