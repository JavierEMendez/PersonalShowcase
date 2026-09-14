"""Monthly operations: revenue deductions, other income, expenses, taxes, and NOI."""

from __future__ import annotations

from dataclasses import dataclass, field

from core.copilot.inputs import CopilotInputs
from core.copilot.renovation import RenovationProgram
from core.copilot.rent_roll import RentRoll
from core.copilot.schedule import monthly_growth, yearly_step, zeros


@dataclass
class Operations:
    gpr: list[float]
    loss_to_lease: list[float]
    renovation_premium: list[float]
    renovation_vacancy: list[float]
    vacancy: list[float]
    concessions: list[float]
    non_revenue: list[float]
    bad_debt: list[float]
    net_rental: list[float]
    other_income: list[float]
    egi: list[float]
    controllable: dict[str, list[float]]
    controllable_total: list[float]
    taxes: list[float]
    management_fee: list[float]
    opex: list[float]
    noi: list[float]
    reserves: list[float]
    months: int = 0
    lines: list[str] = field(default_factory=list)


def build_operations(
    inputs: CopilotInputs, months: int, roll: RentRoll, reno: RenovationProgram
) -> Operations:
    prop, rev, op = inputs.property, inputs.revenue, inputs.operating
    units = prop.units
    price = inputs.acquisition.purchase_price
    lines = list(op.per_unit)
    ops = Operations(
        gpr=zeros(months),
        loss_to_lease=zeros(months),
        renovation_premium=zeros(months),
        renovation_vacancy=zeros(months),
        vacancy=zeros(months),
        concessions=zeros(months),
        non_revenue=zeros(months),
        bad_debt=zeros(months),
        net_rental=zeros(months),
        other_income=zeros(months),
        egi=zeros(months),
        controllable={line: zeros(months) for line in lines},
        controllable_total=zeros(months),
        taxes=zeros(months),
        management_fee=zeros(months),
        opex=zeros(months),
        noi=zeros(months),
        reserves=zeros(months),
        months=months,
        lines=lines,
    )
    for m in range(1, months + 1):
        gpr = roll.gpr[m]
        ltl = roll.loss_to_lease[m]
        premium = reno.premium[m]
        market_rent = roll.avg_market_rent_by_month[m]
        # Economic deductions apply to potential rent after loss to lease and premiums.
        potential = gpr + ltl + premium
        reno_vacancy = -reno.offline[m] * market_rent
        vacancy = -potential * rev.vacancy
        concessions = -potential * rev.concessions
        non_revenue = -prop.non_revenue_units * market_rent
        bad_debt = -potential * rev.bad_debt
        net_rental = potential + reno_vacancy + vacancy + concessions + non_revenue + bad_debt
        other = units * rev.other_income_per_unit_month * monthly_growth(rev.other_income_growth, m)
        egi = net_rental + other

        step = yearly_step(op.expense_growth, m)
        controllable_total = 0.0
        for line in lines:
            amount = op.per_unit[line] * units / 12 * step
            ops.controllable[line][m] = amount
            controllable_total += amount
        # Taxes reassess to the purchase price at closing, then grow.
        taxes = price * op.tax_assessed_share * op.tax_rate / 12 * yearly_step(op.tax_growth, m)
        management = egi * op.management_fee_pct
        opex = controllable_total + taxes + management

        ops.gpr[m] = gpr
        ops.loss_to_lease[m] = ltl
        ops.renovation_premium[m] = premium
        ops.renovation_vacancy[m] = reno_vacancy
        ops.vacancy[m] = vacancy
        ops.concessions[m] = concessions
        ops.non_revenue[m] = non_revenue
        ops.bad_debt[m] = bad_debt
        ops.net_rental[m] = net_rental
        ops.other_income[m] = other
        ops.egi[m] = egi
        ops.controllable_total[m] = controllable_total
        ops.taxes[m] = taxes
        ops.management_fee[m] = management
        ops.opex[m] = opex
        ops.noi[m] = egi - opex
        ops.reserves[m] = op.reserves_per_unit * units / 12 * step
    return ops
