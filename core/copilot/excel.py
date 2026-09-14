"""Excel export of the multifamily model, built from scratch with openpyxl.

Sheets: Inputs, Summary, Pro forma (monthly), Annual, Waterfall. Monthly line items are engine
values; NOI, cash flow, cumulative, the annual roll-up, DSCR, and the returns on the Summary
sheet are live formulas over them, so the arithmetic can be audited in Excel.
"""

from __future__ import annotations

import io
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from core.copilot.inputs import CopilotInputs
from core.copilot.summary import CopilotOutputs

INK = "16191D"
MUTED = "6C7078"
HEAD_FILL = PatternFill("solid", fgColor="F2F5F8")
BASE_FILL = PatternFill("solid", fgColor="DCE4EC")
HEADER_FONT = Font(name="Arial", size=9, bold=True, color=MUTED)
TITLE_FONT = Font(name="Arial", size=14, bold=True, color=INK)
BODY_FONT = Font(name="Arial", size=10, color=INK)
TOTAL_FONT = Font(name="Arial", size=10, bold=True, color=INK)
NOTE_FONT = Font(name="Arial", size=9, italic=True, color=MUTED)
MONEY = '#,##0;(#,##0);"-"'
PCT = "0.0%"
PCT2 = "0.00%"
MULT = '0.00"x"'
DATE = "mmm yyyy"

MONTHLY_LINES: list[tuple[str, str]] = [
    ("Gross potential rent", "gpr"),
    ("Loss to lease", "loss_to_lease"),
    ("Renovation premium", "renovation_premium"),
    ("Renovation vacancy", "renovation_vacancy"),
    ("Vacancy", "vacancy"),
    ("Concessions", "concessions"),
    ("Non-revenue units", "non_revenue"),
    ("Bad debt", "bad_debt"),
    ("Other income", "other_income"),
    ("Controllable expenses", "controllable"),
    ("Real estate taxes", "taxes"),
    ("Management fee", "management_fee"),
    ("Replacement reserves", "reserves"),
    ("Interest", "interest"),
    ("Principal", "principal"),
    ("Asset management fee", "asset_management_fee"),
]
REVENUE_KEYS = {
    "gpr",
    "loss_to_lease",
    "renovation_premium",
    "renovation_vacancy",
    "vacancy",
    "concessions",
    "non_revenue",
    "bad_debt",
    "other_income",
}
OPEX_KEYS = {"controllable", "taxes", "management_fee"}
BELOW_KEYS = {"reserves", "interest", "principal", "asset_management_fee"}


def _title(ws: Worksheet, text: str, subtitle: str) -> None:
    ws["A1"] = text
    ws["A1"].font = TITLE_FONT
    ws["A2"] = subtitle
    ws["A2"].font = NOTE_FONT


def _header(ws: Worksheet, row: int, labels: list[str]) -> None:
    for i, label in enumerate(labels):
        cell = ws.cell(row=row, column=1 + i, value=label)
        cell.font = HEADER_FONT
        cell.fill = HEAD_FILL
        cell.alignment = Alignment(horizontal="left" if i == 0 else "right")


def _put(
    ws: Worksheet, row: int, col: int, value: Any, fmt: str = MONEY, bold: bool = False
) -> None:
    cell = ws.cell(row=row, column=col, value=value)
    cell.number_format = fmt
    cell.font = TOTAL_FONT if bold else BODY_FONT
    if col > 1:
        cell.alignment = Alignment(horizontal="right")


