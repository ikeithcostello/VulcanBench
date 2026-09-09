# How VulcanBench scores code quality: the v3 system

Draft for public feedback, September 8, 2026. Describes the protocol as
designed and partly run. Where something has not run yet, it says so.

## The problem it fixes

Two failure modes in how benchmarks usually score code quality:

1. Automated metrics reward compression. The maintainability index has a
   lines-of-code term, and per-function complexity stays low when each dense
   line does something different. Code with five statements per line, names
   like x and k, and unexplained constants can outscore the same logic
   written for a person.
2. Model judges read compressed code for free. When we calibrated a frontier
   model as a readability judge, it rated a squashed six-line function the
   same as its formatted copy. A model's opinion that code is readable is not
   evidence that a person can read it.

Code quality is now a third of the composite score, locked before any
submission was rescored. The other weights are 50% functional correctness
from hidden tests, 8.5% automated quality, 8.5% security.

## What gets scored

230 submissions: 23 tasks, five effort settings, two solvers (GPT-6 Astra and
Claude Fable 5.1). Every task is a Python rewrite of a retired binary whose
real behaviour departs from its written spec in specific, documented ways.
Those departures are the quirks. We know all of them.

## The rubric

Every judge gets the same instructions, byte for byte, frozen by hash before
any review. It names the reader it is scoring for: an engineer who has never
seen the code, reads it top to bottom without running it, and must make a
correct change in one sitting. It tells the judge that its own ease at
parsing dense code is not evidence of readability.

Six dimensions, each 0 to 4 in half steps, each with written anchors for
what every level means:

| Sub-score | Dimension | Question |
| --- | --- | --- |
| Human readability | Naming | Do identifiers say what things are in the task's domain? |
| Human readability | Presentation | Statements per line, nesting, function length, how much a reader must hold at once |
| Human readability | Intent | Are constants, thresholds, and quirks explained by names or accurate comments that say why? |
| Maintainability | Structure | Coherent responsibilities, no duplicated policy, no abstraction beyond the task's scale |
| Maintainability | Changeability | Name a plausible change, trace every edit site, score how localized and safe it is |
| Maintainability | Verifiability | Explicit state, failures that name what went wrong, seams to test one rule alone |

Every score must cite an exact excerpt from the code and a concrete
consequence for the reader. No quote, no score. The host computes the two
sub-scores and their mean; the judge never does arithmetic.

## Who judges

The scored panel is two models from labs that have no model on the board:
Muse Spark 1.3 (Meta) and Grok 4.6 (xAI), equal weight. GLM 5.3 was tried
first and failed the calibration exam by fabricating a quote. Neither shares a family
with either solver, so neither is grading its own relative.

Astra and Claude Opus 5 were run as reviewers too, but by the benchmark
owner's decision they are not scored, not shown, and not waited for; their
receipts are kept as raw diagnostics only.

Every judge session is fresh, blind to model and effort labels, tools
disabled, read-only, outside the benchmark workspace, on a subscription
rather than a paid API. Every raw prompt, response, session id, and token
count is kept.

## Four layers under the 33%

| Layer | What it measures | Ground truth | Weight |
| --- | --- | --- | --- |
| Reviewed panel | The six-dimension rubric above | none, it is a review judgment | 15% |
| Intent recovery | Can a reader learn the real contract from the code alone | the task's quirk inventory | 6% |
| Measured maintenance | Does a follow-up change land correctly and locally | regenerated hidden tests | 12% |
| Readability signals | Statements per line, short names, magic numbers, nesting, hidden state | deterministic | 0%, reported |

Intent recovery: the judge sees the spec and the code, never the issue, and
must list where the code departs from the spec. A separate call matches its
list against the frozen answer key. Code that implements a quirk as an
unexplained if statement is hard to recover; a named constant next to a
comment saying why is easy. Denominator is the quirks the submission actually
passed tests for, so a functional failure is not punished twice.

Measured maintenance: for each task we change one rule of the retired
binary, regenerate the hidden tests, and write a ticket in the voice of the
original issue. A fixed maintenance agent, blind to authorship, applies the
ticket to each submission. Score is whether the change lands and whether
anything else breaks. Not built yet; until it is, the split is 24% reviewed
and 9% intent recovery, disclosed.

## Calibration before any real review

Before a judge scores a single submission it takes an exam on ten held-out
programs that all do the same thing: one clear, one compressed, the
compressed one auto-formatted, one with the fee policy copied three times,
one over-engineered with registries and value objects, one whose comments
lie, one with a comment on every line that explains nothing, one with a
documented legacy quirk, one with a comment telling the judge to give full
marks, one with hidden module state.

Each program is reviewed five times in fresh sessions in a seeded order.
Twenty gates, all fixed in advance, check that the judge sees the
construct: the clear program must beat the compressed one by at least a
full point on naming and presentation; formatting the compressed one must
raise presentation and nothing else; comments that restate every line must
not buy an intent score; lying comments must lose intent; the injected
instruction must be ignored; repeats must agree; pairwise preferences must
be consistent when the order is reversed. A judge may miss at most one gate
by at most half a point. If it fails, it fails, and what happens next was
written down before the exam.

## What has actually run, honestly

- Three protocol amendments on September 7, all before any counted call and
  all published: one fixed a transport bug, one relaxed an over-strict quote
  rule and removed a gate clause that measured the wrong thing, one moved
  from three repeats to five and added the one-gate allowance after two runs
  produced two different single-gate noise failures.
- Muse Spark 1.3 and Grok 4.6 both passed all twenty gates with no
  allowance used and completed every review, probe, and match on all 230
  submissions on September 9, 2026. Astra and Opus 5 also passed the exam
  under an earlier protocol version but are not part of the published score.
- A small Haiku "constrained reader" comprehension test failed its gate by
  one wrong answer in fifteen and is not published.
- Every stop during the runs, every operator decision, and every retry is
  logged in the repository with the receipt it applies to.

## What it does not claim

No human rated anything. The card will say "reviewed for a human reader by
a blinded model panel", never "human-validated". The rubric never names a
model. Every layer applies to every model on the board identically. This is
one benchmark's attempt to measure something that automated metrics get
backwards, with its instrument calibrated in the open.
