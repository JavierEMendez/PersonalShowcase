"""FastAPI entry point.

Routes render Jinja2 templates. Model logic lives in core/; the web layer calls into it.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app import copilot, underwriting
from app.deals import DATA_DIR
from app.templating import STATIC_DIR, render
from core.copilot.engine import run as run_copilot
from core.copilot.inputs import CopilotInputs
from core.underwriting.engine import run
from core.underwriting.sensitivity import build_grid

app = FastAPI(title="Javier Mendez", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(underwriting.router)
app.include_router(copilot.router)

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


@app.get("/", response_class=HTMLResponse)
async def landing(request: Request) -> HTMLResponse:
    return render(request, "landing.html", sample=LANDING_SAMPLE)


@app.get("/about", response_class=HTMLResponse)
async def about(request: Request) -> HTMLResponse:
    return render(request, "about.html")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
