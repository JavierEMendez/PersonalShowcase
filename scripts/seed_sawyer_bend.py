#!/usr/bin/env python3
"""Write data/sawyer_bend.json: the Sawyer Bend Apartments cases as typed inputs.

Figures follow docs/synthetic-deals.md. Usage: python scripts/seed_sawyer_bend.py
"""

from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.copilot.inputs import (  # noqa: E402
    Acquisition,
    CapitalBudget,
    CopilotInputs,
    Equity,
    Exit,
    FloorPlan,
    Loan,
    OperatingAssumptions,
    Property,
    Renovation,
    RevenueAssumptions,
    WaterfallTier,
)

# Screen output: the fifteen extracted assumptions with source and confidence (build step 6 makes
# these live; until then they are the seed).
ASSUMPTIONS: list[dict[str, str]] = [
    {"assumption": "Asking price", "value": "$50.5M", "source": "OM p. 2", "confidence": "High"},
    {"assumption": "Units", "value": "288", "source": "OM p. 3", "confidence": "High"},
    {
        "assumption": "In-place rent",
        "value": "$1,440 / unit",
        "source": "Rent roll",
        "confidence": "High",
    },
    {"assumption": "Occupancy", "value": "94.1%", "source": "Rent roll", "confidence": "High"},
    {
        "assumption": "Market rent",
        "value": "$1,511 / unit",
        "source": "Comp survey, 8 properties",
        "confidence": "Medium",
    },
    {
        "assumption": "Renovation premium",
        "value": "$145 / mo",
        "source": "Renovated comps",
        "confidence": "Medium",
    },
    {
        "assumption": "Renovation cost",
        "value": "$9,500 / unit",
        "source": "Contractor bid",
        "confidence": "Medium",
    },
    {
        "assumption": "Agency loan rate",
        "value": "5.75%",
        "source": "Term sheet p. 1",
        "confidence": "High",
    },
    {
        "assumption": "Real estate taxes",
        "value": "2.35% of 90% of price",
        "source": "Appraisal district",
        "confidence": "Low",
    },
    {
        "assumption": "Other income",
        "value": "$115 / unit / mo",
        "source": "T-12",
        "confidence": "High",
    },
    {
        "assumption": "Controllable expenses",
        "value": "$4,700 / unit",
        "source": "T-12, buyer adjustments",
        "confidence": "Medium",
    },
    {
        "assumption": "Insurance",
        "value": "$850 / unit",
        "source": "Broker quote",
        "confidence": "High",
    },
    {
        "assumption": "Exit cap rate",
        "value": "5.50%",
        "source": "Comp set, 5 sales",
        "confidence": "Medium",
    },
    {
        "assumption": "Loan terms",
        "value": "65% LTV · 1.25× · 7.5% DY · 36 mo I/O",
        "source": "Term sheet p. 1",
        "confidence": "High",
    },
    {
        "assumption": "Replacement reserves",
        "value": "$300 / unit",
        "source": "Lender requirement",
        "confidence": "High",
    },
]


