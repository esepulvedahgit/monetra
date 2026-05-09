import json
import random
import calendar
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import func

from app import db
from app.models import (
    Transaction, Category, UserYear, DemoState,
    Budget, CategoryBudget, RecurringTransaction, SavingsGoal,
    UsdCategory, UsdTransaction, UsdBudget,
)


DEMO_EXPENSE_RANGES = {
    'Alimentación': (1200, 45000),
    'Transporte':   (1200, 30000),
    'Servicios':    (5000, 70000),
    'Salud':        (3000, 90000),
    'Ocio':         (1500, 35000),
    'Educación':    (10000, 120000),
    'Vivienda':     (80000, 450000),
    'Otros':        (1200, 25000),
}
_DEFAULT_RANGE = (1200, 50000)
_DEMO_MAX_AMOUNT = Decimal('1000000')

_PREFERRED_DEMO_CATS = ['Alimentación', 'Transporte', 'Servicios', 'Salud', 'Ocio']
_CAT_BUDGET_CATS    = ['Alimentación', 'Transporte', 'Ocio']

_USD_DEMO_CATEGORIES = {
    'Software': '#38BDF8',
    'Streaming': '#FB7185',
    'Viajes': '#F97316',
    'Compras online': '#8B5CF6',
}

_USD_EXPENSE_RANGES = {
    'Software': (8, 45),
    'Streaming': (6, 28),
    'Viajes': (35, 180),
    'Compras online': (18, 220),
}


def has_demo_data(user_id: int) -> bool:
    return _demo_transaction_count(user_id) > 0


def _demo_transaction_count(user_id: int) -> int:
    return Transaction.query.filter_by(user_id=user_id, is_demo=True).count()


def get_demo_years(user_id: int) -> set:
    state = DemoState.query.filter_by(user_id=user_id).first()
    if not state:
        return set()
    try:
        return set(json.loads(state.demo_years))
    except (ValueError, TypeError):
        return set()


def get_demo_data_summary(user_id: int) -> dict:
    row = db.session.query(
        func.count(Transaction.id).label('count'),
        func.sum(Transaction.amount).label('total'),
        func.min(Transaction.date).label('from_date'),
        func.max(Transaction.date).label('to_date'),
    ).filter_by(user_id=user_id, is_demo=True).first()
    demo_years = sorted(get_demo_years(user_id))
    return {
        'count':      row.count or 0,
        'total':      float(row.total or 0),
        'from_date':  row.from_date.isoformat() if row.from_date else None,
        'to_date':    row.to_date.isoformat()   if row.to_date   else None,
        'demo_years': demo_years,
    }


