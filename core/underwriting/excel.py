"""Excel export built from scratch with openpyxl.

One workbook, four sheets. The monthly schedule is written as values from the engine; every
total, margin, ratio, and the XIRR on the Summary sheet is a live formula over that schedule,
so a reviewer can audit the arithmetic in Excel and trace each headline figure to the months
behind it. Nothing from the internal workbook template is shipped.
"""

from __future__ import annotations

import io
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from core.underwriting.inputs import DealInputs
from core.underwriting.irr import cashflow_dates
from core.underwriting.sensitivity import build_grid
from core.underwriting.summary import Outputs

INK = "16191D"
MUTED = "6C7078"
NAVY = "0F2A44"
HEAD_FILL = PatternFill("solid", fgColor="F2F5F8")
HEADER_FONT = Font(name="Arial", size=9, bold=True, color=MUTED)
TITLE_FONT = Font(name="Arial", size=14, bold=True, color=INK)
BODY_FONT = Font(name="Arial", size=10, color=INK)
TOTAL_FONT = Font(name="Arial", size=10, bold=True, color=INK)
NOTE_FONT = Font(name="Arial", size=9, italic=True, color=MUTED)
MONEY = '#,##0;(#,##0);"-"'
MONEY_M = '#,##0.0,,;(#,##0.0,,);"-"'
PCT = "0.0%"
DATE = "mmm yyyy"

MONTHLY_COLUMNS: list[tuple[str, str, str]] = [
    # (header, attribute on MonthlyCashflow, group)
    ("Lot sales and fees", "rev_lot_sales", "revenue"),
    ("Residential pods", "rev_res_pods", "revenue"),
    ("Commercial pods", "rev_comm_pods", "revenue"),
    ("MUD and WCID", "rev_mud_wcid", "revenue"),
    ("Land", "cost_land", "cost"),
    ("Sections", "cost_sections", "cost"),
    ("Plants", "cost_plants", "cost"),
    ("Detention", "cost_detention", "cost"),
    ("Collector roads", "cost_roads", "cost"),
    ("Amenities", "cost_amenities", "cost"),
    ("Other items", "cost_other", "cost"),
    ("Landscaping", "cost_landscaping", "cost"),
    ("Fencing", "cost_fencing", "cost"),
    ("Dry utilities", "cost_dry_utilities", "cost"),
    ("Site work", "cost_site_work", "cost"),
    ("DMF", "cost_dmf", "cost"),
    ("Operating, fees and contingency", "cost_operating", "cost"),
]


def _title(ws: Worksheet, text: str, subtitle: str) -> None:
    ws["A1"] = text
    ws["A1"].font = TITLE_FONT
    ws["A2"] = subtitle
    ws["A2"].font = NOTE_FONT


def _header(ws: Worksheet, row: int, labels: list[str], start_col: int = 1) -> None:
    for i, label in enumerate(labels):
        cell = ws.cell(row=row, column=start_col + i, value=label)
        cell.font = HEADER_FONT
        cell.fill = HEAD_FILL
        cell.alignment = Alignment(horizontal="left" if i == 0 else "right")


