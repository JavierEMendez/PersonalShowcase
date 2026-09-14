"""Run the MPC land model end to end.

Order of calculation, kept from the source model:
1. Land and net-outs, 2. infrastructure cost rows, 3. lot allocation and project length,
4. schedules (infrastructure spreads, sections), 5. lot revenue and pods, 6. assessed value,
7. district bonds, 8. operating costs, DMF, and contingency, 9. summary and IRR.
"""

from __future__ import annotations

from core.underwriting.allocation import allocate_lots
from core.underwriting.av import compute_av
from core.underwriting.bonds import compute_bond
from core.underwriting.infrastructure import compute_infrastructure
from core.underwriting.inputs import DealInputs
from core.underwriting.land import compute_land
from core.underwriting.ledger import add_into, total, zeros
from core.underwriting.lookups import effective_lookups
from core.underwriting.netouts import compute_netouts
from core.underwriting.opex import compute_contingency, compute_dmf, compute_operating
from core.underwriting.revenue import compute_lot_revenue, compute_pods
from core.underwriting.sections import (
    project_length,
    schedule_infrastructure,
    schedule_sections,
)
from core.underwriting.summary import EngineState, Outputs, build_outputs


def run(inputs: DealInputs) -> Outputs:
    tract, costs, revenue = inputs.tract, inputs.costs, inputs.revenue
    lookups = effective_lookups(inputs.lookups)

    acreage = compute_netouts(tract, lookups)
    land = compute_land(tract, costs.takedowns)
    infra = compute_infrastructure(tract, costs, lookups, acreage)
    allocation = allocate_lots(costs.lot_sizes, acreage.residential_developable)
    project_months = project_length(infra, costs.lot_sizes, allocation)

    ledger = schedule_infrastructure(land, infra)
    sections = schedule_sections(costs.lot_sizes, allocation, costs)
    lot_revenue = compute_lot_revenue(costs.lot_sizes, allocation, revenue, costs)
    pods = compute_pods(tract, revenue, project_months)
    av = compute_av(costs.lot_sizes, allocation, revenue, pods, project_months)
    mud = compute_bond(revenue.mud_bond, av.cumulative)
    wcid = compute_bond(revenue.wcid_bond, av.cumulative)

    rev_monthly = zeros()
    add_into(rev_monthly, lot_revenue.revenue, pods.residential, pods.commercial)
    add_into(rev_monthly, mud.revenue, wcid.revenue)

    op = compute_operating(costs, infra, lot_revenue, av, total(rev_monthly), project_months)
    dmf, dmf_total = compute_dmf(costs, ledger, sections, lot_revenue, op)
    contingency, contingency_total = compute_contingency(
        costs, infra, ledger, sections, lot_revenue, op
    )

    cost_monthly = zeros()
    add_into(
        cost_monthly,
        ledger.land,
        ledger.plants,
        ledger.amenities,
        ledger.detention,
        ledger.landscaping,
        ledger.other,
        ledger.roads,
    )
    add_into(
        cost_monthly,
        sections.dev_cost,
        sections.landscaping,
        sections.fencing,
        sections.urd,
        sections.streetlights,
        lot_revenue.brokerage,
        lot_revenue.closing,
        lot_revenue.taxes,
        lot_revenue.mailboxes,
    )
    add_into(cost_monthly, mud.fees, wcid.fees, lot_revenue.site_work)
    add_into(
        cost_monthly,
        op.marketing,
        op.prof_svc,
        op.personnel,
        op.marketing_personnel,
        op.legal,
        op.insurance,
        op.bookkeeping,
        op.mud_hoa,
        op.road_streetlights,
    )
    add_into(cost_monthly, dmf, contingency)

    return build_outputs(
        EngineState(
            inputs=inputs,
            acreage=acreage,
            land=land,
            infra=infra,
            allocation=allocation,
            project_months=project_months,
            ledger=ledger,
            sections=sections,
            lot_revenue=lot_revenue,
            pods=pods,
            av=av,
            mud=mud,
            wcid=wcid,
            op=op,
            dmf=dmf,
            dmf_total=dmf_total,
            contingency=contingency,
            contingency_total=contingency_total,
            rev_monthly=rev_monthly,
            cost_monthly=cost_monthly,
        )
    )
