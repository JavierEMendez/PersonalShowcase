#!/usr/bin/env python3
"""Fail on em dashes and banned phrases in text, markdown, and HTML files.

Usage: python scripts/lint_copy.py README.md docs/*.md app/templates/*.html
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.copy_rules import BANNED  # noqa: E402


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
