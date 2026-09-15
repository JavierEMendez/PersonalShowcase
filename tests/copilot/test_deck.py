"""The IC memo deck: two pages for a seeded case, three for a screened one, figures on the page."""

from __future__ import annotations

import datetime
import io
import json
from pathlib import Path

from pypdf import PdfReader

from core.copilot.deck import build_deck
from core.copilot.engine import run
from core.copilot.inputs import CopilotInputs
from core.copilot.memo import TemplateWriter, build_facts, write_memo
from core.copilot.screen import RuleReader, questions, screen
from core.copilot.sensitivity import at_price, stress_table
from evals.screen.run import load_sample

ROOT = Path(__file__).resolve().parents[2]


def _case(name: str) -> CopilotInputs:
    raw = json.loads((ROOT / "data" / "sawyer_bend.json").read_text(encoding="utf-8"))
    return CopilotInputs.model_validate(
        next(c["inputs"] for c in raw["cases"] if c["name"] == name)
    )


def _assumptions() -> list[dict[str, str]]:
    raw = json.loads((ROOT / "data" / "sawyer_bend.json").read_text(encoding="utf-8"))
    return list(raw["assumptions"])


def _deck(name: str, with_screen: bool = False) -> bytes:
    inputs = _case(name)
    out = run(inputs)
    acq = inputs.acquisition
    ask = run(at_price(inputs, acq.asking_price or acq.purchase_price))
    stress = stress_table(inputs)
    facts = build_facts(out, ask, stress, name)
    memo = write_memo(facts, TemplateWriter())
    result = screen(load_sample(), RuleReader()) if with_screen else None
    qa = []
    documents = []
    if result is not None:
        qa = [
            (q.prompt, q.extracted.display() if q.extracted else "", f"{q.prefill:,.4g}")
            for q in questions(inputs, result)
        ]
        documents = [
            ("OM", "sawyer-bend-om.pdf", "7 pages"),
            ("Rent roll", "sawyer-bend-rent-roll.xlsx", "294 rows"),
        ]
    return build_deck(
        "Sawyer Bend Apartments",
        "288 units · Northwest Houston",
        name,
        out,
        memo,
        stress,
        _assumptions(),
        0.12,
        screen=result,
        documents=documents,
        qa=qa,
        date=datetime.date(2026, 9, 14),
    )


def test_seeded_case_is_two_pages_with_the_memo_and_figures() -> None:
    pdf = _deck("Base")
    assert pdf.startswith(b"%PDF")
    reader = PdfReader(io.BytesIO(pdf))
    assert len(reader.pages) == 2
    page1 = reader.pages[0].extract_text()
    assert "Recommendation: bid $46.0M" in page1
    assert "Sawyer Bend Apartments" in page1 and "Base case" in page1
    assert "$46.0M" in page1 and "14.8%" in page1 and "1.89x" in page1
    assert "WHAT THE MODEL CANNOT TELL YOU" in page1
    assert "SOURCES AND USES" in page1 and "SENIOR LOAN" in page1
    page2 = reader.pages[1].extract_text()
    assert "NET OPERATING INCOME" in page2 and "WHAT BREAKS IT" in page2
    assert "UNIT MIX" in page2 and "EXTRACTED ASSUMPTIONS" in page2
    assert "Net operating income" in page2 and "2,639" in page2  # year 1 NOI in thousands
    assert "SEPTEMBER 14, 2026" in page1


def test_downside_case_reads_as_a_pass() -> None:
    reader = PdfReader(io.BytesIO(_deck("Downside")))
    assert "Recommendation: pass at $46.0M" in reader.pages[0].extract_text()
    assert "Breach" in reader.pages[1].extract_text()


def test_screened_case_adds_the_audit_page() -> None:
    reader = PdfReader(io.BytesIO(_deck("Base", with_screen=True)))
    assert len(reader.pages) == 3
    page3 = reader.pages[2].extract_text()
    assert "AUDIT TRAIL" in page3.upper() and "DOCUMENTS READ" in page3
    assert "sawyer-bend-om.pdf" in page3
    assert "Asking price" in page3 and "OM p. 2" in page3
    assert "QUESTIONS THE DOCUMENTS LEFT OPEN" in page3
    assert "Page 3" in page3
