"""Multifamily Copilot routes: the Screen intake, the underwrite screen, cases and export."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import quote

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    RedirectResponse,
    Response,
    StreamingResponse,
)
from pydantic import BaseModel, ValidationError

from app.deals import DATA_DIR
from app.sessions import SessionStore, set_session_cookie
from app.templating import render
from core.copilot import screen as screening
from core.copilot.documents import (
    KIND_LABELS,
    MAX_BYTES,
    Document,
    DocumentError,
    Kind,
    read_document,
)
from core.copilot.engine import run
from core.copilot.excel import export_workbook
from core.copilot.inputs import CopilotInputs
from core.copilot.memo import ClaudeWriter, Memo, TemplateWriter, build_facts, write_memo
from core.copilot.screen import ClaudeReader, Question, RuleReader, ScreenResult
from core.copilot.sensitivity import at_price, stress_table
from core.copilot.summary import CopilotOutputs

router = APIRouter(prefix="/copilot")

SAMPLE_DIR: Path = DATA_DIR / "sawyer_bend"
SAMPLE_FILES: dict[Kind, str] = {
    "om": "sawyer-bend-om.pdf",
    "rent_roll": "sawyer-bend-rent-roll.xlsx",
    "t12": "sawyer-bend-t12.xlsx",
}
SCREENED = "Screened"


class Case(BaseModel):
    name: str
    inputs: CopilotInputs


def _load() -> tuple[dict[str, Any], list[Case], list[dict[str, str]]]:
    raw = json.loads((DATA_DIR / "sawyer_bend.json").read_text(encoding="utf-8"))
    cases = [
        Case(name=c["name"], inputs=CopilotInputs.model_validate(c["inputs"])) for c in raw["cases"]
    ]
    meta = {k: raw[k] for k in ("name", "status", "location", "facts")}
    return meta, cases, raw["assumptions"]


META, CASES, ASSUMPTIONS = _load()
STEPS: list[tuple[str, str]] = [
    ("Screen", "/copilot/screen"),
    ("Underwrite", "/copilot"),
    ("Recommend", "/copilot#memo"),
    ("Monitor", "/copilot#monitor"),
]
THRESHOLD_IRR = 0.12
MONTHS_IN = 6  # the Monitor panel reports the second quarter after closing

COMPARE_METRICS: list[tuple[str, str, str]] = [
    ("Levered IRR", "levered_irr", "pct"),
    ("Unlevered IRR", "unlevered_irr", "pct"),
    ("Equity multiple", "equity_multiple", "mult"),
    ("LP IRR", "lp_irr", "pct"),
    ("Going-in cap", "going_in_cap", "pct2"),
    ("Year 1 NOI", "noi_year1", "money_m"),
    ("Loan", "loan_amount", "money_m"),
    ("LTV", "ltv", "pct"),
    ("Debt yield", "debt_yield", "pct"),
    ("DSCR, year 1", "dscr_year1", "mult"),
    ("Minimum DSCR", "min_dscr", "mult"),
    ("Exit value", "exit_value", "money_m"),
]


# --------------------------------------------------------------------------------------------
# Session
# --------------------------------------------------------------------------------------------
@dataclass
class CopilotSession:
    documents: dict[str, Document] = field(default_factory=dict)
    result: ScreenResult | None = None
    answers: dict[str, float] = field(default_factory=dict)
    screened: CopilotInputs | None = None
    memos: dict[str, Memo] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    updated: float = field(default_factory=time.time)

    def touch(self) -> None:
        self.updated = time.time()

    def cases(self) -> list[Case]:
        cases = list(CASES)
        if self.screened is not None:
            cases.append(Case(name=SCREENED, inputs=self.screened))
        return cases

    def case_named(self, name: str | None) -> Case:
        for case in self.cases():
            if case.name == name:
                return case
        return CASES[0]


store: SessionStore[CopilotSession] = SessionStore(CopilotSession)


def _reader() -> screening.OMReader:
    return ClaudeReader() if ClaudeReader.available() else RuleReader()


# --------------------------------------------------------------------------------------------
# Figures for the templates
# --------------------------------------------------------------------------------------------
def pct(v: float | None, d: int = 1) -> str:
    return "n/a" if v is None else f"{v * 100:.{d}f}%"


def money_m(v: float, d: int = 1) -> str:
    return f"${v / 1e6:.{d}f}M"


def mult(v: float | None) -> str:
    return "n/a" if v is None else f"{v:.2f}×"


def _row(
    test: str, covenant: str, underwritten: str, actual: str, cushion: str, status: str, ok: bool
) -> dict[str, Any]:
    return {
        "test": test,
        "covenant": covenant,
        "underwritten": underwritten,
        "actual": actual,
        "cushion": cushion,
        "status": status,
        "ok": ok,
    }


def monitor_rows(out: CopilotOutputs) -> list[dict[str, Any]]:
    """A synthetic quarter of actuals, two quarters after closing, tested against underwriting."""
    s, ln, reno = out.summary, out.loan, out.renovation
    dscr_uw = s.dscr_year1 or 0.0
    dscr_actual = dscr_uw + 0.03
    dy_actual = s.debt_yield + 0.002
    occupancy_uw, occupancy_actual, occupancy_min = 0.94, 0.948, 0.85
    months_active = max(0, MONTHS_IN - reno.start_month + 1)
    planned = round(min(reno.units, reno.pace_per_month * months_active))
    actual_units = max(0, planned - 3)
    io_left = ln.io_months - MONTHS_IN
    return [
        _row(
            "DSCR",
            mult(ln.covenant_dscr),
            mult(dscr_uw),
            mult(dscr_actual),
            mult(dscr_actual - ln.covenant_dscr),
            "In compliance",
            dscr_actual >= ln.covenant_dscr,
        ),
        _row(
            "Debt yield",
            "7.5%",
            pct(s.debt_yield),
            pct(dy_actual),
            f"{round((dy_actual - 0.075) * 10_000)} bps",
            "In compliance",
            dy_actual >= 0.075,
        ),
        _row(
            "Occupancy",
            pct(occupancy_min),
            pct(occupancy_uw),
            pct(occupancy_actual),
            f"{round((occupancy_actual - occupancy_min) * 10_000):,} bps",
            "In compliance",
            True,
        ),
        _row(
            "Renovations completed",
            "",
            f"{planned} of {reno.units}",
            f"{actual_units} of {reno.units}",
            f"({planned - actual_units}) units",
            "Behind plan",
            False,
        ),
        _row(
            "Interest-only expiry",
            ln.io_expiry.strftime("%B %Y"),
            "",
            f"{io_left} months",
            "",
            f"Amortization begins in {io_left} months",
            True,
        ),
        _row(
            "Loan maturity",
            ln.maturity.strftime("%B %Y"),
            "",
            f"{ln.term_months - MONTHS_IN} months",
            "",
            "Refinance review at 60 months",
            True,
        ),
    ]


def compare_rows(outputs: dict[str, CopilotOutputs]) -> list[tuple[str, list[str]]]:
    rows: list[tuple[str, list[str]]] = []
    for label, key, fmt in COMPARE_METRICS:
        values: list[str] = []
        for out in outputs.values():
            v: Any = out.loan.amount if key == "loan_amount" else getattr(out.summary, key)
            if fmt == "pct":
                values.append(pct(v))
            elif fmt == "pct2":
                values.append(pct(v, 2))
            elif fmt == "mult":
                values.append(mult(v))
            else:
                values.append(money_m(v))
        rows.append((label, values))
    return rows


def assumption_rows(result: ScreenResult | None) -> tuple[list[dict[str, str]], str]:
    """The Extracted assumptions panel: live from the session's Screen when there is one."""
    if result is None:
        return ASSUMPTIONS, f"Seeded · {len(ASSUMPTIONS)} of {len(ASSUMPTIONS)} sourced"
    rows = [
        {
            "assumption": e.label,
            "value": e.display(),
            "source": f"{e.document} {e.page}".strip(),
            "confidence": e.confidence,
        }
        for e in result.extractions
        if not e.plan
    ]
    found = sum(1 for e in result.extractions if not e.plan and e.value is not None)
    return (
        rows,
        f"From Screen · {found} of {len(screening.FIELDS)} sourced · read by {result.reader}",
    )


