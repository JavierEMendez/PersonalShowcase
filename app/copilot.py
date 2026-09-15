"""Multifamily Screening Tool routes: Screen, Underwrite, Recommend, and the memo downloads."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import quote

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from pydantic import BaseModel, ValidationError

from app.deals import DATA_DIR
from app.sessions import SessionStore, set_session_cookie
from app.templating import render
from core.benchmarks.context import multifamily_context
from core.copilot import screen as screening
from core.copilot.deck import build_deck
from core.copilot.documents import (
    KIND_LABELS,
    MAX_BYTES,
    Document,
    DocumentError,
    Kind,
    read_document,
)
from core.copilot.engine import run
from core.copilot.inputs import CopilotInputs
from core.copilot.memo import (
    ClaudeWriter,
    Memo,
    MemoFacts,
    TemplateWriter,
    build_facts,
    write_memo,
)
from core.copilot.recommend import LOW_DISCOUNT_CAP, LP_TARGETS, ValuationRange, valuation_range
from core.copilot.screen import ClaudeReader, Question, RuleReader, ScreenResult
from core.copilot.sensitivity import StressRow, stress_table
from core.copilot.summary import CopilotOutputs

router = APIRouter(prefix="/copilot")

PRODUCT = "Multifamily Screening Tool"
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
STEP_NAMES: list[tuple[str, str]] = [
    ("Screen", "/copilot/screen"),
    ("Underwrite", "/copilot/underwrite"),
    ("Recommend", "/copilot/recommend"),
]

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
        """The named case, else the screened case when there is one, else the first seed."""
        for case in self.cases():
            if case.name == name:
                return case
        if name is None and self.screened is not None:
            return Case(name=SCREENED, inputs=self.screened)
        return CASES[0]


store: SessionStore[CopilotSession] = SessionStore(CopilotSession)


def _reader() -> screening.OMReader:
    return ClaudeReader() if ClaudeReader.available() else RuleReader()


def _steps(query: str) -> list[tuple[str, str]]:
    return [(name, href if name == "Screen" else href + query) for name, href in STEP_NAMES]


# --------------------------------------------------------------------------------------------
# Figures for the templates
# --------------------------------------------------------------------------------------------
def pct(v: float | None, d: int = 1) -> str:
    return "n/a" if v is None else f"{v * 100:.{d}f}%"


def money_m(v: float, d: int = 1) -> str:
    return f"${v / 1e6:.{d}f}M"


def mult(v: float | None) -> str:
    return "n/a" if v is None else f"{v:.2f}×"


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


@dataclass
class Analysis:
    """Everything the Recommend step and the downloads need for one case."""

    out: CopilotOutputs
    stress: list[StressRow]
    valuation: ValuationRange
    facts: MemoFacts
    memo: Memo


def analyse(session: CopilotSession, current: Case) -> Analysis:
    out = run(current.inputs)
    stress = stress_table(current.inputs)
    valuation = valuation_range(current.inputs)
    facts = build_facts(out, valuation, stress, current.name, session.result)
    memo = session.memos.get(current.name) or write_memo(facts, TemplateWriter())
    return Analysis(out=out, stress=stress, valuation=valuation, facts=facts, memo=memo)


def _redirect(request: Request, url: str, sid: str | None) -> Response:
    response = RedirectResponse(url, status_code=303)
    set_session_cookie(response, sid)
    return response


def _query(current: Case) -> str:
    return f"?case={quote(current.name)}"


# --------------------------------------------------------------------------------------------
# Entry, Underwrite, Recommend
# --------------------------------------------------------------------------------------------
@router.get("")
async def entry() -> Response:
    """The tool starts at Screen."""
    return RedirectResponse("/copilot/screen", status_code=307)


@router.get("/underwrite", response_class=HTMLResponse)
async def underwrite(request: Request, case: str | None = None) -> Response:
    session, sid = store.load(request)
    current = session.case_named(case)
    query = _query(current)
    out = run(current.inputs)
    stress = stress_table(current.inputs)
    valuation = valuation_range(current.inputs)
    outputs = {c.name: run(c.inputs) for c in session.cases()}
    assumptions, assumptions_note = assumption_rows(session.result)
    response = render(
        request,
        "copilot/underwrite.html",
        meta=META,
        product=PRODUCT,
        cases=[c.name for c in session.cases()],
        case=current.name,
        steps=_steps(query),
        active_step=2,
        out=out,
        stress=stress,
        valuation=valuation,
        targets=LP_TARGETS,
        assumptions=assumptions,
        assumptions_note=assumptions_note,
        compare=compare_rows(outputs),
        compare_names=list(outputs),
        market=multifamily_context(current.inputs, out),
        query=query,
    )
    set_session_cookie(response, sid)
    return response


@router.get("/recommend", response_class=HTMLResponse)
async def recommend(request: Request, case: str | None = None) -> Response:
    session, sid = store.load(request)
    current = session.case_named(case)
    query = _query(current)
    a = analyse(session, current)
    assumptions, assumptions_note = assumption_rows(session.result)
    response = render(
        request,
        "copilot/recommend.html",
        meta=META,
        product=PRODUCT,
        cases=[c.name for c in session.cases()],
        case=current.name,
        steps=_steps(query),
        active_step=3,
        out=a.out,
        stress=a.stress,
        valuation=a.valuation,
        points=a.valuation.points,
        targets=LP_TARGETS,
        low_cap=LOW_DISCOUNT_CAP,
        memo=a.memo,
        memo_live=ClaudeWriter.available(),
        assumptions=assumptions,
        assumptions_note=assumptions_note,
        market=multifamily_context(current.inputs, a.out),
        query=query,
    )
    set_session_cookie(response, sid)
    return response


@router.post("/memo")
async def draft_memo(request: Request, case: str | None = None) -> Response:
    """Draft the memo for a case with the configured writer and keep it in the session."""
    session, sid = store.load(request)
    current = session.case_named(case)
    a = analyse(session, current)
    session.memos[current.name] = write_memo(a.facts)
    return _redirect(request, f"/copilot/recommend{_query(current)}", sid)


@router.get("/memo.md")
async def memo_markdown(request: Request, case: str | None = None) -> Response:
    session, sid = store.load(request)
    current = session.case_named(case)
    memo = analyse(session, current).memo
    filename = f"sawyer-bend-memo-{current.name.lower()}.md"
    response = Response(
        memo.markdown(META["name"]),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
    set_session_cookie(response, sid)
    return response


@router.get("/memo.pdf")
async def memo_deck(request: Request, case: str | None = None) -> Response:
    """The memo as a two- or three-page PDF deck for the case."""
    session, sid = store.load(request)
    current = session.case_named(case)
    a = analyse(session, current)
    assumptions, _ = assumption_rows(session.result)
    screened = session.result if current.name == SCREENED and session.result else None
    documents: list[tuple[str, str, str]] = []
    qa: list[tuple[str, str, str]] = []
    if screened is not None:
        for kind, doc in session.documents.items():
            extent = (
                f"{len(doc.pages)} pages"
                if kind == "om"
                else f"{len([r for r in doc.rows if r])} rows"
            )
            documents.append((KIND_LABELS[kind], doc.filename, extent))
        base = CASES[0].inputs
        for q in screening.questions(base, screened):
            answer = session.answers.get(q.key, q.prefill)
            shown = f"{answer * 100:.2f}%" if q.kind == "pct" else f"{answer:,.4g}"
            source = (
                f"{q.extracted.display()} ({q.extracted.document} {q.extracted.page})"
                if q.extracted
                else ""
            )
            qa.append((q.prompt, source, shown))
    s = a.out.summary
    facts_line = (
        f"{s.units} units · {s.rentable_sf:,.0f} SF · {META['location']} · "
        f"{s.occupancy * 100:.1f}% occupied · {s.hold_months // 12}-year hold"
    )
    pdf = build_deck(
        META["name"],
        facts_line,
        current.name,
        a.out,
        a.memo,
        a.stress,
        assumptions,
        a.valuation,
        screen=screened,
        documents=documents,
        qa=qa,
    )
    filename = f"sawyer-bend-screening-memo-{current.name.lower()}.pdf"
    response = Response(
        pdf,
        media_type="application/pdf",
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
        product=PRODUCT,
        steps=_steps(f"?case={SCREENED}" if session.screened else ""),
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
    session.memos.pop(SCREENED, None)


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
    return _redirect(request, f"/copilot/underwrite?case={SCREENED}", sid)


@router.post("/screen/reset")
async def reset(request: Request) -> Response:
    store.reset(request)
    return _redirect(request, "/copilot/screen", None)
