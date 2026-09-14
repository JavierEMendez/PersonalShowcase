"""IRR and XIRR reproduce hand-checked cases."""

import datetime

import pytest

from core.underwriting.irr import cashflow_dates, end_of_month, monthly_irr, xirr


def test_xirr_one_year_round_trip() -> None:
    # Invest 100, receive 110 exactly 365 days later: 10.0%.
    d0 = datetime.date(2027, 3, 1)
    rate = xirr([-100.0, 110.0], [d0, d0 + datetime.timedelta(days=365)])
    assert rate is not None
    assert rate == pytest.approx(0.10, abs=1e-9)


def test_xirr_matches_spreadsheet_case() -> None:
    # Spreadsheet XIRR on the same series and dates returns 0.37336 (actual/365).
    flows = [-10000.0, 2750.0, 4250.0, 3250.0, 2750.0]
    dates = [
        datetime.date(2008, 1, 1),
        datetime.date(2008, 3, 1),
        datetime.date(2008, 10, 30),
        datetime.date(2009, 2, 15),
        datetime.date(2009, 4, 1),
    ]
    rate = xirr(flows, dates)
    assert rate is not None
    assert rate == pytest.approx(0.373362535, abs=1e-6)


def test_xirr_needs_a_sign_change() -> None:
    d0 = datetime.date(2027, 3, 1)
    assert xirr([100.0, 50.0], [d0, d0 + datetime.timedelta(days=30)]) is None
    assert xirr([-100.0, -50.0], [d0, d0 + datetime.timedelta(days=30)]) is None


def test_monthly_irr_annualises() -> None:
    # 1% per month for 12 months on a 100 investment returns (1.01^12 - 1) annually.
    flows = [-100.0] + [0.0] * 11 + [100.0 * 1.01**12]
    rate = monthly_irr(flows)
    assert rate is not None
    assert rate == pytest.approx(1.01**12 - 1, abs=1e-7)


def test_end_of_month_handles_leap_years() -> None:
    assert end_of_month(2028, 2) == datetime.date(2028, 2, 29)
    assert end_of_month(2027, 2) == datetime.date(2027, 2, 28)


def test_cashflow_dates_follow_closing_date_convention() -> None:
    dates = cashflow_dates(datetime.date(2027, 3, 15), 4)
    assert dates == [
        datetime.date(2027, 3, 15),
        datetime.date(2027, 4, 30),
        datetime.date(2027, 5, 31),
        datetime.date(2027, 6, 30),
    ]
    # Year roll-over
    assert cashflow_dates(datetime.date(2027, 12, 1), 2)[1] == datetime.date(2028, 1, 31)
