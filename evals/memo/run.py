"""Run the memo eval over the Sawyer Bend cases.

    python -m evals.memo.run                  # template writer (no API key needed)
    python -m evals.memo.run --writer claude  # Claude API drafts; needs ANTHROPIC_API_KEY

Exit code 0 when every case passes: all figures trace to the engine output, no banned phrases,
the structure holds, and the recommendation agrees with the LP floor test. A model draft that
was rejected and replaced by the template counts as a failure for the model writer.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from core.copilot.engine import run
from core.copilot.inputs import CopilotInputs
from core.copilot.memo import ClaudeWriter, TemplateWriter, Writer, build_facts, write_memo
from core.copilot.sensitivity import at_price, max_price_for_lp_irr, stress_table
from evals.memo.score import score_memo

ROOT = Path(__file__).resolve().parents[2]
SEED = ROOT / "data" / "sawyer_bend.json"


def cases() -> list[tuple[str, CopilotInputs]]:
    raw = json.loads(SEED.read_text(encoding="utf-8"))
    return [(c["name"], CopilotInputs.model_validate(c["inputs"])) for c in raw["cases"]]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--writer", choices=["template", "claude"], default="template")
    parser.add_argument("--model", default=None, help="model id for --writer claude")
    parser.add_argument("--show", action="store_true", help="print each memo")
    args = parser.parse_args(argv)
    writer: Writer
    if args.writer == "claude":
        if not ClaudeWriter.available():
            print("ANTHROPIC_API_KEY is not set.", file=sys.stderr)
            return 2
        writer = ClaudeWriter(model=args.model)
    else:
        writer = TemplateWriter()
    ok = True
    for name, inputs in cases():
        out = run(inputs)
        acq = inputs.acquisition
        ask = run(at_price(inputs, acq.asking_price or acq.purchase_price))
        max_bid = max_price_for_lp_irr(inputs, 0.15)
        at_max = run(at_price(inputs, max_bid)) if max_bid else None
        facts = build_facts(
            out, ask, stress_table(inputs), name, max_bid=max_bid, at_max_bid=at_max
        )
        memo = write_memo(facts, writer)
        report = score_memo(memo, facts)
        ok = ok and report.ok
        print(report.line())
        for p in memo.problems:
            print(f"    draft: {p}")
        if args.show:
            print(memo.markdown("Sawyer Bend Apartments"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
