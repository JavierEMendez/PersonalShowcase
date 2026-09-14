"""FastAPI entry point.

Routes render Jinja2 templates. Model logic lives in core/ and is not imported here yet
(build step 1 is the scaffold only).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Mendez Valdez", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

SITE: dict[str, str] = {
    "wordmark": "Javier Mendez",
    "repo_url": "https://github.com/JavierEMendez/PersonalShowcase",
    "github_url": "https://github.com/JavierEMendez",
    "github_label": "github.com/JavierEMendez",
    "linkedin_url": "https://linkedin.com/in/javieremendez",
    "linkedin_label": "linkedin.com/in/javieremendez",
    # Public contact address. Optional; the About row is omitted when unset.
    "contact_email": os.environ.get("CONTACT_EMAIL", ""),
}

# Deal headers for the two tool stubs. Figures arrive with the model ports (build steps 2 and 4).
UNDERWRITING_DEAL: dict[str, Any] = {
    "eyebrow": "Sample deal · Initial UW",
    "title": "Cypress Ridge",
    "facts": "640.0 ac · Waller County, TX · Closing Mar 2027 · $45,000 / ac",
    "scenarios": ["Main", "Faster pace", "Lower lot price"],
    "active_scenario": "Main",
    "tabs": ["Performance", "Tract", "Costs", "Revenue", "Cashflows", "Lookups"],
    "active_tab": "Performance",
    "kpis": [
        "Unlevered IRR",
        "Total revenue",
        "Gross costs",
        "Gross margin",
        "Net margin",
        "Return on cost",
        "Peak cash need",
        "Project length",
    ],
}

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


def render(request: Request, name: str, **context: Any) -> HTMLResponse:
    return templates.TemplateResponse(request, name, {"site": SITE, **context})


@app.get("/", response_class=HTMLResponse)
async def landing(request: Request) -> HTMLResponse:
    return render(request, "landing.html")


@app.get("/underwriting", response_class=HTMLResponse)
async def underwriting(request: Request) -> HTMLResponse:
    return render(request, "underwriting.html", deal=UNDERWRITING_DEAL)


@app.get("/copilot", response_class=HTMLResponse)
async def copilot(request: Request) -> HTMLResponse:
    return render(request, "copilot.html", deal=COPILOT_DEAL)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
