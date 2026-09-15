# Cheat sheet: how the site works and how to operate it

For the owner. Everything here is also in the code and the decisions log; this is the short
version to keep open during a demo or a change.

## The site in one paragraph

One FastAPI app on Railway serves a landing page, an About page and two tools. **Land
Underwriting** (`/underwriting`) is a Python port of the MPC land model with editable inputs,
scenarios, a sensitivity grid and an IC memo PDF. **Multifamily Screening Tool** (`/copilot`, which
opens on Screen) reads a broker package, asks about what the documents leave open, runs a monthly
acquisition model and recommends a valuation range: whether the deal is worth a full underwriting
and at what price. All deals are synthetic. State lives in the browser session for a day; a
redeploy resets everyone.

## URLs

| Page | Path | What it shows |
|---|---|---|
| Landing | `/` | Both products, sample figures pulled from the engines at startup, short About |
| About | `/about` | Full bio with headshot |
| Land Underwriting | `/underwriting` | Performance tab: summary strip, financial summary, acreage, sensitivity, cash flow by year, scenario comparison |
| Input tabs | `/underwriting/tract`, `/costs`, `/revenue`, `/lookups` | Editable inputs; a blank field resets to the model default |
| Cashflows | `/underwriting/cashflows` | Yearly and monthly schedule |
| Land memo | `/underwriting/memo.pdf?scenario=Main` | Two-page IC memo: recommendation with the price per acre solved from a 15% unlevered IRR floor, then the evidence |
| Screen | `/copilot/screen` (also `/copilot`) | Uploads, extracted figures with citations, unit mix, questions |
| Underwrite | `/copilot/underwrite?case=Base` | Cases Base, Downside, Lender, and Screened once Screen has run; no memo here |
| Recommend | `/copilot/recommend?case=Base` | Valuation range (low, mid, max) with KPIs at each price, the memo, stress table, market context |
| Memo | `POST /copilot/memo?case=Base`, `GET /copilot/memo.md?case=Base` | Draft with the configured writer (returns to Recommend); download as markdown |
| Deck | `GET /copilot/memo.pdf?case=Base` | Two-page PDF (recommendation with the range, evidence); a third audit-trail page for the Screened case |
| Health | `/health` | Railway health check |

## Demo in five minutes

1. Land Underwriting: change lot price on the Revenue tab, watch the strip and grid move. Add a
   scenario with the "+ Add" pill, rename it, compare in the table at the bottom. Download the
   IC memo and point at the recommended price per acre.