def base_inputs() -> CopilotInputs:
    return CopilotInputs(
        property=Property(
            name="Sawyer Bend Apartments",
            location="Northwest Houston",
            year_built=2016,
            non_revenue_units=2,
            floor_plans=[
                FloorPlan(
                    code="A1",
                    unit_type="1 x 1",
                    units=144,
                    sf=720,
                    occupied=136,
                    in_place_rent=1_245,
                    market_rent=1_310,
                ),
                FloorPlan(
                    code="B2",
                    unit_type="2 x 2",
                    units=120,
                    sf=1_050,
                    occupied=113,
                    in_place_rent=1_585,
                    market_rent=1_660,
                ),
                FloorPlan(
                    code="C2",
                    unit_type="3 x 2",
                    units=24,
                    sf=1_320,
                    occupied=22,
                    in_place_rent=1_890,
                    market_rent=1_975,
                ),
            ],
        ),
        revenue=RevenueAssumptions(
            market_rent_growth=0.03,
            loss_to_lease_burn_months=12,
            steady_loss_to_lease=0.01,
            vacancy=0.06,
            concessions=0.005,
            bad_debt=0.0075,
            other_income_per_unit_month=115,
            other_income_growth=0.03,
        ),
        renovation=Renovation(
            units=120,
            cost_per_unit=9_500,
            premium_per_month=145,
            start_month=4,
            duration_months=24,
            downtime_months=1,
        ),
        capital=CapitalBudget(
            exterior=850_000, deferred_maintenance=400_000, marketing=0, contingency_pct=0.10
        ),
        operating=OperatingAssumptions(
            per_unit={
                "Payroll": 1_350,
                "Repairs and maintenance": 650,
                "Turnover": 250,
                "Contract services": 300,
                "Marketing": 175,
                "Administrative": 225,
                "Utilities": 900,
                "Insurance": 850,
            },
            expense_growth=0.025,
            tax_rate=0.0235,
            tax_assessed_share=0.90,
            tax_growth=0.03,
            management_fee_pct=0.0275,
            reserves_per_unit=300,
        ),
        acquisition=Acquisition(
            purchase_price=46_000_000,
            asking_price=50_500_000,
            closing_date=datetime.date(2026, 3, 1),
            closing_costs_pct=0.011,
            acquisition_fee_pct=0.01,
            hold_months=60,
        ),
        loan=Loan(
            ltv_max=0.65,
            dscr_min=1.25,
            debt_yield_min=0.075,
            rate=0.0575,
            io_months=36,
            amortization_years=30,
            term_months=84,
            fee_pct=0.0075,
            covenant_dscr=1.25,
        ),
        exit=Exit(cap_rate=0.055, sale_costs_pct=0.015),
        equity=Equity(
            lp_share=0.90,
            preferred_return=0.08,
            tiers=[WaterfallTier(hurdle_irr=0.12, lp_split=0.70)],
            residual_lp_split=0.50,
            asset_management_fee_pct=0.005,
        ),
    )


def downside(base: CopilotInputs, base_loan: float) -> CopilotInputs:
    """Rent growth 1.5%, exit cap 6.00%, vacancy 8%, premium $100, loan held at base sizing."""
    case = base.model_copy(deep=True)
    case.revenue.market_rent_growth = 0.015
    case.exit.cap_rate = 0.06
    case.revenue.vacancy = 0.08
    case.renovation.premium_per_month = 100
    case.loan.amount_override = base_loan
    return case


def lender(base: CopilotInputs) -> CopilotInputs:
    """Rent growth 2%, vacancy 7%, exit cap 5.75%, maximum 55% LTV."""
    case = base.model_copy(deep=True)
    case.revenue.market_rent_growth = 0.02
    case.revenue.vacancy = 0.07
    case.exit.cap_rate = 0.0575
    case.loan.ltv_max = 0.55
    return case


def build() -> dict[str, object]:
    from core.copilot.engine import run

    base = base_inputs()
    base_loan = run(base).loan.amount
    return {
        "name": "Sawyer Bend Apartments",
        "status": "Underwrite",
        "location": "Northwest Houston",
        "facts": "288 units · Built 2016 · Northwest Houston · 94.1% occupied · 5-year hold",
        "assumptions": ASSUMPTIONS,
        "cases": [
            {"name": "Base", "inputs": base.model_dump(mode="json")},
            {
                "name": "Downside",
                "inputs": downside(base, float(base_loan)).model_dump(mode="json"),
            },
            {"name": "Lender", "inputs": lender(base).model_dump(mode="json")},
        ],
    }


if __name__ == "__main__":
    target = ROOT / "data" / "sawyer_bend.json"
    target.write_text(json.dumps(build(), indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {target.relative_to(ROOT)}")
