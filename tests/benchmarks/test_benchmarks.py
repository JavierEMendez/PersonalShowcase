"""Market context: parsers on recorded text, rules on the snapshot, panels on both pages."""

from __future__ import annotations

import datetime
import json
from pathlib import Path

import pytest

from app.deals import load_cypress_ridge
from core.benchmarks import context, sources
from core.benchmarks.context import Sources, land_context, multifamily_context
from core.benchmarks.sources import Series, _bps_row, load_snapshot
from core.copilot.engine import run as run_mf
from core.copilot.inputs import CopilotInputs
from core.underwriting.engine import run as run_land
from evals.memo.run import ROOT

BPS_TEXT = (Path(__file__).resolve().parents[1] / "fixtures" / "bps_county_sample.txt").read_text(
    encoding="utf-8"
)


def test_bps_row_parses_the_county_line() -> None:
    row = _bps_row(BPS_TEXT, "48", "201")
    assert row is not None and row[7] == "10469" and row[16] == "4733"
    assert _bps_row(BPS_TEXT, "48", "999") is None


def test_series_year_over_year_and_points() -> None:
    dates = [datetime.date(2025, 9, 1) + datetime.timedelta(days=30 * i) for i in range(14)]
    values = [100.0 + i for i in range(14)]
    s = Series(series_id="X", label="x", unit="", dates=dates, values=values, source_url="u")
    assert s.latest == (dates[-1], 113)
    assert s.year_over_year() == pytest.approx(0.13)  # a year back lands on the first point
    assert s.change_points() == pytest.approx(13)


def test_snapshot_has_every_series_the_panels_need() -> None:
    snap = load_snapshot()
    for series_id in ("DGS10", "SOFR", "MORTGAGE30US", "CUSR0000SEHA", "HOUS448NA"):
        assert series_id in snap.fred and snap.fred[series_id].values
    assert "permits:48201:5+ units" in snap.permits and "permits:48473:1-unit" in snap.permits
    assert "Houston, TX" in snap.rents
    assert snap.permits["permits:48201:5+ units"].trailing_12 > 0


def test_multifamily_rows_and_flags_from_the_snapshot() -> None:
    raw = json.loads((ROOT / "data" / "sawyer_bend.json").read_text(encoding="utf-8"))
    inputs = CopilotInputs.model_validate(raw["cases"][0]["inputs"])
    out = run_mf(inputs)
    ctx = multifamily_context(inputs, out, Sources(offline=True))
    topics = [r.topic for r in ctx.rows]
    assert topics == [
        "Loan rate against SOFR",
        "Market rent growth",
        "Houston asking rents",
        "Exit cap against the 10-year",
        "Houston employment",
        "Multifamily supply, Harris County",
    ]
    assert not ctx.live and ctx.recorded is not None and ctx.problems == []
    loan = ctx.rows[0]
    assert "5.75% fixed" in loan.underwritten and "bps over SOFR" in loan.underwritten
    assert "at least 150 bps over SOFR" in loan.note
    # A rate under SOFR plus 150 bps is flagged; one above it is in range.
    cheap = inputs.model_copy(deep=True)
    cheap.loan.rate = 0.03
    assert multifamily_context(cheap, out, Sources(offline=True)).rows[0].flag == "watch"
    dear = inputs.model_copy(deep=True)
    dear.loan.rate = 0.09
    assert multifamily_context(dear, out, Sources(offline=True)).rows[0].flag == "ok"
    assert all(r.flag in ("ok", "watch", "info") for r in ctx.rows)
    # A 12% rent growth assumption is flagged against any measured rent inflation.
    hot = inputs.model_copy(deep=True)
    hot.revenue.market_rent_growth = 0.12
    flags = {r.topic: r.flag for r in multifamily_context(hot, out, Sources(offline=True)).rows}
    assert flags["Market rent growth"] == "watch" and flags["Houston asking rents"] == "watch"


def test_land_rows_from_the_snapshot() -> None:
    _, seed = load_cypress_ridge()
    inputs = seed[0].inputs
    out = run_land(inputs)
    ctx = land_context(inputs, out, Sources(offline=True))
    topics = [r.topic for r in ctx.rows]
    assert topics == [
        "Mortgage rates",
        "Single-family permits, Waller County",
        "Houston employment",
        "Return against the risk-free rate",
    ]
    permits = ctx.rows[1]
    assert "420 lots per year" in permits.underwritten
    assert permits.flag == "watch"  # 420 lots a year against a few hundred county permits


def test_live_failure_falls_back_to_the_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    sources.clear_cache()

    def boom(*args: object, **kwargs: object) -> str:
        raise sources.SourceError("network down")

    monkeypatch.setattr(sources, "_get", boom)
    src = Sources()
    series = src.fred("DGS10")
    assert series.values and src.used_snapshot and src.problems
    ctx = multifamily_context(
        CopilotInputs.model_validate(
            json.loads((ROOT / "data" / "sawyer_bend.json").read_text(encoding="utf-8"))["cases"][
                0
            ]["inputs"]
        ),
        run_mf(
            CopilotInputs.model_validate(
                json.loads((ROOT / "data" / "sawyer_bend.json").read_text(encoding="utf-8"))[
                    "cases"
                ][0]["inputs"]
            )
        ),
        src,
    )
    assert not ctx.live and len(ctx.rows) == 6
    sources.clear_cache()


def test_rules_are_the_documented_ones() -> None:
    assert context.LOAN_SPREAD_OVER_SOFR_MIN == 0.015
    assert context.EXIT_CAP_SPREAD_MIN == 0.0075 and context.RENT_GROWTH_HEADROOM == 0.015
