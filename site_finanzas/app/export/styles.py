"""
Shared XlsxWriter format definitions for Monetra Excel export.
All formats use a light, print-friendly theme consistent with the app's color palette.
"""


# Palette
_TEAL = "#00C896"
_TEAL_DARK = "#007A5E"
_TEAL_HEADER = "#0F4C38"
_GREEN_BG = "#ECFDF5"
_GREEN_BORDER = "#6EE7B7"
_RED = "#DC2626"
_RED_BG = "#FEF2F2"
_RED_BORDER = "#FECACA"
_YELLOW = "#D97706"
_YELLOW_BG = "#FFFBEB"
_YELLOW_BORDER = "#FDE68A"
_BLUE = "#2563EB"
_BLUE_BG = "#EFF6FF"
_GRAY_HEADER = "#374151"
_GRAY_BG = "#F9FAFB"
_GRAY_BORDER = "#E5E7EB"
_GRAY_ALT = "#F3F4F6"
_WHITE = "#FFFFFF"


def _money_fmt(sym: str, dec: int) -> str:
    return f'"{sym}"#,##0' + (f'.{"0" * dec}' if dec > 0 else "")


def _money_fmt_red(sym: str, dec: int) -> str:
    base = f'"{sym}"#,##0' + (f'.{"0" * dec}' if dec > 0 else "")
    return f"{base};[RED]-{base}"


