"""Multifamily Copilot routes: the Sawyer Bend deal, its cases, the underwrite screen, export."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from pydantic import BaseModel

from app.deals import DATA_DIR
from app.templating import render
from core.copilot.engine import run
from core.copilot.excel import export_workbook
from core.copilot.inputs import CopilotInputs
from core.copilot.sensitivity import StressRow, at_price, stress_table
from core.copilot.summary import CopilotOutputs

router = APIRouter(prefix="/copilot")


class Case(BaseModel):
    name: str
    inputs: CopilotInputs


def _load() -> tuple[dict[str, Any], list[Case], list[dict[str, str]]]:
    raw = json.loads((DATA_DIR / "sawyer_bend.json").read_text(encoding="utf-8"))
    cases = [
        Case(name=c["name"], inputs=CopilotInputs.model_validate(c["inputs"])) for c in raw["cases"]
    ]
    meta = {k: raw[k] for k in ("name", "status", "location", "facts")}
    return meta, cases, raw["assumptions"]


META, CASES, ASSUMPTIONS = _load()
STEPS = ["Screen", "Underwrite", "Recommend", "Monitor"]
THRESHOLD_IRR = 0.12
MONTHS_IN = 6  # the Monitor panel reports the second quarter after closing

COMPARE_METRICS: list[tuple[str, str, str]] = [
    ("Levered IRR", "levered_irr", "pct"),
    ("Unlevered IRR", "unlevered_irr", "pct"),
    ("Equity multiple", "equity_multiple", "mult"),
    ("LP IRR", "lp_irr", "pct"),
    ("Going-in cap", "going_in_cap", "pct2"),
    ("Year 1 NOI", "noi_year1", "money_m"),
    ("Loan", "loan_amount", "money_m"),
    ("LTV", "ltv", "pct"),
    ("Debt yield", "debt_yield", "pct"),
    ("DSCR, year 1", "dscr_year1", "mult"),
    ("Minimum DSCR", "min_dscr", "mult"),
    ("Exit value", "exit_value", "money_m"),
]


def case_named(name: str | None) -> Case:
    for case in CASES:
        if case.name == name:
            return case
    return CASES[0]


def pct(v: float | None, d: int = 1) -> str:
    return "n/a" if v is None else f"{v * 100:.{d}f}%"


def money_m(v: float, d: int = 1) -> str:
    return f"${v / 1e6:.{d}f}M"


def mult(v: float | None) -> str:
    return "n/a" if v is None else f"{v:.2f}×"


def draft_memo(out: CopilotOutputs, ask: CopilotOutputs, stress: list[StressRow]) -> dict[str, Any]:
    """The Recommend step, drafted from model figures alone.

    Build step 7 adds the language model for prose; every figure comes from the engine and
    would still.
    """
    s, r = out.summary, out.returns
    bid = money_m(s.purchase_price)
    ask_price = money_m(s.asking_price or 0)
    irr = r.levered_irr or 0.0
    cushion_bps = round((irr - THRESHOLD_IRR) * 10_000)
    clears = irr >= THRESHOLD_IRR
    growth = next((row for row in stress if row.label.startswith("Rent growth")), None)
    premium = next((row for row in stress if row.label.startswith("Renovation premium")), None)
    floor_row = min(stress, key=lambda row: row.min_dscr or 9.0) if stress else None
    breaches = [row for row in stress if not row.holds]
    threshold = f"{THRESHOLD_IRR:.0%}"

    if clears:
        recommendation = (
            f"Recommendation: bid {bid}, subject to a tax reassessment estimate from the "
            f"appraisal district and a scope walk of the unit interiors. "
            f"Do not pursue at the {ask_price} ask."
        )
    else:
        recommendation = (
            f"Recommendation: pass at {bid}. The deal returns {pct(irr)} levered against a "
            f"{threshold} threshold; revisit if the price or the renovation premium moves."
        )
    direction = "above" if clears else "below"
    body = [
        (
            f"At {bid} the deal returns a {pct(irr)} levered IRR and a "
            f"{r.equity_multiple:.2f}× multiple, {abs(cushion_bps):,} bps {direction} the "
            f"{threshold} threshold, with a year 1 DSCR of {mult(s.dscr_year1)} against a "
            f"{mult(out.loan.covenant_dscr)} covenant."
        ),
        f"At the {ask_price} ask the levered IRR falls to {pct(ask.returns.levered_irr)}.",
    ]
    if growth:
        body.append(
            "Returns are most sensitive to market rent growth: at 1% the IRR is "
            f"{pct(growth.levered_irr)}."
        )
    if premium:
        body.append(
            f"The renovation premium carries the value-add thesis: at "
            f"{premium.label.split(' ')[-1]} rather than ${out.renovation.premium_per_month:,} "
            f"the IRR is {pct(premium.levered_irr)}."
        )
    if breaches:
        body.append(
            f"The covenant breaks under {breaches[0].label.lower()}, where DSCR falls to "
            f"{mult(breaches[0].min_dscr)}."
        )
    elif floor_row is not None:
        body.append(
            f"No single stress breaches the covenant; the floor is {mult(floor_row.min_dscr)} "
            f"under {floor_row.label.lower()}. The risk in this deal is to equity return, "
            "not to the debt."
        )
    cannot = [
        "Whether the appraisal district reassesses to the purchase price (taxes are "
        f"{pct(s.taxes_share_of_opex, 0)} of operating expenses).",
        f"Whether the ${out.renovation.premium_per_month:,} premium holds once "
        f"{out.renovation.units} more renovated units reach the submarket.",
        "The condition of roofs and HVAC beyond the property condition sample.",
        f"The seller's appetite for a bid {pct(s.discount_to_ask)} below ask.",
    ]
    return {"recommendation": recommendation, "body": body, "cannot": cannot, "clears": clears}


def _row(
    test: str, covenant: str, underwritten: str, actual: str, cushion: str, status: str, ok: bool
) -> dict[str, Any]:
    return {
        "test": test,
        "covenant": covenant,
        "underwritten": underwritten,
        "actual": actual,
        "cushion": cushion,
        "status": status,
        "ok": ok,
    }


def monitor_rows(out: CopilotOutputs) -> list[dict[str, Any]]:
    """A synthetic quarter of actuals, two quarters after closing, tested against underwriting."""
    s, ln, reno = out.summary, out.loan, out.renovation
    dscr_uw = s.dscr_year1 or 0.0
    dscr_actual = dscr_uw + 0.03
    dy_actual = s.debt_yield + 0.002
    occupancy_uw, occupancy_actual, occupancy_min = 0.94, 0.948, 0.85
    months_active = max(0, MONTHS_IN - reno.start_month + 1)
    planned = round(min(reno.units, reno.pace_per_month * months_active))
    actual_units = max(0, planned - 3)
    io_left = ln.io_months - MONTHS_IN
    return [
        _row(
            "DSCR",
            mult(ln.covenant_dscr),
            mult(dscr_uw),
            mult(dscr_actual),
            mult(dscr_actual - ln.covenant_dscr),
            "In compliance",
            dscr_actual >= ln.covenant_dscr,
        ),
        _row(
            "Debt yield",
            "7.5%",
            pct(s.debt_yield),
            pct(dy_actual),
            f"{round((dy_actual - 0.075) * 10_000)} bps",
            "In compliance",
            dy_actual >= 0.075,
        ),
        _row(
            "Occupancy",
            pct(occupancy_min),
            pct(occupancy_uw),
            pct(occupancy_actual),
            f"{round((occupancy_actual - occupancy_min) * 10_000):,} bps",
            "In compliance",
            True,
        ),
        _row(
            "Renovations completed",
            "",
            f"{planned} of {reno.units}",
            f"{actual_units} of {reno.units}",
            f"({planned - actual_units}) units",
            "Behind plan",
            False,
        ),
        _row(
            "Interest-only expiry",
            ln.io_expiry.strftime("%B %Y"),
            "",
            f"{io_left} months",
            "",
            f"Amortization begins in {io_left} months",
            True,
        ),
        _row(
            "Loan maturity",
            ln.maturity.strftime("%B %Y"),
            "",
            f"{ln.term_months - MONTHS_IN} months",
            "",
            "Refinance review at 60 months",
            True,
        ),
    ]


def compare_rows(outputs: dict[str, CopilotOutputs]) -> list[tuple[str, list[str]]]:
    rows: list[tuple[str, list[str]]] = []
    for label, key, fmt in COMPARE_METRICS:
        values: list[str] = []
        for out in outputs.values():
            v: Any = out.loan.amount if key == "loan_amount" else getattr(out.summary, key)
            if fmt == "pct":
                values.append(pct(v))
            elif fmt == "pct2":
                values.append(pct(v, 2))
            elif fmt == "mult":
                values.append(mult(v))
            else:
                values.append(money_m(v))
        rows.append((label, values))
    return rows


@router.get("", response_class=HTMLResponse)
async def underwrite(request: Request, case: str | None = None) -> Response:
    current = case_named(case)
    out = run(current.inputs)
    acq = current.inputs.acquisition
    ask = run(at_price(current.inputs, acq.asking_price or acq.purchase_price))
    stress = stress_table(current.inputs)
    outputs = {c.name: run(c.inputs) for c in CASES}
    return render(
        request,
        "copilot/underwrite.html",
        meta=META,
        cases=[c.name for c in CASES],
        case=current.name,
        steps=STEPS,
        active_step=2,
        out=out,
        ask=ask,
        stress=stress,
        assumptions=ASSUMPTIONS,
        memo=draft_memo(out, ask, stress),
        monitor=monitor_rows(out),
        compare=compare_rows(outputs),
        compare_names=list(outputs),
        threshold=THRESHOLD_IRR,
        query=f"?case={current.name}",
    )


@router.get("/export.xlsx")
async def export(case: str | None = None) -> Response:
    current = case_named(case)
    workbook = export_workbook(current.inputs, run(current.inputs), current.name)
    filename = f"sawyer-bend-{current.name.lower()}.xlsx"
    return StreamingResponse(
        iter([workbook]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
