"""Land Underwriting routes: the Cypress Ridge deal, its scenarios, tabs, sensitivity, memo."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pydantic import ValidationError

from app import forms
from app.deals import load_cypress_ridge
from app.sessions import DealSession, Scenario, scenario_store, set_session_cookie
from app.templating import render
from core.underwriting.deck import build_land_deck
from core.underwriting.engine import run
from core.underwriting.inputs import DealInputs
from core.underwriting.memo import IRR_FLOOR, build_land_facts, write_land_memo
from core.underwriting.sensitivity import (
    AXIS_LABELS,
    METRIC_LABELS,
    Axis,
    Metric,
    build_grid,
    max_land_price_for_irr,
)
from core.underwriting.summary import Outputs

router = APIRouter(prefix="/underwriting")

META, SEED = load_cypress_ridge()
store = scenario_store(SEED)

TABS: list[tuple[str, str, str]] = [
    ("performance", "Performance", "/underwriting"),
    ("tract", "Tract", "/underwriting/tract"),
    ("costs", "Costs", "/underwriting/costs"),
    ("revenue", "Revenue", "/underwriting/revenue"),
    ("cashflows", "Cashflows", "/underwriting/cashflows"),
    ("lookups", "Lookups", "/underwriting/lookups"),
]
INPUT_TABS = {"tract", "costs", "revenue", "lookups"}
TabName = Literal["tract", "costs", "revenue", "cashflows", "lookups"]

COMPARE_METRICS: list[tuple[str, str, str]] = [
    ("Total revenue", "total_revenue", "money_m"),
    ("Gross costs", "gross_costs", "money_m"),
    ("Gross margin", "gross_margin", "money_m"),
    ("Gross margin, % of revenue", "gross_margin_of_revenue", "pct"),
    ("Net margin", "net_margin", "money_m"),
    ("Net margin, % of revenue", "net_margin_of_revenue", "pct"),
    ("Unlevered IRR", "unlevered_irr", "pct"),
    ("Peak cash need", "peak_cash_need", "money_m"),
    ("Total lots", "total_lots", "num"),
    ("Project length, months", "project_length_months", "num"),
]


def header_facts(inputs: DealInputs) -> str:
    t = inputs.tract
    closing = t.closing_date.strftime("%b %Y") if t.closing_date else "Closing date not set"
    return (
        f"{t.gross_acreage:,.1f} ac · {META['location']} · Closing {closing} · "
        f"${t.purchase_price_per_acre:,.0f} / ac"
    )


def deal_context(
    request: Request, session: DealSession, scenario: Scenario, tab: str
) -> dict[str, Any]:
    outputs = run(scenario.inputs)
    compare = [(s.name, run(s.inputs).summary) for s in session.scenarios]
    return {
        "meta": META,
        "facts": header_facts(scenario.inputs),
        "tabs": TABS,
        "active_tab": tab,
        "scenarios": session.names(),
        "scenario": scenario.name,
        "inputs": scenario.inputs,
        "out": outputs,
        "compare": compare,
        "compare_metrics": COMPARE_METRICS,
        "query": f"?scenario={scenario.name}",
    }


def financial_lines(out: Outputs) -> dict[str, Any]:
    """Revenue and cost lines ordered by size; costs beyond the top ten fold into one row."""
    rev_labels = {
        "lot_sales": "Lot sales",
        "mud": "MUD proceeds",
        "wcid": "WCID proceeds",
        "escalations": "Escalations",
        "premiums": "Lot premiums",
        "marketing_fees": "Marketing fees",
        "commercial_pods": "Commercial pod sales",
        "residential_pods": "Residential pod sales",
        "fence_fees": "Fence fees",
    }
    cost_labels = {
        "sections": "Sections",
        "land": "Land",
        "roads": "Collector roads",
        "plants": "Plants",
        "contingency": "Contingency",
        "detention": "Detention",
        "brokerage": "Brokerage",
        "marketing": "Marketing",
        "amenities": "Amenities",
        "landscaping": "Landscaping",
        "fencing": "Fencing",
        "dry_utilities": "Dry utilities",
        "site_work": "Site work",
        "legal": "Legal",
        "lot_taxes": "Lot taxes",
        "mud_hoa": "MUD and HOA",
        "insurance": "Insurance",
        "closing": "Lot closing costs",
        "mailboxes": "Mailboxes",
        "professional_services": "Professional services",
        "other": "Other items",
    }
    rev = out.revenue.model_dump()
    cost = out.costs.model_dump()
    revenue_rows = sorted(
        ((rev_labels[k], v) for k, v in rev.items() if k != "total"), key=lambda r: -r[1]
    )
    cost_rows_all = sorted(
        ((cost_labels[k], v) for k, v in cost.items() if k != "total"), key=lambda r: -r[1]
    )
    top, rest = cost_rows_all[:10], cost_rows_all[10:]
    cost_rows = list(top)
    if rest:
        cost_rows.append((f"All other ({len(rest)} lines)", sum(v for _, v in rest)))
    below = [
        ("Development management fee", out.below_line.dmf),
        ("Personnel", out.below_line.personnel),
        ("Bookkeeping", out.below_line.bookkeeping),
        ("Receivables fees", out.below_line.receivables_fees),
    ]
    return {"revenue_rows": revenue_rows, "cost_rows": cost_rows, "below_rows": below}


def yearly_categories(out: Outputs) -> dict[str, Any]:
    """Cash flow line items by year, aggregated from the monthly detail."""
    rev_cats = [
        ("rev_lot_sales", "Lot sales and fees"),
        ("rev_res_pods", "Residential pod sales"),
        ("rev_comm_pods", "Commercial pod sales"),
        ("rev_mud_wcid", "MUD and WCID proceeds"),
    ]
    cost_cats = [
        ("cost_land", "Land"),
        ("cost_sections", "Sections"),
        ("cost_plants", "Plants"),
        ("cost_detention", "Detention"),
        ("cost_roads", "Collector roads"),
        ("cost_amenities", "Amenities"),
        ("cost_other", "Other items"),
        ("cost_landscaping", "Landscaping"),
        ("cost_fencing", "Fencing"),
        ("cost_dry_utilities", "Dry utilities"),
        ("cost_site_work", "Site work"),
        ("cost_dmf", "Development management fee"),
        ("cost_operating", "Operating, fees and contingency"),
    ]
    years = sorted({m.year for m in out.cf_monthly})
    by_year: dict[int, dict[str, int]] = {y: {} for y in years}
    for m in out.cf_monthly:
        row = by_year[m.year]
        for key, _ in rev_cats + cost_cats:
            row[key] = row.get(key, 0) + getattr(m, key)
        row["revenue"] = row.get("revenue", 0) + m.revenue
        row["cost"] = row.get("cost", 0) + m.cost
        row["net"] = row.get("net", 0) + m.net
    totals = {k: sum(r[k] for r in by_year.values()) for k in by_year[years[0]]}
    return {
        "years": years,
        "by_year": by_year,
        "totals": totals,
        "rev_cats": rev_cats,
        "cost_cats": cost_cats,
    }


def _grid_params(
    row_axis: Axis,
    col_axis: Axis,
    metric: Metric,
    row_steps: int,
    col_steps: int,
    row_step: float,
    col_step: float,
) -> dict[str, Any]:
    return {
        "row_axis": row_axis,
        "col_axis": col_axis,
        "metric": metric,
        "row_steps": row_steps,
        "col_steps": col_steps,
        "row_step": row_step,
        "col_step": col_step,
    }


def _finish(response: Response, sid: str | None) -> Response:
    set_session_cookie(response, sid)
    return response


@router.get("", response_class=HTMLResponse)
async def performance(
    request: Request,
    scenario: str | None = None,
    row_axis: Axis = "pace",
    col_axis: Axis = "lot_price",
    metric: Metric = "irr",
    row_steps: Annotated[int, Query(ge=1, le=3)] = 2,
    col_steps: Annotated[int, Query(ge=1, le=3)] = 2,
    row_step: Annotated[float, Query(gt=0, le=0.5)] = 0.10,
    col_step: Annotated[float, Query(gt=0, le=0.5)] = 0.05,
) -> Response:
    session, sid = store.load(request)
    current = session.get(scenario)
    ctx = deal_context(request, session, current, "performance")
    params = _grid_params(row_axis, col_axis, metric, row_steps, col_steps, row_step, col_step)
    grid = build_grid(current.inputs, **params)
    ctx.update(financial_lines(ctx["out"]))
    ctx.update(grid=grid, grid_params=params, axis_labels=AXIS_LABELS, metric_labels=METRIC_LABELS)
    return _finish(render(request, "underwriting/performance.html", **ctx), sid)


@router.get("/memo.pdf")
async def memo_deck(request: Request, scenario: str | None = None) -> Response:
    """The land deal's IC memo as a two-page PDF, for the scenario."""
    session, sid = store.load(request)
    current = session.get(scenario)
    out = run(current.inputs)
    grid = build_grid(current.inputs)
    max_price = max_land_price_for_irr(current.inputs, IRR_FLOOR)
    at_max = None
    if max_price is not None:
        priced = current.inputs.model_copy(deep=True)
        priced.tract.purchase_price_per_acre = max_price
        at_max = run(priced)
    facts = build_land_facts(current.inputs, out, grid, current.name, IRR_FLOOR, max_price, at_max)
    memo = write_land_memo(facts)
    pdf = build_land_deck(
        META["name"],
        header_facts(current.inputs),
        current.name,
        current.inputs,
        out,
        memo,
        grid,
        IRR_FLOOR,
        max_price,
    )
    filename = f"cypress-ridge-ic-memo-{current.name.lower().replace(' ', '-')}.pdf"
    response = Response(
        pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
    set_session_cookie(response, sid)
    return response


@router.get("/sensitivity", response_class=HTMLResponse)
async def sensitivity(
    request: Request,
    scenario: str | None = None,
    row_axis: Axis = "pace",
    col_axis: Axis = "lot_price",
    metric: Metric = "irr",
    row_steps: Annotated[int, Query(ge=1, le=3)] = 2,
    col_steps: Annotated[int, Query(ge=1, le=3)] = 2,
    row_step: Annotated[float, Query(gt=0, le=0.5)] = 0.10,
    col_step: Annotated[float, Query(gt=0, le=0.5)] = 0.05,
) -> Response:
    session, sid = store.load(request)
    current = session.get(scenario)
    params = _grid_params(row_axis, col_axis, metric, row_steps, col_steps, row_step, col_step)
    grid = build_grid(current.inputs, **params)
    return _finish(
        render(
            request,
            "underwriting/_sensitivity.html",
            grid=grid,
            grid_params=params,
            axis_labels=AXIS_LABELS,
            metric_labels=METRIC_LABELS,
            scenario=current.name,
            query=f"?scenario={current.name}",
        ),
        sid,
    )


@router.get("/{tab}", response_class=HTMLResponse)
async def tab_page(request: Request, tab: TabName, scenario: str | None = None) -> Response:
    session, sid = store.load(request)
    current = session.get(scenario)
    ctx = deal_context(request, session, current, tab)
    if tab == "cashflows":
        ctx.update(yearly_categories(ctx["out"]))
    return _finish(render(request, f"underwriting/{tab}.html", **ctx), sid)


def checkbox_paths(tab: str) -> list[str]:
    if tab == "costs":
        return [f"costs.lot_sizes.{i}.on" for i in range(16)]
    if tab == "revenue":
        return ["revenue.mud_bond.toggle", "revenue.wcid_bond.toggle"]
    return []


@router.post("/inputs/{tab}", response_class=HTMLResponse)
async def update_inputs(request: Request, tab: TabName, scenario: str | None = None) -> Response:
    """Apply an edited input form to the active scenario and re-render the tab and the strip."""
    if tab not in INPUT_TABS:
        return RedirectResponse(f"/underwriting/{tab}", status_code=303)
    session, sid = store.load(request)
    current = session.get(scenario)
    form = await request.form()
    fields = {k: str(v) for k, v in form.multi_items() if isinstance(v, str)}
    errors: list[str] = []
    try:
        current.inputs = forms.apply_form(current.inputs, fields, checkbox_paths(tab))
    except ValidationError as exc:
        errors = forms.validation_messages(exc)
    except (ValueError, TypeError) as exc:
        errors = [str(exc)]
    ctx = deal_context(request, session, current, tab)
    ctx.update(errors=errors, partial=True)
    return _finish(render(request, f"underwriting/{tab}.html", **ctx), sid)


@router.post("/scenarios/add")
async def add_scenario(
    request: Request, source: Annotated[str, Form()], name: Annotated[str, Form()] = ""
) -> Response:
    session, sid = store.load(request)
    base = session.get(source)
    new_name = session.unique_name(name or f"{base.name} copy")
    session.scenarios.append(Scenario(name=new_name, inputs=base.inputs.model_copy(deep=True)))
    return _finish(RedirectResponse(f"/underwriting?scenario={new_name}", status_code=303), sid)


@router.post("/scenarios/rename")
async def rename_scenario(
    request: Request, name: Annotated[str, Form()], new_name: Annotated[str, Form()]
) -> Response:
    session, sid = store.load(request)
    current = session.get(name)
    if new_name.strip() and new_name.strip() != current.name:
        current.name = session.unique_name(new_name)
    return _finish(RedirectResponse(f"/underwriting?scenario={current.name}", status_code=303), sid)


@router.post("/scenarios/delete")
async def delete_scenario(request: Request, name: Annotated[str, Form()]) -> Response:
    session, sid = store.load(request)
    if len(session.scenarios) > 1:
        session.scenarios = [s for s in session.scenarios if s.name != name] or session.scenarios
    return _finish(RedirectResponse("/underwriting", status_code=303), sid)


@router.post("/scenarios/reset")
async def reset_session(request: Request) -> Response:
    store.reset(request)
    return RedirectResponse("/underwriting", status_code=303)
