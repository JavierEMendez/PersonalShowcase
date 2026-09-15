"""The Screen step: read the documents, extract model inputs with citations, ask about the rest.

Structured files (the rent roll and the T-12) are parsed deterministically; their figures are
sums and averages over rows, which is not a job for a language model. The offering memorandum
is prose and tables, and is read by the Claude API when `ANTHROPIC_API_KEY` is set and by a
rule-based reader otherwise. Every extraction carries the document, the page or rows, a
verbatim quote and a confidence grade, and every quote is checked against the document text
before it is shown. Inputs the documents never carry, and extractions that came back weak, turn
into questions; answers flow into the typed inputs and the Underwrite step runs from there.
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from pydantic import BaseModel

from core.copilot.documents import Cell, Document, Kind
from core.copilot.inputs import CopilotInputs, FloorPlan

log = logging.getLogger(__name__)

Confidence = Literal["High", "Medium", "Low"]
CONFIDENCE_RANK: dict[str, int] = {"High": 3, "Medium": 2, "Low": 1}
DEFAULT_MODEL = os.environ.get("COPILOT_MODEL", "claude-sonnet-5")

# Expense lines the buyer controls; insurance and taxes are underwritten separately.
CONTROLLABLE_LINES = [
    "Payroll",
    "Repairs and maintenance",
    "Turnover",
    "Contract services",
    "Marketing",
    "Administrative",
    "Utilities",
]


@dataclass(frozen=True)
class FieldSpec:
    key: str
    label: str
    unit: str
    kind: Literal["money", "count", "rent", "pct", "sf", "year", "per_unit_year"]
    document: Kind
    description: str  # what the reader is asked to find


# The catalogue of figures the Screen step looks for. Order is display order.
FIELDS: list[FieldSpec] = [
    FieldSpec(
        "asking_price",
        "Asking price",
        "$",
        "money",
        "om",
        "The seller's asking or whisper price for the whole property.",
    ),
    FieldSpec("units", "Units", "units", "count", "om", "Total apartment units."),
    FieldSpec("year_built", "Year built", "", "year", "om", "Year the property was built."),
    FieldSpec(
        "rentable_sf",
        "Rentable square feet",
        "SF",
        "sf",
        "om",
        "Total rentable or net rentable square feet.",
    ),
    FieldSpec(
        "in_place_rent",
        "In-place rent",
        "$ / unit / mo",
        "rent",
        "rent_roll",
        "Average lease rent of occupied units per month.",
    ),
    FieldSpec(
        "occupancy", "Occupancy", "%", "pct", "rent_roll", "Occupied units divided by total units."
    ),
    FieldSpec(
        "market_rent",
        "Market rent",
        "$ / unit / mo",
        "rent",
        "om",
        "Average market or survey rent for an unrenovated unit per month.",
    ),
    FieldSpec(
        "renovated_units",
        "Units already renovated",
        "units",
        "count",
        "om",
        "Units the seller has already renovated.",
    ),
    FieldSpec(
        "renovation_premium",
        "Renovation premium",
        "$ / unit / mo",
        "rent",
        "om",
        "Monthly rent premium renovated units achieve over classic units.",
    ),
    FieldSpec(
        "exit_cap", "Exit cap rate", "%", "pct", "om", "Average cap rate of the sale comparables."
    ),
    FieldSpec(
        "tax_rate",
        "Tax rate",
        "%",
        "pct",
        "om",
        "Combined property tax rate applied to assessed value.",
    ),
    FieldSpec(
        "other_income",
        "Other income",
        "$ / unit / mo",
        "rent",
        "t12",
        "Trailing twelve months of other income per unit per month.",
    ),
    FieldSpec(
        "controllable_expenses",
        "Controllable expenses",
        "$ / unit / yr",
        "per_unit_year",
        "t12",
        "Trailing twelve months of controllable operating expenses per unit.",
    ),
    FieldSpec(
        "insurance",
        "Insurance",
        "$ / unit / yr",
        "per_unit_year",
        "t12",
        "Trailing twelve months of property insurance per unit.",
    ),
    FieldSpec(
        "taxes_t12",
        "Real estate taxes, T-12",
        "$ / yr",
        "money",
        "t12",
        "Trailing twelve months of real estate taxes paid by the seller.",
    ),
]
FIELD_BY_KEY: dict[str, FieldSpec] = {f.key: f for f in FIELDS}
OM_FIELDS: list[FieldSpec] = [f for f in FIELDS if f.document == "om"]


class Extraction(BaseModel):
    key: str
    label: str
    value: float | None
    unit: str = ""
    document: str = ""
    page: str = ""
    quote: str = ""
    confidence: Confidence = "Low"
    note: str = ""
    # Set for per-floor-plan facts; empty for the catalogue figures.
    plan: str = ""

    def display(self) -> str:
        return format_value(
            self.value, FIELD_BY_KEY[self.key].kind if self.key in FIELD_BY_KEY else "money"
        )


class PlanFacts(BaseModel):
    code: str
    unit_type: str = ""
    units: int = 0
    sf: float = 0.0
    occupied: int = 0
    in_place_rent: float = 0.0
    market_rent: float = 0.0


class ScreenResult(BaseModel):
    extractions: list[Extraction]
    plans: list[PlanFacts]
    non_revenue_units: int = 0
    reader: str  # "rules" or the model id
    notes: list[str]

    def get(self, key: str) -> Extraction | None:
        for e in self.extractions:
            if e.key == key and not e.plan:
                return e
        return None


def format_value(value: float | None, kind: str) -> str:
    if value is None:
        return "not found"
    if kind == "pct":
        return (
            f"{value * 100:.2f}%" if kind == "pct" and abs(value) < 0.2 else f"{value * 100:.1f}%"
        )
    if kind in ("count", "year"):
        return f"{value:,.0f}" if kind == "count" else f"{value:.0f}"
    if kind == "sf":
        return f"{value:,.0f} SF"
    return f"${value:,.0f}"


# --------------------------------------------------------------------------------------------
# Structured parsers
# --------------------------------------------------------------------------------------------
def _num(cell: Cell) -> float | None:
    if isinstance(cell, bool):
        return None
    if isinstance(cell, (int, float)):
        return float(cell)
    if isinstance(cell, str):
        text = cell.strip().replace(",", "").replace("$", "")
        negative = text.startswith("(") and text.endswith(")")
        try:
            number = float(text.strip("()"))
        except ValueError:
            return None
        return -number if negative else number
    return None


def _text(cell: Cell) -> str:
    return cell.strip() if isinstance(cell, str) else ""


def _find_header(rows: list[list[Cell]], needles: list[str]) -> int | None:
    for i, row in enumerate(rows):
        labels = [_text(c).lower() for c in row]
        if row and all(any(n in label for label in labels) for n in needles):
            return i
    return None


def _column(header: list[Cell], *names: str) -> int | None:
    labels = [_text(c).lower() for c in header]
    for name in names:
        for i, label in enumerate(labels):
            if name in label:
                return i
    return None


OCCUPIED_STATUSES = {"occupied", "occ", "current", "leased", "notice"}
NON_REVENUE_STATUSES = {"model", "office", "employee", "down", "admin", "non-revenue", "nonrevenue"}


def parse_rent_roll(doc: Document) -> tuple[list[Extraction], list[PlanFacts], int, list[str]]:
    rows = doc.rows
    notes: list[str] = []
    header_idx = _find_header(rows, ["unit", "status"])
    if header_idx is None:
        return [], [], 0, ["Rent roll: no header row with Unit and Status columns."]
    header = rows[header_idx]
    c_plan = _column(header, "floor plan", "plan", "type")
    c_sf = _column(header, "sf", "sq")
    c_status = _column(header, "status")
    c_market = _column(header, "market")
    c_rent = _column(header, "lease rent", "current rent", "rent")
    c_type = _column(header, "bed", "br")
    if c_status is None or c_rent is None:
        return [], [], 0, ["Rent roll: could not find the Status and Lease Rent columns."]
    plans: dict[str, PlanFacts] = {}
    first_row = last_row = header_idx + 2  # 1-based row numbers for citations
    total = occupied = non_revenue = 0
    rent_sum = 0.0
    for i in range(header_idx + 1, len(rows)):
        row = rows[i]
        if not row:
            if total:
                break
            continue
        status = _text(row[c_status]).lower() if c_status < len(row) else ""
        unit = _text(row[0]) or (str(int(row[0])) if isinstance(row[0], (int, float)) else "")
        if not unit or not status:
            if total:
                break
            continue
        last_row = i + 1
        total += 1
        code = _text(row[c_plan]) if c_plan is not None and c_plan < len(row) else "All"
        plan = plans.setdefault(code, PlanFacts(code=code))
        plan.units += 1
        if c_type is not None and c_type < len(row) and not plan.unit_type:
            plan.unit_type = _text(row[c_type])
        sf = _num(row[c_sf]) if c_sf is not None and c_sf < len(row) else None
        if sf:
            plan.sf += sf
        market = _num(row[c_market]) if c_market is not None and c_market < len(row) else None
        if market:
            plan.market_rent += market
        rent = _num(row[c_rent]) if c_rent < len(row) else None
        if status in OCCUPIED_STATUSES and rent:
            occupied += 1
            rent_sum += rent
            plan.occupied += 1
            plan.in_place_rent += rent
        elif status in NON_REVENUE_STATUSES:
            non_revenue += 1
    if total == 0:
        return [], [], 0, ["Rent roll: no unit rows under the header."]
    for plan in plans.values():
        plan.sf = plan.sf / plan.units if plan.units else 0.0
        plan.market_rent = plan.market_rent / plan.units if plan.units else 0.0
        plan.in_place_rent = plan.in_place_rent / plan.occupied if plan.occupied else 0.0
    source = f"rows {first_row} to {last_row}"
    avg_rent = rent_sum / occupied if occupied else None
    extractions = [
        Extraction(
            key="in_place_rent",
            label="In-place rent",
            value=avg_rent,
            unit="$ / unit / mo",
            document="Rent roll",
            page=source,
            quote=f"{occupied} occupied units, lease rent total {rent_sum:,.0f} per month",
            confidence="High",
            note="Average lease rent of occupied units.",
        ),
        Extraction(
            key="occupancy",
            label="Occupancy",
            value=occupied / total,
            unit="%",
            document="Rent roll",
            page=source,
            quote=f"{occupied} occupied of {total} units",
            confidence="High",
            note=f"{non_revenue} non-revenue units (model, office) counted as vacant.",
        ),
    ]
    for plan in plans.values():
        for field_name, label, kind in (
            ("units", "Units", "count"),
            ("sf", "Average SF", "sf"),
            ("occupied", "Occupied", "count"),
            ("in_place_rent", "In-place rent", "rent"),
            ("market_rent", "Market rent", "rent"),
        ):
            extractions.append(
                Extraction(
                    key=f"plan.{field_name}",
                    label=label,
                    value=float(getattr(plan, field_name)),
                    unit={"count": "units", "sf": "SF", "rent": "$ / unit / mo"}[kind],
                    document="Rent roll",
                    page=source,
                    confidence="High",
                    plan=plan.code,
                )
            )
    if any(p.market_rent == 0 for p in plans.values()):
        notes.append("Rent roll: no market rent column; market rents come from the OM.")
    return extractions, list(plans.values()), non_revenue, notes


MONTH_HEADER = re.compile(
    r"^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[- ']?\d{2,4}$", re.I
)


def parse_t12(doc: Document, units: int | None) -> tuple[list[Extraction], list[str]]:
    rows = doc.rows
    notes: list[str] = []
    header_idx = None
    month_cols: list[int] = []
    for i, row in enumerate(rows):
        cols = [
            j for j, c in enumerate(row) if isinstance(c, str) and MONTH_HEADER.match(c.strip())
        ]
        if len(cols) >= 12:
            header_idx, month_cols = i, cols[:12]
            break
    if header_idx is None:
        return [], ["T-12: no header row with twelve month columns."]

    def line_total(*names: str) -> tuple[float, int] | None:
        for i in range(header_idx + 1, len(rows)):
            if not rows[i]:
                continue
            label = _text(rows[i][0]).lower()
            if any(label == n or label.startswith(n) for n in names):
                values = [_num(rows[i][c]) for c in month_cols if c < len(rows[i])]
                if any(v is not None for v in values):
                    return sum(v or 0.0 for v in values), i + 1
        return None

    if units is None:
        m = re.search(r"(\d{2,4}) units", doc.text(), re.I)
        units = int(m.group(1)) if m else None
        if units:
            notes.append(f"T-12: unit count {units} taken from the statement header.")
    if not units:
        return [], ["T-12: unit count unknown; upload the rent roll or the OM first."]

    extractions: list[Extraction] = []
    other = line_total("other income", "total other income")
    if other:
        extractions.append(
            Extraction(
                key="other_income",
                label="Other income",
                value=abs(other[0]) / units / 12,
                unit="$ / unit / mo",
                document="T-12",
                page=f"row {other[1]}",
                quote=f"Other income {abs(other[0]):,.0f} over twelve months",
                confidence="High",
                note="Twelve-month total divided by units and twelve.",
            )
        )
    controllable = 0.0
    found_lines: list[str] = []
    rows_cited: list[int] = []
    for name in CONTROLLABLE_LINES:
        hit = line_total(name.lower())
        if hit:
            controllable += abs(hit[0])
            found_lines.append(name)
            rows_cited.append(hit[1])
    if found_lines:
        extractions.append(
            Extraction(
                key="controllable_expenses",
                label="Controllable expenses",
                value=controllable / units,
                unit="$ / unit / yr",
                document="T-12",
                page=f"rows {min(rows_cited)} to {max(rows_cited)}",
                quote=f"{len(found_lines)} lines totalling {controllable:,.0f}",
                confidence="Medium",
                note="Seller's actuals; the buyer's underwriting adjusts these lines.",
            )
        )
        for name in found_lines:
            hit = line_total(name.lower())
            if hit:
                extractions.append(
                    Extraction(
                        key=f"line.{name}",
                        label=name,
                        value=abs(hit[0]) / units,
                        unit="$ / unit / yr",
                        document="T-12",
                        page=f"row {hit[1]}",
                        confidence="High",
                        plan="line",
                    )
                )
    insurance = line_total("insurance", "property insurance")
    if insurance:
        extractions.append(
            Extraction(
                key="insurance",
                label="Insurance",
                value=abs(insurance[0]) / units,
                unit="$ / unit / yr",
                document="T-12",
                page=f"row {insurance[1]}",
                quote=f"Insurance {abs(insurance[0]):,.0f} over twelve months",
                confidence="Medium",
                note="Seller's premium; a buyer's quote replaces it.",
            )
        )
    taxes = line_total("real estate taxes", "property taxes", "taxes")
    if taxes:
        extractions.append(
            Extraction(
                key="taxes_t12",
                label="Real estate taxes, T-12",
                value=abs(taxes[0]),
                unit="$ / yr",
                document="T-12",
                page=f"row {taxes[1]}",
                quote=f"Real estate taxes {abs(taxes[0]):,.0f} over twelve months",
                confidence="Low",
                note="Seller's assessed value; taxes reassess on sale.",
            )
        )
    return extractions, notes


# --------------------------------------------------------------------------------------------
# Offering memorandum readers
# --------------------------------------------------------------------------------------------
class OMReader(Protocol):
    name: str

    def read(self, om: Document) -> tuple[list[Extraction], list[PlanFacts], list[str]]: ...


_MONEY = r"\$([\d,]+(?:\.\d+)?)"
_RULES: list[tuple[str, re.Pattern[str], Confidence, str]] = [
    ("asking_price", re.compile(r"Asking price\s+" + _MONEY), "High", ""),
    ("units", re.compile(r"^Units\s+(\d{2,4})\s*$", re.M), "High", ""),
    ("year_built", re.compile(r"Year built\s+(\d{4})"), "High", ""),
    ("rentable_sf", re.compile(r"Rentable square feet\s+([\d,]+)"), "High", ""),
    (
        "market_rent",
        re.compile(r"Survey average asking rent:\s+" + _MONEY),
        "Medium",
        "Broker's survey of competing properties.",
    ),
    (
        "renovated_units",
        re.compile(r"renovated\s+(\d+)\s+units"),
        "Medium",
        "Seller's claim; confirm in the data room.",
    ),
    (
        "renovation_premium",
        re.compile(r"average premium of\s+" + _MONEY + r"\s+per month"),
        "Medium",
        "Seller's claim on renovated units.",
    ),
    (
        "exit_cap",
        re.compile(r"Average cap rate across the (?:\w+) sales:\s+([\d.]+)%"),
        "Medium",
        "Broker-selected sale comparables.",
    ),
    ("tax_rate", re.compile(r"tax rate of\s+([\d.]+)%"), "High", ""),
]
_PLAN_ROW = re.compile(
    r"^([A-Z]\d)\s+(\d) BR / (\d) BA\s+(\d+)\s+([\d,]+)\s+[\d,]+\s+(\d+)"
    r"\s+\$([\d,]+)\s+\$([\d,]+)\s*$",
    re.M,
)


def _to_number(raw: str) -> float:
    return float(raw.replace(",", ""))


class RuleReader:
    """Regular expressions over the page text. Works on the synthetic OM and on OMs that share
    its labels; anything else needs the model reader."""

    name = "rules"

    def read(self, om: Document) -> tuple[list[Extraction], list[PlanFacts], list[str]]:
        extractions: list[Extraction] = []
        notes: list[str] = []
        for key, pattern, confidence, note in _RULES:
            spec = FIELD_BY_KEY[key]
            found = False
            for page in om.pages:
                m = pattern.search(page.text)
                if m:
                    value = _to_number(m.group(1))
                    if spec.kind == "pct":
                        value /= 100
                    extractions.append(
                        Extraction(
                            key=key,
                            label=spec.label,
                            value=value,
                            unit=spec.unit,
                            document="OM",
                            page=f"p. {page.number}",
                            quote=m.group(0).strip(),
                            confidence=confidence,
                            note=note,
                        )
                    )
                    found = True
                    break
            if not found:
                notes.append(f"OM: {spec.label.lower()} not found.")
        plans: list[PlanFacts] = []
        for page in om.pages:
            for m in _PLAN_ROW.finditer(page.text):
                plans.append(
                    PlanFacts(
                        code=m.group(1),
                        unit_type=f"{m.group(2)} x {m.group(3)}",
                        units=int(m.group(4)),
                        sf=_to_number(m.group(5)),
                        occupied=int(m.group(6)),
                        in_place_rent=_to_number(m.group(7)),
                        market_rent=_to_number(m.group(8)),
                    )
                )
            if plans:
                break
        return extractions, plans, notes


EXTRACTION_TOOL: dict[str, Any] = {
    "name": "record_extractions",
    "description": "Record every catalogue figure found in the offering memorandum, cited.",
    "input_schema": {
        "type": "object",
        "properties": {
            "extractions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string", "enum": [f.key for f in OM_FIELDS]},
                        "value": {
                            "type": ["number", "null"],
                            "description": (
                                "The figure as a plain number. Percentages as a fraction "
                                "(5.5% is 0.055). Null when the document does not state it."
                            ),
                        },
                        "page": {
                            "type": "integer",
                            "description": "Page number the quote comes from.",
                        },
                        "quote": {
                            "type": "string",
                            "description": (
                                "Verbatim text from that page containing the figure, "
                                "under 200 characters."
                            ),
                        },
                        "confidence": {"type": "string", "enum": ["High", "Medium", "Low"]},
                        "note": {
                            "type": "string",
                            "description": (
                                "One sentence on why the confidence is not High, or empty."
                            ),
                        },
                    },
                    "required": ["key", "value", "page", "quote", "confidence"],
                },
            },
            "floor_plans": {
                "type": "array",
                "description": "One entry per floor plan in the unit mix table.",
                "items": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string"},
                        "unit_type": {
                            "type": "string",
                            "description": "Bedrooms x bathrooms, such as '2 x 2'.",
                        },
                        "units": {"type": "integer"},
                        "sf": {"type": "number"},
                        "occupied": {"type": "integer"},
                        "in_place_rent": {"type": "number"},
                        "market_rent": {"type": "number"},
                    },
                    "required": ["code", "units", "sf", "in_place_rent", "market_rent"],
                },
            },
        },
        "required": ["extractions"],
    },
}

SYSTEM_PROMPT = """You read multifamily offering memoranda for an acquisitions analyst.
Find each figure in the catalogue and record it with the page and a verbatim quote from that page.
Rules: report only what the document states; never compute, infer or fill from general knowledge.
If a figure is absent, record it with value null and an empty quote. Confidence is High when the
document states the figure as a fact about the property, Medium when it is a broker estimate,
survey, comparable-based figure or seller claim, Low when it is ambiguous or conflicts with
another page. Percentages are fractions. Dollar figures are plain numbers without symbols."""


class ClaudeReader:
    """Reads the OM with the Claude API through a tool call, so the output is typed."""

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

    def read(self, om: Document) -> tuple[list[Extraction], list[PlanFacts], list[str]]:
        catalogue = "\n".join(
            f"- {f.key}: {f.label}. {f.description} Unit: {f.unit or 'none'}." for f in OM_FIELDS
        )
        pages = "\n\n".join(f"[page {p.number}]\n{p.text}" for p in om.pages)
        prompt = f"Catalogue:\n{catalogue}\n\nOffering memorandum:\n{pages}"
        response = self._messages().create(
            model=self.model,
            max_tokens=4000,
            system=SYSTEM_PROMPT,
            tools=[EXTRACTION_TOOL],
            tool_choice={"type": "tool", "name": "record_extractions"},
            messages=[{"role": "user", "content": prompt}],
        )
        payload: dict[str, Any] | None = None
        log.warning(
            "OM reader response: stop_reason=%s blocks=%s",
            getattr(response, "stop_reason", None),
            [getattr(b, "type", "?") for b in response.content],
        )
        for block in response.content:
            if getattr(block, "type", "") == "tool_use":
                raw_input = block.input
                if isinstance(raw_input, str):
                    raw_input = json.loads(raw_input)
                payload = dict(raw_input)
                break
        if payload is None:
            return [], [], ["OM: the model returned no extraction record."]
        return parse_tool_payload(payload)


def _records(raw: Any, notes: list[str], what: str) -> list[Mapping[str, Any]]:
    """Tool payload lists as records. The model sometimes returns a list as a JSON string, or
    an item as a string; those are decoded when possible and otherwise skipped with a note."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            notes.append(f"OM: the {what} list came back as text and could not be read.")
            return []
    if raw is None:
        return []
    if isinstance(raw, Mapping):
        if any(k in raw for k in ("key", "name", "field", "value", "code", "plan")):
            raw = [raw]  # a single record
        else:
            # An object keyed by figure name: {"asking_price": {...}} or {"asking_price": 50500000}.
            raw = [
                {**v, "key": k} if isinstance(v, Mapping) else {"key": k, "value": v}
                for k, v in raw.items()
            ]
    if not isinstance(raw, list):
        notes.append(f"OM: the {what} list had an unexpected shape ({type(raw).__name__}).")
        return []
    records: list[Mapping[str, Any]] = []
    for item in raw:
        if isinstance(item, str):
            try:
                item = json.loads(item)
            except ValueError:
                notes.append(f"OM: one {what} came back as text and was skipped.")
                continue
        if isinstance(item, Mapping):
            records.append(item)
        else:
            notes.append(f"OM: one {what} had an unexpected shape and was skipped.")
    return records


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


