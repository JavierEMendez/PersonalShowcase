# Case study: what changed when the models left Excel

Two underwriting models moved from spreadsheets into Python for this site. One was a
master-planned-community land model that had already been rebuilt once as an internal Python
engine; the other was a multifamily acquisition model that existed as a 33-sheet workbook. This
is what changed in the work, what the tests and evals caught, and what stayed the same.

## The port is the easy part; the reconciliation is the work

The land model came across module by module in one session: net-outs, land, infrastructure,
allocation, sections, revenue, assessed value and bonds, overhead, summary, XIRR. The port itself
was not where the time went. The time went into a reconciliation script that ran both engines on
the same inputs and compared every summary line, every monthly cash flow row, and the XIRR to ten
decimals, across three scenarios. The bar was zero mismatches, and the first runs did not clear
it. Percentages stored as fractions in one place and as percentages in another; a rounding
helper that behaved differently on the boundary; an allocation that summed in a different order.
None of these show up in a spreadsheet, because a spreadsheet has no second copy to disagree
with.

Reconciling to zero also surfaced two behaviours of the source engine that a reader of the
spreadsheet would call bugs. The month that closes the marketing and insurance windows is taken
from the last lot size processed rather than the latest across all sizes. Empty collector road
rows keep a default start month and a six-month build, so an otherwise empty tract reports a
101-month project. Both were ported unchanged, because changing them would have broken the
reference before the web layer existed, and both are written down in the decisions log as
candidates for a separately reconciled fix. A port that quietly "fixed" them would have produced
a model nobody could check against the original.

## Typed inputs replace named ranges

In the workbook, an input is a cell. In the port, an input is a field on a pydantic model with a
type, a default and a place in a hierarchy: tract, costs, revenue, lookups. That change did more
than the port itself. The web forms could be generated from the same structure, so a blank field
means "use the default" and a percentage typed as 8 is stored as 0.08 by a rule keyed on the
field's path rather than by hand. Scenarios became copies of one typed object rather than copies
of a workbook. The Excel export writes the same object back out, with the schedule as values and
every total, ratio and the XIRR as live formulas, so a reviewer can trace a headline to the months
behind it without trusting the code.

Speed changed what the screen could do. The land engine runs in about three milliseconds, so the
sensitivity grid recalculates on the server for every cell, on any two of six drivers, in one
request. In the workbook the same grid was a data table that took long enough to run that nobody
changed its axes.

## The multifamily model: built to a structure, then tested

The multifamily engine was built from an inventory of the workbook's structure rather than a
cell-level port, a choice made deliberately and revisited once (see the decisions log for the day
the full port was proposed and declined). The first version of the deal was an annual scratch
model that produced a 13.5% levered IRR. The monthly engine produced 14.8% on the same inputs.
The difference was not an error in either. Monthly compounding of market rents and an exit on the
twelve forward months of NOI, which is how the workbook works, lift the return relative to an
annual approximation. The inputs did not move to close the gap; the docs were regenerated from
the engine and the decision recorded.

The tests caught three real defects before the screen existed. The waterfall's hurdle balances
were being reduced by both partners' distributions, so the LP reached its hurdle later than it
should have; the fix reduces them by LP receipts only. The cap rate at the asking price was
computed on the bid's NOI, ignoring that taxes reassess at the price paid; the fix runs
operations again on a price-swapped copy of the inputs. And a renovation premium stress at half
the base premium rounded 72.5 down to 70 rather than up to 75, a one-line rounding rule that
would have been invisible in prose. None of these would have been found by reading the code.

## The language model reads and writes; it does not count

The Screen step reads a broker package. The design decision that mattered was which parts to
hand to the model. The rent roll and the trailing twelve months are tables; their figures are
sums and averages over rows, and they are parsed with code. The offering memorandum is prose and
tables, and the model reads it, returning each figure with a page, a verbatim quote and a
confidence grade through a typed tool call. Every quote is then checked against the cited page,
and the figure must appear in the quote, or the extraction is downgraded and marked unverified.
The eval scores fifteen figures on the synthetic package for value, document, page and
confidence, and the interesting number is not the fifteen of fifteen the rule reader scores by
construction; it is what the model reader does on packages it has not seen.

The memo went further. The requirement was that every figure come from the model output, never
from the language model. Checking figures after the fact would have met the letter of that. The
implementation meets it by construction: the writer receives a table of placeholders with their
values and meanings, writes prose that uses the placeholders, and is not allowed to write a
digit. The code fills the numbers. A draft with a digit, an unknown placeholder, a banned phrase
or a recommendation that disagrees with the threshold test is rejected and the sentence template
takes over, with the rejection recorded on the memo. The eval counts a fallback as a failure for
the model writer, so the rate is visible rather than hidden behind a working page.

## What stayed the same

The underwriting did not change. The land model still allocates section costs by front foot and
sells lots on a pace; the multifamily model still sizes the loan on the lesser of three
constraints and burns loss to lease through rollover. An analyst who knows the workbooks can read
the modules and recognise every step. What changed is that each step now has a type, a test and
a place in a log, and that the parts of the work a model does well (reading a document, drafting
a paragraph) are separated from the parts it should never touch.

The decisions log has close to thirty entries for a project of this size. Most of them are small. Together
they are the argument for doing the work this way: every figure on the site can be traced to an
input, a module and a dated reason.
