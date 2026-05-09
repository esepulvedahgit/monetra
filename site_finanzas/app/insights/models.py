"""Internal dataclasses used inside the insights pipeline.

These are NOT serialized directly to UI/API — see `schemas.py` for the
external DTOs. Keeping internal vs external separated lets us evolve the
pipeline without breaking consumers.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.insights.enums import Severity, Confidence, InsightCategory, AlertType, SignalType


@dataclass
class Signal:
    """Normalized output from analytics, before rule evaluation."""
    signal_type: SignalType
    value: float
    baseline: float | None
    confidence: Confidence
    source: str  # e.g. 'analytics.forecasting', 'analytics.anomalies'
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class Alert:
    """A user-facing alert produced by the rule engine."""
    alert_type: AlertType
    category: InsightCategory
    severity: Severity
    confidence: Confidence
    title: str
    message: str
    explanation: str
    recommended_action: str
    evidence: dict[str, Any] = field(default_factory=dict)
    source_signal: SignalType | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Insight:
    """Generic informational insight (not necessarily actionable)."""
    insight_type: str
    category: InsightCategory
    severity: Severity
    title: str
    message: str
    evidence: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Recommendation:
    """Suggested action attached to an alert or shown standalone."""
    text: str
    priority: int = 0  # higher = more urgent
    related_alert_type: AlertType | None = None
