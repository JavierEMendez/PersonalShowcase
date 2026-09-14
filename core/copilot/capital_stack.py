"""Sources and uses at closing. Capital is funded at close and held for the program."""

from __future__ import annotations

from dataclasses import dataclass

from core.copilot.inputs import CopilotInputs


@dataclass
class CapitalStack:
    purchase_price: float
    closing_costs: float
    loan_fees: float
    acquisition_fee: float
    renovation_budget: float
    other_capital: float
    construction_management_fee: float
    contingency: float
    capital_budget: float
    total_uses: float
    loan: float
    equity: float
    lp_equity: float
    gp_equity: float


def build_capital_stack(inputs: CopilotInputs, loan_amount: float) -> CapitalStack:
    acq, cap, reno, eq = inputs.acquisition, inputs.capital, inputs.renovation, inputs.equity
    renovation_budget = reno.units * reno.cost_per_unit
    other_capital = cap.exterior + cap.deferred_maintenance + cap.marketing
    base = renovation_budget + other_capital
    cm_fee = base * cap.construction_management_fee_pct
    contingency = (base + cm_fee) * cap.contingency_pct
    capital_budget = base + cm_fee + contingency
    closing_costs = acq.purchase_price * acq.closing_costs_pct
    loan_fees = loan_amount * inputs.loan.fee_pct
    acquisition_fee = acq.purchase_price * acq.acquisition_fee_pct
    total_uses = acq.purchase_price + closing_costs + loan_fees + acquisition_fee + capital_budget
    equity = total_uses - loan_amount
    return CapitalStack(
        purchase_price=acq.purchase_price,
        closing_costs=closing_costs,
        loan_fees=loan_fees,
        acquisition_fee=acquisition_fee,
        renovation_budget=renovation_budget,
        other_capital=other_capital,
        construction_management_fee=cm_fee,
        contingency=contingency,
        capital_budget=capital_budget,
        total_uses=total_uses,
        loan=loan_amount,
        equity=equity,
        lp_equity=equity * eq.lp_share,
        gp_equity=equity * (1 - eq.lp_share),
    )
