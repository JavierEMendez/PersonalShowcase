# Handoff to Claude Code

This packet moves the showcase project from planning (done in Cowork) to build (Claude Code). Everything Claude Code needs is in this folder. Nothing in it depends on the Cowork conversation.

## Contents

| Path | What it is |
|---|---|
| `CLAUDE.md` | Project instructions Claude Code reads every session. Put at the repo root. |
| `docs/handoff.md` | This file. |
| `private/strategy-brief.md` | Why the project exists, who it is for, what "it worked" looks like. Gitignored. |
| `private/mpc-tool-inventory.md` | Exact inputs, outputs, formulas, and data shapes of the MPC Underwriting tool, taken from the internal source. Gitignored. |
| `.gitignore` | Keeps `private/` and `.env` out of the public repo. |
| `docs/design-standard.md` | Tokens, type, layout, table rules, copy rules, starter CSS. |
| `docs/synthetic-deals.md` | Every figure shown in the mockups, for seed files and test fixtures. |
| `docs/decisions.md` | Decision log, seeded with the decisions made so far. |
| `design/landing.html`, `design/underwriting.html`, `design/copilot.html` | Approved mockups as plain HTML with inline styles. Lift markup and values directly. |
| `design/*.png` | Renders of the three mockups at 1440px. |
| `scripts/lint_copy.py` | Fails on em dashes and the banned phrase list. Wire into CI. |

## Before the first Claude Code session

1. Complete the EmberApps cleanup in the separate note you received with this packet (make the repo private, rotate keys, remove fallbacks). That note stays out of this repo.
2. Create the new repo: `mkdir showcase && cd showcase && git init && gh repo create showcase --public --source=. --remote=origin`.
3. Copy this packet into it: `CLAUDE.md` and `.gitignore` at the root, everything else in place. Confirm `git status` does not list `private/`. Commit: `Add design standard, mockups, and handoff docs`.
4. Clone EmberApps as a sibling directory (`../EmberApps`) so Claude Code can read `calc.py` during the port. Never copy Ember files into the showcase repo.
5. Create a Railway project with a Postgres plugin and connect it to the repo's `main` branch. Add `ANTHROPIC_API_KEY` as a Railway variable only when you reach step 6 of the build order.

## Session prompts, in order

Run one per session. Each starts with Claude Code reading `CLAUDE.md` automatically. Review the output and commit before the next.

**Session 1, scaffold.**
"Read CLAUDE.md, docs/design-standard.md, and design/landing.html. Scaffold the FastAPI app with the repo layout from CLAUDE.md. Build app/static/site.css from the starter in the design standard. Build the landing page as a Jinja2 template that reproduces design/landing.html, replacing inline styles with classes where a class exists and keeping inline styles otherwise. Stub /underwriting and /copilot with the top bar, deal header, and an empty summary strip. Add ruff, mypy, pytest, and a GitHub Actions workflow. Add a Dockerfile and railway.toml. Do not write any model code. Stop and show me the landing page running locally."

**Session 2, port the MPC engine.**
"Read private/mpc-tool-inventory.md. Read ../EmberApps/calc.py in full. Port it into core/underwriting/ as the modules listed in CLAUDE.md, preserving calculation order and comments, dropping Excel cell references, and using typed pydantic inputs. Write tests first for each module using the Cypress Ridge inputs in docs/synthetic-deals.md. When the port runs end to end, write data/cypress_ridge.json (inputs for Main, Faster pace, and Lower lot price per docs/synthetic-deals.md), save the Main outputs to tests/fixtures/cypress_ridge.json, and list every figure that differs from docs/synthetic-deals.md. Do not touch the web layer."

**Session 3, underwriting screen.**
"Read design/underwriting.html and docs/design-standard.md. Build the /underwriting performance screen from the Cypress Ridge fixture: summary strip, financial summary, acreage, sensitivity grid (server-side recalculation via HTMX), and net cash flow by year with bar cells. Match the mockup. Then add the Cashflows tab (line items by year and monthly detail) and the input tabs (Tract, Costs, Revenue, Lookups) as forms that recalculate on change within the browser session. Then scenarios (add, rename, compare) and Excel export built from scratch with openpyxl and live formulas. Update docs/synthetic-deals.md to the fixture figures and log the change in docs/decisions.md."

**Session 4, copilot core.**
"Read docs/synthetic-deals.md, Harbor Point section. Build core/copilot/: NOI build, sources and uses, debt service with amortization, DSCR by year, levered and unlevered IRR, equity multiple, exit value, loan balance at exit, and a single-variable stress table. Write tests that reproduce the Harbor Point figures. Write data/harbor_point.json with the Base, Downside, and Lender cases per docs/synthetic-deals.md. Add Excel export. No web code."

**Session 5, copilot screen.**
"Read design/copilot.html. Build the /copilot underwrite screen from the Harbor Point seed, including the Monitor panel fed from the same model with a synthetic quarter of actuals. Match the mockup. Case pills switch between Base, Downside, and Lender."

**Session 6, screen module.**
"Build core/copilot/screen.py: extract the 15 assumptions in docs/synthetic-deals.md from a synthetic OM and rent roll PDF (generate both in data/ with realistic layout), returning value, source page or line, and confidence. Use the Claude API with structured output. Build evals/screen/ with the 15 expected values and a scorer. Document failure modes in docs/screen-failure-modes.md. Wire the results into the Extracted assumptions panel."

**Session 7, recommend module.**
"Build core/copilot/memo.py: generate the IC memo from model outputs with the structure in docs/synthetic-deals.md (recommendation, body, what the model cannot tell you). Every figure in the memo must come from the model output dict, never from the language model. Run scripts/lint_copy.py on the output. Build evals/memo/ that checks figure fidelity and banned phrases. Wire 'Draft IC memo' to it."

**Session 8, README and case study.**
"Rewrite README.md as an IC memo: outcome first, a GIF of the two screens, 'How to evaluate this in five minutes', architecture, link to docs/decisions.md. Write docs/case-study.md, 1,200 words, on what changed in the workflow when the model was ported from Excel and what the evals caught. Run scripts/lint_copy.py on both."

## Working rules for every session

- Commit at the end of each session with a one-line imperative message.
- If Claude Code proposes a feature not in the build order, say no and log it in `docs/decisions.md` under "Deferred".
- When the port's numbers differ from the mockup, the port wins. Update the docs and leave the model alone.
- Keep the wordmark "Mendez Valdez" unless you decide otherwise; change it once in `app/templates/base.html` and in `design/` if you do.
