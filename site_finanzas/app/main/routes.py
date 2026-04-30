import calendar
import json
from datetime import date, timedelta
from decimal import Decimal
from itertools import cycle, islice

from flask import render_template, redirect, url_for, flash, request, session, abort, jsonify
from flask_login import login_required, current_user, logout_user
from flask_babel import gettext as _, get_locale
from sqlalchemy import extract, func

from app import db
from app.main import main
from app.main.forms import TransactionForm, CategoryForm, BudgetForm, CategoryBudgetForm, ConfigForm, SMTPConfigForm, RecurringTransactionForm, SavingsGoalForm, ChangePasswordForm
from app.models import Transaction, Category, Budget, CategoryBudget, UserYear, User, AppConfig, UserEmailConfig, RecurringTransaction, SavingsGoal, UserSeenAnnouncement
from app.email_service import encrypt_smtp_password, send_user_email, encrypt_mfa_secret, decrypt_mfa_secret
from flask_jwt_extended import create_access_token

# (nombre, símbolo, nombre_moneda, código_ISO, locale_babel)
COUNTRIES_CURRENCIES = [
    ('Argentina',            '$',    'Peso Argentino',      'ARS', 'es_AR'),
    ('Bolivia',              'Bs.',  'Boliviano',           'BOB', 'es_BO'),
    ('Brasil',               'R$',   'Real',                'BRL', 'pt_BR'),
    ('Chile',                '$',    'Peso Chileno',        'CLP', 'es_CL'),
    ('Colombia',             '$',    'Peso Colombiano',     'COP', 'es_CO'),
    ('Costa Rica',           '₡',   'Colón',               'CRC', 'es_CR'),
    ('Cuba',                 '$',    'Peso Cubano',         'CUP', 'es_CU'),
    ('Ecuador',              '$',    'Dólar',               'USD', 'es_EC'),
    ('El Salvador',          '$',    'Dólar',               'USD', 'es_SV'),
    ('España',               '€',   'Euro',                'EUR', 'es_ES'),
    ('Estados Unidos',       '$',    'Dólar',               'USD', 'en_US'),
    ('Guatemala',            'Q',    'Quetzal',             'GTQ', 'es_GT'),
    ('Honduras',             'L',    'Lempira',             'HNL', 'es_HN'),
    ('México',               '$',    'Peso Mexicano',       'MXN', 'es_MX'),
    ('Nicaragua',            'C$',   'Córdoba',             'NIO', 'es_NI'),
    ('Panamá',               '$',    'Dólar',               'USD', 'es_PA'),
    ('Paraguay',             '₲',   'Guaraní',             'PYG', 'es_PY'),
    ('Perú',                 'S/',   'Sol',                 'PEN', 'es_PE'),
    ('Puerto Rico',          '$',    'Dólar',               'USD', 'es_PR'),
    ('República Dominicana', 'RD$',  'Peso Dominicano',     'DOP', 'es_DO'),
    ('Uruguay',              '$U',   'Peso Uruguayo',       'UYU', 'es_UY'),
    ('Venezuela',            'Bs.S', 'Bolívar Soberano',   'VES', 'es_VE'),
    ('Otro',                 '$',    'Personalizado',       'USD', 'es'),
]

CHART_COLORS = [
    '#00C896', '#F2C94C', '#38BDF8', '#EF4444',
    '#8B5CF6', '#1FE0B0', '#FFD76A', '#00A67E',
    '#F97316', '#A78BFA', '#34D399', '#FB7185',
]

DEFAULT_CATEGORY_COLORS = {
    'Alimentación':   '#00C896',
    'Transporte':     '#F2C94C',
    'Vivienda':       '#38BDF8',
    'Servicios':      '#EF4444',
    'Salud':          '#8B5CF6',
    'Educación':      '#F97316',
    'Ocio':           '#FB7185',
    'Otros':          '#1FE0B0',
    'Sueldo':         '#34D399',
    'Freelance':      '#FFD76A',
    'Inversiones':    '#60A5FA',
    'Otros Ingresos': '#A78BFA',
}

DEFAULT_PALETTE = [
    '#00C896', '#F2C94C', '#38BDF8', '#EF4444', '#8B5CF6',
    '#F97316', '#FB7185', '#1FE0B0', '#34D399', '#FFD76A',
    '#60A5FA', '#A78BFA', '#06B6D4', '#84CC16', '#EC4899',
    '#14B8A6', '#F59E0B', '#4ADE80', '#E879F9', '#67E8F9',
    '#FCA5A5',
]

CUSTOM_PALETTE = [
    '#00956E', '#B8952A', '#1A7FA3', '#B33030', '#6338B8',
    '#B85510', '#B8445A', '#0FA882', '#1F9E6E', '#C2A030',
    '#3A78C4', '#7560C4', '#0088A8', '#5E961A', '#B82878',
    '#0E877A', '#B87208', '#28A858', '#A830C0', '#3AACBF',
    '#B86060',
]

_TX_ENDPOINTS = {'main.transactions', 'main.add_transaction', 'main.edit_transaction',
                 'main.delete_transaction'}


def _locale_month_names(style='wide'):
    from babel.dates import get_month_names
    locale = str(get_locale() or 'es')
    names = get_month_names(style, locale=locale)
    return {i: names[i].capitalize() for i in range(1, 13)}


def _get_period():
    today = date.today()
    return (
        session.get('selected_year', today.year),
        session.get('selected_month', today.month),
    )


def _available_years():
    tx_years = (
        db.session.query(extract('year', Transaction.date).label('yr'))
        .filter(Transaction.user_id == current_user.id)
        .distinct()
        .all()
    )
    explicit_years = (
        db.session.query(UserYear.year)
        .filter(UserYear.user_id == current_user.id)
        .all()
    )
    years = sorted(set(
        [int(r.yr) for r in tx_years]
        + [r.year for r in explicit_years]
        + [date.today().year]
    ))
    return years


