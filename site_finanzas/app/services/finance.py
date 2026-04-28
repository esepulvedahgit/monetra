from datetime import date as _date
from sqlalchemy import func, extract
from app import db
from app.models import Transaction, Category, Budget, RecurringTransaction, SavingsGoal


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
    budget_used_pct = (
        round(total_expense / budget_amount * 100, 1) if budget_amount > 0 else None
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
        db.session.query(Category.name, func.sum(Transaction.amount).label("total"))
        .join(Transaction, Transaction.category_id == Category.id)
        .filter(
            Transaction.user_id == user_id,
            Transaction.type == "expense",
            extract("year", Transaction.date) == year,
            extract("month", Transaction.date) >= from_month,
            extract("month", Transaction.date) <= to_month,
        )
        .group_by(Category.id, Category.name)
        .order_by(func.sum(Transaction.amount).desc())
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

    return {
        "year": year,
        "from_month": from_month,
        "to_month": to_month,
        "trend_income": trend_income,
        "trend_expense": trend_expense,
        "expense_by_category": [
            {"name": name, "total": float(total)} for name, total in cat_rows
        ],
        "yearly_summary": sorted(yearly_map.values(), key=lambda r: r["year"]),
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
            extract("year", Transaction.date) == year,
            extract("month", Transaction.date) == month,
            Transaction.category_id.in_(category_ids),
        )
        .group_by(Transaction.category_id)
        .all()
    )
    return {cat_id: float(total) for cat_id, total in rows}


# ── Recurring transactions ─────────────────────────────────────────────────────

def get_recurring(user_id: int, tx_type=None, active_only=False) -> list:
    query = RecurringTransaction.query.filter_by(user_id=user_id)
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
