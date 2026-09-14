"""Typed inputs for the multifamily acquisition model.

Percentages are fractions. Rents are dollars per unit per month. Months are 1-based project
months; month 0 is closing. The model runs monthly and reports annually.
"""

from __future__ import annotations

import datetime

from pydantic import BaseModel, Field


class FloorPlan(BaseModel):
    code: str
    unit_type: str
    units: int
    sf: float
    occupied: int
    in_place_rent: float
    market_rent: float


class Property(BaseModel):
    name: str = "Property"
    location: str = ""
    year_built: int | None = None
    floor_plans: list[FloorPlan] = Field(default_factory=list)
    non_revenue_units: int = 0

    @property
    def units(self) -> int:
        return sum(fp.units for fp in self.floor_plans)

    @property
    def occupied(self) -> int:
        return sum(fp.occupied for fp in self.floor_plans)

    @property
    def rentable_sf(self) -> float:
        return sum(fp.units * fp.sf for fp in self.floor_plans)


class RevenueAssumptions(BaseModel):
    market_rent_growth: float = 0.03
    # Months to burn the in-place gap to market through lease rollover, then a steady gap.
    loss_to_lease_burn_months: int = 12
    steady_loss_to_lease: float = 0.01
    vacancy: float = 0.06
    concessions: float = 0.005
    bad_debt: float = 0.0075
    other_income_per_unit_month: float = 0.0
    other_income_growth: float = 0.03


class Renovation(BaseModel):
    units: int = 0
    cost_per_unit: float = 0.0
    premium_per_month: float = 0.0
    start_month: int = 4
    duration_months: int = 24
    # Months a unit is offline while renovated; lost rent is booked as renovation vacancy.
    downtime_months: int = 1


class CapitalBudget(BaseModel):
    exterior: float = 0.0
    deferred_maintenance: float = 0.0
    marketing: float = 0.0
    contingency_pct: float = 0.10
    construction_management_fee_pct: float = 0.0


class OperatingAssumptions(BaseModel):
    # Controllable and insurance lines, dollars per unit per year in year 1.
    per_unit: dict[str, float] = Field(default_factory=dict)
    expense_growth: float = 0.025
    tax_rate: float = 0.0235
    tax_assessed_share: float = 0.90
    tax_growth: float = 0.03
    management_fee_pct: float = 0.0275
    reserves_per_unit: float = 300.0


class Acquisition(BaseModel):
    purchase_price: float
    asking_price: float | None = None
    closing_date: datetime.date = datetime.date(2026, 3, 1)
    closing_costs_pct: float = 0.011
    acquisition_fee_pct: float = 0.01
    hold_months: int = 60


class Loan(BaseModel):
    ltv_max: float = 0.65
    dscr_min: float = 1.25
    debt_yield_min: float = 0.075
    rate: float = 0.0575
    io_months: int = 36
    amortization_years: int = 30
    term_months: int = 84
    fee_pct: float = 0.0075
    # Set to hold the loan fixed, for stress cases; None sizes the loan on the constraints.
    amount_override: float | None = None
    covenant_dscr: float = 1.25


class Exit(BaseModel):
    cap_rate: float = 0.055
    sale_costs_pct: float = 0.015


class WaterfallTier(BaseModel):
    """Split above the previous hurdle until the LP reaches `hurdle_irr`."""

    hurdle_irr: float
    lp_split: float


class Equity(BaseModel):
    lp_share: float = 0.90
    preferred_return: float = 0.08
    tiers: list[WaterfallTier] = Field(
        default_factory=lambda: [WaterfallTier(hurdle_irr=0.12, lp_split=0.70)]
    )
    residual_lp_split: float = 0.50
    asset_management_fee_pct: float = 0.005


class CopilotInputs(BaseModel):
    property: Property = Field(default_factory=Property)
    revenue: RevenueAssumptions = Field(default_factory=RevenueAssumptions)
    renovation: Renovation = Field(default_factory=Renovation)
    capital: CapitalBudget = Field(default_factory=CapitalBudget)
    operating: OperatingAssumptions = Field(default_factory=OperatingAssumptions)
    acquisition: Acquisition
    loan: Loan = Field(default_factory=Loan)
    exit: Exit = Field(default_factory=Exit)
    equity: Equity = Field(default_factory=Equity)
