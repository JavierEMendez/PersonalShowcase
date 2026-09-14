"""District bond reimbursements (MUD and WCID).

At each bond period the district can have issued `debt_ratio` of cumulative assessed value as
of three months earlier. The increment since the last issuance, times the developer's share, is
reimbursed to the developer. A receivables fee on each reimbursement is a below-the-line cost.
Bonds are never repaid by the developer.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.underwriting.inputs import Bond
from core.underwriting.ledger import MAX_MONTHS, zeros

AV_LAG_MONTHS = 3


@dataclass
class BondProceeds:
    issuances: list[tuple[int, float]] = field(default_factory=list)
    revenue: list[float] = field(default_factory=zeros)
    fees: list[float] = field(default_factory=zeros)
    total: float = 0.0
    total_fees: float = 0.0


def compute_bond(bond: Bond, cumulative_av: list[float]) -> BondProceeds:
    out = BondProceeds()
    if not bond.toggle or bond.first_bond_period <= 0 or bond.debt_ratio <= 0:
        return out

    period = bond.first_bond_period
    prev_to_date = 0.0
    while period <= MAX_MONTHS:
        lagged = max(0, period - AV_LAG_MONTHS)
        bonds_to_date = cumulative_av[lagged] * bond.debt_ratio
        issued_now = max(0.0, bonds_to_date - prev_to_date)
        proceeds = issued_now * bond.pct_to_dev
        if proceeds > 0:
            out.issuances.append((period, proceeds))
        prev_to_date = bonds_to_date
        if bond.bond_interval <= 0:
            break
        period += bond.bond_interval

    for month, amount in out.issuances:
        out.revenue[month] += amount
        out.fees[month] += amount * bond.receivables_fee
    out.total = sum(amount for _, amount in out.issuances)
    out.total_fees = sum(out.fees[1:])
    return out
