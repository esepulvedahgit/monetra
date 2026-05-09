"""Savings goal viability analysis.

Goals are not expenses: they represent future commitments. This module compares
the user's projected saving capacity against the monthly effort required to
complete active goals on time.
"""
from __future__ import annotations

from datetime import date
from math import ceil

from app.models import SavingsGoal


def analyze_savings_goals(user_id: int, projected_monthly_savings: float | None = None,
                          today: date | None = None) -> dict:
    today = today or date.today()
    capacity = max(float(projected_monthly_savings or 0), 0.0)
    goals = (SavingsGoal.query
             .filter_by(user_id=user_id, is_completed=False)
             .order_by(SavingsGoal.target_date.is_(None).asc(), SavingsGoal.target_date.asc())
             .all())

    items = []
    monthly_required_total = 0.0
    overdue_count = 0
    at_risk_count = 0

    for goal in goals:
        remaining = float(goal.remaining)
        days_left = goal.days_left
        months_left = None
        monthly_required = None
        status = 'no_deadline'

        if goal.target_date:
            if days_left is not None and days_left < 0:
                overdue_count += 1
                status = 'overdue'
                months_left = 0
                monthly_required = remaining
            else:
                months_left = max(1, ceil((days_left or 0) / 30.4375))
                monthly_required = remaining / months_left if months_left else remaining
                monthly_required_total += monthly_required
                status = 'on_track'

        items.append({
            'id': goal.id,
            'name': goal.name,
            'target_amount': float(goal.target_amount),
            'current_amount': float(goal.current_amount),
            'remaining': round(remaining, 2),
            'progress_pct': round(goal.progress_pct, 1),
            'target_date': goal.target_date.isoformat() if goal.target_date else None,
            'days_left': days_left,
            'months_left': months_left,
            'monthly_required': round(monthly_required, 2) if monthly_required is not None else None,
            'status': status,
        })

    if monthly_required_total > 0 and capacity < monthly_required_total:
        for item in items:
            if item['status'] == 'on_track':
                item['status'] = 'at_risk'
        at_risk_count = sum(1 for item in items if item['status'] == 'at_risk')

    coverage_pct = None
    if monthly_required_total > 0:
        coverage_pct = round(capacity / monthly_required_total * 100, 1)

    score = _goal_score(
        active_count=len(goals),
        overdue_count=overdue_count,
        at_risk_count=at_risk_count,
        coverage_pct=coverage_pct,
        items=items,
    )

    return {
        'active_count': len(goals),
        'projected_monthly_savings': round(capacity, 2),
        'monthly_required_total': round(monthly_required_total, 2),
        'coverage_pct': coverage_pct,
        'overdue_count': overdue_count,
        'at_risk_count': at_risk_count,
        'score': score,
        'goals': items,
    }


def _goal_score(active_count: int, overdue_count: int, at_risk_count: int,
                coverage_pct: float | None, items: list[dict]) -> int:
    if active_count == 0:
        return 70

    if coverage_pct is None:
        progresses = [item['progress_pct'] for item in items]
        return int(round(sum(progresses) / len(progresses))) if progresses else 70

    score = min(100, int(round(coverage_pct)))
    score -= overdue_count * 35
    score -= at_risk_count * 10
    return max(0, min(100, score))