def _generate_pending_recurring(user_id, year, month):
    import calendar as _cal
    recs = RecurringTransaction.query.filter_by(user_id=user_id, is_active=True).all()
    changed = False
    for rec in recs:
        exists = Transaction.query.filter_by(
            user_id=user_id, recurring_id=rec.id
        ).filter(
            extract('year', Transaction.date) == year,
            extract('month', Transaction.date) == month,
        ).first()
        if not exists:
            last_day = _cal.monthrange(year, month)[1]
            day = min(rec.day_of_month, last_day)
            db.session.add(Transaction(
                user_id=user_id,
                category_id=rec.category_id,
                type=rec.type,
                amount=rec.amount,
                description=rec.description or '',
                date=date(year, month, day),
                recurring_id=rec.id,
            ))
            changed = True
    if changed:
        db.session.commit()


def _user_categories(type_filter=None):
    q = Category.query.filter(
        (Category.user_id == current_user.id) | (Category.user_id.is_(None))
    )
    if type_filter:
        q = q.filter_by(type=type_filter)
    return q.order_by(Category.name).all()


@main.app_context_processor
def inject_period():
    if current_user.is_authenticated:
        from babel.dates import get_month_names as _babel_months
        locale = str(get_locale() or 'es')
        _names = _babel_months('wide', locale=locale)
        month_names_nav = [(i, _names[i].capitalize()) for i in range(1, 13)]

        today = date.today()
        year = session.get('selected_year', today.year)
        month = session.get('selected_month', today.month)
        avail = _available_years()
        return dict(
            sel_year=year,
            sel_month=month,
            available_years=avail,
            next_year=avail[-1] + 1,
            today_year=today.year,
            month_names_nav=month_names_nav,
            is_tx_page=request.endpoint in _TX_ENDPOINTS,
            currency_symbol=current_user.currency_symbol or '$',
            currency_code=current_user.currency_code or 'USD',
            currency_locale=(current_user.currency_locale or 'es').replace('_', '-'),
            currency_decimals=_currency_decimals(current_user.currency_code or 'USD'),
            help_mode_enabled=bool(current_user.help_mode_enabled),
        )
    return {}


def _currency_decimals(code):
    try:
        from babel.numbers import get_currency_precision
        return get_currency_precision(code)
    except Exception:
        return 2


@main.app_context_processor
def inject_announcement():
    try:
        if not current_user.is_authenticated:
            return {'announcement_to_show': None}
        from app.announcements import CURRENT_ANNOUNCEMENT, ANNOUNCEMENTS
        from datetime import timezone as _tz
        ann = ANNOUNCEMENTS.get(CURRENT_ANNOUNCEMENT)
        if not ann:
            return {'announcement_to_show': None}
        created = current_user.created_at
        if created is None:
            return {'announcement_to_show': None}
        if created.tzinfo is None:
            created = created.replace(tzinfo=_tz.utc)
        if created >= ann['released_at']:
            return {'announcement_to_show': None}
        seen = UserSeenAnnouncement.query.filter_by(
            user_id=current_user.id,
            announcement_key=CURRENT_ANNOUNCEMENT,
        ).first()
        return {'announcement_to_show': None if seen else CURRENT_ANNOUNCEMENT}
    except Exception:
        return {'announcement_to_show': None}


# ── Announcement system ────────────────────────────────────────────────────────

@main.route('/announcements/<key>/seen', methods=['POST'])
@login_required
def mark_announcement_seen(key):
    from app.announcements import CURRENT_ANNOUNCEMENT
    if key == CURRENT_ANNOUNCEMENT:
        if not UserSeenAnnouncement.query.filter_by(
            user_id=current_user.id, announcement_key=key
        ).first():
            db.session.add(UserSeenAnnouncement(
                user_id=current_user.id, announcement_key=key
            ))
            db.session.commit()
    return '', 204


# ── Language selector ──────────────────────────────────────────────────────────

@main.route('/set-language/<lang>')
def set_language(lang):
    if lang in ('es', 'en'):
        if current_user.is_authenticated:
            current_user.language = lang
            db.session.commit()
        else:
            session['lang'] = lang
    referrer = request.referrer
    if referrer:
        return redirect(referrer)
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('auth.login'))


# ── Period management ──────────────────────────────────────────────────────────

@main.route('/set-period', methods=['POST'])
@login_required
def set_period():
    year = request.form.get('year', type=int)
    month = request.form.get('month', type=int)
    if year:
        session['selected_year'] = year
    if month and 1 <= month <= 12:
        session['selected_month'] = month
    return redirect(request.form.get('next') or url_for('main.dashboard'))


@main.route('/create-year', methods=['POST'])
@login_required
def create_year():
    year = request.form.get('year', type=int)
    if year and 2020 <= year <= 2100:
        if not UserYear.query.filter_by(user_id=current_user.id, year=year).first():
            db.session.add(UserYear(user_id=current_user.id, year=year))
            db.session.commit()
        session['selected_year'] = year
        session['selected_month'] = 1
        flash(_('Año %(year)s creado.', year=year), 'success')
    return redirect(url_for('main.dashboard'))


@main.route('/delete-year', methods=['POST'])
@login_required
def delete_year():
    year = request.form.get('year', type=int)
    if not year:
        return redirect(url_for('main.dashboard'))

    Transaction.query.filter(
        Transaction.user_id == current_user.id,
        extract('year', Transaction.date) == year,
    ).delete(synchronize_session=False)

    Budget.query.filter_by(user_id=current_user.id, year=year).delete()
    UserYear.query.filter_by(user_id=current_user.id, year=year).delete()
    db.session.commit()

    if session.get('selected_year') == year:
        session['selected_year'] = date.today().year
        session['selected_month'] = date.today().month

    flash(_('Año %(year)s eliminado junto con todos sus movimientos y presupuestos.', year=year), 'success')
    return redirect(url_for('main.dashboard'))


# ── Monthly dashboard ──────────────────────────────────────────────────────────

