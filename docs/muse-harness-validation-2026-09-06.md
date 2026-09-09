# Muse Code harness validation

Status: repaired locally and validated using synthetic examples. The benchmark
remains paused. No benchmark task was submitted during this validation.

## Configuration

- Model: `muse-spark-1.3-contributor`, explicitly selected and confirmed in
  completed provider receipts. Authentication uses the existing Muse Code account
  credential with unrelated API keys excluded from the child environment.
- Binary: `~/.local/bin/muse-bin-1.0.3-R2198.1`, invoked directly rather than through
  the updating launcher. SHA256:
  `4c0f960028b603174af7df7bd5051d8c35d6c1aa372a37d18bc770926a0577a7`.
  The binary is checked before every task. The sweep also checks source hashes.
- Proposed new run root: `runs-muse13-contributor-cii-v4-v2`. No results from
  `runs-muse13-cii-v4` are reused. A changed protocol fails closed on resume.
- Same 23-task suite at `tasks/coding-intelligence-index-v4`, publicly named
  VulcanBench-SWE v4. Existing task timeouts and grading configuration stay fixed.
- Benchmark launch requires explicit approval of Contributor's training terms.

## Repairs

1. Pin the executable path and SHA256; never use the auto-updating launcher for
   preflight or solving.
2. Deduplicate completed model receipts by run ID plus source record ID. Different
   child runs can reuse record IDs. Reject conflicting or ambiguous receipts.
   Include retained-frame records, but do not add goal-attribution counters again.
3. Permit private workspace and scratch writes, block contents of other temporary
   directories, and explain `$TMPDIR` restrictions in the task's environment
   context. Preserve ancestor metadata access needed for Muse session locks.
   On macOS use an explicit template with `mktemp`.
4. Stream receipt archives instead of loading an entire session log into memory.
5. Keep cache-aware Contributor API-equivalent estimates separate from actual
   subscription charges.

## Validation evidence

The targeted regression suite passed all 112 tests. Coverage includes binary drift and launcher rejection, child-record
collisions, duplicate mirrors, conflicting/invalid receipts, retained frames,
protocol immutability, effort mapping, pricing, and grader tooling. Real macOS
sandbox checks exercised scratch read/write, temporary files, C compilation and
execution, plus denied reads/writes through symlinks to synthetic cross-run
canaries. These are bounded boundary tests, not proof of complete host isolation.

Live synthetic examples created an addition function, ran Python assertions, and
used the isolated temporary directory. Receipts are in
`logs/muse-harness-validation-20260906-v3/`.

| Requested CLI setting | Result | Seconds | Completed model calls | Tokens |
| --- | --- | ---: | ---: | ---: |
| minimal | Passed | 26.8 | 4 | 95,280 |
| low | Passed | 9.6 | 4 | 95,358 |
| medium | Passed | 51.8 | 5 | 120,401 |
| high | Passed | 109.6 | 5 | 122,678 |
| extra-high (`xhigh`) | Passed | 15.0 | 4 | 98,003 |
| ultra | Passed | 11.0 | 4 | 96,696 |

These tiny examples validate integration, not comparative model performance.
Provider receipts confirm the model, not the effective reasoning-effort value.
Successful CLI acceptance alone does not prove the provider honored an effort.

Meta documents `max` as Standard-only. A Contributor CLI probe nevertheless
completed with `max`; its effective reasoning level is unverified, so this point
is excluded, not relabeled. Meta describes `ultra` as a client-side mode mapped
to the provider's highest supported reasoning tier, potentially with more
delegation. It is not asserted to be a separate higher API reasoning tier.

Earlier failed synthetic attempts are retained in the unsuffixed and `-v2`
validation directories. They exposed a session-lock metadata denial and a
retained-frame parsing error, both repaired before the successful checks.
A final minimal smoke check passed in 58.8 seconds after the last adapter repairs;
its receipts live in the `-final` directory.

## Historical accounting

No original summary or grade was rewritten. The sidecar
`logs/muse-harness-validation-20260906-v3/historical-usage-audit.json` preserves
summary hashes and audited receipt totals for 19 completed runs:

- Original reported tokens: 311,423,951.
- Audited tokens: 319,285,771.
- Audited Standard API-equivalent estimate: $70.80358.

All six completed tasks run under the older CLI had undercounts. Failed DepotCore
is outside these completed-run totals. Usage without a completed receipt cannot
be reconstructed. The prior mixed-version run and its sandbox issues remain
historical limitations; corrected accounting does not repair those conditions.

## Tier and remaining limits

Contributor permits Meta to use submitted prompts and completions for future
model training. That is relevant to keeping benchmark content out of future
training data. The new benchmark is not launched until the user explicitly
accepts this tradeoff. Selecting Contributor is a model choice, not a change to
the user's paid subscription plan.

API-equivalent prices per million tokens: $0.10 input, $0.002 cached input,
$0.20 output. These are not subscription charges or a guarantee of lower
subscription-quota consumption. Contributor is not promised to be faster.

The harness still runs on the local host. Web tools are disabled, but shell
network access is not isolated. A concurrent Fable run can affect timing.
No grading weights, benchmark patches, or task contents changed in this repair.

Official documentation checked in the signed-in browser on September 6, 2026:

- [Pricing and data-use terms](https://dev.meta.ai/docs/pricing-rate-limits/)
- [Reasoning and the Standard-only max setting](https://dev.meta.ai/docs/reasoning/)
- [CLI ultra semantics](https://dev.meta.ai/docs/muse-code/configuration/)
- [Subscription billing](https://dev.meta.ai/docs/muse-code/subscriptions/)
