"""Time-series builders.

These produce the historical series that feed forecasting, anomalies and
scoring. Streams stay unified (CLP + USD converted to local) so the analytics
layer always sees one currency, consistent with the consolidated view.
"""
from __future__ import annotations
from datetime import date, datetime, timezone
from sqlalchemy import func, extract, distinct, or_

from app import db
from app.models import User, Transaction, UsdTransaction, Category, RecurringTransaction
from app.analytics.features import get_conversion_rate


def _year_month_iter(end_year: int, end_month: int, months_back: int):
    """Yield (year, month) pairs ending at (end_year, end_month), oldest first."""
    pairs = []
    y, m = end_year, end_month
    for _ in range(months_back):
        pairs.append((y, m))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return list(reversed(pairs))


def build_monthly_unified_expense_series(user_id: int, year: int,
                                         include_recurring: bool = True) -> list[float]:
    """12 monthly expense totals (CLP + USD→local) for the given year."""
    user = User.query.get(user_id)
    if user is None:
        return [0.0] * 12
    rate = get_conversion_rate(user)

    series = [0.0] * 12

    main_query = (db.session.query(
        extract('month', Transaction.date).label('m'),
        func.sum(Transaction.amount).label('total'),
    ).filter(
        Transaction.user_id == user_id,
        Transaction.type == 'expense',
        extract('year', Transaction.date) == year,
    ))
    if not include_recurring:
        main_query = main_query.filter(Transaction.recurring_id.is_(None))
    main_rows = main_query.group_by(extract('month', Transaction.date)).all()
    for m, total in main_rows:
        series[int(m) - 1] += float(total or 0)

    usd_rows = (db.session.query(
        extract('month', UsdTransaction.date).label('m'),
        func.sum(UsdTransaction.amount).label('total'),
    ).filter(
        UsdTransaction.user_id == user_id,
        extract('year', UsdTransaction.date) == year,
    ).group_by(extract('month', UsdTransaction.date)).all())
    factor = rate if rate > 0 else 1.0
    for m, total in usd_rows:
        series[int(m) - 1] += float(total or 0) * factor

    return series


def build_monthly_unified_income_series(user_id: int, year: int,
                                        include_recurring: bool = True) -> list[float]:
    """12 monthly income totals for the given year. USD has no income stream."""
    series = [0.0] * 12
    query = (db.session.query(
        extract('month', Transaction.date).label('m'),
        func.sum(Transaction.amount).label('total'),
    ).filter(
        Transaction.user_id == user_id,
        Transaction.type == 'income',
        extract('year', Transaction.date) == year,
    ))
    if not include_recurring:
        query = query.filter(Transaction.recurring_id.is_(None))
    rows = query.group_by(extract('month', Transaction.date)).all()
    for m, total in rows:
        series[int(m) - 1] += float(total or 0)
    return series


def build_history_window_expense_series(user_id: int, end_year: int, end_month: int,
                                        months_back: int = 12,
                                        include_recurring: bool = True) -> list[float]:
    """Expense totals for the last `months_back` months (oldest → newest).
    Crosses year boundaries cleanly."""
    pairs = _year_month_iter(end_year, end_month, months_back)
    by_year: dict[int, list[float]] = {}
    for y, _ in pairs:
        if y not in by_year:
            by_year[y] = build_monthly_unified_expense_series(
                user_id, y, include_recurring=include_recurring)
    return [by_year[y][m - 1] for y, m in pairs]


def build_history_window_income_series(user_id: int, end_year: int, end_month: int,
                                       months_back: int = 12,
                                       include_recurring: bool = True) -> list[float]:
    pairs = _year_month_iter(end_year, end_month, months_back)
    by_year: dict[int, list[float]] = {}
    for y, _ in pairs:
        if y not in by_year:
            by_year[y] = build_monthly_unified_income_series(
                user_id, y, include_recurring=include_recurring)
    return [by_year[y][m - 1] for y, m in pairs]


