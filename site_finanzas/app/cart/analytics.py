"""Analítica del historial de compras de supermercado (página web «Análisis»).

Trabaja sobre las compras finalizadas del usuario, agrupadas por mes local. Las
comparaciones de precios usan el nombre genérico del producto y, cuando todos los
envases tienen tamaño conocido, el precio por kilo o por litro.
"""
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import selectinload

from app import db
from app.cart import categories as cat
from app.cart.enrichment import unit_measure_price
from app.localtime import to_local
from app.models import Cart, Transaction

PERIODS = ('month', '3m', '6m', 'year', '12m', 'all')
_MONTHS_BACK = {'month': 1, '3m': 3, '6m': 6, '12m': 12}
TREND_CATEGORIES = 5
_ZERO = Decimal(0)


@dataclass
class Period:
    key: str
    start: date | None   # inclusive; None = desde siempre
    end: date | None     # exclusive
    prev_start: date | None
    prev_end: date | None


def _add_months(day: date, months: int) -> date:
    index = day.year * 12 + day.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


def period_for(key: str, today: date) -> Period:
    key = key if key in PERIODS else '3m'
    first = today.replace(day=1)
    if key == 'all':
        return Period(key, None, None, None, None)
    if key == 'year':
        start, end = date(today.year, 1, 1), date(today.year + 1, 1, 1)
        return Period(key, start, end, date(today.year - 1, 1, 1), start)
    months = _MONTHS_BACK[key]
    start, end = _add_months(first, -(months - 1)), _add_months(first, 1)
    return Period(key, start, end, _add_months(start, -months), start)


def _pct(value: Decimal, base: Decimal) -> float | None:
    return float(value / base * 100) if base else None


def _change(current: Decimal, previous: Decimal | None) -> float | None:
    if previous is None or not previous:
        return None
    return float((current - previous) / previous * 100)


def _in(day: date, start: date | None, end: date | None) -> bool:
    return (start is None or day >= start) and (end is None or day < end)


def purchase_day(cart: Cart) -> date:
    return to_local(cart.finalized_at or cart.started_at).date()


def load_purchases(user_id: int) -> list[Cart]:
    return (Cart.query.options(selectinload(Cart.items))
            .filter_by(user_id=user_id, status='finalized').all())


def _months_between(first: date, last: date) -> int:
    return (last.year - first.year) * 12 + last.month - first.month + 1


def _summary(carts, prev_carts, period: Period, user_id: int, today: date) -> dict:
    total = sum((Decimal(c.total) for c in carts), _ZERO)
    count = len(carts)
    items = sum(c.item_count for c in carts)
    prev_total = sum((Decimal(c.total) for c in prev_carts), _ZERO) if period.prev_start else None
    prev_count = len(prev_carts) if period.prev_start else None
    avg = total / count if count else _ZERO
    prev_avg = (prev_total / prev_count) if prev_count else None

    days = [purchase_day(c) for c in carts]
    if period.start:
        months = _months_between(period.start, min(_add_months(period.end, -1), today.replace(day=1)))
    else:
        months = _months_between(min(days), max(days)) if days else 1

    expenses = None
    if period.start:
        expenses = (db.session.query(func.coalesce(func.sum(Transaction.amount), 0))
                    .filter(Transaction.user_id == user_id, Transaction.type == 'expense',
                            Transaction.date >= period.start, Transaction.date < period.end).scalar())
        expenses = Decimal(expenses or 0)
    return {
        'total': total, 'count': count, 'avg_ticket': avg,
        'items_avg': (Decimal(items) / count) if count else _ZERO,
        'monthly_avg': total / max(months, 1),
        'prev_total': prev_total, 'prev_count': prev_count, 'prev_avg': prev_avg,
        'total_change': _change(total, prev_total), 'avg_change': _change(avg, prev_avg),
        'count_change': _change(Decimal(count), Decimal(prev_count)) if prev_count else None,
        # Solo es comparable cuando el gasto del súper quedó registrado como movimiento.
        'expense_share': _pct(total, expenses) if expenses and total <= expenses else None,
    }


def _category_totals(carts) -> dict[str, Decimal]:
    totals = defaultdict(lambda: _ZERO)
    for cart in carts:
        for item in cart.items:
            totals[item.category or cat.OTHER] += Decimal(item.line_total)
    return totals


