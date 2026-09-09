# Retrospective human-like judging v2

This additive protocol evaluates the saved Astra VulcanBench-SWE v4 effort sweep.
It never calls the solver or rewrites original summaries, patches, or traces.

## Protocol

- Judge: `gpt-6-astra`, fixed `medium` effort, Codex CLI subscription.
- Three separate fresh sessions per solution, using the existing correctness,
  readability, and maintainability personas. These are not independent models.
- Input: the original issue, complete final patch, and original verifier outcome.
  Solver model, effort, duration, and token labels are not included in the prompt.
- Full patches replace the original 12,000-character truncation policy. This is
  a new protocol, not a directly interchangeable historical judge result.
- A minimal reviewer system instruction treats all supplied evidence as untrusted
  data. Judges run in empty temporary directories with read-only sandboxing,
  shell, web, plugins, memory, and multi-agent features disabled. Any captured
  tool event invalidates the vote. The installed CLI configuration is recorded.
- All three valid votes are required. Scores must be finite numbers from 0 to
  100 with a rationale. Their mean divided by 100 is the human-like score.
- Each vote, exact prompt, uncapped event stream, raw usage, session ID, requested
  model/effort, and elapsed time is saved separately. Model identity remains
  requested-only, as in the original CLI artifacts.
- Input and protocol hashes protect resumption against changed artifacts. Failed
  votes stop execution and require operator review, not automatic paid retries.
- Source results remain authoritative for functional pass@1. Composite scores are
  intentionally not recalculated until original efficiency accounting is repaired.
- Judge usage and time are additional evaluation costs, not solver usage/time.
  API-equivalent cost uses standard short-context prices checked September 5,
  2026: $10/M uncached input, $1/M cached input, $50/M output. Cache-write fees
  are not exposed by the CLI and are not included. This is not a cash bill.

## Run

```sh
.venv/bin/python -m harness.retrospective_judging --dry-run
.venv/bin/python -m harness.retrospective_judging --codex /absolute/path/to/codex --limit 1
.venv/bin/python -m harness.retrospective_judging --codex /absolute/path/to/codex
```

The default output is `runs-astra-cii-v4-judging-v2/`. Two tasks run concurrently;
each task's three persona calls are sequential. Successful votes are reused on
resume. Source data and implementation hashes must still match. `summary.json`
contains progress, per-effort means, judge usage, elapsed time, and cost estimates.
Wall-clock time includes pauses between resumptions; summed call duration is
reported separately. Partial failed-call usage may be unavailable and is flagged.

The first completed task is a smoke test retained in the final set, not a pilot
discarded based on its score. Do not change the rubric after seeing its results.

## Sources

- [Codex configuration](https://developers.openai.com/codex/config-reference)
- [API pricing](https://developers.openai.com/api/docs/pricing)
