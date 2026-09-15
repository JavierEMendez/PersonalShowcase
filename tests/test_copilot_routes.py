"""The Multifamily Screening Tool: Screen to Underwrite to Recommend, memos and the deck."""

import io

from fastapi.testclient import TestClient
from openpyxl import load_workbook
from pypdf import PdfReader

from app.main import app

client = TestClient(app)


def test_entry_starts_at_screen() -> None:
    response = client.get("/copilot", follow_redirects=False)
    assert response.status_code == 307 and response.headers["location"] == "/copilot/screen"
    page = client.get("/copilot/screen").text
    assert "Multifamily Screening Tool" in page and "Use the sample documents" in page


def test_underwrite_renders_base_case_without_the_memo() -> None:
    page = client.get("/copilot/underwrite").text
    assert "Sawyer Bend Apartments" in page
    assert page.count('class="kpi"') == 8
    for panel in (
        "Net operating income",
        "Rent roll",
        "Renovation program",
        "Extracted assumptions",
        "Sources and uses",
        "What breaks it",
        "Waterfall",
        "Market context",
        "Case comparison",
    ):
        assert panel in page, panel
    assert "IC memo ·" not in page and "Monitor · covenant" not in page
    assert "View recommendation" in page and "/copilot/recommend?case=Base" in page
    assert "Range $40.4M to $46.0M at 17% to 13%" in page
    assert '<span class="pill active">Base</span>' in page
    assert "Show all 15" in page


def test_recommend_page_shows_the_range_and_the_memo() -> None:
    page = client.get("/copilot/recommend?case=Base").text
    assert "Valuation range" in page
    for label in ("Low", "Mid", "Max", "Ask"):
        assert f'<div class="range-label">{label}</div>' in page
    assert "$40.4M" in page and "$43.7M" in page and "$46.0M" in page and "$50.5M" in page
    assert "20% below ask" in page and "LP IRR 15%" in page and "LP IRR 13%" in page
    assert (
        "Recommendation: worth a full underwriting only if the seller engages at or below $46.0M"
        in page
    )
    assert "What the model cannot tell you" in page
    assert "Market context" in page and "What breaks it" in page
    assert "Draft the Memo" in page and "Download IC Memo" in page


def test_cases_switch() -> None:
    downside = client.get("/copilot/recommend?case=Downside").text
    assert '<span class="pill active">Downside</span>' in downside
    assert "at or below $38.2M" in downside
    lender = client.get("/copilot/underwrite?case=Lender").text
    assert '<span class="pill active">Lender</span>' in lender
    assert "55.0%" in lender
    assert (
        '<span class="pill active">Base</span>' in client.get("/copilot/underwrite?case=Nope").text
    )


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
    form = {
        "operating.controllable_per_unit": "3,850",
        "operating.per_unit.Insurance": "850",
        "loan.ltv_max": "60",
    }
    response = session.post("/copilot/screen/answers", data=form, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/copilot/underwrite?case=Screened"
    underwrite = session.get("/copilot/underwrite?case=Screened").text
    assert '<span class="pill active">Screened</span>' in underwrite
    assert "From Screen · 15 of 15 sourced" in underwrite
    assert "60.0%" in underwrite  # the LTV answer flowed into the loan
    # The screened case is the default once it exists.
    assert '<span class="pill active">Screened</span>' in session.get("/copilot/recommend").text
    deck = session.get("/copilot/memo.pdf?case=Screened")
    assert deck.status_code == 200 and "screened" in deck.headers["content-disposition"]
    assert len(PdfReader(io.BytesIO(deck.content)).pages) == 3
    # A fresh browser does not see the screened case.
    assert "Screened" not in client.get("/copilot/underwrite").text


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
    assert load_workbook(io.BytesIO(t12.content)).sheetnames == ["T-12"]
    session.post(
        "/copilot/screen/upload",
        files={"t12": ("my-t12.xlsx", t12.content, "application/octet-stream")},
    )
    page = session.get("/copilot/screen").text
    assert "my-t12.xlsx" in page and "Other income" in page
    assert client.get("/copilot/screen/sample/../secret").status_code in (400, 404)
    session.post("/copilot/screen/reset")
    assert "Not loaded" in session.get("/copilot/screen").text


def test_memo_draft_and_downloads() -> None:
    session = TestClient(app)
    page = session.get("/copilot/recommend?case=Lender").text
    assert "Recommendation · sentence template" in page
    assert "at or below $40.5M" in page
    response = session.post("/copilot/memo?case=Lender", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/copilot/recommend?case=Lender"
    md = session.get("/copilot/memo.md?case=Lender")
    assert md.status_code == 200
    assert md.text.startswith("# Sawyer Bend Apartments: screening memo (Lender case)")
    pdf = session.get("/copilot/memo.pdf?case=Base")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert 'filename="sawyer-bend-screening-memo-base.pdf"' in pdf.headers["content-disposition"]
    reader = PdfReader(io.BytesIO(pdf.content))
    assert len(reader.pages) == 2
    page1 = reader.pages[0].extract_text()
    assert "VALUATION RANGE" in page1 and "Multifamily Screening Tool" in page1
    assert "$40.4M" in page1 and "$46.0M" in page1