def _write_inputs(ws: Worksheet, inputs: CopilotInputs, case: str) -> None:
    p, r, reno, cap, op, acq, loan, ex, eq = (
        inputs.property,
        inputs.revenue,
        inputs.renovation,
        inputs.capital,
        inputs.operating,
        inputs.acquisition,
        inputs.loan,
        inputs.exit,
        inputs.equity,
    )
    _title(
        ws, f"{p.name} · {case}", "Inputs. Percentages are fractions; rents are per unit per month."
    )
    _header(
        ws, 4, ["Floor plan", "Type", "Units", "SF", "Occupied", "In-place rent", "Market rent"]
    )
    row = 5
    for fp in p.floor_plans:
        for j, (v, fmt) in enumerate(
            [
                (fp.code, "@"),
                (fp.unit_type, "@"),
                (fp.units, "0"),
                (fp.sf, "#,##0"),
                (fp.occupied, "0"),
                (fp.in_place_rent, MONEY),
                (fp.market_rent, MONEY),
            ]
        ):
            _put(ws, row, 1 + j, v, fmt)
        row += 1
    row += 1
    rows: list[tuple[str, Any, str]] = [
        ("Purchase price", acq.purchase_price, MONEY),
        ("Asking price", acq.asking_price, MONEY),
        ("Closing date", acq.closing_date, DATE),
        ("Hold (months)", acq.hold_months, "0"),
        ("Closing costs", acq.closing_costs_pct, PCT2),
        ("Acquisition fee", acq.acquisition_fee_pct, PCT2),
        ("Market rent growth", r.market_rent_growth, PCT),
        ("Loss to lease burn (months)", r.loss_to_lease_burn_months, "0"),
        ("Steady loss to lease", r.steady_loss_to_lease, PCT),
        ("Vacancy", r.vacancy, PCT),
        ("Concessions", r.concessions, PCT2),
        ("Bad debt", r.bad_debt, PCT2),
        ("Other income per unit per month", r.other_income_per_unit_month, MONEY),
        ("Non-revenue units", p.non_revenue_units, "0"),
        ("Renovation units", reno.units, "0"),
        ("Renovation cost per unit", reno.cost_per_unit, MONEY),
        ("Renovation premium per month", reno.premium_per_month, MONEY),
        ("Renovation start month / duration", f"{reno.start_month} / {reno.duration_months}", "@"),
        ("Exterior and amenities", cap.exterior, MONEY),
        ("Deferred maintenance", cap.deferred_maintenance, MONEY),
        ("Capital contingency", cap.contingency_pct, PCT),
        ("Expense growth", op.expense_growth, PCT),
        ("Tax rate", op.tax_rate, PCT2),
        ("Taxes assessed at share of price", op.tax_assessed_share, PCT),
        ("Management fee (% of EGI)", op.management_fee_pct, PCT2),
        ("Reserves per unit", op.reserves_per_unit, MONEY),
        (
            "Loan LTV max / DSCR min / debt yield min",
            f"{loan.ltv_max:.0%} / {loan.dscr_min:.2f}x / {loan.debt_yield_min:.1%}",
            "@",
        ),
        ("Loan rate", loan.rate, PCT2),
        (
            "Interest only (months) / amortization (years) / term (months)",
            f"{loan.io_months} / {loan.amortization_years} / {loan.term_months}",
            "@",
        ),
        ("Loan fee", loan.fee_pct, PCT2),
        ("Exit cap rate", ex.cap_rate, PCT2),
        ("Sale costs", ex.sale_costs_pct, PCT2),
        ("LP share", eq.lp_share, PCT),
        ("Preferred return", eq.preferred_return, PCT),
        ("Asset management fee (% of equity)", eq.asset_management_fee_pct, PCT2),
    ]
    _header(ws, row, ["Input", "Value"])
    for i, (label, value, fmt) in enumerate(rows, start=row + 1):
        _put(ws, i, 1, label, "@")
        _put(ws, i, 2, value, fmt)
    row = row + len(rows) + 2
    _header(ws, row, ["Operating expense per unit, year 1", "$ / unit / yr"])
    for i, (line, amount) in enumerate(op.per_unit.items(), start=row + 1):
        _put(ws, i, 1, line, "@")
        _put(ws, i, 2, amount, MONEY)
    ws.column_dimensions["A"].width = 52
    for col in "BCDEFG":
        ws.column_dimensions[col].width = 16


