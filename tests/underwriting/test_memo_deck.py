"""The land deal's IC memo: figures from the engine, verdict from the floor, two-page deck."""

from __future__ import annotations

import datetime
import io
from typing import Any

from pypdf import PdfReader

from app.deals import load_cypress_ridge
from core.underwriting.deck import build_land_deck
from core.underwriting.engine import run
from core.underwriting.memo import LandFacts, build_land_facts, write_land_memo
from core.underwriting.sensitivity import SensitivityGrid, build_grid, max_land_price_for_irr
from core.underwriting.summary import Outputs

META, SEED = load_cypress_ridge()


def _facts(
    name: str, floor: float = 0.15
) -> tuple[Any, Outputs, SensitivityGrid, float | None, LandFacts]:
    scenario = next(s for s in SEED if s.name == name)
    out = run(scenario.inputs)
    grid = build_grid(scenario.inputs)
    max_price = max_land_price_for_irr(scenario.inputs, floor)
    at_max = None
    if max_price is not None:
        priced = scenario.inputs.model_copy(deep=True)
        priced.tract.purchase_price_per_acre = max_price
        at_max = run(priced)
    return (
        scenario,
        out,
        grid,
        max_price,
        build_land_facts(scenario.inputs, out, grid, name, floor, max_price, at_max),
    )


def test_main_scenario_clears_the_floor_and_names_the_headroom() -> None:
    _, out, _, max_price, facts = _facts("Main")
    assert facts.verdict == "bid"
    assert facts.figures["irr"] == "17.4%" and facts.figures["price_per_acre"] == "$45,000"
    assert max_price is not None and max_price > 45_000
    memo = write_land_memo(facts)
    assert memo.problems == []
    assert memo.recommendation.startswith(
        "Recommendation: bid $45,000 per acre ($28.8M for 640 acres)"
    )
    assert "could rise to" in memo.recommendation
    assert "2,380 lots" in memo.body[0] and "$379.1M of revenue" in memo.body[0]


def test_lower_lot_price_scenario_does_not_clear() -> None:
    _, out, _, max_price, facts = _facts("Lower lot price")
    assert (out.summary.unlevered_irr or 0) < 0.15
    assert facts.verdict in ("bid_lower", "pass")
    memo = write_land_memo(facts)
    assert memo.problems == []
    if facts.verdict == "bid_lower":
        assert memo.recommendation.startswith("Recommendation: bid no more than $")
        assert max_price is not None and max_price < 45_000
    else:
        assert memo.recommendation.startswith("Recommendation: pass at $45,000 per acre")


def test_max_land_price_solver_hits_the_floor() -> None:
    scenario = next(s for s in SEED if s.name == "Main")
    price = max_land_price_for_irr(scenario.inputs, 0.15)
    assert price is not None
    priced = scenario.inputs.model_copy(deep=True)
    priced.tract.purchase_price_per_acre = price
    irr = run(priced).summary.unlevered_irr or 0
    assert 0.1495 <= irr <= 0.1505
    assert max_land_price_for_irr(scenario.inputs, 0.60) is None


def test_deck_has_two_pages_with_the_memo_and_evidence() -> None:
    scenario, out, grid, max_price, facts = _facts("Main")
    memo = write_land_memo(facts)
    pdf = build_land_deck(
        META["name"],
        "640.0 ac · Waller County, TX",
        "Main",
        scenario.inputs,
        out,
        memo,
        grid,
        0.15,
        max_price,
        date=datetime.date(2026, 9, 14),
    )
    reader = PdfReader(io.BytesIO(pdf))
    assert len(reader.pages) == 2
    page1 = reader.pages[0].extract_text()
    assert "Recommendation: bid $45,000 per acre" in page1
    assert "Cypress Ridge" in page1 and "Main case" in page1 and "Land Underwriting" in page1
    assert "17.4%" in page1 and "$379.1M" in page1 and "ACREAGE" in page1
    assert "WHAT THE MODEL CANNOT TELL YOU" in page1
    page2 = reader.pages[1].extract_text()
    assert "NET CASH FLOW BY YEAR" in page2 and "SENSITIVITY" in page2
    assert "REVENUE" in page2 and "COSTS" in page2 and "LOT MIX" in page2
    assert "Lot sales" in page2 and "Sections" in page2
