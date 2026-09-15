"""The Recommend step: the valuation range, facts, drafts with placeholders, checks, fallback."""

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
from core.copilot.recommend import LOW_DISCOUNT_CAP, LP_TARGETS, valuation_range
from core.copilot.sensitivity import stress_table
from core.copy_rules import violations
from evals.memo.run import cases
from evals.memo.score import score_memo

ROOT = Path(__file__).resolve().parents[2]


def facts_for(name: str) -> MemoFacts:
    inputs = next(i for n, i in cases() if n == name)
    return build_facts(run(inputs), valuation_range(inputs), stress_table(inputs), name)


@pytest.fixture(scope="module")
def base_facts() -> MemoFacts:
    return facts_for("Base")


def test_range_definitions_on_the_base_case() -> None:
    inputs = next(i for n, i in cases() if n == "Base")
    v = valuation_range(inputs)
    assert LP_TARGETS == {"max": 0.13, "mid": 0.15, "low": 0.17} and LOW_DISCOUNT_CAP == 0.20
    assert v.max is not None and v.max.price == pytest.approx(46_000_000, abs=10_000)
    assert v.max.lp_irr == pytest.approx(0.13, abs=0.0005) and v.max.basis == "LP IRR 13%"
    assert v.mid is not None and v.mid.price == pytest.approx(43_730_000, abs=10_000)
    assert v.mid.lp_irr == pytest.approx(0.15, abs=0.0005)
    # The 17% price ($41.6M) sits above 20% below ask ($40.4M), so the cap binds.
    assert v.low is not None and v.low.price == pytest.approx(40_400_000)
    assert v.low.basis == "20% below ask"
    assert v.verdict == "engage" and v.ask == 50_500_000
    assert v.at_ask.lp_irr is not None and v.at_ask.lp_irr < LP_TARGETS["max"]
    assert [p.label for p in v.points] == ["Low", "Mid", "Max"]


def test_low_end_uses_the_lp_price_when_it_is_lower() -> None:
    inputs = next(i for n, i in cases() if n == "Downside")
    v = valuation_range(inputs)
    assert v.low is not None and v.low.basis == "LP IRR 17%" and v.low.price < 0.8 * v.ask


def test_facts_carry_the_range(base_facts: MemoFacts) -> None:
    f = base_facts.figures
    assert f["range_low"] == "$40.4M" and f["range_mid"] == "$43.7M"
    assert f["range_max"] == "$46.0M"
    assert f["lp_max"] == "13.0%" and f["lp_mid"] == "15.0%" and f["discount_max"] == "8.9%"
    assert f["ask"] == "$50.5M" and f["lp_ask"] == "7.9%"
    assert f["target_max"] == "13%" and f["target_mid"] == "15%" and f["target_low"] == "17%"
    assert base_facts.verdict == "engage" and not base_facts.has_breach


@pytest.mark.parametrize("name", ["Base", "Downside", "Lender"])
def test_template_memo_passes_every_check(name: str) -> None:
    facts = facts_for(name)
    memo = write_memo(facts, TemplateWriter())
    assert memo.problems == [] and not memo.fallback and memo.writer == "template"
    report = score_memo(memo, facts)
    assert report.ok, report.problems
    assert memo.recommendation.startswith("Recommendation: worth a full underwriting only if")
    assert violations(memo.markdown("Sawyer Bend Apartments")) == []


def test_pursue_and_pass_verdicts_render() -> None:
    inputs = next(i for n, i in cases() if n == "Base")
    cheap = inputs.model_copy(deep=True)
    cheap.acquisition.asking_price = 44_000_000
    facts = build_facts(run(cheap), valuation_range(cheap), stress_table(cheap), "Cheap")
    assert facts.verdict == "pursue"
    memo = write_memo(facts, TemplateWriter())
    assert memo.problems == [] and memo.recommendation.startswith("Recommendation: pursue.")
    dear = inputs.model_copy(deep=True)
    dear.acquisition.purchase_price = 120_000_000
    dear.acquisition.asking_price = 130_000_000
    facts = build_facts(run(dear), valuation_range(dear), stress_table(dear), "Dear")
    assert facts.verdict == "pass"
    memo = write_memo(facts, TemplateWriter())
    assert memo.problems == [] and memo.recommendation.startswith("Recommendation: pass.")


def test_downside_memo_reports_the_breach() -> None:
    facts = facts_for("Downside")
    assert facts.has_breach
    memo = write_memo(facts, TemplateWriter())
    assert "The covenant breaks under" in " ".join(memo.body)


def test_check_draft_catches_the_failure_modes(base_facts: MemoFacts) -> None:
    bad = Draft(
        recommendation="Recommendation: pursue this one! Is 13% enough? This is a strong case.",
        body=["The IRR is {irr_made_up}.", "We leverage {ltv} LTV."],
        cannot=["a", "b"],
    )
    problems = check_draft(bad, base_facts)
    labels = " | ".join(problems)
    assert "digit written" in labels
    assert "unknown placeholder {irr_made_up}" in labels
    assert "banned: exclamation point" in labels and "banned: leverage" in labels
    assert "rhetorical question" in labels
    assert "does not cap it at {range_max}" in labels
    assert "talks about the verdict" in labels
    assert "body has 2 sentences" in labels and "cannot section has 2 items" in labels
    assert "does not state {range_low}" in labels
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
        "Recommendation: worth a full underwriting only if the seller engages at or below "
        "{range_max}. Open at {range_mid}; {range_low} buys the deal with confidence."
    ),
    "body": [
        "The range runs from {range_low} to {range_max}, set by levered LP IRRs of {target_low} "
        "and {target_max}; {range_mid} returns {target_mid}.",
        "At {range_mid} the going-in cap is {cap_mid} and the {year_one} DSCR {dscr_mid} against "
        "a {covenant_dscr} covenant.",
        "Paying the {ask} ask returns {lp_ask} to the LP.",
        "Market rent growth is the sensitive driver: at {growth_stress} the levered IRR is "
        "{growth_stress_irr}.",
        "No stress breaches the covenant; the floor is {floor_dscr} under {floor_stress}.",
    ],
    "cannot": [
        "Whether taxes reassess to the price; taxes are {taxes_share_of_opex} of expenses.",
        "Whether the {premium} premium survives {renovation_units} more renovated units.",
        "Roof and HVAC condition beyond the sample.",
        "The seller's appetite for {discount_max} below ask.",
    ],
}


