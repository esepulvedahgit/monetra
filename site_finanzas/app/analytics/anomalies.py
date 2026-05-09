"""Anomaly detection for the user's CLP transactions.

Three detectors run for the period:
    1. Category spikes — current monthly total exceeds Tukey upper fence
       built from the prior 12 months of the category.
    2. Unusual individual transactions — z-score > 2.5 vs the category's
       per-transaction history (last 6 months).
    3. Suspected duplicates — same (category, amount) within ±3 days, only
       one of them flagged.

USD anomaly detection is deferred to a future iteration; CLP is where the
historical depth lives for almost every user.
"""
from __future__ import annotations
from datetime import date, timedelta
from sqlalchemy import extract, func

from app import db
from app.models import Transaction, Category
from app.analytics.schemas import AnomalyResult
from app.analytics.datasets import (
    build_category_monthly_series,
    get_user_expense_categories_with_history,
)
from app.analytics.utils import iqr_bounds, percentile, mean, stdev, z_score, safe_pct_change


# ── Tunables (kept here, not in severity — these define what counts as a
# detection at all; severity is a downstream concern). ────────────────────────
SPIKE_HISTORY_MIN_MONTHS = 3
SPIKE_HIGH_CONFIDENCE_MONTHS = 6
TX_ZSCORE_THRESHOLD = 2.5
TX_HISTORY_MIN_TXS = 5
DUPLICATE_WINDOW_DAYS = 3


def detect_anomalies(user_id: int, year: int, month: int) -> list[AnomalyResult]:
    """All anomalies for the period. Empty list if none / not enough history."""
    results: list[AnomalyResult] = []
    results.extend(_detect_category_spikes(user_id, year, month))
    results.extend(_detect_unusual_transactions(user_id, year, month))
    results.extend(_detect_duplicates(user_id, year, month))
    return results


# ── 1. Category spikes (monthly aggregate) ────────────────────────────────────

def _detect_category_spikes(user_id: int, year: int, month: int) -> list[AnomalyResult]:
    """Compare each category's current monthly total against its IQR upper
    fence over the prior 12 months. Drop categories with too little history."""
    prior_y, prior_m = (year, month - 1) if month > 1 else (year - 1, 12)
    cats = get_user_expense_categories_with_history(user_id, prior_y, prior_m, months_back=12)
    if not cats:
        return []

    current_totals = _current_month_category_totals(user_id, year, month)

    results: list[AnomalyResult] = []
    for cat in cats:
        current = current_totals.get(cat['id'], 0.0)
        if current <= 0:
            continue
        history = build_category_monthly_series(user_id, cat['id'], prior_y, prior_m, months_back=12)
        non_zero = [x for x in history if x > 0]
        if len(non_zero) < SPIKE_HISTORY_MIN_MONTHS:
            continue
        # Need at least 4 points for IQR — for 3, fall back to mean+2*std.
        if len(non_zero) < 4:
            baseline = mean(non_zero)
            cap = baseline + 2 * stdev(non_zero)
            method = 'mean_plus_2std'
        else:
            baseline = percentile(non_zero, 50)
            _, cap = iqr_bounds(non_zero, k=1.5)
            method = 'iqr'
        if current <= cap:
            continue
        deviation = safe_pct_change(current, baseline)
        confidence = ('high' if len(non_zero) >= SPIKE_HIGH_CONFIDENCE_MONTHS else 'medium')
        results.append(AnomalyResult(
            anomaly_type='category_spike',
            category_id=cat['id'],
            category_name=cat['name'],
            value=round(current, 2),
            baseline=round(baseline, 2),
            deviation_pct=round(deviation, 1),
            method=method,
            confidence=confidence,
            evidence={
                'history_months_used': len(non_zero),
                'iqr_upper_fence': round(cap, 2),
                'history_series': [round(x, 2) for x in non_zero],
            },
        ))
    return results


def _current_month_category_totals(user_id: int, year: int, month: int) -> dict[int, float]:
    rows = (db.session.query(
        Transaction.category_id,
        func.sum(Transaction.amount).label('total'),
    ).filter(
        Transaction.user_id == user_id,
        Transaction.type == 'expense',
        extract('year', Transaction.date) == year,
        extract('month', Transaction.date) == month,
    ).group_by(Transaction.category_id).all())
    return {cid: float(total or 0) for cid, total in rows if cid is not None}


