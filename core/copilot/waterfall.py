"""LP/GP distribution waterfall, run monthly.

Tier 1: a preferred return accruing monthly on unreturned capital, and return of capital, paid
pro rata to LP and GP. Then each promote tier splits cash at its LP share until the LP has
earned the tier's hurdle IRR, tracked as an accrual balance. Cash above the last hurdle splits
at the residual share. The GP also receives the acquisition and asset management fees outside
the waterfall.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field

from core.copilot.inputs import Equity
from core.underwriting.irr import xirr


@dataclass
class WaterfallResult:
    lp_flows: list[float] = field(default_factory=list)  # index 0 = closing
    gp_flows: list[float] = field(default_factory=list)
    tier_totals: list[float] = field(default_factory=list)  # cash through each tier
    lp_irr: float | None = None
    gp_irr: float | None = None
    lp_multiple: float = 0.0
    gp_multiple: float = 0.0
    promote: float = 0.0  # GP cash above its pro rata share


def run_waterfall(
    equity: Equity,
    lp_equity: float,
    gp_equity: float,
    distributions: list[float],
    dates: list[datetime.date],
) -> WaterfallResult:
    """`distributions[m]` is the cash to equity in month m (m >= 1); index 0 is ignored."""
    total_equity = lp_equity + gp_equity
    months = len(distributions) - 1
    lp = [0.0] * (months + 1)
    gp = [0.0] * (months + 1)
    lp[0], gp[0] = -lp_equity, -gp_equity
    tiers = equity.tiers
    tier_totals = [0.0] * (len(tiers) + 2)

    pref_rate = (1 + equity.preferred_return) ** (1 / 12) - 1
    hurdle_rates = [(1 + t.hurdle_irr) ** (1 / 12) - 1 for t in tiers]
    pref_balance = total_equity  # capital plus accrued preferred return still owed
    hurdle_balances = [lp_equity for _ in tiers]  # LP capital accruing at each hurdle rate

    for m in range(1, months + 1):
        pref_balance *= 1 + pref_rate
        hurdle_balances = [b * (1 + r) for b, r in zip(hurdle_balances, hurdle_rates, strict=True)]
        remaining = distributions[m]
        if remaining <= 0:
            continue
        # Tier 1: preferred return and capital, pro rata.
        paid = min(remaining, pref_balance)
        pref_balance -= paid
        remaining -= paid
        tier_totals[0] += paid
        lp_paid = paid * equity.lp_share
        gp_paid = paid - lp_paid
        hurdle_balances = [b - lp_paid for b in hurdle_balances]
        # Promote tiers: split until the LP's hurdle balance is repaid.
        for k, tier in enumerate(tiers):
            if remaining <= 0:
                break
            owed_to_lp = max(hurdle_balances[k], 0.0)
            tier_cash = min(remaining, owed_to_lp / tier.lp_split if tier.lp_split else remaining)
            lp_share = tier_cash * tier.lp_split
            hurdle_balances = [b - lp_share for b in hurdle_balances]
            remaining -= tier_cash
            tier_totals[k + 1] += tier_cash
            lp_paid += lp_share
            gp_paid += tier_cash - lp_share
        if remaining > 0:
            tier_totals[-1] += remaining
            lp_paid += remaining * equity.residual_lp_split
            gp_paid += remaining * (1 - equity.residual_lp_split)
        lp[m] = lp_paid
        gp[m] = gp_paid

    lp_in = sum(f for f in lp[1:])
    gp_in = sum(f for f in gp[1:])
    total_in = lp_in + gp_in
    result = WaterfallResult(
        lp_flows=lp,
        gp_flows=gp,
        tier_totals=tier_totals,
        lp_irr=xirr(lp, dates),
        gp_irr=xirr(gp, dates) if gp_equity > 0 else None,
        lp_multiple=lp_in / lp_equity if lp_equity else 0.0,
        gp_multiple=gp_in / gp_equity if gp_equity else 0.0,
        promote=gp_in - total_in * (1 - equity.lp_share),
    )
    return result
