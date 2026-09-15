"""The Recommend step: facts from the engine, drafts with placeholders, checks, fallback."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from core.copilot.engine import run
from core.copilot.inputs import CopilotInputs
from core.copilot.memo import (
    ClaudeWriter,
    Draft,
    MemoFacts,
    TemplateWriter,
    build_facts,
    check_draft,
    write_memo,
)
from core.copilot.sensitivity import at_price, stress_table
from core.copy_rules import violations
from evals.memo.run import cases
from evals.memo.score import score_memo

ROOT = Path(__file__).resolve().parents[2]


def facts_for(name: str) -> MemoFacts:
    inputs = next(i for n, i in cases() if n == name)
    out = run(inputs)
    acq = inputs.acquisition
    ask = run(at_price(inputs, acq.asking_price or acq.purchase_price))
    return build_facts(out, ask, stress_table(inputs), name)


@pytest.fixture(scope="module")
def base_facts() -> MemoFacts:
    return facts_for("Base")


def test_facts_match_the_documented_memo(base_facts: MemoFacts) -> None:
    f = base_facts.figures
    assert f["bid"] == "$46.0M" and f["ask"] == "$50.5M"
    assert f["levered_irr"] == "14.8%" and f["equity_multiple"] == "1.89×"
    assert f["cushion_bps"] == "275 bps" and f["threshold"] == "12%"
    assert f["dscr_year1"] == "1.53×" and f["covenant_dscr"] == "1.25×"
    assert f["levered_irr_at_ask"] == "7.9%"
    assert base_facts.clears and not base_facts.has_breach
    assert "floor_dscr" in f and "breach_dscr" not in f


@pytest.mark.parametrize("name", ["Base", "Downside", "Lender"])
def test_template_memo_passes_every_check(name: str) -> None:
    facts = facts_for(name)
    memo = write_memo(facts, TemplateWriter())
    assert memo.problems == [] and not memo.fallback and memo.writer == "template"
    report = score_memo(memo, facts)
    assert report.ok, report.problems
    assert memo.recommendation.startswith("Recommendation: " + ("bid" if facts.clears else "pass"))
    assert violations(memo.markdown("Sawyer Bend Apartments")) == []


def test_downside_memo_reports_the_breach() -> None:
    facts = facts_for("Downside")
    assert facts.has_breach
    memo = write_memo(facts, TemplateWriter())
    assert "The covenant breaks under" in " ".join(memo.body)


def test_check_draft_catches_the_failure_modes(base_facts: MemoFacts) -> None:
    bad = Draft(
        recommendation="Recommendation: pass on this one! Is 12% enough?",
        body=["The IRR is {irr_made_up}.", "We leverage {ltv} LTV."],
        cannot=["a", "b"],
    )
    problems = check_draft(bad, base_facts)
    labels = " | ".join(problems)
    assert "digit written" in labels
    assert "unknown placeholder {irr_made_up}" in labels
    assert "banned: exclamation point" in labels and "banned: leverage" in labels
    assert "rhetorical question" in labels
    assert "clears the threshold but the recommendation is not a bid" in labels
    assert "does not name the bid" in labels
    assert "body has 2 sentences" in labels and "cannot section has 2 items" in labels
    assert "covenant floor or breach" in labels


class FakeMessages:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return SimpleNamespace(content=[SimpleNamespace(type="tool_use", input=self.payload)])


GOOD_DRAFT = {
    "recommendation": (
        "Recommendation: bid {bid}, conditioned on a reassessment estimate and an interior "
        "scope walk. Do not chase the {ask} ask."
    ),
    "body": [
        "At {bid} the deal earns a {levered_irr} levered IRR and a {equity_multiple} multiple, "
        "{cushion_bps} above the {threshold} threshold.",
        "{year_one} DSCR is {dscr_year1} against a {covenant_dscr} covenant.",
        "Paying the {ask} ask cuts the levered IRR to {levered_irr_at_ask}.",
        "Market rent growth is the sensitive driver: at {growth_stress} the IRR is "
        "{growth_stress_irr}.",
        "No stress breaches the covenant; the floor is {floor_dscr} under {floor_stress}.",
    ],
    "cannot": [
        "Whether taxes reassess to the price; taxes are {taxes_share_of_opex} of expenses.",
        "Whether the {premium} premium survives {renovation_units} more renovated units.",
        "Roof and HVAC condition beyond the sample.",
        "The seller's appetite for {discount_to_ask} below ask.",
    ],
}


def test_claude_writer_draft_is_filled_from_facts(base_facts: MemoFacts) -> None:
    fake = FakeMessages(GOOD_DRAFT)
    writer = ClaudeWriter(client=SimpleNamespace(messages=fake), model="test-model")
    memo = write_memo(base_facts, writer)
    assert memo.writer == "test-model" and not memo.fallback and memo.problems == []
    assert memo.recommendation.startswith("Recommendation: bid $46.0M")
    assert "14.8% levered IRR and a 1.89× multiple, 275 bps above the 12% threshold" in memo.body[0]
    assert fake.calls[0]["tool_choice"] == {"type": "tool", "name": "record_memo"}
    prompt = fake.calls[0]["messages"][0]["content"]
    assert "{levered_irr} = 14.8%" in prompt and "clears the threshold" in prompt
    assert score_memo(memo, base_facts).ok


def test_claude_writer_with_digits_falls_back_to_the_template(base_facts: MemoFacts) -> None:
    bad = dict(GOOD_DRAFT)
    bad["body"] = [*GOOD_DRAFT["body"][:4], "The floor DSCR is 1.36x under a 6.5% rate."]
    fake = FakeMessages(bad)
    writer = ClaudeWriter(client=SimpleNamespace(messages=fake), model="test-model")
    memo = write_memo(base_facts, writer)
    assert memo.fallback and memo.writer == "template"
    assert any("digit written by the writer" in p for p in memo.problems)
    assert memo.recommendation.startswith("Recommendation: bid $46.0M, subject to")
    report = score_memo(memo, base_facts)
    assert not report.ok and "writer draft rejected, template used" in report.problems


def test_claude_writer_failure_falls_back() -> None:
    class Broken:
        def create(self, **kwargs: Any) -> Any:
            raise RuntimeError("network down")

    facts = facts_for("Lender")
    memo = write_memo(facts, ClaudeWriter(client=SimpleNamespace(messages=Broken()), model="m"))
    assert memo.fallback and memo.problems == ["writer failed: network down"]


def test_low_confidence_extractions_reach_the_prompt() -> None:
    from core.copilot.screen import RuleReader, screen
    from evals.screen.run import load_sample

    result = screen(load_sample(), RuleReader())
    inputs = next(i for n, i in cases() if n == "Base")
    out = run(inputs)
    facts = build_facts(out, out, stress_table(inputs), "Base", screen=result)
    assert facts.low_confidence == ["real estate taxes, t-12 (T-12 row 21)"]


def test_markdown_shape(base_facts: MemoFacts) -> None:
    memo = write_memo(base_facts, TemplateWriter())
    md = memo.markdown("Sawyer Bend Apartments")
    assert md.startswith("# Sawyer Bend Apartments: investment committee memo (Base case)")
    assert "## What the model cannot tell you" in md and md.count("\n- ") == 4


def test_seed_json_is_the_eval_source() -> None:
    raw = json.loads((ROOT / "data" / "sawyer_bend.json").read_text(encoding="utf-8"))
    assert [c["name"] for c in raw["cases"]] == [n for n, _ in cases()]
    CopilotInputs.model_validate(raw["cases"][0]["inputs"])


def test_draft_from_stringified_payload(base_facts: MemoFacts) -> None:
    import json

    from core.copilot.memo import draft_from_payload

    payload = dict(GOOD_DRAFT)
    payload["body"] = json.dumps(GOOD_DRAFT["body"])
    draft = draft_from_payload(json.dumps(payload))
    assert draft.body == GOOD_DRAFT["body"] and draft.cannot == GOOD_DRAFT["cannot"]
    memo = write_memo(
        base_facts, ClaudeWriter(client=SimpleNamespace(messages=FakeMessages(payload)), model="m")
    )
    assert not memo.fallback and memo.problems == []
