"""Data normalization for analytics.

This module is the single source of truth for converting USD amounts to the
user's main currency. Everything downstream (consolidated view, future
statistical models, ML forecasts) consumes the normalized streams from here.
"""
import calendar
from datetime import date
from sqlalchemy import extract

from app import db
from app.models import User, Transaction, UsdTransaction, Budget


def get_conversion_rate(user) -> float:
    """Return the multiplier to convert USD → user's main currency.
    Returns 1.0 if the user's main currency is USD.
    Returns 0.0 if no rate is configured (caller must handle)."""
    if user.currency_code == 'USD':
        return 1.0
    return float(user.usd_rate) if user.usd_rate else 0.0


def get_unified_transactions(user_id: int, year: int, month: int) -> list[dict]:
    """Return a single, unified stream of transactions for the period,
    with all amounts expressed in the user's main currency.

    Each item:
        {
            'date': date,
            'amount_local': float,   # always in main currency
            'amount_usd':   float,   # original USD value (or None for main txs)
            'type':         'income' | 'expense',
            'category_id':  int,
            'category_name': str,
            'category_color': str,
            'description': str,
            'source':      'main' | 'usd',
            'recurring_id': int | None,
        }
    """
    user = User.query.get(user_id)
    if user is None:
        return []
    rate = get_conversion_rate(user)

    main_txs = (Transaction.query
                .filter(
                    Transaction.user_id == user_id,
                    extract('year', Transaction.date) == year,
                    extract('month', Transaction.date) == month,
                )
                .all())

    usd_txs = (UsdTransaction.query
               .filter(
                   UsdTransaction.user_id == user_id,
                   extract('year', UsdTransaction.date) == year,
                   extract('month', UsdTransaction.date) == month,
               )
               .all())

    unified: list[dict] = []
    for tx in main_txs:
        unified.append({
            'date': tx.date,
            'amount_local': float(tx.amount),
            'amount_usd': None,
            'type': tx.type,
            'category_id': tx.category_id,
            'category_name': tx.category.name if tx.category else '—',
            'category_color': (tx.category.color if tx.category else '#6c757d') or '#6c757d',
            'description': tx.description or '',
            'source': 'main',
            'recurring_id': tx.recurring_id,
        })

    for tx in usd_txs:
        usd_amt = float(tx.amount)
        local_amt = usd_amt * rate if rate > 0 else usd_amt
        unified.append({
            'date': tx.date,
            'amount_local': local_amt,
            'amount_usd': usd_amt,
            'type': 'expense',
            'category_id': tx.category_id,
            'category_name': tx.category.name if tx.category else '—',
            'category_color': (tx.category.color if tx.category else '#6c757d') or '#6c757d',
            'description': tx.description or '',
            'source': 'usd',
            'recurring_id': None,
        })

    unified.sort(key=lambda x: x['date'], reverse=True)
    return unified


def _month_elapsed_pct(year: int, month: int, today: date | None = None) -> float:
    """Percentage of the period that has elapsed (0-100).
    Past months → 100. Future months → 0. Current month → day/days_in_month."""
    today = today or date.today()
    if (year, month) < (today.year, today.month):
        return 100.0
    if (year, month) > (today.year, today.month):
        return 0.0
    days_in_month = calendar.monthrange(year, month)[1]
    return round((today.day / days_in_month) * 100.0, 2)


def build_feature_bundle(user_id: int, year: int, month: int):
    """Bundle of financial variables for the period, ready for forecasting,
    anomaly detection and scoring. Uses the unified CLP+USD stream so all
    amounts are already in the user's main currency."""
    # Local import to avoid circular dependency (datasets imports from features)
    from app.analytics.schemas import FeatureBundle
    from app.analytics.datasets import (
        get_historical_months_count,
        build_history_window_expense_series,
        get_recurring_totals_for_month,
    )
    from app.analytics.utils import mean, stdev, safe_pct_change

    transactions = get_unified_transactions(user_id, year, month)
    total_income = sum(t['amount_local'] for t in transactions if t['type'] == 'income')
    total_expense = sum(t['amount_local'] for t in transactions if t['type'] == 'expense')
    variable_income = sum(t['amount_local'] for t in transactions
                          if t['type'] == 'income' and t['recurring_id'] is None)
    variable_expense = sum(t['amount_local'] for t in transactions
                           if t['type'] == 'expense' and t['recurring_id'] is None)
    recurring_totals = get_recurring_totals_for_month(user_id, year, month)
    balance = total_income - total_expense

    budget = Budget.query.filter_by(user_id=user_id, year=year, month=month).first()
    budget_amount = float(budget.amount) if budget else None
    budget_used_pct = (round(total_expense / budget_amount * 100, 1)
                       if budget_amount and budget_amount > 0 else None)

    elapsed = _month_elapsed_pct(year, month)
    days_in_month = calendar.monthrange(year, month)[1]
    daily_avg = round(total_expense / days_in_month, 2) if days_in_month else 0.0

    historical_months = get_historical_months_count(user_id, year, month)

    # Per-category aggregation: current total + history mean/std for delta
    by_category: dict[int, dict] = {}
    for tx in transactions:
        if tx['type'] != 'expense':
            continue
        cid = tx['category_id']
        if cid is None:
            continue
        if cid not in by_category:
            by_category[cid] = {
                'name': tx['category_name'],
                'color': tx['category_color'],
                'source': tx['source'],
                'total': 0.0,
                'mean_hist': 0.0,
                'std_hist': 0.0,
                'pct_change': 0.0,
            }
        by_category[cid]['total'] += tx['amount_local']

    # Backfill historical mean/std for CLP categories only (USD categories
    # live in a separate table and skip this enrichment in Phase 1).
    for cid, info in by_category.items():
        if info['source'] != 'main':
            continue
        from app.analytics.datasets import build_category_monthly_series
        # Use the 12 months prior to the period (exclude current month).
        prior_year, prior_month = (year, month - 1) if month > 1 else (year - 1, 12)
        series = build_category_monthly_series(
            user_id, cid, prior_year, prior_month, months_back=12)
        if series:
            info['mean_hist'] = round(mean(series), 2)
            info['std_hist'] = round(stdev(series), 2)
            info['pct_change'] = round(safe_pct_change(info['total'], info['mean_hist']), 1)

    return FeatureBundle(
        user_id=user_id,
        period_year=year,
        period_month=month,
        total_income=total_income,
        total_expense=total_expense,
        balance=balance,
        budget_amount=budget_amount,
        budget_used_pct=budget_used_pct,
        month_elapsed_pct=elapsed,
        daily_avg_expense=daily_avg,
        historical_months=historical_months,
        by_category=by_category,
        recurring_income=recurring_totals['income'],
        recurring_expense=recurring_totals['expense'],
        variable_income=variable_income,
        variable_expense=variable_expense,
    )


def get_category_breakdown(transactions: list[dict]) -> list[dict]:
    """Aggregate expenses by (category, source) for the donut chart.
    Sources stay separated to avoid silently merging unrelated categories
    that happen to share a name (e.g. 'Food' in main and 'Food' in USD)."""
    bucket: dict[tuple, dict] = {}
    for t in transactions:
        if t['type'] != 'expense':
            continue
        key = (t['category_id'], t['source'])
        if key not in bucket:
            bucket[key] = {
                'name': t['category_name'],
                'color': t['category_color'],
                'source': t['source'],
                'amount': 0.0,
            }
        bucket[key]['amount'] += t['amount_local']

    return sorted(bucket.values(), key=lambda x: x['amount'], reverse=True)
