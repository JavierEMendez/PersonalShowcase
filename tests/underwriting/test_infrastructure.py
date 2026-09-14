"""Infrastructure cost rows: plants, amenities, detention, other items, and roads."""

import pytest

from core.underwriting.infrastructure import Infrastructure, compute_infrastructure
from core.underwriting.inputs import DealInputs
from core.underwriting.lookups import effective_lookups
from core.underwriting.netouts import Acreage


@pytest.fixture(scope="module")
def infra(cypress_main: DealInputs, cypress_acreage: Acreage) -> Infrastructure:
    return compute_infrastructure(
        cypress_main.tract,
        cypress_main.costs,
        effective_lookups(cypress_main.lookups),
        cypress_acreage,
    )


def test_plant_rows_pad_to_eight_and_apply_other_costs(infra: Infrastructure) -> None:
    assert len(infra.plants) == 8
    wwtp = infra.plants[0]
    assert wwtp.type == "WWTP"
    assert wwtp.duration == 8
    assert wwtp.total_cost == pytest.approx(5_500_000 * 1.17)
    assert wwtp.ph2_total_cost == pytest.approx(2_000_000 * 1.17)
    assert wwtp.ph2_start_month == 37  # start + 36 by default
    assert infra.plants[2].duration == 3  # lift station
    assert infra.plants[3].type == "None"
    assert infra.plants[3].total_cost == 0.0
    assert infra.total_plants == pytest.approx((5_500_000 + 2_000_000 + 3_000_000 + 750_000) * 1.17)


def test_amenity_rows(infra: Infrastructure) -> None:
    assert len(infra.amenities) == 6
    large = infra.amenities[0]
    assert large.acres == 6.0
    assert large.duration == 12
    assert large.start_month == 6
    assert large.total_cost == pytest.approx(4_500_000 * 1.17)
    assert infra.total_amenities == pytest.approx((4_500_000 + 1_800_000) * 1.17)


def test_detention_rows_share_one_volume(infra: Infrastructure, cypress_acreage: Acreage) -> None:
    volume = 1.1 * 640 * 43560 / 27
    assert infra.detention_volume_cy == pytest.approx(volume)
    assert len(infra.detention) == 6
    first = infra.detention[0]
    assert first.base_cost == pytest.approx(volume * 10 / 6)
    assert first.total_cost == pytest.approx(volume * 10 / 6 * 1.17)
    assert [r.start_month for r in infra.detention] == [1, 16, 31, 46, 61, 76]
    assert first.delivery_month == 9
    assert first.total_landscaping == pytest.approx(
        2 * 43560 * cypress_acreage.detention_each * 1.12 * 0.30
    )


def test_other_rows_take_description_from_netouts(infra: Infrastructure) -> None:
    assert [r.desc for r in infra.other] == ["Pipeline easement", "Gas well setback"]
    assert infra.other[0].total_cost == pytest.approx(1_200_000 * 1.17)
    assert infra.other[0].duration == 6


def test_road_rows(infra: Infrastructure) -> None:
    assert len(infra.roads) == 6
    four_lane, two_lane = infra.roads[:2]
    assert four_lane.base_cost == pytest.approx(4000 * (460 + 663))
    assert four_lane.total_cost == pytest.approx(4000 * 1123 * 1.17)
    assert four_lane.duration == round(4000 / 300 + 6)
    assert four_lane.delivery_month == four_lane.duration
    assert four_lane.total_landscaping == pytest.approx(2 * 10 * 4000 * 2 * 1.12)
    assert four_lane.total_lights == int(4000 / 150 * 2)
    assert two_lane.start_month == 12
    assert two_lane.base_cost == pytest.approx(3850 * (450 + 343))
    # Empty rows keep the default schedule and cost nothing.
    assert infra.roads[2].start_month == 48
    assert infra.roads[2].duration == 6
    assert infra.roads[2].total_cost == 0.0
