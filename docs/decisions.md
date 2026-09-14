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
"Mendez Valdez" as the working wordmark. To be confirmed by Javi.

## 2026-09-14 · Harbor Point priced as a bid below ask
The Copilot sample deal recommends a $38.0M bid against a $41.6M ask, because at the ask the levered IRR is 4.9% against a 12% threshold. Shows the tool producing a pricing decision rather than confirming the seller's number. Rejected: a deal that simply clears the hurdle at the ask.

## 2026-09-14 · Fixed 1440px page width
Pages render at the 1440px design width on every device (viewport meta set to 1440, page container 1440px centered) instead of a responsive layout. The reader is a partner on a laptop; on a phone the page scales down and reads like the PNG render rather than reflowing dense tables into a single column. Rejected: a responsive grid, which would need a second layout for every table and panel.

## 2026-09-14 · Contact email from the environment
The About section shows an email row only when the CONTACT_EMAIL environment variable is set on Railway. Keeps a personal address out of the public repository and lets it change without a commit. Rejected: hardcoding the address in the template.

## 2026-09-14 · Docker build on Railway
Railway builds from the repository Dockerfile (python:3.12-slim, pinned requirements.txt) with a /health check, rather than Nixpacks autodetection. The build is reproducible and the same image runs locally. Rejected: Nixpacks, which picks the Python version and start command implicitly.

## Deferred
- Financing layer (debt draw, interest, waterfall, equity multiple) for the MPC tool.
- Benchmark module (public comps) for the Copilot.
- Dark mode.
