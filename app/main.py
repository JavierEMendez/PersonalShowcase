"""FastAPI entry point.

Routes render Jinja2 templates. Model logic lives in core/; the web layer calls into it.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app import underwriting
from app.deals import DATA_DIR
from app.templating import STATIC_DIR, render
from core.copilot.engine import run as run_copilot
from core.copilot.inputs import CopilotInputs
from core.underwriting.engine import run
from core.underwriting.sensitivity import build_grid

app = FastAPI(title="Javier Mendez", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(underwriting.router)

# Landing-page sample figures come from the engine, so they always match the tool.
_MAIN = underwriting.SEED[0].inputs
LANDING_SAMPLE: dict[str, Any] = {
    "summary": run(_MAIN).summary,
    "grid": build_grid(_MAIN),
    "acres": _MAIN.tract.gross_acreage,
    "location": underwriting.META["location"],
}


def _load_sawyer_bend() -> tuple[dict[str, Any], CopilotInputs]:
    raw = json.loads((DATA_DIR / "sawyer_bend.json").read_text(encoding="utf-8"))
    base = next(c for c in raw["cases"] if c["name"] == "Base")
    return raw, CopilotInputs.model_validate(base["inputs"])


_SAWYER_META, _SAWYER_BASE = _load_sawyer_bend()
SAWYER = run_copilot(_SAWYER_BASE)
LANDING_SAMPLE["multifamily"] = SAWYER

# Deal header for the Multifamily Copilot. The screen itself arrives in build step 5.
_s = SAWYER.summary
COPILOT_DEAL: dict[str, Any] = {
    "eyebrow": "Sample deal · Multifamily · Value-add acquisition",
    "title": "Sawyer Bend Apartments",
    "facts": "288 units · Built 2016 · Northwest Houston · 94.1% occupied · 5-year hold",
    "cases": ["Base", "Downside", "Lender"],
    "active_case": "Base",
    "steps": ["Screen", "Underwrite", "Recommend", "Monitor"],
    "active_step": 2,
    "kpis": [
        (
            "Purchase price",
            f"${_s.purchase_price / 1e6:.1f}M",
            f"${_s.price_per_unit:,} / unit · ask ${(_s.asking_price or 0) / 1e6:.1f}M",
        ),
        ("Going-in cap", f"{_s.going_in_cap:.2%}", f"Year 1 NOI ${_s.noi_year1 / 1e6:.2f}M"),
        ("Levered IRR", f"{(_s.levered_irr or 0):.1%}", f"Unlevered {(_s.unlevered_irr or 0):.1%}"),
        ("LP IRR", f"{(_s.lp_irr or 0):.1%}", "After the waterfall"),
        (
            "Equity multiple",
            f"{_s.equity_multiple:.2f}×",
            f"On ${SAWYER.sources_uses.equity / 1e6:.1f}M equity",
        ),
        (
            "DSCR, year 1",
            f"{(_s.dscr_year1 or 0):.2f}×",
            f"Covenant {SAWYER.loan.covenant_dscr:.2f}×",
        ),
        ("LTV", f"{_s.ltv:.1%}", f"Debt yield {_s.debt_yield:.1%}"),
        ("Exit value", f"${_s.exit_value / 1e6:.1f}M", f"Forward NOI / {SAWYER.exit.cap_rate:.2%}"),
    ],
}


@app.get("/", response_class=HTMLResponse)
async def landing(request: Request) -> HTMLResponse:
    return render(request, "landing.html", sample=LANDING_SAMPLE)


@app.get("/copilot", response_class=HTMLResponse)
async def copilot(request: Request) -> HTMLResponse:
    return render(request, "copilot.html", deal=COPILOT_DEAL)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
