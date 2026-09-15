# Showcase: CLAUDE.md

## What this repo is

A public, hosted showcase of two products built by Javier Mendez with Claude Code and Cowork, aimed at hiring managers in transaction advisory, corporate real estate strategy, credit, and private equity. The reader is a partner or MD with five minutes. They open the URL, read the landing page, click into one tool, and decide whether they trust the analysis. Everything in this repo serves that moment.

Two products live under one Railway app and one domain:

1. `/underwriting`: MPC Underwriting. A port of the calculation engine from a private internal repo (EmberApps, `calc.py`, cloned as a sibling directory for reference), rebuilt here on synthetic data. It is an unlevered residential land pro forma: it returns unlevered XIRR, gross and net margin, and per-acre and per-lot metrics. It has no debt, equity waterfall, or equity multiple. Do not describe it as if it did.
2. `/copilot`: Multifamily Copilot (the deal-to-portfolio workflow). New. Apartment acquisition workflow in four steps: Screen, Underwrite, Recommend, Monitor. Its model follows the structure of a private multifamily buyer's model, inventoried in `private/multifamily-model-inventory.md`: rent roll to market with loss-to-lease burn-off, unit renovation program with premiums, per-unit operating budget with tax reassessment, loan sized on the lesser of LTV, DSCR and debt yield with an interest-only period, exit on forward NOI, and an LP/GP waterfall.

Read `docs/handoff.md` first, then `private/strategy-brief.md`, `private/mpc-tool-inventory.md`, `private/multifamily-model-inventory.md`, `docs/design-standard.md`, and `docs/synthetic-deals.md`. The `private/` folder is gitignored: it holds the strategy brief and the inventories of the internal tool and model being ported, and it never gets committed or quoted in public docs, README, or copy. The approved mockups are in `design/` as HTML and PNG. Match them.

## Non-negotiables

- Public demos run on the synthetic deals in `docs/synthetic-deals.md` (Cypress Ridge, Sawyer Bend Apartments) plus real public market data (FRED, Census/ACS, appraisal district records, TxDOT, SEC EDGAR). Nothing from Ember's book: no client names, real tract IDs, builder data, internal figures, Ember logos, or Ember template files.
- The site loads a pre-seeded deal with no login and no API key. Anyone with the link can evaluate it. Editing inputs works in the browser session; saving requires nothing.
- Numbers are the product. Consistent decimals, units in the panel header, tabular figures, right-aligned numerics, negative values in parentheses in tables, and totals recomputed from rounded lines so every table foots.
- No AI tells in any copy, README, or generated memo (lint-ignore): no em dashes, no "it's not X, it's Y" or "X, not Y" constructions, no "delve", "leverage", "robust", "seamless", "unlock", "empower", no exclamation points, no rhetorical questions. Short declarative sentences. Say the number, then what it means.
- Wordmark is "Javier Mendez" with the JM mark (app/static/brand/mark.svg) at the top left; see docs/brand-mark.md. Page titles: "Javier Mendez" on the landing page, "Javier Mendez · <Product>" on tool pages. No employer branding anywhere. Public docs, README, and copy refer to the source of the MPC tool as "an internal underwriting tool" and never quote figures, defaults, file names, or module descriptions from `private/`.

## Design standard (summary; full spec in docs/design-standard.md)

Executive, bank style. An institutional IC memo and a lender term sheet, rendered as a web page.

- Background `#FAFAF7`, surface `#FFFFFF`, ink `#16191D`, secondary `#3A4048`, muted `#6C7078`, hairline `#E6E4DE`, rule `#B8B5AC`, border `#DCDAD3`. Accent navy `#0F2A44` (primary buttons, links). Positive `#1E6B48`. Negative `#9E3A2B`. Warning `#8A6A1A`. Sequential heat for sensitivity grids: `#FBFCFC` to `#7F9AB6` in eight steps.
- Type: Source Serif 4 (500) for headings and large figures, IBM Plex Sans (400/500/600) for body and tables, `font-variant-numeric: tabular-nums` everywhere. Eyebrow labels 11px uppercase with .08em tracking.
- Geometry: radii 2px, borders 1px, no shadows, no gradients, panel padding 18px 20px, 20px grid gap, 12-column grid, 1440px design width, 32px page gutters in tools and 72px on the landing page.
- Every tool screen: 56px top bar (wordmark / product, tabs or stepper, actions), deal header, a summary strip of eight figures with a 1px ink rule above, then panels. Each panel has an eyebrow title left and its unit or context right.
- Every screen answers three questions in order: what is it, what does it return, what breaks it.

## Architecture

- Python 3.12, FastAPI, Postgres on Railway, SQLAlchemy, Alembic.
- Server-rendered Jinja2 templates with HTMX for recalculation and scenario switching. Add JavaScript only for the sensitivity grid and small inline bar cells. No SPA framework.
- Model logic in `core/` as pure Python with typed inputs (pydantic) and outputs, fully unit tested, no framework imports. The web layer calls into it.
- `core/underwriting/` is a clean port of EmberApps `calc.py`. Keep the calculation order and formula comments; drop the Excel cell references; rename to clear snake_case; keep the numerical results identical to a reference run (see `tests/fixtures/`).
- No Excel exports; each tool ships an IC memo PDF instead (do not ship Ember_Template.xlsx). One workbook: Inputs, Pro Forma (monthly), Summary, Sensitivity.
- Claude API used only in `core/copilot/screen.py` (assumption extraction with citations and confidence) and `core/copilot/memo.py` (IC memo generation). Both have eval sets in `evals/` and a documented failure-mode section. Model math never runs through a language model.
- GitHub Actions: ruff, mypy, pytest, eval smoke test on every PR. Railway deploys from `main`. Secrets only in Railway environment variables; a missing secret fails startup with a clear message, never a fallback value.

