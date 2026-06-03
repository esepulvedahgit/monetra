"""Aggregations that feed the analytics views."""
from app.models import User
from app.analytics.features import (
    get_unified_transactions,
    get_category_breakdown,
    get_conversion_rate,
)


def get_consolidated_summary(user_id: int, year: int, month: int) -> dict:
    """Build the data bundle for /analytics/consolidated.

    Everything in the user's main currency. Sources stay tagged so the UI can
    show where each amount came from."""
    user = User.query.get(user_id)
    rate = get_conversion_rate(user) if user else 0.0

    transactions = get_unified_transactions(user_id, year, month)
    categories = get_category_breakdown(transactions)

    total_income = sum(t['amount_local'] for t in transactions if t['type'] == 'income')
    total_expense = sum(t['amount_local'] for t in transactions if t['type'] == 'expense')
    balance = total_income - total_expense

    main_expense = sum(t['amount_local'] for t in transactions
                       if t['type'] == 'expense' and t['source'] == 'main')
    usd_expense_local = sum(t['amount_local'] for t in transactions
                            if t['type'] == 'expense' and t['source'] == 'usd')
    usd_expense_orig = sum((t['amount_usd'] or 0) for t in transactions
                           if t['source'] == 'usd')

    return {
        'transactions':       transactions,
        'categories':         categories,
        'total_income':       total_income,
        'total_expense':      total_expense,
        'balance':            balance,
        'main_expense':       main_expense,
        'usd_expense_local':  usd_expense_local,
        'usd_expense_orig':   usd_expense_orig,
        'rate':               rate,
    }
