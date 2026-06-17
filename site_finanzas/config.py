import os
import secrets


def _require_key(env_var: str, fallback_in_debug: bool = True) -> str:
    value = os.environ.get(env_var)
    if value:
        return value
    if fallback_in_debug and os.environ.get('FLASK_DEBUG', '0') != '0':
        return secrets.token_hex(32)
    raise RuntimeError(
        f"La variable de entorno '{env_var}' es obligatoria en producción. "
        f"Agrégala al archivo docker/.env o al entorno del contenedor."
    )


class Config:
    SECRET_KEY = _require_key('SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get('DATABASE_URL')
        or 'mysql+pymysql://{user}:{password}@{host}:{port}/{db}'.format(
            user=os.environ.get('DB_USER', 'finanzas_user'),
            password=os.environ.get('DB_PASSWORD', ''),
            host=os.environ.get('DB_HOST', 'mysql'),
            port=os.environ.get('DB_PORT', '3306'),
            db=os.environ.get('DB_NAME', 'finanzas_db'),
        )
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    BABEL_DEFAULT_LOCALE = 'es'
    BABEL_SUPPORTED_LOCALES = ['es', 'en']
    BABEL_TRANSLATION_DIRECTORIES = 'translations'

    # Default 15 MB; raise MAX_CONTENT_UPLOAD_MB in docker/.env to restore large databases.
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_UPLOAD_MB', '15')) * 1024 * 1024

    JWT_SECRET_KEY = _require_key('JWT_SECRET_KEY')
    JWT_ACCESS_TOKEN_EXPIRES = 900        # 15 min
    JWT_REFRESH_TOKEN_EXPIRES = 2592000   # 30 días
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*').split(',')

    # Session and remember-me cookie hardening.
    # By default, Secure cookies are enabled in production (FLASK_DEBUG=0) and
    # disabled in dev/test (FLASK_DEBUG=1) so the HTTP test client keeps the cookie.
    # For HTTP-only deploys (no TLS reverse proxy) set SESSION_COOKIE_SECURE=false
    # in docker/.env so browsers send cookies over plain HTTP.
    # For HTTPS deploys behind a reverse proxy, leave it at the default (true in prod).
    _in_production = os.environ.get('FLASK_DEBUG', '0') == '0'

    def _bool_env(name, default):
        raw = os.environ.get(name)
        if raw is None or raw == '':
            return default
        return raw.strip().lower() in ('1', 'true', 'yes', 'on')

    _secure_cookies = _bool_env('SESSION_COOKIE_SECURE', _in_production)
    SESSION_COOKIE_HTTPONLY  = True
    SESSION_COOKIE_SAMESITE  = 'Lax'
    SESSION_COOKIE_SECURE    = _secure_cookies
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_SECURE   = _secure_cookies
    # Inactivity timeout (seconds). Override with SESSION_INACTIVITY_TIMEOUT env var.
    SESSION_INACTIVITY_TIMEOUT = int(os.environ.get('SESSION_INACTIVITY_TIMEOUT', 900))  # 15 min

    # Telegram Bot (optional — feature is disabled if not set)
    TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
    TELEGRAM_WEBHOOK_SECRET = os.environ.get('TELEGRAM_WEBHOOK_SECRET')
    TELEGRAM_BOT_USERNAME = os.environ.get('TELEGRAM_BOT_USERNAME', '')

    # Cuota diaria máxima de escaneos IA por usuario cuando usan la clave compartida del admin.
    # Sube o baja este valor con AI_SHARED_DAILY_LIMIT en .env.
    AI_SHARED_DAILY_LIMIT = int(os.environ.get('AI_SHARED_DAILY_LIMIT', '25'))
