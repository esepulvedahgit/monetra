from datetime import date
from flask import render_template, redirect, url_for, request, flash, abort, session
from flask_login import login_required, current_user
from flask_babel import gettext as _
from sqlalchemy import func, extract

from app import db
from app.models import UsdCategory, UsdTransaction, UsdBudget
from app.usd import usd_bp
from app.usd.forms import UsdCategoryForm, UsdTransactionForm, UsdBudgetForm
from app.main.routes import CUSTOM_PALETTE


# ── Helpers ─────────────────────────────────────────────────────────────────

def _period_from_request():
    """Resolve period from query string, falling back to global session period."""
    today = date.today()
    year = request.args.get('year', type=int) or session.get('selected_year') or today.year
    month = request.args.get('month', type=int) or session.get('selected_month') or today.month
    return int(year), int(month)


def _next_color(user_id):
    used = {c.color for c in UsdCategory.query.filter_by(user_id=user_id).all() if c.color}
    for color in CUSTOM_PALETTE:
        if color not in used:
            return color
    return CUSTOM_PALETTE[0]


def _own_or_404(model, obj_id):
    obj = db.session.get(model, obj_id)
    if obj is None or obj.user_id != current_user.id:
        abort(404)
    return obj


def _user_categories():
    return (UsdCategory.query
            .filter_by(user_id=current_user.id)
            .order_by(UsdCategory.name)
            .all())


def _back_to_dashboard(year=None, month=None):
    if year and month:
        return redirect(url_for('usd.dashboard', year=year, month=month))
    return redirect(url_for('usd.dashboard'))


# ── Dashboard (single page) ─────────────────────────────────────────────────

@usd_bp.route('/')
@login_required
def dashboard():
    year, month = _period_from_request()
    categories = _user_categories()

    transactions = (UsdTransaction.query
                    .filter(
                        UsdTransaction.user_id == current_user.id,
                        extract('year', UsdTransaction.date) == year,
                        extract('month', UsdTransaction.date) == month,
                    )
                    .order_by(UsdTransaction.date.desc(), UsdTransaction.id.desc())
                    .all())

    total_spent = float(sum((t.amount for t in transactions), start=0))

    budget = UsdBudget.query.filter_by(
        user_id=current_user.id, year=year, month=month
    ).first()
    budget_amount = float(budget.amount) if budget else 0.0
    remaining = budget_amount - total_spent
    progress = (total_spent / budget_amount * 100) if budget_amount > 0 else 0.0

    by_category = (db.session.query(
                       UsdCategory.id,
                       UsdCategory.name,
                       UsdCategory.color,
                       func.sum(UsdTransaction.amount).label('total'),
                   )
                   .join(UsdTransaction, UsdTransaction.category_id == UsdCategory.id)
                   .filter(
                       UsdTransaction.user_id == current_user.id,
                       extract('year', UsdTransaction.date) == year,
                       extract('month', UsdTransaction.date) == month,
                   )
                   .group_by(UsdCategory.id, UsdCategory.name, UsdCategory.color)
                   .order_by(func.sum(UsdTransaction.amount).desc())
                   .all())

    chart_labels = [r.name for r in by_category]
    chart_data = [float(r.total) for r in by_category]
    chart_colors = [r.color or '#6c757d' for r in by_category]

    tx_form = UsdTransactionForm()
    tx_form.category_id.choices = [(c.id, c.name) for c in categories]

    cat_form = UsdCategoryForm()
    budget_form = UsdBudgetForm(amount=budget_amount or None)

    # Conteo total (todas las fechas) por categoría — para saber si se puede borrar inline
    cat_tx_counts_rows = (db.session.query(
                              UsdTransaction.category_id,
                              func.count(UsdTransaction.id),
                          )
                          .filter(UsdTransaction.user_id == current_user.id)
                          .group_by(UsdTransaction.category_id)
                          .all())
    cat_tx_counts = {cat_id: count for cat_id, count in cat_tx_counts_rows}

    return render_template(
        'usd/dashboard.html',
        year=year, month=month,
        categories=categories,
        cat_tx_counts=cat_tx_counts,
        transactions=transactions,
        total_spent=total_spent,
        budget_amount=budget_amount,
        remaining=remaining,
        progress=progress,
        chart_labels=chart_labels,
        chart_data=chart_data,
        chart_colors=chart_colors,
        category_breakdown=by_category,
        tx_form=tx_form,
        cat_form=cat_form,
        budget_form=budget_form,
    )


