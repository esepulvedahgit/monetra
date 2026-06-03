"""Centralized severity classification.

The SeverityClassifier is the single place where thresholds live.  Other
modules call it; they do not embed their own `if x > 25 ...` checks. If the
business wants to tune when an alert becomes critical, this is the only file
that changes.

STUB (Chunk 1): structure + thresholds as constants. Real branching lives in
Chunk 3 (signature kept stable so callers compile).
"""
from __future__ import annotations
from app.insights.enums import Severity, Confidence


# Thresholds — single source of truth. Tweak here, not in rules.
BUDGET_BURN_RATE_WARNING_PP = 25   # gap (used% - elapsed%) over this → warning
BUDGET_BURN_RATE_CRITICAL_PP = 45  # gap over this → critical

CATEGORY_SPIKE_WARNING_RATIO = 1.5   # current / baseline >= 1.5x → warning
CATEGORY_SPIKE_CRITICAL_RATIO = 2.0  # >= 2.0x → critical

SAVINGS_RATE_WARNING_PCT = 5.0    # below this → warning
SAVINGS_RATE_CRITICAL_PCT = 0.0   # at or below 0 → critical

ANOMALY_DEVIATION_CRITICAL_PCT = 75.0


class SeverityClassifier:
    """Stateless classifier — kept as a class for future dependency injection
    (e.g. user-specific thresholds)."""

    def classify_budget_burn_rate(self, projected_pct: float, elapsed_pct: float) -> Severity:
        gap = projected_pct - elapsed_pct
        if gap >= BUDGET_BURN_RATE_CRITICAL_PP:
            return Severity.CRITICAL
        if gap >= BUDGET_BURN_RATE_WARNING_PP:
            return Severity.WARNING
        return Severity.INFO

    def classify_deficit_risk(self, expected_balance: float) -> Severity:
        if expected_balance < 0:
            return Severity.CRITICAL
        return Severity.INFO

    def classify_category_spike(self, current: float, baseline: float) -> Severity:
        if baseline <= 0:
            return Severity.INFO
        ratio = current / baseline
        if ratio >= CATEGORY_SPIKE_CRITICAL_RATIO:
            return Severity.CRITICAL
        if ratio >= CATEGORY_SPIKE_WARNING_RATIO:
            return Severity.WARNING
        return Severity.INFO

    def classify_savings(self, savings_rate_pct: float) -> Severity:
        if savings_rate_pct <= SAVINGS_RATE_CRITICAL_PCT:
            return Severity.CRITICAL
        if savings_rate_pct < SAVINGS_RATE_WARNING_PCT:
            return Severity.WARNING
        return Severity.INFO

    def classify_anomaly(self, deviation_pct: float, signal_confidence: Confidence) -> Severity:
        if signal_confidence == Confidence.HIGH and deviation_pct >= ANOMALY_DEVIATION_CRITICAL_PCT:
            return Severity.CRITICAL
        if deviation_pct >= ANOMALY_DEVIATION_CRITICAL_PCT / 2:
            return Severity.WARNING
        return Severity.INFO
