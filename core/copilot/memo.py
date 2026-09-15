"""The Recommend step: an investment committee memo whose every figure comes from the model.

The writer (a sentence template, or the Claude API when `ANTHROPIC_API_KEY` is set) produces
prose with placeholders such as `{levered_irr}`; it is not allowed to write a digit. The code
then fills every placeholder from a facts table built from the engine output, so a figure can
only appear in the memo if the model produced it. A draft that breaks a rule (an unknown
placeholder, a digit in the prose, a banned phrase, a missing section, a recommendation that
contradicts the threshold test) is rejected and the template memo is used in its place, with the
rejection recorded on the memo.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from typing import Any, Protocol

from pydantic import BaseModel

from core.copilot.screen import ScreenResult
from core.copilot.sensitivity import StressRow
from core.copilot.summary import CopilotOutputs
from core.copy_rules import violations

DEFAULT_MODEL = os.environ.get("COPILOT_MODEL", "claude-sonnet-5")
THRESHOLD_IRR = 0.12
TOKEN = re.compile(r"\{([a-z0-9_]+)\}")
DIGIT = re.compile(r"\d")


# --------------------------------------------------------------------------------------------
# Facts
# --------------------------------------------------------------------------------------------
def _pct(v: float | None, d: int = 1) -> str:
    return "n/a" if v is None else f"{v * 100:.{d}f}%"


def _money_m(v: float, d: int = 1) -> str:
    return f"${v / 1e6:.{d}f}M"


def _mult(v: float | None) -> str:
    return "n/a" if v is None else f"{v:.2f}×"


class MemoFacts(BaseModel):
    """Every figure the memo may use, formatted, keyed by placeholder name."""

    case: str
    clears: bool
    figures: dict[str, str]
    descriptions: dict[str, str]
    has_breach: bool
    low_confidence: list[str]


def build_facts(
    out: CopilotOutputs,
    ask: CopilotOutputs,
    stress: list[StressRow],
    case: str,
    threshold: float = THRESHOLD_IRR,
    screen: ScreenResult | None = None,
) -> MemoFacts:
    s, r, ln, reno = out.summary, out.returns, out.loan, out.renovation
    irr = r.levered_irr or 0.0
    clears = irr >= threshold
    growth = next((row for row in stress if row.label.startswith("Rent growth")), None)
    premium = next((row for row in stress if row.label.startswith("Renovation premium")), None)
    floor_row = min(stress, key=lambda row: row.min_dscr or 9.0) if stress else None
    breaches = [row for row in stress if not row.holds]
    figures: dict[str, str] = {
        "bid": _money_m(s.purchase_price),
        "ask": _money_m(s.asking_price or s.purchase_price),
        "price_per_unit": f"${s.price_per_unit:,.0f}",
        "units": f"{s.units}",
        "hold_years": f"{s.hold_months // 12}",
        "levered_irr": _pct(r.levered_irr),
        "unlevered_irr": _pct(r.unlevered_irr),
        "equity_multiple": _mult(r.equity_multiple),
        "lp_irr": _pct(r.lp_irr),
        "gp_irr": _pct(r.gp_irr),
        "threshold": f"{threshold:.0%}",
        "cushion_bps": f"{abs(round((irr - threshold) * 10_000)):,} bps",
        "year_one": "year 1",
        "dscr_year1": _mult(s.dscr_year1),
        "covenant_dscr": _mult(ln.covenant_dscr),
        "min_dscr": _mult(s.min_dscr),
        "ltv": _pct(s.ltv),
        "debt_yield": _pct(s.debt_yield),
        "loan": _money_m(ln.amount),
        "equity": _money_m(out.sources_uses.equity),
        "going_in_cap": _pct(s.going_in_cap, 2),
        "cap_at_ask": _pct(s.cap_at_ask, 2),
        "exit_cap": _pct(out.exit.cap_rate, 2),
        "exit_value": _money_m(s.exit_value),
        "levered_irr_at_ask": _pct(ask.returns.levered_irr),
        "premium": f"${reno.premium_per_month:,.0f}",
        "renovation_units": f"{reno.units}",
        "renovation_cost": f"${reno.cost_per_unit:,.0f}",
        "taxes_share_of_opex": _pct(s.taxes_share_of_opex, 0),
        "discount_to_ask": _pct(s.discount_to_ask),
    }
    descriptions: dict[str, str] = {
        "bid": "purchase price underwritten",
        "ask": "seller's asking price",
        "price_per_unit": "price per unit at the bid",
        "units": "unit count",
        "hold_years": "hold period in years",
        "levered_irr": "levered IRR at the bid",
        "unlevered_irr": "unlevered IRR at the bid",
        "equity_multiple": "equity multiple at the bid",
        "lp_irr": "LP IRR after the waterfall",
        "gp_irr": "GP IRR including promote",
        "threshold": "levered IRR threshold for a bid",
        "cushion_bps": "distance from the threshold, in basis points, unsigned",
        "year_one": "the words 'year 1'",
        "dscr_year1": "year 1 debt service coverage",
        "covenant_dscr": "DSCR covenant",
        "min_dscr": "lowest DSCR over the hold",
        "ltv": "loan to value",
        "debt_yield": "debt yield on year 1 NOI",
        "loan": "loan amount",
        "equity": "equity required",
        "going_in_cap": "going-in cap rate at the bid",
        "cap_at_ask": "going-in cap rate at the ask",
        "exit_cap": "exit cap rate",
        "exit_value": "gross exit value",
        "levered_irr_at_ask": "levered IRR if bought at the ask",
        "premium": "renovation premium per month",
        "renovation_units": "units to renovate",
        "renovation_cost": "renovation cost per unit",
        "taxes_share_of_opex": "real estate taxes as a share of operating expenses",
        "discount_to_ask": "bid discount to the ask",
    }
    if growth:
        figures["growth_stress"] = growth.label.split(" ")[-1]
        figures["growth_stress_irr"] = _pct(growth.levered_irr)
        descriptions["growth_stress"] = "the stressed market rent growth rate"
        descriptions["growth_stress_irr"] = "levered IRR under the rent growth stress"
    if premium:
        figures["premium_stress"] = premium.label.split(" ")[-1]
        figures["premium_stress_irr"] = _pct(premium.levered_irr)
        descriptions["premium_stress"] = "the stressed renovation premium per month"
        descriptions["premium_stress_irr"] = "levered IRR under the premium stress"
    if breaches:
        figures["breach_stress"] = breaches[0].label.lower()
        figures["breach_dscr"] = _mult(breaches[0].min_dscr)
        descriptions["breach_stress"] = "the stress that breaks the covenant"
        descriptions["breach_dscr"] = "lowest DSCR under that stress"
    elif floor_row is not None:
        figures["floor_stress"] = floor_row.label.lower()
        figures["floor_dscr"] = _mult(floor_row.min_dscr)
        descriptions["floor_stress"] = "the stress with the lowest DSCR, none breaching"
        descriptions["floor_dscr"] = "lowest DSCR across the stresses"
    low: list[str] = []
    if screen is not None:
        for e in screen.extractions:
            if not e.plan and e.value is not None and e.confidence == "Low":
                low.append(f"{e.label.lower()} ({e.document} {e.page})")
    return MemoFacts(
        case=case,
        clears=clears,
        figures=figures,
        descriptions=descriptions,
        has_breach=bool(breaches),
        low_confidence=low,
    )


# --------------------------------------------------------------------------------------------
# Drafts and writers
# --------------------------------------------------------------------------------------------
class Draft(BaseModel):
    """Prose with placeholders. No digits allowed outside placeholders."""

    recommendation: str
    body: list[str]
    cannot: list[str]


class Writer(Protocol):
    name: str

    def draft(self, facts: MemoFacts) -> Draft: ...


class TemplateWriter:
    """Fixed sentences. Always available, always passes the checks; the fallback."""

    name = "template"

    def draft(self, facts: MemoFacts) -> Draft:
        f = facts.figures
        if facts.clears:
            recommendation = (
                "Recommendation: bid {bid}, subject to a tax reassessment estimate from the "
                "appraisal district and a scope walk of the unit interiors. Do not pursue at the "
                "{ask} ask."
            )
        else:
            recommendation = (
                "Recommendation: pass at {bid}. The deal returns {levered_irr} levered against a "
                "{threshold} threshold; revisit if the price or the renovation premium moves."
            )
        direction = "above" if facts.clears else "below"
        body = [
            "At {bid} the deal returns a {levered_irr} levered IRR and a {equity_multiple} "
            f"multiple, {{cushion_bps}} {direction} the {{threshold}} threshold, with a "
            "{year_one} DSCR of {dscr_year1} against a {covenant_dscr} covenant.",
            "At the {ask} ask the levered IRR falls to {levered_irr_at_ask}.",
        ]
        if "growth_stress" in f:
            body.append(
                "Returns are most sensitive to market rent growth: at {growth_stress} the IRR is "
                "{growth_stress_irr}."
            )
        if "premium_stress" in f:
            body.append(
                "The renovation premium carries the value-add thesis: at {premium_stress} rather "
                "than {premium} the IRR is {premium_stress_irr}."
            )
        if facts.has_breach:
            body.append(
                "The covenant breaks under {breach_stress}, where DSCR falls to {breach_dscr}."
            )
        elif "floor_stress" in f:
            body.append(
                "No single stress breaches the covenant; the floor is {floor_dscr} under "
                "{floor_stress}. The risk in this deal sits with the equity return rather than "
                "the debt."
            )
        cannot = [
            "Whether the appraisal district reassesses to the purchase price (taxes are "
            "{taxes_share_of_opex} of operating expenses).",
            "Whether the {premium} premium holds once {renovation_units} more renovated units "
            "reach the submarket.",
            "The condition of roofs and HVAC beyond the property condition sample.",
            "The seller's appetite for a bid {discount_to_ask} below ask.",
        ]
        return Draft(recommendation=recommendation, body=body, cannot=cannot)


MEMO_TOOL: dict[str, Any] = {
    "name": "record_memo",
    "description": "Record the investment committee memo.",
    "input_schema": {
        "type": "object",
        "properties": {
            "recommendation": {
                "type": "string",
                "description": (
                    "One or two sentences starting with 'Recommendation:'. Bid or pass, "
                    "with conditions."
                ),
            },
            "body": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Three to six sentences, one per item, in reading order.",
            },
            "cannot": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Three to five items for the section 'What the model cannot tell you', "
                    "one sentence each."
                ),
            },
        },
        "required": ["recommendation", "body", "cannot"],
    },
}

SYSTEM_PROMPT = """You draft investment committee memos for a multifamily acquisitions team.
You are given a facts table: placeholder names with their values and meanings. Write the memo
using placeholders in braces, such as {levered_irr}, wherever a figure belongs. Never write a
digit yourself; every number, percentage, multiple, dollar amount and count must be a placeholder
from the table. Use only placeholders that exist in the table.
Style: executive, bank style. Short declarative sentences. Say the number, then what it means.
No em dashes, no exclamation points, no rhetorical questions, no "it's not X, it's Y" or
"X, not Y" constructions, and none of these words: delve, leverage, robust, seamless, unlock,
empower, cutting-edge, game-changing.
Content: the recommendation must be to bid when the levered IRR clears the threshold and to
pass when it does not, and must name the bid. The body must compare the return to the
threshold, state the return at the ask, name the most sensitive driver, and state the covenant
floor or breach. The last section lists what the model cannot tell you: reassessment, the
premium holding, physical condition, and the seller's appetite, plus any low-confidence
extraction named in the facts."""


class ClaudeWriter:
    """Drafts the memo with the Claude API through a tool call, placeholders only."""

    name: str

    def __init__(self, client: Any | None = None, model: str | None = None) -> None:
        self._client = client
        self.model = model or DEFAULT_MODEL
        self.name = self.model

    @staticmethod
    def available() -> bool:
        return bool(os.environ.get("ANTHROPIC_API_KEY"))

    def _messages(self) -> Any:
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic()
        return self._client.messages

    def draft(self, facts: MemoFacts) -> Draft:
        table = "\n".join(
            f"- {{{k}}} = {v}  ({facts.descriptions.get(k, '')})" for k, v in facts.figures.items()
        )
        verdict = "clears" if facts.clears else "does not clear"
        low = (
            "Low-confidence extractions: " + "; ".join(facts.low_confidence) + "."
            if facts.low_confidence
            else "No low-confidence extractions."
        )
        prompt = (
            f"Case: {facts.case}. The levered IRR {verdict} the threshold.\n{low}\n\n"
            f"Facts table:\n{table}"
        )
        response = self._messages().create(
            model=self.model,
            max_tokens=1500,
            system=SYSTEM_PROMPT,
            tools=[MEMO_TOOL],
            tool_choice={"type": "tool", "name": "record_memo"},
            messages=[{"role": "user", "content": prompt}],
        )
        for block in response.content:
            if getattr(block, "type", "") == "tool_use":
                return Draft.model_validate(dict(block.input))
        raise ValueError("the model returned no memo record")


# --------------------------------------------------------------------------------------------
# Rendering and checks
# --------------------------------------------------------------------------------------------
class Memo(BaseModel):
    case: str
    recommendation: str
    body: list[str]
    cannot: list[str]
    writer: str
    fallback: bool = False
    problems: list[str] = []

    def markdown(self, deal: str) -> str:
        lines = [
            f"# {deal}: investment committee memo ({self.case} case)",
            "",
            self.recommendation,
            "",
            " ".join(self.body),
            "",
            "## What the model cannot tell you",
            "",
            *[f"- {item}" for item in self.cannot],
            "",
            f"Drafted by {self.writer}; every figure is a model output.",
        ]
        return "\n".join(lines) + "\n"


def check_draft(draft: Draft, facts: MemoFacts) -> list[str]:
    """Rules a draft must pass before its placeholders are filled."""
    problems: list[str] = []
    texts = [draft.recommendation, *draft.body, *draft.cannot]
    for text in texts:
        for token in TOKEN.findall(text):
            if token not in facts.figures:
                problems.append(f"unknown placeholder {{{token}}}")
        if DIGIT.search(TOKEN.sub("", text)):
            problems.append(f"digit written by the writer: {text[:60]!r}")
    for label in violations(" ".join(texts)):
        problems.append(f"banned: {label}")
    if "?" in " ".join(texts):
        problems.append("rhetorical question")
    if not draft.recommendation.startswith("Recommendation:"):
        problems.append("recommendation does not start with 'Recommendation:'")
    lowered = draft.recommendation.lower()
    if facts.clears and "bid" not in lowered:
        problems.append("levered IRR clears the threshold but the recommendation is not a bid")
    if not facts.clears and "pass" not in lowered:
        problems.append("levered IRR misses the threshold but the recommendation is not a pass")
    if "{bid}" not in draft.recommendation:
        problems.append("recommendation does not name the bid")
    if not 3 <= len(draft.body) <= 6:
        problems.append(f"body has {len(draft.body)} sentences; three to six required")
    if not 3 <= len(draft.cannot) <= 5:
        problems.append(f"cannot section has {len(draft.cannot)} items; three to five required")
    body_text = " ".join(draft.body)
    for required in ("{threshold}", "{levered_irr_at_ask}"):
        if required not in body_text:
            problems.append(f"body does not use {required}")
    if not any(t in body_text for t in ("{floor_dscr}", "{breach_dscr}")):
        problems.append("body does not state the covenant floor or breach")
    return problems


def fill(text: str, facts: MemoFacts) -> str:
    return TOKEN.sub(lambda m: facts.figures[m.group(1)], text)


def check_memo(memo: Memo, facts: MemoFacts) -> list[str]:
    """Second pass on the finished text: every number in it must be a facts value."""
    problems: list[str] = []
    allowed = set(facts.figures.values())
    texts = [memo.recommendation, *memo.body, *memo.cannot]
    number = re.compile(r"\$?\d[\d,]*(?:\.\d+)?(?:%|×|M|k| bps)?")
    for text in texts:
        for m in number.finditer(text):
            token = m.group(0)
            if token not in allowed and not any(token in v for v in allowed):
                problems.append(f"figure {token!r} is not a model output")
    for label in violations(" ".join(texts)):
        problems.append(f"banned: {label}")
    return problems


def write_memo(
    facts: MemoFacts,
    writer: Writer | None = None,
) -> Memo:
    """Draft with the writer, check, fill; fall back to the template when the draft fails."""
    if writer is None:
        writer = ClaudeWriter() if ClaudeWriter.available() else TemplateWriter()
    problems: list[str] = []
    fallback = False
    try:
        draft = writer.draft(facts)
        problems = check_draft(draft, facts)
    except Exception as exc:  # network or schema failure from the model
        problems = [f"writer failed: {exc}"]
    if problems and writer.name != TemplateWriter.name:
        fallback = True
        draft = TemplateWriter().draft(facts)
        template_problems = check_draft(draft, facts)
        assert not template_problems, template_problems
    memo = Memo(
        case=facts.case,
        recommendation=fill(draft.recommendation, facts),
        body=[fill(s, facts) for s in draft.body],
        cannot=[fill(s, facts) for s in draft.cannot],
        writer=TemplateWriter.name if fallback else writer.name,
        fallback=fallback,
        problems=problems,
    )
    memo.problems = problems + check_memo(memo, facts)
    return memo


def memo_from_mapping(data: Mapping[str, Any]) -> Memo:
    return Memo.model_validate(dict(data))
