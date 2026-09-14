"""Land cost: purchase price, closing costs, and escalated takedowns."""

from __future__ import annotations

from pydantic import BaseModel

from core.underwriting.inputs import Takedown, Tract


class LandTakedown(BaseModel):
    period: int
    pct: float
    purchase_price: float
    closing_costs: float
    total: float


class Land(BaseModel):
    purchase_price: float
    closing_costs: float
    total: float
    takedowns: list[LandTakedown]
    takedown_pct_check: float
    escalated_purchase: float
    escalated_closing: float
    escalated_total: float


def compute_land(tract: Tract, takedowns: list[Takedown]) -> Land:
    purchase_price = tract.purchase_price_per_acre * tract.gross_acreage
    closing_costs = tract.closing_costs_pct * purchase_price

    # The first take (period 0) is paid at the contract price. Later takes escalate the
    # purchase price by (1 + escalator) ^ (period / 12). Closing costs never escalate.
    valid = [td for td in takedowns if td.pct > 0]
    if not valid:
        valid = [Takedown(period=0, pct=1.0)]

    rows: list[LandTakedown] = []
    for i, td in enumerate(valid):
        if td.period == 0 or i == 0:
            purchase = purchase_price * td.pct
        else:
            purchase = purchase_price * td.pct * (1 + tract.land_escalator) ** (td.period / 12)
        closing = closing_costs * td.pct
        rows.append(
            LandTakedown(
                period=td.period,
                pct=td.pct,
                purchase_price=purchase,
                closing_costs=closing,
                total=purchase + closing,
            )
        )

    escalated_purchase = sum(r.purchase_price for r in rows)
    escalated_closing = sum(r.closing_costs for r in rows)
    return Land(
        purchase_price=purchase_price,
        closing_costs=closing_costs,
        total=purchase_price + closing_costs,
        takedowns=rows,
        takedown_pct_check=round(sum(r.pct for r in rows), 6),
        escalated_purchase=escalated_purchase,
        escalated_closing=escalated_closing,
        escalated_total=escalated_purchase + escalated_closing,
    )
