import calendar
import hashlib
import json
import secrets
from datetime import date, timedelta
from decimal import Decimal
from itertools import cycle, islice

import threading

from flask import render_template, redirect, url_for, flash, request, session, abort, jsonify, current_app
from flask_login import login_required, current_user, logout_user
from flask_babel import gettext as _, get_locale
from sqlalchemy import extract, func

from app import db
from app.main import main
from app.main.forms import TransactionForm, CategoryForm, BudgetForm, CategoryBudgetForm, ConfigForm, SMTPConfigForm, RecurringTransactionForm, SavingsGoalForm, ChangePasswordForm, CustomBudgetForm, AIConfigForm
from app.models import Transaction, Category, Budget, CategoryBudget, UserYear, User, AppConfig, UserEmailConfig, RecurringTransaction, SavingsGoal, UserSeenAnnouncement, CustomBudget, UserAIConfig, ApiToken
from app.email_service import encrypt_smtp_password, send_user_email, encrypt_mfa_secret, decrypt_mfa_secret, encrypt_ai_token, send_security_alert_email

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


def _generate_pending_recurring(user_id, year, month, commit=True):
    from app.services.finance import generate_pending_recurring
    return generate_pending_recurring(user_id, year, month, commit=commit)


def _generate_pending_recurring_range(user_id, year, from_month, to_month):
    from app.services.finance import generate_pending_recurring_range
    return generate_pending_recurring_range(user_id, year, from_month, to_month)


def _backfill_recurring(user_id, rec):
    rec_start = rec.created_at.date() if rec.created_at else date.today()
    cur = date(rec_start.year, rec_start.month, 1)
    annual_end = date(rec_start.year, 12, 31)
    end_date = rec.end_date if rec.end_date and rec.end_date.year == rec_start.year else annual_end
    end = date(end_date.year, end_date.month, 1)

    added = 0
    years_needed = set()

    while cur <= end:
        exists = Transaction.query.filter_by(
            user_id=user_id, recurring_id=rec.id
        ).filter(
            extract('year', Transaction.date) == cur.year,
            extract('month', Transaction.date) == cur.month,
        ).first()
        if not exists:
            last_day = calendar.monthrange(cur.year, cur.month)[1]
            tx_date = date(cur.year, cur.month, min(rec.day_of_month, last_day))
            if tx_date < rec_start or tx_date > end_date:
                cur = date(cur.year + 1, 1, 1) if cur.month == 12 else date(cur.year, cur.month + 1, 1)
                continue
            db.session.add(Transaction(
                user_id=user_id,
                category_id=rec.category_id,
                type=rec.type,
                amount=rec.amount,
                description=rec.description or '',
                date=tx_date,
                recurring_id=rec.id,
            ))
            years_needed.add(cur.year)
            added += 1
        cur = date(cur.year + 1, 1, 1) if cur.month == 12 else date(cur.year, cur.month + 1, 1)

    if years_needed:
        existing_years = {uy.year for uy in UserYear.query.filter_by(user_id=user_id).all()}
        for yr in years_needed:
            if yr not in existing_years:
                db.session.add(UserYear(user_id=user_id, year=yr))

    if added:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
    return added


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

        from app.demo_data.service import get_demo_years
        demo_years = get_demo_years(current_user.id)

        _ai_cfg = getattr(current_user, 'ai_config', None)
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
            demo_years=demo_years,
            is_demo_year=(year in demo_years),
            scan_categories=_user_categories(),
            scanner_enabled=bool(_ai_cfg and _ai_cfg.enabled),
        )
    return {}


def _currency_decimals(code):
    try:
        from babel.numbers import get_currency_precision
        return get_currency_precision(code)
    except Exception:
        return 2


def _is_demo_year(year: int) -> bool:
    from app.demo_data.service import get_demo_years
    return year in get_demo_years(current_user.id)


def _reject_demo(redirect_target='main.dashboard'):
    flash(_('Este registro es de demostración y no puede modificarse.'), 'warning')
    return redirect(url_for(redirect_target))