# --------------------------------------------------------------------------------------------
# Underwrite
# --------------------------------------------------------------------------------------------
def _redirect(request: Request, url: str, sid: str | None) -> Response:
    response = RedirectResponse(url, status_code=303)
    set_session_cookie(response, sid)
    return response


@router.get("", response_class=HTMLResponse)
async def underwrite(request: Request, case: str | None = None) -> Response:
    session, sid = store.load(request)
    current = session.case_named(case)
    out = run(current.inputs)
    acq = current.inputs.acquisition
    ask = run(at_price(current.inputs, acq.asking_price or acq.purchase_price))
    stress = stress_table(current.inputs)
    outputs = {c.name: run(c.inputs) for c in session.cases()}
    assumptions, assumptions_note = assumption_rows(session.result)
    facts = build_facts(out, ask, stress, current.name, THRESHOLD_IRR, session.result)
    memo = session.memos.get(current.name) or write_memo(facts, TemplateWriter())
    response = render(
        request,
        "copilot/underwrite.html",
        meta=META,
        cases=[c.name for c in session.cases()],
        case=current.name,
        steps=STEPS,
        active_step=2,
        out=out,
        ask=ask,
        stress=stress,
        assumptions=assumptions,
        assumptions_note=assumptions_note,
        memo=memo,
        memo_live=ClaudeWriter.available(),
        monitor=monitor_rows(out),
        compare=compare_rows(outputs),
        compare_names=list(outputs),
        threshold=THRESHOLD_IRR,
        query=f"?case={quote(current.name)}",
    )
    set_session_cookie(response, sid)
    return response