def _by_category(carts, prev_carts, has_prev: bool, lang) -> list[dict]:
    totals, prev = _category_totals(carts), _category_totals(prev_carts)
    grand = sum(totals.values(), _ZERO)
    rows = [{
        'key': key, 'label': cat.label(key, lang), 'color': cat.color(key), 'amount': amount,
        'pct': _pct(amount, grand), 'prev_amount': prev.get(key, _ZERO) if has_prev else None,
        'change': _change(amount, prev.get(key)) if has_prev else None,
    } for key, amount in totals.items() if amount]
    return sorted(rows, key=lambda r: r['amount'], reverse=True)


def _category_trend(carts, categories: list[dict], lang) -> dict | None:
    months = sorted({purchase_day(c).replace(day=1) for c in carts})
    if len(months) < 2:
        return None
    top = [r['key'] for r in categories[:TREND_CATEGORIES]]
    amounts = {key: defaultdict(lambda: _ZERO) for key in top}
    for cart in carts:
        month = purchase_day(cart).replace(day=1)
        for item in cart.items:
            key = item.category or cat.OTHER
            if key in amounts:
                amounts[key][month] += Decimal(item.line_total)
    return {
        'labels': [m.strftime('%m/%Y') for m in months],
        'datasets': [{'label': cat.label(key, lang), 'color': cat.color(key),
                      'data': [float(amounts[key][m]) for m in months]} for key in top],
    }


def _chain(cart) -> str:
    return cart.store_chain or cart.store_name or '—'


def _by_chain(carts) -> list[dict]:
    totals, counts = defaultdict(lambda: _ZERO), defaultdict(int)
    for cart in carts:
        totals[_chain(cart)] += Decimal(cart.total)
        counts[_chain(cart)] += 1
    grand = sum(totals.values(), _ZERO)
    rows = [{'chain': chain, 'amount': amount, 'count': counts[chain], 'avg_ticket': amount / counts[chain],
             'pct': _pct(amount, grand)} for chain, amount in totals.items()]
    return sorted(rows, key=lambda r: r['amount'], reverse=True)


def _matrix(carts, categories: list[dict], chains: list[dict]) -> dict:
    """Gasto de cada tipo en cada supermercado, con el % que representa dentro del tipo."""
    cells = defaultdict(lambda: _ZERO)
    for cart in carts:
        for item in cart.items:
            cells[(item.category or cat.OTHER, _chain(cart))] += Decimal(item.line_total)
    rows = []
    for category in categories:
        row_cells = []
        for chain in chains:
            amount = cells.get((category['key'], chain['chain']), _ZERO)
            row_cells.append({'amount': amount, 'pct': _pct(amount, category['amount'])})
        main = max(range(len(chains)), key=lambda i: row_cells[i]['amount']) if chains else None
        rows.append({**category, 'cells': row_cells, 'main_chain': chains[main]['chain'] if main is not None else None,
                     'main_pct': row_cells[main]['pct'] if main is not None else None})
    return {'chains': [c['chain'] for c in chains], 'rows': rows}


def _comparable(item) -> tuple[Decimal, str]:
    per, unit = unit_measure_price(item)
    return (per, unit) if per is not None else (Decimal(item.unit_price), 'u')


