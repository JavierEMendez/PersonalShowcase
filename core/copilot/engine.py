"""Run the multifamily model end to end.

Order: rent roll to market, renovation program, monthly operations and NOI, loan sizing on year 1
NOI, debt schedule, sources and uses, exit on forward NOI, unlevered and levered cash flows,
waterfall, then annual and summary tables. The engine runs monthly for the hold plus twelve
forward months, so the exit values the next year's NOI.
"""

from __future__ import annotations

from core.copilot.capital_stack import build_capital_stack
from core.copilot.debt import build_debt, size_loan
from core.copilot.inputs import CopilotInputs
from core.copilot.operations import build_operations
from core.copilot.renovation import build_renovation
from core.copilot.rent_roll import build_rent_roll
from core.copilot.schedule import add_months, annual_sum, year_of
from core.copilot.summary import (
    AnnualRow,
    CopilotOutputs,
    ExitSummary,
    FloorPlanRow,
    LoanSummary,
    MonthlyRow,
    RenovationSummary,
    Returns,
    SourcesUses,
    Summary,
    WaterfallSummary,
)
from core.copilot.waterfall import run_waterfall
from core.underwriting.irr import xirr

FORWARD_MONTHS = 12


def _ratio(a: float, b: float) -> float:
    return a / b if b else 0.0


