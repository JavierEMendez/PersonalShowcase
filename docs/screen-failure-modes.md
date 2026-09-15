# Screen step: failure modes and what the tool does about them

The Screen step reads a broker package (offering memorandum, rent roll, trailing twelve-month
statement), extracts model inputs with citations, and asks about what the documents leave open.
This is the list of ways that goes wrong, observed while building it against the synthetic
Sawyer Bend package and against the shape of real packages, with the mitigation in place or the
gap left. See `core/copilot/screen.py` and `evals/screen/`.

## Documents

**Scanned PDFs with no text layer.** Many OMs are image PDFs. pypdf returns empty pages; the
upload is rejected with a message asking for a text export or OCR. No OCR is bundled.

**Encrypted or malformed PDFs.** Rejected with the reader's error in plain words.

**Spreadsheets with formulas and no cached values.** A workbook saved by a script (as ours are)
carries formulas but no results, so a total column reads as empty. The T-12 parser sums the
twelve month columns itself and never trusts a total; the rent roll parser counts and averages
rows.

**Multiple sheets.** Only the first sheet with data is parsed. A package that puts the rent roll
on the second tab needs the tab exported on its own. Every sheet is still rendered as text for
citations.

**Size and type.** Eight megabytes per file; PDF for the OM, xlsx or csv for the structured
files. Type is checked by suffix and by the file's leading bytes, not by the browser's MIME type.

## Rent roll

**Status vocabulary.** Occupied, current, leased and notice count as occupied; model, office,
employee, down and admin count as non-revenue. Anything else is treated as vacant and the note
says so. A roll that uses codes such as "O" and "V" would count every unit as vacant; the
occupancy figure would then be wrong and read High. Gap: no vocabulary learning yet.

**Header detection.** The parser looks for a row containing "Unit" and "Status" and then maps
columns by keyword (plan, SF, market, lease rent). A roll without a status column is rejected
with a note rather than guessed.

**Concessions and effective rent.** The parser reads the lease rent column. A roll with a
separate concession column overstates in-place rent. Gap: not handled; the T-12 concession line
catches the effect at the property level.

**Unit count disagreement.** When the OM and rent roll disagree on unit count, the rent roll
wins and a note records both figures.

## T-12

**Month header detection.** Twelve consecutive month-year headers are required. A statement with
quarterly columns, or thirteen months, or "Total" columns interleaved, is reported as unreadable
rather than misread.

**Line naming.** Expense lines are matched by name prefix (payroll, repairs and maintenance,
turnover, contract services, marketing, administrative, utilities, insurance, real estate
taxes). A chart of accounts that calls repairs "R&M" or splits payroll into three lines loses
those lines from the controllable total; the extraction then carries a lower figure at Medium
confidence and the question loop asks the analyst to confirm it.

**Seller figures are not buyer figures.** Taxes on the seller's assessment and the seller's
blended insurance premium are extracted with Low and Medium confidence and always become
questions, because reassessment on sale and a buyer's quote are the two largest expense
surprises in a multifamily acquisition.

**Partial periods.** A T-11 or an annualized T-9 is summed as if it were twelve months. Gap: the
parser does not detect this.

## Offering memorandum

**Broker pro forma figures read as facts.** The OM's financial summary carries a broker pro
forma next to the trailing actuals. The rule reader targets labelled facts (asking price, units,
year built, square feet) and clearly labelled survey and comp figures. The model reader is told
to grade broker estimates, surveys, comp-based figures and seller claims as Medium. The eval
checks that market rent, exit cap and renovation premium come back Medium, not High.

**Hallucinated citations.** Every OM extraction must quote text that appears on the cited page,
and the quote must contain the figure. Anything that fails either check is downgraded to Low and
marked "Unverified", whichever reader produced it. The test suite covers a wrong page, a wrong
figure and an invented quote.

**Figures that move between pages.** The asking price appears in the executive summary; the
same figure can appear on a cover letter with a different number after a price reduction. The
rule reader takes the first match; the model reader is asked to flag conflicts as Low. Gap: no
cross-page reconciliation.

**Rule reader coverage.** The regular expressions match the labels in the synthetic OM and OMs
that share them. A differently worded OM returns "not found" notes for those figures and the
question loop asks for them; nothing is guessed. Reading arbitrary OMs needs the model reader,
which needs `ANTHROPIC_API_KEY`.

**Model reader cost and latency.** One request per OM with the full page text; seven pages is a
few thousand tokens. Long OMs (eighty pages of photographs and maps) are mostly empty text and
still fit; the page cap is one hundred and twenty.

## Question loop

**Defaults hide missing answers.** Every question is prefilled, from the extracted figure when
there is one and from the current model input otherwise, so the analyst can run the model
without typing. The risk is that a prefilled seller figure (insurance at the seller's premium)
is accepted by inertia. The reason line under each question names the source and the current
model input so the difference is visible; the memo's "what the model cannot tell you" list
repeats the reassessment and premium risks.

**Controllable expenses as one number.** The seven controllable lines are extracted
individually and flow into the model per line. The question asks for one per-unit total, and
the answer scales the seven lines proportionally. An analyst who wants to reprice one line
edits it after the Underwrite step in a later build; today that is not exposed.

**Session scope.** Documents, extractions and answers live in the browser session in memory for
a day and are never written to disk. A redeploy clears them. That is the right default for a
public demo and the wrong one for a team tool; a persistent store is deferred.

## Eval

`python -m evals.screen.run` scores the rule reader against `evals/screen/expected.json`:
fifteen figures with value, document, page and minimum confidence, plus the three floor plan
rows. `--reader claude` runs the same score with the model reading the OM. The rule reader
scores fifteen of fifteen by construction; the number to watch is the model reader on OMs that
are not this one, which needs more packages than a synthetic set provides.
