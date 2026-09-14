"""Rent roll to market: gross potential rent and the loss to lease that burns off on rollover."""

from __future__ import annotations

from dataclasses import dataclass, field

from core.copilot.inputs import Property, RevenueAssumptions
from core.copilot.schedule import monthly_growth, zeros


@dataclass
class RentRoll:
    units: int
    occupied: int
    avg_in_place_rent: float
    avg_market_rent: float
    loss_to_lease_pct: float
    gpr: list[float] = field(default_factory=list)  # gross potential rent at market, by month
    loss_to_lease: list[float] = field(default_factory=list)  # negative
    avg_market_rent_by_month: list[float] = field(default_factory=list)


def build_rent_roll(prop: Property, rev: RevenueAssumptions, months: int) -> RentRoll:
    units = prop.units
    gpr0 = sum(fp.units * fp.market_rent for fp in prop.floor_plans)
    in_place0 = sum(fp.units * fp.in_place_rent for fp in prop.floor_plans)
    gap0 = gpr0 - in_place0

    roll = RentRoll(
        units=units,
        occupied=prop.occupied,
        avg_in_place_rent=in_place0 / units if units else 0.0,
        avg_market_rent=gpr0 / units if units else 0.0,
        loss_to_lease_pct=gap0 / gpr0 if gpr0 else 0.0,
        gpr=zeros(months),
        loss_to_lease=zeros(months),
        avg_market_rent_by_month=zeros(months),
    )
    burn = rev.loss_to_lease_burn_months
    for m in range(1, months + 1):
        g = monthly_growth(rev.market_rent_growth, m)
        gpr = gpr0 * g
        # The in-place gap closes linearly as leases roll, then a steady gap to market remains.
        remaining = max(0.0, 1 - (m - 1) / burn) if burn > 0 else 0.0
        gap = max(gap0 * remaining, rev.steady_loss_to_lease * gpr)
        roll.gpr[m] = gpr
        roll.loss_to_lease[m] = -gap
        roll.avg_market_rent_by_month[m] = gpr / units if units else 0.0
    return roll
