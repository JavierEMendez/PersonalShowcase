"""The Screen step: documents, parsers, verification, questions, and the analyst's answers."""

from __future__ import annotations

import io
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from openpyxl import Workbook

from core.copilot.documents import Document, DocumentError, read_document
from core.copilot.engine import run
from core.copilot.inputs import CopilotInputs
from core.copilot.screen import (
    FIELDS,
    ClaudeReader,
    Extraction,
    RuleReader,
    answers_from_form,
    apply_screen,
    parse_answer,
    questions,
    screen,
    verify,
)
from evals.screen.run import load_sample
from evals.screen.score import score

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def documents() -> dict[str, Document]:
    return load_sample()


@pytest.fixture(scope="module")
def result(documents: dict[str, Document]) -> Any:
    return screen(documents, RuleReader())


# --- documents -------------------------------------------------------------------------------
def test_pdf_pages_and_spreadsheet_rows(documents: dict[str, Document]) -> None:
    om, rr, t12 = documents["om"], documents["rent_roll"], documents["t12"]
    assert len(om.pages) == 7 and om.page(2) is not None and "Asking price" in om.page(2).text  # type: ignore[union-attr]
    assert rr.rows[4][0] == "Unit" and rr.rows[5][0] == "0101"  # spreadsheet row 6 is index 5
    assert t12.rows[4][1] == "Sep-25"
    assert "row 6:" in rr.pages[0].text


def test_document_limits() -> None:
    with pytest.raises(DocumentError, match="not accepted"):
        read_document("om", "deal.docx", b"x")
    with pytest.raises(DocumentError, match="not a PDF"):
        read_document("om", "deal.pdf", b"hello")
    with pytest.raises(DocumentError, match="over 8 MB"):
        read_document("rent_roll", "big.csv", b"a" * (8 * 1024 * 1024 + 1))
    with pytest.raises(DocumentError, match="empty"):
        read_document("t12", "empty.xlsx", b"")


def test_csv_rent_roll_reads_numbers() -> None:
    csv = b'Unit,Status,Lease Rent\n101,Occupied,"$1,200"\n102,Vacant,\n'
    doc = read_document("rent_roll", "roll.csv", csv)
    assert doc.rows[1] == ["101", "Occupied", 1200.0] or doc.rows[1] == [101.0, "Occupied", 1200.0]


# --- extraction ------------------------------------------------------------------------------
def test_rule_reader_scores_every_figure(result: Any) -> None:
    report = score(result)
    assert report.ok, report.table()
    assert result.reader == "rules"
    assert [p.code for p in result.plans] == ["A1", "B2", "C2"]
    assert result.non_revenue_units == 2
    assert result.plans[0].unit_type == "1 x 1"  # unit type comes from the OM


def test_every_om_figure_is_quoted_from_its_page(
    result: Any, documents: dict[str, Document]
) -> None:
    om = documents["om"]
    for e in result.extractions:
        if e.document == "OM":
            page = om.page(int(e.page.split()[-1]))
            assert page is not None and e.quote in page.text, e


def test_verification_downgrades_bad_quotes(documents: dict[str, Document]) -> None:
    good = Extraction(
        key="asking_price",
        label="Asking price",
        value=50_500_000,
        document="OM",
        page="p. 2",
        quote="Asking price $50,500,000",
        confidence="High",
    )
    wrong_page = good.model_copy(update={"page": "p. 3"})
    wrong_figure = good.model_copy(update={"value": 48_000_000.0})
    invented = good.model_copy(update={"quote": "Asking price $48,000,000", "value": 48_000_000.0})
    checked = verify([good, wrong_page, wrong_figure, invented], documents)
    assert checked[0].confidence == "High"
    assert checked[1].confidence == "Low" and "cited page" in checked[1].note
    assert checked[2].confidence == "Low" and "figure not present" in checked[2].note
    assert checked[3].confidence == "Low"


def test_partial_packages(documents: dict[str, Document]) -> None:
    om_only = screen({"om": documents["om"]}, RuleReader())
    assert om_only.get("occupancy") is not None and om_only.get("occupancy").confidence == "Medium"  # type: ignore[union-attr]
    assert om_only.get("other_income") is None
    t12_only = screen({"t12": documents["t12"]}, RuleReader())
    assert t12_only.get("other_income") is not None  # unit count read from the statement header
    assert any("taken from the statement header" in n for n in t12_only.notes)


