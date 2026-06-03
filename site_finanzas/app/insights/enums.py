"""Enumerations shared across the insights module.

Using `str, Enum` so values serialize cleanly to JSON for the UI/API and
compare against plain strings in templates without `.value` boilerplate.
"""
from __future__ import annotations
from enum import Enum


class Severity(str, Enum):
    INFO = 'info'
    WARNING = 'warning'
    CRITICAL = 'critical'


class Confidence(str, Enum):
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'


class InsightCategory(str, Enum):
    CASHFLOW = 'cashflow'
    BUDGET = 'budget'
    ANOMALY = 'anomaly'
    FORECAST = 'forecast'
    SAVINGS = 'savings'
    RECURRING = 'recurring'
    CATEGORY = 'category'
    BEHAVIOR = 'behavior'


class AlertType(str, Enum):
    DEFICIT_RISK = 'deficit_risk'
    BUDGET_BURN_RATE = 'budget_burn_rate'
    CATEGORY_SPIKE = 'category_spike'
    UNUSUAL_TRANSACTION = 'unusual_transaction'
    LOW_SAVINGS = 'low_savings'
    SAVINGS_GOAL_RISK = 'savings_goal_risk'
    NEGATIVE_TREND = 'negative_trend'
    CASHFLOW_DROP = 'cashflow_drop'
    RECURRING_INCREASE = 'recurring_increase'
    DUPLICATE_SUSPECTED = 'duplicate_suspected'
    MISSING_CONFIG = 'missing_config'


class SignalType(str, Enum):
    """Maps 1:1 with internal Signal categories produced by `signals.py`."""
    PROJECTED_DEFICIT = 'projected_deficit'
    BUDGET_BURN_RATE = 'budget_burn_rate'
    CATEGORY_SPIKE = 'category_spike'
    UNUSUAL_TRANSACTION = 'unusual_transaction'
    LOW_SAVINGS_RATE = 'low_savings_rate'
    SAVINGS_GOAL_RISK = 'savings_goal_risk'
    NEGATIVE_CASHFLOW_TREND = 'negative_cashflow_trend'
    RECURRING_INCREASE = 'recurring_increase'
    DUPLICATE_SUSPECTED = 'duplicate_suspected'
    MISSING_SETUP = 'missing_setup'