@main.app_context_processor
def inject_account_types():
    """Modular list of account sections shown in the account-switcher modal.
    Add a new dict here to expose another account type — no template changes needed."""
    if not current_user.is_authenticated:
        return {'account_types': []}
    endpoint = request.endpoint or ''
    return {
        'account_types': [
            {
                'key': 'main',
                'name': _('Cuenta principal'),
                'description': _('Movimientos en moneda local'),
                'icon': 'bi-cash-coin',
                'url': url_for('main.transactions'),
                'active': endpoint.startswith('main.') and 'transaction' in endpoint,
            },
            {
                'key': 'usd',
                'name': _('Cuenta USD'),
                'description': _('Gastos en dólares'),
                'icon': 'bi-currency-dollar',
                'url': url_for('usd.dashboard'),
                'active': endpoint.startswith('usd.'),
            },
            {
                'key': 'consolidated',
                'name': _('Consolidado'),
                'description': _('Vista unificada en moneda principal'),
                'icon': 'bi-graph-up-arrow',
                'url': url_for('analytics.consolidated'),
                'active': endpoint.startswith('analytics.'),
            },
        ]
    }


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

    from app.services.finance import get_monthly_summary
    summary = get_monthly_summary(current_user.id, year, month)
    total_income    = summary['total_income']
    total_expense   = summary['total_expense']
    balance         = summary['balance']
    budget_amount   = summary['budget_amount']
    budget_used_pct = min(summary['budget_used_pct'] or 0, 100)

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

    cat_budgets = CategoryBudget.query.filter_by(user_id=current_user.id, year=year, month=month).all()
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

    # ── Custom budget: only the budget created for the selected month ────────
    custom_budget = _custom_budget_for_period(current_user.id, year, month)
    custom_budget_data = None
    if custom_budget:
        from app.services.finance import calculate_custom_budget_usage
        usage = calculate_custom_budget_usage(current_user.id, custom_budget)
        actual = usage['total_consumed']
        used_pct = usage['usage_percent']
        custom_budget_data = {
            'actual': actual,
            'remaining': usage['remaining'],
            'used_pct': min(used_pct, 100),
            'status': 'over' if used_pct >= 100 else 'warning' if used_pct >= 80 else 'ok',
        }

    month_names = _locale_month_names()

    # ── Insights (alerts + forecast + health score) ───────────────────────────
    insights_alerts, insights_forecast, insights_health, insights_maturity = [], None, None, None
    try:
        from app.insights import services as insights_service
        insights_alerts = insights_service.get_dashboard_alerts(current_user.id, year, month)
        insights_forecast = insights_service.get_monthly_forecast(current_user.id, year, month)
        insights_health = insights_service.get_health_score(current_user.id, year, month)
        insights_maturity = insights_service.get_data_maturity(current_user.id, year, month)
    except Exception:
        import logging
        logging.getLogger(__name__).exception('insights pipeline failed for user_id=%s', current_user.id)

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
        custom_budget=custom_budget,
        custom_budget_data=custom_budget_data,
        sel_month_name=month_names.get(month, ''),
        alerts=insights_alerts,
        forecast=insights_forecast,
        health=insights_health,
        insights_maturity=insights_maturity,
        alerts_limit=3,
    )


# ── Transactions ───────────────────────────────────────────────────────────────

@main.route('/transactions')
@login_required
def transactions():
    year, month = _get_period()
    _generate_pending_recurring(current_user.id, year, month)
    type_f = request.args.get('type', 'all')
    cat_f = request.args.get('category_id', 0, type=int)
    day_f = request.args.get('day', 0, type=int)
    last_day = calendar.monthrange(year, month)[1]

    q = Transaction.query.filter(
        Transaction.user_id == current_user.id,
        extract('year', Transaction.date) == year,
        extract('month', Transaction.date) == month,
    )
    if type_f in ('income', 'expense'):
        q = q.filter(Transaction.type == type_f)
    if cat_f:
        q = q.filter(Transaction.category_id == cat_f)
    if day_f and 1 <= day_f <= last_day:
        q = q.filter(extract('day', Transaction.date) == day_f)
    else:
        day_f = 0

    active_rec_ids   = {r.id for r in RecurringTransaction.query.filter_by(
        user_id=current_user.id, is_active=True).all()}
    inactive_rec_ids = {r.id for r in RecurringTransaction.query.filter_by(
        user_id=current_user.id, is_active=False).all()}
    custom_budget_category_ids = {
        cb.category_id for cb in CustomBudget.query.filter(
            CustomBudget.user_id == current_user.id,
            extract('year', CustomBudget.start_date) == year,
            extract('month', CustomBudget.start_date) == month,
        ).all()
    }

    return render_template(
        'main/transactions.html',
        transactions=q.order_by(Transaction.date.desc()).all(),
        categories=_user_categories(),
        type_filter=type_f,
        category_filter=cat_f,
        day_filter=day_f,
        days_in_month=range(1, last_day + 1),
        selected_month_name=_locale_month_names().get(month, ''),
        active_rec_ids=active_rec_ids,
        inactive_rec_ids=inactive_rec_ids,
        custom_budget_category_ids=custom_budget_category_ids,
    )


@main.route('/transactions/new', methods=['GET', 'POST'])
@login_required
def add_transaction():
    year, month = _get_period()
    if _is_demo_year(year):
        return _reject_demo('main.transactions')
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
            cat = Category.query.filter(
                Category.id == form.category_id.data,
                (Category.user_id == current_user.id) | (Category.user_id.is_(None)),
            ).first()
            if not cat:
                flash(_('La categoría seleccionada no es válida.'), 'warning')
            elif cat.type != form.type.data:
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
                           date_month_name=_locale_month_names()[month], date_year=year,
                            custom_budget_info=_custom_budget_info(year, month))


@main.route('/transactions/<int:tx_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_transaction(tx_id):
    tx = Transaction.query.filter_by(id=tx_id, user_id=current_user.id).first_or_404()
    if tx.is_demo:
        return _reject_demo('main.transactions')
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
            cat = Category.query.filter(
                Category.id == form.category_id.data,
                (Category.user_id == current_user.id) | (Category.user_id.is_(None)),
            ).first()
            if not cat:
                flash(_('La categoría seleccionada no es válida.'), 'warning')
            elif cat.type != form.type.data:
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
                           date_month_name=_locale_month_names()[month], date_year=year,
                            custom_budget_info=_custom_budget_info(year, month))


