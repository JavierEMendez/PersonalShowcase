"""The copy linter passes on every template and public doc."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_copy_lint_passes() -> None:
    targets = [
        *sorted((ROOT / "app" / "templates").rglob("*.html")),
        *sorted((ROOT / "docs").glob("*.md")),
        ROOT / "README.md",
        ROOT / "CLAUDE.md",
    ]
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "lint_copy.py"), *map(str, targets)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout
