"""
Sheet 6 – Recurrentes
Recurring transactions table with impact summary and bar chart by category.
"""
from app.export.sheets._helpers import write_title_row, CHART_COLORS


def write(workbook, ws, fmt: dict, data: dict, lang: str = "es"):
    ws_name = ws.name
    items = data["recurring"]

    active = [r for r in items if r["is_active"]]
    inactive = [r for r in items if not r["is_active"]]

    total_expense = sum(r["amount"] for r in active if r["type"] == "expense")
    total_income = sum(r["amount"] for r in active if r["type"] == "income")

    year = data["global_summary"]["year"]
    title = "TRANSACCIONES RECURRENTES" if lang == "es" else "RECURRING TRANSACTIONS"
    subtitle = (
        f"  Año {year} · Activas: {len(active)} · Gasto fijo: {total_expense:,.0f} · Ingreso fijo: {total_income:,.0f} /mes"
        if lang == "es"
        else f"  Year {year} · Active: {len(active)} · Fixed expense: {total_expense:,.0f} · Fixed income: {total_income:,.0f} /mo"
    )

    # ── Column widths ─────────────────────────────────────────────────────────
    ws.set_column(0, 0, 28)   # Descripción
    ws.set_column(1, 1, 12)   # Tipo
    ws.set_column(2, 2, 20)   # Categoría
    ws.set_column(3, 3, 8)    # Día
    ws.set_column(4, 4, 15)   # Monto
    ws.set_column(5, 5, 13)   # Estado
    ws.set_column(6, 6, 12)   # Término
    ws.set_column(7, 7, 2)    # spacer
    ws.set_column(8, 18, 8)   # chart area

    # ── Title ─────────────────────────────────────────────────────────────────
    write_title_row(ws, 0, f"  {title}", subtitle, fmt, 18)

    # ── KPI row ───────────────────────────────────────────────────────────────
    ws.set_row(3, 20)
    ws.set_row(4, 40)
    kpi_l = (
        ["ACTIVAS", "GASTO FIJO /MES", "INGRESO FIJO /MES", "FLUJO NETO /MES"]
        if lang == "es"
        else ["ACTIVE", "FIXED EXPENSE /MO", "FIXED INCOME /MO", "NET FLOW /MO"]
    )
    ws.merge_range(3, 0, 3, 1, kpi_l[0], fmt["kpi_label_neutral"])
    ws.merge_range(3, 2, 3, 3, kpi_l[1], fmt["kpi_label_red"])
    ws.merge_range(3, 4, 3, 5, kpi_l[2], fmt["kpi_label"])
    ws.merge_range(3, 6, 3, 8, kpi_l[3], fmt["kpi_label_neutral"])

    ws.merge_range(4, 0, 4, 1, len(active), fmt["kpi_value_neutral"])
    ws.merge_range(4, 2, 4, 3, total_expense, fmt["kpi_value_red"])
    ws.merge_range(4, 4, 4, 5, total_income, fmt["kpi_value"])
    net_flow = total_income - total_expense
    net_fmt = fmt["kpi_value"] if net_flow >= 0 else fmt["kpi_value_red"]
    ws.merge_range(4, 6, 4, 8, net_flow, net_fmt)
    ws.set_row(5, 8)  # spacer

    # ── Table headers ─────────────────────────────────────────────────────────
    hdrs = (
        ["Descripción", "Tipo", "Categoría", "Día", "Monto /Mes", "Estado", "Término"]
        if lang == "es"
        else ["Description", "Type", "Category", "Day", "Amount /Mo", "Status", "End"]
    )
    ws.set_row(6, 22)
    for c, h in enumerate(hdrs):
        ws.write(6, c, h, fmt["col_header"])

    if not items:
        empty = "Sin transacciones recurrentes registradas." if lang == "es" else "No recurring transactions registered."
        ws.merge_range(7, 0, 7, 6, empty, fmt["status_none"])
        return

    lbl_income = "Ingreso" if lang == "es" else "Income"
    lbl_expense = "Gasto" if lang == "es" else "Expense"
    lbl_active = "Activa" if lang == "es" else "Active"
    lbl_inactive = "Inactiva" if lang == "es" else "Inactive"
    lbl_dia = "Día" if lang == "es" else "Day"

    data_start = 7
    # Active items first, then inactive
    all_items = active + inactive

    for i, r in enumerate(all_items):
        row = data_start + i
        alt = i % 2 == 1
        cfmt = fmt["cell_alt"] if alt else fmt["cell"]
        ccfmt = fmt["cell_center_alt"] if alt else fmt["cell_center"]

        mfmt = (
            (fmt["money_red_alt"] if alt else fmt["money_red"])
            if r["type"] == "expense"
            else (fmt["money_green_alt"] if alt else fmt["money_green"])
        )
        tbadge = fmt["badge_expense"] if r["type"] == "expense" else fmt["badge_income"]
        sbadge = fmt["badge_active"] if r["is_active"] else fmt["badge_inactive"]
        t_lbl = lbl_expense if r["type"] == "expense" else lbl_income
        s_lbl = lbl_active if r["is_active"] else lbl_inactive

        ws.set_row(row, 18)
        ws.write(row, 0, r["description"] or "—", cfmt)
        ws.write(row, 1, t_lbl, tbadge)
        ws.write(row, 2, r["category_name"] or "—", cfmt)
        ws.write(row, 3, f"{lbl_dia} {r['day_of_month']}", ccfmt)
        ws.write(row, 4, r["amount"], mfmt)
        ws.write(row, 5, s_lbl, sbadge)
        ws.write(row, 6, r.get("end_date") or "31/12", ccfmt)

    data_end = data_start + len(all_items) - 1

    # ── Totals ────────────────────────────────────────────────────────────────
    tot_row = data_end + 1
    ws.set_row(tot_row, 20)
    ws.merge_range(tot_row, 0, tot_row, 3, "Gasto fijo mensual:" if lang == "es" else "Monthly fixed expense:", fmt["total_label"])
    ws.write(tot_row, 4, total_expense, fmt["money_total"])
    ws.write(tot_row, 5, "", fmt["total_cell"])

    ws.set_row(tot_row + 1, 20)
    ws.merge_range(tot_row + 1, 0, tot_row + 1, 3, "Ingreso fijo mensual:" if lang == "es" else "Monthly fixed income:", fmt["total_label"])
    ws.write(tot_row + 1, 4, total_income, fmt["money_total"])
    ws.write(tot_row + 1, 5, "", fmt["total_cell"])

    # ── Bar chart: expense by category (active only) ──────────────────────────
    if active:
        # Aggregate expense by category
        cat_totals: dict = {}
        for r in active:
            if r["type"] == "expense":
                cat = r["category_name"] or "Sin categoría"
                cat_totals[cat] = cat_totals.get(cat, 0) + r["amount"]

        if cat_totals:
            # Write chart data in a hidden area (column 9+)
            chart_col_cat = 9
            chart_col_amt = 10
            chart_row_start = 6

            ws.write(chart_row_start, chart_col_cat, "Categoría" if lang == "es" else "Category", fmt["col_header"])
            ws.write(chart_row_start, chart_col_amt, "Monto /mes" if lang == "es" else "Amount /mo", fmt["col_header"])

            sorted_cats = sorted(cat_totals.items(), key=lambda x: x[1], reverse=True)
            for j, (cat_name, amt) in enumerate(sorted_cats):
                r = chart_row_start + 1 + j
                ws.write(r, chart_col_cat, cat_name, fmt["cell"])
                ws.write(r, chart_col_amt, amt, fmt["money"])

            chart_data_end = chart_row_start + len(sorted_cats)

            chart = workbook.add_chart({"type": "bar"})
            chart.add_series(
                {
                    "name": "Monto mensual" if lang == "es" else "Monthly amount",
                    "categories": [ws_name, chart_row_start + 1, chart_col_cat,
                                   chart_data_end, chart_col_cat],
                    "values": [ws_name, chart_row_start + 1, chart_col_amt,
                               chart_data_end, chart_col_amt],
                    "fill": {"color": "#EF4444"},
                    "gap": 50,
                    "data_labels": {"value": True, "font": {"size": 8}},
                }
            )
            chart_title = "Gasto Recurrente por Categoría" if lang == "es" else "Recurring Expense by Category"
            chart.set_title({"name": chart_title, "name_font": {"size": 11, "bold": True}})
            chart.set_x_axis({"name": "", "name_font": {"size": 9}})
            chart.set_y_axis({"name": "", "name_font": {"size": 9}, "reverse": True})
            chart.set_legend({"none": True})
            chart.set_style(10)
            chart.set_size({"width": 420, "height": max(220, len(sorted_cats) * 35 + 100)})
            ws.insert_chart(6, 8, chart, {"x_offset": 5, "y_offset": 5})
