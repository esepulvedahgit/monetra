"""Explainable composite financial health score.

Range: 0–100. Built from four transparent sub-scores so the user (and we)
can see exactly why the number moved:

    cashflow_score  — months with positive balance over the last 6
    budget_score    — adherence to monthly budget for the period
    savings_score   — savings rate + active goal viability
    anomaly_score   — penalty per significant anomaly detected

Weights are deliberate (cashflow > budget > savings > anomaly) and live as
constants in this file so they're easy to find and tweak.
"""
from __future__ import annotations

from app.analytics.schemas import FinancialHealthScore
from app.analytics.features import build_feature_bundle
from app.analytics.datasets import build_history_window_income_series, build_history_window_expense_series
from app.analytics.anomalies import detect_anomalies


# Weights sum to 1.0
W_CASHFLOW = 0.35
W_BUDGET = 0.25
W_SAVINGS = 0.25
W_ANOMALY = 0.15

# Anomaly penalty: 10 pts off per significant anomaly (cap floor at 0).
ANOMALY_PENALTY = 10
SAVINGS_TARGET_PCT = 15.0  # tasa "saludable"


def calculate_health_score(user_id: int, year: int, month: int) -> FinancialHealthScore:
    bundle = build_feature_bundle(user_id, year, month)

    cashflow_score, cashflow_evidence = _cashflow_subscore(user_id, year, month)
    budget_score, budget_evidence = _budget_subscore(bundle)
    savings_score, savings_evidence = _savings_subscore(bundle)
    anomaly_score, anomaly_evidence = _anomaly_subscore(user_id, year, month)

    overall = round(
        cashflow_score * W_CASHFLOW
        + budget_score * W_BUDGET
        + savings_score * W_SAVINGS
        + anomaly_score * W_ANOMALY
    )

    return FinancialHealthScore(
        overall_score=int(max(0, min(100, overall))),
        cashflow_score=cashflow_score,
        budget_score=budget_score,
        savings_score=savings_score,
        anomaly_score=anomaly_score,
        evidence={
            'weights': {'cashflow': W_CASHFLOW, 'budget': W_BUDGET,
                        'savings': W_SAVINGS, 'anomaly': W_ANOMALY},
            'cashflow': cashflow_evidence,
            'budget': budget_evidence,
            'savings': savings_evidence,
            'anomaly': anomaly_evidence,
            'historical_months_available': bundle.historical_months,
        },
    )


# ── Sub-scores ────────────────────────────────────────────────────────────────

def _cashflow_subscore(user_id: int, year: int, month: int) -> tuple[int, dict]:
    """Ratio of months with positive balance over the last 6 (incl. current)."""
    income = build_history_window_income_series(user_id, year, month, months_back=6)
    expense = build_history_window_expense_series(user_id, year, month, months_back=6)
    months_with_data = sum(1 for i in range(len(income)) if income[i] > 0 or expense[i] > 0)
    if months_with_data == 0:
        return 50, {'reason': 'no_data', 'fallback_score': 50}
    positive = sum(1 for i in range(len(income)) if (income[i] - expense[i]) > 0)
    score = int(round(positive / months_with_data * 100))
    return score, {
        'months_evaluated': months_with_data,
        'months_with_positive_balance': positive,
        'income_series': income,
        'expense_series': expense,
    }


def _budget_subscore(bundle) -> tuple[int, dict]:
    """100 if at or under budget at month-end pace, decays to 0 at 200% usage.
    Returns 70 (neutral) if no budget set."""
    if not bundle.budget_amount or bundle.budget_amount <= 0:
        return 70, {'reason': 'no_budget_configured', 'fallback_score': 70}
    used_pct = bundle.budget_used_pct or 0
    elapsed = bundle.month_elapsed_pct or 100
    # Fair pace = used_pct equal to elapsed_pct. Penalize the gap.
    gap = used_pct - elapsed
    if gap <= 0:
        score = 100
    else:
        # Linear decay: every 1pp over → -1.5 score points (so +66pp → 0)
        score = max(0, int(round(100 - gap * 1.5)))
    return score, {
        'budget_amount': bundle.budget_amount,
        'budget_used_pct': used_pct,
        'month_elapsed_pct': elapsed,
        'gap_pp': round(gap, 1),
    }


def _savings_subscore(bundle) -> tuple[int, dict]:
    """Savings rate vs target plus active savings-goal viability."""
    from app.analytics.capacity import calculate_sustainable_savings_capacity
    from app.analytics.savings_goals import analyze_savings_goals

    if bundle.total_income <= 0:
        rate_score = 30
        rate_evidence = {'reason': 'no_income', 'fallback_score': 30}
    else:
        rate = ((bundle.total_income - bundle.total_expense) / bundle.total_income) * 100.0
        if rate <= 0:
            rate_score = 0
        else:
            rate_score = min(100, int(round(rate / SAVINGS_TARGET_PCT * 100)))
        rate_evidence = {
            'total_income': bundle.total_income,
            'total_expense': bundle.total_expense,
            'savings_rate_pct': round(rate, 2),
            'target_rate_pct': SAVINGS_TARGET_PCT,
        }

    capacity = calculate_sustainable_savings_capacity(
        bundle.user_id, bundle.period_year, bundle.period_month)
    goals = analyze_savings_goals(bundle.user_id, capacity['sustainable_capacity'])
    score = int(round(rate_score * 0.6 + goals['score'] * 0.4))
    return score, {
        **rate_evidence,
        'rate_score': rate_score,
        'sustainable_capacity': capacity,
        'goals_score': goals['score'],
        'goals': goals,
        'weights': {'savings_rate': 0.6, 'goals_viability': 0.4},
    }


def _anomaly_subscore(user_id: int, year: int, month: int) -> tuple[int, dict]:
    """100 baseline minus penalty per significant anomaly (medium/high)."""
    anomalies = detect_anomalies(user_id, year, month)
    significant = [a for a in anomalies if a.confidence in ('medium', 'high')]
    score = max(0, 100 - len(significant) * ANOMALY_PENALTY)
    return score, {
        'anomalies_detected_total': len(anomalies),
        'anomalies_significant': len(significant),
        'penalty_per_anomaly': ANOMALY_PENALTY,
        'types': [a.anomaly_type for a in significant],
    }
