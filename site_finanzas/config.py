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

    # ── Rate limiting (Flask-Limiter) ──────────────────────────────────────────
    # Backend donde se guardan los contadores por IP de los límites de
    # login / registro / recuperación de contraseña.
    #
    #   memory://              (default) contadores en el propio proceso. NO se
    #                          comparten entre workers de gunicorn y se pierden
    #                          al reiniciar. Suficiente detrás de un WAF/equipo
    #                          de seguridad o en un único worker (dev).
    #   redis://redis:6379/0   almacén compartido y persistente entre workers y
    #                          reinicios. Úsalo cuando la app está EXPUESTA
    #                          DIRECTAMENTE a internet, para que el límite
    #                          anti fuerza-bruta sea global y no se multiplique
    #                          por la cantidad de workers.
    RATELIMIT_STORAGE_URI = os.environ.get('RATELIMIT_STORAGE_URI', 'memory://')
    # Si Redis se vuelve inalcanzable, degrada a límite en memoria en vez de
    # devolver errores 500, para que el login siga funcionando.
    RATELIMIT_IN_MEMORY_FALLBACK_ENABLED = True

    # Límites por ruta, configurables sin tocar código. Sintaxis Flask-Limiter:
    # "N per second|minute|hour|day" (o compuesto: "N per minute;M per hour").
    # Cambia el valor en docker/.env y reinicia el contenedor para aplicar.
    LOGIN_RATE_LIMIT              = os.environ.get('LOGIN_RATE_LIMIT', '5 per minute')
    API_LOGIN_RATE_LIMIT          = os.environ.get('API_LOGIN_RATE_LIMIT', '5 per minute')
    MFA_VERIFY_RATE_LIMIT         = os.environ.get('MFA_VERIFY_RATE_LIMIT', '5 per minute')
    REGISTER_RATE_LIMIT           = os.environ.get('REGISTER_RATE_LIMIT', '5 per minute')
    RESEND_ACTIVATION_RATE_LIMIT  = os.environ.get('RESEND_ACTIVATION_RATE_LIMIT', '3 per 15 minute')
    FORGOT_PASSWORD_RATE_LIMIT    = os.environ.get('FORGOT_PASSWORD_RATE_LIMIT', '3 per 15 minute')
    RESET_PASSWORD_RATE_LIMIT     = os.environ.get('RESET_PASSWORD_RATE_LIMIT', '5 per 15 minute')
    PIN_SET_RATE_LIMIT            = os.environ.get('PIN_SET_RATE_LIMIT', '10 per minute')
    PIN_DELETE_RATE_LIMIT         = os.environ.get('PIN_DELETE_RATE_LIMIT', '10 per minute')
    PIN_LOGIN_RATE_LIMIT          = os.environ.get('PIN_LOGIN_RATE_LIMIT', '5 per minute')
    BACKUP_EXPORT_RATE_LIMIT      = os.environ.get('BACKUP_EXPORT_RATE_LIMIT', '5 per hour')
    BACKUP_RESTORE_RATE_LIMIT     = os.environ.get('BACKUP_RESTORE_RATE_LIMIT', '5 per hour')
    AI_TEST_CONNECTION_RATE_LIMIT = os.environ.get('AI_TEST_CONNECTION_RATE_LIMIT', '10 per minute')
    TELEGRAM_WEBHOOK_RATE_LIMIT   = os.environ.get('TELEGRAM_WEBHOOK_RATE_LIMIT', '60 per minute')
    TELEGRAM_LINK_CODE_RATE_LIMIT = os.environ.get('TELEGRAM_LINK_CODE_RATE_LIMIT', '5 per 10 minute')

    # ── Lockout de cuenta por fuerza bruta en login (password + MFA) ───────────
    # Tras LOGIN_MAX_FAILS intentos fallidos (password o código MFA) la cuenta
    # queda bloqueada LOGIN_LOCK_MINUTES minutos, sin importar la IP de origen.
    LOGIN_MAX_FAILS    = int(os.environ.get('LOGIN_MAX_FAILS', '3'))
    LOGIN_LOCK_MINUTES = int(os.environ.get('LOGIN_LOCK_MINUTES', '30'))
