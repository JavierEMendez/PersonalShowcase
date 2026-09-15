"""The house copy rules, shared by the linter and the memo writer.

No em dashes, no filler verbs, no "it's not X, it's Y" constructions, no exclamation points.
Short declarative sentences; say the number, then what it means.
"""

from __future__ import annotations

import re

BANNED: list[tuple[str, str]] = [
    (r"—", "em dash"),
    (r"\bdelve", "delve"),
    (r"\bleverag(e|es|ed|ing)\b", "leverage as a verb"),
    (r"\brobust\b", "robust"),
    (r"\bseamless(ly)?\b", "seamless"),
    (r"\bunlock(s|ed|ing)?\b", "unlock"),
    (r"\bempower(s|ed|ing)?\b", "empower"),
    (r"\bcutting-edge\b", "cutting-edge"),
    (r"\bgame-changing\b", "game-changing"),
    (r"\bit'?s not [^.]{1,60}, it'?s\b", "'it's not X, it's Y' construction"),
    (r"\bnot just [^.]{1,60}, but\b", "'not just X, but Y' construction"),
    (r", not (a|an|the) \w", "'X, not Y' construction"),
    (r"(?<!<)!(?=[\s\"'\)]|$)", "exclamation point"),
]


def violations(text: str) -> list[str]:
    """Labels of every rule the text breaks, in rule order, once each."""
    found: list[str] = []
    for pattern, label in BANNED:
        if re.search(pattern, text, flags=re.IGNORECASE) and label not in found:
            found.append(label)
    return found
