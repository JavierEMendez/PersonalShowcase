"""The land deal's investment committee memo: figures from the engine, sentences from a template.

The bid rule is an unlevered IRR floor. The recommended land price is solved from it, the
highest price per acre at which the project's unlevered IRR still reaches the floor, so the memo
adjusts the number rather than only grading the underwritten price. The template writes with
placeholders and the code fills every figure, the same construction as the multifamily memo; a
second pass confirms every number in the finished text is a facts value.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from core.copilot.memo import TOKEN, Memo, check_memo
from core.copy_rules import violations
from core.underwriting.inputs import DealInputs
from core.underwriting.sensitivity import SensitivityGrid
from core.underwriting.summary import Outputs

IRR_FLOOR = 0.15
# A recommended price this far below the underwritten price is a pass, not a bid.
MAX_DISCOUNT_TO_PRICE = 0.25

Verdict = Literal["bid", "bid_lower", "pass"]


def _pct(v: float | None, d: int = 1) -> str:
    return "n/a" if v is None else f"{v * 100:.{d}f}%"


def _money_m(v: float, d: int = 1) -> str:
    return f"${v / 1e6:.{d}f}M"


def _money(v: float) -> str:
    return f"${v:,.0f}"


class LandFacts(BaseModel):
    scenario: str
    verdict: Verdict
    figures: dict[str, str]


def build_land_facts(
    inputs: DealInputs,
    out: Outputs,
    grid: SensitivityGrid,
    scenario: str,
    floor: float = IRR_FLOOR,
    max_price: float | None = None,
    at_max: Outputs | None = None,
) -> LandFacts:
    s, t = out.summary, inputs.tract
    irr = s.unlevered_irr or 0.0
    price = t.purchase_price_per_acre
    if irr >= floor:
        verdict: Verdict = "bid"
    elif max_price is not None and max_price >= price * (1 - MAX_DISCOUNT_TO_PRICE):
        verdict = "bid_lower"
    else:
        verdict = "pass"
    land_total = t.gross_acreage * price
    values = [c.value for row in grid.rows for c in row.cells if c.value is not None]
    figures: dict[str, str] = {
        "price_per_acre": _money(price),
        "land_total": _money_m(land_total),
        "gross_acres": f"{t.gross_acreage:,.0f}",
        "developable_acres": f"{s.developable_acres:,.0f}",
        "lots": f"{s.total_lots:,}",
        "irr": _pct(irr),
        "floor": f"{floor:.0%}",
        "irr_vs_floor": f"{abs(round((irr - floor) * 10_000)):,} bps "
        + ("above" if irr >= floor else "short of"),
        "total_revenue": _money_m(s.total_revenue),
        "gross_costs": _money_m(s.gross_costs),
        "gross_margin": _money_m(s.gross_margin),
        "gross_margin_pct": _pct(s.gross_margin_of_revenue),
        "net_margin": _money_m(s.net_margin),
        "net_margin_pct": _pct(s.net_margin_of_revenue),
        "return_on_cost": _pct(s.return_on_cost),
        "peak_cash": _money_m(s.peak_cash_need),
        "peak_month": f"{s.peak_cash_month}",
        "project_years": f"{s.project_length_years:.1f}",
        "breakeven_year": f"{s.breakeven_year}" if s.breakeven_year else "beyond the hold",
        "lot_sales": _money_m(out.revenue.lot_sales),
        "bond_proceeds": _money_m(out.revenue.mud + out.revenue.wcid),
        "bond_share": _pct((out.revenue.mud + out.revenue.wcid) / s.total_revenue),
        "sections": _money_m(out.costs.sections),
        "sections_share": _pct(out.costs.sections / s.gross_costs),
        "land_share": _pct(out.costs.land / s.gross_costs),
        "grid_low": _pct(min(values)) if values else "n/a",
        "grid_high": _pct(max(values)) if values else "n/a",
        "row_axis": grid.row_axis.replace("_", " "),
        "col_axis": grid.col_axis.replace("_", " "),
    }
    if max_price is not None and at_max is not None:
        figures["max_price_per_acre"] = _money(max_price)
        figures["max_land_total"] = _money_m(t.gross_acreage * max_price)
        change = max_price / price - 1
        figures["max_price_change"] = f"{abs(change) * 100:.1f}% " + (
            "above" if change >= 0 else "below"
        )
        figures["irr_at_max"] = _pct(at_max.summary.unlevered_irr)
        figures["net_margin_at_max"] = _money_m(at_max.summary.net_margin)
    return LandFacts(scenario=scenario, verdict=verdict, figures=figures)


def land_template(facts: LandFacts) -> tuple[str, list[str], list[str]]:
    f = facts.figures
    has_max = "max_price_per_acre" in f
    if facts.verdict == "bid":
        recommendation = (
            "Recommendation: bid {price_per_acre} per acre ({land_total} for {gross_acres} acres). "
            "The unlevered IRR of {irr} is {irr_vs_floor} the {floor} floor"
            + (
                ", and the land price could rise to {max_price_per_acre} per acre before the "
                "floor binds"
                if has_max
                else ""
            )
            + "."
        )
    elif facts.verdict == "bid_lower":
        recommendation = (
            "Recommendation: bid no more than {max_price_per_acre} per acre ({max_land_total}), "
            "{max_price_change} the underwritten {price_per_acre}, the price at which the "
            "unlevered IRR reaches the {floor} floor. At {price_per_acre} the IRR is {irr}, "
            "{irr_vs_floor} the floor."
        )
    elif has_max:
        recommendation = (
            "Recommendation: pass at {price_per_acre} per acre. The unlevered IRR of {irr} is "
            "{irr_vs_floor} the {floor} floor, and the floor is reached only at "
            "{max_price_per_acre} per acre, {max_price_change} the underwritten price."
        )
    else:
        recommendation = (
            "Recommendation: pass at {price_per_acre} per acre. The unlevered IRR of {irr} is "
            "{irr_vs_floor} the {floor} floor and no land price near the underwritten one "
            "reaches it."
        )
    body = [
        "The project delivers {lots} lots on {developable_acres} developable acres over "
        "{project_years} years, with {total_revenue} of revenue against {gross_costs} of gross "
        "costs: a gross margin of {gross_margin} ({gross_margin_pct} of revenue) and a net margin "
        "of {net_margin} ({net_margin_pct}) after overhead and fees.",
        "Return on cost is {return_on_cost}. Peak cash need is {peak_cash} in month {peak_month}, "
        "with breakeven in year {breakeven_year}.",
        "Lot sales are {lot_sales} of revenue; district bond proceeds add {bond_proceeds} "
        "({bond_share} of revenue) and depend on assessed value building on schedule.",
        "Section development is {sections} ({sections_share} of gross costs) and land is "
        "{land_share}; the sensitivity grid on {col_axis} and {row_axis} runs from {grid_low} "
        "to {grid_high}.",
    ]
    if has_max:
        body.append(
            "At {max_price_per_acre} per acre the unlevered IRR is {irr_at_max} and the net "
            "margin {net_margin_at_max}."
        )
    cannot = [
        "Whether lot prices per front foot hold at the underwritten pace once the first sections "
        "deliver; the grid shows what one step in either costs.",
        "Whether the MUD and WCID reimbursements arrive on the assumed bond schedule; "
        "{bond_share} of revenue depends on it.",
        "Section development cost per front foot before the first bids are in.",
        "The seller's appetite for the price and takedown schedule underwritten.",
    ]
    return recommendation, body, cannot


def _fill(text: str, facts: LandFacts) -> str:
    return TOKEN.sub(lambda m: facts.figures[m.group(1)], text)


def write_land_memo(facts: LandFacts) -> Memo:
    recommendation, body, cannot = land_template(facts)
    for text in [recommendation, *body, *cannot]:
        for token in TOKEN.findall(text):
            assert token in facts.figures, token
    memo = Memo(
        case=facts.scenario,
        recommendation=_fill(recommendation, facts),
        body=[_fill(s, facts) for s in body],
        cannot=[_fill(s, facts) for s in cannot],
        writer="template",
    )
    problems = check_memo(
        memo,
        _AsFacts(figures=facts.figures),  # type: ignore[arg-type]
    )
    problems += [f"banned: {label}" for label in violations(memo.markdown("x"))]
    memo.problems = sorted(set(problems))
    return memo


class _AsFacts(BaseModel):
    """The slice of MemoFacts that check_memo reads."""

    figures: dict[str, str]