def generate_demo_data(user_id: int, seed: int = 42):
    if has_demo_data(user_id):
        return False, 'Ya existen datos demo cargados.'

    stale_state = DemoState.query.filter_by(user_id=user_id).first()
    if stale_state:
        reset_demo_data(user_id)

    rng = random.Random(seed)
    today = date.today()
    end_year   = today.year - 1
    start_year = today.year - 3
    demo_year_list = list(range(start_year, end_year + 1))

    # ── Resolve categories ────────────────────────────────────────────────────
    def _get_cats(type_):
        return Category.query.filter(
            (Category.user_id == user_id) | (Category.user_id.is_(None)),
            Category.type == type_,
        ).order_by(Category.name).all()

    all_expense_cats = _get_cats('expense')
    all_income_cats  = _get_cats('income')

    if not all_expense_cats:
        return False, 'No hay categorías de gasto disponibles.'

    cat_by_name = {c.name: c for c in all_expense_cats + all_income_cats}

    expense_cats = [cat_by_name[n] for n in _PREFERRED_DEMO_CATS if n in cat_by_name]
    extras = [c for c in all_expense_cats if c not in expense_cats]
    expense_cats += extras[:max(0, 5 - len(expense_cats))]

    income_cat = cat_by_name.get('Ingresos') or (all_income_cats[0] if all_income_cats else None)

    cb_cats = [cat_by_name[n] for n in _CAT_BUDGET_CATS if n in cat_by_name]

    vivienda_cat = cat_by_name.get('Vivienda') or expense_cats[0]
    ocio_cat     = cat_by_name.get('Ocio')     or expense_cats[0]
    salud_cat    = cat_by_name.get('Salud')    or expense_cats[0]

    # ── Snapshot existing years ────────────────────────────────────────────────
    existing_years = {uy.year for uy in UserYear.query.filter_by(user_id=user_id).all()}

    transactions = []
    budgets      = []
    cat_budgets  = []
    usd_transactions = []
    usd_budgets = []

    usd_cats = {}
    for name, color in _USD_DEMO_CATEGORIES.items():
        cat = UsdCategory.query.filter_by(user_id=user_id, name=name).first()
        if cat is None:
            cat = UsdCategory(user_id=user_id, name=name, color=color, is_demo=True)
            db.session.add(cat)
            db.session.flush()
        usd_cats[name] = cat
    existing_usd_budget_periods = {
        (b.year, b.month)
        for b in UsdBudget.query.filter(
            UsdBudget.user_id == user_id,
            UsdBudget.year.in_(demo_year_list),
        ).all()
    }

    for year in demo_year_list:
        for month in range(1, 13):
            days_in_month = calendar.monthrange(year, month)[1]

            # Income transaction
            if income_cat:
                salary = round(rng.uniform(350000, 900000), 2)
                transactions.append(Transaction(
                    user_id=user_id, category_id=income_cat.id, type='income',
                    amount=Decimal(str(salary)), description='Sueldo demo',
                    date=date(year, month, 5), is_demo=True,
                ))

            # Expense transactions
            month_expenses = []
            for _ in range(rng.randint(10, 18)):
                cat = rng.choice(expense_cats)
                lo, hi = DEMO_EXPENSE_RANGES.get(cat.name, _DEFAULT_RANGE)
                amount = round(rng.uniform(lo, hi), 2)
                day = rng.randint(1, days_in_month)
                tx = Transaction(
                    user_id=user_id, category_id=cat.id, type='expense',
                    amount=Decimal(str(amount)), description=f'{cat.name} demo',
                    date=date(year, month, day), is_demo=True,
                )
                transactions.append(tx)
                month_expenses.append(amount)

            # Monthly budget (slightly above expected monthly spend)
            total_month_expense = sum(month_expenses)
            budget_amount = round(total_month_expense * rng.uniform(1.05, 1.25), 2)
            budget_amount = min(Decimal(str(budget_amount)), _DEMO_MAX_AMOUNT)
            budgets.append(Budget(
                user_id=user_id, year=year, month=month,
                amount=budget_amount,
            ))

            # Category budgets (up to 3 categories)
            for cb_cat in cb_cats[:3]:
                lo, hi = DEMO_EXPENSE_RANGES.get(cb_cat.name, _DEFAULT_RANGE)
                cb_amount = round(hi * rng.uniform(2.5, 4.5), 2)
                cb_amount = min(Decimal(str(cb_amount)), _DEMO_MAX_AMOUNT)
                cat_budgets.append(CategoryBudget(
                    user_id=user_id, year=year, month=month,
                    category_id=cb_cat.id,
                    amount=cb_amount,
                ))

            # USD expenses + monthly USD budget. These feed both the standalone
            # USD dashboard and the unified analytics layer through conversion.
            usd_month_expenses = []
            usd_tx_count = rng.randint(3, 7)
            for _ in range(usd_tx_count):
                usd_name = rng.choice(list(usd_cats.keys()))
                usd_cat = usd_cats[usd_name]
                lo, hi = _USD_EXPENSE_RANGES[usd_name]
                amount = round(rng.uniform(lo, hi), 2)
                day = rng.randint(1, days_in_month)
                usd_transactions.append(UsdTransaction(
                    user_id=user_id,
                    category_id=usd_cat.id,
                    amount=Decimal(str(amount)),
                    description=f'{usd_name} demo USD',
                    date=date(year, month, day),
                    is_demo=True,
                ))
                usd_month_expenses.append(amount)

            if (year, month) not in existing_usd_budget_periods:
                usd_budget_amount = round(sum(usd_month_expenses) * rng.uniform(1.10, 1.35), 2)
                usd_budgets.append(UsdBudget(
                    user_id=user_id,
                    year=year,
                    month=month,
                    amount=Decimal(str(usd_budget_amount)),
                    is_demo=True,
                ))

    # ── Recurring transactions (inactive — showcase only) ─────────────────────
    end_date_rec = date(end_year, 12, 31)
    created_at_rec = datetime(start_year, 1, 1, tzinfo=timezone.utc)

    recurring = []
    if income_cat:
        recurring.append(RecurringTransaction(
            user_id=user_id, category_id=income_cat.id, type='income',
            amount=Decimal('180000'), description='Freelance demo',
            day_of_month=10, is_active=False, is_demo=True,
            end_date=end_date_rec, created_at=created_at_rec,
        ))
        recurring.append(RecurringTransaction(
            user_id=user_id, category_id=income_cat.id, type='income',
            amount=Decimal('75000'), description='Bono mensual demo',
            day_of_month=28, is_active=False, is_demo=True,
            end_date=end_date_rec, created_at=created_at_rec,
        ))

    recurring.extend([
        RecurringTransaction(
            user_id=user_id, category_id=vivienda_cat.id, type='expense',
            amount=Decimal('320000'), description='Arriendo demo',
            day_of_month=1, is_active=False, is_demo=True,
            end_date=end_date_rec, created_at=created_at_rec,
        ),
        RecurringTransaction(
            user_id=user_id, category_id=ocio_cat.id, type='expense',
            amount=Decimal('12000'), description='Netflix demo',
            day_of_month=15, is_active=False, is_demo=True,
            end_date=end_date_rec, created_at=created_at_rec,
        ),
        RecurringTransaction(
            user_id=user_id, category_id=salud_cat.id, type='expense',
            amount=Decimal('85000'), description='Seguro médico demo',
            day_of_month=5, is_active=False, is_demo=True,
            end_date=end_date_rec, created_at=created_at_rec,
        ),
        RecurringTransaction(
            user_id=user_id, category_id=salud_cat.id, type='expense',
            amount=Decimal('18000'), description='Gym demo',
            day_of_month=3, is_active=False, is_demo=True,
            end_date=end_date_rec, created_at=created_at_rec,
        ),
    ])

    # ── Savings goals ─────────────────────────────────────────────────────────
    goals = [
        SavingsGoal(user_id=user_id, name='Fondo de emergencia',
                    target_amount=Decimal('600000'), current_amount=Decimal('510000'),
                    description='3 meses de gastos cubiertos', is_demo=True),
        SavingsGoal(user_id=user_id, name='Vacaciones Europa',
                    target_amount=Decimal('450000'), current_amount=Decimal('270000'),
                    target_date=date(today.year + 1, 6, 30),
                    description='Vuelos, hotel y actividades', is_demo=True),
        SavingsGoal(user_id=user_id, name='Auto nuevo',
                    target_amount=Decimal('900000'), current_amount=Decimal('260000'),
                    target_date=date(today.year + 2, 12, 31),
                    description='Ahorro para pie inicial', is_demo=True),
        SavingsGoal(user_id=user_id, name='MacBook Pro',
                    target_amount=Decimal('220000'), current_amount=Decimal('220000'),
                    is_completed=True, description='Meta cumplida', is_demo=True),
        SavingsGoal(user_id=user_id, name='Renovación hogar',
                    target_amount=Decimal('700000'), current_amount=Decimal('120000'),
                    target_date=date(today.year + 1, 12, 31),
                    description='Muebles y electrodomésticos', is_demo=True),
    ]

    # ── Persist DemoState ─────────────────────────────────────────────────────
    state = DemoState.query.filter_by(user_id=user_id).first()
    if state:
        state.pre_demo_years = json.dumps(sorted(existing_years))
        state.demo_years = json.dumps(demo_year_list)
        state.loaded_at = datetime.now(timezone.utc)
    else:
        db.session.add(DemoState(
            user_id=user_id,
            pre_demo_years=json.dumps(sorted(existing_years)),
            demo_years=json.dumps(demo_year_list),
        ))

    for year in demo_year_list:
        if year not in existing_years:
            db.session.add(UserYear(user_id=user_id, year=year))

    try:
        db.session.bulk_save_objects(transactions)
        db.session.bulk_save_objects(budgets)
        db.session.bulk_save_objects(cat_budgets)
        db.session.bulk_save_objects(usd_transactions)
        db.session.bulk_save_objects(usd_budgets)
        for rec in recurring:
            db.session.add(rec)
        for goal in goals:
            db.session.add(goal)

        db.session.flush()
        if not _global_demo_aggregates_are_ready(user_id, demo_year_list):
            db.session.rollback()
            return False, 'Los datos demo se generaron, pero no alimentan los paneles globales.'

        db.session.commit()
    except Exception:
        db.session.rollback()
        return False, 'Error al guardar los datos demo.'

    n_tx = len(transactions)
    return True, (
        f'{n_tx} transacciones, {len(budgets)} presupuestos, '
        f'{len(usd_transactions)} gastos USD, {len(usd_budgets)} presupuestos USD, '
        f'{len(recurring)} recurrentes y {len(goals)} metas demo generados '
        f'para {start_year}–{end_year}.'
    )


