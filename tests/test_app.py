"""Smoke tests for the web layer: every route renders and the stylesheet is served."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_landing_renders() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Mendez Valdez" in response.text
    assert "Cypress Ridge" in response.text
    assert "Harbor Point Industrial" in response.text
    assert "/static/site.css" in response.text


@pytest.mark.parametrize(
    ("path", "title", "pill"),
    [
        ("/underwriting", "Cypress Ridge", "Lower lot price"),
        ("/copilot", "Harbor Point Industrial", "Downside"),
    ],
)
def test_tool_stubs_render(path: str, title: str, pill: str) -> None:
    response = client.get(path)
    assert response.status_code == 200
    assert title in response.text
    assert pill in response.text
    # Eight summary cells, one per figure in the strip.
    assert response.text.count('class="kpi"') == 8


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_stylesheet_served() -> None:
    response = client.get("/static/site.css")
    assert response.status_code == 200
    assert "--accent: #0F2A44" in response.text
