"""
Sheet 4 – Presupuestos
Month-by-month budget vs actual with status indicator and grouped bar chart.
"""
from app.export.sheets._helpers import month_name, write_title_row


_STATUS_LABELS = {
    "es": {"ok": "✓ OK", "warning": "⚠ Atención", "over": "✗ Excedido", "no_budget": "Sin presupuesto"},
    "en": {"ok": "✓ OK", "warning": "⚠ Warning", "over": "✗ Over budget", "no_budget": "No budget"},
}


def write(workbook, ws, fmt: dict, data: dict, lang: str = "es"):
    ws_name = ws.name
    rows = data["budget_vs_actual"]
    year = data["global_summary"]["year"]
    from_m = data["global_summary"]["from_month"]
    to_m = data["global_summary"]["to_month"]

    period_label = month_name(from_m, lang)
    if from_m != to_m:
        period_label += f" — {month_name(to_m, lang)}"
    period_label += f" {year}"

    status_lbl = _STATUS_LABELS.get(lang, _STATUS_LABELS["es"])
    title = "PRESUPUESTO vs REAL" if lang == "es" else "BUDGET vs ACTUAL"
    subtitle = f"  Período: {period_label}"

    # ── Column widths ─────────────────────────────────────────────────────────
    ws.set_column(0, 0, 15)   # Mes
    ws.set_column(1, 1, 16)   # Presupuesto
    ws.set_column(2, 2, 16)   # Real
    ws.set_column(3, 3, 16)   # Diferencia
    ws.set_column(4, 4, 12)   # % Ejecución
    ws.set_column(5, 5, 16)   # Estado
    ws.set_column(6, 6, 2)    # spacer
    ws.set_column(7, 17, 8)   # chart area

    # ── Title ─────────────────────────────────────────────────────────────────
    write_title_row(ws, 0, f"  {title}", subtitle, fmt, 18)

    # ── Column headers ────────────────────────────────────────────────────────
    hdrs = (
        ["Mes", "Presupuesto", "Gasto Real", "Diferencia", "% Ejecución", "Estado"]
        if lang == "es"
        else ["Month", "Budget", "Actual", "Difference", "% Used", "Status"]
    )
    ws.set_row(3, 22)
    for c, h in enumerate(hdrs):
        ws.write(3, c, h, fmt["col_header"])

    data_start = 4
    total_budget = 0.0
    total_actual = 0.0

    for i, r in enumerate(rows):
        row = data_start + i
        alt = i % 2 == 1
        cfmt = fmt["cell_alt"] if alt else fmt["cell"]
        mfmt = fmt["money_alt"] if alt else fmt["money"]
        pfmt = fmt["pct_alt"] if alt else fmt["pct"]

        diff = r["difference"]
        diff_fmt = (
            fmt["money_red_alt" if alt else "money_red"]
            if diff < 0
            else fmt["money_green_alt" if alt else "money_green"]
        )

        status_key = r["status"]
        sfmt = {
            "ok": fmt["status_ok"],
            "warning": fmt["status_warn"],
            "over": fmt["status_over"],
            "no_budget": fmt["status_none"],
        }.get(status_key, fmt["status_none"])

        pct_val = r["used_pct"]

        ws.set_row(row, 18)
        ws.write(row, 0, month_name(r["month"], lang), cfmt)
        ws.write(row, 1, r["budget"], mfmt)
        ws.write(row, 2, r["actual"], mfmt)
        ws.write(row, 3, diff, diff_fmt)
        ws.write(row, 4, pct_val if pct_val is not None else "—", pfmt if pct_val is not None else fmt["cell_center_alt" if alt else "cell_center"])
        ws.write(row, 5, status_lbl[status_key], sfmt)

        total_budget += r["budget"]
        total_actual += r["actual"]

    data_end = data_start + len(rows) - 1

    # ── Totals row ────────────────────────────────────────────────────────────
    tot_row = data_end + 1
    ws.set_row(tot_row, 20)
    total_lbl = "TOTAL" if lang == "es" else "TOTAL"
    ws.write(tot_row, 0, total_lbl, fmt["total_label"])
    ws.write(tot_row, 1, total_budget, fmt["money_total"])
    ws.write(tot_row, 2, total_actual, fmt["money_total"])
    ws.write(tot_row, 3, total_budget - total_actual, fmt["money_total"])
    pct_total = total_actual / total_budget * 100 if total_budget > 0 else 0
    ws.write(tot_row, 4, pct_total, fmt["money_total"])
    ws.write(tot_row, 5, "", fmt["total_cell"])

    # ── Grouped bar chart ────────────────────────────────────────────────────
    if rows:
        chart = workbook.add_chart({"type": "column"})
        chart.add_series(
            {
                "name": "Presupuesto" if lang == "es" else "Budget",
                "categories": [ws_name, data_start, 0, data_end, 0],
                "values": [ws_name, data_start, 1, data_end, 1],
                "fill": {"color": "#3B82F6"},
                "gap": 80,
            }
        )
        chart.add_series(
            {
                "name": "Real" if lang == "es" else "Actual",
                "categories": [ws_name, data_start, 0, data_end, 0],
                "values": [ws_name, data_start, 2, data_end, 2],
                "fill": {"color": "#EF4444"},
                "gap": 80,
            }
        )
        chart.set_title({"name": title, "name_font": {"size": 11, "bold": True}})
        chart.set_x_axis({"name": "", "name_font": {"size": 9}})
        chart.set_y_axis({"name": "", "name_font": {"size": 9}})
        chart.set_legend({"position": "bottom", "font": {"size": 9}})
        chart.set_style(10)
        chart.set_size({"width": 480, "height": 280})
        ws.insert_chart(3, 7, chart, {"x_offset": 5, "y_offset": 5})
