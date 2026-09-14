"""Infrastructure cost rows: plants, amenities, detention, other items, and collector roads.

Each row carries its total cost, start month, and duration. The schedule that spreads them
across the ledger lives in `sections.py`.
"""

from __future__ import annotations

from pydantic import BaseModel

from core.underwriting.inputs import Costs, Tract
from core.underwriting.ledger import mround
from core.underwriting.lookups import EffectiveLookups
from core.underwriting.netouts import SF_PER_ACRE, Acreage

CUBIC_FEET_PER_CUBIC_YARD = 27.0
# Only the pond perimeter is landscaped: 30% of the footprint area, priced per foot.
DETENTION_LANDSCAPED_SHARE = 0.30
PLANT_ROWS = 8
AMENITY_ROWS = 6
ROAD_ROWS = 6
# Default start months for collector roads, by row.
ROAD_DEFAULT_START_MONTHS = [None, 12, 48, 72, 96, None]


class PlantCostRow(BaseModel):
    type: str
    acres: float
    base_cost: float
    other_pct: float
    total_cost: float
    start_month: int
    duration: int
    ph2_base_cost: float
    ph2_other_pct: float
    ph2_total_cost: float
    ph2_start_month: int
    ph2_duration: int


class AmenityCostRow(BaseModel):
    type: str
    acres: float
    base_cost: float
    other_pct: float
    total_cost: float
    start_month: int
    duration: int


class DetentionCostRow(BaseModel):
    acres: float
    base_cost: float
    other_pct: float
    total_cost: float
    start_month: int
    duration: int
    delivery_month: int
    landscaping_per_foot: float
    total_landscaping: float


class OtherCostRow(BaseModel):
    desc: str
    acres: float
    base_cost: float
    other_pct: float
    total_cost: float
    start_month: int
    duration: int


class RoadCostRow(BaseModel):
    type: str
    lf: float
    wsd_per_lf: float
    paving_per_lf: float
    base_cost: float
    other_pct: float
    total_cost: float
    start_month: int
    duration: int
    delivery_month: int
    landscaping_per_sf: float
    total_landscaping: float
    light_spacing: float
    total_lights: int


class Infrastructure(BaseModel):
    plants: list[PlantCostRow]
    amenities: list[AmenityCostRow]
    detention: list[DetentionCostRow]
    other: list[OtherCostRow]
    roads: list[RoadCostRow]
    detention_volume_cy: float
    total_plants: float
    total_amenities: float
    total_detention: float
    total_detention_landscaping: float
    total_other: float
    total_roads: float
    total_road_landscaping: float
    total_road_lights: int


def _pct(value: float | None, default: float) -> float:
    return default if value is None else value


def plant_rows(
    tract: Tract, costs: Costs, lookups: EffectiveLookups, acreage: Acreage
) -> list[PlantCostRow]:
    rows: list[PlantCostRow] = []
    for i in range(max(len(tract.plants), len(costs.plant_costs), PLANT_ROWS)):
        pc = costs.plant_costs[i] if i < len(costs.plant_costs) else None
        ptype = tract.plants[i].type if i < len(tract.plants) else "None"
        duration = lookups.plant(ptype).duration
        base = pc.base_cost if pc else 0.0
        other = _pct(pc.other_pct if pc else None, costs.default_other_pct)
        start = (
            costs.default_start_month if pc is None or pc.start_month is None else pc.start_month
        )
        ph2_base = pc.ph2_base_cost if pc else 0.0
        ph2_other = _pct(pc.ph2_other_pct if pc else None, costs.default_other_pct)
        ph2_start = start + 36 if pc is None or pc.ph2_start_month is None else pc.ph2_start_month
        rows.append(
            PlantCostRow(
                type=ptype,
                acres=acreage.plant_acres[i] if i < len(acreage.plant_acres) else 0.0,
                base_cost=base,
                other_pct=other,
                total_cost=base * (1 + other) if base else 0.0,
                start_month=start,
                duration=duration,
                ph2_base_cost=ph2_base,
                ph2_other_pct=ph2_other,
                ph2_total_cost=ph2_base * (1 + ph2_other) if ph2_base else 0.0,
                ph2_start_month=ph2_start,
                ph2_duration=duration,
            )
        )
    return rows


def amenity_rows(tract: Tract, costs: Costs, lookups: EffectiveLookups) -> list[AmenityCostRow]:
    rows: list[AmenityCostRow] = []
    for i in range(max(len(tract.amenities), len(costs.amenity_costs), AMENITY_ROWS)):
        ac = costs.amenity_costs[i] if i < len(costs.amenity_costs) else None
        amenity = tract.amenities[i] if i < len(tract.amenities) else None
        atype = amenity.type if amenity else "None"
        base = ac.base_cost if ac else 0.0
        other = _pct(ac.other_pct if ac else None, costs.default_other_pct)
        start = (
            costs.default_start_month if ac is None or ac.start_month is None else ac.start_month
        )
        user_acres = amenity.acres if amenity else 0.0
        rows.append(
            AmenityCostRow(
                type=atype,
                acres=user_acres if user_acres else lookups.amenity(atype).acres,
                base_cost=base,
                other_pct=other,
                total_cost=base * (1 + other) if base else 0.0,
                start_month=start,
                duration=lookups.amenity(atype).duration,
            )
        )
    return rows


