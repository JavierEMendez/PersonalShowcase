"""Lot allocation: residential developable acres split across active lot sizes.

Each active lot size consumes `pace * 18 / yield` acres per 18-month section. Acres are
allocated in proportion to that consumption, so faster or larger lots take more land. Whole
sections are counted first; the remainder becomes a partial final section.
"""

from __future__ import annotations

import math

from pydantic import BaseModel

from core.underwriting.inputs import LotSize

SECTION_MONTHS = 18


class LotAllocation(BaseModel):
    front_footage: float
    on: bool
    yield_per_ac: float
    pace: float
    lots_18mo: float
    acres_18mo: float
    allocated_acres: float
    full_sections: int
    last_section_acres: float
    last_lots: int
    total_lots: int
    dev_cost_per_lot: float


def section_lots(lot: LotAllocation) -> list[tuple[int, float]]:
    """(section number, lots delivered) for every section of a lot size, partial last."""
    sections = [(k, lot.lots_18mo) for k in range(1, lot.full_sections + 1)]
    if lot.last_lots > 0:
        sections.append((lot.full_sections + 1, float(lot.last_lots)))
    return sections


def allocate_lots(lot_sizes: list[LotSize], residential_developable: float) -> list[LotAllocation]:
    active = [ls for ls in lot_sizes if ls.on and ls.pace > 0 and ls.yield_per_ac > 0]
    sum_acres_18mo = sum(ls.pace * SECTION_MONTHS / ls.yield_per_ac for ls in active)

    rows: list[LotAllocation] = []
    for ls in lot_sizes:
        if not ls.on:
            rows.append(
                LotAllocation(
                    front_footage=ls.front_footage,
                    on=False,
                    yield_per_ac=ls.yield_per_ac,
                    pace=ls.pace,
                    lots_18mo=0.0,
                    acres_18mo=0.0,
                    allocated_acres=0.0,
                    full_sections=0,
                    last_section_acres=0.0,
                    last_lots=0,
                    total_lots=0,
                    dev_cost_per_lot=0.0,
                )
            )
            continue

        lots_18mo = ls.pace * SECTION_MONTHS
        acres_18mo = lots_18mo / ls.yield_per_ac if ls.yield_per_ac else 0.0
        if sum_acres_18mo > 0 and acres_18mo > 0:
            allocated = residential_developable * (acres_18mo / sum_acres_18mo)
        else:
            allocated = 0.0
        full_sections = int(allocated / acres_18mo) if acres_18mo > 0 else 0
        last_acres = allocated - full_sections * acres_18mo if acres_18mo > 0 else 0.0
        last_lots = math.floor(last_acres * ls.yield_per_ac) if ls.yield_per_ac else 0
        total_lots = math.floor(full_sections * lots_18mo + last_acres * ls.yield_per_ac)

        rows.append(
            LotAllocation(
                front_footage=ls.front_footage,
                on=True,
                yield_per_ac=ls.yield_per_ac,
                pace=ls.pace,
                lots_18mo=lots_18mo,
                acres_18mo=acres_18mo,
                allocated_acres=allocated,
                full_sections=full_sections,
                last_section_acres=last_acres,
                last_lots=last_lots,
                total_lots=total_lots,
                # Section development cost per lot: water, sewer, drainage and paving per FF.
                dev_cost_per_lot=(ls.wsd_per_ff + ls.paving_per_ff) * ls.front_footage,
            )
        )
    return rows