@main.route('/')
@main.route('/dashboard')
@login_required
def dashboard():
    year, month = _get_period()
    _generate_pending_recurring(current_user.id, year, month)

    monthly = Transaction.query.filter(
        Transaction.user_id == current_user.id,
        extract('year', Transaction.date) == year,
        extract('month', Transaction.date) == month,
    ).all()

    total_income = float(sum((t.amount for t in monthly if t.type == 'income'), Decimal('0')))
    total_expense = float(sum((t.amount for t in monthly if t.type == 'expense'), Decimal('0')))
    balance = total_income - total_expense

    budget = Budget.query.filter_by(user_id=current_user.id, year=year, month=month).first()
    budget_amount = float(budget.amount) if budget else 0.0
    budget_used_pct = min(
        (total_expense / budget_amount * 100) if budget_amount > 0 else 0, 100
    )

    rows = (
        db.session.query(
            Category.id, Category.name, Category.color,
            func.sum(Transaction.amount).label('total'),
        )
        .join(Transaction)
        .filter(
            Transaction.user_id == current_user.id,
            Transaction.type == 'expense',
            extract('year', Transaction.date) == year,
            extract('month', Transaction.date) == month,
        )
        .group_by(Category.id, Category.name, Category.color)
        .all()
    )
    _fb = list(islice(cycle(CHART_COLORS), max(len(rows), 1)))
    chart_colors_list = [r.color if r.color else _fb[i] for i, r in enumerate(rows)]

    recent = (
        Transaction.query
        .filter(
            Transaction.user_id == current_user.id,
            extract('year', Transaction.date) == year,
            extract('month', Transaction.date) == month,
        )
        .order_by(Transaction.date.desc())
        .limit(5)
        .all()
    )

    active_goals = SavingsGoal.query.filter_by(
        user_id=current_user.id, is_completed=False
    ).order_by(
        SavingsGoal.target_date.is_(None).asc(),
        SavingsGoal.target_date.asc()
    ).limit(4).all()

    cat_budgets = CategoryBudget.query.filter_by(user_id=current_user.id).all()
    cat_budget_data = []
    if cat_budgets:
        from app.services.finance import get_category_actuals
        actuals = get_category_actuals(
            current_user.id, year, month,
            [cb.category_id for cb in cat_budgets]
        )
        for cb in cat_budgets:
            budget_amt = float(cb.amount)
            actual_amt = actuals.get(cb.category_id, 0.0)
            used_pct = round(actual_amt / budget_amt * 100, 1) if budget_amt > 0 else 0.0
            cat_budget_data.append({
                'category_name': cb.category.name,
                'budget': budget_amt,
                'actual': actual_amt,
                'remaining': max(0.0, budget_amt - actual_amt),
                'used_pct': used_pct,
                'status': 'over' if used_pct >= 100 else 'warning' if used_pct >= 80 else 'ok',
            })

    month_names = _locale_month_names()
    return render_template(
        'main/dashboard.html',
        total_income=total_income,
        total_expense=total_expense,
        balance=balance,
        budget_amount=budget_amount,
        budget_used_pct=budget_used_pct,
        chart_labels=json.dumps([r.name for r in rows]),
        chart_data=json.dumps([float(r.total) for r in rows]),
        chart_colors=json.dumps(chart_colors_list),
        recent_transactions=recent,
        current_month=f"{month_names[month]} {year}",
        active_goals=active_goals,
        cat_budget_data=cat_budget_data,
        sel_month_name=month_names.get(month, ''),
    )


# ── Transactions ───────────────────────────────────────────────────────────────

@main.route('/transactions')
@login_required
def transactions():
    year, month = _get_period()
    _generate_pending_recurring(current_user.id, year, month)
    type_f = request.args.get('type', 'all')
    cat_f = request.args.get('category_id', 0, type=int)
    month_f = request.args.get('month', month, type=int)

    q = Transaction.query.filter(
        Transaction.user_id == current_user.id,
        extract('year', Transaction.date) == year,
    )
    if type_f in ('income', 'expense'):
        q = q.filter(Transaction.type == type_f)
    if cat_f:
        q = q.filter(Transaction.category_id == cat_f)
    if month_f and 1 <= month_f <= 12:
        q = q.filter(extract('month', Transaction.date) == month_f)

    return render_template(
        'main/transactions.html',
        transactions=q.order_by(Transaction.date.desc()).all(),
        categories=_user_categories(),
        type_filter=type_f,
        category_filter=cat_f,
        month_filter=month_f,
        month_names=_locale_month_names(),
    )


@main.route('/transactions/new', methods=['GET', 'POST'])
@login_required
def add_transaction():
    year, month = _get_period()
    last_day = calendar.monthrange(year, month)[1]
    date_min = date(year, month, 1)
    date_max = date(year, month, last_day)
    form = TransactionForm()
    form.type.choices = [('expense', _('Gasto')), ('income', _('Ingreso'))]
    all_cats = _user_categories()
    form.category_id.choices = [(c.id, c.name) for c in all_cats]
    cats_json = json.dumps([{'id': c.id, 'name': c.name, 'type': c.type} for c in all_cats])

    if request.method == 'GET':
        today = date.today()
        form.date.data = today if date_min <= today <= date_max else date_min

    if form.validate_on_submit():
        if not (date_min <= form.date.data <= date_max):
            flash(_('La fecha debe estar dentro de %(month)s %(year)s.',
                    month=_locale_month_names()[month], year=year), 'warning')
        else:
            cat = db.session.get(Category, form.category_id.data)
            if cat and cat.type != form.type.data:
                flash(_('La categoría no corresponde al tipo de movimiento seleccionado.'), 'warning')
            else:
                db.session.add(Transaction(
                    user_id=current_user.id,
                    type=form.type.data,
                    amount=form.amount.data,
                    category_id=form.category_id.data,
                    description=form.description.data,
                    date=form.date.data,
                ))
                db.session.commit()
                flash(_('Movimiento creado exitosamente.'), 'success')
                return redirect(url_for('main.transactions'))

    return render_template('main/transaction_form.html',
                           form=form, title=_('Nuevo Movimiento'), cats_json=cats_json,
                           date_min=date_min.isoformat(), date_max=date_max.isoformat(),
                           date_month_name=_locale_month_names()[month], date_year=year)


