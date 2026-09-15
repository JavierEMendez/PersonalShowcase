"""The Land Underwriting screens render, recalculate on edits, switch scenarios, and export."""

import re
from urllib.parse import unquote

from fastapi.testclient import TestClient

from app.main import app


def new_client() -> TestClient:
    return TestClient(app)


def test_performance_renders_fixture_figures() -> None:
    client = new_client()
    page = client.get("/underwriting").text
    assert "Cypress Ridge" in page
    assert "Financial summary" in page
    assert "Sensitivity" in page
    assert "Net cash flow by year" in page
    assert page.count('class="kpi"') == 8
    # Headline figures from the fixture.
    assert "17.4%" in page
    assert "$379.1M" in page
    assert "2,380 lots delivered" in page
    # Three seeded scenarios and a comparison panel.
    assert "Faster pace" in page and "Lower lot price" in page
    assert "Scenario comparison" in page


def test_every_tab_renders() -> None:
    client = new_client()
    for tab in ("tract", "costs", "revenue", "cashflows", "lookups"):
        response = client.get(f"/underwriting/{tab}")
        assert response.status_code == 200, tab
        assert 'id="tab-body"' in response.text or tab == "cashflows"
    assert client.get("/underwriting/nonsense").status_code == 422


def test_sensitivity_partial_changes_axes() -> None:
    client = new_client()
    response = client.get(
        "/underwriting/sensitivity?row_axis=yield&col_axis=home_price&metric=gross_margin&row_steps=3&col_steps=1"
    )
    assert response.status_code == 200
    assert "Sensitivity · Gross margin" in response.text
    assert response.text.count("<tr>") == 1 + 7  # header row plus seven value rows
    assert "+5%" in response.text and "-5%" in response.text


def test_edit_recalculates_within_the_session() -> None:
    client = new_client()
    before = client.get("/underwriting").text
    response = client.post(
        "/underwriting/inputs/tract",
        data={"tract.gross_acreage": "700"},
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 200
    assert 'hx-swap-oob="true"' in response.text  # summary strip comes back out of band
    assert 'id="tab-body"' in response.text
    after = client.get("/underwriting").text
    assert "700.0 ac" in after
    revenue_before = re.search(r'Total revenue</div><div class="figure num">([^<]+)', before)
    revenue_after = re.search(r'Total revenue</div><div class="figure num">([^<]+)', after)
    assert revenue_before and revenue_after and revenue_before.group(1) != revenue_after.group(1)
    # A fresh browser still sees the seed.
    assert "640.0 ac" in new_client().get("/underwriting").text


def test_bad_edit_shows_error_and_keeps_inputs() -> None:
    client = new_client()
    response = client.post(
        "/underwriting/inputs/revenue",
        data={"revenue.price_per_ff.0": "abc"},
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 200
    assert 'class="errors"' in response.text
    assert "17.4%" in client.get("/underwriting").text


def test_scenarios_add_rename_delete_reset() -> None:
    client = new_client()
    added = client.post(
        "/underwriting/scenarios/add",
        data={"source": "Main", "name": "Test case"},
        follow_redirects=False,
    )
    assert added.status_code == 303
    assert unquote(added.headers["location"]) == "/underwriting?scenario=Test case"
    page = client.get("/underwriting?scenario=Test%20case").text
    assert '<span class="pill active">Test case</span>' in page
    renamed = client.post(
        "/underwriting/scenarios/rename",
        data={"name": "Test case", "new_name": "Main"},
        follow_redirects=False,
    )
    assert unquote(renamed.headers["location"]) == "/underwriting?scenario=Main 2"  # unique names
    client.post("/underwriting/scenarios/delete", data={"name": "Main 2"})
    assert "Main 2" not in client.get("/underwriting").text
    client.post("/underwriting/inputs/tract", data={"tract.gross_acreage": "700"})
    client.post("/underwriting/scenarios/reset")
    assert "640.0 ac" in client.get("/underwriting").text


def test_inputs_show_separators_and_accept_them() -> None:
    client = new_client()
    page = client.get("/underwriting/costs").text
    assert 'name="costs.personnel_monthly" value="50,000"' in page
    assert 'type="number"' not in page
    response = client.post("/underwriting/inputs/costs", data={"costs.personnel_monthly": "55,000"})
    assert response.status_code == 200
    assert 'name="costs.personnel_monthly" value="55,000"' in response.text
    assert "was not applied" not in response.text
    client.post("/underwriting/scenarios/reset")


def test_memo_deck_downloads_for_a_scenario() -> None:
    client = new_client()
    response = client.get("/underwriting/memo.pdf?scenario=Faster%20pace")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert (
        'filename="cypress-ridge-ic-memo-faster-pace.pdf"'
        in response.headers["content-disposition"]
    )
    assert response.content.startswith(b"%PDF")
