"""Record a snapshot of the public benchmark sources into data/benchmarks/recorded.json.

The snapshot is the test fixture and the fallback the pages use when a source is down or a key
is missing. Run it when the figures should be refreshed:

    python scripts/record_benchmarks.py

Uses FRED_API_KEY when set; otherwise the public FRED CSV endpoint.
"""

from __future__ import annotations

import datetime
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.benchmarks.context import HARRIS, HOUSTON_MSA, WALLER  # noqa: E402
from core.benchmarks.sources import (  # noqa: E402
    FRED_SERIES,
    RECORDED,
    Snapshot,
    census_county_permits,
    fred_series,
    save_snapshot,
    zillow_rent_index,
)


def main() -> int:
    fred = {}
    for series_id in FRED_SERIES:
        fred[series_id] = fred_series(series_id)
        d, v = fred[series_id].latest
        print(f"{series_id:<14} {d} {v:,.2f}  ({len(fred[series_id].values)} obs)")
    permits = {}
    for (state, county), unit_class in ((HARRIS, "5+ units"), (WALLER, "1-unit")):
        p = census_county_permits(state, county, unit_class)
        permits[f"permits:{state}{county}:{unit_class}"] = p
        print(
            f"{p.county} {unit_class}: {p.trailing_12:,} trailing twelve months through "
            f"{p.through} (prior {p.prior_12:,})"
        )
    rents = {HOUSTON_MSA: zillow_rent_index(HOUSTON_MSA)}
    z = rents[HOUSTON_MSA]
    print(f"ZORI {z.region}: {z.level:,.0f} as of {z.as_of}, {z.year_over_year}")
    save_snapshot(Snapshot(recorded=datetime.date.today(), fred=fred, permits=permits, rents=rents))
    print(f"wrote {RECORDED.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
