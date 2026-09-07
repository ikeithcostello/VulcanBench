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