def run(inputs: CopilotInputs) -> CopilotOutputs:
    acq, loan_in, prop = inputs.acquisition, inputs.loan, inputs.property
    hold = acq.hold_months
    months = hold + FORWARD_MONTHS
    years = hold // 12

    roll = build_rent_roll(prop, inputs.revenue, months)
    reno = build_renovation(
        inputs.renovation, inputs.revenue, months, roll.avg_market_rent_by_month
    )
    ops = build_operations(inputs, months, roll, reno)

    noi_year1 = annual_sum(ops.noi, 1)
    # Taxes reassess to the price paid, so the cap rate at the ask uses NOI re-taxed at the ask.
    cap_at_ask: float | None = None
    if acq.asking_price:
        at_ask = inputs.model_copy(deep=True)
        at_ask.acquisition.purchase_price = acq.asking_price
        ask_noi = annual_sum(build_operations(at_ask, months, roll, reno).noi, 1)
        cap_at_ask = ask_noi / acq.asking_price
    sizing = size_loan(loan_in, acq.purchase_price, noi_year1)
    debt = build_debt(loan_in, sizing.amount, months)
    stack = build_capital_stack(inputs, sizing.amount)

    forward_noi = sum(ops.noi[hold + 1 : hold + 1 + FORWARD_MONTHS])
    gross_value = forward_noi / inputs.exit.cap_rate if inputs.exit.cap_rate else 0.0
    sale_costs = gross_value * inputs.exit.sale_costs_pct
    payoff = debt.payoff_at(hold)
    net_proceeds = gross_value - sale_costs

    am_fee_monthly = stack.equity * inputs.equity.asset_management_fee_pct / 12
    dates = [add_months(acq.closing_date, m) for m in range(0, hold + 1)]
    unlevered = [0.0] * (hold + 1)
    levered = [0.0] * (hold + 1)
    unlevered[0] = -(stack.total_uses - stack.loan_fees)
    levered[0] = -stack.equity
    cash_flow = [0.0] * (months + 1)
    for m in range(1, hold + 1):
        after_reserves = ops.noi[m] - ops.reserves[m]
        cash_flow[m] = after_reserves - debt.payment[m] - am_fee_monthly
        unlevered[m] = after_reserves
        levered[m] = cash_flow[m]
    unlevered[hold] += net_proceeds
    levered[hold] += net_proceeds - payoff

    wf = run_waterfall(inputs.equity, stack.lp_equity, stack.gp_equity, levered, dates)

    annual: list[AnnualRow] = []
    for y in range(1, years + 1):
        ds = annual_sum(debt.payment, y)
        noi = annual_sum(ops.noi, y)
        cf = annual_sum(cash_flow, y)
        annual.append(
            AnnualRow(
                year=y,
                gpr=round(annual_sum(ops.gpr, y)),
                loss_to_lease=round(annual_sum(ops.loss_to_lease, y)),
                renovation_premium=round(annual_sum(ops.renovation_premium, y)),
                renovation_vacancy=round(annual_sum(ops.renovation_vacancy, y)),
                vacancy=round(annual_sum(ops.vacancy, y)),
                concessions=round(annual_sum(ops.concessions, y)),
                non_revenue=round(annual_sum(ops.non_revenue, y)),
                bad_debt=round(annual_sum(ops.bad_debt, y)),
                net_rental=round(annual_sum(ops.net_rental, y)),
                other_income=round(annual_sum(ops.other_income, y)),
                egi=round(annual_sum(ops.egi, y)),
                controllable=round(annual_sum(ops.controllable_total, y)),
                taxes=round(annual_sum(ops.taxes, y)),
                management_fee=round(annual_sum(ops.management_fee, y)),
                opex=round(annual_sum(ops.opex, y)),
                noi=round(noi),
                reserves=round(annual_sum(ops.reserves, y)),
                debt_service=round(ds),
                asset_management_fee=round(am_fee_monthly * 12),
                cash_flow=round(cf),
                dscr=noi / ds if ds else None,
                cash_on_cash=_ratio(cf, stack.equity),
            )
        )

    monthly = [
        MonthlyRow(
            month=m,
            date=add_months(acq.closing_date, m),
            year=year_of(m),
            gpr=round(ops.gpr[m]),
            loss_to_lease=round(ops.loss_to_lease[m]),
            renovation_premium=round(ops.renovation_premium[m]),
            renovation_vacancy=round(ops.renovation_vacancy[m]),
            vacancy=round(ops.vacancy[m]),
            concessions=round(ops.concessions[m]),
            non_revenue=round(ops.non_revenue[m]),
            bad_debt=round(ops.bad_debt[m]),
            other_income=round(ops.other_income[m]),
            egi=round(ops.egi[m]),
            controllable=round(ops.controllable_total[m]),
            taxes=round(ops.taxes[m]),
            management_fee=round(ops.management_fee[m]),
            noi=round(ops.noi[m]),
            reserves=round(ops.reserves[m]),
            interest=round(debt.interest[m]),
            principal=round(debt.principal[m]),
            asset_management_fee=round(am_fee_monthly),
            cash_flow=round(cash_flow[m]),
            loan_balance=round(debt.balance[m]),
            renovation_spend=round(reno.spend[m]),
            units_completed=round(reno.completed[m]),
        )
        for m in range(1, hold + 1)
    ]

    dscrs = [row.dscr for row in annual if row.dscr is not None]
    min_dscr = min(dscrs) if dscrs else None
    io_ds = sizing.amount * loan_in.rate
    amort_ds = debt.amortizing_payment * 12
    total_distributions = sum(levered[1:])
    reno_in = inputs.renovation
    opex_year1 = annual_sum(ops.opex, 1)
    price_per_sf = acq.purchase_price / prop.rentable_sf if prop.rentable_sf else 0.0

    summary = Summary(
        units=prop.units,
        occupied=prop.occupied,
        occupancy=_ratio(prop.occupied, prop.units),
        rentable_sf=round(prop.rentable_sf),
        avg_in_place_rent=round(roll.avg_in_place_rent),
        avg_market_rent=round(roll.avg_market_rent),
        loss_to_lease_pct=roll.loss_to_lease_pct,
        purchase_price=round(acq.purchase_price),
        asking_price=round(acq.asking_price) if acq.asking_price else None,
        discount_to_ask=(1 - acq.purchase_price / acq.asking_price) if acq.asking_price else None,
        price_per_unit=round(_ratio(acq.purchase_price, prop.units)),
        price_per_sf=round(price_per_sf),
        going_in_cap=_ratio(noi_year1, acq.purchase_price),
        cap_at_ask=cap_at_ask,
        noi_year1=round(noi_year1),
        debt_yield=_ratio(noi_year1, sizing.amount),
        ltv=_ratio(sizing.amount, acq.purchase_price),
        dscr_year1=annual[0].dscr if annual else None,
        min_dscr=min_dscr,
        covenant_holds=min_dscr is None or min_dscr >= loan_in.covenant_dscr,
        levered_irr=xirr(levered, dates),
        unlevered_irr=xirr(unlevered, dates),
        equity_multiple=_ratio(total_distributions, stack.equity),
        lp_irr=wf.lp_irr,
        exit_value=round(gross_value),
        hold_months=hold,
        opex_per_unit=round(_ratio(opex_year1, prop.units)),
        taxes_share_of_opex=_ratio(annual_sum(ops.taxes, 1), opex_year1),
    )

    lp_by_year = [round(annual_sum(wf.lp_flows, y)) for y in range(1, years + 1)]
    gp_by_year = [round(annual_sum(wf.gp_flows, y)) for y in range(1, years + 1)]
    tiers = inputs.equity.tiers
    residual = inputs.equity.residual_lp_split * 100
    tier_labels = ["Preferred return and capital"]
    for t in tiers:
        lp, hurdle = t.lp_split * 100, t.hurdle_irr * 100
        tier_labels.append(f"{lp:.0f} / {100 - lp:.0f} to {hurdle:.0f}% LP IRR")
    tier_labels.append(f"{residual:.0f} / {100 - residual:.0f} thereafter")

    return CopilotOutputs(
        floor_plans=[FloorPlanRow(**fp.model_dump()) for fp in prop.floor_plans],
        summary=summary,
        sources_uses=SourcesUses(
            purchase_price=round(stack.purchase_price),
            closing_costs=round(stack.closing_costs),
            loan_fees=round(stack.loan_fees),
            acquisition_fee=round(stack.acquisition_fee),
            renovation_budget=round(stack.renovation_budget),
            other_capital=round(stack.other_capital),
            construction_management_fee=round(stack.construction_management_fee),
            contingency=round(stack.contingency),
            capital_budget=round(stack.capital_budget),
            total_uses=round(stack.total_uses),
            loan=round(stack.loan),
            equity=round(stack.equity),
            lp_equity=round(stack.lp_equity),
            gp_equity=round(stack.gp_equity),
        ),
        loan=LoanSummary(
            amount=round(sizing.amount),
            ltv=_ratio(sizing.amount, acq.purchase_price),
            binding=sizing.binding,
            by_ltv=round(sizing.by_ltv),
            by_dscr=round(sizing.by_dscr),
            by_debt_yield=round(sizing.by_debt_yield),
            rate=loan_in.rate,
            io_months=loan_in.io_months,
            amortization_years=loan_in.amortization_years,
            term_months=loan_in.term_months,
            maturity=add_months(acq.closing_date, loan_in.term_months),
            io_expiry=add_months(acq.closing_date, loan_in.io_months),
            annual_debt_service_io=round(io_ds),
            annual_debt_service_amortizing=round(amort_ds),
            debt_yield=_ratio(noi_year1, sizing.amount),
            payoff=round(payoff),
            covenant_dscr=loan_in.covenant_dscr,
        ),
        exit=ExitSummary(
            month=hold,
            date=dates[hold],
            forward_noi=round(forward_noi),
            cap_rate=inputs.exit.cap_rate,
            gross_value=round(gross_value),
            value_per_unit=round(_ratio(gross_value, prop.units)),
            sale_costs=round(sale_costs),
            net_proceeds=round(net_proceeds),
            loan_payoff=round(payoff),
            net_after_debt=round(net_proceeds - payoff),
        ),
        returns=Returns(
            unlevered_irr=xirr(unlevered, dates),
            levered_irr=xirr(levered, dates),
            equity_multiple=_ratio(total_distributions, stack.equity),
            lp_irr=wf.lp_irr,
            lp_multiple=wf.lp_multiple,
            gp_irr=wf.gp_irr,
            gp_multiple=wf.gp_multiple,
            promote=round(wf.promote),
            profit=round(total_distributions - stack.equity),
            average_cash_on_cash=(
                sum(r.cash_on_cash for r in annual) / len(annual) if annual else 0.0
            ),
        ),
        renovation=RenovationSummary(
            units=reno_in.units,
            cost_per_unit=round(reno_in.cost_per_unit),
            premium_per_month=round(reno_in.premium_per_month),
            return_on_cost=_ratio(reno_in.premium_per_month * 12, reno_in.cost_per_unit),
            start_month=reno_in.start_month,
            end_month=reno.end_month,
            pace_per_month=reno.pace,
            total_cost=round(reno.total_cost),
        ),
        waterfall=WaterfallSummary(
            tier_labels=tier_labels,
            tier_totals=[round(t) for t in wf.tier_totals],
            lp_by_year=lp_by_year,
            gp_by_year=gp_by_year,
        ),
        operating_per_unit={
            **{line: round(inputs.operating.per_unit[line]) for line in ops.lines},
            "Real estate taxes": round(_ratio(annual_sum(ops.taxes, 1), prop.units)),
            "Management fee": round(_ratio(annual_sum(ops.management_fee, 1), prop.units)),
        },
        annual=annual,
        monthly=monthly,
    )
