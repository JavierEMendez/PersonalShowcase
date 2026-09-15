"""Generate the synthetic Sawyer Bend deal documents into data/sawyer_bend/.

Three files a broker would send on a value-add multifamily listing: the offering memorandum
(PDF), the rent roll (xlsx) and the trailing twelve-month operating statement (xlsx). Every
figure is invented and reconciles to the seed inputs in scripts/seed_sawyer_bend.py, so the
Screen step can be exercised and scored without an API key.

    python scripts/make_sawyer_bend_docs.py
"""

from __future__ import annotations

import datetime
import random
import sys
from pathlib import Path

from fpdf import FPDF
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.seed_sawyer_bend import base_inputs  # noqa: E402

OUT = ROOT / "data" / "sawyer_bend"
AS_OF = datetime.date(2026, 8, 31)
BROKER = "Ridgeline Multifamily Advisors"
SEED = base_inputs()
PLANS = SEED.property.floor_plans
UNITS = SEED.property.units
RENTABLE_SF = SEED.property.rentable_sf
ASK = SEED.acquisition.asking_price or 0.0

# Seller-side operating figures. The buyer adjusts these upward in underwriting, which is what
# the question loop is for; the T-12 shows what the seller actually spent.
T12_PER_UNIT = {
    "Payroll": 1_290,
    "Repairs and maintenance": 610,
    "Turnover": 230,
    "Contract services": 290,
    "Marketing": 165,
    "Administrative": 215,
    "Utilities": 880,
}
T12_INSURANCE_PER_UNIT = 720
ASSESSED_VALUE_2025 = 26_040_000
TAX_RATE = SEED.operating.tax_rate
OTHER_INCOME_PER_UNIT_MONTH = SEED.revenue.other_income_per_unit_month
RENOVATED_UNITS = 36
RENOVATION_PREMIUM = SEED.renovation.premium_per_month

MONTHS = [
    (datetime.date(2025, 9, 1) + datetime.timedelta(days=31 * i)).replace(day=1) for i in range(12)
]


# --------------------------------------------------------------------------------------------
# Rent roll
# --------------------------------------------------------------------------------------------
def _spread(total: float, n: int, rng: random.Random, step: int = 5, width: int = 60) -> list[int]:
    """n rents in $step increments averaging exactly total / n."""
    if n == 0:
        return []
    avg = int(round(total / n))
    offsets = [rng.randrange(-width, width + 1, step) for _ in range(n)]
    drift = sum(offsets)
    i = 0
    while drift != 0:
        move = step if drift > 0 else -step
        if -width <= offsets[i] - move <= width:
            offsets[i] -= move
            drift -= move
        i = (i + 1) % n
    return [avg + o for o in offsets]


def rent_roll_rows() -> list[dict[str, object]]:
    rng = random.Random(7)
    rows: list[dict[str, object]] = []
    unit_no = 0
    for plan in PLANS:
        occupied_rents = _spread(plan.in_place_rent * plan.occupied, plan.occupied, rng)
        vacant = plan.units - plan.occupied
        statuses = ["Occupied"] * plan.occupied + ["Vacant"] * vacant
        rng.shuffle(statuses)
        rent_iter = iter(occupied_rents)
        for status in statuses:
            unit_no += 1
            building = (unit_no - 1) // 24 + 1
            number = f"{building:02d}{(unit_no - 1) % 24 + 1:02d}"
            lease_rent: float | None = next(rent_iter) if status == "Occupied" else None
            start = AS_OF - datetime.timedelta(days=rng.randrange(30, 400)) if lease_rent else None
            end = start + datetime.timedelta(days=365) if start else None
            rows.append(
                {
                    "unit": number,
                    "plan": plan.code,
                    "type": plan.unit_type.replace(" x ", "BR/") + "BA",
                    "sf": plan.sf,
                    "status": status,
                    "market": plan.market_rent,
                    "rent": lease_rent,
                    "start": start,
                    "end": end,
                    "deposit": 500 if lease_rent else None,
                }
            )
    # Two non-revenue units: a model and a leasing office, taken from the vacant pool.
    non_revenue = [r for r in rows if r["status"] == "Vacant"]
    non_revenue[0]["status"] = "Model"
    non_revenue[-1]["status"] = "Office"
    return rows


