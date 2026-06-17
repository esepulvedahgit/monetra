"""Helpers de formato y parseo monetario reutilizables dentro y fuera de un request.

El filtro Jinja ``money`` (en ``app/__init__.py``) y el bot de Telegram comparten
esta lógica. A diferencia del filtro, estas funciones reciben los parámetros de
moneda explícitamente, por lo que sirven en contextos sin ``current_user``
(p. ej. el webhook de Telegram)."""

from decimal import Decimal


def format_money(value, code='USD', locale='es', symbol='$'):
    """Formatea un monto usando los ajustes de moneda dados.

    Replica el filtro Jinja ``money`` pero con parámetros explícitos.
    """
    try:
        value = float(value)
    except (TypeError, ValueError):
        return str(value)
    try:
        from babel.numbers import format_decimal, get_currency_precision
        decimals = get_currency_precision(code)
        fmt = '#,##0' + ('.' + '0' * decimals if decimals > 0 else '')
        return symbol + format_decimal(value, fmt, locale=locale)
    except Exception:
        return f"{symbol}{value:.2f}"


def format_money_for_user(value, user):
    """Formatea un monto según las preferencias de moneda de un ``User``."""
    if user is None:
        return format_money(value)
    return format_money(
        value,
        code=user.currency_code or 'USD',
        locale=user.currency_locale or 'es',
        symbol=user.currency_symbol or '$',
    )


def parse_amount(value, locale='es', code='USD'):
    """Interpreta un monto escrito por el usuario respetando la convención de su moneda.

    Usa ``babel.numbers.parse_decimal`` para que el separador de miles/decimales sea
    correcto según el locale (en ``es``: ``.`` = miles, ``,`` = decimales).

    Devuelve un ``Decimal`` cuantificado a la precisión de la moneda (p. ej. CLP → 0
    decimales, USD → 2). Lanza ``ValueError`` si el valor no es interpretable.
    """
    from babel.numbers import parse_decimal, get_currency_precision
    from babel.numbers import NumberFormatError as BabelNumberFormatError
    s = str(value).strip()
    try:
        dec = parse_decimal(s, locale=locale or 'es')
    except (BabelNumberFormatError, ValueError, ArithmeticError) as exc:
        raise ValueError(f"monto no interpretable: {value!r}") from exc
    try:
        prec = get_currency_precision(code or 'USD')
    except Exception:
        prec = 2
    return Decimal(dec).quantize(Decimal(1).scaleb(-prec))


def parse_amount_for_user(value, user):
    """Interpreta un monto según las preferencias de moneda de un ``User``."""
    if user is None:
        return parse_amount(value)
    return parse_amount(
        value,
        locale=user.currency_locale or 'es',
        code=user.currency_code or 'USD',
    )
