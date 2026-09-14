"""Unit interior renovation program: pace, downtime, premiums, and capital spend by month."""

from __future__ import annotations

from dataclasses import dataclass, field

from core.copilot.inputs import Renovation, RevenueAssumptions
from core.copilot.schedule import monthly_growth, zeros


@dataclass
class RenovationProgram:
    started: list[float] = field(default_factory=list)  # units starting renovation in the month
    completed: list[float] = field(
        default_factory=list
    )  # cumulative units completed at month start
    offline: list[float] = field(default_factory=list)  # units out of service in the month
    premium: list[float] = field(default_factory=list)  # premium rent earned in the month
    spend: list[float] = field(default_factory=list)  # renovation capital drawn in the month
    total_cost: float = 0.0
    pace: float = 0.0
    end_month: int = 0


def build_renovation(
    reno: Renovation, rev: RevenueAssumptions, months: int, avg_market_rent: list[float]
) -> RenovationProgram:
    program = RenovationProgram(
        started=zeros(months),
        completed=zeros(months),
        offline=zeros(months),
        premium=zeros(months),
        spend=zeros(months),
    )
    if reno.units <= 0 or reno.duration_months <= 0:
        return program
    program.pace = reno.units / reno.duration_months
    program.end_month = reno.start_month + reno.duration_months - 1
    program.total_cost = reno.units * reno.cost_per_unit
    downtime = max(1, reno.downtime_months)

    for m in range(reno.start_month, min(program.end_month, months) + 1):
        program.started[m] = program.pace
        program.spend[m] = program.pace * reno.cost_per_unit

    done = 0.0
    for m in range(1, months + 1):
        program.completed[m] = done
        # Units started in the last `downtime` months are offline this month.
        window = range(max(1, m - downtime + 1), m + 1)
        program.offline[m] = sum(program.started[k] for k in window)
        program.premium[m] = (
            done * reno.premium_per_month * monthly_growth(rev.market_rent_growth, m)
        )
        finished_this_month = program.started[m - downtime + 1] if m - downtime + 1 >= 1 else 0.0
        done += finished_this_month
    return program