@main.route('/transactions/<int:tx_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_transaction(tx_id):
    tx = Transaction.query.filter_by(id=tx_id, user_id=current_user.id).first_or_404()
    year, month = tx.date.year, tx.date.month
    last_day = calendar.monthrange(year, month)[1]
    date_min = date(year, month, 1)
    date_max = date(year, month, last_day)
    form = TransactionForm(obj=tx)
    form.type.choices = [('expense', _('Gasto')), ('income', _('Ingreso'))]
    all_cats = _user_categories()
    form.category_id.choices = [(c.id, c.name) for c in all_cats]
    cats_json = json.dumps([{'id': c.id, 'name': c.name, 'type': c.type} for c in all_cats])

    if form.validate_on_submit():
        if not (date_min <= form.date.data <= date_max):
            flash(_('La fecha debe estar dentro de %(month)s %(year)s.',
                    month=_locale_month_names()[month], year=year), 'warning')
        else:
            cat = db.session.get(Category, form.category_id.data)
            if cat and cat.type != form.type.data:
                flash(_('La categoría no corresponde al tipo de movimiento.'), 'warning')
            else:
                tx.type = form.type.data
                tx.amount = form.amount.data
                tx.category_id = form.category_id.data
                tx.description = form.description.data
                tx.date = form.date.data
                db.session.commit()
                flash(_('Movimiento actualizado.'), 'success')
                return redirect(url_for('main.transactions'))

    return render_template('main/transaction_form.html',
                           form=form, title=_('Editar Movimiento'), cats_json=cats_json,
                           date_min=date_min.isoformat(), date_max=date_max.isoformat(),
                           date_month_name=_locale_month_names()[month], date_year=year)


@main.route('/transactions/<int:tx_id>/delete', methods=['POST'])
@login_required
def delete_transaction(tx_id):
    tx = Transaction.query.filter_by(id=tx_id, user_id=current_user.id).first_or_404()
    db.session.delete(tx)
    db.session.commit()
    flash(_('Movimiento eliminado.'), 'success')
    return redirect(url_for('main.transactions'))


# ── Categories ─────────────────────────────────────────────────────────────────

def _split_categories(type_filter):
    default = Category.query.filter(
        Category.user_id.is_(None), Category.type == type_filter
    ).order_by(Category.name).all()
    user = Category.query.filter(
        Category.user_id == current_user.id, Category.type == type_filter
    ).order_by(Category.name).all()
    return default, user


def _next_custom_color(user_id: int) -> str:
    used = {c.color for c in Category.query.filter_by(user_id=user_id).all() if c.color}
    for color in CUSTOM_PALETTE:
        if color not in used:
            return color
    count = Category.query.filter_by(user_id=user_id).count()
    return CUSTOM_PALETTE[count % len(CUSTOM_PALETTE)]


@main.route('/categories', methods=['GET', 'POST'])
@login_required
def categories():
    form = CategoryForm()
    form.type.choices = [('expense', _('Gasto')), ('income', _('Ingreso'))]
    if form.validate_on_submit():
        existing = Category.query.filter(
            Category.name == form.name.data,
            Category.type == form.type.data,
            (Category.user_id == current_user.id) | (Category.user_id.is_(None)),
        ).first()
        if existing:
            flash(_('Ya existe una categoría con ese nombre y tipo.'), 'warning')
        else:
            db.session.add(Category(
                name=form.name.data,
                type=form.type.data,
                user_id=current_user.id,
                color=_next_custom_color(current_user.id),
            ))
            db.session.commit()
            flash(_('Categoría creada.'), 'success')
        return redirect(url_for('main.categories'))

    default_expense, user_expense = _split_categories('expense')
    default_income, user_income = _split_categories('income')
    blocked = session.pop('_cat_blocked', None)

    return render_template(
        'main/categories.html',
        form=form,
        default_expense=default_expense,
        user_expense=user_expense,
        default_income=default_income,
        user_income=user_income,
        blocked=blocked,
    )


@main.route('/categories/<int:cat_id>/delete', methods=['POST'])
@login_required
def delete_category(cat_id):
    category = Category.query.filter_by(id=cat_id, user_id=current_user.id).first_or_404()

    tx_count  = Transaction.query.filter_by(category_id=cat_id).count()
    rec_count = RecurringTransaction.query.filter_by(category_id=cat_id).count()
    cb_count  = CategoryBudget.query.filter_by(category_id=cat_id).count()

    if tx_count or rec_count or cb_count:
        session['_cat_blocked'] = {
            'name': category.name,
            'tx':   tx_count,
            'rec':  rec_count,
            'cb':   cb_count,
        }
        return redirect(url_for('main.categories'))

    db.session.delete(category)
    db.session.commit()
    flash(_('Categoría eliminada.'), 'success')
    return redirect(url_for('main.categories'))


# ── Budget ─────────────────────────────────────────────────────────────────────

@main.route('/budget', methods=['GET', 'POST'])
@login_required
def budget():
    from app.services.finance import get_category_actuals
    month_names = _locale_month_names()
    year, month = _get_period()

    # ── Monthly budget form ────────────────────────────────────────────────────
    form = BudgetForm()
    form.month.choices = list(month_names.items())

    if form.validate_on_submit():
        existing = Budget.query.filter_by(
            user_id=current_user.id,
            year=year,
            month=form.month.data,
        ).first()
        if existing:
            existing.amount = form.amount.data
            flash(_('Presupuesto actualizado.'), 'success')
        else:
            db.session.add(Budget(
                user_id=current_user.id,
                year=year,
                month=form.month.data,
                amount=form.amount.data,
            ))
            flash(_('Presupuesto creado.'), 'success')
        db.session.commit()
        return redirect(url_for('main.budget'))

    if request.method == 'GET':
        edit_month = request.args.get('edit_month', type=int)
        form.month.data = edit_month if edit_month else month
        if edit_month:
            current_budget = Budget.query.filter_by(
                user_id=current_user.id, year=year, month=edit_month
            ).first()
            if current_budget:
                form.amount.data = current_budget.amount
        else:
            form.amount.data = None

    budgets = (
        Budget.query.filter_by(user_id=current_user.id, year=year)
        .order_by(Budget.month)
        .all()
    )

    # ── Category budget form ───────────────────────────────────────────────────
    cat_form = CategoryBudgetForm()
    expense_cats = (
        Category.query.filter(
            (Category.user_id == current_user.id) | (Category.user_id.is_(None)),
            Category.type == 'expense',
        ).order_by(Category.name).all()
    )

    # Exclude categories that already have a budget for this user
    cat_budgets = (
        CategoryBudget.query.filter_by(user_id=current_user.id)
        .order_by(CategoryBudget.id)
        .all()
    )
    taken_ids = {cb.category_id for cb in cat_budgets}
    available_cats = [c for c in expense_cats if c.id not in taken_ids]

    edit_cb_id = request.args.get('edit_cb', type=int)
    if edit_cb_id and request.method == 'GET':
        editing_cb = CategoryBudget.query.filter_by(
            id=edit_cb_id, user_id=current_user.id
        ).first()
        if editing_cb:
            cat_form.category_id.data = editing_cb.category_id
            cat_form.amount.data = editing_cb.amount
            available_cats = [c for c in expense_cats
                              if c.id not in taken_ids or c.id == editing_cb.category_id]

    cat_form.category_id.choices = [(c.id, c.name) for c in available_cats]

    # Build chart data: actual spending per category budget for current period
    actuals = get_category_actuals(
        current_user.id, year, month,
        [cb.category_id for cb in cat_budgets]
    )
    cat_budget_data = []
    for cb in cat_budgets:
        budget_amt = float(cb.amount)
        actual_amt = actuals.get(cb.category_id, 0.0)
        used_pct = round(actual_amt / budget_amt * 100, 1) if budget_amt > 0 else 0.0
        cat_budget_data.append({
            'id': cb.id,
            'category_name': cb.category.name,
            'budget': budget_amt,
            'actual': actual_amt,
            'remaining': max(0.0, budget_amt - actual_amt),
            'used_pct': used_pct,
            'status': 'over' if used_pct >= 100 else 'warning' if used_pct >= 80 else 'ok',
        })

    return render_template(
        'main/budget.html',
        form=form,
        cat_form=cat_form,
        budgets=budgets,
        cat_budgets=cat_budgets,
        cat_budget_data=cat_budget_data,
        month_names=month_names,
        budget_year=year,
        sel_month_name=month_names.get(month, ''),
        can_add_cat_budget=len(cat_budgets) < 3,
    )


@main.route('/budget/<int:budget_id>/delete', methods=['POST'])
@login_required
def delete_budget(budget_id):
    b = Budget.query.filter_by(id=budget_id, user_id=current_user.id).first_or_404()
    db.session.delete(b)
    db.session.commit()
    flash(_('Presupuesto eliminado.'), 'success')
    return redirect(url_for('main.budget'))


@main.route('/budget/categoria/guardar', methods=['POST'])
@login_required
def save_category_budget():
    month_names = _locale_month_names()
    cat_budgets_count = CategoryBudget.query.filter_by(user_id=current_user.id).count()

    cat_form = CategoryBudgetForm()
    expense_cats = Category.query.filter(
        (Category.user_id == current_user.id) | (Category.user_id.is_(None)),
        Category.type == 'expense',
    ).order_by(Category.name).all()
    taken_ids = {
        cb.category_id for cb in
        CategoryBudget.query.filter_by(user_id=current_user.id).all()
    }
    # Allow the same category if updating
    existing_for_cat = CategoryBudget.query.filter_by(
        user_id=current_user.id,
        category_id=request.form.get('category_id', type=int),
    ).first()
    available_cats = [
        c for c in expense_cats
        if c.id not in taken_ids or (existing_for_cat and c.id == existing_for_cat.category_id)
    ]
    cat_form.category_id.choices = [(c.id, c.name) for c in available_cats]

    if cat_form.validate_on_submit():
        if existing_for_cat:
            existing_for_cat.amount = cat_form.amount.data
            flash(_('Presupuesto de categoría actualizado.'), 'success')
        elif cat_budgets_count >= 3:
            flash(_('Ya tienes el máximo de 3 presupuestos de categoría.'), 'warning')
        else:
            db.session.add(CategoryBudget(
                user_id=current_user.id,
                category_id=cat_form.category_id.data,
                amount=cat_form.amount.data,
            ))
            flash(_('Presupuesto de categoría creado.'), 'success')
        db.session.commit()
    else:
        for field_errors in cat_form.errors.values():
            for e in field_errors:
                flash(e, 'danger')

    return redirect(url_for('main.budget'))


@main.route('/budget/categoria/<int:cb_id>/delete', methods=['POST'])
@login_required
def delete_category_budget(cb_id):
    cb = CategoryBudget.query.filter_by(id=cb_id, user_id=current_user.id).first_or_404()
    db.session.delete(cb)
    db.session.commit()
    flash(_('Presupuesto de categoría eliminado.'), 'success')
    return redirect(url_for('main.budget'))


# ── Global dashboard ───────────────────────────────────────────────────────────

@main.route('/dashboard/global')
@login_required
def global_dashboard():
    today = date.today()
    sel_year_g = request.args.get('year', session.get('selected_year', today.year), type=int)
    from_month = max(1, min(12, request.args.get('from_month', 1, type=int)))
    to_month = max(from_month, min(12, request.args.get('to_month', 12, type=int)))

    # ── Bar chart: expenses by category ──
    bar_rows = (
        db.session.query(
            Category.id, Category.name, Category.color,
            func.sum(Transaction.amount).label('total'),
        )
        .join(Transaction)
        .filter(
            Transaction.user_id == current_user.id,
            Transaction.type == 'expense',
            extract('year', Transaction.date) == sel_year_g,
            extract('month', Transaction.date) >= from_month,
            extract('month', Transaction.date) <= to_month,
        )
        .group_by(Category.id, Category.name, Category.color)
        .order_by(func.sum(Transaction.amount).desc())
        .all()
    )
    _fb = list(islice(cycle(CHART_COLORS), max(len(bar_rows), 1)))
    bar_colors = [r.color if r.color else _fb[i] for i, r in enumerate(bar_rows)]

    # ── Line chart: 12-month trend ──
    trend_income, trend_expense = [], []
    for m in range(1, 13):
        inc = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == current_user.id,
            Transaction.type == 'income',
            extract('year', Transaction.date) == sel_year_g,
            extract('month', Transaction.date) == m,
        ).scalar() or 0
        exp = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == current_user.id,
            Transaction.type == 'expense',
            extract('year', Transaction.date) == sel_year_g,
            extract('month', Transaction.date) == m,
        ).scalar() or 0
        trend_income.append(float(inc))
        trend_expense.append(float(exp))

    # ── Grouped bar chart: yearly totals (all years) ──
    all_tx = (
        db.session.query(
            extract('year', Transaction.date).label('yr'),
            Transaction.type,
            func.sum(Transaction.amount).label('total'),
        )
        .filter(Transaction.user_id == current_user.id)
        .group_by(extract('year', Transaction.date), Transaction.type)
        .order_by(extract('year', Transaction.date))
        .all()
    )
    all_yrs = sorted(set([int(r.yr) for r in all_tx]))
    yearly_income = [
        float(next((r.total for r in all_tx if int(r.yr) == y and r.type == 'income'), 0))
        for y in all_yrs
    ]
    yearly_expense = [
        float(next((r.total for r in all_tx if int(r.yr) == y and r.type == 'expense'), 0))
        for y in all_yrs
    ]

    # ── Multi-year trend line chart: expenses grouped by year and month ──
    multi_year_tx = (
        db.session.query(
            extract('year', Transaction.date).label('yr'),
            extract('month', Transaction.date).label('mo'),
            func.sum(Transaction.amount).label('total'),
        )
        .filter(
            Transaction.user_id == current_user.id,
            Transaction.type == 'expense'
        )
        .group_by(extract('year', Transaction.date), extract('month', Transaction.date))
        .order_by(extract('year', Transaction.date), extract('month', Transaction.date))
        .all()
    )
    
    multi_year_datasets = []
    my_color_cycle = cycle(CHART_COLORS)
    
    # We only show years where tracking info actually exists under 'expense'
    my_yrs = sorted(set([int(r.yr) for r in multi_year_tx]))
    
    for y in my_yrs:
        color = next(my_color_cycle)
        m_data = [0.0] * 12
        for r in multi_year_tx:
            if int(r.yr) == y:
                m_data[int(r.mo) - 1] = float(r.total)
                
        multi_year_datasets.append({
            "label": str(y),
            "data": m_data,
            "borderColor": color,
            "backgroundColor": "transparent",
            "borderWidth": 2.5,
            "pointRadius": 4,
            "pointHoverRadius": 7,
            "tension": 0.35,
            "fill": False
        })

    from babel.dates import get_month_names as _babel_months
    locale = str(get_locale() or 'es')
    _abbr = _babel_months('abbreviated', locale=locale)
    month_names = _locale_month_names()

    return render_template(
        'main/global_dashboard.html',
        sel_year_g=sel_year_g,
        from_month=from_month,
        to_month=to_month,
        bar_count=len(bar_rows),
        bar_labels=json.dumps([r.name for r in bar_rows]),
        bar_data=json.dumps([float(r.total) for r in bar_rows]),
        bar_colors=json.dumps(bar_colors),
        trend_income=json.dumps(trend_income),
        trend_expense=json.dumps(trend_expense),
        month_labels=json.dumps([_abbr[m].capitalize() for m in range(1, 13)]),
        yearly_count=len(all_yrs),
        yearly_labels=json.dumps([str(y) for y in all_yrs]),
        yearly_income=json.dumps(yearly_income),
        yearly_expense=json.dumps(yearly_expense),
        multi_year_trend_datasets=json.dumps(multi_year_datasets),
        month_names=month_names,
        available_years=_available_years(),
    )