def get_recurring_totals_for_month(user_id: int, year: int, month: int) -> dict[str, float]:
    """Known recurring income/expense expected for a month."""
    import calendar

    month_start = date(year, month, 1)
    month_end = datetime(year, month, calendar.monthrange(year, month)[1], 23, 59, 59,
                         tzinfo=timezone.utc)
    totals = {'income': 0.0, 'expense': 0.0}

    materialized = (db.session.query(
        Transaction.recurring_id,
        Transaction.type,
        func.sum(Transaction.amount).label('total'),
    ).filter(
        Transaction.user_id == user_id,
        Transaction.recurring_id.isnot(None),
        extract('year', Transaction.date) == year,
        extract('month', Transaction.date) == month,
    ).group_by(Transaction.recurring_id, Transaction.type).all())
    materialized_ids = set()
    for recurring_id, tx_type, total in materialized:
        materialized_ids.add(recurring_id)
        if tx_type in totals:
            totals[tx_type] += float(total or 0)

    query = (db.session.query(
        RecurringTransaction.id,
        RecurringTransaction.type,
        func.sum(RecurringTransaction.amount).label('total'),
    ).filter(
        RecurringTransaction.user_id == user_id,
        RecurringTransaction.is_active == True,
        RecurringTransaction.created_at <= month_end,
        or_(
            RecurringTransaction.end_date.is_(None),
            RecurringTransaction.end_date >= month_start,
        ),
    ))
    if materialized_ids:
        query = query.filter(RecurringTransaction.id.notin_(materialized_ids))
    rows = query.group_by(RecurringTransaction.id, RecurringTransaction.type).all()

    for _, tx_type, total in rows:
        if tx_type in totals:
            totals[tx_type] += float(total or 0)
    return totals


def build_category_monthly_series(user_id: int, category_id: int, end_year: int,
                                   end_month: int, months_back: int = 12) -> list[float]:
    """Historical monthly expense for one CLP category, oldest → newest.
    USD categories live in a separate table and use their own helper."""
    pairs = _year_month_iter(end_year, end_month, months_back)
    if not pairs:
        return []

    start_year, start_month = pairs[0]
    end_year_, end_month_ = pairs[-1]
    start = date(start_year, start_month, 1)
    # End: first day of the month after end_month (exclusive)
    if end_month_ == 12:
        end_excl = date(end_year_ + 1, 1, 1)
    else:
        end_excl = date(end_year_, end_month_ + 1, 1)

    rows = (db.session.query(
        extract('year', Transaction.date).label('y'),
        extract('month', Transaction.date).label('m'),
        func.sum(Transaction.amount).label('total'),
    ).filter(
        Transaction.user_id == user_id,
        Transaction.type == 'expense',
        Transaction.category_id == category_id,
        Transaction.date >= start,
        Transaction.date < end_excl,
    ).group_by(
        extract('year', Transaction.date),
        extract('month', Transaction.date),
    ).all())
    bucket = {(int(y), int(m)): float(total or 0) for y, m, total in rows}
    return [bucket.get((y, m), 0.0) for y, m in pairs]


def get_historical_months_count(user_id: int, before_year: int | None = None,
                                before_month: int | None = None) -> int:
    """How many distinct (year, month) pairs the user has any transaction in.
    Counts both CLP and USD streams together. When `before_year` and
    `before_month` are provided, only months before that period are counted."""
    main_query = db.session.query(
        distinct(func.concat(extract('year', Transaction.date), '-',
                              extract('month', Transaction.date)))
    ).filter(Transaction.user_id == user_id)
    usd_query = db.session.query(
        distinct(func.concat(extract('year', UsdTransaction.date), '-',
                              extract('month', UsdTransaction.date)))
    ).filter(UsdTransaction.user_id == user_id)

    if before_year is not None and before_month is not None:
        period_start = date(before_year, before_month, 1)
        main_query = main_query.filter(Transaction.date < period_start)
        usd_query = usd_query.filter(UsdTransaction.date < period_start)

    main_pairs = main_query.all()
    usd_pairs = usd_query.all()
    pair_set = {p[0] for p in main_pairs} | {p[0] for p in usd_pairs}
    return len(pair_set)


def get_user_expense_categories_with_history(user_id: int, end_year: int,
                                              end_month: int, months_back: int = 12) -> list[dict]:
    """List of CLP expense categories the user has used in the window, with name + color."""
    pairs = _year_month_iter(end_year, end_month, months_back)
    if not pairs:
        return []
    start = date(pairs[0][0], pairs[0][1], 1)
    if pairs[-1][1] == 12:
        end_excl = date(pairs[-1][0] + 1, 1, 1)
    else:
        end_excl = date(pairs[-1][0], pairs[-1][1] + 1, 1)

    rows = (db.session.query(
        Category.id, Category.name, Category.color,
    ).join(Transaction, Transaction.category_id == Category.id)
     .filter(
        Transaction.user_id == user_id,
        Transaction.type == 'expense',
        Transaction.date >= start,
        Transaction.date < end_excl,
    ).group_by(Category.id, Category.name, Category.color).all())
    return [{'id': cid, 'name': name, 'color': color or '#6c757d'} for cid, name, color in rows]
