"""Independent Claude subscription review using the frozen Astra evidence rubric."""
import argparse
import fcntl
import json
import math
import os
import signal
import subprocess
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

from harness import retrospective_judging as base


def parse(stream):
    events = [json.loads(line) for line in stream.splitlines() if line.strip()]
    init = [e for e in events if e.get("type") == "system" and e.get("subtype") == "init"]
    results = [e for e in events if e.get("type") == "result"]
    if len(init) != 1 or init[0].get("tools") or len(results) != 1:
        raise ValueError("Unexpected session, enabled tools, or missing result")
    for e in events:
        for block in e.get("message", {}).get("content", []):
            if block.get("type") in {"tool_use", "server_tool_use"}:
                raise ValueError("Judge attempted tool use")
    result = results[0]
    if result.get("is_error") or result.get("subtype") != "success":
        raise ValueError(f"Judge failed: {result.get('result', result.get('errors'))}")
    vote = result.get("structured_output")
    if vote is None:
        vote = json.loads(result["result"])
    score = vote.get("score")
    if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score) or not 0 <= score <= 100:
        raise ValueError("Invalid score")
    if not isinstance(vote.get("rationale"), str) or not vote["rationale"].strip():
        raise ValueError("Missing rationale")
    usage = result["usage"]
    for key in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"):
        if not isinstance(usage.get(key), int) or usage[key] < 0:
            raise ValueError(f"Missing usage: {key}")
    return {**vote, "usage": usage, "session_id": result["session_id"], "tool_calls": 0,
            "model_reported": init[0]["model"], "model_usage": result.get("modelUsage"),
            "cli_api_equivalent_estimate_usd": result.get("total_cost_usd")}


def judge_vote(prompt, folder, name, settings):
    (folder / f"{name}.prompt.txt").write_text(prompt)
    env = {k: v for k, v in os.environ.items() if not k.startswith("ANTHROPIC_")
           and not k.endswith("_API_KEY") and not k.startswith("CLAUDE_CODE_USE_")}
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="vb-claude-review-") as scratch:
        argv = [settings["claude"], "-p", "--verbose", "--output-format", "stream-json",
                "--model", settings["model"], "--effort", "medium", "--safe-mode",
                "--tools", "", "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
                "--no-session-persistence", "--disable-slash-commands", "--no-chrome",
                "--setting-sources", "", "--system-prompt", base.SYSTEM]
        proc = subprocess.Popen(argv, cwd=scratch, env=env, text=True, stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        try:
            stdout, stderr = proc.communicate(prompt, timeout=600)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            stdout, stderr = proc.communicate()
            (folder / f"{name}.stream.jsonl").write_text(stdout)
            (folder / f"{name}.stderr.txt").write_text(stderr)
            raise RuntimeError("Timeout; no automatic retry") from None
    (folder / f"{name}.stream.jsonl").write_text(stdout)
    (folder / f"{name}.stderr.txt").write_text(stderr)
    if proc.returncode:
        raise RuntimeError(f"Claude exit {proc.returncode}: {stderr[-300:]}")
    vote = parse(stdout)
    if settings["model"] != "opus" and vote["model_reported"] != settings["model"]:
        raise ValueError("Judge model changed")
    return {**vote, "persona": name, "judge_model_requested": settings["model"],
            "judge_effort_requested": "medium", "duration_s": time.monotonic() - started,
            "completed_at": datetime.now(UTC).isoformat(), "argv": argv}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--model", default="opus")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = root / "runs-astra-cii-v4-claude-judging-v1"
    output.mkdir(exist_ok=True)
    settings = {"protocol": "human-like-retrospective-claude-v1", "model": args.model,
                "effort": "medium", "claude": "/Users/morganlinton/.local/bin/claude",
                "cli_version": subprocess.check_output(["/Users/morganlinton/.local/bin/claude", "--version"], text=True).strip(),
                "system": base.SYSTEM, "rubric": base._INSTRUCTION, "personas": base._PERSONAS,
                "utility_sha256": base.digest(Path(__file__).read_bytes()),
                "base_sha256": base.digest(Path(base.__file__).read_bytes()),
                "aggregation_policy": "Independent validation only; no published score changes or reviewer blending"}
    with (output / ".lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        path = output / "protocol.json"
        if path.exists() and json.loads(path.read_text()) != json.loads(base.canonical(settings)):
            raise ValueError("Frozen protocol mismatch")
        base.save(path, settings)
        sources = json.loads((root / "runs-astra-cii-v4-judging-v2/sources.json").read_text())
        tasks = root / "tasks/coding-intelligence-index-v4"
        assert len(sources) == 115
        for run, hashes in sources.items():
            if base.inputs(Path(run), tasks)["source_hashes"] != hashes:
                raise ValueError("Source changed")
        base.save(output / "sources.json", sources)
        base.judge_vote = judge_vote
        base.PROTOCOL = settings["protocol"]
        execution = output / "execution.json"
        if not execution.exists():
            base.save(execution, {"started_at": datetime.now(UTC).isoformat()})
        for run in list(sources)[:args.limit]:
            rec = base.judge_run(Path(run), tasks, output, settings)
            records = [json.loads(p.read_text()) for p in output.glob("*/*/judging.json")]
            votes = [v for r in records for v in r["votes"]]
            report = {"completed_runs": len(records), "expected_runs": 115, "valid_votes": len(votes),
                      "complete": len(records) == 115, "model_reported": sorted({v["model_reported"] for v in votes}),
                      "efforts": {level: {"n": len(rs), "mean_human_like": sum(r["human_like"] for r in rs) / len(rs)}
                                  for level in base.LEVELS if (rs := [r for r in records if r["solver_effort"] == level])},
                      "usage": {key: sum(v["usage"][key] for v in votes) for key in
                                ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")},
                      "updated_at": datetime.now(UTC).isoformat()}
            base.save(output / "summary.json", report)
            print(base.canonical({"event": "task_judged", "task": rec["task_id"], "effort": rec["solver_effort"],
                                  "human_like": rec["human_like"], "completed": len(records)}), flush=True)


if __name__ == "__main__":
    main()