_LABEL_KEYS: dict[str, str] = {}


def match_key(raw_key: Any) -> str | None:
    """The catalogue key for what the model called a figure: the key itself, its label, or a
    prefixed or spaced variant of either."""
    if not _LABEL_KEYS:
        for f in OM_FIELDS:
            _LABEL_KEYS[_slug(f.label)] = f.key
    slug = _slug(str(raw_key))
    if slug in FIELD_BY_KEY:
        return slug
    if slug in _LABEL_KEYS:
        return _LABEL_KEYS[slug]
    for key in FIELD_BY_KEY:
        if slug.endswith("_" + key):
            return key
    return None


def coerce_number(raw: Any, kind: str) -> float | None:
    """A figure as a float. Strings such as "$50,500,000", "5.50%" or "261,360 SF" are read;
    percentages above one are taken as percent and divided by one hundred."""
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        value = float(raw)
    elif isinstance(raw, str):
        text = raw.strip()
        if not text or text.lower() in ("null", "none", "n/a", "not found", "not stated"):
            return None
        percent = "%" in text
        m = re.search(r"-?\d[\d,]*(?:\.\d+)?", text.replace("$", ""))
        if not m:
            return None
        value = float(m.group(0).replace(",", ""))
        if percent:
            value /= 100
    else:
        return None
    if kind == "pct" and value > 1:
        value /= 100
    return value