def write_rent_roll(path: Path) -> None:
    rows = rent_roll_rows()
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Rent Roll"
    ws["A1"] = "Sawyer Bend Apartments"
    ws["A1"].font = Font(bold=True, size=13)
    ws["A2"] = f"Rent Roll as of {AS_OF:%B %d, %Y}"
    ws["A3"] = f"{UNITS} units, {RENTABLE_SF:,.0f} rentable square feet"
    headers = [
        "Unit",
        "Floor Plan",
        "Bed/Bath",
        "SF",
        "Status",
        "Market Rent",
        "Lease Rent",
        "Lease Start",
        "Lease End",
        "Deposit",
    ]
    ws.append([])
    ws.append(headers)
    for cell in ws[5]:
        cell.font = Font(bold=True)
    for r in rows:
        ws.append(
            [
                r["unit"],
                r["plan"],
                r["type"],
                r["sf"],
                r["status"],
                r["market"],
                r["rent"],
                r["start"],
                r["end"],
                r["deposit"],
            ]
        )
    first, last = 6, 5 + len(rows)
    ws.append([])
    ws.append(["Totals"])
    ws.append(["Units", len(rows)])
    ws.append(["Occupied units", sum(1 for r in rows if r["status"] == "Occupied")])
    ws.append(["Vacant units", sum(1 for r in rows if r["status"] == "Vacant")])
    ws.append(["Non-revenue units", sum(1 for r in rows if r["status"] in ("Model", "Office"))])
    ws.append(["Total monthly lease rent", f"=SUM(G{first}:G{last})"])
    ws.append(["Total monthly market rent", f"=SUM(F{first}:F{last})"])
    for col, width in zip(range(1, 11), [8, 11, 10, 8, 11, 13, 12, 13, 13, 10], strict=True):
        ws.column_dimensions[get_column_letter(col)].width = width
    for row in ws.iter_rows(min_row=first, max_row=last):
        for cell in row[5:7]:
            cell.number_format = "#,##0"
        for cell in row[7:9]:
            cell.number_format = "yyyy-mm-dd"
    ws.freeze_panes = "A6"
    wb.save(path)


# --------------------------------------------------------------------------------------------
# T-12
# --------------------------------------------------------------------------------------------
def _monthly(total: float, rng: random.Random, jitter: float = 0.04) -> list[float]:
    """Twelve months around total / 12 that sum exactly to total."""
    base = total / 12
    values = [round(base * (1 + rng.uniform(-jitter, jitter))) for _ in range(12)]
    values[-1] += round(total) - sum(values)
    return [float(v) for v in values]


def t12_lines() -> list[tuple[str, list[float] | None]]:
    rng = random.Random(11)
    gpr_market = sum(fp.units * fp.market_rent for fp in PLANS) * 12
    loss_to_lease = -sum(fp.units * (fp.market_rent - fp.in_place_rent) for fp in PLANS) * 12
    vacancy = -sum((fp.units - fp.occupied) * fp.in_place_rent for fp in PLANS) * 12
    concessions = -0.005 * (gpr_market + loss_to_lease)
    bad_debt = -0.0075 * (gpr_market + loss_to_lease)
    other_income = OTHER_INCOME_PER_UNIT_MONTH * UNITS * 12
    lines: list[tuple[str, list[float] | None]] = [
        ("Gross potential rent", _monthly(gpr_market, rng, 0.01)),
        ("Loss to lease", _monthly(loss_to_lease, rng)),
        ("Vacancy", _monthly(vacancy, rng, 0.15)),
        ("Concessions", _monthly(concessions, rng, 0.2)),
        ("Bad debt", _monthly(bad_debt, rng, 0.25)),
        ("Other income", _monthly(other_income, rng, 0.06)),
        ("Effective gross income", None),
    ]
    for name, per_unit in T12_PER_UNIT.items():
        lines.append((name, _monthly(-per_unit * UNITS, rng, 0.08)))
    lines.append(("Insurance", _monthly(-T12_INSURANCE_PER_UNIT * UNITS, rng, 0.0)))
    lines.append(("Real estate taxes", _monthly(-ASSESSED_VALUE_2025 * TAX_RATE, rng, 0.0)))
    lines.append(("Management fee", None))
    lines.append(("Total operating expenses", None))
    lines.append(("Net operating income", None))
    return lines


