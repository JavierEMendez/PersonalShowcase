"""Turn posted input forms back into typed DealInputs.

Field names are dotted paths into the inputs model: `tract.gross_acreage`,
`costs.lot_sizes.3.pace`, `lookups.plants.WWTP.acres`. Numeric list segments become list
indexes. Percentage fields are entered as percentages (4.5) and stored as fractions (0.045).
A field submitted blank resets to the model default; a field a tab does not submit keeps its
value, so the Costs and Revenue tabs can each edit their own columns of the lot mix.
Checkbox fields arrive only when ticked, so each tab names the checkboxes it renders.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from core.underwriting.inputs import DealInputs

PERCENT_PATTERNS = [
    r"^tract\.(closing_costs_pct|land_escalator|parks_pct)$",
    r"^costs\.(default_other_pct|sectional_other_pct|landscaping_other_pct|contingency|site_work_pct|fenced_pct|prof_svc_pct|dmf_pct|mud_pct)$",
    r"^costs\.takedowns\.\d+\.pct$",
    r"^costs\.(plant|amenity|det|other|road)_costs\.\d+\.(other_pct|ph2_other_pct)$",
    r"^costs\.lot_sizes\.\d+\.(av_pct|escalation|lot_av_pct|lot_tax_rate)$",
    r"^revenue\.(bem_pct|brokerage_fees|lot_closing_costs)$",
    r"^revenue\.(res_pods|comm_pods)\.\d+\.closing_costs_pct$",
    r"^revenue\.(mud_bond|wcid_bond)\.(debt_ratio|pct_to_dev|receivables_fee)$",
]
_PERCENT = [re.compile(p) for p in PERCENT_PATTERNS]
CHECKBOX_PATTERNS = [
    re.compile(r"^costs\.lot_sizes\.\d+\.on$"),
    re.compile(r"^revenue\.(mud_bond|wcid_bond)\.toggle$"),
]
TEXT_PATTERNS = [
    re.compile(r"^tract\.project_name$"),
    re.compile(r"^tract\.closing_date$"),
    re.compile(r"^tract\.plants\.\d+\.type$"),
    re.compile(r"^tract\.amenities\.\d+\.type$"),
    re.compile(r"^tract\.other_netouts\.\d+\.desc$"),
    re.compile(r"^tract\.roads\.\d+\.type$"),
    re.compile(r"^revenue\.timing_method$"),
]
_NUMBER = re.compile(r"^-?\d+(\.\d+)?$")


class Blank:
    """Marker for a field submitted empty: the model default applies."""


BLANK = Blank()


def is_percent(path: str) -> bool:
    return any(p.match(path) for p in _PERCENT)


def is_checkbox(path: str) -> bool:
    return any(p.match(path) for p in CHECKBOX_PATTERNS)


def is_text(path: str) -> bool:
    return any(p.match(path) for p in TEXT_PATTERNS)


def coerce(path: str, raw: str) -> Any:
    value = raw.strip()
    if value == "":
        return BLANK
    if is_checkbox(path):
        return value in ("on", "true", "1", "True")
    if is_text(path):
        return value
    text = value.replace(",", "").replace("$", "").replace("%", "")
    if not _NUMBER.match(text):
        raise ValueError(f"{path}: {raw!r} is not a number")
    number = float(text)
    return number / 100 if is_percent(path) else number


def _set(target: dict[str, Any], parts: list[str], value: Any) -> None:
    node = target
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value


def parse_form(form: Mapping[str, str], checkbox_paths: list[str] | None = None) -> dict[str, Any]:
    """Nested dict of the submitted values; digit keys stay as dict keys until merge."""
    nested: dict[str, Any] = {}
    for path, raw in form.items():
        _set(nested, path.split("."), coerce(path, raw))
    for path in checkbox_paths or []:
        if path not in form:
            _set(nested, path.split("."), False)
    return nested


def _is_index_dict(node: Any) -> bool:
    return isinstance(node, dict) and bool(node) and all(k.isdigit() for k in node)


def merge(base: Any, update: Any) -> Any:
    """Merge submitted values into the existing inputs dump."""
    if isinstance(update, Blank):
        return BLANK
    if _is_index_dict(update):
        rows = list(base) if isinstance(base, list) else []
        size = max(len(rows), max(int(k) for k in update) + 1)
        rows.extend({} for _ in range(size - len(rows)))
        for key, value in update.items():
            i = int(key)
            rows[i] = merge(rows[i], value)
        return rows
    if isinstance(update, dict):
        merged = dict(base) if isinstance(base, dict) else {}
        for key, value in update.items():
            result = merge(merged.get(key), value)
            if isinstance(result, Blank):
                merged.pop(key, None)
            else:
                merged[key] = result
        return merged
    return update


def _strip_blanks(node: Any) -> Any:
    if isinstance(node, dict):
        return {k: _strip_blanks(v) for k, v in node.items() if not isinstance(v, Blank)}
    if isinstance(node, list):
        return [_strip_blanks(v) for v in node if not isinstance(v, Blank)]
    return node


def apply_form(
    inputs: DealInputs, form: Mapping[str, str], checkbox_paths: list[str] | None = None
) -> DealInputs:
    """Merge a submitted form into existing inputs and validate the result."""
    update = parse_form(form, checkbox_paths)
    merged = _strip_blanks(merge(inputs.model_dump(mode="json"), update))
    return DealInputs.model_validate(merged)


def validation_messages(error: ValidationError) -> list[str]:
    return [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in error.errors()]
