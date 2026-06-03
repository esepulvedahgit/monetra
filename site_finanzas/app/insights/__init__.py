"""Financial insights & alerts.

This module turns analytics results into explainable, actionable messages for
the user. It does NOT calculate analytics, query the DB directly, or train
models — it consumes the analytics layer and applies deterministic rules.

Public surface lives in `services.py` (facade for UI/API).
"""
