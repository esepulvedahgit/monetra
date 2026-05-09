"""
Sheet 7 – Base de Datos
All transactions (full history), formatted as an Excel Table for analysis.
No charts — designed for pivot tables, slicers, and external tools.
"""
from datetime import date as _date
from app.export.sheets._helpers import write_title_row


def write(workbook, ws, fmt: dict, data: dict, lang: str = "es"):
    all_txs = data["all_transactions"]
    from_month = data.get("from_month", 1)
    to_month = data.get("to_month", 12)
    year = data["global_summary"]["year"]

    if from_month == to_month:
        title = (
            f"BASE DE DATOS — MES {from_month}/{year}"
            if lang == "es"
            else f"DATABASE — MONTH {from_month}/{year}"
        )
        subtitle = (
            f"  {len(all_txs)} transacciones · Mes {from_month}/{year}"
            if lang == "es"
            else f"  {len(all_txs)} transactions · Month {from_month}/{year}"
        )
    else:
        title = "BASE DE DATOS — HISTORIAL COMPLETO" if lang == "es" else "DATABASE — FULL HISTORY"
        subtitle = (
            f"  {len(all_txs)} transacciones · Todas las fechas"
            if lang == "es"
            else f"  {len(all_txs)} transactions · All dates"
        )

    # ── Column widths ─────────────────────────────────────────────────────────
    ws.set_column(0, 0, 6)    # ID
    ws.set_column(1, 1, 12)   # Fecha
    ws.set_column(2, 2, 6)    # Año
    ws.set_column(3, 3, 6)    # Mes
    ws.set_column(4, 4, 11)   # Tipo
    ws.set_column(5, 5, 22)   # Categoría
    ws.set_column(6, 6, 35)   # Descripción
    ws.set_column(7, 7, 15)   # Monto
    ws.set_column(8, 8, 8)    # Demo

    # ── Title ─────────────────────────────────────────────────────────────────
    write_title_row(ws, 0, f"  {title}", subtitle, fmt, 9)

    # ── Column headers ────────────────────────────────────────────────────────
    hdrs = (
        ["ID", "Fecha", "Año", "Mes", "Tipo", "Categoría", "Descripción", "Monto", "Demo"]
        if lang == "es"
        else ["ID", "Date", "Year", "Month", "Type", "Category", "Description", "Amount", "Demo"]
    )
    ws.set_row(3, 22)
    for c, h in enumerate(hdrs):
        ws.write(3, c, h, fmt["col_header"])

    ws.autofilter(3, 0, 3, 8)

    # ── Data rows ─────────────────────────────────────────────────────────────
    lbl_income = "Ingreso" if lang == "es" else "Income"
    lbl_expense = "Gasto" if lang == "es" else "Expense"

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

        ws.set_row(row, 16)
        ws.write(row, 0, tx["id"], ccfmt)
        if tx_date:
            ws.write_datetime(row, 1, tx_date, dfmt)
        else:
            ws.write(row, 1, tx.get("date", ""), dfmt)
        ws.write(row, 2, year_val, ccfmt)
        ws.write(row, 3, month_val, ccfmt)
        ws.write(row, 4, t_lbl, tbadge)
        ws.write(row, 5, tx.get("category_name") or "—", cfmt)
        ws.write(row, 6, tx.get("description") or "—", cfmt)
        ws.write(row, 7, tx["amount"], mfmt)
        ws.write(row, 8, "Sí" if tx.get("is_demo") else "No", ccfmt)

    if not all_txs:
        empty = "Sin transacciones registradas." if lang == "es" else "No transactions found."
        ws.merge_range(4, 0, 4, 8, empty, fmt["status_none"])
