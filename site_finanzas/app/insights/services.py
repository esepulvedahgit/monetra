"""Public facade for the insights module.

Routes (web), API endpoints and background jobs should only import from here.
This is the seam between the insights pipeline and the rest of the app —
internal models stay internal.
"""
from __future__ import annotations
import logging

from app.insights.engine import InsightEngine
from app.insights.schemas import AlertDTO, ForecastDTO, HealthScoreDTO
from app.insights.signals import data_maturity_from_months

log = logging.getLogger(__name__)


def get_dashboard_alerts(user_id: int, year: int, month: int,
                          limit: int | None = None) -> list[AlertDTO]:
    """Top alerts for the dashboard. `limit=None` returns all."""
    engine = InsightEngine()
    alerts = engine.generate_monthly_insights(user_id, year, month)
    dtos = [_alert_to_dto(a) for a in alerts]
    if limit is not None:
        dtos = dtos[:limit]
    return dtos


def get_monthly_forecast(user_id: int, year: int, month: int) -> ForecastDTO | None:
    """Projected income/expense/balance for the period. None if not enough data."""
    from app.analytics.forecasting import forecast_monthly
    try:
        f = forecast_monthly(user_id, year, month)
    except Exception:
        log.exception('forecast_monthly failed for user_id=%s', user_id)
        return None
    return ForecastDTO(
        expected_income=float(f.expected_income),
        expected_expense=float(f.expected_expense),
        expected_balance=float(f.expected_balance),
        projected_budget_usage_pct=f.projected_budget_usage_pct,
        method=f.method,
        confidence=f.confidence,
        evidence=f.evidence,
    )


def get_health_score(user_id: int, year: int, month: int) -> HealthScoreDTO | None:
    """Composite financial health score. None if calculation fails."""
    from app.analytics.scoring import calculate_health_score
    try:
        s = calculate_health_score(user_id, year, month)
    except Exception:
        log.exception('calculate_health_score failed for user_id=%s', user_id)
        return None
    return HealthScoreDTO(
        overall_score=int(s.overall_score),
        cashflow_score=int(s.cashflow_score),
        budget_score=int(s.budget_score),
        savings_score=int(s.savings_score),
        anomaly_score=int(s.anomaly_score),
        evidence=s.evidence,
    )


def get_data_maturity(user_id: int, year: int, month: int) -> dict:
    from app.analytics.features import build_feature_bundle
    try:
        bundle = build_feature_bundle(user_id, year, month)
        historical_months = int(bundle.historical_months or 0)
    except Exception:
        log.exception('build_feature_bundle failed for user_id=%s', user_id)
        historical_months = 0
    maturity = data_maturity_from_months(historical_months)
    return {
        'historical_months': historical_months,
        'data_maturity': maturity,
        'learning_mode': maturity == 'learning',
    }


def _alert_to_dto(alert) -> AlertDTO:
    return AlertDTO(
        type=alert.alert_type.value,
        category=alert.category.value,
        severity=alert.severity.value,
        confidence=alert.confidence.value,
        title=str(alert.title),
        message=str(alert.message),
        explanation=str(alert.explanation),
        recommended_action=str(alert.recommended_action),
        evidence=alert.evidence,
        created_at=alert.created_at,
    )