def reset_demo_data(user_id: int) -> int:
    state = DemoState.query.filter_by(user_id=user_id).first()
    demo_years_list = []
    pre_demo_years = []
    if state:
        try:
            demo_years_list = json.loads(state.demo_years)
        except (ValueError, TypeError):
            demo_years_list = []
        try:
            pre_demo_years = json.loads(state.pre_demo_years)
        except (ValueError, TypeError):
            pre_demo_years = []

    count = Transaction.query.filter_by(user_id=user_id, is_demo=True).delete()
    RecurringTransaction.query.filter_by(user_id=user_id, is_demo=True).delete()
    SavingsGoal.query.filter_by(user_id=user_id, is_demo=True).delete()
    UsdTransaction.query.filter_by(user_id=user_id, is_demo=True).delete()
    UsdBudget.query.filter_by(user_id=user_id, is_demo=True).delete()
    UsdCategory.query.filter_by(user_id=user_id, is_demo=True).delete()

    if demo_years_list:
        Budget.query.filter(
            Budget.user_id == user_id,
            Budget.year.in_(demo_years_list),
        ).delete(synchronize_session=False)
        CategoryBudget.query.filter(
            CategoryBudget.user_id == user_id,
            CategoryBudget.year.in_(demo_years_list),
        ).delete(synchronize_session=False)
        demo_created_years = sorted(set(demo_years_list) - set(pre_demo_years))
        if demo_created_years:
            UserYear.query.filter(
                UserYear.user_id == user_id,
                UserYear.year.in_(demo_created_years),
            ).delete(synchronize_session=False)

    if state:
        db.session.delete(state)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return 0
    return count


def _global_demo_aggregates_are_ready(user_id: int, demo_years: list[int]) -> bool:
    from app.services.finance import get_global_summary

    if not demo_years:
        return False

    summary = get_global_summary(user_id, demo_years[-1], 1, 12)
    yearly_years = {row['year'] for row in summary['yearly_summary']}
    trend_years = {
        row['year'] for row in summary['multi_year_expense_trend']
        if any(amount > 0 for amount in row['monthly'])
    }

    expected_years = set(demo_years)
    return expected_years.issubset(yearly_years) and expected_years.issubset(trend_years)
