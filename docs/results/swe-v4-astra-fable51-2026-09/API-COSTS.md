# API-equivalent solver costs

The standard-rate estimate is **$225.04 for Astra and $1,159.10 for Fable with
fallbacks**, for 115 solver runs each. Astra's estimate is 80.59% lower. These
are hypothetical inference charges, not amounts paid through subscriptions.
Judging and local infrastructure are excluded.

## Cost by effort

Each effort includes the same 23 tasks, including partial functional results.
Per-task values are means, not the cost of a typical or median run.

| Effort | Astra per task | Fable per task | Astra total | Fable total | Astra long-context upper total |
|---|---:|---:|---:|---:|---:|
| Low | $1.72 | $7.96 | $39.60 | $183.17 | $75.53 |
| Medium | $1.48 | $9.19 | $34.07 | $211.28 | $64.19 |
| High | $1.71 | $9.70 | $39.35 | $223.14 | $74.00 |
| Extra-high | $2.30 | $14.49 | $52.95 | $333.17 | $97.84 |
| Max | $2.57 | $9.06 | $59.07 | $208.35 | $107.86 |
| Full sweep | | | **$225.04** | **$1,159.10** | **$419.42** |

Totals are calculated from unrounded values. Astra remains cheaper at every
matched effort even at the conservative long-context bound. At that bound its
full-sweep estimate is 63.82% lower, rather than 80.59% lower.

## Verified prices

Official first-party Standard API prices checked September 6, 2026. All rates
below are USD per million tokens; no Batch, Flex, Fast, or regional modifier.

| Model | Uncached input | Cache read | Cache write (5m for Claude) | 1h Claude cache write | Output |
|---|---:|---:|---:|---:|---:|
| GPT-6 Astra | $10 | $1 | $12.50 | Not used | $50 |
| Claude Fable 5.1 | $10 | $0.25 | $12.50 | $20 | $50 |
| Claude Opus 5 / Opus 4.8 | $5 | $0.50 | $6.25 | $10 | $25 |
| Claude Haiku 4.5 | $1 | $0.10 | $1.25 | $2 | $5 |

Sources: [GPT-6 Astra model pricing](https://developers.openai.com/api/docs/models/gpt-6-astra),
[Claude pricing](https://platform.claude.com/docs/en/about-claude/pricing), and
[Fable 5.1 pricing](https://platform.claude.com/docs/en/models/fable-5-1/overview).

## Astra accounting and uncertainty

The standard estimate is `(input - cached_input) * $10/M + cached_input * $1/M
+ output * $50/M`. Cached input is already included in input; reasoning is
already included in output. Neither is counted twice. The saved receipts report
zero cache-write tokens.

The published price doubles input/cache rates and multiplies output rates by
1.5 for individual requests above 272,000 input tokens. The saved CLI receipts
aggregate multiple model calls, and the runner used ephemeral sessions, so
per-request context sizes cannot be reconstructed. Cumulative task input is
not treated as a single API request.

The central estimate assumes short-context rates. The conservative bound applies
long-context rates to all usage in each run whose cumulative input exceeds
272,000, and leaves the one shorter run at base rates. This is a sensitivity
bound, not a confidence interval or a claim that all those calls used long
context. It covers exposed token usage under the stated Standard-rate scope.

## Fable accounting and reconciliation

Fable estimates use the final cumulative `modelUsage` receipt per session, not
the sum of cumulative receipts. Four multi-result runs therefore do not get
their earlier usage charged twice. The receipts include actual Fable usage,
Opus 5 and Opus 4.8 fallback/auxiliary usage, and small Haiku CLI calls. The
rate for each actual model is applied separately, including Fable's discounted
cache reads and observed 5-minute versus 1-hour cache writes.

The 115 sessions expose 252 model-level cost entries. Of these, 251 independently
reconcile to the verified rates using exposed cache information. One internal
Opus 5 call on Medium StampCore has no model-specific cache TTL in the assistant
stream; its $0.40398125 list-price receipt is retained and exactly matches the
5-minute cache-write rate. It is not silently assigned the Fable rate.

Full-sweep cost components: Fable $844.37706325, Opus 4.8 $311.03574850,
Opus 5 $3.50980675, and Haiku $0.178525. These sum to $1,159.10114350.
CLI auxiliary accounting differs between providers; these are estimates from
exposed receipts, not independently observed API invoices.

## Reproduction and validation

Run `.venv/bin/python -m harness.api_equivalent_costs` and then
`.venv/bin/python scripts/cii-v4-board/make_astra_fable_effort_card.py --with-costs`.
The generator verifies every source stream against the frozen comparison hash.
It writes a [per-run ledger](api-equivalent-costs.json) and
[effort totals with scenario bounds](api-equivalent-costs.csv).

The original scores, 20% Code quality weight, raw votes, solver receipts and
previous cards remain unchanged. Tests cover cache inclusion, reasoning-token
inclusion, both cache durations, model fallback rates, cumulative receipts,
duplicate rejection and invalid pricing. See `effort-cost-card-qa.json` for
the final artifact checks.
