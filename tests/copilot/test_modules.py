"""Hand-checked cases for each module of the multifamily model."""

import datetime

import pytest

from core.copilot.capital_stack import build_capital_stack
from core.copilot.debt import annual_constant, build_debt, size_loan
from core.copilot.inputs import (
    Acquisition,
    CapitalBudget,
    CopilotInputs,
    Equity,
    FloorPlan,
    Loan,
    Property,
    Renovation,
    RevenueAssumptions,
    WaterfallTier,
)
from core.copilot.renovation import build_renovation
from core.copilot.rent_roll import build_rent_roll
from core.copilot.schedule import add_months, annual_sum, monthly_growth, pmt, yearly_step
from core.copilot.waterfall import run_waterfall


def one_plan(units: int = 100, in_place: float = 1_000.0, market: float = 1_100.0) -> Property:
    return Property(
        floor_plans=[
            FloorPlan(
                code="A",
                unit_type="1 x 1",
                units=units,
                sf=800,
                occupied=units,
                in_place_rent=in_place,
                market_rent=market,
            )
        ]
    )


def test_schedule_helpers() -> None:
    assert add_months(datetime.date(2026, 1, 31), 1) == datetime.date(2026, 2, 28)
    assert add_months(datetime.date(2026, 3, 1), 12) == datetime.date(2027, 3, 1)
    assert monthly_growth(0.03, 1) == 1.0
    assert monthly_growth(0.03, 13) == pytest.approx(1.03)
    assert yearly_step(0.025, 12) == 1.0
    assert yearly_step(0.025, 13) == pytest.approx(1.025)
    assert pmt(0.05 / 12, 360, 100_000) == pytest.approx(536.82, abs=0.01)
    assert annual_sum([0.0] + [1.0] * 24, 2) == 12


def test_rent_roll_burns_loss_to_lease_then_holds_steady() -> None:
    rev = RevenueAssumptions(
        market_rent_growth=0.0, loss_to_lease_burn_months=10, steady_loss_to_lease=0.01
    )
    roll = build_rent_roll(one_plan(), rev, 24)
    assert roll.avg_in_place_rent == 1_000
    assert roll.avg_market_rent == 1_100
    assert roll.loss_to_lease_pct == pytest.approx(100 / 1_100)
    assert roll.gpr[1] == pytest.approx(110_000)
    assert roll.loss_to_lease[1] == pytest.approx(-10_000)  # full gap in month 1
    assert roll.loss_to_lease[6] == pytest.approx(-5_000)  # half burned
    assert roll.loss_to_lease[11] == pytest.approx(-1_100)  # steady 1% of GPR
    assert roll.loss_to_lease[24] == pytest.approx(-1_100)


def test_rent_roll_grows_monthly() -> None:
    roll = build_rent_roll(one_plan(), RevenueAssumptions(market_rent_growth=0.03), 13)
    assert roll.gpr[13] == pytest.approx(110_000 * 1.03)


def test_renovation_pace_downtime_and_premium() -> None:
    reno = Renovation(
        units=24,
        cost_per_unit=10_000,
        premium_per_month=100,
        start_month=3,
        duration_months=12,
        downtime_months=1,
    )
    rev = RevenueAssumptions(market_rent_growth=0.0)
    program = build_renovation(reno, rev, 24, [1_000.0] * 25)
    assert program.pace == 2
    assert program.end_month == 14
    assert (
        program.started[2] == 0
        and program.started[3] == 2
        and program.started[14] == 2
        and program.started[15] == 0
    )
    assert program.offline[3] == 2 and program.offline[15] == 0
    # One month of downtime: none complete at the start of month 3, two by month 4.
    assert program.completed[3] == 0 and program.completed[4] == 2 and program.completed[20] == 24
    assert program.premium[4] == pytest.approx(200)
    assert program.premium[24] == pytest.approx(2_400)
    assert sum(program.spend) == pytest.approx(240_000)
    assert program.total_cost == 240_000


def test_loan_sizing_takes_the_lesser_constraint() -> None:
    loan = Loan(ltv_max=0.65, dscr_min=1.25, debt_yield_min=0.075, rate=0.06, amortization_years=30)
    constant = annual_constant(loan)
    assert constant == pytest.approx(0.07195, abs=1e-4)
    sizing = size_loan(loan, 10_000_000, 600_000)
    assert sizing.by_ltv == 6_500_000
    assert sizing.by_dscr == pytest.approx(600_000 / 1.25 / constant)
    assert sizing.by_debt_yield == pytest.approx(8_000_000)
    assert sizing.binding == "LTV"
    assert sizing.amount == 6_500_000
    held = size_loan(loan.model_copy(update={"amount_override": 5_000_000.0}), 10_000_000, 600_000)
    assert held.amount == 5_000_000 and held.binding == "Held"


