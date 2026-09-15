"""The valuation range: three prices solved from LP IRR targets, with the KPIs at each.

Max is the price at which the levered LP IRR (after debt service and the waterfall) is 13%: the
most the deal can bear. Mid is the price at 15%: the price to open at. Low is the lower of the
price at 17% and 20% below the ask: the price at which the deal is bought with confidence. The
verdict reads off where the ask sits against the range. Everything here is engine output; the
memo and the page format it.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from core.copilot.engine import run
from core.copilot.inputs import CopilotInputs
from core.copilot.sensitivity import at_price, max_price_for_lp_irr
from core.copilot.summary import CopilotOutputs

LP_TARGETS: dict[str, float] = {"max": 0.13, "mid": 0.15, "low": 0.17}
LOW_DISCOUNT_CAP = 0.20
SEARCH_LOW, SEARCH_HIGH = 0.4, 1.3  # share of the underwritten price the solver searches

Verdict = Literal["pursue", "engage", "pass"]


class PricePoint(BaseModel):
    label: str  # "Low", "Mid", "Max", "Ask", "Underwritten"
    price: float
    basis: str  # what set the price: "LP IRR 15%", "20% below ask", "seller's ask"
    per_unit: float
    discount_to_ask: float
    going_in_cap: float
    levered_irr: float | None
    lp_irr: float | None
    equity_multiple: float
    dscr_year1: float | None
    ltv: float
    loan: float
    equity: float


class ValuationRange(BaseModel):
    ask: float
    underwritten: PricePoint
    at_ask: PricePoint
    low: PricePoint | None
    mid: PricePoint | None
    max: PricePoint | None
    verdict: Verdict

    @property
    def points(self) -> list[PricePoint]:
        return [p for p in (self.low, self.mid, self.max) if p is not None]


def price_point(inputs: CopilotInputs, label: str, price: float, basis: str) -> PricePoint:
    out: CopilotOutputs = run(at_price(inputs, price))
    ask = inputs.acquisition.asking_price or inputs.acquisition.purchase_price
    s, r = out.summary, out.returns
    return PricePoint(
        label=label,
        price=price,
        basis=basis,
        per_unit=price / s.units,
        discount_to_ask=1 - price / ask,
        going_in_cap=s.going_in_cap,
        levered_irr=r.levered_irr,
        lp_irr=r.lp_irr,
        equity_multiple=r.equity_multiple,
        dscr_year1=s.dscr_year1,
        ltv=s.ltv,
        loan=float(out.loan.amount),
        equity=float(out.sources_uses.equity),
    )


def valuation_range(inputs: CopilotInputs) -> ValuationRange:
    ask = inputs.acquisition.asking_price or inputs.acquisition.purchase_price
    solved: dict[str, float | None] = {
        key: max_price_for_lp_irr(inputs, target, SEARCH_LOW, SEARCH_HIGH)
        for key, target in LP_TARGETS.items()
    }
    points: dict[str, PricePoint | None] = {}
    for key in ("max", "mid"):
        price = solved[key]
        points[key] = (
            price_point(inputs, key.title(), price, f"LP IRR {LP_TARGETS[key]:.0%}")
            if price is not None
            else None
        )
    cap = ask * (1 - LOW_DISCOUNT_CAP)
    p17 = solved["low"]
    if p17 is not None and p17 < cap:
        points["low"] = price_point(inputs, "Low", p17, f"LP IRR {LP_TARGETS['low']:.0%}")
    else:
        points["low"] = price_point(inputs, "Low", cap, f"{LOW_DISCOUNT_CAP:.0%} below ask")
    max_point = points["max"]
    if max_point is None:
        verdict: Verdict = "pass"
    elif ask <= max_point.price:
        verdict = "pursue"
    else:
        verdict = "engage"
    return ValuationRange(
        ask=ask,
        underwritten=price_point(
            inputs, "Underwritten", inputs.acquisition.purchase_price, "underwritten price"
        ),
        at_ask=price_point(inputs, "Ask", ask, "seller's ask"),
        low=points["low"],
        mid=points["mid"],
        max=max_point,
        verdict=verdict,
    )
