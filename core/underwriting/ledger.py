"""Monthly ledger helpers.

Every monthly series is a list indexed by project month 1..MAX_MONTHS; index 0 is unused.
Month 1 is the closing month.
"""

from __future__ import annotations

MAX_MONTHS = 360


def zeros() -> list[float]:
    return [0.0] * (MAX_MONTHS + 1)


def in_range(month: int) -> bool:
    return 1 <= month <= MAX_MONTHS


def spread(series: list[float], amount: float, start_month: int, duration: int) -> None:
    """Spread `amount` evenly over `duration` months starting at `start_month`."""
    if duration <= 0 or amount <= 0:
        return
    per_month = amount / duration
    for month in range(int(start_month), int(start_month) + int(duration)):
        if in_range(month):
            series[month] += per_month


def lump(series: list[float], amount: float, month: int) -> None:
    """Book `amount` in a single month if the month is inside the ledger."""
    if in_range(month):
        series[month] += amount


def add_into(target: list[float], *sources: list[float]) -> None:
    for month in range(1, MAX_MONTHS + 1):
        for source in sources:
            target[month] += source[month]


def total(series: list[float]) -> float:
    return sum(series[1:])


def mround(value: float, multiple: float) -> float:
    """Spreadsheet MROUND: round to the nearest multiple."""
    if multiple == 0:
        return 0.0
    return round(value / multiple) * multiple