def _write_pro_forma(ws: Worksheet, out: CopilotOutputs) -> dict[str, Any]:
    _title(
        ws,
        "Pro forma, monthly",
        "$ whole dollars. Line items are engine values; "
        "EGI, NOI, cash flow, and cumulative are formulas.",
    )
    labels = (
        ["Month", "Date", "Year"]
        + [label for label, _ in MONTHLY_LINES]
        + [
            "EGI",
            "Operating expenses",
            "NOI",
            "Cash flow after debt service",
            "Cumulative",
            "Loan balance",
        ]
    )
    header_row = 4
    _header(ws, header_row, labels)
    first = header_row + 1
    n = len(out.monthly)
    last = header_row + n
    col_of = {key: get_column_letter(4 + i) for i, (_, key) in enumerate(MONTHLY_LINES)}
    base = 4 + len(MONTHLY_LINES)
    egi_col, opex_col, noi_col, cf_col, cum_col, bal_col = (
        get_column_letter(base + i) for i in range(6)
    )
    rev_cols = [col_of[k] for _, k in MONTHLY_LINES if k in REVENUE_KEYS]
    opex_cols = [col_of[k] for _, k in MONTHLY_LINES if k in OPEX_KEYS]
    below_cols = [col_of[k] for _, k in MONTHLY_LINES if k in BELOW_KEYS]

    for i, m in enumerate(out.monthly):
        row = first + i
        _put(ws, row, 1, m.month, "0")
        _put(ws, row, 2, m.date, DATE)
        _put(ws, row, 3, m.year, "0")
        for j, (_, key) in enumerate(MONTHLY_LINES):
            _put(ws, row, 4 + j, getattr(m, key))
        _put(ws, row, base, "=" + "+".join(f"{c}{row}" for c in rev_cols))
        _put(ws, row, base + 1, "=" + "+".join(f"{c}{row}" for c in opex_cols))
        _put(ws, row, base + 2, f"={egi_col}{row}-{opex_col}{row}", bold=True)
        _put(
            ws,
            row,
            base + 3,
            f"={noi_col}{row}-" + "-".join(f"{c}{row}" for c in below_cols),
            bold=True,
        )
        _put(
            ws, row, base + 4, f"={cf_col}{row}" if i == 0 else f"={cum_col}{row - 1}+{cf_col}{row}"
        )
        _put(ws, row, base + 5, m.loan_balance)
    total_row = last + 1
    _put(ws, total_row, 1, "Total", "@", bold=True)
    for j in range(len(MONTHLY_LINES) + 4):
        col = get_column_letter(4 + j)
        _put(ws, total_row, 4 + j, f"=SUM({col}{first}:{col}{last})", bold=True)
    ws.freeze_panes = f"D{first}"
    for j in range(2, base + 6):
        ws.column_dimensions[get_column_letter(j)].width = 13
    return {
        "first": first,
        "last": last,
        "col_of": col_of,
        "egi": egi_col,
        "opex": opex_col,
        "noi": noi_col,
        "cf": cf_col,
        "year_col": "C",
        "n_years": len(out.annual),
    }


