"""Public data sources for the market context panels: FRED, Census building permits, Zillow rents.

Every fetch goes through one client with a short timeout and a day-long in-process cache. When a
source is unreachable or a key is missing, the caller falls back to the recorded snapshot in
data/benchmarks/recorded.json and says so on the page. Tests use the snapshot only.

Keys: FRED_API_KEY (the official API; without it the public CSV endpoint is used, which needs
no key but is undocumented). Census permit files and the Zillow index need no key.
"""

from __future__ import annotations

import csv
import datetime
import io
import json
import os
import re
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[2]
RECORDED = ROOT / "data" / "benchmarks" / "recorded.json"
TIMEOUT = 6.0
TTL_SECONDS = 24 * 3600

FRED_SERIES: dict[str, tuple[str, str]] = {
    # id: (label, unit)
    "DGS10": ("10-year Treasury", "%"),
    "SOFR": ("SOFR", "%"),
    "MORTGAGE30US": ("30-year mortgage rate", "%"),
    "CUSR0000SEHA": ("CPI, rent of primary residence", "index"),
    "HOUS448NA": ("Houston MSA nonfarm employment", "thousands"),
    "PERMIT5": ("US permits, 5+ units", "thousands, annual rate"),
}
ZILLOW_METRO_CSV = "https://files.zillowstatic.com/research/public_csvs/zori/Metro_zori_uc_sfrcondomfr_sm_month.csv"
CENSUS_COUNTY = "https://www2.census.gov/econ/bps/County/"


class Series(BaseModel):
    """Dated observations, oldest first."""

    series_id: str
    label: str
    unit: str
    dates: list[datetime.date]
    values: list[float]
    source_url: str

    @property
    def latest(self) -> tuple[datetime.date, float]:
        return self.dates[-1], self.values[-1]

    def value_on_or_before(self, day: datetime.date) -> float | None:
        best: float | None = None
        for d, v in zip(self.dates, self.values, strict=True):
            if d <= day:
                best = v
            else:
                break
        return best

    def year_over_year(self) -> float | None:
        """Change against the observation a year before the latest one, as a fraction."""
        last_date, last = self.latest
        prior = self.value_on_or_before(last_date - datetime.timedelta(days=365))
        if prior in (None, 0):
            return None
        return last / prior - 1

    def change_points(self) -> float | None:
        """Change in level against a year earlier, for rates."""
        last_date, last = self.latest
        prior = self.value_on_or_before(last_date - datetime.timedelta(days=365))
        return None if prior is None else last - prior


class Permits(BaseModel):
    county: str
    unit_class: str  # "1-unit" or "5+ units"
    trailing_12: int
    prior_12: int
    through: str  # "July 2026"
    source_url: str


class RentIndex(BaseModel):
    region: str
    as_of: datetime.date
    level: float
    year_over_year: float | None
    source_url: str


class SourceError(RuntimeError):
    pass


# --------------------------------------------------------------------------------------------
# Cache and HTTP
# --------------------------------------------------------------------------------------------
_cache: dict[str, tuple[float, Any]] = {}


def cached(key: str, load: Callable[[], Any]) -> Any:
    now = time.time()
    hit = _cache.get(key)
    if hit and now - hit[0] < TTL_SECONDS:
        return hit[1]
    value = load()
    _cache[key] = (now, value)
    return value


def clear_cache() -> None:
    _cache.clear()


def _get(url: str, params: dict[str, str] | None = None) -> str:
    try:
        with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            return response.text
    except httpx.HTTPError as exc:
        raise SourceError(f"{url}: {exc}") from exc


# --------------------------------------------------------------------------------------------
# FRED
# --------------------------------------------------------------------------------------------
def fred_series(series_id: str, key: str | None = None, years: int = 3) -> Series:
    label, unit = FRED_SERIES.get(series_id, (series_id, ""))
    start = (datetime.date.today() - datetime.timedelta(days=365 * years)).isoformat()
    key = key or os.environ.get("FRED_API_KEY")
    if key:
        text = _get(
            "https://api.stlouisfed.org/fred/series/observations",
            {
                "series_id": series_id,
                "api_key": key,
                "file_type": "json",
                "observation_start": start,
            },
        )
        rows = [(o["date"], o["value"]) for o in json.loads(text).get("observations", [])]
    else:
        text = _get("https://fred.stlouisfed.org/graph/fredgraph.csv", {"id": series_id})
        reader = csv.reader(io.StringIO(text))
        next(reader, None)
        rows = [(r[0], r[1]) for r in reader if len(r) >= 2 and r[0] >= start]
    dates: list[datetime.date] = []
    values: list[float] = []
    for d, v in rows:
        try:
            values.append(float(v))
        except ValueError:
            continue  # FRED marks missing days with "."
        dates.append(datetime.date.fromisoformat(d))
    if not values:
        raise SourceError(f"FRED {series_id}: no observations")
    return Series(
        series_id=series_id,
        label=label,
        unit=unit,
        dates=dates,
        values=values,
        source_url=f"https://fred.stlouisfed.org/series/{series_id}",
    )