def _write_inputs(ws: Worksheet, inputs: DealInputs, deal_name: str, scenario_name: str) -> None:
    _title(ws, f"{deal_name} · {scenario_name}", "Inputs. Percentages are fractions.")
    t, c, r = inputs.tract, inputs.costs, inputs.revenue
    rows: list[tuple[str, Any, str]] = [
        ("Gross acreage", t.gross_acreage, "#,##0.0"),
        ("Purchase price per acre", t.purchase_price_per_acre, MONEY),
        ("Closing costs", t.closing_costs_pct, PCT),
        ("Land escalator", t.land_escalator, PCT),
        ("Closing date", t.closing_date, DATE),
        ("Detention storage rate (ac-ft / ac)", t.det_storage_rate, "0.00"),
        ("Detention depth (ft)", t.det_depth, "0.0"),
        ("Detention projects", t.det_num_projects, "0"),
        ("Parks and green space", t.parks_pct, PCT),
        ("Drill site acres", t.drill_site_acres, "#,##0.0"),
        ("Commercial pod acres", t.commercial_pod_acres, "#,##0.0"),
        ("Residential pod acres", t.residential_pod_acres, "#,##0.0"),
        ("Default other costs", c.default_other_pct, PCT),
        ("Sectional other costs", c.sectional_other_pct, PCT),
        ("Landscaping other costs", c.landscaping_other_pct, PCT),
        ("Project contingency", c.contingency, PCT),
        ("Site work (% of revenue)", c.site_work_pct, PCT),
        ("Lots fenced", c.fenced_pct, PCT),
        ("Professional services (% of revenue)", c.prof_svc_pct, PCT),
        ("DMF (% of costs)", c.dmf_pct, PCT),
        ("Personnel per month", c.personnel_monthly, MONEY),
        ("Marketing personnel per month", c.marketing_personnel_monthly, MONEY),
        ("Legal per month", c.legal_monthly, MONEY),
        ("MUD and HOA per month", c.mud_monthly, MONEY),
        ("Insurance per month", c.insurance_monthly, MONEY),
        ("Bookkeeping per month", c.bookkeeping_monthly, MONEY),
        ("Revenue timing method", r.timing_method, "@"),
        ("Builder earnest money period (months)", r.bem_period, "0"),
        ("Builder earnest money", r.bem_pct, PCT),
        ("Brokerage fees", r.brokerage_fees, PCT),
        ("Lot closing costs", r.lot_closing_costs, PCT),
        ("MUD debt ratio", r.mud_bond.debt_ratio, PCT),
        ("WCID debt ratio", r.wcid_bond.debt_ratio, PCT),
    ]
    _header(ws, 4, ["Input", "Value"])
    for i, (label, value, fmt) in enumerate(rows, start=5):
        ws.cell(row=i, column=1, value=label).font = BODY_FONT
        cell = ws.cell(row=i, column=2, value=value)
        cell.font = BODY_FONT
        cell.number_format = fmt
        cell.alignment = Alignment(horizontal="right")

    row = 5 + len(rows) + 1
    ws.cell(row=row, column=1, value="Lot price per front foot by year").font = HEADER_FONT
    _header(ws, row + 1, ["Year", "$ / FF"])
    for y, price in enumerate(r.price_per_ff):
        ws.cell(row=row + 2 + y, column=1, value=y).font = BODY_FONT
        cell = ws.cell(row=row + 2 + y, column=2, value=price)
        cell.number_format = MONEY
        cell.font = BODY_FONT

    row = row + 2 + len(r.price_per_ff) + 1
    ws.cell(row=row, column=1, value="Lot mix").font = HEADER_FONT
    lot_cols = [
        ("Front footage", "front_footage", "0"),
        ("On", "on", "@"),
        ("Yield (lots / ac)", "yield_per_ac", "0.0"),
        ("Pace (lots / mo)", "pace", "0.0"),
        ("Home price", "home_price", MONEY),
        ("WSD per FF", "wsd_per_ff", MONEY),
        ("Paving per FF", "paving_per_ff", MONEY),
        ("Landscaping per lot", "landscaping_per_lot", MONEY),
        ("Premium per FF", "premium_per_ff", MONEY),
        ("Escalation", "escalation", PCT),
        ("Fence fee per FF", "fence_per_ff", MONEY),
        ("Marketing fee", "marketing_fee", MONEY),
    ]
    _header(ws, row + 1, [label for label, _, _ in lot_cols])
    for i, ls in enumerate(c.lot_sizes):
        for j, (_, attr, fmt) in enumerate(lot_cols):
            value = getattr(ls, attr)
            cell = ws.cell(
                row=row + 2 + i,
                column=1 + j,
                value="Yes" if value is True else ("No" if value is False else value),
            )
            cell.font = BODY_FONT
            cell.number_format = fmt
    ws.column_dimensions["A"].width = 38
    ws.column_dimensions["B"].width = 16
    for j in range(3, 3 + len(lot_cols)):
        ws.column_dimensions[get_column_letter(j)].width = 14