def _write_annual(ws: Worksheet, out: CopilotOutputs, refs: dict[str, Any]) -> dict[str, str]:
    _title(
        ws, "Annual roll-up", "Every cell is a SUMIF over the monthly Pro forma by project year."
    )
    years = refs["n_years"]
    _header(ws, 4, ["Line"] + [f"Year {y}" for y in range(1, years + 1)])
    lines = MONTHLY_LINES + [
        ("Effective gross income", "__egi"),
        ("Operating expenses", "__opex"),
        ("Net operating income", "__noi"),
        ("Cash flow after debt service", "__cf"),
    ]
    year_range = f"'Pro forma'!$C${refs['first']}:$C${refs['last']}"
    row_of: dict[str, int] = {}
    for i, (label, key) in enumerate(lines):
        row = 5 + i
        row_of[key] = row
        bold = key.startswith("__")
        _put(ws, row, 1, label, "@", bold=bold)
        col = {
            "__egi": refs["egi"],
            "__opex": refs["opex"],
            "__noi": refs["noi"],
            "__cf": refs["cf"],
        }.get(key) or refs["col_of"][key]
        for y in range(1, years + 1):
            rng = f"'Pro forma'!${col}${refs['first']}:${col}${refs['last']}"
            _put(ws, row, 1 + y, f"=SUMIF({year_range},{y},{rng})", bold=bold)
    dscr_row = 5 + len(lines)
    _put(ws, dscr_row, 1, "DSCR (NOI / debt service)", "@", bold=True)
    for y in range(1, years + 1):
        c = get_column_letter(1 + y)
        _put(
            ws,
            dscr_row,
            1 + y,
            f'=IFERROR({c}{row_of["__noi"]}/({c}{row_of["interest"]}+{c}{row_of["principal"]}),"n/a")',
            MULT,
            bold=True,
        )
    ws.column_dimensions["A"].width = 34
    for y in range(1, years + 1):
        ws.column_dimensions[get_column_letter(1 + y)].width = 14
    return {"noi_row": str(row_of["__noi"]), "dscr_row": str(dscr_row)}


def _write_summary(ws: Worksheet, out: CopilotOutputs, refs: dict[str, Any], case: str) -> None:
    s, su, ln, ex, r = out.summary, out.sources_uses, out.loan, out.exit, out.returns
    _title(
        ws,
        f"{out.summary.units} units · {case} · Summary",
        "Headline figures are formulas over the Pro forma and Annual sheets; "
        "engine values sit beside them for reference.",
    )
    _header(ws, 4, ["Headline", "Formula", "Engine value", "Basis"])
    noi1 = f"Annual!B{refs['noi_row']}"
    cf_range = f"'Pro forma'!{refs['cf']}{refs['first']}:{refs['cf']}{refs['last']}"
    headline: list[tuple[str, Any, Any, str, str]] = [
        ("Purchase price", su.purchase_price, su.purchase_price, MONEY, ""),
        ("Year 1 NOI", f"={noi1}", s.noi_year1, MONEY, "Sum of months 1 to 12"),
        ("Going-in cap rate", f"={noi1}/B5", s.going_in_cap, PCT2, "Year 1 NOI / purchase price"),
        ("Loan amount", su.loan, su.loan, MONEY, f"Binding constraint: {ln.binding}"),
        ("Debt yield", f"={noi1}/B8", s.debt_yield, PCT, "Year 1 NOI / loan"),
        ("DSCR, year 1", f"=Annual!B{refs['dscr_row']}", s.dscr_year1, MULT, "NOI / debt service"),
        ("Equity", su.equity, su.equity, MONEY, "Total uses less loan"),
        (
            "Cash flow to equity, hold",
            f"=SUM({cf_range})",
            sum(a.cash_flow for a in out.annual),
            MONEY,
            "After debt service, reserves and fees",
        ),
        ("Exit value", ex.gross_value, ex.gross_value, MONEY, f"Forward NOI / {ex.cap_rate:.2%}"),
        (
            "Net proceeds after debt",
            ex.net_after_debt,
            ex.net_after_debt,
            MONEY,
            "Exit value less sale costs and payoff",
        ),
        (
            "Equity multiple",
            "=(B12+B14)/B11",
            r.equity_multiple,
            MULT,
            "(Cash flow + net proceeds) / equity",
        ),
        (
            "Levered IRR (engine, monthly XIRR)",
            r.levered_irr,
            r.levered_irr,
            PCT,
            "Monthly flows to equity",
        ),
        (
            "LP IRR (engine, after waterfall)",
            r.lp_irr,
            r.lp_irr,
            PCT,
            "Preferred return, capital, promote tiers",
        ),
    ]
    for i, (label, formula, engine, fmt, basis) in enumerate(headline, start=5):
        _put(ws, i, 1, label, "@", bold=True)
        _put(ws, i, 2, formula, fmt, bold=True)
        _put(ws, i, 3, engine, fmt)
        _put(ws, i, 4, basis, "@")
    row = 5 + len(headline) + 1
    _header(ws, row, ["Sources and uses", "Amount", "% of total"])
    lines = [
        ("Purchase price", su.purchase_price),
        ("Closing costs", su.closing_costs),
        ("Loan fees", su.loan_fees),
        ("Acquisition fee", su.acquisition_fee),
        ("Capital budget", su.capital_budget),
        ("Total uses", su.total_uses),
        ("Loan", su.loan),
        ("Equity", su.equity),
        ("LP equity", su.lp_equity),
        ("GP equity", su.gp_equity),
    ]
    total_row = row + 6
    for i, (label, value) in enumerate(lines, start=row + 1):
        bold = label in ("Total uses", "Equity")
        _put(ws, i, 1, label, "@", bold=bold)
        _put(ws, i, 2, value, MONEY, bold=bold)
        _put(ws, i, 3, f"=IFERROR(B{i}/$B${total_row},0)", PCT)
    ws.column_dimensions["A"].width = 38
    ws.column_dimensions["B"].width = 18
    ws.column_dimensions["C"].width = 16
    ws.column_dimensions["D"].width = 44


