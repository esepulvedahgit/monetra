from datetime import date
from flask import request, jsonify
from app.api import api_v1
from app.api.decorators import api_login_required, get_current_api_user


def _alert_to_dict(a):
    return {
        "alert_type": a.alert_type.value if hasattr(a.alert_type, "value") else str(a.alert_type),
        "severity": a.severity.value if hasattr(a.severity, "value") else str(a.severity),
        "category": a.category.value if hasattr(a.category, "value") else str(a.category),
        "title": a.title,
        "message": a.message,
        "evidence": a.evidence,
    }


@api_v1.get("/insights")
@api_login_required
def insights():
    """Financial health, forecast and alerts for a given month.

    Query params: year (int), month (int). Defaults to current month.
    """
    user = get_current_api_user()
    today = date.today()
    try:
        year = int(request.args.get("year", today.year))
        month = int(request.args.get("month", today.month))
        if not (1 <= month <= 12):
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"error": "year y month deben ser enteros válidos"}), 400

    from app.insights import services as svc

    alerts_raw = svc.get_dashboard_alerts(user.id, year, month)
    forecast = svc.get_monthly_forecast(user.id, year, month)
    health = svc.get_health_score(user.id, year, month)
    maturity = svc.get_data_maturity(user.id, year, month)

    return jsonify({
        "year": year,
        "month": month,
        "maturity": maturity,
        "health": {
            "overall_score": health.overall_score,
            "cashflow_score": health.cashflow_score,
            "budget_score": health.budget_score,
            "savings_score": health.savings_score,
            "anomaly_score": health.anomaly_score,
            "evidence": health.evidence,
        } if health else None,
        "forecast": {
            "expected_income": forecast.expected_income,
            "expected_expense": forecast.expected_expense,
            "expected_balance": forecast.expected_balance,
            "projected_budget_usage_pct": forecast.projected_budget_usage_pct,
            "method": forecast.method,
            "confidence": forecast.confidence,
            "evidence": forecast.evidence,
        } if forecast else None,
        "alerts": [_alert_to_dict(a) for a in alerts_raw],
        "alert_count": len(alerts_raw),
    }), 200
