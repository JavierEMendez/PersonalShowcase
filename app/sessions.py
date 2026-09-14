"""Per-browser deal sessions.

Editing inputs works in the browser session and saving requires nothing, so scenarios live in
memory keyed by a cookie. Sessions expire after a day of inactivity and the store is capped; a
redeploy resets everyone to the seed deal, which is the intended behaviour for a public demo.
"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field

from fastapi import Request, Response
from pydantic import BaseModel

from core.underwriting.inputs import DealInputs

COOKIE = "sid"
TTL_SECONDS = 24 * 3600
MAX_SESSIONS = 2000


class Scenario(BaseModel):
    name: str
    inputs: DealInputs


@dataclass
class DealSession:
    scenarios: list[Scenario]
    updated: float = field(default_factory=time.time)

    def get(self, name: str | None) -> Scenario:
        for scenario in self.scenarios:
            if scenario.name == name:
                return scenario
        return self.scenarios[0]

    def names(self) -> list[str]:
        return [s.name for s in self.scenarios]

    def unique_name(self, wanted: str) -> str:
        wanted = wanted.strip() or "Scenario"
        name, n = wanted, 2
        while name in self.names():
            name = f"{wanted} {n}"
            n += 1
        return name

    def touch(self) -> None:
        self.updated = time.time()


class SessionStore:
    def __init__(self, seed: list[Scenario]) -> None:
        self._seed = seed
        self._sessions: dict[str, DealSession] = {}

    def fresh(self) -> DealSession:
        return DealSession(scenarios=[s.model_copy(deep=True) for s in self._seed])

    def _evict(self) -> None:
        now = time.time()
        for key in [k for k, v in self._sessions.items() if now - v.updated > TTL_SECONDS]:
            del self._sessions[key]
        while len(self._sessions) > MAX_SESSIONS:
            oldest = min(self._sessions, key=lambda k: self._sessions[k].updated)
            del self._sessions[oldest]

    def load(self, request: Request) -> tuple[DealSession, str | None]:
        """The caller's session and, when one had to be created, the cookie value to set."""
        sid = request.cookies.get(COOKIE)
        session = self._sessions.get(sid) if sid else None
        new_sid: str | None = None
        if session is None or time.time() - session.updated > TTL_SECONDS:
            self._evict()
            new_sid = secrets.token_urlsafe(24)
            session = self.fresh()
            self._sessions[new_sid] = session
        session.touch()
        return session, new_sid

    def reset(self, request: Request) -> None:
        sid = request.cookies.get(COOKIE)
        if sid and sid in self._sessions:
            self._sessions[sid] = self.fresh()


def set_session_cookie(response: Response, sid: str | None) -> None:
    if sid:
        response.set_cookie(
            COOKIE, sid, max_age=TTL_SECONDS, httponly=True, samesite="lax", path="/"
        )