def test_t12_without_month_columns_is_reported() -> None:
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.append(["Line", "Total"])
    ws.append(["Other income", 1000])
    buf = io.BytesIO()
    wb.save(buf)
    doc = read_document("t12", "odd.xlsx", buf.getvalue())
    res = screen({"t12": doc}, RuleReader())
    assert res.extractions == [] and any("twelve month columns" in n for n in res.notes)


# --- Claude reader ---------------------------------------------------------------------------
class FakeMessages:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return SimpleNamespace(content=[SimpleNamespace(type="tool_use", input=self.payload)])


def test_claude_reader_parses_tool_payload_and_verifies(documents: dict[str, Document]) -> None:
    payload = {
        "extractions": [
            {
                "key": "asking_price",
                "value": 50500000,
                "page": 2,
                "quote": "Asking price $50,500,000",
                "confidence": "High",
            },
            {
                "key": "exit_cap",
                "value": 0.055,
                "page": 6,
                "quote": "Average cap rate across the five sales: 5.50%",
                "confidence": "Medium",
                "note": "Broker comps.",
            },
            {
                "key": "market_rent",
                "value": 1600,
                "page": 5,
                "quote": "Survey average asking rent: $1,600",
                "confidence": "High",
            },
            {"key": "units", "value": None, "page": 0, "quote": "", "confidence": "Low"},
            {"key": "not_a_field", "value": 1, "page": 1, "quote": "x", "confidence": "High"},
        ],
        "floor_plans": [
            {
                "code": "A1",
                "unit_type": "1 x 1",
                "units": 144,
                "sf": 720,
                "occupied": 136,
                "in_place_rent": 1245,
                "market_rent": 1310,
            }
        ],
    }
    fake = FakeMessages(payload)
    reader = ClaudeReader(client=SimpleNamespace(messages=fake), model="test-model")
    res = screen({"om": documents["om"]}, reader)
    assert res.reader == "test-model"
    assert fake.calls[0]["tool_choice"] == {"type": "tool", "name": "record_extractions"}
    assert "[page 2]" in fake.calls[0]["messages"][0]["content"]
    assert res.get("asking_price").confidence == "High"  # type: ignore[union-attr]
    assert res.get("exit_cap").confidence == "Medium"  # type: ignore[union-attr]
    invented = res.get("market_rent")
    assert invented is not None and invented.confidence == "Low" and "Unverified" in invented.note
    assert res.get("units") is None and any("units not found" in n for n in res.notes)
    assert res.plans[0].code == "A1"


# --- questions and answers -------------------------------------------------------------------
def load_base() -> CopilotInputs:
    import json

    raw = json.loads((ROOT / "data" / "sawyer_bend.json").read_text(encoding="utf-8"))
    return CopilotInputs.model_validate(raw["cases"][0]["inputs"])


def test_questions_cover_what_the_documents_leave_open(result: Any) -> None:
    base = load_base()
    asked = questions(base, result)
    keys = [q.key for q in asked]
    assert "loan.rate" in keys and "renovation.cost_per_unit" in keys  # never in documents
    assert "operating.tax_rate" not in keys  # found with High confidence, so not asked
    premium = next(q for q in asked if q.key == "renovation.premium_per_month")
    assert premium.extracted is not None and premium.prefill == 145
    insurance = next(q for q in asked if q.key == "operating.per_unit.Insurance")
    assert insurance.prefill == 720 and insurance.current == 850
    without_docs = questions(base, None)
    assert all(q.extracted is None and q.prefill == q.current for q in without_docs)


