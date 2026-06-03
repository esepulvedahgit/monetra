"""Top-level orchestrator.

Pipeline:
    analytics ─→ signals.build_signals ─→ rules.RuleEngine.evaluate ─→ alerts

Routes/services should call `InsightEngine.generate_monthly_insights()`,
never the lower layers directly.

STUB (Chunk 1): wired up but returns []. Real pipeline activates in Chunk 3.
"""
from __future__ import annotations
import logging

from app.insights.signals import build_signals
from app.insights.rules import RuleEngine
from app.insights.models import Alert

log = logging.getLogger(__name__)


class InsightEngine:
    def __init__(self, rule_engine: RuleEngine | None = None):
        self.rule_engine = rule_engine or RuleEngine()

    def generate_monthly_insights(self, user_id: int, year: int, month: int) -> list[Alert]:
        signals = build_signals(user_id, year, month)
        alerts = self.rule_engine.evaluate(signals)
        log.info('Generated %d insights for user_id=%s period=%s-%02d',
                 len(alerts), user_id, year, month)
        return alerts