def test_claude_writer_draft_is_filled_from_facts(base_facts: MemoFacts) -> None:
    fake = FakeMessages(GOOD_DRAFT)
    writer = ClaudeWriter(client=SimpleNamespace(messages=fake), model="test-model")
    memo = write_memo(base_facts, writer)
    assert memo.writer == "test-model" and not memo.fallback and memo.problems == []
    assert memo.recommendation.startswith(
        "Recommendation: worth a full underwriting only if the seller engages at or below $46.0M"
    )
    assert "The range runs from $40.4M to $46.0M" in memo.body[0]
    assert fake.calls[0]["tool_choice"] == {"type": "tool", "name": "record_memo"}
    prompt = fake.calls[0]["messages"][0]["content"]
    assert "{range_mid} = $43.7M" in prompt and "Verdict: engage" in prompt
    assert score_memo(memo, base_facts).ok


def test_claude_writer_with_digits_falls_back_to_the_template(base_facts: MemoFacts) -> None:
    bad = dict(GOOD_DRAFT)
    bad["body"] = [*GOOD_DRAFT["body"][:4], "The floor DSCR is 1.36x under a 6.5% rate."]
    fake = FakeMessages(bad)
    writer = ClaudeWriter(client=SimpleNamespace(messages=fake), model="test-model")
    memo = write_memo(base_facts, writer)
    assert memo.fallback and memo.writer == "template"
    assert any("digit written by the writer" in p for p in memo.problems)
    assert any(
        p.startswith("draft as received: Recommendation: worth a full") for p in memo.problems
    )
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
    facts = build_facts(
        run(inputs), valuation_range(inputs), stress_table(inputs), "Base", screen=result
    )
    assert facts.low_confidence == ["real estate taxes, t-12 (T-12 row 21)"]
    assert "low_confidence" in facts.figures


def test_markdown_shape(base_facts: MemoFacts) -> None:
    memo = write_memo(base_facts, TemplateWriter())
    md = memo.markdown("Sawyer Bend Apartments")
    assert md.startswith("# Sawyer Bend Apartments: screening memo (Base case)")
    assert "## What the model cannot tell you" in md and md.count("\n- ") == 4


def test_t12_is_not_a_digit_but_other_numbers_are(base_facts: MemoFacts) -> None:
    ok: dict[str, Any] = dict(GOOD_DRAFT)
    ok["cannot"] = [
        "Whether the seller's T-12 taxes at {taxes_share_of_opex} of expenses survive the sale.",
        *GOOD_DRAFT["cannot"][1:],
    ]
    assert not any("digit" in p for p in check_draft(Draft.model_validate(ok), base_facts))
    bad: dict[str, Any] = dict(GOOD_DRAFT)
    bad["cannot"] = [
        "Whether the 2025 assessed value of the T-12 taxes survives reassessment.",
        *GOOD_DRAFT["cannot"][1:],
    ]
    problems = check_draft(Draft.model_validate(bad), base_facts)
    assert any(p.startswith("digit written by the writer: ...") and "2025" in p for p in problems)


def test_paragraph_sections_are_split_and_nested_shapes_flattened(base_facts: MemoFacts) -> None:
    from core.copilot.memo import draft_from_payload, flatten_text, split_items

    payload: dict[str, Any] = dict(GOOD_DRAFT)
    payload["body"] = " ".join(GOOD_DRAFT["body"])
    payload["cannot"] = "\n".join(f"- {c}" for c in GOOD_DRAFT["cannot"])
    draft = draft_from_payload(payload)
    assert draft.body == GOOD_DRAFT["body"] and draft.cannot == GOOD_DRAFT["cannot"]
    assert split_items("1. First item here. 2. Second item {bid}. 3. Third one.") == [
        "First item here.",
        "Second item {bid}.",
        "Third one.",
    ]
    assert split_items("Alpha risk; beta risk; gamma risk.") == [
        "Alpha risk",
        "beta risk",
        "gamma risk.",
    ]
    nested: dict[str, Any] = dict(GOOD_DRAFT)
    nested["body"] = [{"sentences": GOOD_DRAFT["body"]}]
    nested["cannot"] = {"items": [{"text": c} for c in GOOD_DRAFT["cannot"]]}
    draft = draft_from_payload(nested)
    assert draft.body == GOOD_DRAFT["body"] and draft.cannot == GOOD_DRAFT["cannot"]
    assert flatten_text(json.dumps(["a", {"b": "c"}])) == ["a", "c"]
    memo = write_memo(
        base_facts, ClaudeWriter(client=SimpleNamespace(messages=FakeMessages(payload)), model="m")
    )
    assert not memo.fallback and memo.problems == []


def test_seed_json_is_the_eval_source() -> None:
    raw = json.loads((ROOT / "data" / "sawyer_bend.json").read_text(encoding="utf-8"))
    assert [c["name"] for c in raw["cases"]] == [n for n, _ in cases()]
    CopilotInputs.model_validate(raw["cases"][0]["inputs"])