def test_debt_schedule_io_then_amortizing() -> None:
    loan = Loan(rate=0.06, io_months=12, amortization_years=30)
    sched = build_debt(loan, 1_000_000, 36)
    assert sched.interest[1] == pytest.approx(5_000)
    assert sched.principal[12] == 0
    assert sched.balance[12] == 1_000_000
    assert sched.payment[13] == pytest.approx(pmt(0.005, 360, 1_000_000))
    assert sched.principal[13] == pytest.approx(sched.payment[13] - 5_000)
    assert sched.balance[36] < 1_000_000
    assert sched.payoff_at(36) == sched.balance[36]


def test_capital_stack_foots() -> None:
    inputs = CopilotInputs(
        property=one_plan(),
        renovation=Renovation(units=10, cost_per_unit=5_000),
        capital=CapitalBudget(
            exterior=100_000,
            deferred_maintenance=50_000,
            contingency_pct=0.10,
            construction_management_fee_pct=0.05,
        ),
        acquisition=Acquisition(
            purchase_price=10_000_000, closing_costs_pct=0.01, acquisition_fee_pct=0.01
        ),
        loan=Loan(fee_pct=0.01),
        equity=Equity(lp_share=0.9),
    )
    stack = build_capital_stack(inputs, 6_000_000)
    base = 50_000 + 150_000
    cm = base * 0.05
    assert stack.construction_management_fee == pytest.approx(cm)
    assert stack.contingency == pytest.approx((base + cm) * 0.10)
    assert stack.capital_budget == pytest.approx(base + cm + (base + cm) * 0.10)
    assert stack.total_uses == pytest.approx(
        10_000_000 + 100_000 + 60_000 + 100_000 + stack.capital_budget
    )
    assert stack.equity == pytest.approx(stack.total_uses - 6_000_000)
    assert stack.lp_equity + stack.gp_equity == pytest.approx(stack.equity)


def test_waterfall_pref_then_promote() -> None:
    equity = Equity(
        lp_share=0.9,
        preferred_return=0.08,
        tiers=[WaterfallTier(hurdle_irr=0.12, lp_split=0.7)],
        residual_lp_split=0.5,
    )
    start = datetime.date(2026, 1, 1)
    dates = [add_months(start, m) for m in range(0, 13)]
    # One distribution after twelve months: 1,000 of capital returns 1,300.
    distributions = [0.0] * 13
    distributions[12] = 1_300.0
    result = run_waterfall(equity, 900.0, 100.0, distributions, dates)
    pref_total = 1_000 * (1.08 ** (12 / 12))
    assert result.tier_totals[0] == pytest.approx(pref_total, rel=1e-6)
    # Up to a 12% LP IRR the split is 70/30; the remaining cash above that is 50/50.
    lp_hurdle = 900 * 1.12
    tier2_cash = (lp_hurdle - pref_total * 0.9) / 0.7
    assert result.tier_totals[1] == pytest.approx(tier2_cash, rel=1e-6)
    assert result.tier_totals[2] == pytest.approx(1_300 - pref_total - tier2_cash, rel=1e-6)
    lp_cash = pref_total * 0.9 + tier2_cash * 0.7 + result.tier_totals[2] * 0.5
    assert result.lp_flows[12] == pytest.approx(lp_cash, rel=1e-6)
    assert result.gp_flows[12] == pytest.approx(1_300 - lp_cash, rel=1e-6)
    assert result.lp_multiple == pytest.approx(lp_cash / 900)
    assert result.promote == pytest.approx(result.gp_flows[12] - 130)
    assert result.lp_irr is not None and 0.12 < result.lp_irr < 0.30


def test_waterfall_short_of_pref_pays_pro_rata() -> None:
    equity = Equity(lp_share=0.9)
    dates = [add_months(datetime.date(2026, 1, 1), m) for m in range(0, 13)]
    distributions = [0.0] * 13
    distributions[12] = 500.0
    result = run_waterfall(equity, 900.0, 100.0, distributions, dates)
    assert result.lp_flows[12] == pytest.approx(450)
    assert result.gp_flows[12] == pytest.approx(50)
    assert result.promote == pytest.approx(0)
