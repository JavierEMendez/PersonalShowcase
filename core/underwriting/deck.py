"""The land deal's IC memo as a two-page PDF deck.

Page 1 is the recommendation: the memo beside the eight summary figures, the acreage and the
financial summary. Page 2 is the evidence: net cash flow by year, the sensitivity grid, revenue
and cost lines, and the lot mix. Every figure is an engine output; the memo text is the checked
memo. Built on the same primitives as the multifamily deck.
"""

from __future__ import annotations

import datetime
from collections.abc import Sequence

from core.copilot.memo import Memo
from core.pdf import (
    CONTENT_W,
    HAIRLINE,
    INK,
    INK2,
    MARGIN,
    MUTED,
    NEG,
    PAGE_H,
    POS,
    Deck,
    _money,
    _money_m,
    _pct,
)
from core.underwriting.inputs import DealInputs
from core.underwriting.sensitivity import SensitivityGrid
from core.underwriting.summary import Outputs

REVENUE_LABELS = [
    ("lot_sales", "Lot sales"),
    ("mud", "MUD proceeds"),
    ("wcid", "WCID proceeds"),
    ("marketing_fees", "Marketing fees"),
    ("commercial_pods", "Commercial pod sales"),
    ("residential_pods", "Residential pod sales"),
    ("escalations", "Escalations"),
    ("premiums", "Lot premiums"),
    ("fence_fees", "Fence fees"),
]
COST_LABELS = [
    ("sections", "Sections"),
    ("land", "Land"),
    ("detention", "Detention"),
    ("plants", "Plants"),
    ("contingency", "Contingency"),
    ("marketing", "Marketing"),
    ("roads", "Collector roads"),
    ("landscaping", "Landscaping"),
    ("amenities", "Amenities"),
    ("brokerage", "Brokerage"),
    ("other", "Other items"),
    ("fencing", "Fencing"),
    ("dry_utilities", "Dry utilities"),
    ("site_work", "Site work"),
    ("legal", "Legal"),
    ("lot_taxes", "Lot taxes"),
    ("mud_hoa", "MUD and HOA advances"),
    ("insurance", "Insurance"),
]


def _m(v: float) -> str:
    """$ millions with one decimal, negatives in parentheses."""
    return f"({abs(v) / 1e6:,.1f})" if v < 0 else f"{v / 1e6:,.1f}"


