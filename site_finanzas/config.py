import os
import secrets


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
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

    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or secrets.token_hex(32)
    JWT_ACCESS_TOKEN_EXPIRES = 900        # 15 min
    JWT_REFRESH_TOKEN_EXPIRES = 2592000   # 30 días
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*').split(',')
