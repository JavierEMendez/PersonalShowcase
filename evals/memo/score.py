"""Score a memo: figure fidelity, copy rules, structure, and agreement with the floor test.

Fidelity is the check that matters. Every number in the finished memo must be a value in the
facts table built from the engine output; a number the writer produced on its own is a failure
even when it happens to be right.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from core.copilot.memo import Memo, MemoFacts
from core.copy_rules import violations

NUMBER = re.compile(r"\$?\d[\d,]*(?:\.\d+)?(?:%|×|M|k| bps)?")


@dataclass
class MemoReport:
    case: str
    writer: str
    fallback: bool
    figures_checked: int = 0
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems

    def line(self) -> str:
        status = "pass" if self.ok else "; ".join(self.problems)
        via = f"{self.writer}{' (fallback)' if self.fallback else ''}"
        return f"{self.case:<10} {via:<24} {self.figures_checked:>3} figures  {status}"


def score_memo(memo: Memo, facts: MemoFacts) -> MemoReport:
    report = MemoReport(case=memo.case, writer=memo.writer, fallback=memo.fallback)
    texts = [memo.recommendation, *memo.body, *memo.cannot]
    allowed = set(facts.figures.values())
    for text in texts:
        for m in NUMBER.finditer(text):
            token = m.group(0)
            report.figures_checked += 1
            if token not in allowed and not any(token in v for v in allowed):
                report.problems.append(f"figure {token!r} not a model output")
    joined = " ".join(texts)
    report.problems += [f"banned: {label}" for label in violations(joined)]
    if "?" in joined:
        report.problems.append("rhetorical question")
    if not memo.recommendation.startswith("Recommendation:"):
        report.problems.append("no 'Recommendation:' lead")
    lowered = memo.recommendation.lower()
    if facts.verdict == "pass":
        if "pass" not in lowered:
            report.problems.append("floor test says pass but not a pass")
    else:
        if "bid" not in lowered:
            report.problems.append("floor test says bid but not a bid")
        wanted = facts.figures["bid" if facts.verdict == "bid" else "max_bid"]
        if wanted not in memo.recommendation:
            report.problems.append("recommendation does not name the bid price")
    if not 3 <= len(memo.body) <= 6:
        report.problems.append(f"body has {len(memo.body)} sentences")
    if not 3 <= len(memo.cannot) <= 5:
        report.problems.append(f"cannot section has {len(memo.cannot)} items")
    body = " ".join([memo.recommendation, *memo.body])
    if facts.figures["lp_floor"] not in body:
        report.problems.append("memo omits the LP floor")
    if not any(facts.figures[k] in body for k in ("levered_irr_at_ask", "lp_irr_at_ask")):
        report.problems.append("memo omits the return at the ask")
    if not any(
        k in facts.figures and facts.figures[k] in body for k in ("floor_dscr", "breach_dscr")
    ):
        report.problems.append("body omits the covenant floor or breach")
    if memo.fallback:
        report.problems.append("writer draft rejected, template used")
    return report
