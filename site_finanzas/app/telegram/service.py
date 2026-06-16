import hashlib
import logging
import os

import requests
from flask import current_app

_log = logging.getLogger(__name__)
_BASE = "https://api.telegram.org/bot{token}/{method}"


def _token() -> str:
    return current_app.config.get('TELEGRAM_BOT_TOKEN') or ''


def _api(method: str, **kwargs) -> dict:
    """Call a Telegram Bot API method. Returns the response dict or {} on error."""
    token = _token()
    if not token:
        return {}
    url = _BASE.format(token=token, method=method)
    try:
        resp = requests.post(url, json=kwargs, timeout=10, allow_redirects=False)
        return resp.json() if resp.status_code == 200 else {}
    except Exception as exc:
        _log.warning("Telegram API %s error: %s", method, exc)
        return {}


def send_message(chat_id: int, text: str, parse_mode: str = 'HTML') -> None:
    _api('sendMessage', chat_id=chat_id, text=text, parse_mode=parse_mode)


def send_message_with_buttons(chat_id: int, text: str, buttons: list) -> dict:
    """Send a message with inline keyboard buttons.

    buttons: list of rows, each row is a list of dicts with 'text' and 'callback_data'.
    Returns the full API response (needed to get the message_id for edits).
    """
    return _api(
        'sendMessage',
        chat_id=chat_id,
        text=text,
        parse_mode='HTML',
        reply_markup={'inline_keyboard': buttons},
    )


def edit_message_reply_markup(chat_id: int, message_id: int, reply_markup: dict) -> None:
    _api('editMessageReplyMarkup', chat_id=chat_id, message_id=message_id, reply_markup=reply_markup)


def answer_callback_query(callback_query_id: str, text: str = '') -> None:
    _api('answerCallbackQuery', callback_query_id=callback_query_id, text=text, show_alert=False)


_MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024  # 20 MB


def download_file(file_id: str) -> bytes | None:
    """Download a Telegram file by file_id. Returns raw bytes or None.

    SSRF protection: only downloads from api.telegram.org.
    Byte cap: aborts if response exceeds 20 MB.
    """
    token = _token()
    if not token:
        return None
    result = _api('getFile', file_id=file_id)
    path = (result.get('result') or {}).get('file_path')
    if not path:
        return None
    url = f"https://api.telegram.org/file/bot{token}/{path}"
    try:
        resp = requests.get(url, timeout=30, allow_redirects=False, stream=True)
        if resp.status_code != 200:
            return None
        chunks = []
        total = 0
        for chunk in resp.iter_content(chunk_size=65536):
            total += len(chunk)
            if total > _MAX_DOWNLOAD_BYTES:
                _log.warning("Telegram file exceeds 20 MB cap for file_id=%s, aborting", file_id)
                return None
            chunks.append(chunk)
        return b''.join(chunks)
    except Exception as exc:
        _log.warning("Telegram file download error: %s", exc)
    return None


def set_webhook(app_url: str, secret: str) -> bool:
    """Register the webhook with Telegram. Returns True on success."""
    token = _token()
    if not token:
        _log.warning("Telegram setWebhook: no token configured")
        return False
    webhook_path = _webhook_path(secret)
    webhook_url = f"{app_url.rstrip('/')}/telegram/webhook/{webhook_path}"
    try:
        resp = requests.post(
            _BASE.format(token=token, method='setWebhook'),
            json={'url': webhook_url, 'secret_token': secret,
                  'allowed_updates': ['message', 'callback_query']},
            timeout=10, allow_redirects=False,
        )
        data = resp.json() if 'application/json' in resp.headers.get('content-type', '') else {}
        if resp.status_code == 200 and data.get('ok'):
            _log.info("Telegram webhook registered successfully")
            return True
        _log.warning("Telegram setWebhook failed: status=%s body=%s", resp.status_code, resp.text[:500])
        return False
    except Exception as exc:
        _log.warning("Telegram setWebhook error: %s", exc)
        return False


def _webhook_path(secret: str) -> str:
    """Derive a stable, opaque path segment from the webhook secret."""
    return hashlib.sha256(f"tg-hook-{secret}".encode()).hexdigest()[:32]
