"""The multifamily IC memo as a two- or three-page PDF deck.

Page 1 is the recommendation: the memo text beside the eight summary figures, sources and
uses and the loan. Page 2 is the evidence: NOI by year, the stress table, the unit mix, the
renovation program and the extracted assumptions with their sources. Page 3 exists only for a
deal that came through Screen: the documents read, every citation, and each question with the
extracted figure beside the analyst's answer. Every figure is an engine output and the memo text
is the checked memo; nothing is retyped.
"""

from __future__ import annotations

import datetime
from collections.abc import Sequence

from core.copilot.memo import Memo
from core.copilot.screen import ScreenResult
from core.copilot.sensitivity import StressRow
from core.copilot.summary import CopilotOutputs
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
    WARN,
    Deck,
    _k,
    _money,
    _money_m,
    _mult,
    _pct,
)


def build_deck(
    deal: str,
    facts_line: str,
    case: str,
    out: CopilotOutputs,
    memo: Memo,
    stress: Sequence[StressRow],
    assumptions: Sequence[dict[str, str]],
    floor: float,
    max_bid: float | None = None,
    screen: ScreenResult | None = None,
    documents: Sequence[tuple[str, str, str]] = (),
    qa: Sequence[tuple[str, str, str]] = (),
    date: datetime.date | None = None,
) -> bytes:
    """Render the deck. `documents` are (label, filename, extent) rows and `qa` are
    (question, extracted figure with source, analyst answer) rows for the audit page."""
    date = date or datetime.date.today()
    pdf = Deck()
    s, r, ln, su, reno = out.summary, out.returns, out.loan, out.sources_uses, out.renovation
    writer = "the sentence template" if memo.writer == "template" else memo.writer
    pdf.footer_text = (
        f"Synthetic deal. Every figure is a model output; prose drafted by {writer} and checked. "
        f"javiermendez.up.railway.app"
    )

    # ---------------------------------------------------------------- page 1: recommendation
    pdf.add_page()
    y0 = pdf.page_head(deal, case, "Recommendation", date)
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
    if memo.fallback:
        pdf.para(
            MARGIN,
            y + 2,
            left_w,
            "The model draft was rejected by the checks and the template was used.",
            "sans",
            7,
            3.8,
            MUTED,
        )

    lp_color = POS if (r.lp_irr or 0) >= floor else NEG
    bid_note = (
        f"Levered LP floor {floor:.0%} · max bid {_money_m(max_bid)}"
        if max_bid
        else f"Levered LP floor {floor:.0%}"
    )
    dscr_color = POS if (s.dscr_year1 or 0) >= ln.covenant_dscr else NEG
    cells = [
        (
            "Purchase price",
            _money_m(s.purchase_price),
            f"{_money(s.price_per_unit)} / unit"
            + (f" · ask {_money_m(s.asking_price)}" if s.asking_price else ""),
            INK,
        ),
        ("Going-in cap", _pct(s.going_in_cap, 2), f"Year 1 NOI {_money_m(s.noi_year1, 2)}", INK),
        (
            "Levered IRR",
            _pct(r.levered_irr),
            f"Unlevered {_pct(r.unlevered_irr)} · {_mult(r.lp_multiple)} to the LP",
            INK,
        ),
        ("LP IRR", _pct(r.lp_irr), bid_note, lp_color),
        ("Equity multiple", _mult(r.equity_multiple), f"On {_money_m(su.equity)} equity", INK),
        (
            "DSCR, year 1",
            _mult(s.dscr_year1),
            f"Covenant {_mult(ln.covenant_dscr)} · minimum {_mult(s.min_dscr)}",
            dscr_color,
        ),
        ("LTV", _pct(s.ltv), f"Debt yield {_pct(s.debt_yield)} · {ln.binding} bound", INK),
        ("Exit value", _money_m(s.exit_value), f"Forward NOI / {_pct(out.exit.cap_rate, 2)}", INK),
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
    pdf.eyebrow(right_x, y, "Sources and uses  ·  $ millions")
    rows = [
        [
            f"Agency loan, {_pct(ln.ltv)} LTV",
            f"{su.loan / 1e6:,.1f}",
            _pct(su.loan / su.total_uses),
        ],
        ["Equity", f"{su.equity / 1e6:,.1f}", _pct(su.equity / su.total_uses)],
        [
            "Purchase price",
            f"{su.purchase_price / 1e6:,.1f}",
            _pct(su.purchase_price / su.total_uses),
        ],
        [
            "Capital budget",
            f"{su.capital_budget / 1e6:,.1f}",
            _pct(su.capital_budget / su.total_uses),
        ],
        [
            "Closing costs and fees",
            f"{(su.closing_costs + su.loan_fees + su.acquisition_fee) / 1e6:,.1f}",
            _pct((su.closing_costs + su.loan_fees + su.acquisition_fee) / su.total_uses),
        ],
        ["Total uses", f"{su.total_uses / 1e6:,.1f}", "100.0%"],
    ]
    y = pdf.grid(
        right_x,
        y + 4.5,
        [right_w * 0.58, right_w * 0.22, right_w * 0.20],
        [],
        rows,
        ["L", "R", "R"],
        total_rows=[5],
        size=7.2,
        lh=4.3,
    )
    pdf.eyebrow(right_x, y + 3, "Senior loan")
    pdf.kv(
        right_x,
        y + 7.5,
        right_w,
        [
            ("Fixed rate", _pct(ln.rate, 2)),
            ("Interest only", f"{ln.io_months} months to {ln.io_expiry:%b %Y}"),
            (
                "Amortization and term",
                f"{ln.amortization_years} years · {ln.term_months // 12} years",
            ),
            (
                "Sizing",
                f"LTV {_money_m(ln.by_ltv)} · DSCR {_money_m(ln.by_dscr)} · "
                f"DY {_money_m(ln.by_debt_yield)}",
            ),
        ],
        size=7.0,
        lh=4.3,
    )

    # ---------------------------------------------------------------- page 2: evidence
    pdf.add_page()
    y = pdf.page_head(deal, case, "Evidence", date)
    years = out.annual
    pdf.eyebrow(
        MARGIN,
        y,
        f"Net operating income  ·  $ thousands  ·  {len(years)}-year hold  ·  "
        f"forward NOI {_k(out.exit.forward_noi)} sets the exit",
    )
    label_w = 62.0
    col_w = (CONTENT_W - label_w) / len(years)
    widths = [label_w] + [col_w] * len(years)
    aligns = ["L"] + ["R"] * len(years)
    header = ["Line"] + [f"Year {a.year}" for a in years]

    def line(name: str, get: str, sign: float = 1.0) -> list[str]:
        return [name] + [_k(sign * getattr(a, get)) for a in years]

    noi_rows = [
        line("Gross potential rent at market", "gpr"),
        line("Loss to lease", "loss_to_lease"),
        line("Renovation premium", "renovation_premium"),
        ["Vacancy, concessions, non-revenue, bad debt"]
        + [
            _k(a.vacancy + a.concessions + a.non_revenue + a.bad_debt + a.renovation_vacancy)
            for a in years
        ],
        line("Other income", "other_income"),
        line("Effective gross income", "egi"),
        line("Controllable expenses", "controllable", -1),
        line("Real estate taxes", "taxes", -1),
        line("Management fee", "management_fee", -1),
        line("Net operating income", "noi"),
        line("Debt service and reserves", "debt_service", -1),
        line("Cash flow after debt service", "cash_flow"),
        ["DSCR"] + [_mult(a.dscr) for a in years],
    ]
    noi_rows[10] = ["Debt service, reserves, asset management"] + [
        _k(-(a.debt_service + a.reserves + a.asset_management_fee)) for a in years
    ]
    y = pdf.grid(
        MARGIN, y + 4.5, widths, header, noi_rows, aligns, total_rows=[5, 9, 11], size=7.2, lh=4.35
    )

    y += 5
    panel_gap = 6.0
    panel_w = (CONTENT_W - 2 * panel_gap) / 3
    x1, x2, x3 = MARGIN, MARGIN + panel_w + panel_gap, MARGIN + 2 * (panel_w + panel_gap)
    pdf.eyebrow(x1, y, f"What breaks it  ·  loan held at {_money_m(ln.amount)}")
    stress_rows = [
        [row.label, _pct(row.levered_irr), _mult(row.min_dscr), "Holds" if row.holds else "Breach"]
        for row in stress
    ]
    stress_colors = {(i, 3): (POS if row.holds else NEG) for i, row in enumerate(stress)}
    y_stress = pdf.grid(
        x1,
        y + 4.5,
        [panel_w * 0.46, panel_w * 0.2, panel_w * 0.17, panel_w * 0.17],
        ["Stress", "Lev. IRR", "Min DSCR", "Covenant"],
        stress_rows,
        ["L", "R", "R", "R"],
        size=7.0,
        lh=4.3,
        colors=stress_colors,
    )

    pdf.eyebrow(x2, y, "Unit mix  ·  $ per unit per month")
    plan_rows = [
        [
            f"{fp.unit_type}",
            str(fp.units),
            f"{fp.sf:,.0f}",
            str(fp.occupied),
            _money(fp.in_place_rent),
            _money(fp.market_rent),
        ]
        for fp in out.floor_plans
    ]
    plan_rows.append(
        [
            "Total",
            str(s.units),
            f"{s.rentable_sf / s.units:,.0f}",
            str(s.occupied),
            _money(s.avg_in_place_rent),
            _money(s.avg_market_rent),
        ]
    )
    pw = panel_w
    y_plans = pdf.grid(
        x2,
        y + 4.5,
        [pw * 0.22, pw * 0.13, pw * 0.13, pw * 0.16, pw * 0.18, pw * 0.18],
        ["Plan", "Units", "SF", "Occ.", "In place", "Market"],
        plan_rows,
        ["L", "R", "R", "R", "R", "R"],
        total_rows=[len(plan_rows) - 1],
        size=7.0,
        lh=4.3,
    )
    pdf.para(
        x2,
        y_plans + 1.5,
        pw,
        f"Loss to lease {_pct(s.loss_to_lease_pct)}, burning off over twelve months of rollover.",
        "sans",
        6.6,
        3.6,
        MUTED,
    )

    pdf.eyebrow(x3, y, "Renovation and exit")
    pdf.kv(
        x3,
        y + 4.5,
        panel_w,
        [
            ("Units renovated", f"{reno.units} of {s.units}"),
            ("Cost per unit", _money(reno.cost_per_unit)),
            ("Premium per month", _money(reno.premium_per_month)),
            ("Return on cost", _pct(reno.return_on_cost)),
            (
                "Program and capital budget",
                f"{_money_m(reno.total_cost, 2)} · {_money_m(su.capital_budget, 2)}",
            ),
            (
                "Exit",
                f"{_pct(out.exit.cap_rate, 2)} cap on {_money_m(out.exit.forward_noi, 2)} "
                "forward NOI",
            ),
            (
                "Gross exit value",
                f"{_money_m(out.exit.gross_value)} · {_money(out.exit.value_per_unit)} / unit",
            ),
            ("Net proceeds after debt", _money_m(out.exit.net_after_debt)),
        ],
        size=7.0,
        lh=4.3,
    )

    y = max(y_stress, y_plans + 6, y + 4.5 + 8 * 4.3) + 6
    if y < PAGE_H - 50:
        pdf.eyebrow(
            MARGIN,
            y,
            f"Extracted assumptions  ·  {len(assumptions)} figures with source and confidence",
        )
        half = (CONTENT_W - panel_gap) / 2
        cols = [half * 0.30, half * 0.34, half * 0.25, half * 0.11]
        a_aligns = ["L", "R", "L", "R"]
        mid = (len(assumptions) + 1) // 2
        left_rows = [
            [a["assumption"], a["value"], a["source"], a["confidence"]] for a in assumptions[:mid]
        ]
        right_rows = [
            [a["assumption"], a["value"], a["source"], a["confidence"]] for a in assumptions[mid:]
        ]

        def conf_colors(rows_: list[list[str]]) -> dict[tuple[int, int], tuple[int, int, int]]:
            return {
                (i, 3): {"High": POS, "Medium": WARN, "Low": NEG}.get(r_[3], MUTED)
                for i, r_ in enumerate(rows_)
            }

        pdf.grid(
            MARGIN,
            y + 4.5,
            cols,
            ["Assumption", "Value", "Source", "Conf."],
            left_rows,
            a_aligns,
            size=6.8,
            lh=4.1,
            colors=conf_colors(left_rows),
        )
        pdf.grid(
            MARGIN + half + panel_gap,
            y + 4.5,
            cols,
            ["Assumption", "Value", "Source", "Conf."],
            right_rows,
            a_aligns,
            size=6.8,
            lh=4.1,
            colors=conf_colors(right_rows),
        )

    # ---------------------------------------------------------------- page 3: audit trail
    if screen is not None:
        pdf.add_page()
        y = pdf.page_head(deal, case, "Audit trail", date)
        pdf.eyebrow(
            MARGIN,
            y,
            f"Documents read  ·  OM read by {screen.reader}; rent roll and T-12 parsed directly",
        )
        doc_rows = [[label, name, extent] for label, name, extent in documents] or [
            ["No documents", "", ""]
        ]
        y = pdf.grid(
            MARGIN,
            y + 4.5,
            [CONTENT_W * 0.15, CONTENT_W * 0.45, CONTENT_W * 0.4],
            ["Document", "File", "Extent"],
            doc_rows,
            ["L", "L", "L"],
            size=7.0,
            lh=4.3,
        )
        y += 5
        pdf.eyebrow(MARGIN, y, "Extracted figures  ·  every quote checked against the cited page")
        figures = [e for e in screen.extractions if not e.plan]
        ext_rows = [
            [
                e.label,
                e.display(),
                f"{e.document} {e.page}".strip(),
                e.confidence,
                (e.quote or e.note)[:90],
            ]
            for e in figures
        ]
        ext_colors = {
            (i, 3): {"High": POS, "Medium": WARN, "Low": NEG}.get(e.confidence, MUTED)
            for i, e in enumerate(figures)
        }
        y = pdf.grid(
            MARGIN,
            y + 4.5,
            [
                CONTENT_W * 0.17,
                CONTENT_W * 0.11,
                CONTENT_W * 0.15,
                CONTENT_W * 0.07,
                CONTENT_W * 0.5,
            ],
            ["Figure", "Value", "Source", "Conf.", "Quote or note"],
            ext_rows,
            ["L", "R", "L", "L", "L"],
            size=6.6,
            lh=4.0,
            colors=ext_colors,
        )
        if qa and y < PAGE_H - 40:
            y += 5
            pdf.eyebrow(
                MARGIN,
                y,
                "Questions the documents left open  ·  extracted figure beside the answer",
            )
            qa_rows = [[q, e, a] for q, e, a in qa]
            room = int((PAGE_H - 16 - (y + 4.5 + 4.0)) // 4.0)
            pdf.grid(
                MARGIN,
                y + 4.5,
                [CONTENT_W * 0.46, CONTENT_W * 0.32, CONTENT_W * 0.22],
                ["Question", "From the documents", "Underwritten"],
                qa_rows[: max(room, 0)],
                ["L", "L", "R"],
                size=6.6,
                lh=4.0,
            )

    return bytes(pdf.output())
