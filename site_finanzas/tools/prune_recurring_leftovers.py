"""
prune_recurring_leftovers.py — One-off cleanup for recurring rules finalized before the fix.

Finalizing a recurring rule used to leave the transactions that backfill had
already generated after its end date (up to Dec 31). This script removes them
using the same rule as the app (app.services.finance.prune_recurring_after_end).

It also lists transactions whose recurring_id points to a rule that no longer
exists. Those are only reported, never deleted: they may have been edited by
the user and are now shown as "Manual" in the UI.

Usage (dry run by default; nothing is changed without --apply):
    cd site_finanzas
    python tools/prune_recurring_leftovers.py
    python tools/prune_recurring_leftovers.py --apply
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import RecurringTransaction, Transaction
from app.services.finance import prune_recurring_after_end


def main(apply: bool) -> None:
    rules = RecurringTransaction.query.filter(
        (RecurringTransaction.is_active == False) | RecurringTransaction.end_date.isnot(None)  # noqa: E712
    ).all()

    total = 0
    for rec in rules:
        removed = prune_recurring_after_end(rec)
        if removed:
            print(f'rule {rec.id} (user {rec.user_id}, "{rec.description or ""}"): {removed} future transactions')
            total += removed

    orphans = Transaction.query.filter(
        Transaction.recurring_id.isnot(None),
        ~Transaction.recurring_id.in_(db.session.query(RecurringTransaction.id)),
    ).count()

    if apply:
        db.session.commit()
        print(f'Deleted {total} transactions.')
    else:
        db.session.rollback()
        print(f'Dry run: {total} transactions would be deleted. Re-run with --apply to delete them.')
    print(f'Transactions pointing to a missing rule (left untouched): {orphans}')


if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        main(apply='--apply' in sys.argv)