@main.route('/transactions/<int:tx_id>/delete', methods=['POST'])
@login_required
def delete_transaction(tx_id):
    tx = Transaction.query.filter_by(id=tx_id, user_id=current_user.id).first_or_404()
    if tx.is_demo:
        return _reject_demo('main.transactions')
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


@main.route('/ajax/categories')
@login_required
def ajax_categories():
    cats = _user_categories()
    return jsonify([{'id': c.id, 'name': c.name, 'type': c.type} for c in cats])


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

    if CustomBudget.query.filter_by(category_id=cat_id, user_id=current_user.id).first():
        flash(_('Esta categoría pertenece a un presupuesto personalizado. Elimínalo desde la sección Presupuesto.'), 'warning')
        return redirect(url_for('main.categories'))

    tx_count  = Transaction.query.filter_by(user_id=current_user.id, category_id=cat_id).count()
    rec_count = RecurringTransaction.query.filter_by(user_id=current_user.id, category_id=cat_id).count()
    cb_count  = CategoryBudget.query.filter_by(user_id=current_user.id, category_id=cat_id).count()

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


def _custom_budget_info(year=None, month=None):
    """Returns serialisable dict for the user's custom budget in one month, or None."""
    if year is None or month is None:
        year, month = _get_period()
    cb = _custom_budget_for_period(current_user.id, year, month)
    if not cb:
        return None
    return {
        'category_id': cb.category_id,
        'name':        cb.name,
    }


def _expire_custom_budget(cb):
    """
    Deprecated/no destructiva:
    Los presupuestos personalizados ya no se eliminan al vencer.
    El estado se calcula dinámicamente según el período consultado.
    """
    return None


