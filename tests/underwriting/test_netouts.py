"""Acreage net-outs reproduce the hand-computed Cypress Ridge tract."""

import pytest

from core.underwriting.inputs import DealInputs
from core.underwriting.netouts import Acreage, detention_footprint, road_acres


def test_road_acres_formula() -> None:
    # 4,000 LF, 80 ft paved, 10 ft road setback and 10 ft landscaping setback each side.
    assert road_acres(4000, 80, 10, 10) == pytest.approx(4000 * 120 / 43560)
    assert road_acres(0, 80, 10, 10) == 0.0


def test_detention_footprint_grosses_up_by_30_percent() -> None:
    assert detention_footprint(1.1, 640, 9) == pytest.approx(1.1 * 640 / 9 * 1.3)
    assert detention_footprint(1.1, 640, 0) == 0.0


def test_cypress_ridge_acreage(cypress_main: DealInputs, cypress_acreage: Acreage) -> None:
    a = cypress_acreage
    assert a.gross == 640.0
    assert a.plants == pytest.approx(14.25)  # WWTP 10 + water plant 3.5 + lift station 0.75
    assert a.detention == pytest.approx(101.6889, abs=1e-4)
    assert a.detention_each == pytest.approx(101.6889 / 6, abs=1e-4)
    assert a.amenities == pytest.approx(9.0)
    assert a.parks == pytest.approx(19.2)
    assert a.drill_sites == 4.5
    assert a.other == 6.0
    assert a.roads == pytest.approx(11.0193 + 7.6010, abs=1e-3)
    assert a.net_out_total == pytest.approx(173.259, abs=1e-3)
    assert a.developable == pytest.approx(466.741, abs=1e-3)
    assert a.residential_developable == pytest.approx(432.741, abs=1e-3)
    assert a.developable == pytest.approx(a.gross - a.net_out_total)
    assert a.residential_developable == pytest.approx(
        a.developable
        - cypress_main.tract.commercial_pod_acres
        - cypress_main.tract.residential_pod_acres
    )
