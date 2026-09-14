"""Shared fixtures: the Cypress Ridge scenarios from the seed file."""

import json
from pathlib import Path

import pytest

from core.underwriting.inputs import DealInputs
from core.underwriting.lookups import effective_lookups
from core.underwriting.netouts import Acreage, compute_netouts

ROOT = Path(__file__).resolve().parents[2]
SEED = ROOT / "data" / "cypress_ridge.json"


def load_scenario(name: str) -> DealInputs:
    seed = json.loads(SEED.read_text(encoding="utf-8"))
    for scenario in seed["scenarios"]:
        if scenario["name"] == name:
            return DealInputs.model_validate(scenario["inputs"])
    raise KeyError(name)


@pytest.fixture(scope="session")
def cypress_main() -> DealInputs:
    return load_scenario("Main")


@pytest.fixture(scope="session")
def cypress_acreage(cypress_main: DealInputs) -> Acreage:
    return compute_netouts(cypress_main.tract, effective_lookups(cypress_main.lookups))