def _prices(carts, lang) -> dict:
    """Índice de precios por supermercado, precios por producto y ahorro posible.

    Solo cuentan productos (por nombre genérico) comprados en dos o más
    supermercados del período. Un producto se compara por kilo o litro si todos
    sus envases tienen tamaño conocido; si no, por unidad.
    """
    groups = defaultdict(list)   # nombre genérico → [(cadena, item, fecha)]
    for cart in carts:
        for item in cart.items:
            if item.generic_name:
                groups[item.generic_name].append((_chain(cart), item, purchase_day(cart)))

    products, savings_by_cat = [], defaultdict(lambda: _ZERO)
    index_num, index_den = defaultdict(lambda: _ZERO), defaultdict(lambda: _ZERO)
    cat_num, cat_den = defaultdict(lambda: _ZERO), defaultdict(lambda: _ZERO)
    for key, entries in groups.items():
        if len({chain for chain, _i, _d in entries}) < 2:
            continue
        by_measure = all(unit_measure_price(i)[0] is not None for _c, i, _d in entries)
        unit = _comparable(entries[0][1])[1] if by_measure else 'u'
        prices = defaultdict(list)
        for chain, item, day in entries:
            price = _comparable(item)[0] if by_measure else Decimal(item.unit_price)
            prices[chain].append((day, price, Decimal(item.qty), Decimal(item.line_total)))
        avg = {chain: sum(p * q for _d, p, q, _t in rows) / sum(q for _d, _p, q, _t in rows)
               for chain, rows in prices.items()}
        cheapest = min(avg, key=avg.get)
        low = avg[cheapest]
        spend = sum(t for rows in prices.values() for _d, _p, _q, t in rows)
        category = next((i.category for _c, i, _d in reversed(entries) if i.category), cat.OTHER)
        # Lo pagado en cada supermercado, llevado al precio promedio del más barato.
        saving = sum(sum(t for _d, _p, _q, t in rows) * (avg[chain] - low) / avg[chain]
                     for chain, rows in prices.items() if chain != cheapest and avg[chain] > low)
        savings_by_cat[category] += saving
        for chain, price in avg.items():
            index_num[chain] += spend * price / low
            index_den[chain] += spend
            cat_num[(category, chain)] += spend * price / low
            cat_den[(category, chain)] += spend
        latest = entries[-1][1]
        products.append({
            'key': key, 'name': latest.name, 'category': category, 'category_label': cat.label(category, lang),
            'unit': unit, 'spend': spend, 'cheapest': cheapest, 'saving': saving,
            'spread': float((max(avg.values()) - low) / low * 100) if low else None,
            'chains': {chain: {'avg': price, 'last': max(prices[chain])[1]} for chain, price in avg.items()},
        })

    index = sorted(({'chain': chain, 'index': float(index_num[chain] / index_den[chain] * 100)}
                    for chain in index_den), key=lambda r: r['index'])
    by_category = defaultdict(list)
    for (category, chain), den in cat_den.items():
        by_category[category].append({'chain': chain, 'index': float(cat_num[(category, chain)] / den * 100)})
    category_index = sorted(({'key': key, 'label': cat.label(key, lang), 'color': cat.color(key),
                              'chains': sorted(rows, key=lambda r: r['index'])}
                             for key, rows in by_category.items() if len(rows) > 1),
                            key=lambda r: r['label'])
    products.sort(key=lambda p: p['spend'], reverse=True)
    savings = sum(savings_by_cat.values(), _ZERO)
    return {
        'index': index, 'category_index': category_index, 'products': products,
        'savings': savings, 'savings_by_category': sorted(
            ({'key': k, 'label': cat.label(k, lang), 'amount': v} for k, v in savings_by_cat.items() if v),
            key=lambda r: r['amount'], reverse=True),
    }


def build_report(user_id: int, period_key: str = '3m', chain: str | None = None,
                 today: date | None = None, lang: str | None = 'es') -> dict:
    today = today or to_local_today()
    period = period_for(period_key, today)
    purchases = load_purchases(user_id)
    available_chains = sorted({_chain(c) for c in purchases})
    # Comparar precios exige varios supermercados: esa sección ignora el filtro de supermercado.
    all_carts = sorted((c for c in purchases if _in(purchase_day(c), period.start, period.end)), key=purchase_day)
    if chain:
        purchases = [c for c in purchases if _chain(c) == chain]
    carts = [c for c in all_carts if not chain or _chain(c) == chain]
    has_prev = period.prev_start is not None
    prev_carts = [c for c in purchases if has_prev and _in(purchase_day(c), period.prev_start, period.prev_end)]

    categories = _by_category(carts, prev_carts, has_prev, lang)
    chains = _by_chain(carts)
    return {
        'period': period, 'chain': chain, 'available_chains': available_chains,
        'summary': _summary(carts, prev_carts, period, user_id, today),
        'categories': categories,
        'trend': _category_trend(carts, categories, lang),
        'chains': chains,
        'matrix': _matrix(carts, categories, chains),
        'prices': _prices(all_carts, lang),
        'classified_share': _classified_share(carts),
    }


def _classified_share(carts) -> float | None:
    items = [i for c in carts for i in c.items]
    if not items:
        return None
    return sum(1 for i in items if i.category and i.category != cat.OTHER) / len(items) * 100


def to_local_today() -> date:
    return to_local(datetime.now(timezone.utc)).date()