def coerce_page(raw: Any) -> int:
    m = re.search(r"\d+", str(raw or ""))
    return int(m.group(0)) if m else 0


def parse_tool_payload(
    payload: Mapping[str, Any],
) -> tuple[list[Extraction], list[PlanFacts], list[str]]:
    extractions: list[Extraction] = []
    notes: list[str] = []
    seen: set[str] = set()
    records = _records(payload.get("extractions"), notes, "extraction")
    unknown: list[str] = []
    for item in records:
        key = match_key(item.get("key", item.get("name", item.get("field", ""))))
        spec = FIELD_BY_KEY.get(key or "")
        if key is None or spec is None or spec.document != "om":
            unknown.append(str(item.get("key", item.get("name", "?")))[:40])
            continue
        if key in seen:
            continue
        seen.add(key)
        value = coerce_number(item.get("value"), spec.kind)
        if value is None:
            notes.append(f"OM: {spec.label.lower()} not found.")
            continue
        confidence = str(item.get("confidence", "Low")).title()
        extractions.append(
            Extraction(
                key=key,
                label=spec.label,
                value=value,
                unit=spec.unit,
                document="OM",
                page=f"p. {coerce_page(item.get('page'))}",
                quote=str(item.get("quote", "") or "")[:300],
                confidence=confidence if confidence in CONFIDENCE_RANK else "Low",  # type: ignore[arg-type]
                note=str(item.get("note", "") or ""),
            )
        )
    if unknown:
        notes.append(
            f"OM: {len(unknown)} record(s) did not match the catalogue: {', '.join(unknown[:5])}."
        )
    if not records:
        keys = ", ".join(map(str, payload)) or "none"
        notes.append(f"OM: the model returned no figures (payload keys: {keys}).")
    log.warning(
        "OM reader payload: keys=%s records=%d matched=%d unknown=%d",
        list(payload),
        len(records),
        len(extractions),
        len(unknown),
    )
    plans: list[PlanFacts] = []
    for fp in _records(payload.get("floor_plans"), notes, "floor plan"):
        try:
            plans.append(
                PlanFacts(
                    code=str(fp.get("code", fp.get("plan", ""))),
                    unit_type=str(fp.get("unit_type", fp.get("type", ""))),
                    units=int(coerce_number(fp.get("units"), "count") or 0),
                    sf=coerce_number(fp.get("sf", fp.get("avg_sf")), "sf") or 0.0,
                    occupied=int(coerce_number(fp.get("occupied"), "count") or 0),
                    in_place_rent=coerce_number(fp.get("in_place_rent"), "rent") or 0.0,
                    market_rent=coerce_number(fp.get("market_rent"), "rent") or 0.0,
                )
            )
        except (TypeError, ValueError):
            notes.append("OM: a floor plan row could not be read.")
    return extractions, plans, notes


