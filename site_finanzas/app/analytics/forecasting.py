"""Monthly forecasting with automatic fallback by data availability.

Strategy:
    < 3 months of history → naive extrapolation from current month's pace
    3-5 months           → weighted moving average
    >= 6 months          → linear trend (slope + last-value baseline)
    >= 12 months (future, Phase 2) → RandomForestRegressor

Every result returns a MonthlyForecast with `method` + `confidence` + `evidence`.
The evidence dict is the auditable trail: which numbers fed the prediction.
"""
from __future__ import annotations
import logging

from app.analytics.schemas import MonthlyForecast, FeatureBundle
from app.analytics.features import build_feature_bundle
from app.analytics.datasets import (
    build_history_window_expense_series,
    build_history_window_income_series,
)
from app.analytics.utils import (
    mean,
    weighted_moving_average,
    linear_trend,
)

log = logging.getLogger(__name__)


def forecast_monthly(user_id: int, year: int, month: int) -> MonthlyForecast:
    """Pick the right forecasting strategy based on variable history.

    Recurring income/expenses are known commitments and are added as a fixed
    base. Statistical projection is applied only to non-recurring activity.
    """
    bundle = build_feature_bundle(user_id, year, month)
    n = _variable_history_months(user_id, year, month)

    if n < 3:
        return _forecast_naive(bundle, n)
    if n < 6:
        return _forecast_weighted_avg(user_id, year, month, bundle, n)
    return _forecast_linear_trend(user_id, year, month, bundle, n)


# ── Strategies ────────────────────────────────────────────────────────────────

def _forecast_naive(bundle: FeatureBundle, variable_history_months: int) -> MonthlyForecast:
    """Extrapolate the current month's pace to month-end. Used when there
    isn't enough history to do anything else."""
    elapsed = bundle.month_elapsed_pct
    if elapsed <= 0:
        return _build_component_forecast(
            bundle,
            variable_income=0.0,
            variable_expense=0.0,
            method='known_recurring_only',
            confidence='low',
            evidence={
                'reason': 'future_period_or_no_elapsed_period_yet',
                'variable_historical_months': variable_history_months,
            },
        )

    factor = 100.0 / elapsed
    variable_income = round(bundle.variable_income * factor, 2)
    variable_expense = round(bundle.variable_expense * factor, 2)

    return _build_component_forecast(
        bundle,
        variable_income=variable_income,
        variable_expense=variable_expense,
        method='component_current_pace',
        confidence='low',
        evidence={
            'variable_historical_months': variable_history_months,
            'current_variable_income': bundle.variable_income,
            'current_variable_expense': bundle.variable_expense,
            'month_elapsed_pct': elapsed,
            'extrapolation_factor': round(factor, 3),
        },
    )


def _forecast_weighted_avg(user_id: int, year: int, month: int,
                            bundle: FeatureBundle,
                            variable_history_months: int) -> MonthlyForecast:
    """Weighted moving average over the last 5 months (excluding current).
    Newer months weigh more (linear weights 1..N)."""
    prior_y, prior_m = (year, month - 1) if month > 1 else (year - 1, 12)
    expense_hist = build_history_window_expense_series(
        user_id, prior_y, prior_m, months_back=5, include_recurring=False)
    income_hist = build_history_window_income_series(
        user_id, prior_y, prior_m, months_back=5, include_recurring=False)
    expense_hist = [x for x in expense_hist if x > 0]
    income_hist = [x for x in income_hist if x > 0]

    exp_expense = round(weighted_moving_average(expense_hist), 2) if expense_hist else 0.0
    exp_income = round(weighted_moving_average(income_hist), 2) if income_hist else 0.0
    return _build_component_forecast(
        bundle,
        variable_income=exp_income,
        variable_expense=exp_expense,
        method='component_weighted_moving_average',
        confidence='medium',
        evidence={
            'variable_historical_months': variable_history_months,
            'expense_series_used': expense_hist,
            'income_series_used': income_hist,
            'weights_scheme': 'linear (1..N, newest=N)',
            'current_month_progress_pct': bundle.month_elapsed_pct,
        },
    )


