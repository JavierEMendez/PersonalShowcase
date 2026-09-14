"""Shared Jinja2 environment, site-wide context, and the render helper."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app import formatting

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

templates = Jinja2Templates(directory=BASE_DIR / "templates")
formatting.register(templates.env)

SITE: dict[str, str] = {
    "wordmark": "Javier Mendez",
    "repo_url": "https://github.com/JavierEMendez/PersonalShowcase",
    "github_url": "https://github.com/JavierEMendez",
    "github_label": "github.com/JavierEMendez",
    "linkedin_url": "https://linkedin.com/in/javieremendez",
    "linkedin_label": "linkedin.com/in/javieremendez",
    # Public contact address. Optional; the About row is omitted when unset.
    "contact_email": os.environ.get("CONTACT_EMAIL", ""),
    # Changes whenever the stylesheet changes, so browsers never hold a stale copy.
    "asset_version": str(int((STATIC_DIR / "site.css").stat().st_mtime)),
}


def render(
    request: Request,
    name: str,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
    **context: Any,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request, name, {"site": SITE, **context}, status_code=status_code, headers=headers
    )
