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

## Deferred
- Financing layer (debt draw, interest, waterfall, equity multiple) for the MPC tool.
- Benchmark module (public comps) for the Copilot.
- Dark mode.
