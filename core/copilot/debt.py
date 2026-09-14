"""Acquisition loan.

Sized on the lesser of LTV, DSCR and debt yield; interest-only, then amortizing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.copilot.inputs import Loan
from core.copilot.schedule import pmt, zeros


def annual_constant(loan: Loan) -> float:
    """Annual debt service per dollar of loan on a fully amortizing schedule."""
    return pmt(loan.rate / 12, loan.amortization_years * 12, 1.0) * 12


@dataclass
class LoanSizing:
    by_ltv: float
    by_dscr: float
    by_debt_yield: float
    amount: float
    binding: str


def size_loan(loan: Loan, purchase_price: float, noi_year1: float) -> LoanSizing:
    by_ltv = purchase_price * loan.ltv_max
    constant = annual_constant(loan)
    by_dscr = noi_year1 / loan.dscr_min / constant if constant else 0.0
    by_dy = noi_year1 / loan.debt_yield_min if loan.debt_yield_min else by_ltv
    if loan.amount_override is not None:
        return LoanSizing(by_ltv, by_dscr, by_dy, loan.amount_override, "Held")
    candidates = [("LTV", by_ltv), ("DSCR", by_dscr), ("Debt yield", by_dy)]
    binding, amount = min(candidates, key=lambda c: c[1])
    return LoanSizing(by_ltv, by_dscr, by_dy, amount, binding)


@dataclass
class DebtSchedule:
    amount: float
    interest: list[float] = field(default_factory=list)
    principal: list[float] = field(default_factory=list)
    payment: list[float] = field(default_factory=list)
    balance: list[float] = field(default_factory=list)  # end of month
    amortizing_payment: float = 0.0

    def payoff_at(self, month: int) -> float:
        return self.balance[month] if 0 <= month < len(self.balance) else 0.0


def build_debt(loan: Loan, amount: float, months: int) -> DebtSchedule:
    sched = DebtSchedule(
        amount=amount,
        interest=zeros(months),
        principal=zeros(months),
        payment=zeros(months),
        balance=zeros(months),
    )
    sched.balance[0] = amount
    monthly_rate = loan.rate / 12
    sched.amortizing_payment = pmt(monthly_rate, loan.amortization_years * 12, amount)
    balance = amount
    for m in range(1, months + 1):
        interest = balance * monthly_rate
        if m <= loan.io_months:
            principal = 0.0
        else:
            principal = min(balance, sched.amortizing_payment - interest)
        balance -= principal
        sched.interest[m] = interest
        sched.principal[m] = principal
        sched.payment[m] = interest + principal
        sched.balance[m] = balance
    return sched
