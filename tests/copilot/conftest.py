"""Shared fixtures: the Sawyer Bend cases from the seed file."""

import json
from pathlib import Path

import pytest

from core.copilot.inputs import CopilotInputs

ROOT = Path(__file__).resolve().parents[2]
SEED = ROOT / "data" / "sawyer_bend.json"


def load_case(name: str) -> CopilotInputs:
    seed = json.loads(SEED.read_text(encoding="utf-8"))
    for case in seed["cases"]:
        if case["name"] == name:
            return CopilotInputs.model_validate(case["inputs"])
    raise KeyError(name)


@pytest.fixture(scope="session")
def sawyer_base() -> CopilotInputs:
    return load_case("Base")
