"""External DTOs for UI templates and the future API.

These mirror the internal `models.py` structures but use plain strings
instead of enums and primitive floats instead of Decimals so they
serialize cleanly to JSON and play well with Jinja2.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any


@dataclass
class AlertDTO:
    type: str
    category: str
    severity: str
    confidence: str
    title: str
    message: str
    explanation: str
    recommended_action: str
    evidence: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None

    def to_dict(self) -> dict:
        d = asdict(self)
        if self.created_at:
            d['created_at'] = self.created_at.isoformat()
        return d


@dataclass
class ForecastDTO:
    expected_income: float
    expected_expense: float
    expected_balance: float
    projected_budget_usage_pct: float | None
    method: str
    confidence: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class HealthScoreDTO:
    overall_score: int
    cashflow_score: int
    budget_score: int
    savings_score: int
    anomaly_score: int
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SignalDTO:
    """Exposed only when the API caller wants raw signals (debugging/audit)."""
    signal_type: str
    value: float
    baseline: float | None
    confidence: str
    source: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)