# --------------------------------------------------------------------------------------------
# Verification
# --------------------------------------------------------------------------------------------
def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _value_forms(value: float, kind: str) -> list[str]:
    forms = {f"{value:,.0f}", f"{value:.0f}", f"{value:,.2f}", f"{value:.2f}", f"{value:,.1f}"}
    if kind == "pct":
        pct = value * 100
        forms |= {f"{pct:.2f}", f"{pct:.1f}", f"{pct:.4f}", f"{pct:.0f}", f"{pct:g}"}
    return [f for f in forms if f]


def verify(extractions: list[Extraction], documents: Mapping[str, Document]) -> list[Extraction]:
    """Downgrade an OM extraction whose quote is not on the cited page or lacks the figure.

    Rent roll and T-12 figures are computed from rows, so their quotes are descriptive and skipped.
    """
    checked: list[Extraction] = []
    for e in extractions:
        m = re.match(r"p\.\s*(\d+)", e.page)
        derived = not e.quote and m is None  # computed from a table, not quoted
        if e.document != "OM" or e.value is None or e.plan or derived:
            checked.append(e)
            continue
        om = documents.get("om")
        page = om.page(int(m.group(1))) if om and m else None
        problems: list[str] = []
        if page is None or not e.quote or _norm(e.quote) not in _norm(page.text):
            problems.append("quote not found on the cited page")
        kind = FIELD_BY_KEY[e.key].kind if e.key in FIELD_BY_KEY else "money"
        if e.quote and not any(form in e.quote for form in _value_forms(e.value, kind)):
            problems.append("figure not present in the quote")
        if problems:
            e = e.model_copy(
                update={
                    "confidence": "Low",
                    "note": (e.note + " " if e.note else "")
                    + "Unverified: "
                    + "; ".join(problems)
                    + ".",
                }
            )
        checked.append(e)
    return checked