# ── Transactions ────────────────────────────────────────────────────────────

@usd_bp.route('/transaction/new', methods=['POST'])
@login_required
def transaction_new():
    form = UsdTransactionForm()
    form.category_id.choices = [(c.id, c.name) for c in _user_categories()]
    if form.validate_on_submit():
        tx = UsdTransaction(
            user_id=current_user.id,
            category_id=form.category_id.data,
            amount=form.amount.data,
            date=form.date.data,
            description=(form.description.data or None),
        )
        db.session.add(tx)
        db.session.commit()
        flash(_('Movimiento agregado.'), 'success')
        return _back_to_dashboard(form.date.data.year, form.date.data.month)
    flash(_('Datos inválidos. Revisa los campos.'), 'danger')
    return _back_to_dashboard()


@usd_bp.route('/transaction/<int:tx_id>/edit', methods=['POST'])
@login_required
def transaction_edit(tx_id):
    tx = _own_or_404(UsdTransaction, tx_id)
    form = UsdTransactionForm()
    form.category_id.choices = [(c.id, c.name) for c in _user_categories()]
    if form.validate_on_submit():
        tx.category_id = form.category_id.data
        tx.amount = form.amount.data
        tx.date = form.date.data
        tx.description = (form.description.data or None)
        db.session.commit()
        flash(_('Movimiento actualizado.'), 'success')
    else:
        flash(_('Datos inválidos. Revisa los campos.'), 'danger')
    return _back_to_dashboard(tx.date.year, tx.date.month)


@usd_bp.route('/transaction/<int:tx_id>/delete', methods=['POST'])
@login_required
def transaction_delete(tx_id):
    tx = _own_or_404(UsdTransaction, tx_id)
    year, month = tx.date.year, tx.date.month
    db.session.delete(tx)
    db.session.commit()
    flash(_('Movimiento eliminado.'), 'success')
    return _back_to_dashboard(year, month)


# ── Categories ──────────────────────────────────────────────────────────────

@usd_bp.route('/category/new', methods=['POST'])
@login_required
def category_new():
    form = UsdCategoryForm()
    if not form.validate_on_submit():
        flash(_('Nombre inválido.'), 'danger')
        return _back_to_dashboard()
    name = form.name.data.strip()
    existing = UsdCategory.query.filter_by(user_id=current_user.id, name=name).first()
    if existing:
        flash(_('Ya existe una categoría con ese nombre.'), 'warning')
    else:
        cat = UsdCategory(
            user_id=current_user.id,
            name=name,
            color=_next_color(current_user.id),
        )
        db.session.add(cat)
        db.session.commit()
        flash(_('Categoría creada.'), 'success')
    return _back_to_dashboard()


@usd_bp.route('/category/<int:cat_id>/delete', methods=['POST'])
@login_required
def category_delete(cat_id):
    cat = _own_or_404(UsdCategory, cat_id)
    if cat.transactions:
        flash(_('No se puede eliminar: la categoría tiene movimientos asociados.'), 'warning')
    else:
        db.session.delete(cat)
        db.session.commit()
        flash(_('Categoría eliminada.'), 'success')
    return _back_to_dashboard()


# ── Budget ──────────────────────────────────────────────────────────────────

@usd_bp.route('/budget/set', methods=['POST'])
@login_required
def budget_set():
    year, month = _period_from_request()
    form = UsdBudgetForm()
    if not form.validate_on_submit():
        flash(_('Monto inválido.'), 'danger')
        return _back_to_dashboard(year, month)
    budget = UsdBudget.query.filter_by(
        user_id=current_user.id, year=year, month=month
    ).first()
    if budget:
        budget.amount = form.amount.data
    else:
        budget = UsdBudget(
            user_id=current_user.id, year=year, month=month,
            amount=form.amount.data,
        )
        db.session.add(budget)
    db.session.commit()
    flash(_('Presupuesto actualizado.'), 'success')
    return _back_to_dashboard(year, month)