# ── 2. Unusual individual transactions (per-tx z-score) ───────────────────────

def _detect_unusual_transactions(user_id: int, year: int, month: int) -> list[AnomalyResult]:
    """Flag individual transactions whose amount sits > 2.5 std from the
    category's per-transaction history."""
    current_txs = (Transaction.query.join(Category, Category.id == Transaction.category_id)
                   .filter(
                       Transaction.user_id == user_id,
                       Transaction.type == 'expense',
                       extract('year', Transaction.date) == year,
                       extract('month', Transaction.date) == month,
                   ).all())
    if not current_txs:
        return []

    six_months_ago = date(year, month, 1) - timedelta(days=183)
    history_by_cat: dict[int, list[float]] = {}

    results: list[AnomalyResult] = []
    for tx in current_txs:
        if tx.category_id is None:
            continue
        if tx.category_id not in history_by_cat:
            rows = (db.session.query(Transaction.amount)
                    .filter(
                        Transaction.user_id == user_id,
                        Transaction.type == 'expense',
                        Transaction.category_id == tx.category_id,
                        Transaction.date >= six_months_ago,
                        Transaction.date < date(year, month, 1),
                    ).all())
            history_by_cat[tx.category_id] = [float(r[0]) for r in rows]

        history = history_by_cat[tx.category_id]
        if len(history) < TX_HISTORY_MIN_TXS:
            continue
        m = mean(history)
        sd = stdev(history)
        if sd == 0:
            continue
        amount = float(tx.amount)
        zs = z_score(amount, m, sd)
        if zs <= TX_ZSCORE_THRESHOLD:
            continue
        results.append(AnomalyResult(
            anomaly_type='unusual_transaction',
            category_id=tx.category_id,
            category_name=tx.category.name if tx.category else None,
            value=amount,
            baseline=round(m, 2),
            deviation_pct=round(safe_pct_change(amount, m), 1),
            method='z_score',
            confidence='high' if zs > 3.0 else 'medium',
            evidence={
                'transaction_id': tx.id,
                'transaction_date': tx.date.isoformat() if tx.date else None,
                'description': tx.description or '',
                'z_score': round(zs, 2),
                'category_history_size': len(history),
                'category_mean': round(m, 2),
                'category_std': round(sd, 2),
            },
        ))
    return results


# ── 3. Suspected duplicates (same cat + amount within ±3 days) ────────────────

def _detect_duplicates(user_id: int, year: int, month: int) -> list[AnomalyResult]:
    """Sort by (category, amount, date). Whenever two consecutive rows match
    on (category, amount) and their dates differ by ≤ DUPLICATE_WINDOW_DAYS,
    flag the second one."""
    txs = (Transaction.query.join(Category, Category.id == Transaction.category_id)
           .filter(
               Transaction.user_id == user_id,
               Transaction.type == 'expense',
               extract('year', Transaction.date) == year,
               extract('month', Transaction.date) == month,
           )
           .order_by(Transaction.category_id, Transaction.amount, Transaction.date)
           .all())
    if len(txs) < 2:
        return []

    results: list[AnomalyResult] = []
    seen_pairs = set()
    for i in range(1, len(txs)):
        prev, curr = txs[i - 1], txs[i]
        if prev.category_id != curr.category_id:
            continue
        if float(prev.amount) != float(curr.amount):
            continue
        if abs((curr.date - prev.date).days) > DUPLICATE_WINDOW_DAYS:
            continue
        if curr.id in seen_pairs:
            continue
        seen_pairs.add(curr.id)
        results.append(AnomalyResult(
            anomaly_type='duplicate_suspected',
            category_id=curr.category_id,
            category_name=curr.category.name if curr.category else None,
            value=float(curr.amount),
            baseline=float(prev.amount),
            deviation_pct=0.0,
            method='neighbor_match',
            confidence='medium',
            evidence={
                'transaction_id': curr.id,
                'transaction_date': curr.date.isoformat() if curr.date else None,
                'paired_transaction_id': prev.id,
                'paired_date': prev.date.isoformat() if prev.date else None,
                'days_apart': abs((curr.date - prev.date).days),
            },
        ))
    return results