def create_formats(workbook, sym: str = "$", dec: int = 2) -> dict:
    mfmt = _money_fmt(sym, dec)
    mfmt_signed = _money_fmt_red(sym, dec)

    f = {}

    # ── Title / section ───────────────────────────────────────────────────────
    f["title"] = workbook.add_format(
        {
            "bold": True,
            "font_size": 18,
            "font_color": _WHITE,
            "bg_color": _TEAL_HEADER,
            "align": "left",
            "valign": "vcenter",
            "left": 0,
            "top": 0,
            "right": 0,
            "bottom": 0,
        }
    )
    f["title_right"] = workbook.add_format(
        {
            "bold": True,
            "font_size": 11,
            "font_color": _TEAL,
            "bg_color": _TEAL_HEADER,
            "align": "right",
            "valign": "vcenter",
        }
    )
    f["subtitle"] = workbook.add_format(
        {
            "font_size": 10,
            "font_color": "#6B7280",
            "bg_color": _GRAY_BG,
            "align": "left",
            "valign": "vcenter",
            "italic": True,
        }
    )
    f["section"] = workbook.add_format(
        {
            "bold": True,
            "font_size": 10,
            "font_color": _WHITE,
            "bg_color": _TEAL_DARK,
            "align": "left",
            "valign": "vcenter",
            "left": 1,
            "left_color": _TEAL,
            "top": 0,
            "bottom": 0,
            "right": 0,
        }
    )

    # ── Column headers ────────────────────────────────────────────────────────
    f["col_header"] = workbook.add_format(
        {
            "bold": True,
            "font_size": 9,
            "font_color": _WHITE,
            "bg_color": _GRAY_HEADER,
            "align": "center",
            "valign": "vcenter",
            "border": 1,
            "border_color": "#4B5563",
            "text_wrap": True,
        }
    )
    f["col_header_left"] = workbook.add_format(
        {
            "bold": True,
            "font_size": 9,
            "font_color": _WHITE,
            "bg_color": _GRAY_HEADER,
            "align": "left",
            "valign": "vcenter",
            "border": 1,
            "border_color": "#4B5563",
        }
    )

    # ── KPI boxes ─────────────────────────────────────────────────────────────
    f["kpi_label"] = workbook.add_format(
        {
            "font_size": 8,
            "font_color": "#6B7280",
            "bg_color": _GREEN_BG,
            "align": "center",
            "valign": "vcenter",
            "bold": True,
            "border": 1,
            "border_color": _GREEN_BORDER,
            "top": 2,
            "top_color": _TEAL,
        }
    )
    f["kpi_label_red"] = workbook.add_format(
        {
            "font_size": 8,
            "font_color": "#6B7280",
            "bg_color": _RED_BG,
            "align": "center",
            "valign": "vcenter",
            "bold": True,
            "border": 1,
            "border_color": _RED_BORDER,
            "top": 2,
            "top_color": _RED,
        }
    )
    f["kpi_label_neutral"] = workbook.add_format(
        {
            "font_size": 8,
            "font_color": "#6B7280",
            "bg_color": _BLUE_BG,
            "align": "center",
            "valign": "vcenter",
            "bold": True,
            "border": 1,
            "border_color": "#BFDBFE",
            "top": 2,
            "top_color": _BLUE,
        }
    )
    f["kpi_value"] = workbook.add_format(
        {
            "bold": True,
            "font_size": 16,
            "font_color": _TEAL_DARK,
            "bg_color": _GREEN_BG,
            "align": "center",
            "valign": "vcenter",
            "num_format": mfmt,
            "border": 1,
            "border_color": _GREEN_BORDER,
        }
    )
    f["kpi_value_red"] = workbook.add_format(
        {
            "bold": True,
            "font_size": 16,
            "font_color": _RED,
            "bg_color": _RED_BG,
            "align": "center",
            "valign": "vcenter",
            "num_format": mfmt,
            "border": 1,
            "border_color": _RED_BORDER,
        }
    )
    f["kpi_value_neutral"] = workbook.add_format(
        {
            "bold": True,
            "font_size": 16,
            "font_color": _BLUE,
            "bg_color": _BLUE_BG,
            "align": "center",
            "valign": "vcenter",
            "num_format": mfmt,
            "border": 1,
            "border_color": "#BFDBFE",
        }
    )
    f["kpi_pct"] = workbook.add_format(
        {
            "bold": True,
            "font_size": 16,
            "font_color": _YELLOW,
            "bg_color": _YELLOW_BG,
            "align": "center",
            "valign": "vcenter",
            "num_format": '0.0"%"',
            "border": 1,
            "border_color": _YELLOW_BORDER,
        }
    )
    f["kpi_value_int"] = workbook.add_format(
        {
            "bold": True,
            "font_size": 16,
            "font_color": _BLUE,
            "bg_color": _BLUE_BG,
            "align": "center",
            "valign": "vcenter",
            "num_format": "0",
            "border": 1,
            "border_color": "#BFDBFE",
        }
    )

    # ── Regular cells ─────────────────────────────────────────────────────────
    f["cell"] = workbook.add_format(
        {
            "font_size": 9,
            "border": 1,
            "border_color": _GRAY_BORDER,
            "valign": "vcenter",
        }
    )
    f["cell_alt"] = workbook.add_format(
        {
            "font_size": 9,
            "border": 1,
            "border_color": _GRAY_BORDER,
            "bg_color": _GRAY_ALT,
            "valign": "vcenter",
        }
    )
    f["cell_center"] = workbook.add_format(
        {
            "font_size": 9,
            "border": 1,
            "border_color": _GRAY_BORDER,
            "align": "center",
            "valign": "vcenter",
        }
    )
    f["cell_center_alt"] = workbook.add_format(
        {
            "font_size": 9,
            "border": 1,
            "border_color": _GRAY_BORDER,
            "bg_color": _GRAY_ALT,
            "align": "center",
            "valign": "vcenter",
        }
    )
    f["cell_bold"] = workbook.add_format(
        {
            "font_size": 9,
            "bold": True,
            "border": 1,
            "border_color": _GRAY_BORDER,
            "valign": "vcenter",
        }
    )

    # ── Money cells ───────────────────────────────────────────────────────────
    f["money"] = workbook.add_format(
        {
            "font_size": 9,
            "num_format": mfmt,
            "align": "right",
            "border": 1,
            "border_color": _GRAY_BORDER,
            "valign": "vcenter",
        }
    )
    f["money_alt"] = workbook.add_format(
        {
            "font_size": 9,
            "num_format": mfmt,
            "align": "right",
            "border": 1,
            "border_color": _GRAY_BORDER,
            "bg_color": _GRAY_ALT,
            "valign": "vcenter",
        }
    )
    f["money_green"] = workbook.add_format(
        {
            "font_size": 9,
            "bold": True,
            "num_format": mfmt,
            "font_color": _TEAL_DARK,
            "align": "right",
            "border": 1,
            "border_color": _GRAY_BORDER,
            "valign": "vcenter",
        }
    )
    f["money_green_alt"] = workbook.add_format(
        {
            "font_size": 9,
            "bold": True,
            "num_format": mfmt,
            "font_color": _TEAL_DARK,
            "align": "right",
            "border": 1,
            "border_color": _GRAY_BORDER,
            "bg_color": _GRAY_ALT,
            "valign": "vcenter",
        }
    )
    f["money_red"] = workbook.add_format(
        {
            "font_size": 9,
            "bold": True,
            "num_format": mfmt,
            "font_color": _RED,
            "align": "right",
            "border": 1,
            "border_color": _GRAY_BORDER,
            "valign": "vcenter",
        }
    )
    f["money_red_alt"] = workbook.add_format(
        {
            "font_size": 9,
            "bold": True,
            "num_format": mfmt,
            "font_color": _RED,
            "align": "right",
            "border": 1,
            "border_color": _GRAY_BORDER,
            "bg_color": _GRAY_ALT,
            "valign": "vcenter",
        }
    )
    f["money_signed"] = workbook.add_format(
        {
            "font_size": 9,
            "num_format": mfmt_signed,
            "align": "right",
            "border": 1,
            "border_color": _GRAY_BORDER,
            "valign": "vcenter",
        }
    )
    f["money_signed_alt"] = workbook.add_format(
        {
            "font_size": 9,
            "num_format": mfmt_signed,
            "align": "right",
            "border": 1,
            "border_color": _GRAY_BORDER,
            "bg_color": _GRAY_ALT,
            "valign": "vcenter",
        }
    )
    f["money_total"] = workbook.add_format(
        {
            "font_size": 9,
            "bold": True,
            "num_format": mfmt,
            "align": "right",
            "border": 1,
            "border_color": _GRAY_BORDER,
            "bg_color": "#E5E7EB",
            "valign": "vcenter",
        }
    )

    # ── Percent cells ─────────────────────────────────────────────────────────
    f["pct"] = workbook.add_format(
        {
            "font_size": 9,
            "num_format": '0.0"%"',
            "align": "center",
            "border": 1,
            "border_color": _GRAY_BORDER,
            "valign": "vcenter",
        }
    )
    f["pct_alt"] = workbook.add_format(
        {
            "font_size": 9,
            "num_format": '0.0"%"',
            "align": "center",
            "border": 1,
            "border_color": _GRAY_BORDER,
            "bg_color": _GRAY_ALT,
            "valign": "vcenter",
        }
    )

    # ── Date cells ────────────────────────────────────────────────────────────
    f["date"] = workbook.add_format(
        {
            "font_size": 9,
            "num_format": "yyyy-mm-dd",
            "align": "center",
            "border": 1,
            "border_color": _GRAY_BORDER,
            "valign": "vcenter",
        }
    )
    f["date_alt"] = workbook.add_format(
        {
            "font_size": 9,
            "num_format": "yyyy-mm-dd",
            "align": "center",
            "border": 1,
            "border_color": _GRAY_BORDER,
            "bg_color": _GRAY_ALT,
            "valign": "vcenter",
        }
    )

    # ── Status badges ─────────────────────────────────────────────────────────
    f["status_ok"] = workbook.add_format(
        {
            "font_size": 9,
            "bold": True,
            "align": "center",
            "valign": "vcenter",
            "border": 1,
            "border_color": _GRAY_BORDER,
            "bg_color": "#D1FAE5",
            "font_color": "#065F46",
        }
    )
    f["status_warn"] = workbook.add_format(
        {
            "font_size": 9,
            "bold": True,
            "align": "center",
            "valign": "vcenter",
            "border": 1,
            "border_color": _GRAY_BORDER,
            "bg_color": _YELLOW_BG,
            "font_color": "#92400E",
        }
    )
    f["status_over"] = workbook.add_format(
        {
            "font_size": 9,
            "bold": True,
            "align": "center",
            "valign": "vcenter",
            "border": 1,
            "border_color": _GRAY_BORDER,
            "bg_color": _RED_BG,
            "font_color": "#991B1B",
        }
    )
    f["status_none"] = workbook.add_format(
        {
            "font_size": 9,
            "align": "center",
            "valign": "vcenter",
            "border": 1,
            "border_color": _GRAY_BORDER,
            "bg_color": _GRAY_ALT,
            "font_color": "#6B7280",
        }
    )
    f["badge_income"] = workbook.add_format(
        {
            "font_size": 9,
            "align": "center",
            "valign": "vcenter",
            "border": 1,
            "border_color": _GRAY_BORDER,
            "bg_color": "#D1FAE5",
            "font_color": "#065F46",
        }
    )
    f["badge_expense"] = workbook.add_format(
        {
            "font_size": 9,
            "align": "center",
            "valign": "vcenter",
            "border": 1,
            "border_color": _GRAY_BORDER,
            "bg_color": _RED_BG,
            "font_color": "#991B1B",
        }
    )
    f["badge_active"] = workbook.add_format(
        {
            "font_size": 9,
            "align": "center",
            "valign": "vcenter",
            "border": 1,
            "border_color": _GRAY_BORDER,
            "bg_color": "#D1FAE5",
            "font_color": "#065F46",
        }
    )
    f["badge_inactive"] = workbook.add_format(
        {
            "font_size": 9,
            "align": "center",
            "valign": "vcenter",
            "border": 1,
            "border_color": _GRAY_BORDER,
            "bg_color": _GRAY_ALT,
            "font_color": "#6B7280",
        }
    )

    # ── Total / footer rows ───────────────────────────────────────────────────
    f["total_label"] = workbook.add_format(
        {
            "bold": True,
            "font_size": 9,
            "align": "right",
            "valign": "vcenter",
            "border": 1,
            "border_color": _GRAY_BORDER,
            "bg_color": "#E5E7EB",
        }
    )
    f["total_cell"] = workbook.add_format(
        {
            "bold": True,
            "font_size": 9,
            "valign": "vcenter",
            "border": 1,
            "border_color": _GRAY_BORDER,
            "bg_color": "#E5E7EB",
        }
    )

    return f
