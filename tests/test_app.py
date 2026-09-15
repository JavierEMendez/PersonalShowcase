"""Smoke tests for the web layer: every route renders and the stylesheet is served."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_landing_renders() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Javier Mendez" in response.text
    assert "Cypress Ridge" in response.text
    assert "Sawyer Bend Apartments" in response.text
    assert "/static/site.css" in response.text


@pytest.mark.parametrize(
    ("path", "title", "pill"),
    [
        ("/underwriting", "Cypress Ridge", "Lower lot price"),
        ("/copilot/underwrite", "Sawyer Bend Apartments", "Downside"),
    ],
)
def test_tool_stubs_render(path: str, title: str, pill: str) -> None:
    response = client.get(path)
    assert response.status_code == 200
    assert title in response.text
    assert pill in response.text
    # Eight summary cells, one per figure in the strip.
    assert response.text.count('class="kpi"') == 8


def test_about_page_has_bio_and_portrait() -> None:
    response = client.get("/about")
    assert response.status_code == 200
    assert "Javier Mendez" in response.text
    assert "/static/headshot.png" in response.text
    assert "Baylor University" in response.text
    assert "<title>Javier Mendez · About</title>" in response.text


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_stylesheet_served() -> None:
    response = client.get("/static/site.css")
    assert response.status_code == 200
    assert "--accent: #0F2A44" in response.text


def test_brand_assets_and_titles() -> None:
    manifest = client.get("/static/brand/site.webmanifest")
    assert manifest.status_code == 200
    assert manifest.headers["content-type"].startswith("application/manifest+json")
    assert client.get("/static/brand/mark.svg").headers["content-type"].startswith("image/svg+xml")
    assert client.get("/static/brand/favicon.ico").status_code == 200
    landing = client.get("/").text
    assert "<title>Javier Mendez</title>" in landing
    assert 'href="/static/brand/mark.svg" type="image/svg+xml"' in landing
    assert "<title>Javier Mendez · Land Underwriting</title>" in client.get("/underwriting").text
    assert (
        "<title>Javier Mendez · Multifamily Screening Tool</title>"
        in client.get("/copilot/underwrite").text
    )