def test_answers_flow_into_the_inputs_and_the_engine(result: Any) -> None:
    base = load_base()
    asked = questions(base, result)
    form = {
        q.key: (f"{q.prefill * 100:g}" if q.kind == "pct" else f"{q.prefill:,.4f}") for q in asked
    }
    form["operating.controllable_per_unit"] = "3,850"
    form["operating.per_unit.Insurance"] = "$850"
    form["loan.ltv_max"] = "60%"
    parsed, errors = answers_from_form(form, asked)
    assert errors == [] and parsed["loan.ltv_max"] == pytest.approx(0.60)
    inputs = apply_screen(base, result, parsed)
    assert inputs.property.units == 288 and inputs.property.non_revenue_units == 2
    assert inputs.property.year_built == 2016 and inputs.acquisition.asking_price == 50_500_000
    assert inputs.operating.tax_rate == pytest.approx(0.0235)
    assert inputs.revenue.other_income_per_unit_month == pytest.approx(115)
    assert inputs.operating.per_unit["Insurance"] == 850
    assert sum(
        v for k, v in inputs.operating.per_unit.items() if k != "Insurance"
    ) == pytest.approx(3850, abs=3)
    assert inputs.loan.ltv_max == pytest.approx(0.60)
    out = run(inputs)
    base_out = run(base)
    # Same answers as the seed except the lower LTV: close to base, and identifiably different.
    assert abs((out.returns.levered_irr or 0) - (base_out.returns.levered_irr or 0)) < 0.02
    assert out.loan.amount < base_out.loan.amount


def test_parse_answer_and_errors() -> None:
    assert parse_answer("money", "$46,000,000") == 46_000_000
    assert parse_answer("pct", "5.5%") == pytest.approx(0.055)
    assert parse_answer("count", "1.25x") == 1.25
    with pytest.raises(ValueError):
        parse_answer("money", "")
    asked = questions(load_base(), None)
    _, errors = answers_from_form({"loan.rate": "five"}, asked)
    assert errors and "loan" in errors[0].lower() or "Fixed rate" in errors[0]


def test_catalogue_matches_expected_file() -> None:
    from evals.screen.score import load_expected

    assert set(load_expected()["figures"]) == {f.key for f in FIELDS}


def test_claude_reader_tolerates_stringified_payloads(documents: dict[str, Document]) -> None:
    import json

    items = [
        {
            "key": "asking_price",
            "value": 50500000,
            "page": 2,
            "quote": "Asking price $50,500,000",
            "confidence": "High",
        },
        {"key": "units", "value": 288, "page": 3, "quote": "Units 288", "confidence": "High"},
    ]
    payload = {
        "extractions": json.dumps(items[:1]) + "",  # the whole list as a JSON string
        "floor_plans": [
            json.dumps(
                {"code": "A1", "units": 144, "sf": 720, "in_place_rent": 1245, "market_rent": 1310}
            ),
            "garbage",
            7,
        ],
    }
    payload["extractions"] = [json.dumps(items[0]), items[1], "not json", 5]
    fake = FakeMessages(payload)
    reader = ClaudeReader(client=SimpleNamespace(messages=fake), model="test-model")
    res = screen({"om": documents["om"]}, reader)
    assert res.get("asking_price") is not None and res.get("units") is not None
    assert res.plans and res.plans[0].code == "A1"
    # A whole list as a JSON string is also accepted.
    fake_str = FakeMessages({"extractions": json.dumps(items)})
    res2 = screen(
        {"om": documents["om"]}, ClaudeReader(client=SimpleNamespace(messages=fake_str), model="m")
    )
    assert res2.get("units") is not None and res2.get("units").confidence == "High"  # type: ignore[union-attr]


def test_claude_reader_tolerates_labels_and_string_values(documents: dict[str, Document]) -> None:
    from core.copilot.screen import coerce_number, match_key

    assert match_key("Asking price") == "asking_price"
    assert match_key("om.exit_cap") == "exit_cap" and match_key("Exit Cap Rate") == "exit_cap"
    assert match_key("units") == "units" and match_key("broker name") is None
    assert coerce_number("$50,500,000", "money") == 50_500_000
    assert coerce_number("5.50%", "pct") == pytest.approx(0.055)
    assert (
        coerce_number(5.5, "pct") == pytest.approx(0.055) and coerce_number(0.055, "pct") == 0.055
    )
    assert (
        coerce_number("261,360 SF", "sf") == 261_360
        and coerce_number("not stated", "money") is None
    )
    payload = {
        "extractions": [
            {
                "key": "Asking price",
                "value": "$50,500,000",
                "page": "p. 2",
                "quote": "Asking price $50,500,000",
                "confidence": "high",
            },
            {
                "name": "Exit cap rate",
                "value": "5.50%",
                "page": 6,
                "quote": "Average cap rate across the five sales: 5.50%",
                "confidence": "Medium",
            },
            {"key": "Broker", "value": "Ridgeline", "page": 1, "quote": "", "confidence": "High"},
        ],
        "floor_plans": [
            {
                "plan": "A1",
                "type": "1 x 1",
                "units": "144",
                "avg_sf": "720",
                "occupied": "136",
                "in_place_rent": "$1,245",
                "market_rent": "$1,310",
            }
        ],
    }
    fake = FakeMessages(payload)
    res = screen(
        {"om": documents["om"]}, ClaudeReader(client=SimpleNamespace(messages=fake), model="m")
    )
    ask = res.get("asking_price")
    assert (
        ask is not None
        and ask.value == 50_500_000
        and ask.page == "p. 2"
        and ask.confidence == "High"
    )
    cap = res.get("exit_cap")
    assert cap is not None and cap.value == pytest.approx(0.055) and cap.confidence == "Medium"
    assert res.plans[0].units == 144 and res.plans[0].sf == 720
    assert any("did not match the catalogue: Broker" in n for n in res.notes)
    empty = screen(
        {"om": documents["om"]},
        ClaudeReader(client=SimpleNamespace(messages=FakeMessages({"figures": []})), model="m"),
    )
    assert any(
        "no usable figures; payload shape {figures: list[0] of nothing}" in n for n in empty.notes
    )


