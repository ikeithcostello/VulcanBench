"""Audit all saved reviewer evidence and compute an equal-model review panel."""
import json
import statistics
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from harness import retrospective_judging as base  # noqa: E402
from harness.claude_retrospective import parse  # noqa: E402
from harness.evaluator.reviewed_score import reviewed_score  # noqa: E402


def main():  # noqa: PLR0915
    output = ROOT / "runs-astra-cii-v4-claude-judging-v1"
    settings = json.loads((output / "protocol.json").read_text())
    sources = json.loads((output / "sources.json").read_text())
    assert len(sources) == 115
    rows, votes, sessions = [], [], set()
    for source, hashes in sources.items():
        run = Path(source)
        data = base.inputs(run, ROOT / "tasks/coding-intelligence-index-v4")
        assert data["source_hashes"] == hashes
        folder = output / run.parent.name / run.name
        record = json.loads((folder / "judging.json").read_text())
        assert record["status"] == "complete" and record["source_hashes"] == hashes
        binding = base.digest(base.canonical({"sources": hashes, "settings": settings}).encode())
        checked = []
        for name, persona in base._PERSONAS:
            vote = json.loads((folder / f"{name}.json").read_text())
            prompt = base.prompt_for(data, persona)
            assert (folder / f"{name}.prompt.txt").read_text() == prompt
            assert vote["binding"] == binding and vote["prompt_sha256"] == base.digest(prompt.encode())
            parsed = parse((folder / f"{name}.stream.jsonl").read_text())
            assert parsed["model_reported"] == "claude-opus-5"
            assert vote["status"] == "complete" and vote["judge_effort_requested"] == "medium"
            for key in ("score", "rationale", "usage", "session_id"):
                assert vote[key] == parsed[key]
            assert vote["session_id"] not in sessions
            sessions.add(vote["session_id"])
            checked.append(vote)
        assert record["votes"] == checked
        assert record["human_like"] == round(sum(v["score"] for v in checked) / 300, 4)
        astra = json.loads((ROOT / "runs-astra-cii-v4-judging-v2" / run.parent.name / run.name / "judging.json").read_text())
        assert astra["source_hashes"] == hashes
        astra_folder = ROOT / "runs-astra-cii-v4-judging-v2" / run.parent.name / run.name
        for name, persona in base._PERSONAS:
            raw_astra = base.parse_stream((astra_folder / f"{name}.stream.jsonl").read_text())
            saved_astra = json.loads((astra_folder / f"{name}.json").read_text())
            assert (astra_folder / f"{name}.prompt.txt").read_text() == base.prompt_for(data, persona)
            assert raw_astra["score"] == saved_astra["score"]
            assert any(v["persona"] == name and v["score"] == raw_astra["score"] for v in astra["votes"])
        # Retain existing per-model four-decimal scores, then average equally.
        panel = (astra["human_like"] + record["human_like"]) / 2
        score = reviewed_score({**data["summary"]["scores"], "human_like": panel})
        rows.append({"effort": run.parent.name, "task": record["task_id"], "run_id": run.name,
                     "astra": astra["human_like"], "claude": record["human_like"], "panel": panel,
                     "combined": score, "functional": data["summary"]["scores"]["functional"],
                     "quality": data["summary"]["scores"]["quality"], "security": data["summary"]["scores"]["security"]})
        votes.extend(checked)
    assert len(votes) == 345
    all_streams = list(output.rglob("*.stream.jsonl"))
    usage = {k: 0 for k in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")}
    api_cost = 0
    active_ms = 0
    for path in all_streams:
        events = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        results = [e for e in events if e.get("type") == "result"]
        assert len(results) == 1
        result = results[0]
        for key in usage:
            usage[key] += result["usage"][key]
        api_cost += result["total_cost_usd"]
        active_ms += result["duration_ms"]
        init = [e for e in events if e.get("type") == "system" and e.get("subtype") == "init"]
        assert len(init) == 1 and init[0]["model"] == "claude-opus-5" and not init[0]["tools"] and not init[0]["mcp_servers"]
        assert init[0].get("apiKeySource") == "none"
        for e in events:
            for block in e.get("message", {}).get("content", []):
                assert block.get("type") not in {"tool_use", "server_tool_use"}
            if e.get("type") == "rate_limit_event":
                assert e["rate_limit_info"]["isUsingOverage"] is False
    start = datetime.fromisoformat(json.loads((output / "execution.json").read_text())["started_at"])
    end = max(datetime.fromisoformat(v["completed_at"]) for v in votes)
    efforts = {level: {key: statistics.mean(r[key] for r in rows if r["effort"] == level)
                        for key in ("astra", "claude", "panel", "combined")}
               for level in base.LEVELS}
    result = {"profile": "swe-v4-reviewed-equal-panel-2026-09-05", "runs": 115, "valid_votes": 345,
              "total_claude_calls": len(all_streams), "excluded_format_failures": len(all_streams)-345,
              "source_hashes_unchanged": True, "raw_votes_and_prompts_verified": True,
              "model": "claude-opus-5", "no_overage_detected": True, "usage_including_retries": usage,
              "total_tokens": sum(usage.values()), "cli_api_equivalent_estimate_usd": api_cost,
              "api_cost_note": "CLI-reported estimate, not subscription cash charge; includes failed attempts",
              "claude_active_request_seconds": active_ms / 1000,
              "claude_elapsed_seconds_including_pauses": (end-start).total_seconds(),
              "efforts": efforts, "rows": rows,
              "largest_review_gaps": sorted(rows, key=lambda r: abs(r["astra"]-r["claude"]), reverse=True)[:10]}
    base.save(output / "verification.json", result)
    print(json.dumps({k:v for k,v in result.items() if k not in ("rows", "largest_review_gaps")}, indent=2))


if __name__ == "__main__":
    main()