def _custom_budget_for_period(user_id, year, month, active_only=True):
    """Return one CustomBudget created for the selected month.
    By default returns only the active (vigente) one — finalized budgets
    are part of historical archive and shouldn't be surfaced as 'current'."""
    q = CustomBudget.query.filter(
        CustomBudget.user_id == user_id,
        extract('year', CustomBudget.start_date) == year,
        extract('month', CustomBudget.start_date) == month,
    )
    if active_only:
        q = q.filter(CustomBudget.end_date >= date.today())
    return q.order_by(CustomBudget.start_date.desc()).first()


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
    form.month.data = month

    edit_budget_id = None
    edit_budget = request.args.get('edit_budget', type=int)
    current_budget = Budget.query.filter_by(
        user_id=current_user.id, year=year, month=month
    ).first()
    if edit_budget and not current_budget:
        edit_budget = None

    if form.validate_on_submit():
        if _is_demo_year(year):
            return _reject_demo('main.budget')
        budget_id = request.form.get('budget_id', 0, type=int)
        if budget_id:
            target = Budget.query.filter_by(
                id=budget_id, user_id=current_user.id, year=year, month=month
            ).first_or_404()
            target.amount = form.amount.data
            db.session.commit()
            flash(_('Presupuesto actualizado.'), 'success')
            return redirect(url_for('main.budget'))
        if current_budget:
            current_budget.amount = form.amount.data
            db.session.commit()
            flash(_('Presupuesto actualizado.'), 'success')
            return redirect(url_for('main.budget'))
        else:
            db.session.add(Budget(
                user_id=current_user.id,
                year=year,
                month=month,
                amount=form.amount.data,
            ))
            db.session.commit()
            flash(_('Presupuesto creado.'), 'success')
            return redirect(url_for('main.budget'))

    if request.method == 'GET':
        form.amount.data = current_budget.amount if current_budget else None
    edit_budget_id = current_budget.id if current_budget else None

    # ── Category budget form ───────────────────────────────────────────────────
    cat_form = CategoryBudgetForm()
    expense_cats = (
        Category.query.filter(
            (Category.user_id == current_user.id) | (Category.user_id.is_(None)),
            Category.type == 'expense',
        ).order_by(Category.name).all()
    )

    # Exclude categories that already have a budget for this period
    cat_budgets = (
        CategoryBudget.query.filter_by(user_id=current_user.id, year=year, month=month)
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

    # ── Custom budget: datos preparados por estado dinámico para este período ─
    from app.services.finance import group_custom_budgets_for_period
    custom_budget_groups = group_custom_budgets_for_period(current_user.id, year, month)
    today = date.today()
    period_start = date(year, month, 1)
    period_end = date(year, month, calendar.monthrange(year, month)[1])
    custom_budget = None
    if custom_budget_groups['active']:
        custom_budget = custom_budget_groups['active'][0]['budget']
    # Solo los activos bloquean creación; los finalizados quedan como historial
    has_current_custom_budget = bool(custom_budget_groups['active'])

    # Si hay finalizados en el mes, el nuevo budget debe arrancar después del último end_date
    last_finalized_end = None
    if custom_budget_groups['finalized']:
        last_finalized_end = max(item['end_date'] for item in custom_budget_groups['finalized'])

    custom_date_min_date = max(today, period_start)
    if last_finalized_end:
        custom_date_min_date = max(custom_date_min_date, last_finalized_end + timedelta(days=1))
    can_create_custom_budget = custom_date_min_date <= period_end
    custom_date_min = custom_date_min_date.isoformat()
    custom_date_max = period_end.isoformat()
    custom_form = CustomBudgetForm()
    edit_custom = request.args.get('edit_custom', type=int)
    if edit_custom and not custom_budget:
        edit_custom = None

    if custom_budget and edit_custom and request.method == 'GET':
        custom_form.name.data = custom_budget.name
        custom_form.amount.data = custom_budget.amount
        custom_form.start_date.data = custom_budget.start_date
        custom_form.end_date.data = custom_budget.end_date

    return render_template(
        'main/budget.html',
        form=form,
        cat_form=cat_form,
        monthly_budget=current_budget,
        cat_budgets=cat_budgets,
        cat_budget_data=cat_budget_data,
        month_names=month_names,
        budget_year=year,
        sel_month_name=month_names.get(month, ''),
        can_add_cat_budget=len(cat_budgets) < 5,
        edit_budget_id=edit_budget_id,
        edit_budget=edit_budget,
        custom_budget=custom_budget,
        custom_budget_groups=custom_budget_groups,
        has_current_custom_budget=has_current_custom_budget,
        can_create_custom_budget=can_create_custom_budget,
        custom_date_min=custom_date_min,
        custom_date_max=custom_date_max,
        custom_form=custom_form,
        edit_custom=edit_custom,
    )


@main.route('/budget/<int:budget_id>/delete', methods=['POST'])
@login_required
def delete_budget(budget_id):
    year, month = _get_period()
    if _is_demo_year(year):
        return _reject_demo('main.budget')
    b = Budget.query.filter_by(
        id=budget_id, user_id=current_user.id, year=year, month=month
    ).first_or_404()
    db.session.delete(b)
    db.session.commit()
    flash(_('Presupuesto eliminado.'), 'success')
    return redirect(url_for('main.budget'))


@main.route('/budget/categoria/guardar', methods=['POST'])
@login_required
def save_category_budget():
    year, month = _get_period()
    if _is_demo_year(year):
        return _reject_demo('main.budget')
    month_names = _locale_month_names()
    cat_budgets_count = CategoryBudget.query.filter_by(user_id=current_user.id, year=year, month=month).count()

    cat_form = CategoryBudgetForm()
    expense_cats = Category.query.filter(
        (Category.user_id == current_user.id) | (Category.user_id.is_(None)),
        Category.type == 'expense',
    ).order_by(Category.name).all()
    taken_ids = {
        cb.category_id for cb in
        CategoryBudget.query.filter_by(user_id=current_user.id, year=year, month=month).all()
    }
    # Allow the same category if updating within this period
    existing_for_cat = CategoryBudget.query.filter_by(
        user_id=current_user.id,
        year=year,
        month=month,
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
        elif cat_budgets_count >= 5:
            flash(_('Ya tienes el máximo de 5 presupuestos de categoría.'), 'warning')
        else:
            db.session.add(CategoryBudget(
                user_id=current_user.id,
                year=year,
                month=month,
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
    if _is_demo_year(cb.year):
        return _reject_demo('main.budget')
    db.session.delete(cb)
    db.session.commit()
    flash(_('Presupuesto de categoría eliminado.'), 'success')
    return redirect(url_for('main.budget'))


@main.route('/budget/personalizado/guardar', methods=['POST'])
@login_required
def save_custom_budget():
    year, month = _get_period()
    custom_form = CustomBudgetForm()
    current_budget_id = request.form.get('custom_budget_id', type=int)
    current_budget = None
    if current_budget_id:
        current_budget = CustomBudget.query.filter_by(
            id=current_budget_id, user_id=current_user.id
        ).first_or_404()

    today = date.today()

    # Bloquear edición de presupuestos finalizados (historial inmutable)
    if current_budget and current_budget.end_date < today:
        flash(_('No se puede editar un presupuesto finalizado. Queda como historial.'), 'warning')
        return redirect(url_for('main.budget'))

    if not custom_form.validate_on_submit():
        for field_errors in custom_form.errors.values():
            for e in field_errors:
                flash(e, 'danger')
        return redirect(url_for('main.budget', edit_custom=1 if current_budget else None))

    name = custom_form.name.data.strip()
    start = custom_form.start_date.data
    end = custom_form.end_date.data

    if (start.year, start.month) != (year, month) or (end.year, end.month) != (year, month):
        flash(_('El presupuesto personalizado debe pertenecer al mes seleccionado.'), 'danger')
        return redirect(url_for('main.budget', edit_custom=1 if current_budget else None))

    if start < today and (not current_budget or start != current_budget.start_date):
        flash(_('La fecha de inicio no puede ser anterior a hoy.'), 'danger')
        return redirect(url_for('main.budget', edit_custom=1 if current_budget else None))

    if (start.year, start.month) != (end.year, end.month):
        flash(_('El presupuesto personalizado debe estar dentro del mismo mes.'), 'danger')
        return redirect(url_for('main.budget', edit_custom=1 if current_budget else None))

    # Bloqueo solo si hay otro presupuesto VIGENTE en el mes (los finalizados no bloquean)
    existing_active = CustomBudget.query.filter(
        CustomBudget.user_id == current_user.id,
        extract('year', CustomBudget.start_date) == year,
        extract('month', CustomBudget.start_date) == month,
        CustomBudget.end_date >= today,
    )
    if current_budget:
        existing_active = existing_active.filter(CustomBudget.id != current_budget.id)
    existing_active = existing_active.first()

    if existing_active:
        flash(_('Ya tienes un presupuesto personalizado vigente para este mes.'), 'danger')
        return redirect(url_for('main.budget', edit_custom=1 if current_budget else None))

    # Si hay finalizados en el mes, el nuevo start debe ser posterior al último end_date
    if not current_budget:
        last_finalized_end = db.session.query(func.max(CustomBudget.end_date)).filter(
            CustomBudget.user_id == current_user.id,
            extract('year', CustomBudget.start_date) == year,
            extract('month', CustomBudget.start_date) == month,
            CustomBudget.end_date < today,
        ).scalar()
        if last_finalized_end and start <= last_finalized_end:
            flash(_('La fecha de inicio debe ser posterior al %(d)s (último presupuesto finalizado).',
                    d=last_finalized_end.strftime('%d/%m/%Y')), 'danger')
            return redirect(url_for('main.budget'))

    conflict = Category.query.filter(
        (Category.user_id == current_user.id) | (Category.user_id.is_(None)),
        Category.name == name,
    )
    if current_budget:
        conflict = conflict.filter(Category.id != current_budget.category_id)
    conflict = conflict.first()
    if conflict:
        flash(_('Ya existe una categoría con ese nombre. Elige otro.'), 'danger')
        return redirect(url_for('main.budget', edit_custom=1 if current_budget else None))

    if current_budget:
        current_budget.name = name
        current_budget.amount = custom_form.amount.data
        current_budget.start_date = start
        current_budget.end_date = end
        if current_budget.category and current_budget.category.user_id == current_user.id:
            current_budget.category.name = name
        db.session.commit()
        flash(_('Presupuesto personalizado actualizado.'), 'success')
        return redirect(url_for('main.budget'))

    cat = Category(
        name=name, type='expense',
        user_id=current_user.id,
        color=_next_custom_color(current_user.id),
    )
    db.session.add(cat)
    db.session.flush()
    db.session.add(CustomBudget(
        user_id=current_user.id,
        name=name,
        amount=custom_form.amount.data,
        start_date=start,
        end_date=end,
        category_id=cat.id,
    ))
    db.session.commit()
    flash(_('Presupuesto personalizado creado. La categoría "%(name)s" fue creada automáticamente.', name=name), 'success')

    return redirect(url_for('main.budget'))


@main.route('/budget/personalizado/<int:cb_id>/delete', methods=['POST'])
@login_required
def delete_custom_budget(cb_id):
    cb = CustomBudget.query.filter_by(id=cb_id, user_id=current_user.id).first_or_404()
    today = date.today()

    # Finalizado → historial inmutable, no se puede eliminar
    if cb.end_date < today:
        flash(_('No se puede eliminar un presupuesto finalizado. Queda como historial.'), 'warning')
        return redirect(url_for('main.budget'))

    # Activo → eliminación en cascada: budget + movimientos + recurrentes + cat-budgets + categoría.
    # Toda esa data sólo existe por este presupuesto, así que se va junta.
    category = cb.category if cb.category and cb.category.user_id == current_user.id else None
    cat_name = category.name if category else ''

    tx_deleted = Transaction.query.filter_by(
        user_id=current_user.id, category_id=cb.category_id
    ).delete(synchronize_session=False)
    rec_deleted = RecurringTransaction.query.filter_by(
        user_id=current_user.id, category_id=cb.category_id
    ).delete(synchronize_session=False)
    CategoryBudget.query.filter_by(
        user_id=current_user.id, category_id=cb.category_id
    ).delete(synchronize_session=False)

    db.session.delete(cb)
    if category:
        db.session.delete(category)
    db.session.commit()

    if tx_deleted or rec_deleted:
        flash(_('Presupuesto "%(n)s" eliminado junto con %(tx)s movimientos y %(rec)s recurrentes asociados.',
                n=cat_name, tx=tx_deleted, rec=rec_deleted), 'success')
    else:
        flash(_('Presupuesto y categoría "%(n)s" eliminados.', n=cat_name), 'success')
    return redirect(url_for('main.budget'))


# ── Global dashboard ───────────────────────────────────────────────────────────

@main.route('/dashboard/global')
@login_required
def global_dashboard():
    today = date.today()
    sel_year_g = request.args.get('year', session.get('selected_year', today.year), type=int)
    from_month = max(1, min(12, request.args.get('from_month', 1, type=int)))
    to_month = max(from_month, min(12, request.args.get('to_month', 12, type=int)))
    _generate_pending_recurring_range(current_user.id, sel_year_g, from_month, to_month)

    from app.services.finance import get_global_summary
    summary = get_global_summary(current_user.id, sel_year_g, from_month, to_month)

    # ── Range charts: expense categories + selected-year monthly trend ───────
    bar_rows = summary['expense_by_category']
    _fb = list(islice(cycle(CHART_COLORS), max(len(bar_rows), 1)))
    bar_colors = [r.get('color') or _fb[i] for i, r in enumerate(bar_rows)]
    trend_income = summary['trend_income']
    trend_expense = summary['trend_expense']

    # ── Annual charts: yearly totals + expense trend by year ─────────────────
    all_yrs = [r['year'] for r in summary['yearly_summary']]
    yearly_income = [r['income'] for r in summary['yearly_summary']]
    yearly_expense = [r['expense'] for r in summary['yearly_summary']]
    multi_year_datasets = []
    my_color_cycle = cycle(CHART_COLORS)

    for row in summary['multi_year_expense_trend']:
        color = next(my_color_cycle)
        multi_year_datasets.append({
            "label": str(row['year']),
            "data": row['monthly'],
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
        bar_labels=json.dumps([r['name'] for r in bar_rows]),
        bar_data=json.dumps([r['total'] for r in bar_rows]),
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
        if goal.is_demo:
            return _reject_demo('main.metas')

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
    if goal.is_demo:
        return _reject_demo('main.metas')
    db.session.delete(goal)
    db.session.commit()
    flash(_('Meta eliminada.'), 'success')
    return redirect(url_for('main.metas'))


@main.route('/metas/<int:goal_id>/abonar', methods=['POST'])
@login_required
def meta_abonar(goal_id):
    goal = SavingsGoal.query.filter_by(id=goal_id, user_id=current_user.id).first_or_404()
    if goal.is_demo:
        return jsonify({'error': _('Esta meta es de demostración y no puede modificarse.')}), 403
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
    if goal.is_demo:
        return _reject_demo('main.metas')
    goal.is_completed = not goal.is_completed
    db.session.commit()
    return redirect(url_for('main.metas'))


# ── Transacciones recurrentes ──────────────────────────────────────────────────

@main.route('/recurrentes')
@login_required
def recurrentes():
    year, month = _get_period()
    period_start = date(year, month, 1)
    period_end = date(year, month, calendar.monthrange(year, month)[1])
    all_items = RecurringTransaction.query.filter(
        RecurringTransaction.user_id == current_user.id,
        extract('year', RecurringTransaction.created_at) == year,
    ).order_by(RecurringTransaction.is_active.desc(), RecurringTransaction.type, RecurringTransaction.description).all()

    def _vigente(r):
        start = r.created_at.date() if r.created_at else date(year, 1, 1)
        return start <= period_end and not (r.end_date and r.end_date < period_start)

    items       = [r for r in all_items if _vigente(r)]
    finalizadas = [r for r in all_items if not _vigente(r)]

    active_vigentes = [r for r in items if r.is_active]
    total_expense = float(sum(r.amount for r in active_vigentes if r.type == 'expense'))
    total_income  = float(sum(r.amount for r in active_vigentes if r.type == 'income'))

    # Chart data: group active vigentes by category
    cat_map = {}
    for r in active_vigentes:
        key = (r.category.name, r.type)
        cat_map[key] = cat_map.get(key, 0) + float(r.amount)

    chart_labels  = json.dumps([k[0] for k in cat_map])
    chart_data    = json.dumps(list(cat_map.values()))
    chart_colors  = json.dumps(['#EF4444' if k[1] == 'expense' else '#00C896' for k in cat_map])

    return render_template('main/recurrentes.html',
                           items=items,
                           finalizadas=finalizadas,
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
        if rec.is_demo:
            return _reject_demo('main.recurrentes')
    rec_year = rec.created_at.year if rec and rec.created_at else date.today().year

    form = RecurringTransactionForm(obj=rec)
    cats = _user_categories()
    form.category_id.choices = [(c.id, c.name) for c in cats]
    all_cats_json = [
        {
            'id': c.id,
            'name': c.name,
            'type': c.type,
            'is_custom': c.user_id == current_user.id,
        }
        for c in cats
    ]

    if form.validate_on_submit():
        cat = Category.query.filter(
            Category.id == form.category_id.data,
            (Category.user_id == current_user.id) | (Category.user_id.is_(None)),
        ).first()
        if not cat or cat.type != form.type.data:
            flash(_('La categoría no corresponde al tipo seleccionado.'), 'danger')
        elif form.end_date.data and form.end_date.data.year != rec_year:
            flash(_('La fecha de término debe estar dentro del año de la recurrente.'), 'danger')
        elif form.end_date.data and form.end_date.data < date.today() and rec is None:
            flash(_('La fecha de término no puede ser anterior a hoy.'), 'danger')
        else:
            is_new = rec is None
            if is_new:
                rec = RecurringTransaction(user_id=current_user.id)
                db.session.add(rec)
                was_active = False
            else:
                was_active = rec.is_active
            rec.type         = form.type.data
            rec.amount       = form.amount.data
            rec.category_id  = form.category_id.data
            rec.description  = form.description.data
            rec.day_of_month = form.day_of_month.data
            rec.end_date     = form.end_date.data or None
            rec.is_active    = form.is_active.data
            db.session.commit()

            current_month_date = None
            added = 0

            # 1) Backfill solo cuando la recurrente acaba de activarse
            if not was_active and rec.is_active:
                added = _backfill_recurring(current_user.id, rec)

            # 2) Mes actual: opt-in explícito del usuario (independiente de is_active)
            if is_new and request.form.get('include_current_month') == 'y':
                today = date.today()
                if rec.day_of_month < today.day:
                    last_day = calendar.monthrange(today.year, today.month)[1]
                    tx_date = date(today.year, today.month, min(rec.day_of_month, last_day))
                    already = Transaction.query.filter_by(
                        user_id=current_user.id, recurring_id=rec.id
                    ).filter(
                        extract('year', Transaction.date) == today.year,
                        extract('month', Transaction.date) == today.month,
                    ).first()
                    if not already:
                        db.session.add(Transaction(
                            user_id=current_user.id,
                            category_id=rec.category_id,
                            type=rec.type,
                            amount=rec.amount,
                            description=rec.description or '',
                            date=tx_date,
                            recurring_id=rec.id,
                        ))
                        db.session.commit()
                        current_month_date = tx_date

            # 3) Mensaje de éxito según los caminos ejecutados
            if current_month_date and added:
                flash(_('Recurrente creada. Se registró el mes actual (%(date)s) y %(n)s entradas futuras generadas.',
                        date=current_month_date.strftime('%d/%m/%Y'), n=added), 'success')
            elif current_month_date:
                flash(_('Recurrente creada. Se registró el mes actual (%(date)s).',
                        date=current_month_date.strftime('%d/%m/%Y')), 'success')
            elif is_new and added:
                flash(_('Recurrente creada. %(n)s entradas generadas hasta fin de año.', n=added), 'success')
            elif added:
                flash(_('Recurrente activada. %(n)s transacciones generadas retroactivamente.', n=added), 'success')
            else:
                flash(_('Transacción recurrente guardada.'), 'success')
            return redirect(url_for('main.recurrentes'))

    if request.method == 'GET' and rec is None:
        form.is_active.data = True

    month_names = _locale_month_names()
    generation_start = rec.created_at.date() if rec and rec.created_at else date.today()
    generation_start_label = f"{month_names[generation_start.month]} {generation_start.year}"
    recurrence_year_end = date(generation_start.year, 12, 31)

    return render_template('main/recurrente_form.html',
                           form=form,
                           rec=rec,
                           all_cats_json=all_cats_json,
                           today_iso=date.today().isoformat(),
                           today_day=date.today().day,
                           generation_start_label=generation_start_label,
                           recurrence_year_end=recurrence_year_end.isoformat(),
                           title=_('Editar Recurrente') if rec else _('Nueva Recurrente'))


@main.route('/recurrentes/<int:rec_id>/finalizar', methods=['POST'])
@login_required
def recurrente_finalizar(rec_id):
    rec = RecurringTransaction.query.filter_by(id=rec_id, user_id=current_user.id).first_or_404()
    if rec.is_demo:
        return _reject_demo('main.recurrentes')
    rec.end_date = date.today()
    rec.is_active = False
    db.session.commit()
    flash(_('Recurrente finalizada. Ya no generará nuevos movimientos.'), 'success')
    return redirect(url_for('main.recurrentes'))


# ── Guía de usuario ───────────────────────────────────────────────────────────

@main.route('/ayuda')
@login_required
def ayuda():
    return render_template('main/guia.html')


# ── Configuración de cuenta ────────────────────────────────────────────────────

@main.route('/configurar', methods=['GET', 'POST'])
@login_required
def configurar():
    form = ConfigForm()
    smtp_form = SMTPConfigForm()
    ai_form = AIConfigForm()

    # Get or lazy-create the AI config row
    ai_config = current_user.ai_config
    if not ai_config:
        ai_config = UserAIConfig(user_id=current_user.id)
        db.session.add(ai_config)

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

    elif 'submit_ai' in request.form:
        if ai_form.validate_on_submit():
            ai_config.enabled = ai_form.enabled.data
            ai_config.provider = ai_form.provider.data
            ai_config.model = ai_form.model.data or None
            ai_config.base_url = ai_form.base_url.data or None
            if ai_form.api_token.data:
                ai_config.api_token_encrypted = encrypt_ai_token(ai_form.api_token.data)
            db.session.commit()
            flash(_('Configuración del escáner IA guardada.'), 'success')
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
        # Tasa del dólar: solo aplica si la moneda principal NO es USD; si lo es, se limpia.
        if country_data['code'] == 'USD':
            current_user.usd_rate = None
        else:
            current_user.usd_rate = form.usd_rate.data
        db.session.commit()
        flash(_('Configuración regional guardada exitosamente.'), 'success')
        return redirect(url_for('main.configurar'))

    if request.method == 'GET':
        form.country.data = current_user.country or 'Otro'
        form.currency_symbol.data = current_user.currency_symbol or '$'
        form.usd_rate.data = current_user.usd_rate

        smtp_form.smtp_enabled.data = email_config.smtp_enabled
        smtp_form.smtp_host.data = email_config.smtp_host
        smtp_form.smtp_port.data = email_config.smtp_port
        smtp_form.smtp_username.data = email_config.smtp_username
        smtp_form.smtp_use_tls.data = email_config.smtp_use_tls
        smtp_form.smtp_use_ssl.data = email_config.smtp_use_ssl
        smtp_form.sender_email.data = email_config.sender_email
        smtp_form.sender_name.data = email_config.sender_name

        ai_form.enabled.data = ai_config.enabled
        ai_form.provider.data = ai_config.provider or 'openai'
        ai_form.model.data = ai_config.model
        ai_form.base_url.data = ai_config.base_url
        # Never repopulate api_token (PasswordField — never shown)

    admin_smtp_available = False
    if not current_user.is_first_admin:
        admin = User.query.filter_by(is_first_admin=True).first()
        if (admin and admin.email_config and admin.email_config.smtp_enabled
                and admin.email_config.smtp_password_encrypted):
            admin_smtp_available = True

    countries_json = json.dumps(_country_map)
    api_tok = ApiToken.query.filter_by(user_id=current_user.id).first()
    return render_template('main/configurar.html',
                           form=form,
                           smtp_form=smtp_form,
                           ai_form=ai_form,
                           ai_config=ai_config,
                           pwd_form=ChangePasswordForm(),
                           email_config=email_config,
                           admin_smtp_available=admin_smtp_available,
                           countries_json=countries_json,
                           app_config=app_config,
                           api_token_active=api_tok is not None,
                           api_token_prefix=api_tok.prefix if api_tok else None,
                           api_token_created_at=api_tok.created_at if api_tok else None,
                           api_token_last_used_at=api_tok.last_used_at if api_tok else None,
                           has_pin=current_user.has_pin,
                           title=_('Configurar Cuenta'))


@main.route('/configurar/theme', methods=['POST'])
@login_required
def set_theme():
    valid_themes = {'dark', 'ocean', 'carbon', 'dusk', 'forest', 'pearl', 'abyss', 'graphite', 'enterprise'}
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
    from datetime import date as _date_cls

    app = current_app._get_current_object()
    user_id = current_user.id
    today = _date_cls.today()
    filename = f"monetra_{current_user.username}_{today.year}_{today.month:02d}.xlsx"

    def _send_in_background():
        from app.models import User
        from app.export.excel_builder import build_excel
        from app.email_service import send_weekly_report

        with app.app_context():
            user = User.query.get(user_id)
            if user is None:
                app.logger.warning("send_report_now: usuario %s no encontrado en DB.", user_id)
                return
            try:
                buf = build_excel(user, today.year, today.month, today.month)
                ok, msg = send_weekly_report(user, buf.read(), filename)
                if ok:
                    app.logger.info("send_report_now: reporte enviado a %s.", user.email)
                else:
                    app.logger.warning("send_report_now: fallo al enviar a %s — %s", user.email, msg)
            except Exception as exc:
                app.logger.error("send_report_now: error generando reporte para %s — %s", user.email, exc, exc_info=True)

    threading.Thread(target=_send_in_background, daemon=True).start()
    flash(_('Tu reporte se está generando y se enviará a %(email)s en unos momentos.', email=current_user.email), 'info')
    return redirect(url_for('main.configurar'))


@main.route('/configurar/help-toggle', methods=['POST'])
@login_required
def help_toggle():
    current_user.help_mode_enabled = not current_user.help_mode_enabled
    db.session.commit()
    return redirect(url_for('main.configurar'))


@main.route('/configurar/insights-panel-toggle', methods=['POST'])
@login_required
def insights_panel_toggle():
    current_user.insights_panel_enabled = not current_user.insights_panel_enabled
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
    raw = 'mntr_' + secrets.token_urlsafe(32)
    h = hashlib.sha256(raw.encode()).hexdigest()
    prefix = raw[:12]

    existing = ApiToken.query.filter_by(user_id=current_user.id).first()
    if existing:
        existing.token_hash = h
        existing.prefix = prefix
        from datetime import datetime, timezone
        existing.created_at = datetime.now(timezone.utc)
        existing.last_used_at = None
    else:
        db.session.add(ApiToken(
            user_id=current_user.id,
            token_hash=h,
            prefix=prefix,
        ))
    db.session.commit()
    return jsonify({"token": raw}), 200


@main.route('/configurar/revoke-api-token', methods=['POST'])
@login_required
def revoke_api_token():
    ApiToken.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    return jsonify({"ok": True}), 200


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
        send_security_alert_email(current_user, "cambió la contraseña")
        try:
            from app.audit import events as ev
            from app.audit.logger import log_event
            log_event(ev.AUTH_PASSWORD_CHANGE,
                      description=f'{current_user.email} cambió su contraseña',
                      user_id=current_user.id, request=request)
            db.session.commit()
        except Exception:
            db.session.rollback()
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
