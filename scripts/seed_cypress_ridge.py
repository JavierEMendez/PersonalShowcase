#!/usr/bin/env python3
"""Write data/cypress_ridge.json: the Cypress Ridge scenarios as typed inputs.

Figures follow docs/synthetic-deals.md. Where that document is silent the values are the
model defaults or a realistic Houston-area figure chosen for the synthetic deal.

Usage: python scripts/seed_cypress_ridge.py
"""

from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.underwriting.inputs import (  # noqa: E402
    Amenity,
    AmenityCost,
    Bond,
    CommercialPod,
    Costs,
    DealInputs,
    LotSize,
    OtherCost,
    OtherNetout,
    Plant,
    PlantCost,
    ResidentialPod,
    Revenue,
    Road,
    RoadCost,
    Takedown,
    Tract,
)
from core.underwriting.lookups import LOT_FF_BY_INDEX  # noqa: E402

ACTIVE_LOTS: dict[float, tuple[float, float]] = {
    # front footage: (home price, marketing fee per lot)
    40.0: (280_000, 3_000),
    45.0: (320_000, 3_500),
    50.0: (360_000, 4_000),
    60.0: (430_000, 5_000),
    80.0: (560_000, 6_500),
}


def lot_mix(pace: float) -> list[LotSize]:
    rows: list[LotSize] = []
    for ff in LOT_FF_BY_INDEX:
        if ff not in ACTIVE_LOTS:
            rows.append(LotSize(front_footage=ff))
            continue
        home_price, marketing_fee = ACTIVE_LOTS[ff]
        rows.append(
            LotSize(
                front_footage=ff,
                on=True,
                yield_per_ac=5.5,
                pace=pace,
                dev_start_month=1,
                wsd_per_ff=580,
                paving_per_ff=440,
                landscaping_per_lot=2_000,
                urd_per_lot=35,
                lots_per_streetlight=4,
                fence_cost_per_ff=94,
                build_time=6,
                home_price=home_price,
                av_pct=0.85,
                premium_per_ff=25,
                escalation=0.06,
                fence_per_ff=65,
                marketing_fee=marketing_fee,
                lot_av_pct=0.5,
                lot_tax_rate=0.02,
            )
        )
    return rows


def main_inputs() -> DealInputs:
    tract = Tract(
        project_name="Cypress Ridge",
        gross_acreage=640.0,
        purchase_price_per_acre=45_000,
        closing_costs_pct=0.045,
        land_escalator=0.05,
        closing_date=datetime.date(2027, 3, 1),
        plants=[Plant(type="WWTP"), Plant(type="Water Plant"), Plant(type="Lift Station")],
        det_storage_rate=1.1,
        det_depth=9,
        det_num_projects=6,
        det_cost_per_cy=10,
        amenities=[
            Amenity(type="Large Amenity Center", acres=6.0),
            Amenity(type="Small Amenity Center", acres=3.0),
        ],
        parks_pct=0.03,
        drill_site_acres=4.5,
        other_netouts=[
            OtherNetout(desc="Pipeline easement", acres=3.0),
            OtherNetout(desc="Gas well setback", acres=3.0),
        ],
        roads=[
            Road(type="4 Lane", lf=4_000, width=80, road_setback=10, landscaping_setback=10),
            Road(type="2 Lane", lf=3_850, width=60, road_setback=5, landscaping_setback=8),
        ],
        commercial_pod_acres=22.0,
        residential_pod_acres=12.0,
    )
    costs = Costs(
        default_other_pct=0.17,
        sectional_other_pct=0.17,
        landscaping_other_pct=0.12,
        contingency=0.05,
        site_work_pct=0.01,
        fenced_pct=0.25,
        cost_per_mailbox=200,
        cost_per_streetlight=1_700,
        default_start_month=1,
        takedowns=[Takedown(period=0, pct=0.5), Takedown(period=36, pct=0.5)],
        plant_costs=[
            PlantCost(base_cost=5_500_000, start_month=1, ph2_base_cost=2_000_000),
            PlantCost(base_cost=3_000_000, start_month=1),
            PlantCost(base_cost=750_000, start_month=1),
        ],
        amenity_costs=[
            AmenityCost(base_cost=4_500_000, start_month=6),
            AmenityCost(base_cost=1_800_000, start_month=30),
        ],
        other_costs=[
            OtherCost(base_cost=1_200_000, start_month=3, duration=6),
            OtherCost(base_cost=600_000, start_month=2, duration=3),
        ],
        road_costs=[
            RoadCost(start_month=1, landscaping_per_sf=2, light_spacing=150),
            RoadCost(start_month=12, landscaping_per_sf=2, light_spacing=200),
        ],
        lot_sizes=lot_mix(pace=7.0),
        prof_svc_pct=0.015,
        dmf_pct=0.025,
        personnel_monthly=50_000,
        marketing_personnel_monthly=15_000,
        legal_monthly=10_000,
        mud_monthly=35_000,
        insurance_monthly=10_000,
        bookkeeping_monthly=10_000,
        mud_pct=0.2,
    )
    revenue = Revenue(
        timing_method="50/25/25",
        bem_period=9,
        bem_pct=0.18,
        brokerage_fees=0.03,
        lot_closing_costs=0.015,
        price_per_ff=[1_800.0] * 11,
        res_pods=[
            ResidentialPod(
                price_per_acre=350_000,
                closing_costs_pct=0.045,
                implied_lots_per_acre=3.5,
                impact_fee_per_lot=10_000,
                sale_period=12,
            )
        ],
        comm_pods=[
            CommercialPod(price_per_sf=8, sale_period=12, av_per_acre=1_200_000),
            CommercialPod(price_per_sf=8, sale_period=36, av_per_acre=1_200_000),
        ],
        mud_bond=Bond(debt_ratio=0.12, first_bond_period=48, bond_interval=12),
        wcid_bond=Bond(debt_ratio=0.042, first_bond_period=48, bond_interval=12),
    )
    return DealInputs(tract=tract, costs=costs, revenue=revenue)


def faster_pace(base: DealInputs) -> DealInputs:
    """Pace 8.4 lots per month on every active lot size, all else equal."""
    scenario = base.model_copy(deep=True)
    scenario.costs.lot_sizes = lot_mix(pace=8.4)
    return scenario


def lower_lot_price(base: DealInputs) -> DealInputs:
    """Lot price $1,620 per front foot every year, all else equal."""
    scenario = base.model_copy(deep=True)
    scenario.revenue.price_per_ff = [1_620.0] * 11
    return scenario


def build() -> dict[str, object]:
    main = main_inputs()
    return {
        "name": "Cypress Ridge",
        "status": "Initial UW",
        "location": "Waller County, TX",
        "scenarios": [
            {"name": "Main", "inputs": main.model_dump(mode="json")},
            {"name": "Faster pace", "inputs": faster_pace(main).model_dump(mode="json")},
            {"name": "Lower lot price", "inputs": lower_lot_price(main).model_dump(mode="json")},
        ],
    }


if __name__ == "__main__":
    target = ROOT / "data" / "cypress_ridge.json"
    target.write_text(json.dumps(build(), indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {target.relative_to(ROOT)}")