def _write_pro_forma(ws: Worksheet, inputs: DealInputs, out: Outputs) -> dict[str, Any]:
    """Monthly schedule with live totals. Returns the ranges the Summary sheet refers to."""
    _title(
        ws,
        "Pro forma, monthly",
        "$ whole dollars. Line items are engine values; totals, net, and cumulative are formulas.",
    )
    months = out.cf_monthly
    n = len(months)
    closing = inputs.tract.closing_date
    dates = cashflow_dates(closing, n) if closing else None

    labels = (
        ["Month", "Date", "Year"]
        + [h for h, _, _ in MONTHLY_COLUMNS]
        + ["Total revenue", "Total cost", "Net cash flow", "Cumulative"]
    )
    header_row = 4
    _header(ws, header_row, labels)
    first = header_row + 1
    last = header_row + n
    rev_cols = [i for i, (_, _, g) in enumerate(MONTHLY_COLUMNS) if g == "revenue"]
    cost_cols = [i for i, (_, _, g) in enumerate(MONTHLY_COLUMNS) if g == "cost"]

    def col_of(idx: int) -> str:
        return get_column_letter(4 + idx)

    rev_first, rev_last = col_of(rev_cols[0]), col_of(rev_cols[-1])
    cost_first, cost_last = col_of(cost_cols[0]), col_of(cost_cols[-1])
    total_rev_col = get_column_letter(4 + len(MONTHLY_COLUMNS))
    total_cost_col = get_column_letter(5 + len(MONTHLY_COLUMNS))
    net_col = get_column_letter(6 + len(MONTHLY_COLUMNS))
    cum_col = get_column_letter(7 + len(MONTHLY_COLUMNS))

    for i, m in enumerate(months):
        row = first + i
        ws.cell(row=row, column=1, value=m.month).font = BODY_FONT
        if dates:
            d = ws.cell(row=row, column=2, value=dates[i])
            d.number_format = DATE
            d.font = BODY_FONT
        ws.cell(row=row, column=3, value=m.year).font = BODY_FONT
        for j, (_, attr, _) in enumerate(MONTHLY_COLUMNS):
            cell = ws.cell(row=row, column=4 + j, value=getattr(m, attr))
            cell.number_format = MONEY
            cell.font = BODY_FONT
        for col, formula in (
            (total_rev_col, f"=SUM({rev_first}{row}:{rev_last}{row})"),
            (total_cost_col, f"=SUM({cost_first}{row}:{cost_last}{row})"),
            (net_col, f"={total_rev_col}{row}-{total_cost_col}{row}"),
            (cum_col, f"={net_col}{row}" if i == 0 else f"={cum_col}{row - 1}+{net_col}{row}"),
        ):
            cell = ws[f"{col}{row}"]
            cell.value = formula
            cell.number_format = MONEY
            cell.font = TOTAL_FONT if col in (net_col, cum_col) else BODY_FONT

    total_row = last + 1
    ws.cell(row=total_row, column=1, value="Total").font = TOTAL_FONT
    for j in range(len(MONTHLY_COLUMNS) + 3):
        col = get_column_letter(4 + j)
        cell = ws[f"{col}{total_row}"]
        cell.value = f"=SUM({col}{first}:{col}{last})"
        cell.number_format = MONEY
        cell.font = TOTAL_FONT
    ws.freeze_panes = f"D{first}"
    ws.column_dimensions["B"].width = 11
    for j in range(4, 8 + len(MONTHLY_COLUMNS)):
        ws.column_dimensions[get_column_letter(j)].width = 13

    return {
        "sheet": "'Pro forma'",
        "rev_total": f"'Pro forma'!{total_rev_col}{total_row}",
        "cost_total": f"'Pro forma'!{total_cost_col}{total_row}",
        "net_range": f"'Pro forma'!{net_col}{first}:{net_col}{last}",
        "date_range": f"'Pro forma'!B{first}:B{last}" if dates else "",
        "cum_range": f"'Pro forma'!{cum_col}{first}:{cum_col}{last}",
        "year_range": f"'Pro forma'!C{first}:C{last}",
        "first": str(first),
        "last": str(last),
        "col_of": {
            attr: get_column_letter(4 + j) for j, (_, attr, _) in enumerate(MONTHLY_COLUMNS)
        },
    }


