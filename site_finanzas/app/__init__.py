from datetime import datetime, timezone, timedelta

from flask import Flask, render_template, request, session, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user, logout_user
from flask_wtf.csrf import CSRFProtect, CSRFError
from config import Config
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_babel import Babel, lazy_gettext as _l, gettext as _
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

    # Trust the X-Forwarded-For / X-Forwarded-Proto headers from the reverse proxy
    # (nginx, Traefik, Caddy…). Required so request.is_secure, get_remote_address
    # and SESSION_COOKIE_SECURE work correctly behind TLS termination.
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

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

    from app.audit import audit_bp
    app.register_blueprint(audit_bp)

    from app.usd import usd_bp
    app.register_blueprint(usd_bp)

    from app.analytics import analytics_bp
    app.register_blueprint(analytics_bp)

    from app.scanner import scanner_bp
    app.register_blueprint(scanner_bp)

    from app.backup import backup_bp
    app.register_blueprint(backup_bp)

    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        if current_user.is_authenticated:
            flash(_('La solicitud expiró. Por favor intenta de nuevo.'), 'warning')
            return redirect(request.referrer or url_for('main.dashboard'))
        flash(_('La sesión expiró. Por favor inicia sesión nuevamente.'), 'warning')
        return redirect(url_for('auth.login'))

    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(429)
    def too_many_requests(e):
        try:
            from flask_login import current_user as cu
            from app.audit.logger import log_event
            from app.audit.events import APP_RATE_LIMITED
            uid = cu.id if cu.is_authenticated else None
            log_event(APP_RATE_LIMITED, description=request.path, user_id=uid, request=request)
            db.session.commit()
        except Exception:
            pass
        return render_template('errors/429.html'), 429

    @app.errorhandler(500)
    def internal_error(e):
        db.session.rollback()
        try:
            from flask_login import current_user as cu
            from app.audit.logger import log_event
            from app.audit.events import APP_ERROR_500
            uid = cu.id if cu.is_authenticated else None
            log_event(APP_ERROR_500, description=str(e)[:200], user_id=uid, request=request)
            db.session.commit()
        except Exception:
            pass
        return render_template('errors/500.html'), 500

    import os
    if not app.testing:
        if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
            from app.scheduler import init_scheduler
            init_scheduler(app)

    from app.admin import admin_bp
    app.register_blueprint(admin_bp)

    @app.before_request
    def _enforce_session_validity():
        """Invalidate web sessions created before a DB restore, force-logout suspended users,
        and close sessions that have been inactive for longer than SESSION_INACTIVITY_TIMEOUT.

        After a restore, backup/routes.py sets app_config.sessions_valid_after = now().
        Any session cookie missing _login_at or stamped before that threshold is
        rejected so users cannot carry stale identity across a restore boundary.
        Wrapped in a broad try/except so a missing column never breaks the app.
        """
        try:
            if not current_user.is_authenticated:
                return
            # Force-logout suspended users even if they already have an active session
            if getattr(current_user, 'is_suspended', False):
                logout_user()
                session.clear()
                return redirect(url_for('auth.login'))
            # Inactivity timeout — skip /api routes (those use JWT with their own TTL)
            if not request.path.startswith('/api'):
                timeout = app.config.get('SESSION_INACTIVITY_TIMEOUT', 900)
                now = datetime.now(timezone.utc)
                last_str = session.get('_last_activity')
                if last_str is not None:
                    last = datetime.fromisoformat(last_str)
                    if last.tzinfo is None:
                        last = last.replace(tzinfo=timezone.utc)
                    if (now - last) > timedelta(seconds=timeout):
                        logout_user()
                        session.clear()
                        flash(_('Tu sesión expiró por inactividad. Inicia sesión nuevamente.'), 'warning')
                        return redirect(url_for('auth.login'))
                # Renew activity timestamp on every authenticated non-API request
                session['_last_activity'] = now.isoformat()
            from app.models import AppConfig
            config = AppConfig.get()
            valid_after = getattr(config, 'sessions_valid_after', None)
            if valid_after is None:
                return
            if valid_after.tzinfo is None:
                valid_after = valid_after.replace(tzinfo=timezone.utc)
            login_at_str = session.get('_login_at')
            if login_at_str is None:
                # Pre-fix session without timestamp — invalidate after a restore
                logout_user()
                session.clear()
                return redirect(url_for('auth.login'))
            login_at = datetime.fromisoformat(login_at_str)
            if login_at.tzinfo is None:
                login_at = login_at.replace(tzinfo=timezone.utc)
            if login_at < valid_after:
                logout_user()
                session.clear()
                return redirect(url_for('auth.login'))
        except Exception:
            pass

    return app