# ── Metas de ahorro ───────────────────────────────────────────────────────────

@main.route('/metas')
@login_required
def metas():
    goals = SavingsGoal.query.filter_by(user_id=current_user.id)\
        .order_by(
            SavingsGoal.is_completed.asc(),
            SavingsGoal.target_date.is_(None).asc(),
            SavingsGoal.target_date.asc()
        ).all()

    active    = [g for g in goals if not g.is_completed]
    completed = [g for g in goals if g.is_completed]

    total_target  = float(sum(g.target_amount for g in active))
    total_saved   = float(sum(g.current_amount for g in active))

    chart_labels = json.dumps([g.name for g in active])
    chart_saved  = json.dumps([float(g.current_amount) for g in active])
    chart_remain = json.dumps([float(g.remaining) for g in active])

    return render_template('main/metas.html',
                           goals=goals,
                           active=active,
                           completed=completed,
                           total_target=total_target,
                           total_saved=total_saved,
                           chart_labels=chart_labels,
                           chart_saved=chart_saved,
                           chart_remain=chart_remain,
                           title=_('Metas de Ahorro'))


@main.route('/metas/nueva', methods=['GET', 'POST'])
@main.route('/metas/<int:goal_id>/editar', methods=['GET', 'POST'])
@login_required
def meta_form(goal_id=None):
    goal = None
    if goal_id:
        goal = SavingsGoal.query.filter_by(id=goal_id, user_id=current_user.id).first_or_404()

    form = SavingsGoalForm(obj=goal)
    if form.validate_on_submit():
        if goal is None:
            goal = SavingsGoal(user_id=current_user.id)
            db.session.add(goal)
        goal.name           = form.name.data
        goal.target_amount  = form.target_amount.data
        goal.current_amount = form.current_amount.data or 0
        goal.target_date    = form.target_date.data
        goal.description    = form.description.data
        db.session.commit()
        flash(_('Meta guardada exitosamente.'), 'success')
        return redirect(url_for('main.metas'))

    return render_template('main/meta_form.html', form=form, goal=goal,
                           title=_('Editar Meta') if goal else _('Nueva Meta'))


