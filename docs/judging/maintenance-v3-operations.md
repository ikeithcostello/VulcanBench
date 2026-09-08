# Maintenance v3 operations log

Operator actions and observations during calibration and the full pass.
This file is not hash-bound by the protocol; the protocol document is, so
operational notes live here.

## v3.2 calibration, September 7, 2026

- Astra: passed all twenty gates on 80 calls with no allowance used.
- Opus 5, control 2, repeat 1: the Claude CLI exited non-zero with result
  subtype `error_max_structured_output_retries` after the model omitted the
  `dimensions` field in all five internal attempts. The transport recorded
  this as non-retryable. Operator review reclassified it as an invalid-schema
  response, which the protocol grants one fresh retry; the receipt is
  retained with the review note inside it and the panel resumed. The same
  rule applies to any later occurrence: one fresh attempt, receipt kept, no
  other change.
- Constrained reader: failed gate 17. Control 0 accuracy 0.933 (one read
  answered (0.25) for a balance of -125 cents) against 1.0 on the compressed
  control. The gate compares two accuracies at the ceiling, so a single slip
  decides it; that is a design weakness recorded here, not amended. L5
  carries no weight and its results are not published under v3.2.
- Opus 5, control 5, repeat 4: second occurrence of
  `error_max_structured_output_retries` (dimensions field omitted again).
  Same rule applied: receipt retained with the review note, one fresh
  attempt, panel resumed. Two occurrences in the first 29 Opus 5 reviews. If
  this rate holds, the full pass of 460 reviews would need roughly 30 such
  reviews; the fix belongs in the transport's retry classification and can
  only land with a new protocol identifier, so it is deferred to the
  boundary before the full pass and recorded here.
- Opus 5, control 2, repeat 5: third occurrence in 31 reviews. The documented
  rule is now applied by `harness/maintenance_review_v3_resume.py`, a script
  outside the frozen code set that marks exactly this CLI subtype retryable
  once per call and re-invokes the stage. Anything else still stops for a
  person. Every application is printed and recorded in the receipt.
- Opus 5: passed all twenty gates on 80 calls with no allowance used, after
  three structured-output stops resolved under the documented rule (one of
  them by the wrapper). Repeatability shortfall -0.18, the closest gate.
- v3.2 calibration verdict: Astra passed, Opus 5 passed, reader failed gate
  17. Both panels are eligible for the full pass under the frozen protocol
  (hash 47ae9135). L5 results will not be published.

## v3.2 full pass

- Astra: all 230 primary reviews and 10 repeats complete; 2 of 10 pairwise
  calls complete. Stopped on the Codex subscription usage limit ("try again
  at Sep 12th, 2026 8:50 AM"). Per protocol: receipts preserved, no paid API
  fallback, resume with identical frozen inputs after the reset. Remaining
  for Astra: 8 pairwise, 230 probe, 230 match calls.
- Opus 5: stopped at primary review 101 after the retry rule fired four
  times in 100 reviews. Both attempts on submission 101 failed only the
  excerpt rule: the intent excerpt joined a hard-wrapped Markdown line into
  one line. Content verbatim, scores unaffected. Second operator rule added
  to the wrapper: when both attempts fail only on excerpts and every
  rejected excerpt matches the source once whitespace and line breaks are
  collapsed, attempt 1 is selected with those excerpts re-wrapped to the
  source's line breaks, scores untouched, original excerpts recorded in
  the selected receipt under operator_recovery. Quotes that do not match
  after collapsing are not recovered and stop for a person.
- Opus 5, primary submission 133 (evening of September 7): both attempts were
  answered by claude-opus-4-8 although the session requested and reported
  claude-opus-5, with no model_fallback event and no refusal text in the
  stream. This is the silent refusal fallback previously documented in the
  Fable panel comparison. The v3 protocol text accepts no reviewer fallback,
  so the identity guard rejected both attempts and the chain stopped. Not
  recoverable by either wrapper rule; awaiting the benchmark owner's policy
  decision. Opus 5 stands at 132 of 230 primary reviews. No other Opus 5
  stream in this run contains a fallback.
- Owner decision, evening of September 7, 2026: retain and disclose
  reviewer fallbacks, as in the earlier Fable panel comparison. This amends
  the protocol text's "no reviewer fallback is accepted" for the v3.2 full
  pass; no gate, weight, prompt, or hash changes. Mechanism: third wrapper
  rule. An attempt that failed only the identity guard, whose session
  requested and reported claude-opus-5, whose every assistant message came
  from claude-opus-4-8, that used no tool, and whose response validates, is
  selected with a reviewer_fallback record in the receipt. The card and
  summary must report the count of fallback-served reviews per stage.
- Opus 5, primary submission 136 (overnight, September 7 to 8): both attempts
  quoted two verbatim fragments joined by an inline ellipsis on one line.
  The re-wrap rule now splits excerpt lines on inline ellipsis markers and
  requires each fragment to be verbatim; fragments are rejoined with a
  dots-only line. Any fragment absent from the source still stops. The chain
  sat idle overnight on this stop.
