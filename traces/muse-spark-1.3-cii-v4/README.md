# Muse Spark 1.3 (Contributor) on VulcanBench-SWE v4: minimal-effort traces

Raw agent traces from the minimal-effort pass of a six-level effort sweep of
Meta's Muse Spark 1.3 model, driven by the Muse Code CLI, on the 23-task
VulcanBench-SWE v4 suite (internally `coding-intelligence-index-v4`). The
tasks, gold patches, and tests live in the public
[VulcanBench](https://github.com/morganlinton/VulcanBench) repository under
`tasks/coding-intelligence-index-v4/`.

These are the solver's own records, published so others can analyze how the
model spent its time. Nothing here has been edited apart from the harness's
standard redaction pass and gzip compression of the two largest file types.

## Configuration

| Item | Value |
| --- | --- |
| Model | `muse-spark-1.3-contributor` (Meta Contributor tier) |
| CLI | Muse Code 1.0.3 (1.0.3-R2198.1), macOS arm64, pinned by SHA256 |
| Effort | `minimal`, passed as `--reasoning-effort minimal` |
| Billing | Meta account subscription; no API key in the child environment |
| Web tools | disabled |
| Isolation | macOS `sandbox-exec` outer profile; per-task workspace and scratch |
| Task timeout | 36,000 s (10 hours) per task |
| Concurrency | 1 (sequential) |
| Host | Apple Silicon Mac, shared with a concurrent Claude sweep at times |

The full pre-registered protocol, including task hashes and the three
amendments made during the sweep, is in `protocol.json`. The protocol as
originally written is preserved in `protocol-original-2026-09-06.json`.

## Results (minimal pass)

`results-minimal.jsonl` has one line per scored run. Functional score is the
hidden-test pass fraction; a regression against a previously passing test
scores 0.

| Task | Functional | Tokens | Wall clock |
| --- | ---: | ---: | ---: |
| settlecore | 0.30 | 1,680,001 | 3 min |
| matchcore | 0.78 | 4,361,712 | 24 min |
| qlite-store | 1.00 | 751,177 | 3 min |
| payrollcore | 1.00 | 5,224,221 | 35 min |
| metercore | 1.00 | 1,414,794 | 12 min |
| freightcore | 1.00 | 11,555,396 | 55 min |
| codeccore | 0.20 | 1,308,815 | 6 min |
| quotacore | 1.00 | 1,607,751 | 13 min |
| snapcore | 0.60 | 861,115 | 5 min |
| vaultcore | 1.00 | 1,897,588 | 4 min |
| queuecore | 0.62 | 5,446,180 | 28 min |
| hedgecore | 0.88 | 3,401,413 | 24 min |
| schedcore | 1.00 | 6,446,767 | 44 min |
| reflowcore | 1.00 | 15,824,965 | 63 min |
| tallycore | 0.50 | 233,848,497 | 6.7 h |
| pacecore | 1.00 | 2,834,207 | 52 min |
| blendcore | 1.00 | 13,765,600 | 31 min |
| stampcore | 0.89 | 4,172,234 | 11 min |
| granarycore | 0.43 | 271,959,327 | 9.4 h |
| depotcore | 0.64 | 232,246,160 | 4.2 h |
| lodgecore | 0.00 (timeout) | 219,422,694 | 10.0 h |
| cellarcore | 0.64 | 60,490,937 | 4.1 h |
| paddockcore | 0.00 (timeout) | 114,850,448 | 10.0 h |

Mean functional 0.717. Total 1,215,371,999 tokens and 51.3 hours. Six runs
over three hours account for 93 percent of the tokens. Token counts are the
sum of Muse's own per-call receipts (input plus output, with cached input
included in input), deduplicated by run and record id.

## Layout

```
minimal/<task>-<run-id>/
  summary.json                 harness summary: scores, usage, effort, task hash (scored runs only)
  trace.jsonl                  harness event log: start/result events, verifier output
  cli-agent-stream.jsonl.gz    Muse Code's JSON event stream as received by the harness
  final.patch                  the diff the harness graded (scored runs only)
  replay.html                  harness replay page for the run
  workspace/                   the task workspace as the model left it
  muse-session-logs/
    <date>/<session-id>/session.jsonl.gz   Muse's own session log, with per-call token receipts
    stderr.txt                 Muse's stderr
    boundary.sb                the sandbox profile applied to the run
```

Nine directories have no `summary.json`. They are attempts the provider
aborted mid-run ("model stream idle timeout"), which produced no patch and
were not scored. The task was then relaunched from a clean workspace. They are
kept for completeness: blendcore (2), stampcore (1), lodgecore (6).

## Reading the traces

Decompress with `gunzip -k` or read with `gzip.open` in Python. Every file is
JSON Lines.

In `cli-agent-stream.jsonl`, each shell command and its result appear as a
`tool.result` record whose `payload.text` is itself a JSON string with
`command`, `description`, `exit_code`, and `output`. The `description` field
is the model's own one-line label for the step, which makes it a quick way to
follow what it was doing. Model turns are `task.lifecycle.*` records with
`task_kind` of `model.meta.response`; file edits are `tool.edit_file`.

In `session.jsonl`, completed model calls are records whose
`payload.event.kind` is `model_completed`, with `usage` holding
`input_tokens`, `cached_tokens`, `output_tokens`, and `reasoning_tokens`, and
`recorded_at` in microseconds since the epoch. Some records are wrapped in a
`retained_frame` envelope whose `children[].record_json` holds nested records;
`harness/agent/muse_code.py` in the VulcanBench repository has a reference
parser (`session_records` and `collect_usage`).

## Caveats

- **Contributor tier.** Meta's Contributor pricing tier permits Meta to use
  submitted prompts and completions for training. That was accepted for this
  run. The task suite was already public.
- **Effort is asserted, not echoed.** The CLI accepted `minimal` and the
  provider receipts confirm the model id, but the provider does not report the
  effective reasoning effort.
- **Retries.** Only provider-aborted attempts were relaunched. Timeouts and
  failing patches were scored as they stand. See the amendments in
  `protocol.json` for the idle-timeout change made after the minimal pass.
- **Timing.** Wall clock includes tool execution on the host, which was shared
  with other work at times. Treat durations as indicative.
- **Paths.** Logs contain local filesystem paths from the machine that ran the
  sweep. They carry no secrets; the harness redaction pass ran over every
  record.
