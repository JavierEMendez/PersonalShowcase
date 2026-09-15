"""The Recommend step: an investment committee memo whose every figure comes from the model.

The bid rule is a levered LP IRR floor: a bid must return at least the floor to the limited
partners after debt service and the waterfall. The recommended bid is solved from it, the
highest price at which that return still reaches the floor, so the recommendation adjusts the
number rather than only grading the underwritten price.

The writer (a sentence template, or the Claude API when `ANTHROPIC_API_KEY` is set) produces
prose with placeholders such as `{lp_irr}`; it is not allowed to write a digit. The code then
fills every placeholder from a facts table built from the engine output, so a figure can only
appear in the memo if the model produced it. A draft that breaks a rule (an unknown
placeholder, a digit in the prose, a banned phrase, a missing section, a recommendation that
contradicts the floor test) is rejected and the template memo is used in its place, with the
rejection recorded on the memo.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from typing import Any, Literal, Protocol

from pydantic import BaseModel

from core.copilot.screen import ScreenResult
from core.copilot.sensitivity import StressRow
from core.copilot.summary import CopilotOutputs
from core.copy_rules import violations

DEFAULT_MODEL = os.environ.get("COPILOT_MODEL", "claude-sonnet-5")
LP_FLOOR = 0.15
# A recommended bid this far below the ask is not a bid a seller entertains; recommend a pass.
MAX_DISCOUNT_TO_ASK = 0.20
TOKEN = re.compile(r"\{([a-z0-9_]+)\}")
DIGIT = re.compile(r"\d")
# Names that carry digits but are not figures; stripped before the digit check.
ALLOWED_WITH_DIGITS = re.compile(r"\bT-?12\b|\bLP\b|\bGP\b", re.I)

Verdict = Literal["bid", "bid_lower", "pass"]


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
    verdict: Verdict
    figures: dict[str, str]
    descriptions: dict[str, str]
    has_breach: bool
    low_confidence: list[str]

    @property
    def clears(self) -> bool:
        return self.verdict == "bid"


def build_facts(
    out: CopilotOutputs,
    ask: CopilotOutputs,
    stress: list[StressRow],
    case: str,
    floor: float = LP_FLOOR,
    screen: ScreenResult | None = None,
    max_bid: float | None = None,
    at_max_bid: CopilotOutputs | None = None,
) -> MemoFacts:
    """`max_bid` is the highest price at which the LP IRR reaches the floor (None when no price
    above half the underwritten price does) and `at_max_bid` the engine output at that price."""
    s, r, ln, reno = out.summary, out.returns, out.loan, out.renovation
    lp = r.lp_irr or 0.0
    ask_price = s.asking_price or s.purchase_price
    if lp >= floor:
        verdict: Verdict = "bid"
    elif max_bid is not None and max_bid >= ask_price * (1 - MAX_DISCOUNT_TO_ASK):
        verdict = "bid_lower"
    else:
        verdict = "pass"
    growth = next((row for row in stress if row.label.startswith("Rent growth")), None)
    premium = next((row for row in stress if row.label.startswith("Renovation premium")), None)
    floor_row = min(stress, key=lambda row: row.min_dscr or 9.0) if stress else None
    breaches = [row for row in stress if not row.holds]
    figures: dict[str, str] = {
        "bid": _money_m(s.purchase_price),
        "ask": _money_m(ask_price),
        "price_per_unit": f"${s.price_per_unit:,.0f}",
        "units": f"{s.units}",
        "hold_years": f"{s.hold_months // 12}",
        "levered_irr": _pct(r.levered_irr),
        "unlevered_irr": _pct(r.unlevered_irr),
        "equity_multiple": _mult(r.equity_multiple),
        "lp_irr": _pct(r.lp_irr),
        "lp_multiple": _mult(r.lp_multiple),
        "gp_irr": _pct(r.gp_irr),
        "lp_floor": f"{floor:.0%}",
        "lp_vs_floor": (
            f"{abs(round((lp - floor) * 10_000)):,} bps " + ("above" if lp >= floor else "short of")
        ),
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
        "lp_irr_at_ask": _pct(ask.returns.lp_irr),
        "premium": f"${reno.premium_per_month:,.0f}",
        "renovation_units": f"{reno.units}",
        "renovation_cost": f"${reno.cost_per_unit:,.0f}",
        "taxes_share_of_opex": _pct(s.taxes_share_of_opex, 0),
        "discount_to_ask": _pct(s.discount_to_ask),
    }
    descriptions: dict[str, str] = {
        "bid": "the underwritten purchase price",
        "ask": "seller's asking price",
        "price_per_unit": "underwritten price per unit",
        "units": "unit count",
        "hold_years": "hold period in years",
        "levered_irr": "levered IRR at the underwritten price",
        "unlevered_irr": "unlevered IRR at the underwritten price",
        "equity_multiple": "equity multiple at the underwritten price",
        "lp_irr": "levered LP IRR after the waterfall at the underwritten price; the floor test",
        "lp_multiple": "LP equity multiple",
        "gp_irr": "GP IRR including promote",
        "lp_floor": "levered LP IRR floor a bid must clear",
        "lp_vs_floor": (
            "the LP IRR's distance from the floor with its direction, such as '200 bps short of'; "
            "always write it as '{lp_vs_floor} the {lp_floor} floor'"
        ),
        "year_one": "the words 'year 1'",
        "dscr_year1": "year 1 debt service coverage",
        "covenant_dscr": "DSCR covenant",
        "min_dscr": "lowest DSCR over the hold",
        "ltv": "loan to value",
        "debt_yield": "debt yield on year 1 NOI",
        "loan": "loan amount",
        "equity": "equity required",
        "going_in_cap": "going-in cap rate at the underwritten price",
        "cap_at_ask": "going-in cap rate at the ask",
        "exit_cap": "exit cap rate",
        "exit_value": "gross exit value",
        "levered_irr_at_ask": "levered IRR if bought at the ask",
        "lp_irr_at_ask": "LP IRR if bought at the ask",
        "premium": "renovation premium per month",
        "renovation_units": "units to renovate",
        "renovation_cost": "renovation cost per unit",
        "taxes_share_of_opex": "real estate taxes as a share of operating expenses",
        "discount_to_ask": "discount of the underwritten price to the ask",
    }
    if max_bid is not None and at_max_bid is not None:
        figures["max_bid"] = _money_m(max_bid)
        figures["max_bid_per_unit"] = f"${max_bid / s.units:,.0f}"
        figures["discount_max_bid"] = _pct(1 - max_bid / ask_price)
        figures["lp_irr_at_max_bid"] = _pct(at_max_bid.returns.lp_irr)
        figures["levered_irr_at_max_bid"] = _pct(at_max_bid.returns.levered_irr)
        figures["dscr_at_max_bid"] = _mult(at_max_bid.summary.dscr_year1)
        descriptions["max_bid"] = (
            "highest price at which the LP IRR reaches the floor; the recommended bid when the "
            "underwritten price misses"
        )
        descriptions["max_bid_per_unit"] = "that price per unit"
        descriptions["discount_max_bid"] = "discount of the maximum bid to the ask"
        descriptions["lp_irr_at_max_bid"] = "LP IRR at the maximum bid (the floor)"
        descriptions["levered_irr_at_max_bid"] = "levered IRR at the maximum bid"
        descriptions["dscr_at_max_bid"] = "year 1 DSCR at the maximum bid"
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
    if low:
        figures["low_confidence"] = "; ".join(low)
        descriptions["low_confidence"] = "the low-confidence extractions with their sources"
    return MemoFacts(
        case=case,
        verdict=verdict,
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
        has_max = "max_bid" in f
        if facts.verdict == "bid":
            recommendation = (
                "Recommendation: bid {bid}. The levered LP IRR of {lp_irr} is {lp_vs_floor} the "
                "{lp_floor} floor"
                + (
                    ", and the price could rise to {max_bid} before the floor binds"
                    if has_max
                    else ""
                )
                + ". Do not pursue at the {ask} ask."
            )
        elif facts.verdict == "bid_lower":
            recommendation = (
                "Recommendation: bid no more than {max_bid}, the price at which the levered LP IRR "
                "reaches the {lp_floor} floor, {discount_max_bid} below the {ask} ask. At the "
                "{bid} underwritten price the levered LP IRR is {lp_irr}, {lp_vs_floor} the floor."
            )
        elif has_max:
            recommendation = (
                "Recommendation: pass. The levered LP IRR reaches the {lp_floor} floor only at "
                "{max_bid}, {discount_max_bid} below the {ask} ask, and the underwritten {bid} "
                "returns {lp_irr} to the LP."
            )
        else:
            recommendation = (
                "Recommendation: pass. No price near the {ask} ask returns the {lp_floor} floor "
                "to the LP; the underwritten {bid} returns {lp_irr}."
            )
        body = [
            "At {bid} the deal returns a {levered_irr} levered IRR, a {lp_irr} levered LP IRR "
            "after the waterfall and a {equity_multiple} multiple, with a {year_one} DSCR of "
            "{dscr_year1} against a {covenant_dscr} covenant.",
        ]
        if has_max:
            body.append(
                "At {max_bid} ({max_bid_per_unit} per unit) the LP IRR is {lp_irr_at_max_bid}, the "
                "levered IRR {levered_irr_at_max_bid} and the {year_one} DSCR {dscr_at_max_bid}."
            )
        body.append(
            "At the {ask} ask the levered IRR falls to {levered_irr_at_ask} and the LP IRR to "
            "{lp_irr_at_ask}."
        )
        if "growth_stress" in f:
            body.append(
                "Returns are most sensitive to market rent growth: at {growth_stress} the levered "
                "IRR is {growth_stress_irr}."
            )
        if "premium_stress" in f:
            body.append(
                "The renovation premium carries the value-add thesis: at {premium_stress} rather "
                "than {premium} the levered IRR is {premium_stress_irr}."
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
        appetite = (
            "{discount_max_bid}" if facts.verdict != "bid" and has_max else "{discount_to_ask}"
        )
        cannot = [
            "Whether the appraisal district reassesses to the purchase price (taxes are "
            "{taxes_share_of_opex} of operating expenses).",
            "Whether the {premium} premium holds once {renovation_units} more renovated units "
            "reach the submarket.",
            "The condition of roofs and HVAC beyond the property condition sample.",
            f"The seller's appetite for a bid {appetite} below ask.",
        ]
        if "low_confidence" in f:
            cannot.append("Whether the low-confidence extractions hold: {low_confidence}.")
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
                    "One to three sentences starting with 'Recommendation:'. Bid, bid at a lower "
                    "price, or pass, with conditions."
                ),
            },
            "body": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Three to seven sentences, one per item, in reading order.",
            },
            "cannot": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Three to five items for the section 'What the model cannot tell you', "
                    "one sentence each, as separate array elements."
                ),
            },
        },
        "required": ["recommendation", "body", "cannot"],
    },
}

SYSTEM_PROMPT = """You draft investment committee memos for a multifamily acquisitions team.
You are given a facts table: placeholder names with their values and meanings. Write the memo
using placeholders in braces, such as {lp_irr}, wherever a figure belongs. Never write a digit
yourself; every number, percentage, multiple, dollar amount, count, page or row reference must be
a placeholder from the table. Use only placeholders that exist in the table.
Style: executive, bank style. Short declarative sentences. Say the number, then what it means.
No em dashes, no exclamation points, no rhetorical questions, no "it's not X, it's Y" or
"X, not Y" constructions, and none of these words: delve, leverage, robust, seamless, unlock,
empower, cutting-edge, game-changing.
The bid rule is a levered LP IRR floor (the LP return after debt service and the waterfall).
The verdict is given: "bid" means bid the underwritten price {bid}; "bid lower" means recommend
a bid no higher than {max_bid}, the price at which the LP IRR reaches the floor; "pass" means
recommend passing. Write to the committee, never about the verdict: do not write the words
"verdict", "bid lower case" or "floor test". The recommendation must use the word bid or pass to
match, and must name {bid} for a bid and {max_bid} for a lower bid. State the LP IRR against the
floor only as "{lp_irr} is {lp_vs_floor} the {lp_floor} floor"; that placeholder carries the
direction, so never write clears, exceeds, short or below around it yourself. Never cite a page
or row; {low_confidence} carries the citations when there are any. The body must state
the levered LP IRR against the {lp_floor} floor, the return at the ask, the most sensitive
driver, and the covenant floor or breach. The last section lists what the model cannot tell you:
reassessment, the premium holding, physical condition, the seller's appetite, and the
low-confidence extractions through {low_confidence} when that placeholder exists.
Format: body and cannot are JSON arrays of strings, one sentence per element, three to five
separate elements in cannot. Do not join them into a paragraph. The only digits allowed outside
placeholders are in the name T-12; write other counts and dates in words or leave them out."""


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
        verdict = {"bid": "bid", "bid_lower": "bid lower", "pass": "pass"}[facts.verdict]
        prompt = (
            f"Case: {facts.case}. Verdict from the floor test: {verdict}.\n\nFacts table:\n{table}"
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
                return draft_from_payload(block.input)
        raise ValueError("the model returned no memo record")


def draft_from_payload(raw: Any) -> Draft:
    """A Draft from the tool payload, tolerating lists or the whole record returned as JSON text."""
    if isinstance(raw, str):
        raw = json.loads(raw)
    data = dict(raw)
    for key in ("body", "cannot"):
        items = flatten_text(data.get(key))
        if len(items) == 1:
            items = split_items(items[0])
        data[key] = [i for i in items if i]
    rec = data.get("recommendation")
    if not isinstance(rec, str):
        data["recommendation"] = " ".join(flatten_text(rec))
    return Draft.model_validate(data)


def flatten_text(value: Any) -> list[str]:
    """Strings from any nesting of lists and objects; JSON text is decoded first."""
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        if text[:1] in "[{":
            try:
                return flatten_text(json.loads(text))
            except ValueError:
                pass
        return [text] if text else []
    if isinstance(value, Mapping):
        out: list[str] = []
        for v in value.values():
            out.extend(flatten_text(v))
        return out
    if isinstance(value, (list, tuple)):
        out = []
        for v in value:
            out.extend(flatten_text(v))
        return out
    return [str(value)]


_LIST_BREAK = re.compile(r"\n+|\s+(?=(?:[-*•]|\(?\d+[.)])\s)")
_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+(?=[A-Z{(\"])")
_SEMICOLON_BREAK = re.compile(r"\s*;\s+")


def split_items(text: str) -> list[str]:
    """A paragraph the model should have returned as a list, split into its items: on
    newlines, bullets or numbering when present, else on sentence ends, else on semicolons."""
    text = text.strip()
    if not text:
        return []
    for pattern in (_LIST_BREAK, _SENTENCE_BREAK, _SEMICOLON_BREAK):
        parts = [part.strip(" -*•\t") for part in pattern.split(text)]
        parts = [re.sub(r"^\(?\d+[.)]\s*", "", part).strip() for part in parts]
        parts = [part for part in parts if part]
        if len(parts) > 1:
            return parts
    return [text]


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
        stripped = ALLOWED_WITH_DIGITS.sub("", TOKEN.sub("", text))
        hit = DIGIT.search(stripped)
        if hit:
            around = stripped[max(0, hit.start() - 30) : hit.start() + 30].strip()
            problems.append(f"digit written by the writer: ...{around}...")
    for label in violations(" ".join(texts)):
        problems.append(f"banned: {label}")
    if "?" in " ".join(texts):
        problems.append("rhetorical question")
    if not draft.recommendation.startswith("Recommendation:"):
        problems.append("recommendation does not start with 'Recommendation:'")
    lowered = draft.recommendation.lower()
    if facts.verdict == "pass":
        if "pass" not in lowered:
            problems.append("the floor test says pass but the recommendation is not a pass")
    else:
        if "bid" not in lowered:
            problems.append("the floor test says bid but the recommendation is not a bid")
        wanted = "{bid}" if facts.verdict == "bid" else "{max_bid}"
        if wanted not in draft.recommendation:
            problems.append(f"recommendation does not name {wanted}")
    if not 3 <= len(draft.body) <= 7:
        problems.append(f"body has {len(draft.body)} sentences; three to seven required")
    if not 3 <= len(draft.cannot) <= 5:
        problems.append(f"cannot section has {len(draft.cannot)} items; three to five required")
    for sentence in texts:
        if "{lp_irr}" not in sentence:
            continue
        lowered_sentence = sentence.lower()
        says_clears = any(
            w in lowered_sentence for w in ("clears", "exceeds", "above the", "over the")
        )
        says_short = any(
            w in lowered_sentence for w in ("short of", "below the", "misses", "under the")
        )
        if facts.verdict == "bid" and says_short and not says_clears:
            problems.append("says the LP IRR misses the floor, but it clears it")
        if facts.verdict != "bid" and says_clears and not says_short:
            problems.append("says the LP IRR clears the floor, but it misses it")
    meta = ("bid lower case", "verdict", "floor test", "this is a bid", "this is a pass")
    if any(m in draft.recommendation.lower() for m in meta):
        problems.append("recommendation talks about the verdict instead of the deal")
    all_text = " ".join(texts)
    if "{lp_floor}" not in all_text:
        problems.append("memo does not use {lp_floor}")
    if not any(t in all_text for t in ("{levered_irr_at_ask}", "{lp_irr_at_ask}")):
        problems.append("memo does not state the return at the ask")
    if not any(t in all_text for t in ("{floor_dscr}", "{breach_dscr}")):
        problems.append("memo does not state the covenant floor or breach")
    return problems


def fill(text: str, facts: MemoFacts) -> str:
    return TOKEN.sub(lambda m: facts.figures[m.group(1)], text)


def check_memo(memo: Memo, facts: MemoFacts) -> list[str]:
    """Second pass on the finished text: every number in it must be a facts value."""
    problems: list[str] = []
    allowed = set(facts.figures.values())
    texts = [memo.recommendation, *memo.body, *memo.cannot]
    number = re.compile(r"\$?\d(?:[\d,]*\d)?(?:\.\d+)?(?:%|×|M|k| bps)?")
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
        if problems:
            received = (
                f"{draft.recommendation} | body: {' | '.join(draft.body)} | "
                f"cannot: {' | '.join(draft.cannot)}"
            )
            problems.append(f"draft as received: {received[:700]}")
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
