"""Market context: public figures beside the assumptions they test, with a plain flag.

Each row names a public figure, its date and source, the underwritten figure it bears on, and
one of three flags: "ok", "watch" (the assumption sits outside the range the public figure
suggests) or "info" (context with no direct assumption). The rules are simple and stated in the
note so a reader can disagree with them.
"""

from __future__ import annotations

import datetime
import logging
from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel

from core.benchmarks.sources import (
    Permits,
    RentIndex,
    Series,
    Snapshot,
    SourceError,
    cached,
    census_county_permits,
    fred_series,
    load_snapshot,
    zillow_rent_index,
)
from core.copilot.inputs import CopilotInputs
from core.copilot.summary import CopilotOutputs
from core.underwriting.inputs import DealInputs
from core.underwriting.summary import Outputs

log = logging.getLogger(__name__)

Flag = Literal["ok", "watch", "info"]

# Where the two synthetic deals sit, for the county and metro series.
HOUSTON_MSA = "Houston, TX"
HARRIS = ("48", "201")
WALLER = ("48", "473")

# Agency multifamily debt has priced between roughly 125 and 300 bps over the 10-year.
LOAN_SPREAD_LOW, LOAN_SPREAD_HIGH = 0.0125, 0.0325
# Cap rates below the 10-year plus this spread leave little room for rates to rise.
EXIT_CAP_SPREAD_MIN = 0.0075
# Rent growth this far above measured rent inflation is a bet, not a base case.
RENT_GROWTH_HEADROOM = 0.015


class Row(BaseModel):
    topic: str
    public: str
    as_of: str
    source: str
    source_url: str
    underwritten: str
    flag: Flag
    note: str


class MarketContext(BaseModel):
    rows: list[Row]
    live: bool  # False when every row came from the recorded snapshot
    recorded: datetime.date | None
    problems: list[str]


def _pct(v: float | None, d: int = 1) -> str:
    return "n/a" if v is None else f"{v * 100:.{d}f}%"


def _pts(v: float | None) -> str:
    return "n/a" if v is None else f"{v * 100:+.2f} pts"


def _scaled(points: float | None) -> float | None:
    """Percentage points from FRED (4.96 means 4.96%) as a fraction, or None."""
    return None if points is None else points / 100


class Sources:
    """Live sources with the snapshot as fallback. `offline=True` uses the snapshot only."""

    def __init__(self, offline: bool = False) -> None:
        self.offline = offline
        self.problems: list[str] = []
        self.used_snapshot = False
        self._snapshot: Snapshot | None = None

    @property
    def snapshot(self) -> Snapshot:
        if self._snapshot is None:
            self._snapshot = load_snapshot()
        return self._snapshot

    def _live_or_recorded(
        self, key: str, live: Callable[[], Any], recorded: Callable[[], Any]
    ) -> Any:
        if not self.offline:
            try:
                return cached(key, live)
            except (SourceError, ValueError, KeyError) as exc:
                log.warning("benchmark source failed, using snapshot: %s", exc)
                self.problems.append(str(exc)[:160])
        self.used_snapshot = True
        return recorded()

    def fred(self, series_id: str) -> Series:
        return self._live_or_recorded(  # type: ignore[no-any-return]
            f"fred:{series_id}",
            lambda: fred_series(series_id),
            lambda: self.snapshot.fred[series_id],
        )

    def permits(self, state: str, county: str, unit_class: str) -> Permits:
        key = f"permits:{state}{county}:{unit_class}"
        return self._live_or_recorded(  # type: ignore[no-any-return]
            key,
            lambda: census_county_permits(state, county, unit_class),
            lambda: self.snapshot.permits[key],
        )

    def rents(self, region: str) -> RentIndex:
        return self._live_or_recorded(  # type: ignore[no-any-return]
            f"zori:{region}",
            lambda: zillow_rent_index(region),
            lambda: self.snapshot.rents[region],
        )


def _as_of(series: Series) -> str:
    return series.latest[0].strftime("%b %d, %Y")


