"""
Sheet 1 – Dashboard
KPIs + top expense categories (pie chart) + 12-month trend (line chart).
"""
from app.export.sheets._helpers import month_name, write_title_row, CHART_COLORS


def write(workbook, ws, fmt: dict, data: dict, lang: str = "es"):
    ws_name = ws.name
    from_m = data["global_summary"]["from_month"]
    to_m = data["global_summary"]["to_month"]
    year = data["global_summary"]["year"]

    trend_income = data["global_summary"]["trend_income"]
    trend_expense = data["global_summary"]["trend_expense"]
    categories = data["global_summary"]["expense_by_category"]

    # Period totals (slice the trend arrays to the selected range)
    period_income = sum(trend_income[m - 1] for m in range(from_m, to_m + 1))
    period_expense = sum(trend_expense[m - 1] for m in range(from_m, to_m + 1))
    period_balance = period_income - period_expense

    total_budget = sum(b["budget"] for b in data["budget_vs_actual"])

    period_label = month_name(from_m, lang)
    if from_m != to_m:
        period_label += f" — {month_name(to_m, lang)}"
    period_label += f" {year}"

    # ── Column widths ─────────────────────────────────────────────────────────
    ws.set_column(0, 0, 26)   # A: labels / category names
    ws.set_column(1, 1, 16)   # B: amounts
    ws.set_column(2, 2, 12)   # C: %
    ws.set_column(3, 3, 10)   # D: count / extra
    ws.set_column(4, 4, 2)    # E: spacer
    ws.set_column(5, 13, 10)  # F-N: chart area

    # ── Row 0-2: Title ────────────────────────────────────────────────────────
    title_lbl = "REPORTE FINANCIERO PERSONAL"
    if lang == "en":
        title_lbl = "PERSONAL FINANCE REPORT"
    write_title_row(ws, 0, f"  {title_lbl}", f"  Período: {period_label}", fmt, 14)

    # ── Row 3-4: KPI labels & values ─────────────────────────────────────────
    lbl_inc = "INGRESOS" if lang == "es" else "INCOME"
    lbl_exp = "GASTOS" if lang == "es" else "EXPENSES"
    lbl_bal = "BALANCE"
    lbl_bgt = "PRESUPUESTO TOTAL" if lang == "es" else "TOTAL BUDGET"

    ws.set_row(3, 20)
    ws.set_row(4, 45)

    ws.merge_range(3, 0, 3, 1, lbl_inc, fmt["kpi_label"])
    ws.merge_range(3, 2, 3, 3, lbl_exp, fmt["kpi_label_red"])
    ws.merge_range(3, 4, 3, 6, lbl_bal, fmt["kpi_label_neutral"])
    ws.merge_range(3, 7, 3, 9, lbl_bgt, fmt["kpi_label_neutral"])

    ws.merge_range(4, 0, 4, 1, period_income, fmt["kpi_value"])
    ws.merge_range(4, 2, 4, 3, period_expense, fmt["kpi_value_red"])

    bal_fmt = fmt["kpi_value"] if period_balance >= 0 else fmt["kpi_value_red"]
    ws.merge_range(4, 4, 4, 6, period_balance, bal_fmt)

    if total_budget > 0:
        bgt_pct = period_expense / total_budget * 100
        ws.merge_range(4, 7, 4, 9, bgt_pct, fmt["kpi_pct"])
    else:
        no_bgt = "Sin presupuesto" if lang == "es" else "No budget"
        ws.merge_range(4, 7, 4, 9, no_bgt, fmt["kpi_value_neutral"] if "kpi_value_neutral" in fmt else fmt["status_none"])

    ws.set_row(5, 8)  # spacer

    # ── Row 6-12: Top categories table ───────────────────────────────────────
    lbl_cats = "TOP CATEGORÍAS DE GASTO" if lang == "es" else "TOP EXPENSE CATEGORIES"
    ws.merge_range(6, 0, 6, 3, f"  {lbl_cats}", fmt["section"])
    ws.set_row(6, 24)

    hdrs = (
        ["Categoría", "Monto", "% Total", "# Trans."]
        if lang == "es"
        else ["Category", "Amount", "% Total", "# Trans."]
    )
    ws.set_row(7, 22)
    for c, h in enumerate(hdrs):
        ws.write(7, c, h, fmt["col_header"])

    top5 = categories[:5]
    other_total = sum(cat["total"] for cat in categories[5:])
    grand_total = sum(cat["total"] for cat in categories) or 1

    cat_data_start = 8
    for i, cat in enumerate(top5):
        alt = i % 2 == 1
        mfmt = fmt["money_alt"] if alt else fmt["money"]
        cfmt = fmt["cell_alt"] if alt else fmt["cell"]
        pfmt = fmt["pct_alt"] if alt else fmt["pct"]
        ws.set_row(cat_data_start + i, 18)
        ws.write(cat_data_start + i, 0, cat["name"], cfmt)
        ws.write(cat_data_start + i, 1, cat["total"], mfmt)
        ws.write(cat_data_start + i, 2, cat["total"] / grand_total * 100, pfmt)
        # Count of transactions not available in this aggregation – show dash
        ws.write(cat_data_start + i, 3, "—", fmt["cell_center_alt"] if alt else fmt["cell_center"])

    cat_end = cat_data_start + len(top5)

    if other_total > 0:
        otros = "Otros" if lang == "es" else "Others"
        ws.set_row(cat_end, 18)
        ws.write(cat_end, 0, otros, fmt["cell_alt"])
        ws.write(cat_end, 1, other_total, fmt["money_alt"])
        ws.write(cat_end, 2, other_total / grand_total * 100, fmt["pct_alt"])
        ws.write(cat_end, 3, "—", fmt["cell_center_alt"])
        cat_end += 1

    # Total row
    ws.set_row(cat_end, 20)
    total_lbl = "TOTAL" if lang == "es" else "TOTAL"
    ws.write(cat_end, 0, total_lbl, fmt["total_label"])
    ws.write(cat_end, 1, grand_total, fmt["money_total"])
    ws.write(cat_end, 2, 100.0, fmt["money_total"])
    ws.write(cat_end, 3, "", fmt["total_cell"])

    ws.set_row(cat_end + 1, 8)  # spacer

    # ── Pie chart: category distribution ─────────────────────────────────────
    if top5:
        pie = workbook.add_chart({"type": "pie"})
        pie.add_series(
            {
                "name": lbl_cats,
                "categories": [ws_name, cat_data_start, 0, cat_end - 1, 0],
                "values": [ws_name, cat_data_start, 1, cat_end - 1, 1],
                "data_labels": {
                    "percentage": True,
                    "category": True,
                    "separator": "\n",
                    "font": {"size": 8},
                },
                "points": [
                    {"fill": {"color": CHART_COLORS[i % len(CHART_COLORS)]}}
                    for i in range(cat_end - cat_data_start)
                ],
            }
        )
        pie.set_title({"name": lbl_cats, "name_font": {"size": 11, "bold": True}})
        pie.set_legend({"position": "bottom", "font": {"size": 8}})
        pie.set_style(10)
        pie.set_size({"width": 380, "height": 280})
        ws.insert_chart(6, 5, pie, {"x_offset": 5, "y_offset": 5})

    # ── Row cat_end+2 onwards: Monthly evolution ──────────────────────────────
    trend_start = cat_end + 2
    lbl_trend = "EVOLUCIÓN MENSUAL" if lang == "es" else "MONTHLY TREND"
    ws.merge_range(trend_start, 0, trend_start, 3, f"  {lbl_trend}", fmt["section"])
    ws.set_row(trend_start, 24)

    trend_hdrs = (
        ["Mes", "Ingresos", "Gastos", "Balance"]
        if lang == "es"
        else ["Month", "Income", "Expenses", "Balance"]
    )
    ws.set_row(trend_start + 1, 22)
    for c, h in enumerate(trend_hdrs):
        ws.write(trend_start + 1, c, h, fmt["col_header"])

    months_row_start = trend_start + 2
    t_income_total = 0.0
    t_expense_total = 0.0
    for i, m in enumerate(range(from_m, to_m + 1)):
        row = months_row_start + i
        alt = i % 2 == 1
        inc = trend_income[m - 1]
        exp = trend_expense[m - 1]
        bal = inc - exp
        cfmt = fmt["cell_alt"] if alt else fmt["cell"]
        mfmt = fmt["money_alt"] if alt else fmt["money"]
        sfmt = fmt["money_signed_alt"] if alt else fmt["money_signed"]
        ws.set_row(row, 17)
        ws.write(row, 0, month_name(m, lang), cfmt)
        ws.write(row, 1, inc, mfmt)
        ws.write(row, 2, exp, mfmt)
        ws.write(row, 3, bal, sfmt)
        t_income_total += inc
        t_expense_total += exp

    months_row_end = months_row_start + (to_m - from_m + 1) - 1

    # Totals row
    tot_row = months_row_end + 1
    ws.set_row(tot_row, 20)
    ws.write(tot_row, 0, "TOTAL", fmt["total_label"])
    ws.write(tot_row, 1, t_income_total, fmt["money_total"])
    ws.write(tot_row, 2, t_expense_total, fmt["money_total"])
    ws.write(tot_row, 3, t_income_total - t_expense_total, fmt["money_total"])

    # ── Line chart: monthly trend ─────────────────────────────────────────────
    line = workbook.add_chart({"type": "line"})
    line.add_series(
        {
            "name": "Ingresos" if lang == "es" else "Income",
            "categories": [ws_name, months_row_start, 0, months_row_end, 0],
            "values": [ws_name, months_row_start, 1, months_row_end, 1],
            "line": {"color": "#00C896", "width": 2.5},
            "marker": {"type": "circle", "size": 5, "fill": {"color": "#00C896"}},
        }
    )
    line.add_series(
        {
            "name": "Gastos" if lang == "es" else "Expenses",
            "categories": [ws_name, months_row_start, 0, months_row_end, 0],
            "values": [ws_name, months_row_start, 2, months_row_end, 2],
            "line": {"color": "#EF4444", "width": 2.5},
            "marker": {"type": "circle", "size": 5, "fill": {"color": "#EF4444"}},
        }
    )
    line.add_series(
        {
            "name": "Balance",
            "categories": [ws_name, months_row_start, 0, months_row_end, 0],
            "values": [ws_name, months_row_start, 3, months_row_end, 3],
            "line": {"color": "#3B82F6", "width": 2.0, "dash_type": "dash"},
            "marker": {"type": "diamond", "size": 5, "fill": {"color": "#3B82F6"}},
        }
    )
    line.set_title(
        {"name": lbl_trend, "name_font": {"size": 11, "bold": True}}
    )
    line.set_x_axis({"name": "", "name_font": {"size": 9}})
    line.set_y_axis({"name": "", "name_font": {"size": 9}})
    line.set_legend({"position": "bottom", "font": {"size": 9}})
    line.set_style(10)
    line.set_size({"width": 480, "height": 280})
    ws.insert_chart(trend_start, 5, line, {"x_offset": 5, "y_offset": 5})