@main.route('/metas/<int:goal_id>/eliminar', methods=['POST'])
@login_required
def meta_delete(goal_id):
    goal = SavingsGoal.query.filter_by(id=goal_id, user_id=current_user.id).first_or_404()
    db.session.delete(goal)
    db.session.commit()
    flash(_('Meta eliminada.'), 'success')
    return redirect(url_for('main.metas'))


@main.route('/metas/<int:goal_id>/abonar', methods=['POST'])
@login_required
def meta_abonar(goal_id):
    goal = SavingsGoal.query.filter_by(id=goal_id, user_id=current_user.id).first_or_404()
    data = request.get_json(silent=True) or {}
    try:
        amount = float(data.get('amount', 0))
        if amount <= 0:
            return jsonify({'error': _('El monto debe ser mayor a cero.')}), 400
    except (TypeError, ValueError):
        return jsonify({'error': _('Monto inválido.')}), 400

    goal.current_amount = float(goal.current_amount) + amount
    if float(goal.current_amount) >= float(goal.target_amount):
        goal.is_completed = True
    db.session.commit()
    return jsonify({
        'ok': True,
        'current_amount': float(goal.current_amount),
        'progress_pct': goal.progress_pct,
        'is_completed': goal.is_completed,
    })


@main.route('/metas/<int:goal_id>/completar', methods=['POST'])
@login_required
def meta_completar(goal_id):
    goal = SavingsGoal.query.filter_by(id=goal_id, user_id=current_user.id).first_or_404()
    goal.is_completed = not goal.is_completed
    db.session.commit()
    return redirect(url_for('main.metas'))


