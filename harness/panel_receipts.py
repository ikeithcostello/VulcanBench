"""Final accounting and provenance checks for every reviewer call, even retries."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime

from harness import retrospective_judging as base
from harness.panel_comparison import OUTPUT, PANELS, claude_model_evidence, read, require


def reviewer_receipts(output, reviewer):
    records = [read(p) for p in output.glob("*/*/judging.json")]
    require(len(records) == 115, "Reviewer not finished")
    selected = {}
    votes = []
    for record in records:
        folder = output / record["solver_effort"] / record["run_id"]
        for vote in record["votes"]:
            raw = folder / vote.get("raw_stream_relative", f"{vote['persona']}.stream.jsonl")
            require(raw not in selected, "Selected raw response counted twice")
            selected[raw] = vote
            votes.append(vote)
    require(len(selected) == 345, "Reviewer vote coverage mismatch")
    usage = Counter()
    sessions = set()
    calls = []
    for path in sorted(output.rglob("*.stream.jsonl")):
        events = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        if reviewer == "claude":
            init = [e for e in events if e.get("type") == "system" and e.get("subtype") == "init"]
            results = [e for e in events if e.get("type") == "result"]
            require(len(init) == len(results) == 1, "Unexpected Claude call envelope")
            require(
                init[0]["model"] == "claude-opus-5"
                and not init[0].get("tools")
                and not init[0].get("mcp_servers")
                and init[0].get("apiKeySource") == "none",
                "Claude call isolation or billing changed",
            )
            for event in events:
                for block in event.get("message", {}).get("content", []):
                    require(
                        block.get("type") not in {"tool_use", "server_tool_use"},
                        "Reviewer used tools",
                    )
                if event.get("type") == "rate_limit_event":
                    require(
                        event["rate_limit_info"].get("isUsingOverage") is False, "Reviewer overage"
                    )
            result = results[0]
            require(
                result["subtype"] == "success" and not result["is_error"],
                "Failed call needs separate accounting",
            )
            session = result["session_id"]
            raw_usage = {
                k: result["usage"][k]
                for k in (
                    "input_tokens",
                    "output_tokens",
                    "cache_read_input_tokens",
                    "cache_creation_input_tokens",
                )
            }
            call = {
                "cli_api_equivalent_estimate_usd": result["total_cost_usd"],
                "cli_duration_s": result["duration_ms"] / 1000,
                **claude_model_evidence(events, allow_fallbacks=True),
            }
        else:
            parsed = base.parse_stream(path.read_text())
            session = parsed["session_id"]
            raw_usage = parsed["usage"]
            call = {"model_identity": "requested-only", "fallback": False}
        require(session not in sessions, "Duplicate reviewer session")
        sessions.add(session)
        require(all(type(v) is int and v >= 0 for v in raw_usage.values()), "Invalid call usage")
        usage.update(raw_usage)
        call.update(
            {
                "path": str(path),
                "sha256": base.digest(path.read_bytes()),
                "session_id": session,
                "included_in_score": path in selected,
                "format_recovered": bool(selected.get(path, {}).get("format_recovery")),
                "usage": raw_usage,
            }
        )
        calls.append(call)
    require(
        len(calls) >= 345 and sum(c["included_in_score"] for c in calls) == 345, "Missing raw calls"
    )
    start = datetime.fromisoformat(read(output / "execution.json")["started_at"])
    end = max(datetime.fromisoformat(v["completed_at"]) for v in votes)
    if reviewer == "astra":
        total_tokens = usage["input_tokens"] + usage["output_tokens"]
    else:
        total_tokens = sum(usage.values())
    return {
        "all_calls": len(calls),
        "selected_ratings": 345,
        "excluded_calls": len(calls) - 345,
        "format_recovered_ratings": sum(c["format_recovered"] for c in calls),
        "fallback_ratings": sum(c["included_in_score"] and c["fallback"] for c in calls),
        "usage_including_excluded_calls": dict(usage),
        "raw_tokens_including_excluded_calls": total_tokens,
        "cli_api_equivalent_estimate_usd": sum(c["cli_api_equivalent_estimate_usd"] for c in calls)
        if reviewer == "claude"
        else None,
        "cost_note": "CLI-reported API-equivalent estimate, not subscription cash charge",
        "elapsed_seconds_including_pauses": (end - start).total_seconds(),
        "valid_vote_active_seconds": sum(v["duration_s"] for v in votes),
        "started_at": start.isoformat(),
        "finished_at": end.isoformat(),
        "calls": calls,
    }


def main():
    result = {}
    for model, outputs in PANELS.items():
        for reviewer, output in zip(("astra", "claude"), outputs, strict=True):
            result[f"{model}/{reviewer}"] = reviewer_receipts(output, reviewer)
    base.save(OUTPUT / "reviewer-accounting.json", result)
    print(
        json.dumps(
            {
                key: {k: v for k, v in value.items() if k != "calls"}
                for key, value in result.items()
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
