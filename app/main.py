"""FastAPI entry point.

Routes render Jinja2 templates. Model logic lives in core/; the web layer calls into it.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app import underwriting
from app.templating import STATIC_DIR, render
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

# Deal header for the Multifamily Copilot stub. Figures arrive with the model in build step 4.
COPILOT_DEAL: dict[str, Any] = {
    "eyebrow": "Sample deal · Multifamily · Value-add acquisition",
    "title": "Sawyer Bend Apartments",
    "facts": "288 units · Built 2016 · Northwest Houston · 94.1% occupied · 5-year hold",
    "cases": ["Base", "Downside", "Lender"],
    "active_case": "Base",
    "steps": ["Screen", "Underwrite", "Recommend", "Monitor"],
    "active_step": 2,
    "kpis": [
        "Purchase price",
        "Going-in cap",
        "Levered IRR",
        "LP IRR",
        "Equity multiple",
        "DSCR, year 1",
        "LTV",
        "Exit value",
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
