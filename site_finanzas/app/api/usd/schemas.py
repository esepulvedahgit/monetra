def usd_category_schema(category):
    return {
        'id': category.id,
        'name': category.name,
        'color': category.color,
        'is_demo': category.is_demo,
    }


def usd_transaction_schema(transaction):
    return {
        'id': transaction.id,
        'type': 'expense',
        'currency': 'USD',
        'amount': float(transaction.amount),
        'description': transaction.description or '',
        'date': transaction.date.isoformat() if transaction.date else None,
        'category_id': transaction.category_id,
        'category_name': transaction.category.name if transaction.category else None,
        'is_demo': transaction.is_demo,
        'created_at': transaction.created_at.isoformat() if transaction.created_at else None,
    }
