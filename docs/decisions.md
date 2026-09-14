# Decisions

Dated entries. One paragraph each: what, why, what was rejected. Newest at the bottom.

## 2026-09-14 · Two products, one site
Showcase two things under one domain: the existing MPC Underwriting tool (ported from an internal tool) and a new Deal-to-Portfolio Copilot. One product alone covered too few of the target roles; the pair covers credit, M&A operations, business modeling, and CRE strategy. Rejected: a narrower Houston MPC land market model, and a portfolio monitoring tool on its own.

## 2026-09-14 · One Railway app, one domain
Landing page and both tools live in a single FastAPI app with routes /underwriting and /copilot. One link to send, one codebase to maintain. Rejected: a static landing page linking to separately hosted apps.

## 2026-09-14 · Synthetic deals with public market data
Demos run on invented deals (Cypress Ridge, Harbor Point Industrial) with realistic Houston-area figures and public data sources. Nothing from the internal book, no employer branding or template files. Rejected: anonymized internal deals (needs sign-off) and SEC-filings-only deals (weak tie to MPC land).

## 2026-09-14 · Describe the MPC tool as an unlevered model
The internal tool's documentation claims debt terms and equity multiple; its engine has neither. The showcase describes the tool accurately: unlevered XIRR, gross and net margin, per-acre and per-lot metrics. Adding a financing layer to the MPC tool is deferred.

## 2026-09-14 · Design standard locked from mockups
Executive, bank-style standard: warm near-white ground, charcoal ink, navy accent, Source Serif 4 and IBM Plex Sans, tabular numerals, 2px radii, no shadows or gradients, eight-figure summary strip on every tool screen. Rejected: reusing the employer theme (employer branding on a personal showcase) and Inter (overused).

## 2026-09-14 · Wordmark
"Javier Mendez Valdez" with a small headshot at the top left of every page, confirmed by Javi. Superseded the working wordmark "Mendez Valdez".

## 2026-09-14 · Harbor Point priced as a bid below ask
The Copilot sample deal recommends a $38.0M bid against a $41.6M ask, because at the ask the levered IRR is 4.9% against a 12% threshold. Shows the tool producing a pricing decision rather than confirming the seller's number. Rejected: a deal that simply clears the hurdle at the ask.

## 2026-09-14 · Fixed 1440px page width
Pages render at the 1440px design width on every device (viewport meta set to 1440, page container 1440px centered) instead of a responsive layout. The reader is a partner on a laptop; on a phone the page scales down and reads like the PNG render rather than reflowing dense tables into a single column. Rejected: a responsive grid, which would need a second layout for every table and panel.

## 2026-09-14 · Contact email from the environment
The About section shows an email row only when the CONTACT_EMAIL environment variable is set on Railway. Keeps a personal address out of the public repository and lets it change without a commit. Rejected: hardcoding the address in the template.

## 2026-09-14 · Docker build on Railway
Railway builds from the repository Dockerfile (python:3.12-slim, pinned requirements.txt) with a /health check, rather than Nixpacks autodetection. The build is reproducible and the same image runs locally. Rejected: Nixpacks, which picks the Python version and start command implicitly.

## 2026-09-14 · Engine ported and reconciled; Cypress Ridge figures now come from the port
`core/underwriting/` is a module-by-module port of the internal land model, with typed pydantic inputs and the calculation order preserved. On the Cypress Ridge inputs it reproduces the internal engine to the dollar on every summary line, every monthly cash flow row, and the XIRR to ten decimals, for all three scenarios. The reference outputs are frozen in `tests/fixtures/cypress_ridge.json`. Inputs the deals document left open were set as model defaults or realistic Houston figures; section development cost was calibrated to $1,020 per front foot ($580 water, sewer and drainage, $440 paving) so the deal lands near the intended return. The port's headline figures replace the hand-built mockup figures: unlevered IRR 17.4% (mockup 18.4%), total revenue $379.1M (412.6), gross costs $291.7M (318.4), gross margin $87.4M or 23.1% of revenue (94.2M, 22.8%), net margin $72.5M (71.5M), 2,380 lots (2,412), 101 months (134), peak cash need $87.1M in month 37 (92.2M, month 34), breakeven in year 6 (year 8). Faster pace runs 19.5% and Lower lot price 11.9%; the sensitivity grid spans 10.1% to 25.9%. The largest line differences: MUD and WCID proceeds $112.3M against 46.1M in the mockup, because the 12% and 4.2% debt ratios apply to about $800M of assessed value; lot sales $235.6M against 318.9M on 2,380 lots at $1,800 per front foot; collector roads $8.8M against 22.6M on 18.6 acres of right of way. Rejected: forcing inputs to hit the mockup numbers. `docs/synthetic-deals.md` is updated to the fixture in build step 3.

