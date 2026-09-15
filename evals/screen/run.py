"""Run the Screen eval on the synthetic Sawyer Bend package.

    python -m evals.screen.run                # rule reader for the OM (no API key needed)
    python -m evals.screen.run --reader claude  # Claude API reads the OM; needs ANTHROPIC_API_KEY

Exit code 0 when every figure passes. The rent roll and T-12 are parsed deterministically in both
modes; the reader choice only changes who reads the offering memorandum.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from core.copilot.documents import Document, Kind, read_document
from core.copilot.screen import ClaudeReader, OMReader, RuleReader, screen
from evals.screen.score import score

ROOT = Path(__file__).resolve().parents[2]
SAMPLE_DIR = ROOT / "data" / "sawyer_bend"
SAMPLE_FILES: dict[Kind, str] = {
    "om": "sawyer-bend-om.pdf",
    "rent_roll": "sawyer-bend-rent-roll.xlsx",
    "t12": "sawyer-bend-t12.xlsx",
}


def load_sample() -> dict[str, Document]:
    return {
        kind: read_document(kind, name, (SAMPLE_DIR / name).read_bytes())
        for kind, name in SAMPLE_FILES.items()
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reader", choices=["rules", "claude"], default="rules")
    parser.add_argument("--model", default=None, help="model id for --reader claude")
    args = parser.parse_args(argv)
    reader: OMReader
    if args.reader == "claude":
        if not ClaudeReader.available():
            print("ANTHROPIC_API_KEY is not set.", file=sys.stderr)
            return 2
        reader = ClaudeReader(model=args.model)
    else:
        reader = RuleReader()
    result = screen(load_sample(), reader)
    report = score(result)
    print(f"reader: {result.reader}")
    print(report.table())
    for note in result.notes:
        print(f"note: {note}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
