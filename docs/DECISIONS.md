# VulcanBench decisions

A running log of operating decisions that are not derivable from the code:
what was decided, the evidence, and when to revisit. Agents working on the
harness or on sweeps should read the entries that touch their area before
changing run conditions. Suite-level policy for v4 lives in
[tasks/coding-intelligence-index-v4/CHARTER.md](../tasks/coding-intelligence-index-v4/CHARTER.md);
entries here record the measurements behind those rules.

## 2026-09-18: Devin SWE-2 sweeps run medium, high and max only, unpriced

### Decision

The Devin SWE-2 column on VulcanBench Frontier v4 is swept at exactly the
three effort variants Devin's account catalog lists for the family
(`swe-2-medium`, `swe-2-high`, `swe-2-max`), through the Devin CLI harness
(`--harness devin`), one attempt per task, serial, under the flat 3-hour
task timeout. No low or extra-high column is published for SWE-2, and the
cost column is "unavailable" rather than an API-equivalent estimate.
Launcher: `scripts/cii-v4-board/run_devin_effort_sweep.sh`, queued behind
the Sol chain by `logs/devin-swe2-chain.sh`. Owner request, in chat,
2026-09-18.

### Evidence

- Devin exposes effort only as the last token of a model id; `devin models
  list --format json` on this account lists SWE-2 as `swe-2-medium`,
  `swe-2-high` and `swe-2-max` and nothing else (no `-low`, no `-xhigh`).
  Cognition's SWE-2 announcement names the same three levels. The adapter
  refuses an unlisted uid because the CLI otherwise falls back silently to a
  default model (its log: "did not resolve to an available, allowed model;
  starting on the default").
- The cloud Devin Sessions API cannot pin a model or an effort at all (its
  only knob is `devin_mode`: normal, fast, lite, ultra, fusion), so the local
  CLI is the only route that measures SWE-2 at a known effort. `ultra` there
  is a session mode, not an effort, and is blocked anyway.
- SWE-2 has no public per-token price (catalog cost tier "Free" through
  2026-10-10, Devin-only availability), so an API-equivalent cost would be
  invented. Tokens and Devin's credit/ACU counters are recorded instead.
- A live hello-world run on 2026-09-18 (`swe-2-medium`, CLI 3000.10.31)
  confirmed print-mode flags, per-run config acceptance, session harvest,
  receipt deduplication and the served-model check.

### What this touched

- `harness/agent/devin_cli.py` (new), `harness/agent/cli_agents.py`,
  `harness/effort.py`, `harness/agent/run_audit.py` (`"webfetch"` marker),
  `harness/agent/loop.py` (`.devin/` ignored in workspaces), `harness/cli.py`,
  `harness/pricing.py` (comment only), `tests/test_devin_cli.py`,
  `scripts/cii-v4-board/run_devin_effort_sweep.sh`, `logs/devin-swe2-chain.sh`,
  README and `docs/HARNESS_BENCHMARKING.md`.

### Revisit triggers

- Devin adds `swe-2-low` or `swe-2-xhigh` to the catalog: extend `LEVELS`
  in the launcher and the sweep gains a column, nothing else changes.
- Cognition publishes a per-token API rate for SWE-2: add a `devin:swe-2`
  price entry and re-run `reprice_runs.py`; until then the column stays
  unpriced.

## 2026-09-16: the "ultra" effort level never runs

### Decision

No VulcanBench benchmark runs at effort "ultra", for any model, harness or
suite. The block lives in `vulcanbench.toml` (`[effort].blocked`) and is
enforced before any model call by `harness/settings.py` at every entry point:
`vulcanbench run`, `vulcanbench effort-sweep`, `run_agent` (which every sweep
driver calls), and the Codex effort launcher. A blocked level is refused with
an error naming the file. Owner decision, in chat, 2026-09-16.

### Evidence

- The Codex model catalogue lists "ultra" for GPT-5.6 Terra only, above max;
  GPT-5.5 stops at xhigh and Luna at max. The board publishes Low to Max, so
  an ultra column would compare against nothing.
- Muse Code's "ultra" is a client-side mode mapped onto the provider's
  highest supported tier, not a distinct API effort (recorded in the Muse
  Contributor sweep protocol), so it does not measure a new level either.
- A settings file rather than a code constant so the rule survives new
  adapters and catalogue changes without anyone remembering it.

### What this touched

- `vulcanbench.toml` (new), `harness/settings.py` (new), `harness/agent/loop.py`,
  `harness/cli.py`, `scripts/cii-v4-board/run_codex_effort_sweep.sh`,
  `tests/test_settings.py`.
- Not touched: `harness/effort.py` and `harness/agent/muse_code.py` still know
  the word so recorded runs and protocol hashes stay valid; the running Muse
  Contributor sweep pins both files. That sweep's protocol lists ultra as its
  final level; under this block it will stop with a refusal before that level
  rather than run it, and its protocol should be amended to drop ultra at its
  next stop.

## 2026-09-13: v4 task timeout lowered to 3 hours; concurrency stays at 1

### Decision

1. Every VulcanBench Frontier v4 (`coding-intelligence-index-v4`) task carries a
   flat 3-hour agent timeout (10800 s, 540 steps at the 20 s/step stamp),
   down from 10 hours. Stamped in each task's `agent_hints` and declared
   once in `suite.json` `flat_budget`; `scripts/stamp_task_budgets.py --check`
   verifies against it.
2. Sweeps keep running one task at a time (`--max-concurrency 1`, the
   harness default). Concurrency was considered and deferred.

### Evidence for the timeout

Measured over every completed v4 solver run on disk at the time
(479 runs: claude-fable-5-1, gpt-5.5, gpt-5.6-luna, gpt-6-astra, muse-spark-1.3, muse-spark-1.3-contributor; efforts from minimal to max).

| Statistic | Minutes |
|---|---|
| Median | 11.2 |
| Mean | 25.3 |
| p90 | 33 |
| p95 | 55 |
| p99 | 404 |
| Max | 953 (two runs exhausted the 10-hour bound, both scored 0) |

Runs above each candidate cutoff, and how many of those still passed
functional:

| Cutoff | Runs over | Passed |
|---|---|---|
| 30 min | 60 | 34 |
| 60 min | 22 | 7 |
| 120 min | 16 | 4 |
| 180 min | 9 | 0 |
| 240 min | 9 | 0 |

None of the nine runs past 3 hours passed (best functional score in that
group 0.88). Eight were Muse Spark 1.3 runs. The ninth was a GPT-5.5
extra-high run on paddockcore that ran 16 hours against the 10-hour cap:
the harness's watchdog fired but killed only the npm launcher, not the
native Codex worker, which kept working and writing to the pipe. That is
fixed (the adapters now start each CLI in its own session and kill the
whole process group; see `_kill_process_group` in
`harness/agent/cli_agents.py`), but the fix has not yet been exercised by
a real Codex timeout. The Muse adapter was verified to cut off at 600
minutes. The slowest passing run on record is
claude-fable-5-1 at extra-high effort on legacy-depotcore-binary-parity,
168 minutes. Apart from that runaway run, Codex-harness models (GPT-6 Astra,
GPT-5.5, GPT-5.6 Luna) never exceeded 61 minutes at any effort. So a 3-hour
bound would have changed no pass@1 result while removing 7 hours of wall
clock per stuck run (13 hours in the runaway case).

Note the margin: the slowest passing run sits 12 minutes under the new bound.
A 4-hour bound has the same zero-loss property with more headroom (no run
landed between 3 and 4 hours). 3 hours was chosen deliberately; if a
Claude Code run at high or max effort passes after more than 2.5 hours,
reconsider 4 hours before treating the timeout as a result.

### Why concurrency was deferred

The harness supports it (thread pool in `harness/suite.py`, one temp
workspace per run, no fixed ports), and no rate-limit rejection has ever
been recorded (867 infra retries across v4 sweeps: 866 were one expired
Codex refresh token, one was a Claude Overloaded error). The blocker is
the wall-clock metric. The speed cards and the v4 report cards rank models
by wall-clock minutes per task, and every v4 suite record on the board was
produced at concurrency 1. Runs sharing one 10-core machine and one
subscription session would take longer per task than they do today, and
their durations would not compare against the serial history. Until the
speed panel is sourced only from serial runs (the suite record stores
`max_concurrency`, so a filter is possible) or is decoupled from wall
clock, sweeps stay serial.

Two smaller reasons: no run has ever exercised the Codex or Claude Code
subscription with more than one session at once, so the rate-limit
behavior is unmeasured, and the infra-retry path has no backoff, so a
burst of usage-limit rejections would exhaust both retries and record
scored failures.

### Revisit triggers

- Any v4 run that passes after more than 2.5 hours: consider 4 hours.
- The first Codex run that hits the 3-hour bound: confirm from its
  `summary.json` that `duration_s` is within a minute of 10800 and that
  `cli_agent.timed_out` is true. If it overran, the process-group kill
  regressed and the bound is not enforced for Codex.
- Speed reporting sourced from serial runs only, or from a metric that
  does not depend on wall clock: concurrency 2 or 3 becomes viable. Add a
  backoff on usage-limit infra retries first.
- A new model family with a materially different duration profile: rerun
  the cutoff table above before its first full sweep.

### What this touched

- `tasks/coding-intelligence-index-v4/*/metadata.json` (23 tasks):
  `agent_hints` restamped to 10800 s / 540 steps, `budget_calibration`
  updated. blendcore had been left on the formula value (5400 s) when the
  10-hour bound was stamped; it now carries the flat bound like the rest.
- `tasks/coding-intelligence-index-v4/suite.json`: `flat_budget` added.
- `tasks/coding-intelligence-index-v4/CHARTER.md`: budgets rule 1 revised.
- `scripts/stamp_task_budgets.py`: checks against `flat_budget` when the
  suite declares one.
- `scripts/cii-v4-board/make_report_card.py`, `scripts/harbor-export/`:
  wording that quoted the 10-hour figure.
- Published snapshots under `docs/results/` describe the conditions their
  runs were made under and were not rewritten.

Runs are comparable across the change: no run in either regime was bound
below 3 hours, so results before and after differ only in how long a
failure could take. The GPT-5.6 Luna extra-high sweep was 17 of 23 tasks
in when the restamp landed on 2026-09-13; its last six runs, and the
queued Astra rerun, run under the 3-hour bound.