2. Copilot Screen: "Use the sample documents". Point at a quote and its confidence. Change
   insurance to 850 and controllables to 3,850 (the buyer's numbers); "Run the underwriting".
3. Underwrite: the Screened pill is active. Read the strip and the stress table, then "View
   recommendation". The range table shows low, mid and max with the KPIs at each; "Draft the Memo"
   rewrites the prose on the same figures (without an API key it says "sentence template"); "Download IC
   Memo" is the PDF.
4. Say what is synthetic (everything) and where the logic came from (internal models, ported and
   reconciled for the land tool; structure-faithful for the multifamily tool).

## How each tool computes

**Land model** (`core/underwriting/`). Inputs: tract (acreage, net-outs, roads, plants,
amenities), costs (per front foot and per lot by lot size, overhead, takedowns), revenue (lot
price per front foot by year, pods, bonds), lookups. Order: net-outs to developable acres; land
takedowns; infrastructure by project; allocation of shared costs to lot sizes by front foot;
sections developed on a pace; lots sold with a takedown timing method; assessed value and MUD or
WCID bond proceeds; overhead and fees; a 360-month ledger summed to a summary and an XIRR on
actual/365 dates. Unlevered only, by design.

**Multifamily model** (`core/copilot/`). Inputs: property floor plans, revenue assumptions,
renovation program, capital budget, operating per-unit lines, acquisition, loan, exit, equity.
Order: rent roll to market with loss to lease burning off over twelve months; renovation premium
and downtime; vacancy, concessions, bad debt, other income; expenses stepped yearly with taxes
reassessed at the purchase price; management fee on EGI; reserves; loan sized on the lesser of
LTV, DSCR and debt yield, interest only then amortizing; sources and uses; exit on the twelve
forward months of NOI at the exit cap; monthly XIRR; LP/GP waterfall with preferred return and a
hurdle tier. Stress table holds the loan fixed and moves one variable at a time.

**Screen** (`core/copilot/screen.py`). Rent roll and T-12 are parsed with code. The OM is read
by the Claude API when `ANTHROPIC_API_KEY` is set, else by regular expressions. Every OM figure
is checked: quote on the cited page, figure in the quote. About twenty questions default to the
extracted figure or the current model input; answers land on the Base inputs as the Screened
case.

**Recommend** (`core/copilot/recommend.py`, `core/copilot/memo.py`). The range is solved from
levered LP IRR targets (`LP_TARGETS`): 13% sets the max, 15% the mid, and the low is the lower
of the 17% price and 20% below the ask (`LOW_DISCOUNT_CAP`). The verdict is pursue when the ask
sits inside the range, engage (only below the max) when it is above, pass when no price returns
13%. A facts table of about sixty formatted figures. The writer
(template, or Claude when the key is set) writes prose with `{placeholders}` and may not write a
digit. Drafts that break a rule fall back to the template and say so.

## Run it locally

```bash
cd C:\Users\Javier\Documents\PersonalShowcase
.venv\Scripts\python -m uvicorn app.main:app --port 8010
```

Then open http://127.0.0.1:8010. Checks before a commit:

```bash
.venv\Scripts\ruff check . && .venv\Scripts\ruff format --check .
.venv\Scripts\mypy
.venv\Scripts\python -m pytest -q
.venv\Scripts\python scripts\lint_copy.py README.md CLAUDE.md docs\*.md app\templates\*.html app\templates\underwriting\*.html app\templates\copilot\*.html
.venv\Scripts\python -m evals.screen.run
.venv\Scripts\python -m evals.memo.run
```

CI runs the same on every push. Railway builds the Dockerfile from `main` and checks `/health`.

## Environment variables (Railway)

| Variable | Effect |
|---|---|
| `ANTHROPIC_API_KEY` | Turns on the Claude reader for the OM and the Claude writer for the memo. Without it the rule reader and the template are used and the pages say so. |
| `COPILOT_MODEL` | Model id for both; default `claude-sonnet-5`. |
| `CONTACT_EMAIL` | Adds an Email row to the About tables. Optional. |
| `FRED_API_KEY` | FRED official API for the Market context panels. Without it the public CSV endpoint is used, and if that fails the recorded snapshot. |

No other secrets. Nothing is written to disk at runtime.

## Change the deals

- **Land inputs**: edit `scripts/seed_cypress_ridge.py`, run it to regenerate
  `data/cypress_ridge.json`, then regenerate the fixture if the engine output should change:
  the fixture test in `tests/underwriting/test_engine.py` tells you what moved. Update
  `docs/synthetic-deals.md` with the session docs script pattern (figures come from the engine).
- **Multifamily inputs**: edit `scripts/seed_sawyer_bend.py`, run it for `data/sawyer_bend.json`,
  then `scripts/make_sawyer_bend_docs.py` to regenerate the OM, rent roll and T-12 so the
  documents still reconcile, then `python -m evals.screen.run` and fix `evals/screen/expected.json`
  if a figure moved.
- **Extracted-assumption catalogue**: `FIELDS` in `core/copilot/screen.py`, mirrored in
  `evals/screen/expected.json`; a test checks the two agree.
- **Questions**: `QUESTIONS` in `core/copilot/screen.py`.
- **Memo sentences**: `TemplateWriter` in `core/copilot/memo.py`; placeholders in `build_facts`.
- **Deck layout**: `core/copilot/deck.py`. The site typefaces are bundled in `app/static/fonts/` (OFL) and embedded in the PDF.
- **Copy rules**: `core/copy_rules.py`, used by the linter and the memo checks.
- **Market context**: rules and rows in `core/benchmarks/context.py`, sources in `core/benchmarks/sources.py`; refresh the fallback snapshot with `python scripts/record_benchmarks.py`. See `docs/benchmarks.md`.

## Where things live

```
app/            routes (main, underwriting, copilot), sessions, forms, formatting, templates, site.css
core/           underwriting/ and copilot/ engines; copy_rules.py
data/           seeds and the synthetic broker package (data/sawyer_bend/)
evals/          screen/ and memo/ (run with python -m evals.<name>.run)
scripts/        seed and document generators, lint_copy.py
tests/          123 tests; fixtures under tests/fixtures/
docs/           decisions.md (the log), case-study.md, failure modes, design standard, this file
private/        gitignored; strategy brief and internal inventories; never quote publicly
design/         approved mockups; the layout reference, figures superseded by the engines
```

## Rules that keep the site honest

- No client data, internal figures, internal files or logos. The internal workbook is never
  copied into the repo.
- Model math never runs through a language model. The model reads documents and writes
  sentences, with checks on both.
- Every figure on a page comes from an engine at request time or startup; nothing is hard-coded.
- Every trade-off goes in `docs/decisions.md` with the date and what was rejected.
- Copy rules: no em dashes, no filler verbs, none of the contrast constructions on the banned list, no exclamation points.

## If something looks wrong

- **Unstyled page after a deploy**: the stylesheet URL carries a version from the file's
  modification time; a hard refresh fixes a cached copy.
- **Scenario or screened case disappeared**: sessions last a day and reset on redeploy.
- **"Extraction failed"** on Screen with a key set: the model call failed; the page falls back to
  no result. Check the Railway logs and the key.
- **Memo says "template was used"**: the model draft broke a rule; the reasons are shown under
  the memo head. This is by design.
- **A test fixture fails after an engine change**: the fixture is the reference. Decide whether
  the change is intended, then regenerate it and record the figure differences in the decisions
  log.
