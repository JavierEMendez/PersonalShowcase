"""Ledger helpers spread and lump amounts inside the 360-month window."""

import pytest

from core.underwriting.ledger import MAX_MONTHS, lump, mround, spread, total, zeros


def test_spread_is_even_and_foots() -> None:
    s = zeros()
    spread(s, 1200.0, 5, 12)
    assert s[4] == 0.0
    assert s[5] == pytest.approx(100.0)
    assert s[16] == pytest.approx(100.0)
    assert s[17] == 0.0
    assert total(s) == pytest.approx(1200.0)


def test_spread_ignores_zero_duration_and_negative_amounts() -> None:
    s = zeros()
    spread(s, 1200.0, 5, 0)
    spread(s, -50.0, 5, 3)
    assert total(s) == 0.0


def test_spread_clips_to_the_window() -> None:
    s = zeros()
    spread(s, 100.0, MAX_MONTHS - 1, 4)
    # Two of the four months fall past the window and are dropped, so the series does not foot.
    assert total(s) == pytest.approx(50.0)


def test_lump_outside_window_is_dropped() -> None:
    s = zeros()
    lump(s, 10.0, 0)
    lump(s, 10.0, MAX_MONTHS + 1)
    lump(s, 10.0, 12)
    assert total(s) == 10.0


def test_mround_matches_spreadsheet() -> None:
    assert mround(23.4, 1) == 23
    assert mround(26.6, 1) == 27
    assert mround(7, 5) == 5
    assert mround(8, 5) == 10
    assert mround(3, 0) == 0
