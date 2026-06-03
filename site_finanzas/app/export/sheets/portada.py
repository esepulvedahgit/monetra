"""
Sheet 0 – Portada
Cover page: period KPIs and sheet index with scope of each tab.
"""
from app.export.sheets._helpers import month_name, write_title_row


def write(workbook, ws, fmt: dict, data: dict, lang: str = "es"):
    gs = data["global_summary"]
    from_m = gs["from_month"]
    to_m = gs["to_month"]
    year = gs["year"]
    trend_income = gs["trend_income"]
    trend_expense = gs["trend_expense"]

    period_income = sum(trend_income[m - 1] for m in range(from_m, to_m + 1))
    period_expense = sum(trend_expense[m - 1] for m in range(from_m, to_m + 1))
    period_balance = period_income - period_expense
    n_txs = len(data["transactions"])

    if from_m == to_m:
        period_label = f"{month_name(from_m, lang)} {year}"
    else:
        period_label = f"{month_name(from_m, lang)} – {month_name(to_m, lang)} {year}"

    # ── Column widths ─────────────────────────────────────────────────────────
    ws.set_column(0, 0, 22)   # A: sheet name
    ws.set_column(1, 5, 9)    # B-F: description (merged)
    ws.set_column(6, 6, 20)   # G: scope badge
    ws.set_column(7, 7, 4)    # H: padding

    # ── Title ─────────────────────────────────────────────────────────────────
    title = "MONETRA — REPORTE FINANCIERO" if lang == "es" else "MONETRA — FINANCIAL REPORT"
    subtitle_period = "Período" if lang == "es" else "Period"
    write_title_row(ws, 0, f"  {title}", f"  {subtitle_period}: {period_label}", fmt, 8)

    # ── KPIs (rows 3-4) ───────────────────────────────────────────────────────
    lbl_inc = "INGRESOS" if lang == "es" else "INCOME"
    lbl_exp = "GASTOS" if lang == "es" else "EXPENSES"
    lbl_bal = "BALANCE"
    lbl_txs = "TRANSACCIONES" if lang == "es" else "TRANSACTIONS"

    ws.set_row(3, 20)
    ws.set_row(4, 45)

    ws.merge_range(3, 0, 3, 1, lbl_inc, fmt["kpi_label"])
    ws.merge_range(3, 2, 3, 3, lbl_exp, fmt["kpi_label_red"])
    ws.merge_range(3, 4, 3, 5, lbl_bal, fmt["kpi_label_neutral"])
    ws.merge_range(3, 6, 3, 7, lbl_txs, fmt["kpi_label_neutral"])

    ws.merge_range(4, 0, 4, 1, period_income, fmt["kpi_value"])
    ws.merge_range(4, 2, 4, 3, period_expense, fmt["kpi_value_red"])
    bal_fmt = fmt["kpi_value"] if period_balance >= 0 else fmt["kpi_value_red"]
    ws.merge_range(4, 4, 4, 5, period_balance, bal_fmt)
    ws.merge_range(4, 6, 4, 7, n_txs, fmt["kpi_value_int"])

    ws.set_row(5, 10)  # spacer

    # ── Sheet index ───────────────────────────────────────────────────────────
    lbl_idx = "ÍNDICE DE PESTAÑAS" if lang == "es" else "SHEET INDEX"
    ws.merge_range(6, 0, 6, 7, f"  {lbl_idx}", fmt["section"])
    ws.set_row(6, 24)

    h_tab = "Pestaña" if lang == "es" else "Sheet"
    h_desc = "Contenido" if lang == "es" else "Content"
    h_scope = "Alcance" if lang == "es" else "Scope"
    ws.set_row(7, 22)
    ws.write(7, 0, h_tab, fmt["col_header"])
    ws.merge_range(7, 1, 7, 5, h_desc, fmt["col_header"])
    ws.merge_range(7, 6, 7, 7, h_scope, fmt["col_header"])

    scope_period = "Período seleccionado" if lang == "es" else "Selected period"
    scope_full = "Historial completo" if lang == "es" else "Full history"

    if lang == "es":
        sheets_info = [
            ("Dashboard",     "KPIs, evolución mensual y distribución por categorías",  scope_period),
            ("Movimientos",   "Listado detallado de ingresos y gastos",                 scope_period),
            ("Categorías",    "Total de gastos agrupados por categoría",                scope_period),
            ("Presupuestos",  "Comparativa entre presupuesto fijado y gasto real",      scope_period),
            ("Metas",         "Objetivos de ahorro y estado de avance",                 scope_full),
            ("Recurrentes",   "Gastos e ingresos fijos mensuales y su estado",          scope_full),
            ("Base de Datos", "Datos en bruto para análisis propio (tablas dinámicas)", scope_period),
        ]
    else:
        sheets_info = [
            ("Dashboard",    "KPIs, monthly trend and category breakdown",      scope_period),
            ("Transactions", "Detailed list of income and expenses",            scope_period),
            ("Categories",   "Total expenses grouped by category",              scope_period),
            ("Budgets",      "Budget vs actual spending comparison",            scope_period),
            ("Goals",        "Savings goals and their progress",                scope_full),
            ("Recurring",    "Fixed monthly income and expenses with status",   scope_full),
            ("Raw Data",     "Raw data for custom analysis (pivot tables)",     scope_period),
        ]

    for i, (tab_name, desc, scope) in enumerate(sheets_info):
        row = 8 + i
        alt = i % 2 == 1
        cfmt = fmt["cell_alt"] if alt else fmt["cell"]
        name_fmt = fmt["cell_bold"] if not alt else fmt["cell_alt"]
        scope_fmt = fmt["status_ok"] if scope == scope_period else fmt["status_none"]
        ws.set_row(row, 18)
        ws.write(row, 0, tab_name, name_fmt)
        ws.merge_range(row, 1, row, 5, desc, cfmt)
        ws.merge_range(row, 6, row, 7, scope, scope_fmt)
