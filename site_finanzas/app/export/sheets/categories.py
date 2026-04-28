"""
Sheet 3 – Categorías
Expense breakdown by category with horizontal bar chart.
"""
from app.export.sheets._helpers import month_name, write_title_row, CHART_COLORS


def write(workbook, ws, fmt: dict, data: dict, lang: str = "es"):
    ws_name = ws.name
    categories = data["global_summary"]["expense_by_category"]
    from_m = data["global_summary"]["from_month"]
    to_m = data["global_summary"]["to_month"]
    year = data["global_summary"]["year"]

    period_label = month_name(from_m, lang)
    if from_m != to_m:
        period_label += f" — {month_name(to_m, lang)}"
    period_label += f" {year}"

    title = "GASTOS POR CATEGORÍA" if lang == "es" else "EXPENSES BY CATEGORY"
    subtitle = f"  Período: {period_label}"

    # ── Column widths ─────────────────────────────────────────────────────────
    ws.set_column(0, 0, 26)  # category name
    ws.set_column(1, 1, 16)  # amount
    ws.set_column(2, 2, 12)  # % of total
    ws.set_column(3, 3, 2)   # spacer
    ws.set_column(4, 13, 8)  # chart area

    # ── Title ─────────────────────────────────────────────────────────────────
    write_title_row(ws, 0, f"  {title}", subtitle, fmt, 14)

    # ── Column headers ────────────────────────────────────────────────────────
    hdrs = (
        ["Categoría", "Total Gasto", "% del Total"]
        if lang == "es"
        else ["Category", "Total Expense", "% of Total"]
    )
    ws.set_row(3, 22)
    for c, h in enumerate(hdrs):
        ws.write(3, c, h, fmt["col_header"])

    grand_total = sum(cat["total"] for cat in categories) or 1
    data_start = 4

    for i, cat in enumerate(categories):
        row = data_start + i
        alt = i % 2 == 1
        cfmt = fmt["cell_alt"] if alt else fmt["cell"]
        mfmt = fmt["money_red_alt"] if alt else fmt["money_red"]
        pfmt = fmt["pct_alt"] if alt else fmt["pct"]
        ws.set_row(row, 18)
        ws.write(row, 0, cat["name"], cfmt)
        ws.write(row, 1, cat["total"], mfmt)
        ws.write(row, 2, cat["total"] / grand_total * 100, pfmt)

    data_end = data_start + len(categories) - 1

    # Total row
    if categories:
        tot_row = data_end + 1
        ws.set_row(tot_row, 20)
        total_lbl = "TOTAL" if lang == "es" else "TOTAL"
        ws.write(tot_row, 0, total_lbl, fmt["total_label"])
        ws.write(tot_row, 1, grand_total, fmt["money_total"])
        ws.write(tot_row, 2, 100.0, fmt["money_total"])
    else:
        empty = "Sin datos de gastos para el período." if lang == "es" else "No expense data for this period."
        ws.merge_range(4, 0, 4, 2, empty, fmt["status_none"])

    # ── Bar chart (horizontal) ────────────────────────────────────────────────
    if categories:
        chart = workbook.add_chart({"type": "bar"})
        chart.add_series(
            {
                "name": title,
                "categories": [ws_name, data_start, 0, data_end, 0],
                "values": [ws_name, data_start, 1, data_end, 1],
                "fill": {"color": "#EF4444"},
                "gap": 50,
                "data_labels": {"value": True, "font": {"size": 8}},
            }
        )
        chart.set_title({"name": title, "name_font": {"size": 11, "bold": True}})
        chart.set_x_axis({"name": "", "name_font": {"size": 9}})
        chart.set_y_axis({"name": "", "name_font": {"size": 9}, "reverse": True})
        chart.set_legend({"none": True})
        chart.set_style(10)
        chart.set_size({"width": 480, "height": max(260, len(categories) * 32 + 80)})
        ws.insert_chart(3, 4, chart, {"x_offset": 5, "y_offset": 5})
