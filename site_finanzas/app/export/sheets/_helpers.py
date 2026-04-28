"""Shared helpers for all sheet modules."""
from datetime import date as _date

MONTHS_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}
MONTHS_EN = {
    1: "January", 2: "February", 3: "March", 4: "April",
    5: "May", 6: "June", 7: "July", 8: "August",
    9: "September", 10: "October", 11: "November", 12: "December",
}

CHART_COLORS = [
    "#00C896", "#3B82F6", "#8B5CF6", "#F59E0B", "#EF4444",
    "#06B6D4", "#84CC16", "#F97316", "#EC4899", "#14B8A6",
]


def month_name(month_num: int, lang: str = "es") -> str:
    names = MONTHS_ES if lang == "es" else MONTHS_EN
    return names.get(month_num, str(month_num))


def parse_date(date_str: str):
    if not date_str:
        return None
    try:
        return _date.fromisoformat(date_str)
    except ValueError:
        return None


def write_title_row(ws, row: int, title: str, subtitle: str, fmt: dict, n_cols: int = 9):
    ws.merge_range(row, 0, row, n_cols - 1, title, fmt["title"])
    ws.set_row(row, 36)
    ws.merge_range(row + 1, 0, row + 1, n_cols - 1, subtitle, fmt["subtitle"])
    ws.set_row(row + 1, 20)
    ws.set_row(row + 2, 6)  # spacer
