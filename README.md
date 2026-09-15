# Javier Mendez: transaction tools

Two underwriting tools for real estate transactions developed with Claude Code. Both started as internal systems and were rebuilt here on synthetic deals so the full model can be read.

Live site: https://javiermendez.up.railway.app

![Land Underwriting, the Copilot intake, and the Copilot underwrite screen](docs/media/demo.gif)

## Recommendation

Read this repo the way a committee reads a memo: outcome first, then the evidence.

- **Land Underwriting** is a module-by-module port of a master-planned-community land model: 640 acres, 21 cost lines, a 360-month ledger, and an unlevered XIRR. On the sample deal it reproduces the source engine to the dollar on every summary line and every monthly cash flow, with the XIRR matching to ten decimals across three scenarios. Inputs are editable in the browser; the sensitivity grid recalculates on the server at three milliseconds per run; the Excel export carries live formulas over the schedule.
- **Multifamily Copilot** takes a broker package (offering memorandum, rent roll, T-12), extracts model inputs with a page citation, a verbatim quote and a confidence grade for each, asks about what the documents leave open, runs a monthly acquisition model with loan sizing, stress tests and an LP/GP waterfall, and drafts the investment committee memo. Every figure in the memo comes from the model: the writer produces prose with placeholders and the code fills the numbers.
- **The language model is kept in its lane.** It reads documents and writes sentences. It never does arithmetic. Extractions are verified against the cited page; memo drafts that contain a digit are rejected. Both uses have eval sets and a written failure-mode list.

## How to evaluate this in five minutes

1. Open the [Land Underwriting demo](https://javiermendez.up.railway.app/underwriting). Change lot price on the Revenue tab; watch the summary strip, the cash flow by year and the sensitivity grid move. Export the model and open the Summary sheet: the XIRR is a formula over the months.
2. Open the [Copilot Screen step](https://javiermendez.up.railway.app/copilot/screen) and press "Use the sample documents". Fifteen figures arrive with their sources. Change the insurance answer to the broker quote and press "Run the underwriting": a Screened case opens beside Base, Downside and Lender.
3. On the underwrite screen, read the IC memo panel and the stress table. Press "Draft IC memo" to regenerate it. Download the memo as markdown.
4. Read [docs/decisions.md](docs/decisions.md), which records every trade-off in date order, including the ones rejected, and [docs/case-study.md](docs/case-study.md) on what changed when the models left Excel.
5. Run the checks yourself:

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest -q
python -m evals.screen.run
python -m evals.memo.run
```

## Architecture

```
app/              FastAPI routes, Jinja templates, one stylesheet; per-browser sessions in memory
core/underwriting Land model: netouts, land, infrastructure, allocation, sections, revenue,
                  assessed value and bonds, opex, summary, XIRR, sensitivity, Excel export
core/copilot      Multifamily model: rent roll, renovation, operations, debt, capital stack,
                  waterfall, sensitivity, Excel export; documents, screen (extraction), memo
evals/            Extraction eval (15 figures, cited) and memo eval (fidelity, structure, copy rules)
data/             Synthetic seeds: Cypress Ridge (land), Sawyer Bend (multifamily) and its broker package
scripts/          Seed generators, the synthetic document generator, the copy linter
tests/            123 tests; reference fixtures freeze both engines' outputs
docs/             Decisions log, case study, failure modes, design standard, synthetic deals, cheat sheet
```

The web layer calls into `core/`; model logic never lives in a route or a template. Percentages are fractions inside the models and percentages in the browser. Editable state lives in a cookie-keyed in-memory session for a day; a redeploy resets the demo, which is the intended behaviour for a public site.

Quality gates on every push: ruff, mypy in strict mode, pytest, and a copy linter that fails on em dashes and a list of filler phrases, applied to templates, docs and generated memos.

## What is real and what is synthetic

Both deals are invented. Cypress Ridge and Sawyer Bend, their brokers, comparables and documents exist only in this repository. Market inputs come from public sources. No client data, internal figures or internal files appear here; the internal models the tools descend from stay private, and the decisions log records where the port reconciles to them and where it deliberately does not.

The language model paths (reading the offering memorandum, drafting the memo) run when `ANTHROPIC_API_KEY` is set; without it a rule reader and a sentence template take over, so the site works with no key at all.

## Documents

- [Decisions](docs/decisions.md): every trade-off, dated, with the alternatives rejected.
- [Case study](docs/case-study.md): what changed when the models left Excel, and what the tests and evals caught.
- [Cheat sheet](docs/cheat-sheet.md): how the site works, how to run it, how to change the deals.
- [Screen failure modes](docs/screen-failure-modes.md) and [memo failure modes](docs/memo-failure-modes.md).
- [Synthetic deals](docs/synthetic-deals.md): the two deals in full, generated from the engines.
- [Design standard](docs/design-standard.md) and [brand mark](docs/brand-mark.md).

## About

Javier Mendez Valdez, Finance and Analytics Manager at EMBER, MBA candidate at Rice University, Houston. Six years in financial modeling, transaction analysis and FP&A across real estate investment and private equity. [LinkedIn](https://linkedin.com/in/javieremendez) · [GitHub](https://github.com/JavierEMendez) · [Full bio](https://javiermendez.up.railway.app/about)