# --------------------------------------------------------------------------------------------
# Census Building Permits Survey, county files
# --------------------------------------------------------------------------------------------
_UNIT_COLUMNS = {"1-unit": 7, "5+ units": 16}  # "Units" column for each class, 0-based


def _bps_row(text: str, state: str, county: str) -> list[str] | None:
    for line in text.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) > 17 and parts[1] == state and parts[2] == county:
            return parts
    return None


def census_county_permits(
    state: str, county: str, unit_class: str, today: datetime.date | None = None
) -> Permits:
    """Trailing twelve months of permitted units: this year to date, plus last year's annual,
    less last year's same-month year to date. The latest monthly file is found by walking back
    from last month, since the survey publishes about six weeks after the month."""
    today = today or datetime.date.today()
    col = _UNIT_COLUMNS[unit_class]
    month = today.replace(day=1)
    ytd_text = ytd_row = None
    for _ in range(8):
        month = (month - datetime.timedelta(days=1)).replace(day=1)
        url = f"{CENSUS_COUNTY}co{month:%y%m}y.txt"
        try:
            ytd_text = _get(url)
        except SourceError:
            continue
        ytd_row = _bps_row(ytd_text, state, county)
        if ytd_row:
            break
    if not ytd_row:
        raise SourceError(f"Census permits: no year-to-date file found for {state}{county}")
    prior_year = month.year - 1
    annual_row = _bps_row(_get(f"{CENSUS_COUNTY}co{prior_year}a.txt"), state, county)
    prior_ytd_row = _bps_row(
        _get(f"{CENSUS_COUNTY}co{prior_year % 100:02d}{month.month:02d}y.txt"), state, county
    )
    if not annual_row or not prior_ytd_row:
        raise SourceError(f"Census permits: prior-year files missing for {state}{county}")
    ytd, annual, prior_ytd = int(ytd_row[col]), int(annual_row[col]), int(prior_ytd_row[col])
    prior_annual_row = _bps_row(_get(f"{CENSUS_COUNTY}co{prior_year - 1}a.txt"), state, county)
    prior_prior_ytd_row = _bps_row(
        _get(f"{CENSUS_COUNTY}co{(prior_year - 1) % 100:02d}{month.month:02d}y.txt"),
        state,
        county,
    )
    prior_12 = 0
    if prior_annual_row and prior_prior_ytd_row:
        prior_12 = prior_ytd + int(prior_annual_row[col]) - int(prior_prior_ytd_row[col])
    name = re.sub(r"\s+", " ", ytd_row[5]).strip()
    return Permits(
        county=name,
        unit_class=unit_class,
        trailing_12=ytd + annual - prior_ytd,
        prior_12=prior_12,
        through=month.strftime("%B %Y"),
        source_url="https://www.census.gov/construction/bps/",
    )


# --------------------------------------------------------------------------------------------
# Zillow Observed Rent Index, metro level
# --------------------------------------------------------------------------------------------
def zillow_rent_index(region: str = "Houston, TX") -> RentIndex:
    text = _get(ZILLOW_METRO_CSV)
    reader = csv.reader(io.StringIO(text))
    header = next(reader)
    for row in reader:
        if len(row) > 5 and row[2] == region:
            points = [(d, v) for d, v in zip(header[5:], row[5:], strict=True) if v]
            if not points:
                break
            as_of = datetime.date.fromisoformat(points[-1][0])
            level = float(points[-1][1])
            prior = next(
                (
                    float(v)
                    for d, v in reversed(points)
                    if datetime.date.fromisoformat(d) <= as_of - datetime.timedelta(days=364)
                ),
                None,
            )
            return RentIndex(
                region=region,
                as_of=as_of,
                level=level,
                year_over_year=(level / prior - 1) if prior else None,
                source_url="https://www.zillow.com/research/data/",
            )
    raise SourceError(f"Zillow ZORI: region {region!r} not found")


# --------------------------------------------------------------------------------------------
# Recorded snapshot
# --------------------------------------------------------------------------------------------
class Snapshot(BaseModel):
    recorded: datetime.date
    fred: dict[str, Series]
    permits: dict[str, Permits]
    rents: dict[str, RentIndex]


def load_snapshot(path: Path = RECORDED) -> Snapshot:
    return Snapshot.model_validate_json(path.read_text(encoding="utf-8"))


def save_snapshot(snapshot: Snapshot, path: Path = RECORDED) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(snapshot.model_dump_json(indent=1), encoding="utf-8", newline="\n")
