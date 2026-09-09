# Fable 5.1 and Astra comparison

Status: complete, September 6, 2026. All 230 solver runs and 1,380 selected
ratings passed the final audit. The local PNG/SVG comparison card and executed
audit notebook are in `docs/results/swe-v4-astra-fable51-2026-09`. Nothing has
been published. Muse remains paused.

## Scope

Include all 115 Fable-labeled runs in `runs-effort`, 23 tasks at each of Low,
Medium, High, Extra-high, and Max. The user approved inclusion of solver
fallbacks. Public label: **Fable 5.1 with fallbacks**.

Raw assistant-message and fallback-event checks found 11 runs that switched
from Fable 5.1 to Opus 4.8 after refusal. Per-effort counts: 1, 3, 2, 3, 2.
The default-effort runs in `runs-board` are not included. The existing Astra
population is the 115 runs in `runs-astra-cii-v4`.

The suite is `tasks/coding-intelligence-index-v4`, publicly named
**VulcanBench-SWE v4**. It contains 23 Python replacement implementations for
C-built opaque binaries, not a broad multi-language replacement-code mix.

## Judging

`harness/fable_panel.py` reuses the full-patch Astra retrospective prompts:
three personas per reviewer, GPT-6 Astra and Claude Opus 5 at Medium effort.
Each call is a fresh isolated session with tools disabled. All raw prompts,
responses, source hashes, usage, requested models, and available model receipts
are retained in `runs-fable51-cii-v4-panel-v1`.

Two processes collect ratings concurrently, one sequential batch per reviewer.
Valid saved votes are reused; no solver runs are repeated. One malformed JSON
retry is allowed, with the original raw attempt archived. Score-based retries
are not allowed. Claude pauses before another call if quota is unknown,
overage is active, or a reported window reaches 80% usage.

Do not change the runner or its frozen dependencies while these batches run.
The protocol binds their source hashes. Resume commands, when no matching
process is active:

```sh
.venv/bin/python -u -m harness.fable_panel --reviewer astra
.venv/bin/python -u -m harness.fable_panel_resume
```

The combined score is 50% functional, 15% automated quality, 15% security,
and 20% Code quality. Code quality is the equal average of the two reviewer
means, each formed from its three personas. Existing four-decimal reviewer
means are preserved to match the Astra score profile. It is LLM judgment,
not human ground truth. Solver runtime and tokens exclude post-hoc judging.

## Disclosed reviewer fallbacks

An assistant-message-level audit of Astra's existing Claude reviews found
10 of 345 ratings were produced by Opus 4.8 after automatic refusal fallback,
despite the initial session model being Opus 5. The earlier verification
checked initial session identity and did not catch these switches.

Affected votes: all three StampCore personas at Low, Medium, and High, plus
Extra-high TallyCore maintainability. Original votes and scores are untouched.

The user approved retaining and disclosing reviewer fallbacks on September 6,
2026. The continuation runner requires an explicit Opus 5 to Opus 4.8
session-level refusal event and rejects unexplained model changes. Its
`continuation-policy.json` supplements, rather than replaces, the frozen
original prompts and vote bindings. Final audit command:

```sh
.venv/bin/python -m harness.panel_comparison --include-reviewer-fallbacks
.venv/bin/python -m harness.panel_receipts
```

High QueueCore readability paused after two responses had unescaped quotes
inside inline code in their rationale. A narrow deterministic normalizer
recovers the first response's unchanged score of 70. The later response,
scored 72, is excluded, not selected by score. Both raw streams and the
original failed-vote artifact are preserved. No new reviewer call was used
for the recovery. Future instances use the same narrow normalizer; unrelated
malformed responses still fail or use the single format-only retry allowance.

## Verified completed effort

Fable Low: 23/23 saved solutions reviewed, 138/138 ratings verified directly
against raw streams, prompts, bindings, and unchanged solver evidence.
No Claude reviewer fallback in this effort.

| Metric | Value |
|---|---:|
| Combined score | 91.03630434782609 / 100 |
| Code quality | 80.71717391304348 / 100 |
| Fully passed | 19/23 |
| Mean solver runtime | 26.897049275362317 minutes |
| Raw receipt tokens, including cache | 100,833,634 |
| Historical cache-price-weighted summary units | 15,587,824 |

Both reviewers finished all five efforts. Fable's combined scores are Low
91.04, Medium 91.56, High 90.97, Extra-high 91.53, and Max 92.90. Code quality
scores are 80.72, 82.43, 83.81, 84.96, and 85.36 respectively. Every effort
contains all 23 tasks. The final card includes 11 Fable solver fallback runs
and 10 Claude fallback ratings on Astra, with no Claude fallback ratings on
Fable. All 690 new Fable ratings are complete; Claude made 349 calls for 345
selected ratings, with four excluded calls and two format-recovered ratings.

## Final verification and rendering

`harness/panel_comparison.py` checks matched coverage, all six ratings per
solution, raw/saved agreement, prompt hashes, frozen settings, unique sessions,
reviewer model evidence, original source hashes, exact arithmetic, and unchanged
Astra scores. It refuses a final comparison unless all 230 runs and 1,380
ratings are verified. The existing Astra panel's `opus` alias was later pinned
to Opus 5 by its execution guard; the audit checks actual assistant messages,
not just the alias or initialization event.

`scripts/cii-v4-board/make_astra_fable_card.py` generated the PNG and SVG card.
It requires final audited data and uses focused, labeled dot-and-interval
score plots plus zero-origin runtime bars. It retains exact combined scores,
Code quality, full-pass counts, sample sizes, one-task-standard-error whiskers,
raw receipt token totals, and explicit solver/reviewer fallback counts.
Visually inspect the rendered PNG before sharing. No synthetic preview data
should be mistaken for final benchmark evidence.

Expected output folder: `docs/results/swe-v4-astra-fable51-2026-09`.
Timing must distinguish summed solver duration, calendar span, and judging.
No new API price estimate is claimed on the card. Raw Fable usage receipts
sum to 738,373,965 tokens, including cache, versus 88,865,963 cache-price-weighted
units in the old summaries. Four runs have multiple per-turn usage receipts;
all are summed. Their CLI cost is cumulative per session, so only the final
cost receipt is retained. Original solver summaries are not modified.

`harness/solver_receipts.py` and the executed companion notebook provide the
reproducible accounting checks. The notebook is executed top-to-bottom using
Python, without a Jupyter kernel, since Jupyter packages are not installed.

Focused tests: 50 passed with `--no-cov`. The initial focused invocation also
passed its assertions but failed the repository-wide 80% coverage gate because
it did not run the full repository test suite. Ruff passed for the new audit,
comparison renderer, and comparison tests. No changes have been committed,
pushed, deployed, or published as part of this work.