# ── Transacciones recurrentes ──────────────────────────────────────────────────

@main.route('/recurrentes')
@login_required
def recurrentes():
    items = RecurringTransaction.query.filter_by(user_id=current_user.id)\
        .order_by(RecurringTransaction.is_active.desc(), RecurringTransaction.type, RecurringTransaction.description).all()

    active = [r for r in items if r.is_active]
    total_expense = float(sum(r.amount for r in active if r.type == 'expense'))
    total_income  = float(sum(r.amount for r in active if r.type == 'income'))

    # Chart data: group active by category
    cat_map = {}
    for r in active:
        key = (r.category.name, r.type)
        cat_map[key] = cat_map.get(key, 0) + float(r.amount)

    chart_labels  = json.dumps([k[0] for k in cat_map])
    chart_data    = json.dumps(list(cat_map.values()))
    chart_colors  = json.dumps(['#EF4444' if k[1] == 'expense' else '#00C896' for k in cat_map])

    return render_template('main/recurrentes.html',
                           items=items,
                           total_expense=total_expense,
                           total_income=total_income,
                           chart_labels=chart_labels,
                           chart_data=chart_data,
                           chart_colors=chart_colors,
                           chart_count=len(cat_map),
                           title=_('Recurrentes'))


@main.route('/recurrentes/nueva', methods=['GET', 'POST'])
@main.route('/recurrentes/<int:rec_id>/editar', methods=['GET', 'POST'])
@login_required
def recurrente_form(rec_id=None):
    rec = None
    if rec_id:
        rec = RecurringTransaction.query.filter_by(id=rec_id, user_id=current_user.id).first_or_404()

    form = RecurringTransactionForm(obj=rec)
    cats = _user_categories()
    form.category_id.choices = [(c.id, c.name) for c in cats]
    all_cats_json = json.dumps([{'id': c.id, 'name': c.name, 'type': c.type} for c in cats])

    if form.validate_on_submit():
        cat = db.session.get(Category, form.category_id.data)
        if not cat or cat.type != form.type.data:
            flash(_('La categoría no corresponde al tipo seleccionado.'), 'danger')
        else:
            if rec is None:
                rec = RecurringTransaction(user_id=current_user.id)
                db.session.add(rec)
            rec.type         = form.type.data
            rec.amount       = form.amount.data
            rec.category_id  = form.category_id.data
            rec.description  = form.description.data
            rec.day_of_month = form.day_of_month.data
            rec.is_active    = form.is_active.data
            db.session.commit()
            flash(_('Transacción recurrente guardada.'), 'success')
            return redirect(url_for('main.recurrentes'))

    if request.method == 'GET' and rec is None:
        form.is_active.data = True

    return render_template('main/recurrente_form.html',
                           form=form,
                           rec=rec,
                           all_cats_json=all_cats_json,
                           title=_('Editar Recurrente') if rec else _('Nueva Recurrente'))


@main.route('/recurrentes/<int:rec_id>/eliminar', methods=['POST'])
@login_required
def recurrente_delete(rec_id):
    rec = RecurringTransaction.query.filter_by(id=rec_id, user_id=current_user.id).first_or_404()
    db.session.delete(rec)
    db.session.commit()
    flash(_('Transacción recurrente eliminada.'), 'success')
    return redirect(url_for('main.recurrentes'))


# ── Configuración de cuenta ────────────────────────────────────────────────────

@main.route('/configurar', methods=['GET', 'POST'])
@login_required
def configurar():
    form = ConfigForm()
    smtp_form = SMTPConfigForm()

    form.country.choices = [(c[0], f"{c[0]}  —  {c[2]}") for c in COUNTRIES_CURRENCIES]
    _country_map = {c[0]: {'symbol': c[1], 'currency': c[2], 'code': c[3], 'locale': c[4]}
                    for c in COUNTRIES_CURRENCIES}

    app_config = AppConfig.get()

    email_config = current_user.email_config
    if not email_config:
        email_config = UserEmailConfig(user_id=current_user.id)
        db.session.add(email_config)

    if 'submit_smtp' in request.form:
        if not email_config.smtp_password_encrypted:
            smtp_form.password_is_empty = True

        if smtp_form.validate_on_submit():
            email_config.smtp_enabled = smtp_form.smtp_enabled.data
            if smtp_form.smtp_enabled.data:
                email_config.smtp_host = smtp_form.smtp_host.data
                email_config.smtp_port = smtp_form.smtp_port.data
                email_config.smtp_username = smtp_form.smtp_username.data
                email_config.smtp_use_tls = smtp_form.smtp_use_tls.data
                email_config.smtp_use_ssl = smtp_form.smtp_use_ssl.data
                email_config.sender_email = smtp_form.sender_email.data
                email_config.sender_name = smtp_form.sender_name.data
                if smtp_form.smtp_password.data:
                    email_config.smtp_password_encrypted = encrypt_smtp_password(smtp_form.smtp_password.data)
            db.session.commit()
            flash(_('Configuración de correo (SMTP) guardada exitosamente.'), 'success')
            return redirect(url_for('main.configurar'))

    elif 'submit_admin' in request.form:
        if not (current_user.is_admin and current_user.is_first_admin):
            abort(403)
        app_config.allow_registration = request.form.get('allow_registration') == 'on'
        db.session.commit()
        flash(_('Configuración de administrador guardada.'), 'success')
        return redirect(url_for('main.configurar'))

    elif form.validate_on_submit():
        country_data = _country_map.get(form.country.data, _country_map['Otro'])
        current_user.country = form.country.data
        current_user.currency_symbol = form.currency_symbol.data.strip() or '$'
        current_user.currency_code = country_data['code']
        current_user.currency_locale = country_data['locale']
        db.session.commit()
        flash(_('Configuración regional guardada exitosamente.'), 'success')
        return redirect(url_for('main.configurar'))

    if request.method == 'GET':
        form.country.data = current_user.country or 'Otro'
        form.currency_symbol.data = current_user.currency_symbol or '$'

        smtp_form.smtp_enabled.data = email_config.smtp_enabled
        smtp_form.smtp_host.data = email_config.smtp_host
        smtp_form.smtp_port.data = email_config.smtp_port
        smtp_form.smtp_username.data = email_config.smtp_username
        smtp_form.smtp_use_tls.data = email_config.smtp_use_tls
        smtp_form.smtp_use_ssl.data = email_config.smtp_use_ssl
        smtp_form.sender_email.data = email_config.sender_email
        smtp_form.sender_name.data = email_config.sender_name

    admin_smtp_available = False
    if not current_user.is_first_admin:
        admin = User.query.filter_by(is_first_admin=True).first()
        if (admin and admin.email_config and admin.email_config.smtp_enabled
                and admin.email_config.smtp_password_encrypted):
            admin_smtp_available = True

    countries_json = json.dumps(_country_map)
    return render_template('main/configurar.html',
                           form=form,
                           smtp_form=smtp_form,
                           pwd_form=ChangePasswordForm(),
                           email_config=email_config,
                           admin_smtp_available=admin_smtp_available,
                           countries_json=countries_json,
                           app_config=app_config,
                           title=_('Configurar Cuenta'))