# --------------------------------------------------------------------------------------------
# Screen
# --------------------------------------------------------------------------------------------
def screen(documents: Mapping[str, Document], reader: OMReader | None = None) -> ScreenResult:
    """Read whatever documents were supplied and return every figure found, verified."""
    if reader is None:
        reader = ClaudeReader() if ClaudeReader.available() else RuleReader()
    extractions: list[Extraction] = []
    plans: list[PlanFacts] = []
    notes: list[str] = []
    non_revenue = 0
    units: int | None = None
    om_plans: list[PlanFacts] = []
    if om := documents.get("om"):
        found, om_plans, om_notes = reader.read(om)
        extractions.extend(found)
        notes.extend(om_notes)
        units_e = next((e for e in found if e.key == "units" and e.value), None)
        units = int(units_e.value) if units_e and units_e.value else None
    if rr := documents.get("rent_roll"):
        found, plans, non_revenue, rr_notes = parse_rent_roll(rr)
        extractions.extend(found)
        notes.extend(rr_notes)
        if plans:
            rr_units = sum(p.units for p in plans)
            if units and rr_units != units:
                notes.append(
                    f"Unit count differs: OM {units}, rent roll {rr_units}. The rent roll is used."
                )
            units = rr_units
            # Market rents and unit types come from the OM when the rent roll lacks them.
            by_code = {p.code: p for p in om_plans}
            for plan in plans:
                om_plan = by_code.get(plan.code)
                if om_plan:
                    if not plan.market_rent:
                        plan.market_rent = om_plan.market_rent
                    if om_plan.unit_type:
                        plan.unit_type = om_plan.unit_type
    elif om_plans:
        plans = om_plans
        occ = sum(p.occupied for p in plans)
        tot = sum(p.units for p in plans)
        if tot:
            in_place = sum(p.occupied * p.in_place_rent for p in plans) / occ if occ else None
            extractions.append(
                Extraction(
                    key="in_place_rent",
                    label="In-place rent",
                    value=in_place,
                    unit="$ / unit / mo",
                    document="OM",
                    page="unit mix",
                    quote="",
                    confidence="Medium",
                    note="From the OM unit mix; upload the rent roll to confirm.",
                )
            )
            extractions.append(
                Extraction(
                    key="occupancy",
                    label="Occupancy",
                    value=occ / tot,
                    unit="%",
                    document="OM",
                    page="unit mix",
                    quote="",
                    confidence="Medium",
                    note="From the OM unit mix; upload the rent roll to confirm.",
                )
            )
    if t12 := documents.get("t12"):
        found, t12_notes = parse_t12(t12, units)
        extractions.extend(found)
        notes.extend(t12_notes)
    extractions = verify(extractions, documents)
    order = {f.key: i for i, f in enumerate(FIELDS)}
    extractions.sort(key=lambda e: (bool(e.plan), order.get(e.key, 99)))
    return ScreenResult(
        extractions=extractions,
        plans=plans,
        non_revenue_units=non_revenue,
        reader=reader.name,
        notes=notes,
    )


