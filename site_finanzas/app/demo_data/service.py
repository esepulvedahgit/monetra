import random
import calendar
from datetime import date
from decimal import Decimal

from sqlalchemy import func

from app import db
from app.models import Transaction, Category, UserYear


DEMO_EXPENSE_RANGES = {
    'Alimentación': (15, 120),
    'Transporte':   (5,  60),
    'Servicios':    (20, 150),
    'Salud':        (15, 200),
    'Ocio':         (10, 80),
    'Educación':    (20, 120),
    'Vivienda':     (200, 800),
    'Otros':        (5,  50),
}
_DEFAULT_RANGE = (10, 100)

# Categorías preferidas para demo (en orden de preferencia)
_PREFERRED_DEMO_CATS = ['Alimentación', 'Transporte', 'Servicios', 'Salud', 'Ocio']
_DEMO_CAT_LIMIT = 5


def has_demo_data(user_id):
    return db.session.query(Transaction).filter_by(
        user_id=user_id, is_demo=True
    ).first() is not None


def get_demo_data_summary(user_id):
    row = db.session.query(
        func.count(Transaction.id).label('count'),
        func.sum(Transaction.amount).label('total'),
        func.min(Transaction.date).label('from_date'),
        func.max(Transaction.date).label('to_date'),
    ).filter_by(user_id=user_id, is_demo=True).first()
    return {
        'count': row.count or 0,
        'total': float(row.total or 0),
        'from_date': row.from_date.isoformat() if row.from_date else None,
        'to_date':   row.to_date.isoformat()   if row.to_date   else None,
    }


def generate_demo_data(user_id, years=4, seed=42):
    if has_demo_data(user_id):
        return False, 'Ya existen datos demo cargados.'

    rng = random.Random(seed)

    all_expense_cats = Category.query.filter(
        (Category.user_id == user_id) | (Category.user_id.is_(None)),
        Category.type == 'expense',
    ).order_by(Category.name).all()

    # Usar las 5 categorías preferidas; si alguna no existe, completar con las disponibles
    cat_by_name = {c.name: c for c in all_expense_cats}
    expense_cats = [cat_by_name[n] for n in _PREFERRED_DEMO_CATS if n in cat_by_name]
    if len(expense_cats) < _DEMO_CAT_LIMIT:
        extras = [c for c in all_expense_cats if c not in expense_cats]
        expense_cats += extras[:_DEMO_CAT_LIMIT - len(expense_cats)]

    income_cat = Category.query.filter(
        (Category.user_id == user_id) | (Category.user_id.is_(None)),
        Category.type == 'income',
    ).first()

    if not expense_cats:
        return False, 'No hay categorías de gasto disponibles.'

    today = date.today()
    end_year = today.year
    start_year = end_year - years + 1

    transactions = []
    years_to_ensure = set()

    for year in range(start_year, end_year + 1):
        end_month = today.month if year == end_year else 12
        for month in range(1, end_month + 1):
            years_to_ensure.add(year)
            days_in_month = calendar.monthrange(year, month)[1]

            if income_cat:
                salary = round(rng.uniform(2500, 4000), 2)
                transactions.append(Transaction(
                    user_id=user_id,
                    category_id=income_cat.id,
                    type='income',
                    amount=Decimal(str(salary)),
                    description='Sueldo demo',
                    date=date(year, month, 5),
                    is_demo=True,
                ))

            for _ in range(rng.randint(10, 18)):
                cat = rng.choice(expense_cats)
                lo, hi = DEMO_EXPENSE_RANGES.get(cat.name, _DEFAULT_RANGE)
                amount = round(rng.uniform(lo, hi), 2)
                day = rng.randint(1, days_in_month)
                transactions.append(Transaction(
                    user_id=user_id,
                    category_id=cat.id,
                    type='expense',
                    amount=Decimal(str(amount)),
                    description=f'{cat.name} demo',
                    date=date(year, month, day),
                    is_demo=True,
                ))

    existing_years = {uy.year for uy in UserYear.query.filter_by(user_id=user_id).all()}
    for year in years_to_ensure:
        if year not in existing_years:
            db.session.add(UserYear(user_id=user_id, year=year))

    db.session.bulk_save_objects(transactions)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return False, 'Error al guardar los datos demo.'

    return True, f'{len(transactions)} transacciones demo generadas correctamente.'


def reset_demo_data(user_id):
    count = Transaction.query.filter_by(user_id=user_id, is_demo=True).delete()
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return 0
    return count