## 2026-09-14 · Two source-model behaviours kept as is
Two behaviours of the internal engine were ported unchanged so the numbers reconcile, and are flagged here rather than fixed. First, the last home-sale month that closes the marketing, insurance and bookkeeping windows is taken from the last lot size processed, not the latest across all sizes; on Cypress Ridge every size sells out in the same month so nothing changes. Second, empty collector road rows keep their default start months and a six-month build, so an otherwise empty tract still reports a 101-month project and Cypress Ridge runs to month 101 rather than 98. Rejected: changing either in the port, which would break the reference reconciliation before the web layer exists. Both are candidates for a later, separately reconciled fix.

## 2026-09-14 · Copilot refocused on multifamily; Harbor Point Industrial replaced by Sawyer Bend Apartments
The second product is now the Multifamily Copilot. Its model follows the structure of a private multifamily buyer's model (inventoried in the gitignored `private/multifamily-model-inventory.md`): rent roll by floor plan to market rent with loss-to-lease burn-off, a unit renovation program with premiums, a per-unit operating budget with real estate taxes reassessed at purchase, an agency-style loan sized on the lesser of LTV, DSCR and debt yield with an interest-only period, exit on forward NOI, and an LP/GP waterfall with a preferred return and tiered promote. The synthetic sample deal is Sawyer Bend Apartments, a 288-unit garden community built in 2016 in Northwest Houston, replacing Harbor Point Industrial; its hand-built figures are in `docs/synthetic-deals.md` and, as with Cypress Ridge, the model's outputs replace them in build step 4. Landing navigation reads Land Underwriting and Multifamily Copilot. The copilot mockup in `design/` keeps its panel layout as the reference; its industrial content is superseded. Rejected: keeping a generic income-property copilot, which matched no single hiring conversation as well as multifamily does.

