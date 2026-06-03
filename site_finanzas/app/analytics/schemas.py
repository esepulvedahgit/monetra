"""Internal DTOs for the analytics module.

These dataclasses are the contract between analytics submodules (features,
forecasting, anomalies, scoring) and the insights module that consumes them.
Every result that leaves analytics carries an `evidence` dict so it can be
audited downstream.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FeatureBundle:
    """Financial variables for a period, ready for forecasting/scoring/rules."""
    user_id: int
    period_year: int
    period_month: int
    total_income: float
    total_expense: float
    balance: float
    budget_amount: float | None
    budget_used_pct: float | None
    month_elapsed_pct: float
    daily_avg_expense: float
    historical_months: int
    by_category: dict[int, dict] = field(default_factory=dict)
    recurring_income: float = 0.0
    recurring_expense: float = 0.0
    variable_income: float = 0.0
    variable_expense: float = 0.0
    # Each entry: {name, total, mean_hist, std_hist, pct_change}


@dataclass
class MonthlyForecast:
    expected_income: float
    expected_expense: float
    expected_balance: float
    projected_budget_usage_pct: float | None
    method: str
    confidence: str
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class AnomalyResult:
    anomaly_type: str
    category_id: int | None
    category_name: str | None
    value: float
    baseline: float
    deviation_pct: float
    method: str
    confidence: str
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class FinancialHealthScore:
    overall_score: int
    cashflow_score: int
    budget_score: int
    savings_score: int
    anomaly_score: int
    evidence: dict[str, Any] = field(default_factory=dict)
