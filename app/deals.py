"""Seed deals loaded from data/ at startup."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.sessions import Scenario
from core.underwriting.inputs import DealInputs

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_cypress_ridge() -> tuple[dict[str, Any], list[Scenario]]:
    """The Cypress Ridge seed: deal metadata and its scenarios as typed inputs."""
    raw = json.loads((DATA_DIR / "cypress_ridge.json").read_text(encoding="utf-8"))
    scenarios = [
        Scenario(name=s["name"], inputs=DealInputs.model_validate(s["inputs"]))
        for s in raw["scenarios"]
    ]
    meta = {"name": raw["name"], "status": raw["status"], "location": raw["location"]}
    return meta, scenarios
