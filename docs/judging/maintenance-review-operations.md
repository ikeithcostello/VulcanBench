# Maintenance review operations

The active pass is `code-quality-maintenance-v2`, with automated calibration
only. Version 1 calibration receipts are preserved separately after detecting
model aggregate-arithmetic errors. No version 1 primary reviews were run.

## Files

- Frozen specification: `docs/judging/code-quality-maintenance-v2.md`.
- Runner: `harness/maintenance_review_v2.py`.
- Local evidence and receipts: `runs-code-quality-maintenance-v2/`.
- Frozen identity mapping: `private-manifest.json`. Never give it to judges.
- Machine protocol and hashes: `protocol.json`.
- Evidence completeness: `preflight.json`.
- Calibration gates: `calibration-astra.json` and `calibration-claude.json`.
- Raw attempts: `calls/<panel>/<stage>/<blinded-id>/attempt-*`.
- Accepted response: `selected.json`, with prompt and protocol bindings.
- Source recovery receipts: `reconstruction/`.
- Derived progress and diagnostics: `summary.json`.

## Commands

Run from the VulcanBench checkout using its existing virtual environment.

```sh
.venv/bin/python -m harness.maintenance_review_v2 calibrate --panel astra
.venv/bin/python -m harness.maintenance_review_v2 calibrate --panel claude
.venv/bin/python -m harness.maintenance_review_v2 run --panel astra
.venv/bin/python -m harness.maintenance_review_v2 run --panel claude
.venv/bin/python -m harness.maintenance_summary
```

Only one process per panel is permitted. The two different panels can operate
concurrently. `run` refuses to start unless both calibration panels passed under
the same frozen protocol. Completed calls are reused only with identical prompt
and protocol bindings. A non-retryable failed call requires operator review.
Do not delete failed receipts to force a retry.

`summary.json` is a snapshot refreshed by the summary command, not a live
monitor. It separates partial coverage from readiness for publication. The
summary includes usage from unsuccessful attempts when the provider returned
usage, and identifies missing usage rather than assuming zero consumption.

Claude's saved quota guard deliberately pauses at 80% utilization or overage.
A quota reset requires fresh read-only quota evidence before changing that
operational receipt; never clear it merely to force continuation. Authentication,
reviewer identity, source hashes, and frozen code must still match on resume.

The existing website, PDF, model card, old score protocol, original solver
results, and saved submissions are not changed by this pass. Publication needs
complete coverage and inspection of the calibration and validation diagnostics.

The new 33% composite and the 20% sensitivity view use the same new Code quality
ratings. No weight is fitted to a desired model ordering.
