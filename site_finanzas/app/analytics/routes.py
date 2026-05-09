import logging
from datetime import date
from flask import render_template, redirect, url_for, flash, session
from flask_login import login_required, current_user
from flask_babel import gettext as _

log = logging.getLogger(__name__)

from app.analytics import analytics_bp
from app.analytics.services import get_consolidated_summary


def _period():
    today = date.today()
    return (
        int(session.get('selected_year', today.year)),
        int(session.get('selected_month', today.month)),
    )


@analytics_bp.route('/consolidated')
@login_required
def consolidated():
    # Si la moneda principal NO es USD, requiere tasa configurada para convertir.
    if current_user.currency_code != 'USD' and not current_user.usd_rate:
        flash(_('Configura el valor del dólar en Configuración antes de ver el consolidado.'), 'warning')
        return redirect(url_for('main.configurar'))

    year, month = _period()
    data = get_consolidated_summary(current_user.id, year, month)

    return render_template(
        'analytics/consolidated.html',
        year=year,
        month=month,
        title=_('Consolidado'),
        **data,
    )


@analytics_bp.route('/dashboard')
@login_required
def dashboard():
    """Vista de Analítica completa: alertas, forecast, health score y evidencia."""
    from app.insights import services as insights_svc
    year, month = _period()
    try:
        alerts = insights_svc.get_dashboard_alerts(current_user.id, year, month)
    except Exception:
        log.exception('get_dashboard_alerts failed for user_id=%s', current_user.id)
        alerts = []
    try:
        forecast = insights_svc.get_monthly_forecast(current_user.id, year, month)
    except Exception:
        log.exception('get_monthly_forecast failed for user_id=%s', current_user.id)
        forecast = None
    try:
        health = insights_svc.get_health_score(current_user.id, year, month)
    except Exception:
        log.exception('get_health_score failed for user_id=%s', current_user.id)
        health = None

    return render_template(
        'analytics/dashboard.html',
        year=year,
        month=month,
        title=_('Analítica'),
        alerts=alerts,
        forecast=forecast,
        health=health,
    )
