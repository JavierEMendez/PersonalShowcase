"""Typed inputs for the MPC land model.

Percentages are fractions (4.5% closing costs is 0.045). Months are 1-based project months
unless a field says otherwise: `dev_start_month` and takedown `period` are 0-based periods,
as they were in the source workbook, and the engine adds one when it schedules them.
"""

from __future__ import annotations

import datetime
from typing import Literal

from pydantic import BaseModel, Field

PlantType = Literal["WWTP", "Water Plant", "Lift Station", "None"]
AmenityType = Literal["Pocket Park", "Small Amenity Center", "Large Amenity Center", "None"]
RoadType = Literal["2 Lane", "4 Lane", ""]
TimingMethod = Literal["1 Takedown", "50/50", "50/25/25", "25/25/25/25"]


class PlantLookup(BaseModel):
    acres: float
    duration: int


class AmenityLookup(BaseModel):
    acres: float
    duration: int


class RoadLookup(BaseModel):
    wsd: float
    paving: float


class Lookups(BaseModel):
    """Editable master tables. Keys are the type names used in the tract inputs."""

    plants: dict[str, PlantLookup] = Field(default_factory=dict)
    amenities: dict[str, AmenityLookup] = Field(default_factory=dict)
    roads: dict[str, RoadLookup] = Field(default_factory=dict)


class Plant(BaseModel):
    type: PlantType = "None"


class Amenity(BaseModel):
    type: AmenityType = "None"
    acres: float = 0.0


class OtherNetout(BaseModel):
    desc: str = ""
    acres: float = 0.0


class Road(BaseModel):
    type: RoadType = ""
    lf: float = 0.0
    width: float = 0.0
    road_setback: float = 0.0
    landscaping_setback: float = 0.0


class Takedown(BaseModel):
    period: int = 0
    pct: float = 0.0


class PlantCost(BaseModel):
    base_cost: float = 0.0
    other_pct: float | None = None
    start_month: int | None = None
    ph2_base_cost: float = 0.0
    ph2_other_pct: float | None = None
    ph2_start_month: int | None = None


class AmenityCost(BaseModel):
    base_cost: float = 0.0
    other_pct: float | None = None
    start_month: int | None = None


class DetentionCost(BaseModel):
    other_pct: float | None = None
    start_month: int | None = None
    duration: int = 9
    landscaping_per_foot: float = 2.0


class OtherCost(BaseModel):
    base_cost: float = 0.0
    other_pct: float | None = None
    start_month: int | None = None
    duration: int = 1


class RoadCost(BaseModel):
    other_pct: float | None = None
    start_month: int | None = None
    landscaping_per_sf: float = 0.0
    light_spacing: float = 0.0


class LotSize(BaseModel):
    """One row of the lot mix. Cost fields and home fields share the row."""

    front_footage: float
    on: bool = False
    yield_per_ac: float = 0.0
    pace: float = 0.0
    dev_start_month: int = 1
    # Section development
    wsd_per_ff: float = 0.0
    paving_per_ff: float = 0.0
    landscaping_per_lot: float = 0.0
    urd_per_lot: float = 0.0
    lots_per_streetlight: float = 0.0
    fence_cost_per_ff: float = 0.0
    # Home table
    build_time: int = 12
    home_price: float = 0.0
    av_pct: float = 0.85
    premium_per_ff: float = 0.0
    escalation: float = 0.0
    fence_per_ff: float = 0.0
    marketing_fee: float = 0.0
    lot_av_pct: float = 0.5
    lot_tax_rate: float = 0.022


class ResidentialPod(BaseModel):
    price_per_acre: float = 0.0
    closing_costs_pct: float = 0.045
    implied_lots_per_acre: float = 0.0
    impact_fee_per_lot: float = 0.0
    sale_period: int | None = None


class CommercialPod(BaseModel):
    price_per_sf: float = 0.0
    closing_costs_pct: float = 0.045
    sale_period: int | None = None
    av_per_acre: float = 0.0
    av_delay_months: int = 18


class Bond(BaseModel):
    toggle: bool = True
    debt_ratio: float = 0.12
    first_bond_period: int = 0
    bond_interval: int = 12
    pct_to_dev: float = 0.85
    receivables_fee: float = 0.025


class Tract(BaseModel):
    project_name: str = "New Project"
    gross_acreage: float = 0.0
    purchase_price_per_acre: float = 0.0
    closing_costs_pct: float = 0.045
    land_escalator: float = 0.05
    closing_date: datetime.date | None = None
    plants: list[Plant] = Field(default_factory=list)
    det_storage_rate: float = 0.0
    det_depth: float = 0.0
    det_num_projects: int = 0
    det_cost_per_cy: float = 10.0
    amenities: list[Amenity] = Field(default_factory=list)
    parks_pct: float = 0.03
    drill_site_acres: float = 0.0
    other_netouts: list[OtherNetout] = Field(default_factory=list)
    roads: list[Road] = Field(default_factory=list)
    commercial_pod_acres: float = 0.0
    residential_pod_acres: float = 0.0


class Costs(BaseModel):
    default_other_pct: float = 0.17
    sectional_other_pct: float = 0.17
    landscaping_other_pct: float = 0.12
    contingency: float = 0.05
    site_work_pct: float = 0.01
    fenced_pct: float = 0.25
    cost_per_mailbox: float = 200.0
    cost_per_streetlight: float = 1700.0
    default_start_month: int = 1
    takedowns: list[Takedown] = Field(default_factory=list)
    plant_costs: list[PlantCost] = Field(default_factory=list)
    amenity_costs: list[AmenityCost] = Field(default_factory=list)
    det_costs: list[DetentionCost] = Field(default_factory=list)
    other_costs: list[OtherCost] = Field(default_factory=list)
    road_costs: list[RoadCost] = Field(default_factory=list)
    lot_sizes: list[LotSize] = Field(default_factory=list)
    prof_svc_pct: float = 0.015
    dmf_pct: float = 0.025
    personnel_monthly: float = 0.0
    marketing_personnel_monthly: float = 0.0
    legal_monthly: float = 0.0
    mud_monthly: float = 0.0
    insurance_monthly: float = 0.0
    bookkeeping_monthly: float = 0.0
    mud_pct: float = 0.2


class Revenue(BaseModel):
    timing_method: TimingMethod = "50/25/25"
    bem_period: int = 9
    bem_pct: float = 0.18
    brokerage_fees: float = 0.03
    lot_closing_costs: float = 0.015
    price_per_ff: list[float] = Field(default_factory=lambda: [1800.0] * 11)
    res_pods: list[ResidentialPod] = Field(default_factory=list)
    comm_pods: list[CommercialPod] = Field(default_factory=list)
    mud_bond: Bond = Field(default_factory=Bond)
    wcid_bond: Bond = Field(default_factory=Bond)


class DealInputs(BaseModel):
    tract: Tract = Field(default_factory=Tract)
    costs: Costs = Field(default_factory=Costs)
    revenue: Revenue = Field(default_factory=Revenue)
    lookups: Lookups = Field(default_factory=Lookups)