def multifamily_context(
    inputs: CopilotInputs, out: CopilotOutputs, sources: Sources | None = None
) -> MarketContext:
    src = sources or Sources()
    rows: list[Row] = []

    def add(row: Row | None) -> None:
        if row:
            rows.append(row)

    def guard(build: Callable[[], Row]) -> Row | None:
        try:
            return build()
        except (KeyError, SourceError, ValueError, IndexError) as exc:
            src.problems.append(str(exc)[:160])
            return None

    def loan_rate() -> Row:
        t10 = src.fred("DGS10")
        sofr = src.fred("SOFR")
        rate = inputs.loan.rate
        spread = rate - t10.latest[1] / 100
        flag: Flag = "ok" if LOAN_SPREAD_LOW <= spread <= LOAN_SPREAD_HIGH else "watch"
        return Row(
            topic="Loan rate against the curve",
            public=f"10-year {t10.latest[1]:.2f}% · SOFR {sofr.latest[1]:.2f}%",
            as_of=_as_of(t10),
            source="FRED",
            source_url=t10.source_url,
            underwritten=f"{_pct(rate, 2)} fixed",
            flag=flag,
            note=(
                f"Spread of {spread * 10_000:.0f} bps over the 10-year; agency debt has priced "
                f"between {LOAN_SPREAD_LOW * 10_000:.0f} and {LOAN_SPREAD_HIGH * 10_000:.0f} bps."
            ),
        )

    def rent_growth() -> Row:
        cpi = src.fred("CUSR0000SEHA")
        yoy = cpi.year_over_year()
        growth = inputs.revenue.market_rent_growth
        flag: Flag = "watch" if yoy is not None and growth > yoy + RENT_GROWTH_HEADROOM else "ok"
        return Row(
            topic="Market rent growth",
            public=f"CPI rent {_pct(yoy)} over twelve months",
            as_of=_as_of(cpi),
            source="FRED (BLS)",
            source_url=cpi.source_url,
            underwritten=f"{_pct(growth)} per year",
            flag=flag,
            note=(
                "National rent inflation; the assumption is flagged when it runs more than "
                f"{RENT_GROWTH_HEADROOM * 100:.1f} points above it."
            ),
        )

    def local_rents() -> Row:
        zori = src.rents(HOUSTON_MSA)
        growth = inputs.revenue.market_rent_growth
        yoy = zori.year_over_year
        flag: Flag = "watch" if yoy is not None and growth > yoy + RENT_GROWTH_HEADROOM else "ok"
        return Row(
            topic="Houston asking rents",
            public=f"ZORI ${zori.level:,.0f} · {_pct(yoy)} over twelve months",
            as_of=zori.as_of.strftime("%b %Y"),
            source="Zillow Research",
            source_url=zori.source_url,
            underwritten=(
                f"{_pct(growth)} per year · market ${out.summary.avg_market_rent:,} / unit"
            ),
            flag=flag,
            note="Metro-wide observed asking rent index for all property types.",
        )

    def exit_cap() -> Row:
        t10 = src.fred("DGS10")
        cap = inputs.exit.cap_rate
        spread = cap - t10.latest[1] / 100
        flag: Flag = "ok" if spread >= EXIT_CAP_SPREAD_MIN else "watch"
        return Row(
            topic="Exit cap against the 10-year",
            public=(
                f"10-year {t10.latest[1]:.2f}% · {_pts(_scaled(t10.change_points()))} "
                "over twelve months"
            ),
            as_of=_as_of(t10),
            source="FRED",
            source_url=t10.source_url,
            underwritten=f"{_pct(cap, 2)} exit cap · {_pct(out.summary.going_in_cap, 2)} going in",
            flag=flag,
            note=f"Exit cap sits {spread * 10_000:.0f} bps over today's 10-year.",
        )

    def employment() -> Row:
        emp = src.fred("HOUS448NA")
        yoy = emp.year_over_year()
        flag: Flag = "watch" if yoy is not None and yoy < 0 else "info"
        return Row(
            topic="Houston employment",
            public=f"{emp.latest[1]:,.0f}k jobs · {_pct(yoy)} over twelve months",
            as_of=_as_of(emp),
            source="FRED (BLS)",
            source_url=emp.source_url,
            underwritten=f"{_pct(inputs.revenue.vacancy)} stabilized vacancy",
            flag=flag,
            note="Nonfarm payrolls for the Houston MSA, not seasonally adjusted.",
        )

    def supply() -> Row:
        p = src.permits(*HARRIS, "5+ units")
        change = (p.trailing_12 / p.prior_12 - 1) if p.prior_12 else None
        flag: Flag = "watch" if change is not None and change > 0.25 else "info"
        return Row(
            topic="Multifamily supply, Harris County",
            public=(
                f"{p.trailing_12:,} units permitted in 5+ unit buildings, trailing twelve months"
            ),
            as_of=f"through {p.through}",
            source="Census Building Permits Survey",
            source_url=p.source_url,
            underwritten=f"{out.summary.units} units · {_pct(inputs.revenue.vacancy)} vacancy",
            flag=flag,
            note=f"Prior twelve months {p.prior_12:,} ({_pct(change)} change)."
            if p.prior_12
            else "Prior period unavailable.",
        )

    for build in (loan_rate, rent_growth, local_rents, exit_cap, employment, supply):
        add(guard(build))
    return MarketContext(
        rows=rows,
        live=not src.used_snapshot,
        recorded=src.snapshot.recorded if src.used_snapshot else None,
        problems=src.problems,
    )


