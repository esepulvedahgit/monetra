"""
Sheet 5 – Metas de Ahorro
Progress table with stacked horizontal bar chart (saved vs remaining).
"""
from datetime import date as _date
from app.export.sheets._helpers import write_title_row


def write(workbook, ws, fmt: dict, data: dict, lang: str = "es"):
    ws_name = ws.name
    goals = data["savings"]

    title = "METAS DE AHORRO" if lang == "es" else "SAVINGS GOALS"

    active = [g for g in goals if not g["is_completed"]]
    completed = [g for g in goals if g["is_completed"]]

    total_saved = sum(g["current_amount"] for g in goals)
    total_target = sum(g["target_amount"] for g in goals)
    subtitle = (
        f"  {len(active)} activas · {len(completed)} completadas · "
        f"Total ahorrado: {total_saved:,.0f} / {total_target:,.0f}"
        if lang == "es"
        else f"  {len(active)} active · {len(completed)} completed · "
        f"Total saved: {total_saved:,.0f} / {total_target:,.0f}"
    )

    # ── Column widths ─────────────────────────────────────────────────────────
    ws.set_column(0, 0, 24)   # Nombre
    ws.set_column(1, 1, 15)   # Objetivo
    ws.set_column(2, 2, 15)   # Ahorrado
    ws.set_column(3, 3, 15)   # Restante
    ws.set_column(4, 4, 12)   # Progreso %
    ws.set_column(5, 5, 13)   # Fecha límite
    ws.set_column(6, 6, 12)   # Días restantes
    ws.set_column(7, 7, 14)   # Estado
    ws.set_column(8, 8, 2)    # spacer
    ws.set_column(9, 18, 8)   # chart area

    # ── Title ─────────────────────────────────────────────────────────────────
    write_title_row(ws, 0, f"  {title}", subtitle, fmt, 19)

    # ── KPI summary row ───────────────────────────────────────────────────────
    ws.set_row(3, 20)
    ws.set_row(4, 40)
    kpi_labels = (
        ["METAS ACTIVAS", "COMPLETADAS", "TOTAL AHORRADO", "TOTAL OBJETIVO"]
        if lang == "es"
        else ["ACTIVE GOALS", "COMPLETED", "TOTAL SAVED", "TOTAL TARGET"]
    )
    ws.merge_range(3, 0, 3, 1, kpi_labels[0], fmt["kpi_label"])
    ws.merge_range(3, 2, 3, 3, kpi_labels[1], fmt["kpi_label"])
    ws.merge_range(3, 4, 3, 5, kpi_labels[2], fmt["kpi_label"])
    ws.merge_range(3, 6, 3, 7, kpi_labels[3], fmt["kpi_label_red"])

    ws.merge_range(4, 0, 4, 1, len(active), fmt["kpi_value_neutral"])
    ws.merge_range(4, 2, 4, 3, len(completed), fmt["kpi_value"])
    ws.merge_range(4, 4, 4, 5, total_saved, fmt["kpi_value"])
    ws.merge_range(4, 6, 4, 7, total_target, fmt["kpi_value_red"])

    ws.set_row(5, 8)  # spacer

    # ── Table headers ─────────────────────────────────────────────────────────
    hdrs = (
        ["Meta", "Objetivo", "Ahorrado", "Restante", "Progreso", "Fecha Límite", "Días", "Estado"]
        if lang == "es"
        else ["Goal", "Target", "Saved", "Remaining", "Progress", "Deadline", "Days", "Status"]
    )
    ws.set_row(6, 22)
    for c, h in enumerate(hdrs):
        ws.write(6, c, h, fmt["col_header"])

    if not goals:
        empty = "Sin metas de ahorro registradas." if lang == "es" else "No savings goals registered."
        ws.merge_range(7, 0, 7, 7, empty, fmt["status_none"])
        return

    # ── Data rows ─────────────────────────────────────────────────────────────
    data_start = 7
    active_data_start = data_start
    today = _date.today()

    for i, g in enumerate(goals):
        row = data_start + i
        alt = i % 2 == 1
        cfmt = fmt["cell_alt"] if alt else fmt["cell"]
        mfmt = fmt["money_alt"] if alt else fmt["money"]
        pfmt = fmt["pct_alt"] if alt else fmt["pct"]
        ccfmt = fmt["cell_center_alt"] if alt else fmt["cell_center"]

        # Status
        if g["is_completed"]:
            sfmt = fmt["status_ok"]
            slbl = "✓ Completada" if lang == "es" else "✓ Completed"
        elif g["days_left"] is not None and g["days_left"] < 0:
            sfmt = fmt["status_over"]
            slbl = "✗ Vencida" if lang == "es" else "✗ Overdue"
        elif g["days_left"] is not None and g["days_left"] < 30:
            sfmt = fmt["status_warn"]
            slbl = f"⚠ {g['days_left']}d"
        else:
            sfmt = fmt["status_none"]
            slbl = "En curso" if lang == "es" else "In progress"

        deadline_str = g.get("target_date") or ""
        days_val = g["days_left"] if g["days_left"] is not None else "—"

        ws.set_row(row, 18)
        ws.write(row, 0, g["name"], cfmt)
        ws.write(row, 1, g["target_amount"], mfmt)
        ws.write(row, 2, g["current_amount"], mfmt)
        ws.write(row, 3, g["remaining"], mfmt)
        ws.write(row, 4, g["progress_pct"], pfmt)
        if deadline_str:
            d_obj = _date.fromisoformat(deadline_str)
            ws.write_datetime(row, 5, d_obj, fmt["date_alt"] if alt else fmt["date"])
        else:
            ws.write(row, 5, "—", ccfmt)
        ws.write(row, 6, days_val, ccfmt)
        ws.write(row, 7, slbl, sfmt)

    data_end = data_start + len(goals) - 1

    # ── Totals row ────────────────────────────────────────────────────────────
    tot_row = data_end + 1
    ws.set_row(tot_row, 20)
    ws.write(tot_row, 0, "TOTAL", fmt["total_label"])
    ws.write(tot_row, 1, total_target, fmt["money_total"])
    ws.write(tot_row, 2, total_saved, fmt["money_total"])
    ws.write(tot_row, 3, total_target - total_saved, fmt["money_total"])
    pct_overall = total_saved / total_target * 100 if total_target > 0 else 0
    ws.write(tot_row, 4, pct_overall, fmt["money_total"])
    for c in range(5, 8):
        ws.write(tot_row, c, "", fmt["total_cell"])

    # ── Stacked bar chart (saved vs remaining) for active goals ──────────────
    active_goals = [g for g in goals if not g["is_completed"]]
    if active_goals:
        # Write a mini data table for the chart (separate area at column 10+)
        chart_data_col_name = 10
        chart_data_col_saved = 11
        chart_data_col_remain = 12
        chart_data_row_start = 6

        ws.write(chart_data_row_start, chart_data_col_name, "Meta", fmt["col_header"])
        ws.write(chart_data_row_start, chart_data_col_saved, "Ahorrado" if lang == "es" else "Saved", fmt["col_header"])
        ws.write(chart_data_row_start, chart_data_col_remain, "Restante" if lang == "es" else "Remaining", fmt["col_header"])

        for j, g in enumerate(active_goals):
            r = chart_data_row_start + 1 + j
            ws.write(r, chart_data_col_name, g["name"], fmt["cell"])
            ws.write(r, chart_data_col_saved, g["current_amount"], fmt["money"])
            ws.write(r, chart_data_col_remain, g["remaining"], fmt["money"])

        chart_data_end = chart_data_row_start + len(active_goals)

        chart = workbook.add_chart({"type": "bar", "subtype": "stacked"})
        chart.add_series(
            {
                "name": "Ahorrado" if lang == "es" else "Saved",
                "categories": [ws_name, chart_data_row_start + 1, chart_data_col_name,
                                chart_data_end, chart_data_col_name],
                "values": [ws_name, chart_data_row_start + 1, chart_data_col_saved,
                           chart_data_end, chart_data_col_saved],
                "fill": {"color": "#00C896"},
                "data_labels": {"value": True, "font": {"size": 8}},
            }
        )
        chart.add_series(
            {
                "name": "Restante" if lang == "es" else "Remaining",
                "categories": [ws_name, chart_data_row_start + 1, chart_data_col_name,
                                chart_data_end, chart_data_col_name],
                "values": [ws_name, chart_data_row_start + 1, chart_data_col_remain,
                           chart_data_end, chart_data_col_remain],
                "fill": {"color": "#E5E7EB"},
            }
        )
        chart_title = "Progreso de Metas Activas" if lang == "es" else "Active Goals Progress"
        chart.set_title({"name": chart_title, "name_font": {"size": 11, "bold": True}})
        chart.set_x_axis({"name": "", "name_font": {"size": 9}})
        chart.set_y_axis({"name": "", "name_font": {"size": 9}, "reverse": True})
        chart.set_legend({"position": "bottom", "font": {"size": 9}})
        chart.set_style(10)
        chart.set_size({"width": 420, "height": max(220, len(active_goals) * 35 + 100)})
        ws.insert_chart(6, 9, chart, {"x_offset": 5, "y_offset": 5})
