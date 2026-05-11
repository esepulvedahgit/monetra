"""Build normalized Signals from analytics output.

A Signal is the intermediate representation between "raw analytics result"
and "user-facing alert". The rule engine consumes Signals — it never sees
analytics DTOs directly. This decoupling lets analytics evolve (new methods,
new evidence shape) without breaking rules.
"""
from __future__ import annotations
import logging

from app.insights.models import Signal
from app.insights.enums import SignalType, Confidence

log = logging.getLogger(__name__)


def _to_confidence(value: str | None) -> Confidence:
    if value == 'high':
        return Confidence.HIGH
    if value == 'low':
        return Confidence.LOW
    return Confidence.MEDIUM


def data_maturity_from_months(historical_months: int) -> str:
    if historical_months < 3:
        return 'learning'
    if historical_months < 6:
        return 'building'
    return 'stable'


def _maturity_evidence(historical_months: int) -> dict:
    return {
        'historical_months': historical_months,
        'data_maturity': data_maturity_from_months(historical_months),
        'learning_mode': historical_months < 3,
    }


def build_signals(user_id: int, year: int, month: int) -> list[Signal]:
    """Pull analytics results and convert each into a normalized Signal."""
    from app.analytics.features import build_feature_bundle
    from app.analytics.forecasting import forecast_monthly
    from app.analytics.anomalies import detect_anomalies
    from app.analytics.capacity import calculate_sustainable_savings_capacity
    from app.analytics.datasets import build_history_window_expense_series
    from app.analytics.savings_goals import analyze_savings_goals

    signals: list[Signal] = []

    bundle = build_feature_bundle(user_id, year, month)
    forecast = forecast_monthly(user_id, year, month)
    capacity = calculate_sustainable_savings_capacity(user_id, year, month)
    anomalies = detect_anomalies(user_id, year, month)

    maturity = _maturity_evidence(bundle.historical_months)

    signals.extend(_signals_from_setup_check(bundle, maturity))
    signals.extend(_signals_from_forecast(forecast, bundle, maturity))
    signals.extend(_signals_from_bundle(bundle, maturity))
    signals.extend(_signals_from_goals(
        analyze_savings_goals(user_id, capacity['sustainable_capacity']), capacity, maturity))
    signals.extend(_signals_from_anomalies(anomalies, maturity))
    signals.extend(_signals_from_trend(user_id, year, month, bundle))

    log.debug('Built %d signals for user_id=%s period=%s-%02d',
              len(signals), user_id, year, month)
    return signals


# ── From setup check ─────────────────────────────────────────────────────────

def _signals_from_setup_check(bundle, maturity: dict) -> list[Signal]:
    """Emit an INFO signal when basic configuration is missing.

    Only relevant during early months — once the user has ≥3 months of data
    and recurring activity, this signal stops being generated.
    """
    missing: list[str] = []
    if not bundle.budget_amount or bundle.budget_amount <= 0:
        missing.append('budget')
    if bundle.recurring_expense == 0 and bundle.historical_months < 3:
        missing.append('recurring')
    if not missing:
        return []
    return [Signal(
        signal_type=SignalType.MISSING_SETUP,
        value=float(len(missing)),
        baseline=0.0,
        confidence=Confidence.HIGH,
        source='analytics.setup_check',
        evidence={
            'missing_items': missing,
            'has_budget': bool(bundle.budget_amount and bundle.budget_amount > 0),
            'has_recurring': bundle.recurring_expense > 0,
            **maturity,
        },
    )]


# ── From forecast ────────────────────────────────────────────────────────────

def _signals_from_forecast(forecast, bundle, maturity: dict) -> list[Signal]:
    out: list[Signal] = []
    conf = _to_confidence(forecast.confidence)

    # Projected deficit: expected balance < 0
    out.append(Signal(
        signal_type=SignalType.PROJECTED_DEFICIT,
        value=float(forecast.expected_balance),
        baseline=0.0,
        confidence=conf,
        source='analytics.forecasting',
        evidence={
            'expected_income': forecast.expected_income,
            'expected_expense': forecast.expected_expense,
            'expected_balance': forecast.expected_balance,
            'method': forecast.method,
            **maturity,
            **forecast.evidence,
        },
    ))

    # Budget burn rate: only meaningful if a budget exists
    if bundle.budget_amount and bundle.budget_amount > 0 and forecast.projected_budget_usage_pct is not None:
        out.append(Signal(
            signal_type=SignalType.BUDGET_BURN_RATE,
            value=float(forecast.projected_budget_usage_pct),
            baseline=float(bundle.month_elapsed_pct or 0),
            confidence=conf,
            source='analytics.forecasting',
            evidence={
                'projected_pct': forecast.projected_budget_usage_pct,
                'budget_used_pct': bundle.budget_used_pct or 0,
                'month_elapsed_pct': bundle.month_elapsed_pct,
                'budget_amount': bundle.budget_amount,
                'expected_expense': forecast.expected_expense,
                'method': forecast.method,
                **maturity,
            },
        ))

    return out