def write_t12(path: Path) -> None:
    lines = t12_lines()
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "T-12"
    ws["A1"] = "Sawyer Bend Apartments"
    ws["A1"].font = Font(bold=True, size=13)
    ws["A2"] = f"Trailing Twelve Month Operating Statement, {MONTHS[0]:%b %Y} to {MONTHS[-1]:%b %Y}"
    ws["A3"] = f"{UNITS} units. Actuals per the seller's general ledger; unaudited."
    ws.append([])
    ws.append(["Line", *[m.strftime("%b-%y") for m in MONTHS], "T-12 Total", "Per Unit"])
    for cell in ws[5]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="right")
    ws["A5"].alignment = Alignment(horizontal="left")
    row = 6
    row_of: dict[str, int] = {}
    for name, values in lines:
        row_of[name] = row
        if values is not None:
            ws.append([name, *values, f"=SUM(B{row}:M{row})", f"=N{row}/{UNITS}"])
        else:
            ws.append([name])
        row += 1
    letters = [get_column_letter(c) for c in range(2, 15)]

    def formula(target: str, parts: list[str], sign: str = "+") -> None:
        r = row_of[target]
        for col in letters:
            terms = sign.join(f"{col}{row_of[p]}" for p in parts)
            ws[f"{col}{r}"] = f"={terms}"
        ws[f"O{r}"] = f"=N{r}/{UNITS}"
        for col in [*letters, "O"]:
            ws[f"{col}{r}"].font = Font(bold=True)
        ws[f"A{r}"].font = Font(bold=True)

    revenue = [
        "Gross potential rent",
        "Loss to lease",
        "Vacancy",
        "Concessions",
        "Bad debt",
        "Other income",
    ]
    formula("Effective gross income", revenue)
    egi = row_of["Effective gross income"]
    mgmt = row_of["Management fee"]
    for col in letters:
        ws[f"{col}{mgmt}"] = f"=-0.03*{col}{egi}"
    ws[f"O{mgmt}"] = f"=N{mgmt}/{UNITS}"
    expenses = [*T12_PER_UNIT, "Insurance", "Real estate taxes", "Management fee"]
    formula("Total operating expenses", expenses)
    formula("Net operating income", ["Effective gross income", "Total operating expenses"])
    ws.column_dimensions["A"].width = 28
    for col in [*letters, "O"]:
        ws.column_dimensions[col].width = 11
    for r in ws.iter_rows(min_row=6, max_row=row - 1, min_col=2, max_col=15):
        for cell in r:
            cell.number_format = "#,##0;(#,##0)"
    ws.freeze_panes = "B6"
    wb.save(path)


def t12_totals() -> dict[str, float]:
    """Line totals as numbers, for the OM financial summary and the eval expectations."""
    totals = {name: sum(values) for name, values in t12_lines() if values is not None}
    revenue = [
        "Gross potential rent",
        "Loss to lease",
        "Vacancy",
        "Concessions",
        "Bad debt",
        "Other income",
    ]
    totals["Effective gross income"] = sum(totals[k] for k in revenue)
    totals["Management fee"] = -0.03 * totals["Effective gross income"]
    expenses = [*T12_PER_UNIT, "Insurance", "Real estate taxes", "Management fee"]
    totals["Total operating expenses"] = sum(totals[k] for k in expenses)
    totals["Net operating income"] = (
        totals["Effective gross income"] + totals["Total operating expenses"]
    )
    return totals


