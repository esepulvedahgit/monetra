"""Tests for the Telegram webhook rate limit.

Regression coverage for the bug where the webhook's rate limit was keyed by
remote IP (shared by ALL Telegram traffic, since every update arrives from
Telegram's small server IP pool). Under load this shared bucket could exhaust
and silently drop the `/start <code>` message that completes account
linking. The fix scopes the limit per chat_id and exempts `/start`
unconditionally — see app/telegram/routes.py.

conftest.py's shared `app` fixture is built with RATELIMIT_ENABLED = False,
and Flask-Limiter's `init_app` skips wiring its before/after_request hooks
entirely when the limiter is disabled at init time (see
flask_limiter.extension.Limiter.init_app: `if not self.enabled: return`).
That means flipping app.config afterwards can't retroactively enable it on
that app. So this module builds its own small app (own in-memory DB) with
RATELIMIT_ENABLED = True from the start.
"""
import hashlib
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy.pool import StaticPool

from app import create_app, db as _db, limiter
from app.models import AuditLog, TelegramLink, TelegramLinkCode, User
from app.telegram.service import _webhook_path

WEBHOOK_SECRET = 'test-telegram-webhook-secret-32chars-xxxx'
RATE_LIMIT = '3 per minute'


class RateLimitTestConfig:
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_ENGINE_OPTIONS = {
        'connect_args': {'check_same_thread': False},
        'poolclass': StaticPool,
    }
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False
    SECRET_KEY = 'test-secret-key-32bytes-xxxxxxxxx'
    JWT_SECRET_KEY = 'test-jwt-secret-key-32bytes-xxxxx'
    JWT_ACCESS_TOKEN_EXPIRES = 900
    JWT_REFRESH_TOKEN_EXPIRES = 2592000
    BABEL_DEFAULT_LOCALE = 'es'
    BABEL_SUPPORTED_LOCALES = ['es', 'en']
    BABEL_TRANSLATION_DIRECTORIES = 'translations'
    MAX_CONTENT_LENGTH = 15 * 1024 * 1024
    CORS_ORIGINS = ['*']
    RATELIMIT_ENABLED = True
    TELEGRAM_BOT_TOKEN = 'test-bot-token'
    TELEGRAM_WEBHOOK_SECRET = WEBHOOK_SECRET
    TELEGRAM_WEBHOOK_RATE_LIMIT = RATE_LIMIT


@pytest.fixture(scope='module')
def rl_app():
    previous_enabled = limiter.enabled
    application = create_app(RateLimitTestConfig)
    with application.app_context():
        _db.create_all()
    yield application
    with application.app_context():
        _db.session.remove()
        _db.drop_all()
    limiter.enabled = previous_enabled


@pytest.fixture(scope='module')
def rl_client(rl_app):
    return rl_app.test_client()


@pytest.fixture(scope='module')
def rl_user_id(rl_app):
    with rl_app.app_context():
        u = User(username='tg_rate_limit_user', email='tg_rate_limit@example.com',
                  role='user', email_verified=True)
        u.set_password('Password123!')
        _db.session.add(u)
        _db.session.commit()
        return u.id


def _webhook_url():
    return f"/telegram/webhook/{_webhook_path(WEBHOOK_SECRET)}"


def _headers():
    return {'X-Telegram-Bot-Api-Secret-Token': WEBHOOK_SECRET}


def _text_update(chat_id, text):
    return {'message': {'chat': {'id': chat_id, 'type': 'private'}, 'text': text}}


def _post(c, update):
    return c.post(_webhook_url(), json=update, headers=_headers())


@pytest.fixture
def link_code(rl_app, rl_user_id):
    """Create a fresh one-time linking code for rl_user_id, return the raw code."""
    with rl_app.app_context():
        raw_code = f'raw-code-{rl_user_id}'
        _db.session.add(TelegramLinkCode(
            user_id=rl_user_id,
            code_hash=hashlib.sha256(raw_code.encode()).hexdigest(),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        ))
        _db.session.commit()
        return raw_code


@pytest.fixture(autouse=True)
def _cleanup_links(rl_app):
    yield
    with rl_app.app_context():
        TelegramLink.query.delete()
        TelegramLinkCode.query.delete()
        _db.session.commit()


@patch('app.telegram.handlers.send_message')
class TestWebhookRateLimit:

    def test_exceeding_limit_returns_429_and_is_audited(self, mock_send, rl_app, rl_client):
        chat_id = 111001
        for _ in range(3):
            r = _post(rl_client, _text_update(chat_id, 'hola'))
            assert r.status_code == 200
        r = _post(rl_client, _text_update(chat_id, 'hola'))
        assert r.status_code == 429

        with rl_app.app_context():
            events = AuditLog.query.filter_by(event_type='app.rate_limited').filter(
                AuditLog.description.like('/telegram/webhook/%')
            ).all()
            assert len(events) >= 1

    def test_start_is_exempt_even_when_chat_is_throttled(self, mock_send, rl_app, rl_client, rl_user_id, link_code):
        chat_id = 111002
        for _ in range(3):
            r = _post(rl_client, _text_update(chat_id, 'hola'))
            assert r.status_code == 200
        # The chat's non-/start budget is now exhausted...
        r = _post(rl_client, _text_update(chat_id, 'hola'))
        assert r.status_code == 429

        # ...but /start must still go through and complete the linking.
        r = _post(rl_client, _text_update(chat_id, f'/start {link_code}'))
        assert r.status_code == 200
        with rl_app.app_context():
            link = TelegramLink.query.filter_by(chat_id=chat_id).first()
            assert link is not None
            assert link.enabled is True
            assert link.user_id == rl_user_id

    def test_buckets_are_not_shared_across_chats(self, mock_send, rl_app, rl_client):
        chat_a, chat_b = 111003, 111004
        for _ in range(3):
            r = _post(rl_client, _text_update(chat_a, 'hola'))
            assert r.status_code == 200
        r = _post(rl_client, _text_update(chat_a, 'hola'))
        assert r.status_code == 429

        # A different chat has its own, untouched budget.
        r = _post(rl_client, _text_update(chat_b, 'hola'))
        assert r.status_code == 200

    def test_start_succeeds_on_a_fresh_chat(self, mock_send, rl_app, rl_client, rl_user_id, link_code):
        chat_id = 111005
        r = _post(rl_client, _text_update(chat_id, f'/start {link_code}'))
        assert r.status_code == 200
        with rl_app.app_context():
            link = TelegramLink.query.filter_by(chat_id=chat_id).first()
            assert link is not None
            assert link.enabled is True