def _write_waterfall(ws: Worksheet, out: CopilotOutputs) -> None:
    _title(
        ws,
        "Waterfall",
        "Cash to equity through each tier, and LP and GP distributions by year (engine values).",
    )
    _header(ws, 4, ["Tier", "Cash"])
    for i, (label, total) in enumerate(
        zip(out.waterfall.tier_labels, out.waterfall.tier_totals, strict=True), start=5
    ):
        _put(ws, i, 1, label, "@")
        _put(ws, i, 2, total)
    row = 5 + len(out.waterfall.tier_labels) + 1
    _header(ws, row, ["Year", "LP", "GP"])
    for y, (lp, gp) in enumerate(
        zip(out.waterfall.lp_by_year, out.waterfall.gp_by_year, strict=True), start=1
    ):
        _put(ws, row + y, 1, y, "0")
        _put(ws, row + y, 2, lp)
        _put(ws, row + y, 3, gp)
    r = out.returns
    end = row + len(out.waterfall.lp_by_year) + 2
    for i, (label, value, fmt) in enumerate(
        [
            ("LP IRR", r.lp_irr, PCT),
            ("LP multiple", r.lp_multiple, MULT),
            ("GP IRR", r.gp_irr, PCT),
            ("GP multiple", r.gp_multiple, MULT),
            ("Promote", r.promote, MONEY),
        ]
    ):
        _put(ws, end + i, 1, label, "@", bold=True)
        _put(ws, end + i, 2, value, fmt, bold=True)
    ws.column_dimensions["A"].width = 34
    ws.column_dimensions["B"].width = 16
    ws.column_dimensions["C"].width = 16


def export_workbook(inputs: CopilotInputs, out: CopilotOutputs, case: str) -> bytes:
    wb = Workbook()
    ws_inputs = wb.active
    assert isinstance(ws_inputs, Worksheet)
    ws_inputs.title = "Inputs"
    _write_inputs(ws_inputs, inputs, case)
    refs = _write_pro_forma(wb.create_sheet("Pro forma"), out)
    annual_refs = _write_annual(wb.create_sheet("Annual"), out, refs)
    _write_summary(wb.create_sheet("Summary"), out, {**refs, **annual_refs}, case)
    _write_waterfall(wb.create_sheet("Waterfall"), out)
    wb.move_sheet("Summary", offset=-2)
    wb.calculation.fullCalcOnLoad = True
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