# --------------------------------------------------------------------------------------------
# Offering memorandum
# --------------------------------------------------------------------------------------------
class OM(FPDF):
    def header(self) -> None:
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 6, "Sawyer Bend Apartments  |  Offering Memorandum", align="L")
        self.cell(0, 6, BROKER, align="R", new_x="LMARGIN", new_y="NEXT")
        self.ln(4)
        self.set_text_color(0, 0, 0)

    def footer(self) -> None:
        self.set_y(-14)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 6, f"Page {self.page_no()}", align="C")
        self.set_text_color(0, 0, 0)

    def h1(self, text: str) -> None:
        self.set_font("Helvetica", "B", 16)
        self.cell(0, 10, text, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def h2(self, text: str) -> None:
        self.set_font("Helvetica", "B", 11)
        self.cell(0, 8, text, new_x="LMARGIN", new_y="NEXT")

    def para(self, text: str) -> None:
        self.set_font("Helvetica", "", 10)
        self.multi_cell(0, 5.2, text)
        self.ln(2)

    def kv(self, pairs: list[tuple[str, str]]) -> None:
        self.set_font("Helvetica", "", 10)
        for k, v in pairs:
            self.cell(70, 6.5, k)
            self.set_font("Helvetica", "B", 10)
            self.cell(0, 6.5, v, new_x="LMARGIN", new_y="NEXT")
            self.set_font("Helvetica", "", 10)
        self.ln(2)

    def table(self, headers: list[str], rows: list[list[str]], widths: list[int]) -> None:
        self.set_font("Helvetica", "B", 9)
        for h, w in zip(headers, widths, strict=True):
            self.cell(w, 7, h, border="B", align="L" if h == headers[0] else "R")
        self.ln()
        self.set_font("Helvetica", "", 9)
        for row in rows:
            bold = row[0].startswith(("Total", "Average", "Survey"))
            self.set_font("Helvetica", "B" if bold else "", 9)
            for i, (c, w) in enumerate(zip(row, widths, strict=True)):
                self.cell(w, 6.5, c, border="T" if bold else 0, align="L" if i == 0 else "R")
            self.ln()
        self.ln(4)


def money(v: float) -> str:
    return f"(${-v:,.0f})" if v < 0 else f"${v:,.0f}"


def rent_comps() -> list[list[str]]:
    comps = [
        ("The Reserve at Copper Creek", 2018, 312, 905, 1_545, "95.2%"),
        ("Willowmere Flats", 2015, 264, 880, 1_430, "93.8%"),
        ("Larkspur Commons", 2017, 336, 925, 1_560, "94.6%"),
        ("Bellwood Station", 2014, 240, 890, 1_425, "92.9%"),
        ("Ashford Park", 2019, 296, 940, 1_595, "95.8%"),
        ("Cedar Pointe", 2016, 272, 900, 1_490, "94.1%"),
        ("Northgate Crossing", 2013, 320, 870, 1_395, "93.3%"),
        ("Prairie Oaks", 2018, 248, 915, 1_648, "96.0%"),
    ]
    rows = [[n, str(y), str(u), f"{sf:,}", money(r), o] for n, y, u, sf, r, o in comps]
    avg_rent = sum(c[4] for c in comps) / len(comps)
    assert round(avg_rent) == 1_511, avg_rent
    rows.append(["Survey average (8 properties)", "2016", "286", "903", money(avg_rent), "94.5%"])
    return rows


def sale_comps() -> list[list[str]]:
    comps = [
        ("Larkspur Commons", "Mar 2026", 336, 61_200_000, "5.35%"),
        ("Cedar Pointe", "Jan 2026", 272, 46_500_000, "5.60%"),
        ("Bellwood Station", "Nov 2025", 240, 39_000_000, "5.70%"),
        ("Ashford Park", "Sep 2025", 296, 56_800_000, "5.30%"),
        ("Willowmere Flats", "Jun 2025", 264, 44_900_000, "5.55%"),
    ]
    rows = [[n, d, str(u), money(p), money(p / u), c] for n, d, u, p, c in comps]
    rows.append(["Average (5 sales)", "", "282", money(49_680_000), money(176_170), "5.50%"])
    return rows


def write_om(path: Path) -> None:
    totals = t12_totals()
    occupied = SEED.property.occupied
    in_place_avg = sum(fp.occupied * fp.in_place_rent for fp in PLANS) / occupied
    market_avg = sum(fp.units * fp.market_rent for fp in PLANS) / UNITS
    noi_t12 = totals["Net operating income"]
    pdf = OM(format="Letter")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(20, 18, 20)

    # 1 Cover
    pdf.add_page()
    pdf.ln(60)
    pdf.set_font("Helvetica", "B", 30)
    pdf.cell(0, 14, "SAWYER BEND APARTMENTS", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 13)
    pdf.cell(
        0,
        9,
        f"{UNITS}-Unit Value-Add Multifamily Community",
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.cell(0, 9, "Northwest Houston, Texas", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(30)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 9, "OFFERING MEMORANDUM", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(
        0, 8, f"Presented by {BROKER}  |  September 2026", align="C", new_x="LMARGIN", new_y="NEXT"
    )
    pdf.ln(50)
    pdf.set_font("Helvetica", "I", 8)
    pdf.multi_cell(
        0,
        4.5,
        "This is a synthetic document created for a software demonstration. The property, the "
        "figures, the comparables and the broker are invented. It is not an offer to sell.",
        align="C",
    )

    # 2 Executive summary
    pdf.add_page()
    pdf.h1("Executive Summary")
    pdf.para(
        f"{BROKER} is pleased to present Sawyer Bend Apartments, a {UNITS}-unit garden-style "
        f"community built in {SEED.property.year_built} in the Northwest Houston submarket. The "
        "property offers a value-add investor a proven interior renovation program with "
        f"{RENOVATED_UNITS} units completed and {UNITS - RENOVATED_UNITS} classic units remaining, "
        "in a submarket with steady employment growth and limited new supply."
    )
    pdf.h2("Offering terms")
    pdf.kv(
        [
            ("Asking price", money(ASK)),
            ("Price per unit", money(ASK / UNITS)),
            ("Price per square foot", f"${ASK / RENTABLE_SF:,.2f}"),
            ("T-12 net operating income", money(noi_t12)),
            ("T-12 cap rate at asking price", f"{noi_t12 / ASK:.2%}"),
            ("Broker pro forma cap rate", f"{(noi_t12 * 1.21) / ASK:.2%}"),
            ("Current occupancy", f"{occupied / UNITS:.1%} ({occupied} of {UNITS} units)"),
            ("Offers due", "October 15, 2026"),
        ]
    )
    pdf.h2("Investment highlights")
    pdf.para(
        f"Proven renovation premium: {RENOVATED_UNITS} renovated units are achieving an average "
        f"premium of ${RENOVATION_PREMIUM:,.0f} per month over classic units of the same "
        "floor plan."
    )
    pdf.para(
        f"Loss to lease: in-place rents average ${in_place_avg:,.0f} against a surveyed market "
        f"average of ${market_avg:,.0f}, a gap of ${market_avg - in_place_avg:,.0f} per unit "
        "per month before renovation."
    )
    pdf.para(
        "Assumable agency financing is not available; the property is offered free and clear. "
        "Buyers should arrange their own debt."
    )

    # 3 Property summary
    pdf.add_page()
    pdf.h1("Property Summary")
    pdf.kv(
        [
            ("Address", "14200 Sawyer Bend Drive, Houston, Texas 77064"),
            ("Units", str(UNITS)),
            ("Year built", str(SEED.property.year_built)),
            ("Rentable square feet", f"{RENTABLE_SF:,.0f}"),
            ("Average unit size", f"{RENTABLE_SF / UNITS:,.0f} SF"),
            ("Site", "12.6 acres, 22.9 units per acre"),
            ("Buildings", "12 three-story residential buildings and a clubhouse"),
            ("Parking", "486 surface spaces and 48 detached garages"),
            (
                "Construction",
                "Wood frame, brick and cementitious siding, pitched composition roofs",
            ),
        ]
    )
    pdf.h2("Unit mix")
    rows = []
    for fp in PLANS:
        rows.append(
            [
                f"{fp.code}  {fp.unit_type.replace(' x ', ' BR / ')} BA",
                str(fp.units),
                f"{fp.sf:,.0f}",
                f"{fp.units * fp.sf:,.0f}",
                str(fp.occupied),
                money(fp.in_place_rent),
                money(fp.market_rent),
            ]
        )
    rows.append(
        [
            "Total / weighted average",
            str(UNITS),
            f"{RENTABLE_SF / UNITS:,.0f}",
            f"{RENTABLE_SF:,.0f}",
            str(occupied),
            money(in_place_avg),
            money(market_avg),
        ]
    )
    pdf.table(
        ["Floor plan", "Units", "Avg SF", "Total SF", "Occupied", "In-place rent", "Market rent"],
        rows,
        [52, 16, 18, 22, 20, 24, 24],
    )
    pdf.para(
        f"In-place rents are the average lease rent of occupied units per the rent roll dated "
        f"{AS_OF:%B %d, %Y}. Market rents are the broker's estimate for an unrenovated unit, "
        "supported by the rent survey on page 5."
    )

    # 4 Value-add
    pdf.add_page()
    pdf.h1("Value-Add Opportunity")
    pdf.para(
        f"The seller renovated {RENOVATED_UNITS} units between 2024 and 2026 with quartz counters, "
        "wood-style plank flooring, stainless appliances, two-inch blinds, upgraded lighting and "
        f"hardware. Renovated units are achieving an average premium of ${RENOVATION_PREMIUM:,.0f} "
        f"per month over classic units, and renovated units leased in an average of 11 days."
    )
    pdf.para(
        f"A buyer may continue the program across the remaining {UNITS - RENOVATED_UNITS} classic "
        "units. The seller's interior scope is available in the data room; buyers should obtain "
        "their own contractor pricing."
    )
    pdf.h2("Exterior and common area")
    pdf.para(
        "The clubhouse, fitness center and pool were refreshed in 2023. Roofs are original (2016) "
        "and in serviceable condition per the seller; a property condition report is available "
        "in the data room. Buyers should budget their own exterior and deferred maintenance "
        "program."
    )

    # 5 Rent survey
    pdf.add_page()
    pdf.h1("Market Rent Survey")
    pdf.para(
        "Eight competing communities within three miles, built 2013 to 2019, surveyed in August "
        "2026. Rents are asking rents for unrenovated units, averaged across floor plans."
    )
    pdf.table(
        ["Property", "Built", "Units", "Avg SF", "Avg rent", "Occupancy"],
        rent_comps(),
        [64, 16, 18, 20, 26, 24],
    )
    pdf.para(
        f"Survey average asking rent: ${market_avg:,.0f} per unit per month. Sawyer Bend's "
        f"in-place average of ${in_place_avg:,.0f} sits {1 - in_place_avg / market_avg:.1%} "
        "below the survey."
    )

    # 6 Sale comps
    pdf.add_page()
    pdf.h1("Sale Comparables")
    pdf.para(
        "Five sales of 2013 to 2019 vintage garden communities in Northwest Houston, "
        "June 2025 to March 2026."
    )
    pdf.table(
        ["Property", "Sale date", "Units", "Price", "Price / unit", "Cap rate"],
        sale_comps(),
        [58, 22, 16, 30, 26, 20],
    )
    pdf.para("Average cap rate across the five sales: 5.50% on trailing net operating income.")

    # 7 Financial summary
    pdf.add_page()
    pdf.h1("Financial Summary")
    pdf.para(
        f"Trailing twelve months {MONTHS[0]:%B %Y} through {MONTHS[-1]:%B %Y} per the seller's "
        "general ledger, and the broker's year 1 pro forma."
    )
    pro_forma_scale = {
        "Gross potential rent": 1.06,
        "Loss to lease": 0.4,
        "Vacancy": 0.85,
        "Concessions": 0.8,
        "Bad debt": 0.8,
        "Other income": 1.08,
        "Insurance": 1.0,
        "Real estate taxes": 1.0,
    }
    rows = []
    order = [
        "Gross potential rent",
        "Loss to lease",
        "Vacancy",
        "Concessions",
        "Bad debt",
        "Other income",
        "Effective gross income",
        *T12_PER_UNIT,
        "Insurance",
        "Real estate taxes",
        "Management fee",
        "Total operating expenses",
        "Net operating income",
    ]
    pf: dict[str, float] = {}
    for name in order:
        if name in pro_forma_scale:
            pf[name] = totals[name] * pro_forma_scale[name]
        elif name in T12_PER_UNIT:
            pf[name] = totals[name] * 1.03
    pf["Effective gross income"] = sum(pf[k] for k in order[:6])
    pf["Management fee"] = -0.03 * pf["Effective gross income"]
    pf["Total operating expenses"] = sum(
        pf[k] for k in [*T12_PER_UNIT, "Insurance", "Real estate taxes", "Management fee"]
    )
    pf["Net operating income"] = pf["Effective gross income"] + pf["Total operating expenses"]
    for name in order:
        rows.append([name, money(totals[name]), money(totals[name] / UNITS), money(pf[name])])
    pdf.table(["Line", "T-12 actual", "Per unit", "Broker pro forma"], rows, [70, 34, 30, 38])
    pdf.para(
        f"Real estate taxes reflect the 2025 assessed value of {money(ASSESSED_VALUE_2025)} at the "
        f"combined 2025 tax rate of {TAX_RATE:.4%}. Insurance is the seller's blended portfolio "
        "premium. The broker pro forma does not reassess taxes on sale."
    )
    pdf.output(str(path))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    write_rent_roll(OUT / "sawyer-bend-rent-roll.xlsx")
    write_t12(OUT / "sawyer-bend-t12.xlsx")
    write_om(OUT / "sawyer-bend-om.pdf")
    for p in sorted(OUT.iterdir()):
        print(f"wrote {p.relative_to(ROOT)} ({p.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