def detention_rows(
    tract: Tract, costs: Costs, acreage: Acreage
) -> tuple[list[DetentionCostRow], float]:
    """Detention projects share one excavation volume equally; each carries its own schedule."""
    gross = tract.gross_acreage
    volume_cy = (
        tract.det_storage_rate * gross * SF_PER_ACRE / CUBIC_FEET_PER_CUBIC_YARD if gross else 0.0
    )
    total_base = volume_cy * tract.det_cost_per_cy
    num = tract.det_num_projects
    base_each = total_base / num if num else 0.0
    rows: list[DetentionCostRow] = []
    for idx in range(int(num)):
        dc = costs.det_costs[idx] if idx < len(costs.det_costs) else None
        other = _pct(dc.other_pct if dc else None, costs.default_other_pct)
        start = (
            costs.default_start_month + idx * 15
            if dc is None or dc.start_month is None
            else dc.start_month
        )
        duration = dc.duration if dc else 9
        lpf = dc.landscaping_per_foot if dc else 2.0
        rows.append(
            DetentionCostRow(
                acres=acreage.detention_each,
                base_cost=base_each,
                other_pct=other,
                total_cost=base_each * (1 + other),
                start_month=start,
                duration=duration,
                delivery_month=start + duration - 1,
                landscaping_per_foot=lpf,
                total_landscaping=lpf
                * SF_PER_ACRE
                * acreage.detention_each
                * (1 + costs.landscaping_other_pct)
                * DETENTION_LANDSCAPED_SHARE,
            )
        )
    return rows, volume_cy


def other_rows(tract: Tract, costs: Costs) -> list[OtherCostRow]:
    rows: list[OtherCostRow] = []
    for i, oc in enumerate(costs.other_costs):
        netout = tract.other_netouts[i] if i < len(tract.other_netouts) else None
        other = _pct(oc.other_pct, costs.default_other_pct)
        rows.append(
            OtherCostRow(
                desc=netout.desc if netout else "",
                acres=netout.acres if netout else 0.0,
                base_cost=oc.base_cost,
                other_pct=other,
                total_cost=oc.base_cost * (1 + other) if oc.base_cost else 0.0,
                start_month=costs.default_start_month if oc.start_month is None else oc.start_month,
                duration=oc.duration,
            )
        )
    return rows


def road_rows(tract: Tract, costs: Costs, lookups: EffectiveLookups) -> list[RoadCostRow]:
    rows: list[RoadCostRow] = []
    for i in range(max(len(tract.roads), len(costs.road_costs), ROAD_ROWS)):
        rc = costs.road_costs[i] if i < len(costs.road_costs) else None
        road = tract.roads[i] if i < len(tract.roads) else None
        rtype = road.type if road else ""
        lf = road.lf if road else 0.0
        ls_setback = road.landscaping_setback if road else 0.0
        lookup = lookups.road(rtype)
        base = lf * (lookup.wsd + lookup.paving) if lf else 0.0
        other = _pct(rc.other_pct if rc else None, costs.default_other_pct)
        default_start = ROAD_DEFAULT_START_MONTHS[i] if i < len(ROAD_DEFAULT_START_MONTHS) else None
        if rc is not None and rc.start_month is not None:
            start = rc.start_month
        else:
            start = costs.default_start_month if default_start is None else default_start
        # Build time grows with length: six months plus one month per 300 LF.
        duration = int(mround(lf / 300 + 6, 1)) if lf else 6
        lsf = rc.landscaping_per_sf if rc else 0.0
        spacing = rc.light_spacing if rc else 0.0
        rows.append(
            RoadCostRow(
                type=rtype,
                lf=lf,
                wsd_per_lf=lookup.wsd,
                paving_per_lf=lookup.paving,
                base_cost=base,
                other_pct=other,
                total_cost=base * (1 + other) if base else 0.0,
                start_month=start,
                duration=duration,
                delivery_month=duration + start - 1,
                landscaping_per_sf=lsf,
                total_landscaping=(
                    lsf * ls_setback * lf * 2 * (1 + costs.landscaping_other_pct) if lf else 0.0
                ),
                light_spacing=spacing,
                total_lights=int(lf / spacing * 2) if spacing and lf else 0,
            )
        )
    return rows


def compute_infrastructure(
    tract: Tract, costs: Costs, lookups: EffectiveLookups, acreage: Acreage
) -> Infrastructure:
    plants = plant_rows(tract, costs, lookups, acreage)
    amenities = amenity_rows(tract, costs, lookups)
    detention, volume_cy = detention_rows(tract, costs, acreage)
    other = other_rows(tract, costs)
    roads = road_rows(tract, costs, lookups)
    return Infrastructure(
        plants=plants,
        amenities=amenities,
        detention=detention,
        other=other,
        roads=roads,
        detention_volume_cy=volume_cy,
        total_plants=sum(r.total_cost + r.ph2_total_cost for r in plants),
        total_amenities=sum(r.total_cost for r in amenities),
        total_detention=sum(r.total_cost for r in detention),
        total_detention_landscaping=sum(r.total_landscaping for r in detention),
        total_other=sum(r.total_cost for r in other),
        total_roads=sum(r.total_cost for r in roads),
        total_road_landscaping=sum(r.total_landscaping for r in roads),
        total_road_lights=sum(r.total_lights for r in roads),
    )
