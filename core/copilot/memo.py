"""The Recommend step: a screening memo whose every figure comes from the model.

The recommendation is a valuation range. Max is the price at which the levered LP IRR (the
limited partners' return after debt service and the waterfall) reaches 13%; mid the price at
15%; low the lower of the price at 17% and 20% below the ask. The verdict reads off where the ask
sits: pursue when the ask is inside the range, engage the seller below the max when it is above
it, pass when no price in reach returns 13%.

The writer (a sentence template, or the Claude API when `ANTHROPIC_API_KEY` is set) produces
prose with placeholders such as `{range_mid}`; it is not allowed to write a digit. The code then
fills every placeholder from a facts table built from the engine output, so a figure can only
appear in the memo if the model produced it. A draft that breaks a rule (an unknown
placeholder, a digit in the prose, a banned phrase, a missing section, a recommendation that
contradicts the verdict) is rejected and the template memo is used in its place, with the
rejection recorded on the memo.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from typing import Any, Protocol

from pydantic import BaseModel

from core.copilot.recommend import LP_TARGETS, PricePoint, ValuationRange, Verdict
from core.copilot.screen import ScreenResult
from core.copilot.sensitivity import StressRow
from core.copilot.summary import CopilotOutputs
from core.copy_rules import violations

DEFAULT_MODEL = os.environ.get("COPILOT_MODEL", "claude-sonnet-5")
TOKEN = re.compile(r"\{([a-z0-9_]+)\}")
DIGIT = re.compile(r"\d")
# Names that carry digits but are not figures; stripped before the digit check.
ALLOWED_WITH_DIGITS = re.compile(r"\bT-?12\b|\bLP\b|\bGP\b", re.I)


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


def _point_figures(
    key: str,
    p: PricePoint,
    figures: dict[str, str],
    descriptions: dict[str, str],
    meaning: str,
) -> None:
    figures[f"range_{key}"] = _money_m(p.price)
    figures[f"per_unit_{key}"] = f"${p.per_unit:,.0f}"
    figures[f"discount_{key}"] = _pct(p.discount_to_ask)
    figures[f"lp_{key}"] = _pct(p.lp_irr)
    figures[f"lev_{key}"] = _pct(p.levered_irr)
    figures[f"em_{key}"] = _mult(p.equity_multiple)
    figures[f"cap_{key}"] = _pct(p.going_in_cap, 2)
    figures[f"dscr_{key}"] = _mult(p.dscr_year1)
    descriptions[f"range_{key}"] = f"{meaning}; set by {p.basis}"
    descriptions[f"per_unit_{key}"] = f"price per unit at the {key} price"
    descriptions[f"discount_{key}"] = f"discount of the {key} price to the ask"
    descriptions[f"lp_{key}"] = f"levered LP IRR at the {key} price"
    descriptions[f"lev_{key}"] = f"levered IRR at the {key} price"
    descriptions[f"em_{key}"] = f"equity multiple at the {key} price"
    descriptions[f"cap_{key}"] = f"going-in cap rate at the {key} price"
    descriptions[f"dscr_{key}"] = f"year 1 DSCR at the {key} price"


def build_facts(
    out: CopilotOutputs,
    valuation: ValuationRange,
    stress: list[StressRow],
    case: str,
    screen: ScreenResult | None = None,
) -> MemoFacts:
    """`out` is the engine output at the underwritten price; the range carries the rest."""
    s, r, ln, reno = out.summary, out.returns, out.loan, out.renovation
    growth = next((row for row in stress if row.label.startswith("Rent growth")), None)
    premium = next((row for row in stress if row.label.startswith("Renovation premium")), None)
    floor_row = min(stress, key=lambda row: row.min_dscr or 9.0) if stress else None
    breaches = [row for row in stress if not row.holds]
    ask = valuation.at_ask
    figures: dict[str, str] = {
        "ask": _money_m(valuation.ask),
        "per_unit_ask": f"${ask.per_unit:,.0f}",
        "lp_ask": _pct(ask.lp_irr),
        "lev_ask": _pct(ask.levered_irr),
        "cap_ask": _pct(ask.going_in_cap, 2),
        "underwritten": _money_m(s.purchase_price),
        "units": f"{s.units}",
        "hold_years": f"{s.hold_months // 12}",
        "levered_irr": _pct(r.levered_irr),
        "unlevered_irr": _pct(r.unlevered_irr),
        "equity_multiple": _mult(r.equity_multiple),
        "lp_irr": _pct(r.lp_irr),
        "target_max": f"{LP_TARGETS['max']:.0%}",
        "target_mid": f"{LP_TARGETS['mid']:.0%}",
        "target_low": f"{LP_TARGETS['low']:.0%}",
        "year_one": "year 1",
        "dscr_year1": _mult(s.dscr_year1),
        "covenant_dscr": _mult(ln.covenant_dscr),
        "min_dscr": _mult(s.min_dscr),
        "ltv": _pct(s.ltv),
        "debt_yield": _pct(s.debt_yield),
        "loan": _money_m(ln.amount),
        "equity": _money_m(out.sources_uses.equity),
        "going_in_cap": _pct(s.going_in_cap, 2),
        "exit_cap": _pct(out.exit.cap_rate, 2),
        "exit_value": _money_m(s.exit_value),
        "premium": f"${reno.premium_per_month:,.0f}",
        "renovation_units": f"{reno.units}",
        "renovation_cost": f"${reno.cost_per_unit:,.0f}",
        "taxes_share_of_opex": _pct(s.taxes_share_of_opex, 0),
    }
    descriptions: dict[str, str] = {
        "ask": "seller's asking price",
        "per_unit_ask": "asking price per unit",
        "lp_ask": "levered LP IRR if bought at the ask",
        "lev_ask": "levered IRR if bought at the ask",
        "cap_ask": "going-in cap rate at the ask",
        "underwritten": "the price the base underwriting uses",
        "units": "unit count",
        "hold_years": "hold period in years",
        "levered_irr": "levered IRR at the underwritten price",
        "unlevered_irr": "unlevered IRR at the underwritten price",
        "equity_multiple": "equity multiple at the underwritten price",
        "lp_irr": "levered LP IRR at the underwritten price",
        "target_max": "LP IRR that sets the max price",
        "target_mid": "LP IRR that sets the mid price",
        "target_low": "LP IRR that sets the low price unless the ask cap binds",
        "year_one": "the words 'year 1'",
        "dscr_year1": "year 1 DSCR at the underwritten price",
        "covenant_dscr": "DSCR covenant",
        "min_dscr": "lowest DSCR over the hold at the underwritten price",
        "ltv": "loan to value",
        "debt_yield": "debt yield on year 1 NOI",
        "loan": "loan amount at the underwritten price",
        "equity": "equity required at the underwritten price",
        "going_in_cap": "going-in cap rate at the underwritten price",
        "exit_cap": "exit cap rate",
        "exit_value": "gross exit value",
        "premium": "renovation premium per month",
        "renovation_units": "units to renovate",
        "renovation_cost": "renovation cost per unit",
        "taxes_share_of_opex": "real estate taxes as a share of operating expenses",
    }
    meanings = {
        "low": "low end of the range: buy with confidence",
        "mid": "mid of the range: the price to open at",
        "max": "top of the range: the most the deal can bear",
    }
    for key, point in (("low", valuation.low), ("mid", valuation.mid), ("max", valuation.max)):
        if point is not None:
            _point_figures(key, point, figures, descriptions, meanings[key])
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
        verdict=valuation.verdict,
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
        has_range = "range_max" in f and "range_mid" in f
        if facts.verdict == "pursue":
            recommendation = (
                "Recommendation: pursue. The {ask} ask sits inside the range of {range_low} to "
                "{range_max}: it returns {lp_ask} to the LP against the {target_max} that sets "
                "the top of the range. Open at {range_mid} and hold {range_max} as the ceiling."
            )
        elif facts.verdict == "engage":
            recommendation = (
                "Recommendation: worth a full underwriting only if the seller engages at or "
                "below {range_max}, {discount_max} below the {ask} ask. Open at {range_mid} "
                "({per_unit_mid} per unit); {range_low} is the price to buy with confidence. At "
                "the ask the levered LP IRR is {lp_ask}."
            )
        else:
            recommendation = (
                "Recommendation: pass. No price in reach returns {target_max} to the LP; at the "
                "{ask} ask the levered LP IRR is {lp_ask}."
            )
        body = []
        if has_range:
            body.append(
                "The range is set by the levered LP IRR after debt service and the waterfall: "
                "{range_max} returns {target_max}, {range_mid} returns {target_mid}, and "
                "{range_low} is the lower of the {target_low} price and the ask less a fifth."
            )
            body.append(
                "At {range_mid} the deal shows a {cap_mid} going-in cap, a {lev_mid} levered IRR, "
                "a {em_mid} multiple and a {year_one} DSCR of {dscr_mid} against a "
                "{covenant_dscr} covenant."
            )
        body.append(
            "At the {ask} ask ({per_unit_ask} per unit) the going-in cap is {cap_ask}, the "
            "levered IRR {lev_ask} and the levered LP IRR {lp_ask}."
        )
        if "growth_stress" in f:
            body.append(
                "Returns are most sensitive to market rent growth: at {growth_stress} the levered "
                "IRR at the underwritten {underwritten} is {growth_stress_irr}."
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
        appetite = "{discount_max}" if has_range else "{discount_low}"
        cannot = [
            "Whether the appraisal district reassesses to the purchase price (taxes are "
            "{taxes_share_of_opex} of operating expenses).",
            "Whether the {premium} premium holds once {renovation_units} more renovated units "
            "reach the submarket.",
            "The condition of roofs and HVAC beyond the property condition sample.",
            f"The seller's appetite for a price {appetite} below ask.",
        ]
        if "low_confidence" in f:
            cannot.append("Whether the low-confidence extractions hold: {low_confidence}.")
        return Draft(recommendation=recommendation, body=body, cannot=cannot)


MEMO_TOOL: dict[str, Any] = {
    "name": "record_memo",
    "description": "Record the screening memo.",
    "input_schema": {
        "type": "object",
        "properties": {
            "recommendation": {
                "type": "string",
                "description": (
                    "One to three sentences starting with 'Recommendation:'. Pursue, engage the "
                    "seller below the max, or pass, naming the range."
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

SYSTEM_PROMPT = """You draft screening memos for a multifamily acquisitions team. The memo decides
whether a deal is worth a full underwriting and at what price.
You are given a facts table: placeholder names with their values and meanings. Write the memo
using placeholders in braces, such as {range_mid}, wherever a figure belongs. Never write a digit
yourself; every number, percentage, multiple, dollar amount, count, page or row reference must be
a placeholder from the table. Use only placeholders that exist in the table.
Style: executive, bank style. Short declarative sentences. Say the number, then what it means.
No em dashes, no exclamation points, no rhetorical questions, no "it's not X, it's Y" or
"X, not Y" constructions, and none of these words: delve, leverage, robust, seamless, unlock,
empower, cutting-edge, game-changing.
The recommendation is a valuation range: {range_max} is the most the deal can bear (levered LP
IRR of {target_max}), {range_mid} is the price to open at ({target_mid}), {range_low} is the
price to buy with confidence. The verdict is given: "pursue" means the ask sits inside the range
and the recommendation must contain the word pursue; "engage" means the ask is above the max and
the recommendation must say the deal is worth a full underwriting only at or below {range_max};
"pass" means no price in reach returns {target_max} and the recommendation must contain the word
pass. Write to the committee, never about the verdict: do not write the words "verdict" or
"case". State the range and what sets it, the figures at the mid price, the figures at the ask,
the most sensitive driver, and the covenant floor or breach. The last section lists what the
model cannot tell you: reassessment, the premium holding, physical condition, the seller's
appetite, and the low-confidence extractions through {low_confidence} when that placeholder
exists. Never cite a page or row; {low_confidence} carries the citations.
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
        prompt = f"Deal: {facts.case}. Verdict: {facts.verdict}.\n\nFacts table:\n{table}"
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
            f"# {deal}: screening memo ({self.case} case)",
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
    if facts.verdict == "pursue" and "pursue" not in lowered:
        problems.append("the ask sits inside the range but the recommendation does not say pursue")
    if facts.verdict == "engage":
        if "{range_max}" not in draft.recommendation or "below" not in lowered:
            problems.append(
                "the ask is above the range but the recommendation does not cap it at {range_max}"
            )
        if "full underwriting" not in lowered:
            problems.append("an engage recommendation must say what a full underwriting depends on")
    if facts.verdict == "pass" and "pass" not in lowered:
        problems.append("no price returns the target but the recommendation is not a pass")
    meta = ("verdict", "this is a", "the case is")
    if any(m in lowered for m in meta):
        problems.append("recommendation talks about the verdict instead of the deal")
    if not 3 <= len(draft.body) <= 7:
        problems.append(f"body has {len(draft.body)} sentences; three to seven required")
    if not 3 <= len(draft.cannot) <= 5:
        problems.append(f"cannot section has {len(draft.cannot)} items; three to five required")
    all_text = " ".join(texts)
    if facts.verdict != "pass":
        for required in ("{range_low}", "{range_mid}", "{range_max}"):
            if required not in all_text:
                problems.append(f"memo does not state {required}")
    if "{lp_ask}" not in all_text and "{lev_ask}" not in all_text:
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
