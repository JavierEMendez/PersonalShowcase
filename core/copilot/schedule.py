"""Month arithmetic and growth factors for the monthly engine.

Series are lists indexed by project month 1..N; index 0 is closing (or unused).
"""

from __future__ import annotations

import calendar
import datetime


def add_months(start: datetime.date, months: int) -> datetime.date:
    """The same day of the month `months` later, clamped to the month's length."""
    year = start.year + (start.month - 1 + months) // 12
    month = (start.month - 1 + months) % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return datetime.date(year, month, day)


def year_of(month: int) -> int:
    return (month - 1) // 12 + 1


def monthly_growth(annual_rate: float, month: int) -> float:
    """Compounded monthly: the factor that applies in project month `month` (month 1 = 1.0)."""
    return float((1 + annual_rate) ** ((month - 1) / 12))


def yearly_step(annual_rate: float, month: int) -> float:
    """Stepped once a year: the factor for the project year that holds `month`."""
    return float((1 + annual_rate) ** (year_of(month) - 1))


def zeros(months: int) -> list[float]:
    return [0.0] * (months + 1)


def annual_sum(series: list[float], year: int) -> float:
    first = (year - 1) * 12 + 1
    return sum(series[first : first + 12])


def pmt(rate: float, periods: int, principal: float) -> float:
    """Level payment that amortises `principal` over `periods` at periodic `rate`."""
    if rate == 0:
        return principal / periods
    return principal * rate / (1 - (1 + rate) ** (-periods))
