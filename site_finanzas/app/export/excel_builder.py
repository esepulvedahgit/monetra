"""
Excel report orchestrator.
Fetches all data once via the service layer, then delegates each sheet to its module.
Adding or removing sheets only requires editing this file.
"""
import io

import xlsxwriter

from app.services import finance as svc
from app.export.styles import create_formats
from app.export.sheets import (
    dashboard as sh_dashboard,
    transactions as sh_transactions,
    categories as sh_categories,
    budgets as sh_budgets,
    savings as sh_savings,
    recurring as sh_recurring,
    raw_data as sh_raw,
)

try:
    from babel.numbers import get_currency_precision
    def _dec(code):
        return get_currency_precision(code or "USD")
except Exception:
    def _dec(code):
        return 2


def build_excel(user, year: int, from_month: int = 1, to_month: int = 12) -> io.BytesIO:
    lang = user.language or "es"
    sym = user.currency_symbol or "$"
    dec = _dec(user.currency_code or "USD")

    # ── Fetch all data once ───────────────────────────────────────────────────
    data = {
        "global_summary": svc.get_global_summary(user.id, year, from_month, to_month),
        "transactions": svc.get_transactions(
            user.id, year=year, from_month=from_month, to_month=to_month
        ),
        "budget_vs_actual": svc.get_budget_vs_actual(user.id, year, from_month, to_month),
        "savings": svc.get_savings(user.id),
        "recurring": svc.get_recurring(user.id),
        "all_transactions": svc.get_transactions(user.id),  # full history for raw sheet
    }

    # ── Build workbook ────────────────────────────────────────────────────────
    output = io.BytesIO()
    wb = xlsxwriter.Workbook(output, {"in_memory": True, "default_date_format": "yyyy-mm-dd"})
    wb.set_properties(
        {
            "title": f"Monetra – Reporte {year}",
            "subject": "Finanzas personales",
            "author": user.username,
            "company": "Monetra",
        }
    )

    fmt = create_formats(wb, sym=sym, dec=dec)

    # ── Sheet definitions: (name_es, name_en, writer_module) ─────────────────
    sheet_defs = [
        ("Dashboard", "Dashboard", sh_dashboard),
        ("Movimientos", "Transactions", sh_transactions),
        ("Categorías", "Categories", sh_categories),
        ("Presupuestos", "Budgets", sh_budgets),
        ("Metas", "Goals", sh_savings),
        ("Recurrentes", "Recurring", sh_recurring),
        ("Base de Datos", "Raw Data", sh_raw),
    ]

    for name_es, name_en, module in sheet_defs:
        sheet_name = name_es if lang == "es" else name_en
        ws = wb.add_worksheet(sheet_name)
        ws.hide_gridlines(2)  # hide both screen and print gridlines
        ws.set_zoom(90)
        module.write(wb, ws, fmt, data, lang)

    wb.close()
    output.seek(0)
    return output
