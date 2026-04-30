from flask import Flask, render_template, request, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from flask_wtf.csrf import CSRFProtect
from config import Config
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_babel import Babel, lazy_gettext as _l
from flask_jwt_extended import JWTManager
from flask_cors import CORS

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address)
babel = Babel()
jwt = JWTManager()


def get_locale():
    try:
        if current_user.is_authenticated and current_user.language:
            return current_user.language
    except Exception:
        pass
    try:
        lang = session.get('lang')
        if lang in ('es', 'en'):
            return lang
        return request.accept_languages.best_match(['es', 'en'], default='es')
    except Exception:
        return 'es'


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    babel.init_app(app, locale_selector=get_locale)
    jwt.init_app(app)
    CORS(app, resources={r"/api/*": {"origins": app.config['CORS_ORIGINS']}})

    login_manager.login_view = 'auth.login'
    login_manager.login_message = _l('Por favor inicia sesión para acceder.')
    login_manager.login_message_category = 'info'

    @app.template_filter('month_name')
    def month_name_filter(month_num):
        try:
            from babel.dates import get_month_names
            locale = get_locale() or 'es'
            names = get_month_names('wide', locale=str(locale))
            n = int(month_num)
            return names[n].capitalize() if 0 < n <= 12 else ''
        except Exception:
            names = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                     'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
            return names[int(month_num)] if 0 < int(month_num) <= 12 else ''

    @app.template_filter('money')
    def money_filter(amount):
        try:
            value = float(amount)
        except (TypeError, ValueError):
            return str(amount)
        if current_user.is_authenticated:
            code = current_user.currency_code or 'USD'
            locale = current_user.currency_locale or 'es'
            symbol = current_user.currency_symbol or '$'
        else:
            code, locale, symbol = 'USD', 'en_US', '$'
        try:
            from babel.numbers import format_decimal, get_currency_precision
            decimals = get_currency_precision(code)
            fmt = '#,##0' + ('.' + '0' * decimals if decimals > 0 else '')
            return symbol + format_decimal(value, fmt, locale=locale)
        except Exception:
            return f"{symbol}{value:.2f}"

    @app.context_processor
    def inject_get_locale():
        return dict(get_locale=get_locale)

    from app.auth import auth as auth_blueprint
    app.register_blueprint(auth_blueprint)

    from app.main import main as main_blueprint
    app.register_blueprint(main_blueprint)

    from app.demo_data import demo_data_bp
    app.register_blueprint(demo_data_bp)

    from app.demo_data.cli import register_cli
    register_cli(app)

    from app.api import api_v1
    app.register_blueprint(api_v1)
    csrf.exempt(api_v1)

    from app.export import export_bp
    app.register_blueprint(export_bp)

    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(429)
    def too_many_requests(e):
        return render_template('errors/429.html'), 429

    @app.errorhandler(500)
    def internal_error(e):
        db.session.rollback()
        return render_template('errors/500.html'), 500

    import os
    if not app.testing:
        if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
            from app.scheduler import init_scheduler
            init_scheduler(app)

    return app
