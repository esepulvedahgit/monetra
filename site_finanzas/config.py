import os
import secrets


def _require_https_origin(env_var: str, default: str) -> str:
    value = os.environ.get(env_var, default)
    if os.environ.get('FLASK_DEBUG', '0') == '0' and not value.startswith('https://'):
        raise RuntimeError(
            f"'{env_var}' debe comenzar con https:// en producción. "
            f"Valor actual: '{value}'. Agrégala al archivo docker/.env."
        )
    return value


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
            password=os.environ.get('DB_PASSWORD', 'FinanzasPass123!'),
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

    # WebAuthn / Passkeys — MUST match deployment domain in production
    WEBAUTHN_RP_ID   = os.environ.get('WEBAUTHN_RP_ID',   'localhost')
    WEBAUTHN_RP_NAME = os.environ.get('WEBAUTHN_RP_NAME', 'Monetra')
    WEBAUTHN_ORIGIN  = _require_https_origin('WEBAUTHN_ORIGIN', 'http://localhost:5000')

    JWT_SECRET_KEY = _require_key('JWT_SECRET_KEY')
    JWT_ACCESS_TOKEN_EXPIRES = 900        # 15 min
    JWT_REFRESH_TOKEN_EXPIRES = 2592000   # 30 días
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*').split(',')
