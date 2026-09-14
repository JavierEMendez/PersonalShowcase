"""Net-outs: gross acreage down to residential developable acreage."""

from __future__ import annotations

from pydantic import BaseModel

from core.underwriting.inputs import Tract
from core.underwriting.lookups import EffectiveLookups

SF_PER_ACRE = 43560.0
# Detention ponds take 30% more footprint than the storage volume alone implies.
DETENTION_FOOTPRINT_FACTOR = 1.3


class Acreage(BaseModel):
    gross: float
    plants: float
    detention: float
    amenities: float
    parks: float
    drill_sites: float
    other: float
    roads: float
    net_out_total: float
    developable: float
    commercial_pods: float
    residential_pods: float
    residential_developable: float
    detention_each: float
    plant_acres: list[float]
    road_acres: list[float]


def road_acres(lf: float, width: float, road_setback: float, landscaping_setback: float) -> float:
    """Right of way acres: length times paved width plus both setbacks on each side."""
    if not lf:
        return 0.0
    return lf * (width + (landscaping_setback + road_setback) * 2) / SF_PER_ACRE


def detention_footprint(storage_rate: float, gross_acres: float, depth: float) -> float:
    """Total detention footprint in acres: storage volume over depth, grossed up 30%."""
    if not depth:
        return 0.0
    return storage_rate * gross_acres / depth * DETENTION_FOOTPRINT_FACTOR


def compute_netouts(tract: Tract, lookups: EffectiveLookups) -> Acreage:
    gross = tract.gross_acreage

    plant_acres = [lookups.plant(p.type).acres for p in tract.plants]
    plants = sum(plant_acres)

    detention = detention_footprint(tract.det_storage_rate, gross, tract.det_depth)
    detention_each = detention / tract.det_num_projects if tract.det_num_projects else 0.0

    # Amenity net-outs use the acres entered on the tract, not the lookup table.
    amenities = sum(a.acres for a in tract.amenities)
    other = sum(o.acres for o in tract.other_netouts)
    roads_list = [
        road_acres(r.lf, r.width, r.road_setback, r.landscaping_setback) for r in tract.roads
    ]
    roads = sum(roads_list)
    parks = tract.parks_pct * gross

    net_out_total = plants + detention + amenities + parks + tract.drill_site_acres + other + roads
    developable = gross - net_out_total
    residential_developable = developable - tract.commercial_pod_acres - tract.residential_pod_acres

    return Acreage(
        gross=gross,
        plants=plants,
        detention=detention,
        amenities=amenities,
        parks=parks,
        drill_sites=tract.drill_site_acres,
        other=other,
        roads=roads,
        net_out_total=net_out_total,
        developable=developable,
        commercial_pods=tract.commercial_pod_acres,
        residential_pods=tract.residential_pod_acres,
        residential_developable=residential_developable,
        detention_each=detention_each,
        plant_acres=plant_acres,
        road_acres=roads_list,
    )
