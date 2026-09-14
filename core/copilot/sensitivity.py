"""What breaks it: single-variable stresses with the base loan held fixed."""

from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel

from core.copilot.engine import run
from core.copilot.inputs import CopilotInputs


class StressRow(BaseModel):
    label: str
    levered_irr: float | None
    dscr_year1: float | None
    min_dscr: float | None
    holds: bool


Mutation = Callable[[CopilotInputs], None]


def _exit_cap(bps: int) -> Mutation:
    def apply(i: CopilotInputs) -> None:
        i.exit.cap_rate += bps / 10_000

    return apply


def _vacancy(rate: float) -> Mutation:
    def apply(i: CopilotInputs) -> None:
        i.revenue.vacancy = rate

    return apply


def _premium(amount: float) -> Mutation:
    def apply(i: CopilotInputs) -> None:
        i.renovation.premium_per_month = amount

    return apply


def _rate(bps: int) -> Mutation:
    def apply(i: CopilotInputs) -> None:
        i.loan.rate += bps / 10_000

    return apply


def _rent_growth(rate: float) -> Mutation:
    def apply(i: CopilotInputs) -> None:
        i.revenue.market_rent_growth = rate

    return apply


def _taxes_full() -> Mutation:
    def apply(i: CopilotInputs) -> None:
        i.operating.tax_assessed_share = 1.0

    return apply


def default_stresses(inputs: CopilotInputs) -> list[tuple[str, Mutation]]:
    cap = inputs.exit.cap_rate + 0.0075
    rate = inputs.loan.rate + 0.0075
    half_premium = int(inputs.renovation.premium_per_month / 2 / 5 + 0.5) * 5
    return [
        (f"Exit cap {cap * 100:.2f}%", _exit_cap(75)),
        ("Occupancy 90%", _vacancy(0.10)),
        (f"Renovation premium ${half_premium:,.0f}", _premium(half_premium)),
        (f"Loan rate {rate * 100:.2f}%", _rate(75)),
        ("Rent growth 1%", _rent_growth(0.01)),
        ("Taxes reassessed to 100% of price", _taxes_full()),
    ]


def stress_table(
    inputs: CopilotInputs, stresses: list[tuple[str, Mutation]] | None = None
) -> list[StressRow]:
    base_loan = run(inputs).loan.amount
    rows: list[StressRow] = []
    for label, mutate in stresses or default_stresses(inputs):
        stressed = inputs.model_copy(deep=True)
        mutate(stressed)
        stressed.loan.amount_override = float(base_loan)
        out = run(stressed)
        rows.append(
            StressRow(
                label=label,
                levered_irr=out.summary.levered_irr,
                dscr_year1=out.summary.dscr_year1,
                min_dscr=out.summary.min_dscr,
                holds=out.summary.covenant_holds,
            )
        )
    return rows


def at_price(inputs: CopilotInputs, price: float) -> CopilotInputs:
    """The same deal bought at a different price; the loan re-sizes on the constraints."""
    priced = inputs.model_copy(deep=True)
    priced.acquisition.purchase_price = price
    priced.loan.amount_override = None
    return priced
