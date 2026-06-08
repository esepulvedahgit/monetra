"""
Sheet 7 – Base de Datos
Transactions for the selected period, formatted as an Excel Table for analysis.
No charts — designed for pivot tables, slicers, and external tools.
"""
from datetime import date as _date
from app.export.sheets._helpers import month_name, write_title_row


def write(workbook, ws, fmt: dict, data: dict, lang: str = "es"):
    all_txs = data["all_transactions"]
    from_month = data.get("from_month", 1)
    to_month = data.get("to_month", 12)
    year = data["global_summary"]["year"]

    if from_month == to_month:
        period_str = f"{month_name(from_month, lang)} {year}"
    else:
        period_str = f"{month_name(from_month, lang)} – {month_name(to_month, lang)} {year}"

    title = (
        f"BASE DE DATOS — {period_str.upper()}"
        if lang == "es"
        else f"DATABASE — {period_str.upper()}"
    )
    subtitle = (
        f"  {len(all_txs)} transacciones · {period_str}"
        if lang == "es"
        else f"  {len(all_txs)} transactions · {period_str}"
    )

    # ── Column widths ─────────────────────────────────────────────────────────
    ws.set_column(0, 0, 6)    # ID
    ws.set_column(1, 1, 12)   # Fecha
    ws.set_column(2, 2, 6)    # Año
    ws.set_column(3, 3, 6)    # Mes
    ws.set_column(4, 4, 11)   # Tipo
    ws.set_column(5, 5, 14)   # Origen
    ws.set_column(6, 6, 22)   # Categoría
    ws.set_column(7, 7, 35)   # Descripción
    ws.set_column(8, 8, 15)   # Monto
    ws.set_column(9, 9, 8)    # Demo

    # ── Title ─────────────────────────────────────────────────────────────────
    write_title_row(ws, 0, f"  {title}", subtitle, fmt, 10)

    # ── Column headers ────────────────────────────────────────────────────────
    hdrs = (
        ["ID", "Fecha", "Año", "Mes", "Tipo", "Origen", "Categoría", "Descripción", "Monto", "Demo"]
        if lang == "es"
        else ["ID", "Date", "Year", "Month", "Type", "Origin", "Category", "Description", "Amount", "Demo"]
    )
    ws.set_row(3, 22)
    for c, h in enumerate(hdrs):
        ws.write(3, c, h, fmt["col_header"])

    ws.autofilter(3, 0, 3, 9)

    # ── Data rows ─────────────────────────────────────────────────────────────
    lbl_income = "Ingreso" if lang == "es" else "Income"
    lbl_expense = "Gasto" if lang == "es" else "Expense"
    lbl_recurrente = "Recurrente" if lang == "es" else "Recurring"
    lbl_manual = "Manual"

    for i, tx in enumerate(all_txs):
        row = 4 + i
        alt = i % 2 == 1
        cfmt = fmt["cell_alt"] if alt else fmt["cell"]
        ccfmt = fmt["cell_center_alt"] if alt else fmt["cell_center"]
        dfmt = fmt["date_alt"] if alt else fmt["date"]

        tx_date = _date.fromisoformat(tx["date"]) if tx.get("date") else None

        if tx["type"] == "income":
            mfmt = fmt["money_green_alt"] if alt else fmt["money_green"]
            tbadge = fmt["badge_income"]
            t_lbl = lbl_income
        else:
            mfmt = fmt["money_red_alt"] if alt else fmt["money_red"]
            tbadge = fmt["badge_expense"]
            t_lbl = lbl_expense

        year_val = tx_date.year if tx_date else ""
        month_val = tx_date.month if tx_date else ""
        origen = lbl_recurrente if tx.get("recurring_id") else lbl_manual

        ws.set_row(row, 16)
        ws.write(row, 0, tx["id"], ccfmt)
        if tx_date:
            ws.write_datetime(row, 1, tx_date, dfmt)
        else:
            ws.write(row, 1, tx.get("date", ""), dfmt)
        ws.write(row, 2, year_val, ccfmt)
        ws.write(row, 3, month_val, ccfmt)
        ws.write(row, 4, t_lbl, tbadge)
        ws.write(row, 5, origen, ccfmt)
        ws.write(row, 6, tx.get("category_name") or "—", cfmt)
        ws.write(row, 7, tx.get("description") or "—", cfmt)
        ws.write(row, 8, tx["amount"], mfmt)
        ws.write(row, 9, "Sí" if tx.get("is_demo") else "No", ccfmt)

    if not all_txs:
        empty = "Sin transacciones registradas." if lang == "es" else "No transactions found."
        ws.merge_range(4, 0, 4, 9, empty, fmt["status_none"])