# --------------------------------------------------------------------------------------------
# Questions and answers
# --------------------------------------------------------------------------------------------
QuestionKind = Literal["money", "pct", "count", "months", "years", "rent", "per_unit_year"]


@dataclass(frozen=True)
class QuestionSpec:
    key: str  # dotted input path, or a virtual path handled in apply_answers
    group: str
    prompt: str
    kind: QuestionKind
    informed_by: str | None = None  # extraction key that can answer it
    always: bool = True  # asked even when the extraction is High


QUESTIONS: list[QuestionSpec] = [
    QuestionSpec(
        "acquisition.purchase_price",
        "Pricing",
        "Purchase price to underwrite",
        "money",
        "asking_price",
    ),
    QuestionSpec("acquisition.hold_months", "Pricing", "Hold period", "months"),
    QuestionSpec("renovation.units", "Renovation", "Units to renovate", "count", "renovated_units"),
    QuestionSpec(
        "renovation.cost_per_unit",
        "Renovation",
        "Renovation cost per unit (contractor bid)",
        "money",
    ),
    QuestionSpec(
        "renovation.premium_per_month",
        "Renovation",
        "Renovation premium per month",
        "rent",
        "renovation_premium",
        always=False,
    ),
    QuestionSpec("revenue.market_rent_growth", "Operations", "Market rent growth per year", "pct"),
    QuestionSpec("revenue.vacancy", "Operations", "Stabilized vacancy", "pct"),
    QuestionSpec(
        "operating.controllable_per_unit",
        "Operations",
        "Controllable expenses per unit per year",
        "per_unit_year",
        "controllable_expenses",
        always=False,
    ),
    QuestionSpec(
        "operating.per_unit.Insurance",
        "Operations",
        "Insurance per unit per year (broker quote)",
        "per_unit_year",
        "insurance",
        always=False,
    ),
    QuestionSpec(
        "operating.tax_rate", "Operations", "Combined tax rate", "pct", "tax_rate", always=False
    ),
    QuestionSpec(
        "operating.tax_assessed_share",
        "Operations",
        "Reassessment: share of price the district will assess",
        "pct",
        "taxes_t12",
    ),
    QuestionSpec(
        "operating.reserves_per_unit",
        "Operations",
        "Replacement reserves per unit per year (lender requirement)",
        "per_unit_year",
    ),
    QuestionSpec("loan.ltv_max", "Debt", "Maximum loan to value", "pct"),
    QuestionSpec("loan.dscr_min", "Debt", "Minimum debt service coverage", "count"),
    QuestionSpec("loan.debt_yield_min", "Debt", "Minimum debt yield", "pct"),
    QuestionSpec("loan.rate", "Debt", "Fixed rate", "pct"),
    QuestionSpec("loan.io_months", "Debt", "Interest-only period", "months"),
    QuestionSpec("loan.amortization_years", "Debt", "Amortization", "years"),
    QuestionSpec("loan.term_months", "Debt", "Loan term", "months"),
    QuestionSpec("exit.cap_rate", "Exit", "Exit cap rate", "pct", "exit_cap", always=False),
]


