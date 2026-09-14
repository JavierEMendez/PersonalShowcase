"""Master lookup tables and the effective tables after user overrides."""

from __future__ import annotations

from dataclasses import dataclass

from core.underwriting.inputs import AmenityLookup, Lookups, PlantLookup, RoadLookup

PLANT_LOOKUPS: dict[str, PlantLookup] = {
    "WWTP": PlantLookup(acres=10.0, duration=8),
    "Water Plant": PlantLookup(acres=3.5, duration=8),
    "Lift Station": PlantLookup(acres=0.75, duration=3),
    "None": PlantLookup(acres=0.0, duration=0),
}
AMENITY_LOOKUPS: dict[str, AmenityLookup] = {
    "Pocket Park": AmenityLookup(acres=0.5, duration=2),
    "Small Amenity Center": AmenityLookup(acres=3.0, duration=8),
    "Large Amenity Center": AmenityLookup(acres=6.0, duration=12),
    "None": AmenityLookup(acres=0.0, duration=0),
}
ROAD_LOOKUPS: dict[str, RoadLookup] = {
    "2 Lane": RoadLookup(wsd=450, paving=343),
    "4 Lane": RoadLookup(wsd=460, paving=663),
}

# Lot size front footage by row index (rows 0 to 15 are 25, 30, 35, ..., 100 FF).
LOT_FF_BY_INDEX: list[float] = [25.0 + 5.0 * i for i in range(16)]

NO_PLANT = PlantLookup(acres=0.0, duration=0)
NO_AMENITY = AmenityLookup(acres=0.0, duration=0)
NO_ROAD = RoadLookup(wsd=0.0, paving=0.0)


@dataclass(frozen=True)
class EffectiveLookups:
    plants: dict[str, PlantLookup]
    amenities: dict[str, AmenityLookup]
    roads: dict[str, RoadLookup]

    def plant(self, kind: str) -> PlantLookup:
        return self.plants.get(kind, NO_PLANT)

    def amenity(self, kind: str) -> AmenityLookup:
        return self.amenities.get(kind, NO_AMENITY)

    def road(self, kind: str) -> RoadLookup:
        return self.roads.get(kind, NO_ROAD)


def effective_lookups(overrides: Lookups) -> EffectiveLookups:
    """Master tables with user rows layered on top, keyed by type name."""
    return EffectiveLookups(
        plants={**PLANT_LOOKUPS, **overrides.plants},
        amenities={**AMENITY_LOOKUPS, **overrides.amenities},
        roads={**ROAD_LOOKUPS, **overrides.roads},
    )
