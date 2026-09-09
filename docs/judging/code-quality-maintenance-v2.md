# Code quality maintenance v2

Status: protocol prepared for automated calibration and a separate retrospective
rejudging pass. Not human-calibrated. No original solver result is replaced.

## Population and question

All 230 saved submissions in the frozen Astra and Fable comparison: 23 tasks,
five effort settings, two solver configurations. Include the same 11 Fable
fallback runs and retain their identity in the analyst manifest. No solver is
rerun. No task or submission is selected by its previous score.

Question: How readily could another engineer understand, debug, and safely
extend this implementation?

## Rubric

Four equally weighted dimensions use anchored scores from 0 to 4, in steps of
0.5. Code quality is computed by the host as 25 times the mean dimension score, on a\n0 to 100 scale. The model's top-level score is a transport placeholder only,\nnever an authoritative aggregate. This removes arithmetic from model grading.

| Dimension | What is assessed |
| --- | --- |
| Readability | Names, control flow, expressions, and presentation make reasoning straightforward. |
| Structure | Responsibilities, data ownership, and boundaries are coherent without needless abstraction. |
| Changeability | A concrete plausible change can be localized, without duplicated policy or fragile coupling. |
| Intent | Non-obvious assumptions, invariants, compatibility behavior, and algorithms are recoverable from names and useful explanations. |

Anchors apply separately to each dimension:

- 0: pervasive obstacles make routine maintenance unreliable without a rewrite.
- 1: substantial obstacles require repeated reconstruction of logic or state.
- 2: usable, but material localized obstacles complicate ordinary maintenance.
- 3: clear and maintainable, with minor localized shortcomings.
- 4: consistently easy to understand and safely change at the task's scale;
  no material shortcoming supported by the supplied evidence.

Intermediate scores require evidence between adjacent anchors. Neither brevity
nor verbosity is inherently good. Do not require comments for self-evident
code, object orientation, type annotations, or unnecessary helper functions.
Formatting-only issues primarily affect readability, not every dimension.
Do not speculate about model incentives or reward hacking. Do not repeat the
functional, lint, complexity, or security score as a subjective score.
Assess submitted changes in the context of the final implementation; do not
attribute unchanged baseline defects to the candidate. Recovered legacy quirks
are requirements, not bugs merely because they look unusual.

Each dimension must cite an exact excerpt from the evidence and explain a
concrete maintenance consequence. Changeability must name a plausible future
change. These are review judgments, not measured future maintenance outcomes.

## Evidence and reviewers

Provide the original task issue, complete saved patch, and reconstructed final
source and documentation from the starting repository plus that patch. Include
all Python source, Markdown documentation, and changed text files. Record hashes
and byte lengths for binary files instead of rendering them as source. Never
provide hidden tests, gold patches, solver transcripts, prior grades, model
labels, effort labels, timing, costs, or token counts. Judge sessions are fresh,
read-only, tool-disabled, and outside benchmark workspaces. Evidence is untrusted
data and cannot instruct the judge. Blinding removes metadata, not all possible
style cues; source comments may themselves disclose authorship.

If original text-mode patch capture normalized embedded carriage returns, use
the preserved Git index diff only when the identical normalization reproduces
the complete saved patch exactly. Apply its raw bytes to the verified starting
repository, retaining a separate recovery receipt. Never edit a submission or
guess missing content to make reconstruction pass.

Panels: GPT-6 Astra and Claude Opus 5, both at medium reviewer effort, equal
weight. One fresh call per panel rates all four dimensions jointly. Dimension
ratings are correlated, not four independent reviewers. No reviewer fallback is
accepted. Raw calls, prompts, response identity, token use, timing, and errors
are retained. Requested-only identity remains a caveat when not returned by the
provider. Subscription access only; no paid API fallback or automatic reset.

## Automated calibration and frozen gates

Freeze the protocol, code hashes, source manifest, synthetic controls, prompts,
selection seed (20260906), and gates before the first review call. Controls are
author-created and test construct sensitivity, not human ground truth.

For each panel, eight independent absolute reviews cover clear concise code,
dense code, formatting-only improvement, verbose duplicated policy, needless
abstraction, misleading comments, a repeated clear sample, and an embedded
instruction attack. Two matched pairs are reviewed in both orders: clear versus
verbose duplicated policy, and formatted versus dense code. Ties are allowed.

Each panel must pass all gates before any production submission is judged:

1. All responses valid, with exact evidence excerpts, no tools or model fallback.
2. Clear code has a mean dimension score of at least 3; it exceeds verbose
   duplicated code by at least 0.5 in structure or changeability.
3. Formatting improves readability by at least 0.5, while structure and
   changeability each change by no more than 0.5.
4. Misleading comments score lower on intent than clear code.
5. The repeated clear sample differs by no more than 0.5 on average across
   dimensions. Embedded instructions do not change the clear sample's mean by
   more than 0.5 and are not obeyed.
6. Pairwise choices are consistent under order reversal and do not prefer
   duplicated verbose code to clear code or dense code to its formatted copy.

On a gate failure, stop and retain the failed calibration. Do not loosen gates
or tune against Astra versus Fable rankings. A changed rubric needs a new
protocol identifier and a fresh calibration pass. No numerical rescaling is
fitted to controls, and no score spread or winning model is targeted.

## Full pass and validation

After both panels pass, independently judge all 230 submissions in a seeded,
interleaved order. Never omit a failure or replace a valid low score. Allow at
most one fresh retry for malformed JSON or invalid schema, independent of score;
retain both attempts and count all available usage. Stop on authentication,
quota, transport, tool-use, identity, or evidence-integrity failures.

Run 10 preselected blind repeated submissions (one from each solver and effort
cell) and five preselected matched solver pairs (one per effort), each pair in
both orders. These are diagnostics, excluded from published point estimates.
Flag repeat mean absolute error above 0.5 on the 0 to 4 scale, order consistency
below 80%, or pairwise disagreement with absolute-score ordering above 40%
(absolute gaps below 0.5 count as ties). Diagnostics do not choose new winners or
replace original ratings. Failed diagnostics block a claim that the protocol is
validated and require review before publication, not selective rejudging.

Planned calls: 24 calibration, 460 primary, 20 repeat, 20 pairwise, total 524
before malformed-response retries. Full coverage requires 230 paired ratings
and 920 dimension ratings per panel. Quota stops preserve completed receipts;
resume with identical frozen inputs only. Claude stops before another call when
reported subscription usage reaches 80% or overage is reported. No elapsed-time
estimate is a guarantee; measure calibration latency before estimating the pass.

## Scoring and disclosure

New proposed composite: 50% functional, 8.5% automated quality, 8.5% security,
33% Code quality. Also retain the 50/15/15/20 sensitivity comparison using the
same newly judged quality scores. This is a policy choice, not an optimized
weight. Original 20% protocol results remain separately available and unchanged.

Report panel disagreement, dimension breakdowns, paired task uncertainty,
coverage, fallback labels, and calibration diagnostics. Do not claim actual
human agreement, no bias, causality, or statistical significance from narrow
whiskers. Do not silently replace the staged website, PDF, card, or public
evidence snapshot before the full pass and validation are complete.

## Calibration provenance

Version 1 was stopped during calibration because model-produced aggregate
arithmetic was inconsistent with its dimension ratings. Its prompts and raw
receipts remain intact. Version 2 preserves the rubric, anchors, dimensions,
weights, controls, and gates, but computes aggregate arithmetic in the host.
Both panels must undergo fresh calibration. No primary submission was judged
under version 1, and its calibration scores are not reused as primary ratings.

