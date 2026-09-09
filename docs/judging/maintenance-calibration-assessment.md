# Maintenance calibration assessment

## Assessment: not ready for the full rejudging pass

The active frozen protocol is `code-quality-maintenance-v2`. Calibration was
automated only, as approved by the user. It is not human-calibrated.

All 230 original submissions were inventoried and reconstructed, with matching
recorded source hashes and 23 submissions in each of ten model/effort cells.
Two patches required documented recovery of carriage returns from their saved
Git index diffs. The exact original capture normalization matched each saved
patch before recovery. No solver was rerun or original submission changed.

| Panel | Gates passed | Result |
| --- | --- | --- |
| GPT-6 Astra, medium reviewer effort | 8 of 9 | Formatting sensitivity gate failed |
| Claude Opus 5, medium reviewer effort | 9 of 9 | Calibration passed |

Astra assigned readability 3/4 to both the dense and formatted control. The
predeclared gate required an improvement of at least 0.5. Astra nevertheless
preferred the formatted candidate in both pairwise orders. This mismatch does
not establish model bias or poor solver code quality. It means this protocol's
absolute scale did not demonstrate the required sensitivity in this test.

The control is a tiny function, and ratings are stochastic. A single failed
check is not a broad conclusion about a reviewer's capabilities. The frozen
gate still applies: do not silently relax it, repeatedly sample until it passes,
discard that reviewer, or substitute a favorable primary score.

Version 1 receipts remain intact. That version encountered model aggregate
arithmetic errors during calibration. Version 2 moved aggregate arithmetic to
the host without changing the four dimensions, anchors, weights, or gates, and
ran fresh calibration for both panels.

## State and next decision

- Primary submissions rejudged: 0 of 230.
- Original 20% scores, website, PDF, and card: unchanged.
- Proposed 33% composite: implemented as a separate calculation, not published.
- Focused offline tests: 31 passed with repository-wide coverage disabled for
  the focused run; this is not a claim of full-suite coverage.
- Full pass: blocked by the predeclared calibration gate.

Recommended next step: agree on a new, broader automated calibration protocol
with held-out, multi-function controls and repeated absolute reviews, then
freeze it before new calls. Evaluate both panels identically. Keep this failed
calibration visible, preserve the substantive quality criteria, and do not tune
against Astra versus Fable submission rankings. Human review remains the
stronger missing validation, but is not required by the user's chosen automated
mode. Changing to a Claude-only panel would be a separate methodology decision.

## Reproducible evidence

The machine-readable gate results are in
`runs-code-quality-maintenance-v2/calibration-astra.json` and
`runs-code-quality-maintenance-v2/calibration-claude.json`. Exact prompts,
responses, model receipts, and usage are under that directory's `calls/`.
`summary.json` explicitly reports incomplete coverage and publication readiness
as false. See `maintenance-review-operations.md` for read-only status commands.
