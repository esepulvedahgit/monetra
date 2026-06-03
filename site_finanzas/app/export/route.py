import io
from datetime import date
from flask import request, send_file
from flask_login import login_required, current_user
from app.export import export_bp
from app.export.excel_builder import build_excel


@export_bp.route("/export/excel")
@login_required
def export_excel():
    today = date.today()
    year = request.args.get("year", today.year, type=int)
    from_month = max(1, min(12, request.args.get("from_month", 1, type=int)))
    to_month = max(from_month, min(12, request.args.get("to_month", 12, type=int)))

    if not (2000 <= year <= 2100):
        year = today.year

    output: io.BytesIO = build_excel(current_user, year, from_month, to_month)
    if from_month == to_month:
        filename = f"monetra_{current_user.username}_{year}_{from_month:02d}.xlsx"
    else:
        filename = f"monetra_{current_user.username}_{year}.xlsx"

    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename,
    )
