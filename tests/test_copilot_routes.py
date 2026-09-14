"""The Multifamily Copilot underwrite screen renders every case and exports."""

import io

from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app.main import app

client = TestClient(app)


def test_underwrite_renders_base_case() -> None:
    page = client.get("/copilot").text
    assert "Sawyer Bend Apartments" in page
    assert page.count('class="kpi"') == 8
    for panel in (
        "Net operating income",
        "Rent roll",
        "Renovation program",
        "Extracted assumptions",
        "Sources and uses",
        "What breaks it",
        "IC memo",
        "Waterfall",
        "Monitor",
        "Case comparison",
    ):
        assert panel in page, panel
    assert '<span class="pill active">Base</span>' in page
    assert "Recommendation: bid $46.0M" in page
    assert "Do not pursue at the $50.5M ask" in page
    assert "What the model cannot tell you" in page
    assert "Show all 15" in page


def test_cases_switch() -> None:
    downside = client.get("/copilot?case=Downside").text
    assert '<span class="pill active">Downside</span>' in downside
    assert "Recommendation: pass at $46.0M" in downside  # below the 12% threshold
    lender = client.get("/copilot?case=Lender").text
    assert '<span class="pill active">Lender</span>' in lender
    assert "55.0%" in lender
    assert '<span class="pill active">Base</span>' in client.get("/copilot?case=Nope").text


def test_export_per_case() -> None:
    response = client.get("/copilot/export.xlsx?case=Lender")
    assert response.status_code == 200
    assert 'filename="sawyer-bend-lender.xlsx"' in response.headers["content-disposition"]
    wb = load_workbook(io.BytesIO(response.content))
    assert "Summary" in wb.sheetnames and "Waterfall" in wb.sheetnames