def build_land_deck(
    deal: str,
    facts_line: str,
    scenario: str,
    inputs: DealInputs,
    out: Outputs,
    memo: Memo,
    grid: SensitivityGrid,
    floor: float,
    max_price: float | None = None,
    compare: Sequence[tuple[str, str, Sequence[str]]] = (),
    date: datetime.date | None = None,
) -> bytes:
    """Render the deck. `compare` rows are (metric, unit, values per scenario) with the
    scenario names carried in the first row's values position by the caller."""
    date = date or datetime.date.today()
    pdf = Deck()
    pdf.product = "Land Underwriting"
    s, a, t = out.summary, out.acreage, inputs.tract
    pdf.footer_text = (
        "Synthetic deal. Every figure is a model output; prose from the sentence template and "
        "checked. javiermendez.up.railway.app"
    )

    # ---------------------------------------------------------------- page 1: recommendation
    pdf.add_page()
    y0 = pdf.page_head(deal, scenario, "Recommendation", date)
    pdf.font("sans", 8, color=MUTED)
    pdf.set_xy(MARGIN, y0 - 2.5)
    pdf.cell(CONTENT_W, 4, pdf.text_safe(facts_line))
    y0 += 5
    left_w, gap = 150.0, 8.0
    right_x = MARGIN + left_w + gap
    right_w = CONTENT_W - left_w - gap

    pdf.eyebrow(MARGIN, y0, "Recommendation")
    y = pdf.para(MARGIN, y0 + 5, left_w, memo.recommendation, "serif", 12.5, 6.2)
    y = pdf.para(MARGIN, y + 3, left_w, " ".join(memo.body), "sans", 8.6, 4.7, INK2)
    pdf.eyebrow(MARGIN, y + 5, "What the model cannot tell you")
    y = y + 10
    for item in memo.cannot:
        pdf.font("sans", 8.4, color=INK2)
        pdf.set_xy(MARGIN, y)
        pdf.cell(4, 4.5, "-")
        y = pdf.para(MARGIN + 4, y, left_w - 4, item, "sans", 8.4, 4.5, INK2) + 0.8

    irr_color = POS if (s.unlevered_irr or 0) >= floor else NEG
    irr_note = f"Floor {floor:.0%}" + (f" · max {_money(max_price)} / ac" if max_price else "")
    cells = [
        ("Unlevered IRR", _pct(s.unlevered_irr), irr_note, irr_color),
        ("Total revenue", _money_m(s.total_revenue), f"{s.total_lots:,} lots delivered", INK),
        (
            "Gross costs",
            _money_m(s.gross_costs),
            f"{_pct(s.gross_costs / s.total_revenue)} of revenue",
            INK,
        ),
        (
            "Gross margin",
            _money_m(s.gross_margin),
            f"{_pct(s.gross_margin_of_revenue)} of revenue",
            INK,
        ),
        ("Net margin", _money_m(s.net_margin), f"{_pct(s.net_margin_of_revenue)} of revenue", INK),
        ("Return on cost", _pct(s.return_on_cost), "Gross profit / gross costs", INK),
        (
            "Peak cash need",
            _money_m(s.peak_cash_need),
            f"Cumulative, month {s.peak_cash_month}",
            INK,
        ),
        (
            "Project length",
            f"{s.project_length_years:.1f} yrs",
            f"{s.project_length_months} months"
            + (f" · breakeven in year {s.breakeven_year}" if s.breakeven_year else ""),
            INK,
        ),
    ]
    cell_w, cell_h = right_w / 2, 18.0
    pdf.rule(right_x, y0, right_w, INK, 0.4)
    for i, (label, figure, note, color) in enumerate(cells):
        cx = right_x + (i % 2) * cell_w
        cy = y0 + 1.5 + (i // 2) * cell_h
        pdf.kpi(cx, cy, cell_w - 3, cell_h, label, figure, note, color)
        if i % 2 == 1:
            pdf.rule(right_x, cy + cell_h - 0.5, right_w, HAIRLINE, 0.18)
    y = y0 + 1.5 + 4 * cell_h + 4
    pdf.eyebrow(right_x, y, "Acreage")
    acres = [
        ["Gross", f"{a.gross:,.1f}"],
        [
            "Detention, parks, roads, plants, amenities",
            f"({a.detention + a.parks + a.roads + a.plants + a.amenities:,.1f})",
        ],
        ["Drill sites and other net-outs", f"({a.drill_sites + a.other:,.1f})"],
        ["Developable", f"{a.developable:,.1f}"],
        ["Commercial and residential pods", f"({a.commercial_pods + a.residential_pods:,.1f})"],
        ["Residential developable", f"{a.residential_developable:,.1f}"],
    ]
    y = pdf.grid(
        right_x,
        y + 4.5,
        [right_w * 0.72, right_w * 0.28],
        [],
        acres,
        ["L", "R"],
        total_rows=[3, 5],
        size=7.2,
        lh=4.3,
    )
    pdf.eyebrow(right_x, y + 3, f"Land  ·  {_money(t.purchase_price_per_acre)} per acre")
    pdf.kv(
        right_x,
        y + 7.5,
        right_w,
        [
            ("Purchase price", _money_m(t.gross_acreage * t.purchase_price_per_acre)),
            ("Revenue per developable acre", _money(s.rev_per_dev_acre)),
            ("Infrastructure per lot", _money(s.infra_per_lot)),
            ("Lots per year", f"{s.home_sales_per_year:,}"),
        ],
        size=7.0,
        lh=4.3,
    )

    # ---------------------------------------------------------------- page 2: evidence
    pdf.add_page()
    y = pdf.page_head(deal, scenario, "Evidence", date)
    panel_gap = 6.0
    half = (CONTENT_W - panel_gap) / 2
    x2 = MARGIN + half + panel_gap

    pdf.eyebrow(MARGIN, y, "Net cash flow by year  ·  $ millions  ·  unlevered")
    cf_rows = [
        [
            f"Year {r.year}",
            _m(r.revenue),
            _m(-r.cost),
            _m(r.net),
            _m(r.cumulative),
            f"{r.lots:,}",
            f"{r.homes:,}",
        ]
        for r in out.yearly
    ]
    cf_rows.append(
        [
            "Total",
            _m(sum(r.revenue for r in out.yearly)),
            _m(-sum(r.cost for r in out.yearly)),
            _m(sum(r.net for r in out.yearly)),
            _m(out.yearly[-1].cumulative if out.yearly else 0),
            f"{sum(r.lots for r in out.yearly):,}",
            f"{sum(r.homes for r in out.yearly):,}",
        ]
    )
    cw = half
    y_cf = pdf.grid(
        MARGIN,
        y + 4.5,
        [cw * 0.16, cw * 0.16, cw * 0.16, cw * 0.16, cw * 0.16, cw * 0.1, cw * 0.1],
        ["Period", "Revenue", "Cost", "Net", "Cumulative", "Lots", "Homes"],
        cf_rows,
        ["L", "R", "R", "R", "R", "R", "R"],
        total_rows=[len(cf_rows) - 1],
        size=7.0,
        lh=4.2,
    )

    metric = "Unlevered IRR" if grid.metric == "irr" else "Gross margin"
    pdf.eyebrow(x2, y, f"Sensitivity  ·  {metric}  ·  {grid.note}")
    g_widths = [half * 0.22] + [half * 0.78 / len(grid.col_labels)] * len(grid.col_labels)
    g_header = [grid.row_axis.replace("_", " ").title()] + list(grid.col_labels)
    g_rows = []
    g_colors: dict[tuple[int, int], tuple[int, int, int]] = {}
    for i, row in enumerate(grid.rows):
        cells_txt = []
        for j, c in enumerate(row.cells):
            if c.value is None:
                cells_txt.append("n/a")
                continue
            cells_txt.append(_pct(c.value) if grid.metric == "irr" else _money_m(c.value))
            if c.base:
                g_colors[(i, j + 1)] = INK
            elif grid.metric == "irr" and c.value < floor:
                g_colors[(i, j + 1)] = NEG
        g_rows.append([row.label, *cells_txt])
    y_grid = pdf.grid(
        x2,
        y + 4.5,
        g_widths,
        g_header,
        g_rows,
        ["L"] + ["R"] * len(grid.col_labels),
        size=7.0,
        lh=4.2,
        colors=g_colors,
    )
    pdf.para(
        x2,
        y_grid + 1.5,
        half,
        f"Base case in black; cells below the {floor:.0%} floor in red.",
        "sans",
        6.6,
        3.6,
        MUTED,
    )

    y = max(y_cf, y_grid + 6) + 6
    pdf.eyebrow(MARGIN, y, "Revenue  ·  $ millions")
    rev_rows = [
        [label, _m(getattr(out.revenue, key)), _pct(getattr(out.revenue, key) / s.total_revenue)]
        for key, label in REVENUE_LABELS
        if getattr(out.revenue, key)
    ]
    rev_rows.sort(key=lambda r: -float(r[1].strip("()").replace(",", "")))
    rev_rows.append(["Total revenue", _m(s.total_revenue), "100.0%"])
    y_rev = pdf.grid(
        MARGIN,
        y + 4.5,
        [half * 0.6, half * 0.2, half * 0.2],
        ["Line", "Amount", "% of revenue"],
        rev_rows,
        ["L", "R", "R"],
        total_rows=[len(rev_rows) - 1],
        size=7.0,
        lh=4.1,
    )

    pdf.eyebrow(x2, y, "Costs  ·  $ millions")
    cost_rows = [
        [label, _m(getattr(out.costs, key)), _pct(getattr(out.costs, key) / s.gross_costs)]
        for key, label in COST_LABELS
        if hasattr(out.costs, key) and getattr(out.costs, key)
    ]
    cost_rows.sort(key=lambda r: -float(r[1].strip("()").replace(",", "")))
    shown = cost_rows[:10]
    rest = cost_rows[10:]
    if rest:
        rest_total = sum(
            getattr(out.costs, key) for key, _ in COST_LABELS if hasattr(out.costs, key)
        ) - sum(float(r[1].replace(",", "")) * 1e6 for r in shown)
        shown.append(
            [f"All other ({len(rest)} lines)", _m(rest_total), _pct(rest_total / s.gross_costs)]
        )
    shown.append(["Gross costs", _m(s.gross_costs), "100.0%"])
    shown.append(
        ["Overhead and fees", _m(out.below_line.total), _pct(out.below_line.total / s.gross_costs)]
    )
    y_cost = pdf.grid(
        x2,
        y + 4.5,
        [half * 0.6, half * 0.2, half * 0.2],
        ["Line", "Amount", "% of costs"],
        shown,
        ["L", "R", "R"],
        total_rows=[len(shown) - 2],
        size=7.0,
        lh=4.1,
    )

    y = max(y_rev, y_cost) + 6
    active = [ls for ls in inputs.costs.lot_sizes if ls.on]
    if active and y < PAGE_H - 40:
        pdf.eyebrow(MARGIN, y, "Lot mix  ·  active lot sizes")
        lot_rows = [
            [
                f"{ls.front_footage:.0f} FF",
                f"{ls.yield_per_ac:.1f}",
                f"{ls.pace:.1f}",
                f"{ls.dev_start_month}",
                _money(ls.wsd_per_ff + ls.paving_per_ff),
                _money(ls.home_price),
            ]
            for ls in active
        ]
        pdf.grid(
            MARGIN,
            y + 4.5,
            [half * 0.16, half * 0.16, half * 0.16, half * 0.16, half * 0.18, half * 0.18],
            ["Lot", "Lots / ac", "Pace / mo", "Dev start", "Section $ / FF", "Home price"],
            lot_rows,
            ["L", "R", "R", "R", "R", "R"],
            size=7.0,
            lh=4.1,
        )
    return bytes(pdf.output())
