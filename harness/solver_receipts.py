"""Additive raw-token accounting from original CLI result receipts.

Fable's historical summary folds cache tokens into price-equivalent units.
This reader does not alter those summaries. It sums per-turn usage receipts
and takes only the final cumulative CLI cost for each Claude session.
"""

import json
import math

from harness.retrospective_judging import digest

CLAUDE_KEYS = (
    "input_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
    "output_tokens",
)


def claude_receipts(results):
    if not results:
        raise ValueError("Missing CLI result")
    tokens = {key: 0 for key in CLAUDE_KEYS}
    costs = {}
    seen = set()
    for event in results:
        if event.get("subtype") != "success" or event.get("is_error"):
            raise ValueError("Unsuccessful solver receipt")
        identity = event.get("uuid")
        if identity is not None:
            if identity in seen:
                raise ValueError("Duplicate solver receipt")
            seen.add(identity)
        for key in tokens:
            value = event["usage"][key]
            if type(value) is not int or value < 0:
                raise ValueError("Invalid raw solver token receipt")
            tokens[key] += value
        session = event["session_id"]
        cost = event["total_cost_usd"]
        if (
            not isinstance(cost, (int, float))
            or not math.isfinite(cost)
            or cost < costs.get(session, 0)
        ):
            raise ValueError("Invalid cumulative CLI cost")
        costs[session] = cost
    return {
        "raw_tokens": sum(tokens.values()),
        "usage": tokens,
        "result_receipts": len(results),
        "cli_api_equivalent_estimate_usd": sum(costs.values()),
        "sessions": len(costs),
    }


def solver_receipt(run, summary):
    path = run / "cli-agent-stream.jsonl"
    events = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if summary["model"] == "claude-code:claude-fable-5-1":
        results = [e for e in events if e.get("type") == "result"]
        result = claude_receipts(results)
        last = results[-1]["usage"]
        effective = (
            round(
                last["input_tokens"]
                + last["cache_read_input_tokens"] * 0.1
                + last["cache_creation_input_tokens"] * 1.25
            )
            + last["output_tokens"]
        )
        if effective != summary["total_tokens"]:
            raise ValueError("Historical token summary no longer matches its cache-price fold")
        result["historical_summary_unit"] = (
            "Cache-price-weighted units from last result, not raw tokens"
        )
    elif summary["model"] == "codex:gpt-6-astra":
        receipts = [e["usage"] for e in events if e.get("type") == "turn.completed"]
        if len(receipts) != 1:
            raise ValueError("Unexpected Astra result count")
        usage = receipts[0]
        total = usage["input_tokens"] + usage["output_tokens"]
        if total != summary["total_tokens"] or usage["cached_input_tokens"] > usage["input_tokens"]:
            raise ValueError("Astra receipt/summary mismatch")
        result = {
            "raw_tokens": total,
            "usage": usage,
            "result_receipts": 1,
            "historical_summary_unit": "Raw input plus output; cached input included in input",
        }
    else:
        raise ValueError("Unknown solver")
    return {**result, "stream_sha256": digest(path.read_bytes())}