@router.post("/memo")
async def draft_memo(request: Request, case: str | None = None) -> Response:
    """Draft the IC memo for a case with the configured writer and keep it in the session."""
    session, sid = store.load(request)
    current = session.case_named(case)
    memo = write_memo(_facts(session, current))
    session.memos[current.name] = memo
    return _redirect(request, f"/copilot?case={quote(current.name)}#memo", sid)


@router.get("/memo.md")
async def memo_markdown(request: Request, case: str | None = None) -> Response:
    session, sid = store.load(request)
    current = session.case_named(case)
    memo = session.memos.get(current.name) or write_memo(_facts(session, current), TemplateWriter())
    filename = f"sawyer-bend-memo-{current.name.lower()}.md"
    response = Response(
        memo.markdown(META["name"]),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
    set_session_cookie(response, sid)
    return response


def _facts(session: CopilotSession, current: Case) -> Any:
    out = run(current.inputs)
    acq = current.inputs.acquisition
    ask = run(at_price(current.inputs, acq.asking_price or acq.purchase_price))
    return build_facts(
        out, ask, stress_table(current.inputs), current.name, THRESHOLD_IRR, session.result
    )


@router.get("/export.xlsx")
async def export(request: Request, case: str | None = None) -> Response:
    session, sid = store.load(request)
    current = session.case_named(case)
    workbook = export_workbook(current.inputs, run(current.inputs), current.name)
    filename = f"sawyer-bend-{current.name.lower()}.xlsx"
    response = StreamingResponse(
        iter([workbook]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
    set_session_cookie(response, sid)
    return response


# --------------------------------------------------------------------------------------------
# Screen
# --------------------------------------------------------------------------------------------
def _grouped(asked: list[Question]) -> list[tuple[str, list[Question]]]:
    groups: dict[str, list[Question]] = {}
    for q in asked:
        groups.setdefault(q.group, []).append(q)
    return list(groups.items())


@router.get("/screen", response_class=HTMLResponse)
async def screen_page(request: Request) -> Response:
    session, sid = store.load(request)
    base = CASES[0].inputs
    asked = screening.questions(base, session.result)
    figures = [e for e in (session.result.extractions if session.result else []) if not e.plan]
    plans = session.result.plans if session.result else []
    response = render(
        request,
        "copilot/screen.html",
        meta=META,
        steps=STEPS,
        active_step=1,
        documents=session.documents,
        kinds=[(k, KIND_LABELS[k], SAMPLE_FILES[k]) for k in ("om", "rent_roll", "t12")],
        result=session.result,
        figures=figures,
        plans=plans,
        catalogue=len(screening.FIELDS),
        groups=_grouped(asked),
        errors=session.errors,
        screened=session.screened is not None,
        reader_live=ClaudeReader.available(),
        max_mb=MAX_BYTES // (1024 * 1024),
    )
    session.errors = []
    set_session_cookie(response, sid)
    return response


def _run_screen(session: CopilotSession) -> None:
    session.result = screening.screen(session.documents, _reader()) if session.documents else None
    session.screened = None
    session.answers = {}


@router.post("/screen/upload")
async def upload(
    request: Request,
    om: Annotated[UploadFile | None, File()] = None,
    rent_roll: Annotated[UploadFile | None, File()] = None,
    t12: Annotated[UploadFile | None, File()] = None,
) -> Response:
    session, sid = store.load(request)
    errors: list[str] = []
    received = 0
    for kind, upload_file in (("om", om), ("rent_roll", rent_roll), ("t12", t12)):
        if upload_file is None or not upload_file.filename:
            continue
        data = await upload_file.read(MAX_BYTES + 1)
        try:
            session.documents[kind] = read_document(kind, upload_file.filename, data)  # type: ignore[arg-type]
            received += 1
        except DocumentError as exc:
            errors.append(str(exc))
    if received == 0 and not errors:
        errors.append("Choose at least one file.")
    if received:
        try:
            _run_screen(session)
        except Exception as exc:  # the reader is a network call when the API is configured
            errors.append(f"The documents were read but extraction failed: {exc}")
            session.result = None
    session.errors = errors
    return _redirect(request, "/copilot/screen", sid)


@router.post("/screen/sample")
async def use_sample(request: Request) -> Response:
    session, sid = store.load(request)
    for kind, name in SAMPLE_FILES.items():
        session.documents[kind] = read_document(kind, name, (SAMPLE_DIR / name).read_bytes())
    try:
        _run_screen(session)
    except Exception as exc:
        session.errors = [f"The documents were read but extraction failed: {exc}"]
        session.result = None
    return _redirect(request, "/copilot/screen", sid)


@router.get("/screen/sample/{name}")
async def sample_file(name: str) -> Response:
    if name not in SAMPLE_FILES.values():
        return Response(status_code=404)
    return FileResponse(SAMPLE_DIR / name, filename=name)


@router.post("/screen/answers")
async def answers(request: Request) -> Response:
    session, sid = store.load(request)
    form = await request.form()
    fields = {k: str(v) for k, v in form.items() if isinstance(v, str)}
    base = CASES[0].inputs
    asked = screening.questions(base, session.result)
    parsed, errors = screening.answers_from_form(fields, asked)
    if not errors:
        try:
            session.screened = screening.apply_screen(base, session.result, parsed)
            session.memos.pop(SCREENED, None)
            session.answers = parsed
        except ValidationError as exc:
            errors = [e.get("msg", "invalid") for e in exc.errors()]
    if errors:
        session.errors = errors
        return _redirect(request, "/copilot/screen", sid)
    return _redirect(request, f"/copilot?case={SCREENED}", sid)


@router.post("/screen/reset")
async def reset(request: Request) -> Response:
    store.reset(request)
    return _redirect(request, "/copilot/screen", None)
