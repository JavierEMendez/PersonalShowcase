# Market context: public data beside the assumptions

Both tools show a Market context panel: a public figure, its date and source, the underwritten
figure it bears on, and a flag. "In range" means the assumption sits where the public figure
suggests; "Watch" means it does not, by the rule stated in the row's note; "Context" means there
is no direct assumption to test. See `core/benchmarks/`.

## Sources

| Source | Series | Feeds | Key |
|---|---|---|---|
| FRED | 10-year Treasury (DGS10), SOFR, 30-year mortgage (MORTGAGE30US), CPI rent of primary residence (CUSR0000SEHA), Houston MSA nonfarm employment (HOUS448NA), US 5+ unit permits (PERMIT5) | Loan rate spread, exit cap spread, rent growth, demand, mortgage rate context | `FRED_API_KEY`; without it the public CSV endpoint is used |
| Census Building Permits Survey | County files (`co{yymm}y.txt`, `co{yyyy}a.txt`): Harris County 5+ units, Waller County 1-unit | Local supply for the multifamily deal; county absorption pace for the land deal | none |
| Zillow Research | Observed Rent Index, Houston MSA, metro CSV | Local asking-rent trend against the rent growth assumption | none |

Trailing twelve months of permits is this year to date plus last year's annual less last year's
same-month year to date; the survey publishes about six weeks after the month, so the loader
walks back from last month to the latest file.

## Rules behind the flags

- Loan rate: at least 150 bps over SOFR, the house guideline; flagged when the underwritten rate sits below SOFR plus 150 bps.
- Exit cap: at least 75 bps over today's 10-year.
- Rent growth: no more than 1.5 points above CPI rent inflation or the Houston rent index.
- Supply: trailing permits more than 25% above the prior twelve months.
- Land pace: the project taking more than half the county's current single-family permitting.
- Employment: negative year-over-year.

## Refresh, cache and fallback

Live figures are fetched at request time with a six-second timeout and cached in memory for a
day. When a source fails or a key is missing, the row comes from `data/benchmarks/recorded.json`
and the panel says so with the recording date. Refresh the snapshot with
`python scripts/record_benchmarks.py`. Tests use the snapshot only and never touch the network.

## Not included, and why

Cap rate and vacancy comps by submarket live in paid databases (CoStar, RealPage, RCA); the
public proxy is the cap rate spread over the 10-year. Appraisal district assessed values and tax
rates are public but not an API; the tax rate stays an input with a link. Insurance has no public
source. HUD Fair Market Rents by ZIP would add a per-bedroom rent benchmark and need a free HUD
User token; deferred until the token is set.
