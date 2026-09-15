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
    assert "Recommendation: bid no more than $43.7M" in page
    assert "Floor 15% · max bid $43.7M" in page
    assert "What the model cannot tell you" in page
    assert "Show all 15" in page


def test_cases_switch() -> None:
    downside = client.get("/copilot?case=Downside").text
    assert '<span class="pill active">Downside</span>' in downside
    assert "Recommendation: pass." in downside  # no bid within 20% of the ask clears the floor
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


def test_screen_flow_from_sample_documents_to_screened_case() -> None:
    session = TestClient(app)
    page = session.get("/copilot/screen").text
    assert "What the documents leave open" in page and "Use the sample documents" in page
    assert "Not loaded" in page
    response = session.post("/copilot/screen/sample", follow_redirects=False)
    assert response.status_code == 303 and response.headers["location"] == "/copilot/screen"
    page = session.get("/copilot/screen").text
    assert "sawyer-bend-om.pdf" in page and "15 of 15 found" in page
    assert "Asking price $50,500,000" in page  # the quote
    assert "Unit mix from the documents" in page
    # Accept every default, then override two answers the way an analyst would.
    form = {
        "operating.controllable_per_unit": "3,850",
        "operating.per_unit.Insurance": "850",
        "loan.ltv_max": "60",
    }
    response = session.post("/copilot/screen/answers", data=form, follow_redirects=False)
    assert response.status_code == 303 and response.headers["location"] == "/copilot?case=Screened"
    underwrite = session.get("/copilot?case=Screened").text
    assert '<span class="pill active">Screened</span>' in underwrite
    assert "From Screen · 15 of 15 sourced" in underwrite
    assert "60.0%" in underwrite  # the LTV answer flowed into the loan
    export = session.get("/copilot/export.xlsx?case=Screened")
    assert export.status_code == 200 and "screened" in export.headers["content-disposition"]
    # A fresh browser does not see the screened case.
    assert "Screened" not in client.get("/copilot").text


def test_upload_rejects_bad_files_and_reads_good_ones() -> None:
    session = TestClient(app)
    response = session.post(
        "/copilot/screen/upload",
        files={"om": ("deal.pdf", b"not a pdf", "application/pdf")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    page = session.get("/copilot/screen").text
    assert "is not a PDF" in page
    assert "is not a PDF" not in session.get("/copilot/screen").text  # errors show once
    t12 = client.get("/copilot/screen/sample/sawyer-bend-t12.xlsx")
    assert t12.status_code == 200 and t12.content.startswith(b"PK")
    session.post(
        "/copilot/screen/upload",
        files={"t12": ("my-t12.xlsx", t12.content, "application/octet-stream")},
    )
    page = session.get("/copilot/screen").text
    assert "my-t12.xlsx" in page and "Other income" in page
    assert client.get("/copilot/screen/sample/../secret").status_code in (400, 404)
    session.post("/copilot/screen/reset")
    assert "Not loaded" in session.get("/copilot/screen").text


def test_memo_draft_and_download() -> None:
    session = TestClient(app)
    page = session.get("/copilot?case=Lender").text
    assert "IC memo · sentence template" in page
    assert "Recommendation: pass." in page
    response = session.post("/copilot/memo?case=Lender", follow_redirects=False)
    assert response.status_code == 303 and response.headers["location"].endswith("case=Lender#memo")
    page = session.get("/copilot?case=Lender").text
    assert "Recommendation: pass." in page  # template writer without an API key
    md = session.get("/copilot/memo.md?case=Lender")
    assert md.status_code == 200 and md.text.startswith(
        "# Sawyer Bend Apartments: investment committee memo (Lender case)"
    )
    assert 'filename="sawyer-bend-memo-lender.md"' in md.headers["content-disposition"]
