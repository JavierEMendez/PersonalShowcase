"""Jinja filters for figures.

Consistent decimals, thousands separators, negatives in parentheses.
"""

from __future__ import annotations

from jinja2 import Environment


def _paren(text: str, negative: bool) -> str:
    return f"({text})" if negative else text


def num(value: float | int | None, decimals: int = 0) -> str:
    """Number with thousands separators; negatives in parentheses."""
    if value is None:
        return ""
    text = f"{abs(value):,.{decimals}f}"
    return _paren(text, value < 0)


def millions(value: float | int | None, decimals: int = 1) -> str:
    """Dollars shown in millions, no unit (the unit lives in the panel header)."""
    if value is None:
        return ""
    return num(value / 1e6, decimals)


def money_m(value: float | int | None, decimals: int = 1) -> str:
    """Dollars shown as $12.3M."""
    if value is None:
        return ""
    text = f"${abs(value) / 1e6:,.{decimals}f}M"
    return _paren(text, value < 0)


def money_k(value: float | int | None) -> str:
    """Dollars shown as $884k or $24.1k."""
    if value is None:
        return ""
    thousands = abs(value) / 1e3
    text = f"${thousands:,.0f}k" if thousands >= 100 else f"${thousands:,.1f}k"
    return _paren(text, value < 0)


def money(value: float | int | None, decimals: int = 0) -> str:
    """Dollars with separators: $45,000."""
    if value is None:
        return ""
    return _paren(f"${abs(value):,.{decimals}f}", value < 0)


def pct(value: float | None, decimals: int = 1) -> str:
    """Fraction shown as a percentage: 0.174 -> 17.4%."""
    if value is None:
        return ""
    return _paren(f"{abs(value) * 100:.{decimals}f}%", value < 0)


def mult(value: float | None, decimals: int = 2) -> str:
    """Multiple with the times sign: 1.73×."""
    if value is None:
        return ""
    return f"{value:.{decimals}f}×"


def years(months: int | None) -> str:
    if months is None:
        return ""
    return f"{months / 12:.1f} yrs"


def register(env: Environment) -> None:
    env.filters.update(
        {
            "num": num,
            "millions": millions,
            "money_m": money_m,
            "money_k": money_k,
            "money": money,
            "pct": pct,
            "mult": mult,
            "years": years,
        }
    )