class Question(BaseModel):
    key: str
    group: str
    prompt: str
    kind: QuestionKind
    current: float
    extracted: Extraction | None = None
    prefill: float
    reason: str


def _get_path(inputs: CopilotInputs, path: str) -> float:
    if path == "operating.controllable_per_unit":
        return float(
            sum(v for k, v in inputs.operating.per_unit.items() if k in CONTROLLABLE_LINES)
        )
    node: Any = inputs
    for part in path.split("."):
        node = node[part] if isinstance(node, dict) else getattr(node, part)
    return float(node)


def questions(inputs: CopilotInputs, result: ScreenResult | None) -> list[Question]:
    """Everything the documents did not settle, in catalogue order. Answers default to the
    extracted figure when there is one, otherwise to the current model input."""
    out: list[Question] = []
    for spec in QUESTIONS:
        extracted = result.get(spec.informed_by) if result and spec.informed_by else None
        if extracted is not None and extracted.value is None:
            extracted = None
        if not spec.always and extracted is not None and extracted.confidence == "High":
            continue
        current = _get_path(inputs, spec.key)
        if extracted is None:
            reason = (
                "Not in the documents."
                if spec.informed_by
                else "Buyer's assumption; never in the documents."
            )
            prefill = current
        elif spec.key == "acquisition.purchase_price":
            reason = f"Asking price {extracted.display()} per the OM; the bid is yours."
            prefill = current
        elif spec.key == "renovation.units":
            reason = f"Seller renovated {extracted.display()}; the program from here is yours."
            prefill = current
        elif spec.key == "operating.tax_assessed_share":
            reason = (
                f"Seller paid {extracted.display()} in taxes on the old assessment; "
                "reassessment on sale is the risk."
            )
            prefill = current
        else:
            reason = f"{extracted.confidence} confidence: {extracted.note or 'confirm the figure.'}"
            prefill = extracted.value if extracted.value is not None else current
        out.append(
            Question(
                key=spec.key,
                group=spec.group,
                prompt=spec.prompt,
                kind=spec.kind,
                current=current,
                extracted=extracted,
                prefill=prefill,
                reason=reason,
            )
        )
    return out