def _signals_from_goals(goal_analysis: dict, capacity: dict, maturity: dict) -> list[Signal]:
    if not goal_analysis.get('active_count'):
        return []
    if not goal_analysis.get('overdue_count') and not goal_analysis.get('at_risk_count'):
        return []

    priority_goal = next(
        (g for g in goal_analysis['goals'] if g['status'] == 'overdue'),
        None,
    ) or next(
        (g for g in goal_analysis['goals'] if g['status'] == 'at_risk'),
        goal_analysis['goals'][0],
    )
    coverage = goal_analysis.get('coverage_pct')
    return [Signal(
        signal_type=SignalType.SAVINGS_GOAL_RISK,
        value=float(coverage if coverage is not None else 0),
        baseline=100.0,
        confidence=Confidence.HIGH,
        source='analytics.savings_goals',
        evidence={
            **goal_analysis,
            **maturity,
            'sustainable_capacity': capacity,
            'priority_goal': priority_goal,
        },
    )]


# ── From feature bundle ──────────────────────────────────────────────────────

def _signals_from_bundle(bundle, maturity: dict) -> list[Signal]:
    out: list[Signal] = []

    # Savings rate
    if bundle.total_income > 0:
        rate = ((bundle.total_income - bundle.total_expense) / bundle.total_income) * 100.0
        out.append(Signal(
            signal_type=SignalType.LOW_SAVINGS_RATE,
            value=round(rate, 2),
            baseline=10.0,
            confidence=Confidence.HIGH,
            source='analytics.features',
            evidence={
                'savings_rate_pct': round(rate, 2),
                'total_income': bundle.total_income,
                'total_expense': bundle.total_expense,
                **maturity,
            },
        ))

    return out


# ── From anomalies ───────────────────────────────────────────────────────────

def _signals_from_anomalies(anomalies, maturity: dict) -> list[Signal]:
    out: list[Signal] = []
    for a in anomalies:
        conf = _to_confidence(a.confidence)
        if a.anomaly_type == 'category_spike':
            stype = SignalType.CATEGORY_SPIKE
        elif a.anomaly_type == 'unusual_transaction':
            stype = SignalType.UNUSUAL_TRANSACTION
        elif a.anomaly_type == 'duplicate_suspected':
            stype = SignalType.DUPLICATE_SUSPECTED
        else:
            continue
        out.append(Signal(
            signal_type=stype,
            value=float(a.value),
            baseline=float(a.baseline) if a.baseline is not None else None,
            confidence=conf,
            source='analytics.anomalies',
            evidence={
                'category_id': a.category_id,
                'category_name': a.category_name,
                'deviation_pct': a.deviation_pct,
                'method': a.method,
                **maturity,
                **a.evidence,
            },
        ))
    return out


# ── From multi-month trend ──────────────────────────────────────────────────

def _signals_from_trend(user_id: int, year: int, month: int, bundle) -> list[Signal]:
    """Negative cashflow trend: 3 of last 4 months ended negative."""
    from app.analytics.datasets import build_history_window_expense_series
    if bundle.historical_months < 3:
        return []
    expense = build_history_window_expense_series(user_id, year, month, months_back=4)
    # Approximation: rising expense series w/o income parity → negative trend
    nonzero = [x for x in expense if x > 0]
    if len(nonzero) < 3:
        return []
    # Simple slope check: expenses growing month over month
    rising = sum(1 for i in range(1, len(nonzero)) if nonzero[i] > nonzero[i - 1])
    if rising >= len(nonzero) - 1 and len(nonzero) >= 3:
        return [Signal(
            signal_type=SignalType.NEGATIVE_CASHFLOW_TREND,
            value=float(nonzero[-1]),
            baseline=float(nonzero[0]),
            confidence=Confidence.MEDIUM,
            source='analytics.datasets',
            evidence={
                'expense_series': nonzero,
                'months_evaluated': len(nonzero),
                'months_rising': rising,
            },
        )]
    return []