def _write_summary(
    ws: Worksheet, out: Outputs, refs: dict[str, Any], deal_name: str, scenario_name: str
) -> None:
    _title(
        ws,
        f"{deal_name} · {scenario_name} · Summary",
        "Headline figures are formulas over the Pro forma sheet; "
        "line items are engine values that foot to the same totals.",
    )
    s = out.summary
    row = 4
    _header(ws, row, ["Headline", "Value", "Basis"])
    headline: list[tuple[str, str, str, str]] = [
        ("Total revenue", f"={refs['rev_total']}", MONEY, "Sum of monthly revenue"),
        (
            "Gross costs",
            f"={refs['cost_total']}",
            MONEY,
            "Sum of monthly cost, including below-the-line items",
        ),
        (
            "Net cash flow",
            f"={refs['rev_total']}-{refs['cost_total']}",
            MONEY,
            "Revenue less all costs (net margin)",
        ),
        ("Net margin, % of revenue", "=IFERROR(B7/B5,0)", PCT, ""),
        (
            "Peak cash need",
            f"=-MIN({refs['cum_range']})",
            MONEY,
            "Most negative cumulative net cash flow",
        ),
        ("Project length, months", f"=COUNT({refs['net_range']})", "0", "Months with activity"),
    ]
    if refs["date_range"]:
        headline.append(
            (
                "Unlevered IRR",
                f"=XIRR({refs['net_range']},{refs['date_range']})",
                PCT,
                "XIRR, actual / 365, month 1 = closing date",
            )
        )
    else:
        headline.append(
            (
                "Unlevered IRR",
                f"=(1+IRR({refs['net_range']}))^12-1",
                PCT,
                "Monthly IRR annualised (no closing date set)",
            )
        )
    for i, (label, formula, fmt, basis) in enumerate(headline):
        r = row + 1 + i
        ws.cell(row=r, column=1, value=label).font = TOTAL_FONT
        cell = ws.cell(row=r, column=2, value=formula)
        cell.number_format = fmt
        cell.font = TOTAL_FONT
        cell.alignment = Alignment(horizontal="right")
        ws.cell(row=r, column=3, value=basis).font = NOTE_FONT

    row = row + 2 + len(headline)
    ws.cell(row=row, column=1, value="Engine figures for reference").font = HEADER_FONT
    _header(ws, row + 1, ["Line", "Amount", "% of revenue"])
    lines: list[tuple[str, float, bool]] = []
    for label, key in (
        ("Lot sales", "lot_sales"),
        ("MUD proceeds", "mud"),
        ("WCID proceeds", "wcid"),
        ("Lot premiums", "premiums"),
        ("Fence fees", "fence_fees"),
        ("Escalations", "escalations"),
        ("Marketing fees", "marketing_fees"),
        ("Residential pod sales", "residential_pods"),
        ("Commercial pod sales", "commercial_pods"),
    ):
        lines.append((label, getattr(out.revenue, key), False))
    lines.append(("Total revenue", out.revenue.total, True))
    for label, key in (
        ("Land", "land"),
        ("Plants", "plants"),
        ("Amenities", "amenities"),
        ("Detention", "detention"),
        ("Sections", "sections"),
        ("Other items", "other"),
        ("Collector roads", "roads"),
        ("Fencing", "fencing"),
        ("Dry utilities", "dry_utilities"),
        ("Site work", "site_work"),
        ("Landscaping", "landscaping"),
        ("Legal", "legal"),
        ("Lot taxes", "lot_taxes"),
        ("MUD and HOA", "mud_hoa"),
        ("Insurance", "insurance"),
        ("Marketing", "marketing"),
        ("Brokerage", "brokerage"),
        ("Lot closing costs", "closing"),
        ("Mailboxes", "mailboxes"),
        ("Professional services", "professional_services"),
        ("Contingency", "contingency"),
    ):
        lines.append((label, getattr(out.costs, key), False))
    lines.append(("Gross costs", out.costs.total, True))
    lines.append(("Gross margin", s.gross_margin, True))
    for label, key in (
        ("Development management fee", "dmf"),
        ("Personnel", "personnel"),
        ("Bookkeeping", "bookkeeping"),
        ("Receivables fees", "receivables_fees"),
    ):
        lines.append((label, getattr(out.below_line, key), False))
    lines.append(("Net margin", s.net_margin, True))
    first_line = row + 2
    total_rev_cell = None
    for i, (label, value, is_total) in enumerate(lines):
        r = first_line + i
        ws.cell(row=r, column=1, value=label).font = TOTAL_FONT if is_total else BODY_FONT
        cell = ws.cell(row=r, column=2, value=value)
        cell.number_format = MONEY
        cell.font = TOTAL_FONT if is_total else BODY_FONT
        if label == "Total revenue":
            total_rev_cell = f"$B${r}"
        if total_rev_cell or label == "Total revenue":
            ref = total_rev_cell or f"$B${r}"
            p = ws.cell(row=r, column=3, value=f"=IFERROR(B{r}/{ref},0)")
            p.number_format = PCT
            p.font = BODY_FONT
    ws.column_dimensions["A"].width = 34
    ws.column_dimensions["B"].width = 18
    ws.column_dimensions["C"].width = 48


def _write_sensitivity(ws: Worksheet, inputs: DealInputs) -> None:
    grid = build_grid(inputs)
    _title(ws, "Sensitivity · Unlevered IRR", grid.note + " Values from the engine.")
    _header(ws, 4, ["Pace (lots / mo)"] + grid.col_labels)
    for i, row in enumerate(grid.rows):
        ws.cell(row=5 + i, column=1, value=row.label).font = BODY_FONT
        for j, cell in enumerate(row.cells):
            c = ws.cell(row=5 + i, column=2 + j, value=cell.value)
            c.number_format = PCT
            c.font = TOTAL_FONT if cell.base else BODY_FONT
            if cell.base:
                c.fill = PatternFill("solid", fgColor="DCE4EC")
    ws.column_dimensions["A"].width = 18


def export_workbook(inputs: DealInputs, out: Outputs, deal_name: str, scenario_name: str) -> bytes:
    wb = Workbook()
    ws_inputs = wb.active
    assert isinstance(ws_inputs, Worksheet)
    ws_inputs.title = "Inputs"
    _write_inputs(ws_inputs, inputs, deal_name, scenario_name)
    ws_pf = wb.create_sheet("Pro forma")
    refs = _write_pro_forma(ws_pf, inputs, out)
    ws_summary = wb.create_sheet("Summary")
    _write_summary(ws_summary, out, refs, deal_name, scenario_name)
    _write_sensitivity(wb.create_sheet("Sensitivity"), inputs)
    wb.move_sheet("Summary", offset=-1)
    wb.calculation.fullCalcOnLoad = True
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
