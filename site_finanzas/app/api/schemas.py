def user_schema(user):
    return {
        "id": user.id,
        "username": user.username,
        "name": user.username,
        "email": user.email,
        "mfa_enabled": user.mfa_enabled,
        "country": user.country,
        "currency_symbol": user.currency_symbol or '$',
        "currency_code": user.currency_code or 'USD',
        "currency_locale": user.currency_locale or 'es',
        "language": user.language or 'es',
        "role": user.role,
        "weekly_report_enabled": getattr(user, "weekly_report_enabled", False),
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def transaction_schema(tx):
    return {
        "id": tx.id,
        "type": tx.type,
        "amount": float(tx.amount),
        "description": tx.description,
        "date": tx.date.isoformat() if tx.date else None,
        "category_id": tx.category_id,
        "category_name": tx.category.name if tx.category else None,
        "is_demo": tx.is_demo,
        "created_at": tx.created_at.isoformat() if tx.created_at else None,
    }


def category_schema(cat):
    return {
        "id": cat.id,
        "name": cat.name,
        "type": cat.type,
        "is_global": cat.user_id is None,
    }


def budget_schema(budget):
    return {
        "id": budget.id,
        "year": budget.year,
        "month": budget.month,
        "amount": float(budget.amount),
    }


def recurring_schema(r):
    return {
        "id": r.id,
        "type": r.type,
        "amount": float(r.amount),
        "description": r.description,
        "category_id": r.category_id,
        "category_name": r.category.name if r.category else None,
        "day_of_month": r.day_of_month,
        "is_active": r.is_active,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def savings_goal_schema(g):
    return {
        "id": g.id,
        "name": g.name,
        "target_amount": float(g.target_amount),
        "current_amount": float(g.current_amount),
        "remaining": float(g.remaining),
        "progress_pct": round(g.progress_pct, 2),
        "target_date": g.target_date.isoformat() if g.target_date else None,
        "days_left": g.days_left,
        "description": g.description,
        "is_completed": g.is_completed,
        "created_at": g.created_at.isoformat() if g.created_at else None,
    }


def audit_log_schema(log):
    return {
        "id":          log.id,
        "event_type":  log.event_type,
        "category":    log.event_type.split('.')[0] if '.' in log.event_type else 'app',
        "description": log.description,
        "ip_address":  log.ip_address,
        "user_id":     log.user_id,
        "username":    log.user.username if log.user else None,
        "created_at":  log.created_at.isoformat(),
    }


def _iso(value):
    return value.isoformat() if value else None


def cart_item_schema(item):
    return {
        "id": item.id,
        "name": item.name,
        "qty": float(item.qty),
        "unit_price": float(item.unit_price),
        "line_total": float(item.line_total),
        "source": item.source,
        "category": item.category,
        "created_at": _iso(item.created_at),
    }


def cart_schema(cart, include_items=False, movement=None):
    """``movement``: Transaction vigente del carrito (ver cart.service.linked_transaction)."""
    data = {
        "id": cart.id,
        "status": cart.status,
        "store_name": cart.store_name,
        "total": float(cart.total),
        "item_count": cart.item_count,
        "source": cart.source,
        "started_at": _iso(cart.started_at),
        "updated_at": _iso(cart.updated_at),
        "finalized_at": _iso(cart.finalized_at),
        "transaction_id": cart.transaction_id,
    }
    if include_items:
        data["items"] = [cart_item_schema(i) for i in cart.items]
        data["movement"] = transaction_schema(movement) if movement else None
    return data
