from datetime import date as _date, datetime, timezone
from sqlalchemy import func, extract, or_
from app import db
from app.models import Transaction, Category, Budget, RecurringTransaction, SavingsGoal, CustomBudget


def _tx_dict(tx):
    return {
        "id": tx.id,
        "type": tx.type,
        "amount": float(tx.amount),
        "description": tx.description or "",
        "date": tx.date.isoformat() if tx.date else None,
        "category_id": tx.category_id,
        "category_name": tx.category.name if tx.category else None,
        "is_demo": tx.is_demo,
        "created_at": tx.created_at.isoformat() if tx.created_at else None,
        "recurring_id": tx.recurring_id,
    }


def _cat_dict(cat):
    return {
        "id": cat.id,
        "name": cat.name,
        "type": cat.type,
        "is_global": cat.user_id is None,
    }


def _budget_dict(b):
    return {
        "id": b.id,
        "year": b.year,
        "month": b.month,
        "amount": float(b.amount),
    }


def _recurring_dict(r):
    return {
        "id": r.id,
        "type": r.type,
        "amount": float(r.amount),
        "description": r.description or "",
        "category_id": r.category_id,
        "category_name": r.category.name if r.category else None,
        "day_of_month": r.day_of_month,
        "end_date": r.end_date.isoformat() if r.end_date else None,
        "is_active": r.is_active,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def _savings_dict(g):
    return {
        "id": g.id,
        "name": g.name,
        "target_amount": float(g.target_amount),
        "current_amount": float(g.current_amount),
        "remaining": float(g.remaining),
        "progress_pct": round(g.progress_pct, 2),
        "target_date": g.target_date.isoformat() if g.target_date else None,
        "days_left": g.days_left,
        "description": g.description or "",
        "is_completed": g.is_completed,
        "created_at": g.created_at.isoformat() if g.created_at else None,
    }


# ── Monthly summary ────────────────────────────────────────────────────────────

def get_monthly_summary(user_id: int, year: int, month: int) -> dict:
    base = Transaction.query.filter(
        Transaction.user_id == user_id,
        extract("year", Transaction.date) == year,
        extract("month", Transaction.date) == month,
    )

    total_income = float(
        base.filter_by(type="income")
        .with_entities(func.coalesce(func.sum(Transaction.amount), 0))
        .scalar()
    )
    total_expense = float(
        base.filter_by(type="expense")
        .with_entities(func.coalesce(func.sum(Transaction.amount), 0))
        .scalar()
    )

    budget = Budget.query.filter_by(user_id=user_id, year=year, month=month).first()
    budget_amount = float(budget.amount) if budget else 0.0
    budget_expense = float(
        base.filter_by(type="expense", exclude_from_budget=False)
        .with_entities(func.coalesce(func.sum(Transaction.amount), 0))
        .scalar()
    )
    budget_used_pct = (
        round(budget_expense / budget_amount * 100, 1) if budget_amount > 0 else None
    )

    top_cats = (
        db.session.query(Category.name, func.sum(Transaction.amount).label("total"))
        .join(Transaction, Transaction.category_id == Category.id)
        .filter(
            Transaction.user_id == user_id,
            Transaction.type == "expense",
            extract("year", Transaction.date) == year,
            extract("month", Transaction.date) == month,
        )
        .group_by(Category.id, Category.name)
        .order_by(func.sum(Transaction.amount).desc())
        .limit(5)
        .all()
    )

    recent = (
        base.order_by(Transaction.date.desc(), Transaction.id.desc()).limit(5).all()
    )

    return {
        "year": year,
        "month": month,
        "total_income": total_income,
        "total_expense": total_expense,
        "balance": round(total_income - total_expense, 2),
        "budget_amount": budget_amount,
        "budget_used_pct": budget_used_pct,
        "top_expense_categories": [
            {"name": name, "total": float(total)} for name, total in top_cats
        ],
        "recent_transactions": [_tx_dict(t) for t in recent],
    }


# ── Global / annual summary ────────────────────────────────────────────────────

def get_global_summary(
    user_id: int, year: int, from_month: int = 1, to_month: int = 12
) -> dict:
    from_month = max(1, min(12, from_month))
    to_month = max(from_month, min(12, to_month))

    monthly_rows = (
        db.session.query(
            extract("month", Transaction.date).label("m"),
            Transaction.type,
            func.sum(Transaction.amount).label("total"),
        )
        .filter(
            Transaction.user_id == user_id,
            extract("year", Transaction.date) == year,
            extract("month", Transaction.date) >= from_month,
            extract("month", Transaction.date) <= to_month,
        )
        .group_by("m", Transaction.type)
        .all()
    )

    trend_income = [0.0] * 12
    trend_expense = [0.0] * 12
    for m, tx_type, total in monthly_rows:
        idx = int(m) - 1
        if tx_type == "income":
            trend_income[idx] = float(total)
        else:
            trend_expense[idx] = float(total)

    cat_rows = (
        db.session.query(
            Category.id,
            Category.name,
            Category.color,
            func.sum(Transaction.amount).label("total"),
        )
        .join(Transaction, Transaction.category_id == Category.id)
        .filter(
            Transaction.user_id == user_id,
            Transaction.type == "expense",
            extract("year", Transaction.date) == year,
            extract("month", Transaction.date) >= from_month,
            extract("month", Transaction.date) <= to_month,
        )
        .group_by(Category.id, Category.name, Category.color)
        .order_by(func.sum(Transaction.amount).desc())
        .all()
    )

    multi_year_rows = (
        db.session.query(
            extract("year", Transaction.date).label("y"),
            extract("month", Transaction.date).label("m"),
            func.sum(Transaction.amount).label("total"),
        )
        .filter(
            Transaction.user_id == user_id,
            Transaction.type == "expense",
        )
        .group_by("y", "m")
        .order_by("y", "m")
        .all()
    )

    yearly_rows = (
        db.session.query(
            extract("year", Transaction.date).label("y"),
            Transaction.type,
            func.sum(Transaction.amount).label("total"),
        )
        .filter(Transaction.user_id == user_id)
        .group_by("y", Transaction.type)
        .order_by("y")
        .all()
    )

    yearly_map: dict = {}
    for y, tx_type, total in yearly_rows:
        yr = int(y)
        if yr not in yearly_map:
            yearly_map[yr] = {"year": yr, "income": 0.0, "expense": 0.0}
        yearly_map[yr][tx_type] = float(total)

    multi_year_map: dict = {}
    for y, m, total in multi_year_rows:
        yr = int(y)
        if yr not in multi_year_map:
            multi_year_map[yr] = [0.0] * 12
        multi_year_map[yr][int(m) - 1] = float(total)

    return {
        "year": year,
        "from_month": from_month,
        "to_month": to_month,
        "trend_income": trend_income,
        "trend_expense": trend_expense,
        "expense_by_category": [
            {"id": cat_id, "name": name, "color": color, "total": float(total)}
            for cat_id, name, color, total in cat_rows
        ],
        "yearly_summary": sorted(yearly_map.values(), key=lambda r: r["year"]),
        "multi_year_expense_trend": [
            {"year": yr, "monthly": monthly}
            for yr, monthly in sorted(multi_year_map.items())
        ],
    }


# ── Transactions ───────────────────────────────────────────────────────────────

def get_transactions(
    user_id: int,
    year=None,
    month=None,
    from_month=None,
    to_month=None,
    tx_type=None,
    category_id=None,
    limit=None,
) -> list:
    query = Transaction.query.filter_by(user_id=user_id)
    if year:
        query = query.filter(extract("year", Transaction.date) == year)
    if month:
        query = query.filter(extract("month", Transaction.date) == month)
    elif from_month is not None:
        query = query.filter(extract("month", Transaction.date) >= from_month)
        if to_month is not None:
            query = query.filter(extract("month", Transaction.date) <= to_month)
    if tx_type in ("income", "expense"):
        query = query.filter_by(type=tx_type)
    if category_id:
        query = query.filter_by(category_id=category_id)
    query = query.order_by(Transaction.date.desc(), Transaction.id.desc())
    if limit:
        query = query.limit(limit)
    return [_tx_dict(t) for t in query.all()]


# ── Categories ─────────────────────────────────────────────────────────────────

def get_categories(user_id: int, tx_type=None) -> list:
    query = Category.query.filter(
        (Category.user_id == user_id) | (Category.user_id.is_(None))
    )
    if tx_type in ("income", "expense"):
        query = query.filter_by(type=tx_type)
    return [_cat_dict(c) for c in query.order_by(Category.type, Category.name).all()]


# ── Budgets ────────────────────────────────────────────────────────────────────

def get_budgets(user_id: int, year=None) -> list:
    query = Budget.query.filter_by(user_id=user_id)
    if year:
        query = query.filter_by(year=year)
    return [_budget_dict(b) for b in query.order_by(Budget.year, Budget.month).all()]


def get_budget_vs_actual(
    user_id: int, year: int, from_month: int, to_month: int
) -> list:
    budgets_map = {
        b.month: float(b.amount)
        for b in Budget.query.filter(
            Budget.user_id == user_id,
            Budget.year == year,
            Budget.month >= from_month,
            Budget.month <= to_month,
        ).all()
    }

    expense_rows = (
        db.session.query(
            extract("month", Transaction.date).label("m"),
            func.sum(Transaction.amount).label("total"),
        )
        .filter(
            Transaction.user_id == user_id,
            Transaction.type == "expense",
            Transaction.exclude_from_budget == False,
            extract("year", Transaction.date) == year,
            extract("month", Transaction.date) >= from_month,
            extract("month", Transaction.date) <= to_month,
        )
        .group_by("m")
        .all()
    )
    actuals_map = {int(m): float(total) for m, total in expense_rows}

    result = []
    for m in range(from_month, to_month + 1):
        budget_amt = budgets_map.get(m, 0.0)
        actual_amt = actuals_map.get(m, 0.0)
        used_pct = (
            round(actual_amt / budget_amt * 100, 1) if budget_amt > 0 else None
        )
        if budget_amt == 0:
            status = "no_budget"
        elif used_pct >= 100:
            status = "over"
        elif used_pct >= 80:
            status = "warning"
        else:
            status = "ok"
        result.append(
            {
                "month": m,
                "budget": budget_amt,
                "actual": actual_amt,
                "difference": round(budget_amt - actual_amt, 2),
                "used_pct": used_pct,
                "status": status,
            }
        )
    return result


def get_category_actuals(user_id: int, year: int, month: int, category_ids: list) -> dict:
    """Returns {category_id: actual_spending} for expense transactions in the given month."""
    if not category_ids:
        return {}
    rows = (
        db.session.query(
            Transaction.category_id,
            func.sum(Transaction.amount).label("total"),
        )
        .filter(
            Transaction.user_id == user_id,
            Transaction.type == "expense",
            Transaction.exclude_from_budget == False,
            extract("year", Transaction.date) == year,
            extract("month", Transaction.date) == month,
            Transaction.category_id.in_(category_ids),
        )
        .group_by(Transaction.category_id)
        .all()
    )
    return {cat_id: float(total) for cat_id, total in rows}


# ── Custom budget ──────────────────────────────────────────────────────────────

def get_custom_budget_status_for_period(budget, period_start):
    if (budget.start_date.year, budget.start_date.month) != (period_start.year, period_start.month):
        return None
    if budget.end_date < _date.today():
        return "finalized"
    return "active"

def get_custom_budget_granular_actual(user_id: int, category_id: int, start_date, end_date) -> dict:
    """Return custom-budget usage split by date bucket for one user's category."""
    import calendar

    month_start = _date(start_date.year, start_date.month, 1)
    month_end = _date(start_date.year, start_date.month, calendar.monthrange(start_date.year, start_date.month)[1])
    advance_spent = float(
        db.session.query(func.coalesce(func.sum(Transaction.amount), 0))
        .filter(
            Transaction.user_id == user_id,
            Transaction.type == 'expense',
            Transaction.category_id == category_id,
            Transaction.date >= month_start,
            Transaction.date < start_date
        ).scalar()
    )

    spent_within_range = float(
        db.session.query(func.coalesce(func.sum(Transaction.amount), 0))
        .filter(
            Transaction.user_id == user_id,
            Transaction.type == 'expense',
            Transaction.category_id == category_id,
            Transaction.date >= start_date,
            Transaction.date <= end_date
        ).scalar()
    )

    post_period_spent = float(
        db.session.query(func.coalesce(func.sum(Transaction.amount), 0))
        .filter(
            Transaction.user_id == user_id,
            Transaction.type == 'expense',
            Transaction.category_id == category_id,
            Transaction.date > end_date,
            Transaction.date <= month_end,
        ).scalar()
    )

    total_consumed = advance_spent + spent_within_range
    return {
        "advance_spent": advance_spent,
        "spent_within_range": spent_within_range,
        "post_period_spent": post_period_spent,
        "total_consumed": total_consumed
    }

def calculate_custom_budget_usage(user_id: int, budget) -> dict:
    """Calculate derived usage for a preserved historical CustomBudget."""
    granular = get_custom_budget_granular_actual(
        user_id, budget.category_id, budget.start_date, budget.end_date
    )
    limit = float(budget.amount)
    remaining = max(limit - granular['total_consumed'], 0.0)
    usage_pct = round((granular['total_consumed'] / limit) * 100, 1) if limit > 0 else 0.0
    return {
        **granular,
        "remaining": remaining,
        "usage_percent": usage_pct,
    }

def get_custom_budget_actual(user_id: int, category_id: int) -> float:
    """Compatibility wrapper: returns budget consumption, excluding post-period spending."""
    budget = CustomBudget.query.filter_by(
        user_id=user_id, category_id=category_id
    ).order_by(CustomBudget.start_date.desc()).first()
    if budget:
        return calculate_custom_budget_usage(user_id, budget)['total_consumed']

    return float(
        db.session.query(func.coalesce(func.sum(Transaction.amount), 0))
        .filter(
            Transaction.user_id == user_id,
            Transaction.type == 'expense',
            Transaction.category_id == category_id,
        )
        .scalar()
    )

def group_custom_budgets_for_period(user_id: int, year: int, month: int) -> dict:
    from datetime import date

    period_start = date(year, month, 1)

    budgets = CustomBudget.query.filter(
        CustomBudget.user_id == user_id,
        extract("year", CustomBudget.start_date) == year,
        extract("month", CustomBudget.start_date) == month,
    ).order_by(CustomBudget.start_date.desc()).all()

    result = {
        "active": [],
        "finalized": [],
        "summary": {
            "total_limit": 0.0,
            "total_advance_spent": 0.0,
            "total_spent_within_range": 0.0,
            "total_consumed": 0.0,
            "active_count": 0,
            "finalized_count": 0
        }
    }

    for b in budgets:
        status = get_custom_budget_status_for_period(b, period_start)
        if not status:
            continue
        limit = float(b.amount)
        usage = calculate_custom_budget_usage(user_id, b)

        item = {
            "budget": b,
            "visual_status": status,
            "advance_spent": usage['advance_spent'],
            "spent_within_range": usage['spent_within_range'],
            "post_period_spent": usage['post_period_spent'],
            "total_consumed": usage['total_consumed'],
            "remaining": usage['remaining'],
            "usage_percent": usage['usage_percent'],
            "start_date": b.start_date,
            "end_date": b.end_date
        }

        result[status].append(item)

        if status == "active":
            result['summary']['total_limit'] += limit
            result['summary']['total_advance_spent'] += usage['advance_spent']
            result['summary']['total_spent_within_range'] += usage['spent_within_range']
            result['summary']['total_consumed'] += usage['total_consumed']

    result['summary']['active_count'] = len(result['active'])
    result['summary']['finalized_count'] = len(result['finalized'])

    return result


# ── Recurring transactions ─────────────────────────────────────────────────────

def generate_pending_recurring(user_id: int, year: int, month: int, commit: bool = True) -> bool:
    """Materialize annual recurring transactions for one month."""
    import calendar

    recs = RecurringTransaction.query.filter_by(user_id=user_id, is_active=True).all()
    changed = False
    for rec in recs:
        rec_start = rec.created_at.date() if rec.created_at else _date(year, month, 1)
        if rec_start.year != year:
            continue

        last_day = calendar.monthrange(year, month)[1]
        tx_date = _date(year, month, min(rec.day_of_month, last_day))
        annual_end = _date(year, 12, 31)
        end_date = rec.end_date if rec.end_date and rec.end_date.year == year else annual_end
        if tx_date < rec_start or tx_date > end_date:
            continue

        exists = Transaction.query.filter_by(
            user_id=user_id, recurring_id=rec.id
        ).filter(
            extract("year", Transaction.date) == year,
            extract("month", Transaction.date) == month,
        ).first()
        if exists:
            continue

        db.session.add(Transaction(
            user_id=user_id,
            category_id=rec.category_id,
            type=rec.type,
            amount=rec.amount,
            description=rec.description or "",
            date=tx_date,
            recurring_id=rec.id,
        ))
        changed = True

    if changed and commit:
        db.session.commit()
    return changed


def generate_pending_recurring_range(user_id: int, year: int, from_month: int, to_month: int) -> bool:
    """Materialize annual recurring transactions for every month in a selected range."""
    changed = False
    for month in range(from_month, to_month + 1):
        changed = generate_pending_recurring(user_id, year, month, commit=False) or changed
    if changed:
        db.session.commit()
    return changed


def get_recurring_for_month(user_id: int, year: int, month: int) -> list:
    """Return active recurring transactions that apply to the given year/month."""
    import calendar
    month_start = _date(year, month, 1)
    month_end_dt = datetime(year, month, calendar.monthrange(year, month)[1], 23, 59, 59, tzinfo=timezone.utc)
    query = RecurringTransaction.query.filter(
        RecurringTransaction.user_id == user_id,
        RecurringTransaction.is_active == True,
        RecurringTransaction.created_at <= month_end_dt,
        or_(
            RecurringTransaction.end_date.is_(None),
            RecurringTransaction.end_date >= month_start,
        ),
    )
    return [_recurring_dict(r) for r in query.order_by(RecurringTransaction.amount.desc()).all()]


def get_recurring(user_id: int, tx_type=None, active_only=False, year=None) -> list:
    query = RecurringTransaction.query.filter_by(user_id=user_id)
    if year:
        query = query.filter(extract("year", RecurringTransaction.created_at) == year)
    if tx_type in ("income", "expense"):
        query = query.filter_by(type=tx_type)
    if active_only:
        query = query.filter_by(is_active=True)
    return [
        _recurring_dict(r)
        for r in query.order_by(RecurringTransaction.amount.desc()).all()
    ]


# ── Savings goals ──────────────────────────────────────────────────────────────

def get_savings(user_id: int, completed=None) -> list:
    query = SavingsGoal.query.filter_by(user_id=user_id)
    if completed is True:
        query = query.filter_by(is_completed=True)
    elif completed is False:
        query = query.filter_by(is_completed=False)
    return [
        _savings_dict(g)
        for g in query.order_by(SavingsGoal.is_completed, SavingsGoal.created_at.desc()).all()
    ]
