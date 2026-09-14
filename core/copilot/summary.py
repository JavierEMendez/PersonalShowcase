"""Outputs of the multifamily model: annual pro forma, capital stack, debt, exit, returns."""

from __future__ import annotations

import datetime

from pydantic import BaseModel


class FloorPlanRow(BaseModel):
    code: str
    unit_type: str
    units: int
    sf: float
    occupied: int
    in_place_rent: float
    market_rent: float


class AnnualRow(BaseModel):
    year: int
    gpr: int
    loss_to_lease: int
    renovation_premium: int
    renovation_vacancy: int
    vacancy: int
    concessions: int
    non_revenue: int
    bad_debt: int
    net_rental: int
    other_income: int
    egi: int
    controllable: int
    taxes: int
    management_fee: int
    opex: int
    noi: int
    reserves: int
    debt_service: int
    asset_management_fee: int
    cash_flow: int
    dscr: float | None
    cash_on_cash: float


class MonthlyRow(BaseModel):
    month: int
    date: datetime.date
    year: int
    gpr: int
    loss_to_lease: int
    renovation_premium: int
    renovation_vacancy: int
    vacancy: int
    concessions: int
    non_revenue: int
    bad_debt: int
    other_income: int
    egi: int
    controllable: int
    taxes: int
    management_fee: int
    noi: int
    reserves: int
    interest: int
    principal: int
    asset_management_fee: int
    cash_flow: int
    loan_balance: int
    renovation_spend: int
    units_completed: int


class SourcesUses(BaseModel):
    purchase_price: int
    closing_costs: int
    loan_fees: int
    acquisition_fee: int
    renovation_budget: int
    other_capital: int
    construction_management_fee: int
    contingency: int
    capital_budget: int
    total_uses: int
    loan: int
    equity: int
    lp_equity: int
    gp_equity: int


class LoanSummary(BaseModel):
    amount: int
    ltv: float
    binding: str
    by_ltv: int
    by_dscr: int
    by_debt_yield: int
    rate: float
    io_months: int
    amortization_years: int
    term_months: int
    maturity: datetime.date
    io_expiry: datetime.date
    annual_debt_service_io: int
    annual_debt_service_amortizing: int
    debt_yield: float
    payoff: int
    covenant_dscr: float


class ExitSummary(BaseModel):
    month: int
    date: datetime.date
    forward_noi: int
    cap_rate: float
    gross_value: int
    value_per_unit: int
    sale_costs: int
    net_proceeds: int
    loan_payoff: int
    net_after_debt: int


class Returns(BaseModel):
    unlevered_irr: float | None
    levered_irr: float | None
    equity_multiple: float
    lp_irr: float | None
    lp_multiple: float
    gp_irr: float | None
    gp_multiple: float
    promote: int
    profit: int
    average_cash_on_cash: float


class WaterfallSummary(BaseModel):
    tier_labels: list[str]
    tier_totals: list[int]
    lp_by_year: list[int]
    gp_by_year: list[int]


class RenovationSummary(BaseModel):
    units: int
    cost_per_unit: int
    premium_per_month: int
    return_on_cost: float
    start_month: int
    end_month: int
    pace_per_month: float
    total_cost: int


class Summary(BaseModel):
    units: int
    occupied: int
    occupancy: float
    rentable_sf: int
    avg_in_place_rent: int
    avg_market_rent: int
    loss_to_lease_pct: float
    purchase_price: int
    asking_price: int | None
    discount_to_ask: float | None
    price_per_unit: int
    price_per_sf: int
    going_in_cap: float
    cap_at_ask: float | None
    noi_year1: int
    debt_yield: float
    ltv: float
    dscr_year1: float | None
    min_dscr: float | None
    covenant_holds: bool
    levered_irr: float | None
    unlevered_irr: float | None
    equity_multiple: float
    lp_irr: float | None
    exit_value: int
    hold_months: int
    opex_per_unit: int
    taxes_share_of_opex: float


class CopilotOutputs(BaseModel):
    floor_plans: list[FloorPlanRow]
    summary: Summary
    sources_uses: SourcesUses
    loan: LoanSummary
    exit: ExitSummary
    returns: Returns
    renovation: RenovationSummary
    waterfall: WaterfallSummary
    operating_per_unit: dict[str, int]
    annual: list[AnnualRow]
    monthly: list[MonthlyRow]