def _forecast_linear_trend(user_id: int, year: int, month: int,
                            bundle: FeatureBundle,
                            variable_history_months: int) -> MonthlyForecast:
    """Linear regression on the last 12 months (excluding current).
    Predicts the next index; falls back to mean if slope is flat."""
    prior_y, prior_m = (year, month - 1) if month > 1 else (year - 1, 12)
    expense_hist = build_history_window_expense_series(
        user_id, prior_y, prior_m, months_back=12, include_recurring=False)
    income_hist = build_history_window_income_series(
        user_id, prior_y, prior_m, months_back=12, include_recurring=False)

    # Strip leading zeros (months with no data) so the trend isn't dragged down.
    def _clean(xs):
        for i, v in enumerate(xs):
            if v > 0:
                return xs[i:]
        return []

    expense_clean = _clean(expense_hist)
    income_clean = _clean(income_hist)

    def _predict_next(series):
        if not series:
            return 0.0
        if len(series) == 1:
            return series[0]
        slope, intercept = linear_trend(series)
        next_idx = len(series)
        prediction = slope * next_idx + intercept
        # Clamp to non-negative (income/expense can't be negative)
        return max(0.0, round(prediction, 2))

    exp_expense = _predict_next(expense_clean)
    exp_income = _predict_next(income_clean)
    expense_slope, _ = linear_trend(expense_clean) if len(expense_clean) >= 2 else (0.0, 0.0)
    income_slope, _ = linear_trend(income_clean) if len(income_clean) >= 2 else (0.0, 0.0)

    return _build_component_forecast(
        bundle,
        variable_income=exp_income,
        variable_expense=exp_expense,
        method='component_linear_trend',
        confidence='high',
        evidence={
            'variable_historical_months': variable_history_months,
            'expense_series_used': expense_clean,
            'income_series_used': income_clean,
            'expense_slope_per_month': round(expense_slope, 2),
            'income_slope_per_month': round(income_slope, 2),
            'mean_expense_baseline': round(mean(expense_clean), 2) if expense_clean else 0.0,
            'mean_income_baseline': round(mean(income_clean), 2) if income_clean else 0.0,
        },
    )


def _variable_history_months(user_id: int, year: int, month: int) -> int:
    prior_y, prior_m = (year, month - 1) if month > 1 else (year - 1, 12)
    expense = build_history_window_expense_series(
        user_id, prior_y, prior_m, months_back=12, include_recurring=False)
    income = build_history_window_income_series(
        user_id, prior_y, prior_m, months_back=12, include_recurring=False)
    return sum(1 for i in range(len(expense)) if expense[i] > 0 or income[i] > 0)


def _build_component_forecast(bundle: FeatureBundle, variable_income: float,
                              variable_expense: float, method: str,
                              confidence: str, evidence: dict) -> MonthlyForecast:
    expected_income = round(bundle.recurring_income + variable_income, 2)
    expected_expense = round(bundle.recurring_expense + variable_expense, 2)
    expected_balance = round(expected_income - expected_expense, 2)
    projected = (round(expected_expense / bundle.budget_amount * 100, 1)
                 if bundle.budget_amount and bundle.budget_amount > 0 else None)
    evidence = {
        **evidence,
        'recurring_income_known': round(bundle.recurring_income, 2),
        'recurring_expense_known': round(bundle.recurring_expense, 2),
        'variable_income_projected': round(variable_income, 2),
        'variable_expense_projected': round(variable_expense, 2),
        'budget_amount': bundle.budget_amount,
    }
    return MonthlyForecast(
        expected_income=expected_income,
        expected_expense=expected_expense,
        expected_balance=expected_balance,
        projected_budget_usage_pct=projected,
        method=method,
        confidence=confidence,
        evidence=evidence,
    )
