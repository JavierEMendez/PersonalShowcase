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

NUMBER = re.compile(r"\$?\d(?:[\d,]*\d)?(?:\.\d+)?(?:%|×|M|k| bps)?")


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
    if facts.verdict == "pursue" and "pursue" not in lowered:
        report.problems.append("ask inside the range but not a pursue")
    if facts.verdict == "engage":
        if facts.figures["range_max"] not in memo.recommendation or "below" not in lowered:
            report.problems.append("ask above the range but the max is not named as the cap")
    if facts.verdict == "pass" and "pass" not in lowered:
        report.problems.append("no price returns the target but not a pass")
    if not 3 <= len(memo.body) <= 7:
        report.problems.append(f"body has {len(memo.body)} sentences")
    if not 3 <= len(memo.cannot) <= 5:
        report.problems.append(f"cannot section has {len(memo.cannot)} items")
    body = " ".join([memo.recommendation, *memo.body])
    if facts.verdict != "pass":
        for key in ("range_low", "range_mid", "range_max"):
            if facts.figures[key] not in body:
                report.problems.append(f"memo omits {key}")
    if not any(facts.figures[k] in body for k in ("lp_ask", "lev_ask")):
        report.problems.append("memo omits the return at the ask")
    if memo.fallback:
        report.problems.append("writer draft rejected, template used")
    return report