## 2026-09-14 · Site mark and wordmark
JM monogram in Source Serif 4 Medium, page ground on a navy square, with the wordmark "Javier Mendez" so initials and name agree. Two initials read at 16 px and give the browser tab a solid block where the default globe was. The lockup replaces the headshot and full-name wordmark used earlier the same day; the photo stays in the repository for a later About-section use. Rejected: MV (initials should be the person's), a single J, a circular seal (ring disappears at 16 px), and a sans version.

## 2026-09-14 · Land Underwriting screen: scenarios live in a browser session, not a database
Edits on the Tract, Costs, Revenue and Lookups tabs recalculate the active scenario and are held in a server-side session keyed by a cookie, expiring after a day. Nothing is written to Postgres in this release: the public demo needs no login and no saving, and a redeploy returning every visitor to the seed deal is the right behaviour for a showcase. Scenarios can be added, renamed, removed, and compared side by side; Main is the seed and the only one that cannot be removed. Rejected: persisting anonymous sessions to the database (adds a table, migrations and cleanup jobs for no reader-visible benefit).

## 2026-09-14 · Excel export: schedule as values, arithmetic as live formulas
The export is built from scratch with openpyxl and ships four sheets: Inputs, Summary, Pro forma (monthly), Sensitivity. The monthly line items are engine values; every total, net, cumulative, margin, ratio and the XIRR on the Summary sheet is a live formula over them, so a reviewer can audit the arithmetic and trace each headline to the months behind it. The landing page copy was tightened to say so. Rejected: rebuilding the full land model as spreadsheet formulas (thousands of cells to maintain in parallel with the Python engine) and shipping the internal workbook template (not ours to publish).

## 2026-09-14 · Sensitivity grid recalculates on the server
The grid reruns the engine for every cell (3 ms per run, at most 49 cells) when the axes change, through one HTMX request. Six drivers are offered: lot price per front foot, pace, contingency, home price, yield, and development cost per lot; metric is unlevered IRR or gross margin. Cell shading ranks values across the visible grid. Rejected: precomputing grids or shading on fixed thresholds.

## 2026-09-14 · Cypress Ridge documentation now matches the fixture
`docs/synthetic-deals.md` carries the engine's figures for Cypress Ridge (acreage, summary, financial summary, yearly cash flow, sensitivity), generated from `tests/fixtures/cypress_ridge.json` and the seed. The hand-built mockup figures are gone from the docs; the mockup PNGs in `design/` still show them and remain the layout reference. The landing page reads its sample figures from the engine at startup, so the two cannot drift.

## 2026-09-14 · Multifamily Copilot direction: a working intake, with the buyer's-model port as the calculator
The Copilot is built to be used, not only shown. Its backbone is the multifamily engine ported in build step 4 from the structure in `private/multifamily-model-inventory.md`. The Screen step becomes an intake: the user uploads a broker offering memorandum and, when available, a rent roll and a trailing twelve-month operating statement; extraction returns every model input it can find with a source citation and a confidence grade; the tool then lists what the documents did not settle and asks for it, one question per missing or low-confidence input (renovation scope and premium, tax reassessment basis, insurance quote, loan terms, exit cap, hold period), with the extracted figure and its source shown next to each question so the analyst can accept or override. Answers flow into the typed inputs and the Underwrite step runs from there. The demo ships with synthetic documents for Sawyer Bend so the intake can be exercised without an API key; the live extraction path needs `ANTHROPIC_API_KEY`. Phasing: build step 4 engine and tests; step 5 screen from the seed; step 6 uploads, extraction, evals and the question loop; step 7 memo. Rejected: a free-form chat over the documents (no auditable link from a figure to its source) and extraction without the question loop (an OM never carries the buyer's assumptions, so the model would silently fill them).

## 2026-09-14 · Multifamily engine built; Sawyer Bend figures now come from the engine
`core/copilot/` is a monthly engine reported annually, following the private inventory: rent roll by floor plan to market with loss to lease burning off over twelve months, a renovation program with pace, downtime and premiums, revenue deductions, per-unit expenses stepped yearly with taxes reassessed at the price, management fee on EGI, reserves, a loan sized on the lesser of LTV, DSCR and debt yield with interest only then amortization, sources and uses with capital funded at close, exit on the twelve forward months of NOI, monthly XIRR, and a three-tier LP/GP waterfall on monthly accrual balances. The engine's figures replace the hand-built annual figures: levered IRR 14.8% (was 13.5%), unlevered 10.2%, equity multiple 1.89× (1.81×), LP IRR 13.0% (12.4%), going-in cap 5.74% (5.81%), year 1 NOI $2.64M, exit value $62.8M (61.3M), levered IRR at the ask 7.9% (6.8%). The lift comes from monthly compounding of market rents and an exit on forward NOI, which the annual scratch model approximated. Inputs did not change. The reference outputs are frozen in `tests/fixtures/sawyer_bend.json`. Rejected: tuning inputs to reproduce the scratch figures.

## Deferred
- Financing layer (debt draw, interest, waterfall, equity multiple) for the MPC tool.
- Benchmark module (public comps) for the Copilot.
- Floating-rate debt with SOFR caps, a refinance loan, and multi-level waterfall catch-ups in the Copilot; the first release ships fixed-rate acquisition debt and a three-tier waterfall.
- Dark mode.