def parse_answer(kind: QuestionKind, raw: str) -> float:
    text = (
        raw.strip()
        .replace(",", "")
        .replace("$", "")
        .replace("%", "")
        .replace("×", "")
        .replace("x", "")
    )
    if text == "":
        raise ValueError("blank")
    value = float(text)
    return value / 100 if kind == "pct" else value


def apply_screen(
    base: CopilotInputs, result: ScreenResult | None, answers: Mapping[str, float]
) -> CopilotInputs:
    """Document facts first, then the analyst's answers on top, onto a copy of the base inputs."""
    data = base.model_dump(mode="python")
    if result is not None:
        if result.plans and all(p.units for p in result.plans):
            data["property"]["floor_plans"] = [
                FloorPlan(
                    code=p.code,
                    unit_type=p.unit_type or p.code,
                    units=p.units,
                    sf=p.sf,
                    occupied=p.occupied,
                    in_place_rent=p.in_place_rent,
                    market_rent=p.market_rent or p.in_place_rent,
                ).model_dump()
                for p in result.plans
            ]
            data["property"]["non_revenue_units"] = result.non_revenue_units
        for key, path in (
            ("year_built", ("property", "year_built")),
            ("asking_price", ("acquisition", "asking_price")),
        ):
            e = result.get(key)
            if e and e.value is not None:
                data[path[0]][path[1]] = int(e.value) if key == "year_built" else e.value
        if (e := result.get("tax_rate")) and e.value is not None and e.confidence == "High":
            data["operating"]["tax_rate"] = e.value
        if (e := result.get("other_income")) and e.value is not None:
            data["revenue"]["other_income_per_unit_month"] = round(e.value, 2)
        lines = {
            x.label: x.value for x in result.extractions if x.plan == "line" and x.value is not None
        }
        if lines:
            for name, value in lines.items():
                data["operating"]["per_unit"][name] = round(value)
        if (e := result.get("insurance")) and e.value is not None:
            data["operating"]["per_unit"]["Insurance"] = round(e.value)
    for answer_path, value in answers.items():
        if answer_path == "operating.controllable_per_unit":
            per_unit = data["operating"]["per_unit"]
            current = sum(v for k, v in per_unit.items() if k in CONTROLLABLE_LINES)
            if current > 0:
                scale = value / current
                for k in CONTROLLABLE_LINES:
                    if k in per_unit:
                        per_unit[k] = round(per_unit[k] * scale)
            continue
        parts = answer_path.split(".")
        node: Any = data
        for part in parts[:-1]:
            node = node[part]
        leaf = parts[-1]
        integer_leaf = leaf in {
            "units",
            "hold_months",
            "io_months",
            "amortization_years",
            "term_months",
            "start_month",
            "duration_months",
        }
        node[leaf] = int(round(value)) if integer_leaf else value
    return CopilotInputs.model_validate(data)


def answers_from_form(
    form: Mapping[str, str], asked: list[Question]
) -> tuple[dict[str, float], list[str]]:
    answers: dict[str, float] = {}
    errors: list[str] = []
    for q in asked:
        raw = form.get(q.key)
        if raw is None:
            continue
        try:
            answers[q.key] = parse_answer(q.kind, raw)
        except ValueError:
            errors.append(f"{q.prompt}: {raw!r} is not a number")
    return answers, errors


def result_to_json(result: ScreenResult) -> str:
    return json.dumps(result.model_dump(mode="json"))


ReaderFactory = Callable[[], OMReader]
