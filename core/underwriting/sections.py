"""Schedules: project length, infrastructure spreads, and the 18-month section program.

Section k of a lot size starts at `dev_start + 18 (k - 1)` and delivers 18 months later. Its
development cost is spent 10% over the first twelve months and 90% over the last six. Lump
sums that land at delivery: landscaping, fencing, dry utilities (URD), and streetlights.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.underwriting.allocation import SECTION_MONTHS, LotAllocation, section_lots
from core.underwriting.infrastructure import Infrastructure
from core.underwriting.inputs import Costs, LotSize
from core.underwriting.land import Land
from core.underwriting.ledger import MAX_MONTHS, lump, spread, zeros

PHASE_ONE_SHARE = 0.10
PHASE_ONE_MONTHS = 12
PHASE_TWO_SHARE = 0.90
PHASE_TWO_MONTHS = 6
MINIMUM_PROJECT_MONTHS = 60


def project_length(
    infra: Infrastructure, lot_sizes: list[LotSize], allocation: list[LotAllocation]
) -> int:
    """Months until the last plant, road, lot take, or home sale, at least 60, at most 360."""
    deliveries: list[int] = []
    for plant in infra.plants:
        if plant.type not in ("None", ""):
            deliveries.append(plant.start_month + plant.duration - 1)
    for road in infra.roads:
        deliveries.append(road.delivery_month)
    if allocation:
        max_lot_months = 0
        for ls, lot in zip(lot_sizes, allocation, strict=True):
            if lot.total_lots > 0 and lot.pace > 0:
                start = ls.dev_start_month + 1
                build_time = max(0, ls.build_time)
                section_count = lot.full_sections + (1 if lot.last_lots > 0 else 0)
                last_third_take = start + section_count * SECTION_MONTHS + 9
                # Home sales run on after the last delivery: build time plus one more section.
                last_home_sale = (
                    start + section_count * SECTION_MONTHS + build_time + SECTION_MONTHS
                )
                max_lot_months = max(max_lot_months, last_third_take, last_home_sale)
        deliveries.append(max_lot_months)
    if not deliveries:
        return MINIMUM_PROJECT_MONTHS
    return min(max([*deliveries, MINIMUM_PROJECT_MONTHS]), MAX_MONTHS)


@dataclass
class InfrastructureLedger:
    land: list[float] = field(default_factory=zeros)
    plants: list[float] = field(default_factory=zeros)
    amenities: list[float] = field(default_factory=zeros)
    detention: list[float] = field(default_factory=zeros)
    other: list[float] = field(default_factory=zeros)
    roads: list[float] = field(default_factory=zeros)
    # Detention and road landscaping, booked as lump sums at delivery.
    landscaping: list[float] = field(default_factory=zeros)


def schedule_infrastructure(land: Land, infra: Infrastructure) -> InfrastructureLedger:
    ledger = InfrastructureLedger()
    # Takedown periods are 0-based; cash leaves in the following project month.
    for td in land.takedowns:
        lump(ledger.land, td.total, td.period + 1)
    for plant in infra.plants:
        spread(ledger.plants, plant.total_cost, plant.start_month, plant.duration)
        spread(ledger.plants, plant.ph2_total_cost, plant.ph2_start_month, plant.ph2_duration)
    for amenity in infra.amenities:
        spread(ledger.amenities, amenity.total_cost, amenity.start_month, amenity.duration)
    for pond in infra.detention:
        spread(ledger.detention, pond.total_cost, pond.start_month, pond.duration)
        if pond.total_landscaping > 0:
            lump(ledger.landscaping, pond.total_landscaping, pond.delivery_month)
    for item in infra.other:
        spread(ledger.other, item.total_cost, item.start_month, max(item.duration, 1))
    for road in infra.roads:
        spread(ledger.roads, road.total_cost, road.start_month, road.duration)
        if road.total_landscaping > 0:
            lump(ledger.landscaping, road.total_landscaping, road.delivery_month)
    return ledger


@dataclass
class SectionSchedule:
    dev_cost: list[float] = field(default_factory=zeros)
    landscaping: list[float] = field(default_factory=zeros)
    fencing: list[float] = field(default_factory=zeros)
    urd: list[float] = field(default_factory=zeros)
    streetlights: list[float] = field(default_factory=zeros)
    lot_deliveries: list[float] = field(default_factory=zeros)
    total_dev_cost: float = 0.0
    total_landscaping: float = 0.0
    total_fencing: float = 0.0
    total_urd: float = 0.0
    total_streetlights: float = 0.0


def schedule_sections(
    lot_sizes: list[LotSize], allocation: list[LotAllocation], costs: Costs
) -> SectionSchedule:
    sched = SectionSchedule()
    for ls, lot in zip(lot_sizes, allocation, strict=True):
        if not lot.on or lot.total_lots == 0 or lot.pace <= 0:
            continue
        start_month = ls.dev_start_month + 1
        for k, lots in section_lots(lot):
            section_start = start_month + (k - 1) * SECTION_MONTHS
            delivery = section_start + SECTION_MONTHS

            # Development cost carries the sectional contingency on FF x (WSD + paving) per lot.
            section_cost = lots * lot.dev_cost_per_lot * (1 + costs.sectional_other_pct)
            sched.total_dev_cost += section_cost
            phase_one = section_cost * PHASE_ONE_SHARE / PHASE_ONE_MONTHS
            for offset in range(PHASE_ONE_MONTHS):
                lump(sched.dev_cost, phase_one, section_start + offset)
            phase_two = section_cost * PHASE_TWO_SHARE / PHASE_TWO_MONTHS
            for offset in range(PHASE_ONE_MONTHS, PHASE_ONE_MONTHS + PHASE_TWO_MONTHS):
                lump(sched.dev_cost, phase_two, section_start + offset)

            # Delivery-timed lump sums.
            if ls.landscaping_per_lot:
                amount = lots * ls.landscaping_per_lot * (1 + costs.landscaping_other_pct)
                sched.total_landscaping += amount
                lump(sched.landscaping, amount, delivery)
            if ls.fence_cost_per_ff and ls.front_footage and costs.fenced_pct:
                amount = lots * ls.fence_cost_per_ff * ls.front_footage * costs.fenced_pct
                sched.total_fencing += amount
                lump(sched.fencing, amount, delivery)
            if ls.urd_per_lot:
                amount = lots * ls.urd_per_lot
                sched.total_urd += amount
                lump(sched.urd, amount, delivery)
            if ls.lots_per_streetlight > 0:
                amount = (lots / ls.lots_per_streetlight) * costs.cost_per_streetlight
                sched.total_streetlights += amount
                lump(sched.streetlights, amount, delivery)

            lump(sched.lot_deliveries, lots, delivery)
    return sched
