"""Rule engine: turns Signals into Alerts.

Each rule handler maps one SignalType → at most one Alert. Handlers consult
`SeverityClassifier` for severity and `messages` for copy. They never embed
thresholds locally and never decide copy locally.
"""
from __future__ import annotations
import logging
from typing import Callable

from app.insights.models import Signal, Alert
from app.insights.enums import SignalType, AlertType, InsightCategory, Severity
from app.insights.severity import SeverityClassifier
from app.insights.messages import get_template

log = logging.getLogger(__name__)


class RuleEngine:
    def __init__(self, classifier: SeverityClassifier | None = None):
        self.classifier = classifier or SeverityClassifier()
        self._handlers: dict[SignalType, Callable[[Signal], Alert | None]] = {
            SignalType.PROJECTED_DEFICIT: self._handle_deficit,
            SignalType.BUDGET_BURN_RATE: self._handle_budget_burn_rate,
            SignalType.CATEGORY_SPIKE: self._handle_category_spike,
            SignalType.UNUSUAL_TRANSACTION: self._handle_unusual_transaction,
            SignalType.LOW_SAVINGS_RATE: self._handle_low_savings,
            SignalType.SAVINGS_GOAL_RISK: self._handle_goal_risk,
            SignalType.NEGATIVE_CASHFLOW_TREND: self._handle_negative_trend,
            SignalType.DUPLICATE_SUSPECTED: self._handle_duplicate,
        }

    def evaluate(self, signals: list[Signal]) -> list[Alert]:
        alerts: list[Alert] = []
        for sig in signals:
            handler = self._handlers.get(sig.signal_type)
            if handler is None:
                continue
            try:
                alert = handler(sig)
            except Exception:
                log.exception('Rule handler failed for signal %s', sig.signal_type)
                continue
            if alert is not None:
                alerts.append(alert)
        # Sort: critical → warning → info; preserve original order otherwise
        order = {Severity.CRITICAL: 0, Severity.WARNING: 1, Severity.INFO: 2}
        alerts.sort(key=lambda a: order.get(a.severity, 99))
        return alerts

    # ── Handlers ─────────────────────────────────────────────────────────────

    def _build_alert(self, alert_type: AlertType, category: InsightCategory,
                     severity: Severity, sig: Signal,
                     fmt: dict) -> Alert | None:
        tpl = get_template(alert_type, severity)
        if tpl is None:
            return None
        try:
            title = str(tpl['title']).format(**fmt)
            message = str(tpl['message']).format(**fmt)
            explanation = str(tpl['explanation']).format(**fmt)
            recommended_action = str(tpl['recommended_action']).format(**fmt)
        except (KeyError, ValueError, IndexError):
            log.exception('Template formatting failed for %s/%s', alert_type, severity)
            return None
        return Alert(
            alert_type=alert_type,
            category=category,
            severity=severity,
            confidence=sig.confidence,
            title=title,
            message=message,
            explanation=explanation,
            recommended_action=recommended_action,
            evidence=dict(sig.evidence),
            source_signal=sig.signal_type,
        )

    def _handle_deficit(self, sig: Signal) -> Alert | None:
        severity = self.classifier.classify_deficit_risk(sig.value)
        if severity == Severity.INFO:
            return None
        ev = sig.evidence
        return self._build_alert(
            AlertType.DEFICIT_RISK, InsightCategory.CASHFLOW, severity, sig,
            fmt={
                'expected_balance': ev.get('expected_balance', sig.value),
                'expected_income': ev.get('expected_income', 0),
                'expected_expense': ev.get('expected_expense', 0),
            },
        )

    def _handle_budget_burn_rate(self, sig: Signal) -> Alert | None:
        ev = sig.evidence
        projected_pct = ev.get('projected_pct', sig.value)
        elapsed_pct = ev.get('month_elapsed_pct', sig.baseline or 0)
        severity = self.classifier.classify_budget_burn_rate(projected_pct, elapsed_pct)
        if severity == Severity.INFO:
            return None
        return self._build_alert(
            AlertType.BUDGET_BURN_RATE, InsightCategory.BUDGET, severity, sig,
            fmt={
                'projected_pct': projected_pct,
                'budget_used_pct': ev.get('budget_used_pct', 0),
                'month_elapsed_pct': elapsed_pct,
            },
        )

    def _handle_category_spike(self, sig: Signal) -> Alert | None:
        baseline = sig.baseline or 0
        severity = self.classifier.classify_category_spike(sig.value, baseline)
        if severity == Severity.INFO:
            return None
        ev = sig.evidence
        return self._build_alert(
            AlertType.CATEGORY_SPIKE, InsightCategory.CATEGORY, severity, sig,
            fmt={
                'category_name': ev.get('category_name', '—'),
                'current': sig.value,
                'baseline': baseline,
                'deviation_pct': ev.get('deviation_pct', 0),
            },
        )

    def _handle_unusual_transaction(self, sig: Signal) -> Alert | None:
        ev = sig.evidence
        severity = self.classifier.classify_anomaly(
            ev.get('deviation_pct', 0), sig.confidence)
        if severity == Severity.INFO:
            return None
        # Force WARNING (template only defines WARNING for this alert type)
        if severity == Severity.CRITICAL:
            severity = Severity.WARNING
        return self._build_alert(
            AlertType.UNUSUAL_TRANSACTION, InsightCategory.ANOMALY, severity, sig,
            fmt={
                'category_name': ev.get('category_name', '—'),
                'value': sig.value,
                'deviation_pct': ev.get('deviation_pct', 0),
            },
        )

    def _handle_low_savings(self, sig: Signal) -> Alert | None:
        severity = self.classifier.classify_savings(sig.value)
        if severity == Severity.INFO:
            return None
        return self._build_alert(
            AlertType.LOW_SAVINGS, InsightCategory.SAVINGS, severity, sig,
            fmt={'savings_rate_pct': sig.value},
        )

    def _handle_goal_risk(self, sig: Signal) -> Alert | None:
        ev = sig.evidence
        goal = ev.get('priority_goal') or {}
        severity = Severity.CRITICAL if goal.get('status') == 'overdue' else Severity.WARNING
        return self._build_alert(
            AlertType.SAVINGS_GOAL_RISK, InsightCategory.SAVINGS, severity, sig,
            fmt={
                'goal_name': goal.get('name', '—'),
                'monthly_required': goal.get('monthly_required') or 0,
                'remaining': goal.get('remaining') or 0,
            },
        )

    def _handle_negative_trend(self, sig: Signal) -> Alert | None:
        return self._build_alert(
            AlertType.NEGATIVE_TREND, InsightCategory.CASHFLOW, Severity.WARNING, sig,
            fmt={'value': sig.value, 'baseline': sig.baseline or 0},
        )

    def _handle_duplicate(self, sig: Signal) -> Alert | None:
        ev = sig.evidence
        return self._build_alert(
            AlertType.DUPLICATE_SUSPECTED, InsightCategory.ANOMALY, Severity.INFO, sig,
            fmt={
                'category_name': ev.get('category_name', '—'),
                'value': sig.value,
            },
        )
