"""Return metrics: XIRR on the closing-date convention and a monthly Newton IRR fallback."""

from __future__ import annotations

import calendar
import datetime


def monthly_irr(cashflows: list[float], guess: float = 0.1, max_iter: int = 1000) -> float | None:
    """Newton-Raphson IRR on monthly cashflows, returned as an annual rate.

    Returns None when the series has no sign change or the solver leaves (-50%, 1000%).
    """
    if not any(c < 0 for c in cashflows) or not any(c > 0 for c in cashflows):
        return None
    r = guess / 12  # monthly
    for _ in range(max_iter):
        try:
            npv: float = sum(c / (1 + r) ** t for t, c in enumerate(cashflows))
            dnpv: float = sum(-t * c / (1 + r) ** (t + 1) for t, c in enumerate(cashflows))
        except (OverflowError, ZeroDivisionError):
            return None
        if dnpv == 0:
            break
        r_new = r - npv / dnpv
        # Clamp to prevent divergence
        r_new = max(-0.99, min(10.0, r_new))
        if abs(r_new - r) < 1e-8:
            r = r_new
            break
        r = r_new
    try:
        annual = (1 + r) ** 12 - 1
    except OverflowError:
        return None
    return annual if -0.5 < annual < 10 else None


def xirr(
    cashflows: list[float],
    dates: list[datetime.date],
    guess: float = 0.1,
    max_iter: int = 1000,
) -> float | None:
    """Newton-Raphson XIRR on the actual/365 convention.

    Tries several seeds when the first fails to converge. Returns None when the series has
    no sign change or no seed converges inside (-50%, 1000%).
    """
    if not any(c < 0 for c in cashflows) or not any(c > 0 for c in cashflows):
        return None
    d0 = dates[0]
    year_fractions = [(d - d0).days / 365.0 for d in dates]
    pairs = [(c, t) for c, t in zip(cashflows, year_fractions, strict=True) if c != 0]

    def solve(r: float) -> float | None:
        for _ in range(max_iter):
            npv: float = sum(c / (1 + r) ** t for c, t in pairs)
            dnpv: float = sum(-t * c / (1 + r) ** (t + 1) for c, t in pairs)
            if abs(dnpv) < 1e-14:
                return None
            r_new = r - npv / dnpv
            if r_new <= -1:
                return None  # prevent divergence
            if abs(r_new - r) < 1e-9:
                return r_new
            r = r_new
        residual: float = sum(c / (1 + r) ** t for c, t in pairs)
        return r if abs(residual) < 1.0 else None

    for seed in [guess, 0.05, 0.15, 0.25, 0.01, -0.05]:
        result = solve(seed)
        if result is not None and -0.5 < result < 10:
            return result
    return None


def end_of_month(year: int, month: int) -> datetime.date:
    return datetime.date(year, month, calendar.monthrange(year, month)[1])


def cashflow_dates(closing_date: datetime.date, months: int) -> list[datetime.date]:
    """Month 1 is the closing date; month N is the end of the month N-1 months later."""
    dates = [closing_date]
    for m in range(2, months + 1):
        offset = m - 1
        year = closing_date.year + (closing_date.month - 1 + offset) // 12
        month = (closing_date.month - 1 + offset) % 12 + 1
        dates.append(end_of_month(year, month))
    return dates