def land_context(inputs: DealInputs, out: Outputs, sources: Sources | None = None) -> MarketContext:
    src = sources or Sources()
    rows: list[Row] = []

    def guard(build: Callable[[], Row]) -> None:
        try:
            rows.append(build())
        except (KeyError, SourceError, ValueError, IndexError) as exc:
            src.problems.append(str(exc)[:160])

    def mortgage() -> Row:
        m = src.fred("MORTGAGE30US")
        change = m.change_points()
        flag: Flag = "watch" if change is not None and change > 0.5 else "info"
        return Row(
            topic="Mortgage rates",
            public=f"30-year fixed {m.latest[1]:.2f}% · {_pts(_scaled(change))} over twelve months",
            as_of=_as_of(m),
            source="FRED (Freddie Mac)",
            source_url=m.source_url,
            underwritten=f"{out.summary.home_sales_per_year:,} lots per year",
            flag=flag,
            note="Rising mortgage rates slow lot absorption; the pace assumption bears the risk.",
        )

    def permits() -> Row:
        p = src.permits(*WALLER, "1-unit")
        share = out.summary.home_sales_per_year / p.trailing_12 if p.trailing_12 else None
        flag: Flag = "watch" if share is not None and share > 0.5 else "ok"
        return Row(
            topic="Single-family permits, Waller County",
            public=f"{p.trailing_12:,} single-family units permitted, trailing twelve months",
            as_of=f"through {p.through}",
            source="Census Building Permits Survey",
            source_url=p.source_url,
            underwritten=f"{out.summary.home_sales_per_year:,} lots per year",
            flag=flag,
            note=(
                f"The project would take {_pct(share, 0)} of the county's current permitting pace."
                if share is not None
                else "County pace unavailable."
            ),
        )

    def employment() -> Row:
        emp = src.fred("HOUS448NA")
        yoy = emp.year_over_year()
        flag: Flag = "watch" if yoy is not None and yoy < 0 else "info"
        return Row(
            topic="Houston employment",
            public=f"{emp.latest[1]:,.0f}k jobs · {_pct(yoy)} over twelve months",
            as_of=_as_of(emp),
            source="FRED (BLS)",
            source_url=emp.source_url,
            underwritten=(
                f"{out.summary.total_lots:,} lots over {out.summary.project_length_years:.1f} years"
            ),
            flag=flag,
            note="Nonfarm payrolls for the Houston MSA, not seasonally adjusted.",
        )

    def rates() -> Row:
        t10 = src.fred("DGS10")
        irr = out.summary.unlevered_irr or 0
        flag: Flag = "info"
        return Row(
            topic="Return against the risk-free rate",
            public=f"10-year Treasury {t10.latest[1]:.2f}%",
            as_of=_as_of(t10),
            source="FRED",
            source_url=t10.source_url,
            underwritten=f"{_pct(irr)} unlevered IRR",
            flag=flag,
            note=(
                f"Unlevered return of {(irr - t10.latest[1] / 100) * 100:.0f} bps over the "
                "10-year for land development risk."
            ),
        )

    for build in (mortgage, permits, employment, rates):
        guard(build)
    return MarketContext(
        rows=rows,
        live=not src.used_snapshot,
        recorded=src.snapshot.recorded if src.used_snapshot else None,
        problems=src.problems,
    )
