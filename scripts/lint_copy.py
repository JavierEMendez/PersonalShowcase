#!/usr/bin/env python3
"""Fail on em dashes and banned phrases in text, markdown, and HTML files.

Usage: python scripts/lint_copy.py README.md docs/*.md app/templates/*.html
"""

import re
import sys

BANNED = [
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
    (r"(?<!<)!(?=[\s\"'\)]|$)", "exclamation point"),
]


def main(paths):
    failures = 0
    for path in paths:
        try:
            text = open(path, encoding="utf-8").read()
        except OSError as exc:
            print(f"{path}: {exc}")
            failures += 1
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if "lint-ignore" in line:
                continue
            for pattern, label in BANNED:
                if re.search(pattern, line, flags=re.IGNORECASE):
                    print(f"{path}:{lineno}: {label}: {line.strip()[:100]}")
                    failures += 1
    if failures:
        print(f"{failures} issue(s)")
        return 1
    print("copy lint passed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