## Repo layout

```
app/            FastAPI app, routes, templates, static/site.css
core/
  underwriting/ MPC land model: netouts, allocation, sections, revenue, av, bonds, opex, summary, irr
  copilot/      rent_roll, renovation, operations, debt, capital_stack, waterfall, sensitivity, screen, memo, monitor
data/           synthetic deal seeds (JSON) and public dataset loaders
design/         approved mockups: landing.html, underwriting.html, copilot.html and PNGs
docs/           handoff, design standard, synthetic deals, decisions log
private/        gitignored: strategy brief, internal tool inventory
evals/          extraction and memo eval sets
tests/          unit tests and reference fixtures
CLAUDE.md
README.md
```

## Working conventions

- Before starting a module, read its section in `private/mpc-tool-inventory.md` or `docs/synthetic-deals.md`.
- Append a dated entry to `docs/decisions.md` whenever an architectural or product decision is made. One paragraph: what, why, what was rejected.
- Write the test before the model function. Underwriting math must reproduce the Cypress Ridge reference outputs in `tests/fixtures/cypress_ridge.json` to the dollar.
- Commit messages: imperative, one line, no emoji. Branch per feature, PR to `main`.
- Do not add features that need explanation to a non-technical reader. If it needs a tooltip, reconsider it.
- Do not start the Copilot UI before `core/copilot/` has passing tests and an Excel export.
- Scenarios and cases: the MPC tool ships with Main, Faster pace, and Lower lot price; the Multifamily Copilot ships with Base, Downside, and Lender. Their input deltas are defined in `docs/synthetic-deals.md`.
- When copy is generated (memo, README), run `scripts/lint_copy.py`, which fails on em dashes and the banned phrase list.

## Build order

1. Scaffold: FastAPI app, `site.css` from `docs/design-standard.md`, landing page built from `design/landing.html`, routes `/underwriting` and `/copilot` stubbed with the deal header and empty summary strip. Deploy to Railway. Confirm the fonts load and the page matches the PNG.
2. Port `core/underwriting/` from EmberApps `calc.py`, module by module, with tests. Produce the Cypress Ridge fixture from the port and check it against the mockup figures in `docs/synthetic-deals.md` (they were hand-built; the port's outputs become the source of truth and the mockup figures are updated to match).
3. `/underwriting` performance screen from `design/underwriting.html`: summary strip, financial summary, acreage, sensitivity grid (server-side, HTMX), net cash flow by year. Then the input tabs. Then scenarios and Excel export.
4. `core/copilot/`: multifamily model following `private/multifamily-model-inventory.md`: rent roll by floor plan to market rent with loss-to-lease burn-off, renovation program and premiums, revenue deductions, per-unit operating budget with tax reassessment, loan sizing on the lesser of LTV, DSCR and debt yield with interest-only then amortization, sources and uses, exit on forward NOI, unlevered and levered IRR, equity multiple, LP/GP waterfall, single-variable stress table. Excel export. Tests against the Sawyer Bend figures in `docs/synthetic-deals.md`; the model's outputs then become the source of truth.
5. `/copilot` underwrite screen using the panel layout of `design/copilot.html` with the multifamily content from `docs/synthetic-deals.md` (the mockup's industrial figures are superseded), with the Monitor panel fed from the same model. Done: `app/copilot.py`, `app/templates/copilot/underwrite.html`; the extracted assumptions are seeded in `data/sawyer_bend.json` until step 6.
6. Screen as an intake: upload an OM and, optionally, a rent roll and T-12 PDF; extraction with citations and confidence over them; a question loop that asks for each missing or low-confidence input with the extracted figure and source shown beside the question; answers flow into the typed inputs. Synthetic Sawyer Bend documents ship with the demo; eval set of 15 assumptions. Done: `core/copilot/documents.py`, `core/copilot/screen.py`, `app/templates/copilot/screen.html`, `data/sawyer_bend/` (generated by `scripts/make_sawyer_bend_docs.py`), `evals/screen/`, `docs/screen-failure-modes.md`. The rent roll and T-12 are parsed deterministically; the OM is read by the Claude API when `ANTHROPIC_API_KEY` is set and by a rule reader otherwise.
7. Recommend: IC memo generation from model outputs; eval set; "what the model cannot tell you" section required. Done: `core/copilot/memo.py` (facts table from the engine, template and Claude writers that emit placeholders only, draft checks with template fallback), `evals/memo/`, `docs/memo-failure-modes.md`. Copy rules live in `core/copy_rules.py`, shared with the linter.
8. README rewritten as an IC memo: outcome first, GIF demo, "how to evaluate this in five minutes", architecture, decision log link. Case study in `docs/`. The buyer's-model port considered on 2026-09-14 was declined; see `docs/decisions.md`.

## Audience map

- Credit officers: Monitor panel, DSCR and covenant tests, maturity.
- M&A operations: the four-step lifecycle and the decision log.
- Business modeling: `core/` math, Excel export, reconciliation tests.
- CRE strategy: sensitivity grid, stress table, IC memo.
