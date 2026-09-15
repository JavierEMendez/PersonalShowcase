"""Two-axis sensitivity grid: rerun the engine over a range of two inputs.

Axes scale an input by a factor around the base case. Rows and columns take one to three
steps each side at a chosen step size, so the grid is 3 x 3 up to 7 x 7. The metric is
unlevered IRR or gross margin as a share of revenue.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from core.underwriting.engine import run
from core.underwriting.inputs import DealInputs

Axis = Literal["lot_price", "pace", "contingency", "home_price", "yield", "dev_cost"]
Metric = Literal["irr", "gross_margin"]

AXIS_LABELS: dict[str, str] = {
    "lot_price": "Lot price / FF",
    "pace": "Pace (lots / mo)",
    "contingency": "Contingency",
    "home_price": "Home price",
    "yield": "Yield (lots / ac)",
    "dev_cost": "Dev cost / lot",
}
METRIC_LABELS: dict[str, str] = {"irr": "Unlevered IRR", "gross_margin": "Gross margin"}
HEAT_LEVELS = 9


class GridCell(BaseModel):
    value: float | None
    heat: int  # 1..9, 0 when the value is missing
    base: bool


class GridRow(BaseModel):
    label: str
    cells: list[GridCell]


class SensitivityGrid(BaseModel):
    row_axis: Axis
    col_axis: Axis
    metric: Metric
    row_step: float
    col_step: float
    col_labels: list[str]
    rows: list[GridRow]
    note: str


def scale_axis(inputs: DealInputs, axis: Axis, factor: float) -> DealInputs:
    """A deep copy of the inputs with one driver scaled by `factor`."""
    scaled = inputs.model_copy(deep=True)
    if axis == "lot_price":
        scaled.revenue.price_per_ff = [p * factor for p in inputs.revenue.price_per_ff]
    elif axis == "contingency":
        scaled.costs.contingency = inputs.costs.contingency * factor
    else:
        for ls in scaled.costs.lot_sizes:
            if not ls.on:
                continue
            if axis == "pace":
                ls.pace *= factor
            elif axis == "home_price":
                ls.home_price *= factor
            elif axis == "yield":
                ls.yield_per_ac *= factor
            elif axis == "dev_cost":
                ls.wsd_per_ff *= factor
                ls.paving_per_ff *= factor
    return scaled


def axis_label(inputs: DealInputs, axis: Axis, factor: float) -> str:
    """Header text for one step: the scaled value where every lot shares it, else the change."""
    active = [ls for ls in inputs.costs.lot_sizes if ls.on]
    if axis == "lot_price":
        return f"${inputs.revenue.price_per_ff[0] * factor:,.0f}"
    if axis == "contingency":
        return f"{inputs.costs.contingency * factor * 100:.1f}%"
    if axis == "pace" and active and len({ls.pace for ls in active}) == 1:
        return f"{active[0].pace * factor:.1f}"
    if axis == "yield" and active and len({ls.yield_per_ac for ls in active}) == 1:
        return f"{active[0].yield_per_ac * factor:.2f}"
    change = (factor - 1) * 100
    return f"{change:+.0f}%" if abs(change) > 1e-9 else "Base"


def metric_value(inputs: DealInputs, metric: Metric) -> float | None:
    summary = run(inputs).summary
    if metric == "irr":
        return summary.unlevered_irr
    return summary.gross_margin_of_revenue


def build_grid(
    inputs: DealInputs,
    row_axis: Axis = "pace",
    col_axis: Axis = "lot_price",
    metric: Metric = "irr",
    row_steps: int = 2,
    col_steps: int = 2,
    row_step: float = 0.10,
    col_step: float = 0.05,
) -> SensitivityGrid:
    row_steps = max(1, min(3, row_steps))
    col_steps = max(1, min(3, col_steps))
    row_factors = [1 + row_step * k for k in range(row_steps, -row_steps - 1, -1)]
    col_factors = [1 + col_step * k for k in range(-col_steps, col_steps + 1)]

    values: list[list[float | None]] = []
    for rf in row_factors:
        row_inputs = scale_axis(inputs, row_axis, rf)
        values.append(
            [metric_value(scale_axis(row_inputs, col_axis, cf), metric) for cf in col_factors]
        )

    present = [v for row in values for v in row if v is not None]
    low, high = (min(present), max(present)) if present else (0.0, 0.0)
    span = high - low

    def heat(v: float | None) -> int:
        if v is None:
            return 0
        if span <= 0:
            return (HEAT_LEVELS + 1) // 2
        return 1 + min(HEAT_LEVELS - 1, int((v - low) / span * HEAT_LEVELS))

    rows = [
        GridRow(
            label=axis_label(inputs, row_axis, rf),
            cells=[
                GridCell(value=v, heat=heat(v), base=abs(rf - 1) < 1e-9 and abs(cf - 1) < 1e-9)
                for cf, v in zip(col_factors, row_values, strict=True)
            ],
        )
        for rf, row_values in zip(row_factors, values, strict=True)
    ]
    note = (
        f"Base case outlined. {AXIS_LABELS[col_axis]} in {col_step * 100:.0f}% steps, "
        f"{AXIS_LABELS[row_axis].lower()} in {row_step * 100:.0f}% steps."
    )
    return SensitivityGrid(
        row_axis=row_axis,
        col_axis=col_axis,
        metric=metric,
        row_step=row_step,
        col_step=col_step,
        col_labels=[axis_label(inputs, col_axis, cf) for cf in col_factors],
        rows=rows,
        note=note,
    )


def max_land_price_for_irr(
    inputs: DealInputs, floor: float, low_share: float = 0.25, high_share: float = 1.75
) -> float | None:
    """The highest land price per acre at which the unlevered IRR still reaches `floor`, by
    bisection between `low_share` and `high_share` of the underwritten price. None when even the
    low end misses the floor."""
    base = inputs.tract.purchase_price_per_acre
    lo, hi = base * low_share, base * high_share

    def irr_at(price: float) -> float:
        priced = inputs.model_copy(deep=True)
        priced.tract.purchase_price_per_acre = price
        value = run(priced).summary.unlevered_irr
        return value if value is not None else -1.0

    if irr_at(lo) < floor:
        return None
    if irr_at(hi) >= floor:
        return hi
    for _ in range(40):
        mid = (lo + hi) / 2
        if irr_at(mid) >= floor:
            lo = mid
        else:
            hi = mid
    return round(lo, -2)  # to the nearest $100 per acre