def test_claude_reader_accepts_an_object_keyed_by_figure(documents: dict[str, Document]) -> None:
    payload = {
        "extractions": {
            "asking_price": {
                "value": 50500000,
                "page": 2,
                "quote": "Asking price $50,500,000",
                "confidence": "High",
            },
            "units": 288,
            "year_built": {
                "value": "2016",
                "page": "3",
                "quote": "Year built 2016",
                "confidence": "High",
            },
        },
        "floor_plans": {
            "A1": {
                "units": 144,
                "sf": 720,
                "occupied": 136,
                "in_place_rent": 1245,
                "market_rent": 1310,
            }
        },
    }
    fake = FakeMessages(payload)
    res = screen(
        {"om": documents["om"]}, ClaudeReader(client=SimpleNamespace(messages=fake), model="m")
    )
    assert res.get("asking_price").value == 50_500_000  # type: ignore[union-attr]
    assert res.get("year_built").value == 2016 and res.get("year_built").page == "p. 3"  # type: ignore[union-attr]
    units = res.get("units")
    assert (
        units is not None and units.value == 288 and units.confidence == "Low"
    )  # no quote: unverified
    assert res.plans and res.plans[0].code == "A1" and res.plans[0].units == 144
    assert not any("did not match" in n for n in res.notes)


def test_claude_reader_finds_records_in_nested_payloads(documents: dict[str, Document]) -> None:
    from core.copilot.screen import describe_shape, find_records

    record = {
        "key": "asking_price",
        "value": 50500000,
        "page": 2,
        "quote": "Asking price $50,500,000",
        "confidence": "High",
    }
    plan = {
        "code": "A1",
        "units": 144,
        "sf": 720,
        "occupied": 136,
        "in_place_rent": 1245,
        "market_rent": 1310,
    }
    shapes: list[dict[str, Any]] = [
        {"extractions": {"extractions": [record], "floor_plans": [plan]}},  # wrapped one level
        {"record_extractions": {"extractions": [record], "floor_plans": {"A1": plan}}},
        {"extractions": json.dumps([record]), "floor_plans": json.dumps([plan])},
        {
            "data": {
                "figures": {"asking_price": {k: v for k, v in record.items() if k != "key"}},
                "unit_mix": [plan],
            }
        },
    ]
    for payload in shapes:
        fake = FakeMessages(payload)
        res = screen(
            {"om": documents["om"]}, ClaudeReader(client=SimpleNamespace(messages=fake), model="m")
        )
        ask = res.get("asking_price")
        assert ask is not None and ask.value == 50_500_000 and ask.confidence == "High", payload
        assert res.plans and res.plans[0].code == "A1" and res.plans[0].units == 144, payload
    assert find_records({"x": [{"a": 1}]}, ("key", "value")) == []
    empty = screen(
        {"om": documents["om"]},
        ClaudeReader(client=SimpleNamespace(messages=FakeMessages({"figures": "none"})), model="m"),
    )
    assert any("payload shape {figures: text(4)}" in n for n in empty.notes)
    assert describe_shape({"a": [{"b": 1}]}) == "{a: list[1] of {b: int}}"
