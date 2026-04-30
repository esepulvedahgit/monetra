"""
Sheet 2 – Movimientos
Full transaction list for the selected period, with auto-filter and totals.
"""
from datetime import date as _date
from app.export.sheets._helpers import month_name, write_title_row


def write(workbook, ws, fmt: dict, data: dict, lang: str = "es"):
    txs = data["transactions"]
    from_m = data["global_summary"]["from_month"]
    to_m = data["global_summary"]["to_month"]
    year = data["global_summary"]["year"]

    period_label = month_name(from_m, lang)
    if from_m != to_m:
        period_label += f" — {month_name(to_m, lang)}"
    period_label += f" {year}"

    title = "MOVIMIENTOS" if lang == "es" else "TRANSACTIONS"
    subtitle = f"  Período: {period_label} — {len(txs)} registros"

    # ── Column widths ─────────────────────────────────────────────────────────
    ws.set_column(0, 0, 5)    # #
    ws.set_column(1, 1, 12)   # Fecha
    ws.set_column(2, 2, 11)   # Tipo
    ws.set_column(3, 3, 20)   # Categoría
    ws.set_column(4, 4, 35)   # Descripción
    ws.set_column(5, 5, 15)   # Monto

    # ── Title ─────────────────────────────────────────────────────────────────
    write_title_row(ws, 0, f"  {title}", subtitle, fmt, 6)

    # ── Column headers (row 3) ────────────────────────────────────────────────
    hdrs = (
        ["#", "Fecha", "Tipo", "Categoría", "Descripción", "Monto"]
        if lang == "es"
        else ["#", "Date", "Type", "Category", "Description", "Amount"]
    )
    ws.set_row(3, 22)
    for c, h in enumerate(hdrs):
        ws.write(3, c, h, fmt["col_header"])

    ws.autofilter(3, 0, 3, 5)

    # ── Data rows ─────────────────────────────────────────────────────────────
    total_income = 0.0
    total_expense = 0.0

    lbl_income = "Ingreso" if lang == "es" else "Income"
    lbl_expense = "Gasto" if lang == "es" else "Expense"

    for i, tx in enumerate(txs):
        row = 4 + i
        alt = i % 2 == 1
        cfmt = fmt["cell_alt"] if alt else fmt["cell"]
        ccfmt = fmt["cell_center_alt"] if alt else fmt["cell_center"]
        dfmt = fmt["date_alt"] if alt else fmt["date"]

        tx_date = _date.fromisoformat(tx["date"]) if tx.get("date") else None

        if tx["type"] == "income":
            mfmt = fmt["money_green_alt"] if alt else fmt["money_green"]
            tbadge = fmt["badge_income"]
            lbl_type = lbl_income
            total_income += tx["amount"]
        else:
            mfmt = fmt["money_red_alt"] if alt else fmt["money_red"]
            tbadge = fmt["badge_expense"]
            lbl_type = lbl_expense
            total_expense += tx["amount"]

        ws.set_row(row, 17)
        ws.write(row, 0, i + 1, ccfmt)
        if tx_date:
            ws.write_datetime(row, 1, tx_date, dfmt)
        else:
            ws.write(row, 1, tx.get("date", ""), dfmt)
        ws.write(row, 2, lbl_type, tbadge)
        ws.write(row, 3, tx.get("category_name") or "—", cfmt)
        ws.write(row, 4, tx.get("description") or "—", cfmt)
        ws.write(row, 5, tx["amount"], mfmt)

    # ── Totals ────────────────────────────────────────────────────────────────
    if txs:
        tot_row = 4 + len(txs) + 1
        ws.set_row(tot_row - 1, 6)  # spacer

        lbl_ti = "Total Ingresos" if lang == "es" else "Total Income"
        lbl_te = "Total Gastos" if lang == "es" else "Total Expenses"
        lbl_tb = "Balance" if lang == "es" else "Balance"

        ws.set_row(tot_row, 20)
        ws.merge_range(tot_row, 0, tot_row, 4, lbl_ti, fmt["total_label"])
        ws.write(tot_row, 5, total_income, fmt["money_total"])

        ws.set_row(tot_row + 1, 20)
        ws.merge_range(tot_row + 1, 0, tot_row + 1, 4, lbl_te, fmt["total_label"])
        ws.write(tot_row + 1, 5, total_expense, fmt["money_total"])

        ws.set_row(tot_row + 2, 20)
        ws.merge_range(tot_row + 2, 0, tot_row + 2, 4, lbl_tb, fmt["total_label"])
        ws.write(tot_row + 2, 5, total_income - total_expense, fmt["money_total"])
    else:
        empty_lbl = "Sin transacciones para el período." if lang == "es" else "No transactions for this period."
        ws.merge_range(4, 0, 4, 5, empty_lbl, fmt["status_none"])
