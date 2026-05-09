"""Sustainable savings capacity.

This is a conservative planning metric, not a month-end forecast. It estimates
how much the user can safely commit to goals every month using stable income,
known recurring expenses and historical variable behavior.
"""
from __future__ import annotations

from app.analytics.datasets import (
    build_history_window_expense_series,
    build_history_window_income_series,
    get_recurring_totals_for_month,
)
from app.analytics.utils import mean


VARIABLE_HISTORY_MONTHS = 6
VARIABLE_INCOME_HAIRCUT = 0.80
VARIABLE_EXPENSE_STRESS = 1.10
SAFETY_BUFFER_PCT = 0.10


def calculate_sustainable_savings_capacity(user_id: int, year: int, month: int) -> dict:
    """Return a conservative monthly savings capacity with auditable evidence."""
    prior_y, prior_m = (year, month - 1) if month > 1 else (year - 1, 12)
    recurring = get_recurring_totals_for_month(user_id, year, month)

    variable_income_series = build_history_window_income_series(
        user_id, prior_y, prior_m, months_back=VARIABLE_HISTORY_MONTHS,
        include_recurring=False,
    )
    variable_expense_series = build_history_window_expense_series(
        user_id, prior_y, prior_m, months_back=VARIABLE_HISTORY_MONTHS,
        include_recurring=False,
    )

    variable_months = sum(
        1 for i in range(VARIABLE_HISTORY_MONTHS)
        if variable_income_series[i] > 0 or variable_expense_series[i] > 0
    )
    variable_income_baseline = _positive_mean(variable_income_series) * VARIABLE_INCOME_HAIRCUT
    variable_expense_baseline = _positive_mean(variable_expense_series) * VARIABLE_EXPENSE_STRESS

    stable_income = recurring['income']
    fixed_expense = recurring['expense']
    safety_buffer = stable_income * SAFETY_BUFFER_PCT
    capacity = stable_income + variable_income_baseline - fixed_expense - variable_expense_baseline - safety_buffer

    return {
        'stable_income': round(stable_income, 2),
        'variable_income_baseline': round(variable_income_baseline, 2),
        'fixed_expense': round(fixed_expense, 2),
        'variable_expense_baseline': round(variable_expense_baseline, 2),
        'safety_buffer': round(safety_buffer, 2),
        'sustainable_capacity': round(max(capacity, 0.0), 2),
        'raw_capacity': round(capacity, 2),
        'confidence': _confidence(variable_months),
        'evidence': {
            'variable_months_available': variable_months,
            'variable_history_months': VARIABLE_HISTORY_MONTHS,
            'variable_income_series': variable_income_series,
            'variable_expense_series': variable_expense_series,
            'variable_income_haircut': VARIABLE_INCOME_HAIRCUT,
            'variable_expense_stress': VARIABLE_EXPENSE_STRESS,
            'safety_buffer_pct': SAFETY_BUFFER_PCT,
        },
    }


def _positive_mean(series: list[float]) -> float:
    values = [x for x in series if x > 0]
    return mean(values) if values else 0.0


def _confidence(variable_months: int) -> str:
    if variable_months >= 6:
        return 'high'
    if variable_months >= 3:
        return 'medium'
    return 'low'
