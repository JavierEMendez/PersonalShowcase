"""Score a Screen result against the expected values for the Sawyer Bend package.

A figure passes when it is found, its value is within tolerance, its document matches, its page
matches when one is expected, and its confidence is at least the expected grade. The floor plan
rows are checked exactly.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.copilot.screen import CONFIDENCE_RANK, ScreenResult

EXPECTED_PATH = Path(__file__).with_name("expected.json")


@dataclass
class Row:
    key: str
    expected: str
    actual: str
    found: bool
    value_ok: bool
    document_ok: bool
    page_ok: bool
    confidence_ok: bool

    @property
    def passed(self) -> bool:
        return (
            self.found
            and self.value_ok
            and self.document_ok
            and self.page_ok
            and self.confidence_ok
        )

    def problems(self) -> str:
        out = []
        if not self.found:
            out.append("not found")
        else:
            if not self.value_ok:
                out.append("value")
            if not self.document_ok:
                out.append("document")
            if not self.page_ok:
                out.append("page")
            if not self.confidence_ok:
                out.append("confidence")
        return ", ".join(out) or "pass"


@dataclass
class Report:
    rows: list[Row]
    plan_problems: list[str]

    @property
    def passed(self) -> int:
        return sum(1 for r in self.rows if r.passed)

    @property
    def total(self) -> int:
        return len(self.rows)

    @property
    def ok(self) -> bool:
        return self.passed == self.total and not self.plan_problems

    def table(self) -> str:
        width = max(len(r.key) for r in self.rows)
        lines = [f"{'figure':<{width}}  {'expected':>14}  {'actual':>14}  result"]
        for r in self.rows:
            lines.append(f"{r.key:<{width}}  {r.expected:>14}  {r.actual:>14}  {r.problems()}")
        lines.append(f"{self.passed} of {self.total} figures pass")
        for p in self.plan_problems:
            lines.append(f"floor plans: {p}")
        return "\n".join(lines)


def load_expected(path: Path = EXPECTED_PATH) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def score(result: ScreenResult, expected: dict[str, Any] | None = None) -> Report:
    expected = expected or load_expected()
    rows: list[Row] = []
    for key, spec in expected["figures"].items():
        e = result.get(key)
        want = float(spec["value"])
        found = e is not None and e.value is not None
        actual = e.value if found and e is not None else None
        value_ok = found and actual is not None and abs(actual - want) <= float(spec["tolerance"])
        document_ok = found and e is not None and e.document == spec["document"]
        page_ok = found and e is not None and (spec.get("page") is None or e.page == spec["page"])
        confidence_ok = (
            found
            and e is not None
            and CONFIDENCE_RANK[e.confidence] >= CONFIDENCE_RANK[spec["min_confidence"]]
        )
        rows.append(
            Row(
                key=key,
                expected=f"{want:,.4g}" if want < 1 else f"{want:,.2f}".rstrip("0").rstrip("."),
                actual=""
                if actual is None
                else (f"{actual:,.4g}" if actual < 1 else f"{actual:,.2f}".rstrip("0").rstrip(".")),
                found=found,
                value_ok=value_ok,
                document_ok=document_ok,
                page_ok=page_ok,
                confidence_ok=confidence_ok,
            )
        )
    plan_problems: list[str] = []
    plans = {p.code: p for p in result.plans}
    for code, want_plan in expected.get("floor_plans", {}).items():
        plan = plans.get(code)
        if plan is None:
            plan_problems.append(f"{code} missing")
            continue
        for field_name, want_value in want_plan.items():
            got = getattr(plan, field_name)
            if abs(float(got) - float(want_value)) > 0.5:
                plan_problems.append(f"{code}.{field_name}: expected {want_value}, got {got}")
    return Report(rows=rows, plan_problems=plan_problems)
