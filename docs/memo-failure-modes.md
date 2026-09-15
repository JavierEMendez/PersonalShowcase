# Recommend step: failure modes and what the tool does about them

The Recommend step drafts the investment committee memo. The rule from `CLAUDE.md` is that every
figure in the memo comes from the model output, never from the language model. This is how that
rule is enforced, and the ways a memo can still go wrong. See `core/copilot/memo.py` and
`evals/memo/`.

## How figures are kept honest

The writer never sees a request to write numbers. It receives a facts table (placeholder name,
value, meaning) and writes prose with the names in braces. The code fills the placeholders from
the engine output. Three checks run on every draft before it is shown:

1. **No digits.** Any digit in the writer's prose outside a placeholder rejects the draft. This
   catches the common failure where a model restates a figure from memory, rounds it differently,
   or invents a supporting statistic.
2. **Known placeholders only.** A name that is not in the table rejects the draft.
3. **A second pass on the finished text.** Every number in the filled memo must equal a facts
   value. This guards the template writer and the fill step as much as the model.

A rejected model draft falls back to the sentence template, and the memo carries the rejection
reasons so the reader knows a template was used and why.

## Failure modes

**The model writes a digit anyway.** Observed in testing with the fake client and expected in
production: "year 1", "12 months", "the top 3 risks". The draft is rejected. Common digits have
placeholders (`{year_one}`, `{hold_years}`, `{units}`) and the system prompt lists them; the
fallback covers the rest. Gap: a fallback is a worse memo than a good model draft. The eval
counts fallbacks as failures for the model writer so the rate is visible.

**Lists returned as paragraphs.** Observed on the first live run: the model returned the body
as one paragraph and the cannot section as one string, so the checks counted one sentence and
one item and fell back to the template, which looked to the reader like the button did
nothing. The parser now splits a single string on newlines, bullets and numbering, then on
sentence ends, then on semicolons, and the prompt asks for arrays explicitly. The rejection
banner names the reason when a fallback still happens.

**The recommendation contradicts the model.** A fluent draft that says "pursue" for a deal whose
ask sits above the range is the most dangerous output a memo tool can produce. The engine gives the
verdict (pursue, engage, pass) from where the ask sits against the solved range; the check compares
the recommendation against it and rejects a mismatch. An engage recommendation must name the max
price as the cap and say the deal is worth a full underwriting only below it.

**Missing sections.** The memo must state the three range prices, the return at the ask, and
the covenant floor or breach; the "what the model cannot tell you" section must have three to
five items. Drafts that skip them are rejected. Gap: the check confirms the placeholders are
present, not that the sentence around them is sensible.

**Banned phrases and AI tells.** The same rules as `scripts/lint_copy.py`, now shared from
`core/copy_rules.py`: em dashes, the filler verbs and adjectives on the list, the "it's not X,
it's Y" construction, exclamation points. Question marks are also rejected, since the memo has
no place for rhetorical questions. Gap: "X, not Y" constructions are asked for in the
prompt and not checked mechanically; the template avoids them.

**Direction inverted.** Observed on the first accepted live draft: "the levered LP IRR is 13.0%,
which clears the 15% floor by 200 bps", when it falls 200 bps short. The unsigned cushion
figure invited the error. The figure now carries its direction ("200 bps short of"), the
prompt asks for it in one fixed phrasing, and a check rejects a sentence that says clears or
exceeds about an LP IRR that misses the floor, or short or below about one that clears it.
The same draft opened with "Recommendation: bid lower", echoing the verdict label; drafts
that talk about the verdict or the test instead of the deal are now rejected too.

**Placeholders used with the wrong meaning.** The model can write "{ltv} of the equity" and pass
every check, because the checks are about provenance and structure, not semantics. The facts
table carries a one-line meaning for each placeholder to reduce this, and the eval's `--show`
flag prints the memos for a human read. Gap: no semantic check; a reader is still required.

**Stale memo after inputs change.** Memos are kept per case in the browser session. Re-running
Screen replaces the Screened case and drops its memo; the seeded cases do not change. Gap: an
edit to the Screened inputs in a later build would need the same invalidation.

**Negative returns.** The Downside case has a negative levered IRR at the ask. The facts table
formats it as "-4.8%" and the fidelity check accepts it as a substring match; the template
sentence "the levered IRR falls to -4.8%" reads correctly. A model draft that writes "a loss of
{levered_irr_at_ask}" would double the sign in meaning; not checked.

**Cost and latency.** One request per draft with about thirty facts and a short prompt; a few
hundred output tokens. The template renders in microseconds and is what the page shows until
"Draft IC memo" is pressed.

## Eval

`python -m evals.memo.run` scores the template writer on Base, Downside and Lender (pass by
construction; the run guards the checks themselves). `python -m evals.memo.run --writer claude
--show` scores the model writer and prints the memos. The number to watch is the fallback rate
across cases and, once real deals flow through Screen, across deals.