@main.route('/configurar/theme', methods=['POST'])
@login_required
def set_theme():
    valid_themes = {'dark', 'ocean', 'carbon', 'dusk', 'forest', 'pearl', 'abyss', 'graphite'}
    theme = request.form.get('theme', 'dark')
    if theme not in valid_themes:
        theme = 'dark'
    current_user.theme = theme
    db.session.commit()
    return redirect(url_for('main.configurar'))


@main.route('/configurar/weekly-report', methods=['POST'])
@login_required
def save_weekly_report():
    current_user.weekly_report_enabled = request.form.get('weekly_report_enabled') == 'on'
    db.session.commit()
    flash(_('Configuración de reporte semanal guardada.'), 'success')
    return redirect(url_for('main.configurar'))


@main.route('/configurar/send-report-now', methods=['POST'])
@login_required
def send_report_now():
    from app.export.excel_builder import build_excel
    from app.email_service import send_weekly_report
    from datetime import date as _date_cls
    today = _date_cls.today()
    try:
        buf = build_excel(current_user, today.year, 1, today.month)
        filename = f"monetra_{current_user.username}_{today.year}.xlsx"
        ok, msg = send_weekly_report(current_user, buf.read(), filename)
        if ok:
            flash(_('Reporte enviado correctamente a %(email)s.', email=current_user.email), 'success')
        else:
            flash(_('Error al enviar el reporte: %(msg)s', msg=msg), 'danger')
    except Exception as e:
        flash(_('Error generando el reporte: %(e)s', e=str(e)), 'danger')
    return redirect(url_for('main.configurar'))


@main.route('/configurar/help-toggle', methods=['POST'])
@login_required
def help_toggle():
    current_user.help_mode_enabled = not current_user.help_mode_enabled
    db.session.commit()
    return redirect(url_for('main.configurar'))


@main.route('/onboarding/dismiss', methods=['POST'])
@login_required
def onboarding_dismiss():
    current_user.has_seen_onboarding = True
    db.session.commit()
    return jsonify({'ok': True})


@main.route('/configurar/generate-api-token', methods=['POST'])
@login_required
def generate_api_token():
    token = create_access_token(
        identity=str(current_user.id),
        expires_delta=timedelta(days=365),
    )
    return jsonify({"token": token}), 200


@main.route('/configurar/change-password', methods=['POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash(_('La contraseña actual es incorrecta.'), 'danger')
            return redirect(url_for('main.configurar'))
        current_user.set_password(form.new_password.data)
        db.session.commit()
        logout_user()
        flash(_('Contraseña actualizada correctamente. Inicia sesión con tu nueva contraseña.'), 'success')
        return redirect(url_for('auth.login'))
    for field in form:
        for error in field.errors:
            flash(error, 'danger')
    return redirect(url_for('main.configurar'))


@main.route('/configurar/mfa-setup', methods=['POST'])
@login_required
def mfa_setup():
    import pyotp, qrcode, io, base64
    secret = pyotp.random_base32()
    session['mfa_setup_secret'] = secret
    totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(
        name=current_user.email,
        issuer_name='Monetra'
    )
    img = qrcode.make(totp_uri)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    qr_b64 = base64.b64encode(buf.getvalue()).decode()
    return jsonify({'qr': qr_b64, 'secret': secret})


@main.route('/configurar/mfa-confirm', methods=['POST'])
@login_required
def mfa_confirm():
    import pyotp
    secret = session.get('mfa_setup_secret')
    if not secret:
        return jsonify({'error': _('Sesión expirada. Inicia el proceso nuevamente.')}), 400
    data = request.get_json(silent=True) or {}
    code = data.get('code', '')
    if not pyotp.TOTP(secret).verify(code):
        return jsonify({'error': _('Código incorrecto.')}), 400
    current_user.mfa_secret_encrypted = encrypt_mfa_secret(secret)
    current_user.mfa_enabled = True
    db.session.commit()
    session.pop('mfa_setup_secret', None)
    return jsonify({'ok': True})


@main.route('/configurar/mfa-disable', methods=['POST'])
@login_required
def mfa_disable():
    import pyotp
    if not current_user.mfa_enabled:
        return jsonify({'error': 'MFA no está activo.'}), 400
    data = request.get_json(silent=True) or {}
    code = data.get('code', '')
    secret = decrypt_mfa_secret(current_user.mfa_secret_encrypted)
    if not pyotp.TOTP(secret).verify(code):
        return jsonify({'error': _('Código incorrecto.')}), 400
    current_user.mfa_enabled = False
    current_user.mfa_secret_encrypted = None
    db.session.commit()
    return jsonify({'ok': True})


@main.route('/configurar/test-email', methods=['POST'])
@login_required
def test_email():
    success, msg = send_user_email(
        current_user,
        current_user.email,
        "Monetra - Correo de Prueba",
        "Hola,\n\nEste es un correo de prueba de tu configuración SMTP en Monetra.\nSi estás leyendo esto, tu configuración para el envío de correos, como recuperación de contraseña, funciona correctamente.\n\nSaludos."
    )
    if success:
        flash(_('Correo de prueba enviado correctamente. Revisa tu bandeja de entrada.'), 'success')
    else:
        flash(_('Error al enviar correo de prueba: %(msg)s', msg=msg), 'danger')
    return redirect(url_for('main.configurar'))
