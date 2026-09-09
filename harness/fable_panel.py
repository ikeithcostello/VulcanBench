"""Retrospective Fable 5.1 panel, including explicitly disclosed CLI fallbacks.

Reuse Astra's full-patch prompts and judge transports without changing frozen
Astra utilities or any solver artifact. Each reviewer runs in its own process.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from harness import claude_retrospective as claude
from harness import retrospective_judging as base
from harness.claude_review_guard import quota_ok

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs-effort"
TASKS = ROOT / "tasks/coding-intelligence-index-v4"
OUTPUT = ROOT / "runs-fable51-cii-v4-panel-v1"
CLAUDE = Path.home() / ".local/share/claude/versions/2.1.261"
CODEX = Path.home() / ".nvm/versions/node/v22.11.0/lib/node_modules/@openai/codex/bin/codex.js"


def source_manifest():
    task_ids = set(json.loads((TASKS / "suite.json").read_text())["tasks"])
    sources, audit = {}, []
    for level in base.LEVELS:
        paths = sorted((RUNS / level).glob("*/summary.json"))
        assert len(paths) == 23, f"Wrong coverage: {level}"
        seen = set()
        for path in paths:
            data = base.inputs(path.parent, TASKS)
            summary = data["summary"]
            assert summary["model"] == "claude-code:claude-fable-5-1"
            assert summary["effort"]["requested"] == level and summary["effort"]["supported"]
            assert summary["task_id"] not in seen
            seen.add(summary["task_id"])
            stream = path.parent / "cli-agent-stream.jsonl"
            events = [json.loads(line) for line in stream.read_text().splitlines()]
            init = [e for e in events if e.get("type") == "system" and e.get("subtype") == "init"]
            assert init and init[0]["model"] == "claude-fable-5-1"
            fallback = [e for e in events if e.get("subtype") == "model_refusal_fallback"]
            models = {e["message"]["model"] for e in events if e.get("type") == "assistant"
                      and e.get("message", {}).get("model")}
            allowed = {"claude-fable-5-1"}
            if fallback:
                assert all(e["original_model"] == "claude-fable-5-1" and
                           e["fallback_model"] == "claude-opus-4-8" and e["scope"] == "session"
                           for e in fallback)
                allowed.add("claude-opus-4-8")
            assert models <= allowed, (path, models)
            sources[str(path.parent.resolve())] = data["source_hashes"]
            audit.append({"run_id": summary["run_id"], "task": summary["task_id"], "effort": level,
                          "fallback": bool(fallback), "assistant_models": sorted(models),
                          "cli_version": summary["cli_agent"]["harness_version"],
                          "stream_sha256": base.digest(stream.read_bytes())})
        assert seen == task_ids
    assert len(sources) == 115 and sum(r["fallback"] for r in audit) == 11
    return sources, audit


def frozen(path, value):
    if path.exists():
        assert json.loads(path.read_text()) == json.loads(base.canonical(value)), f"Changed manifest: {path}"
    else:
        base.save(path, value)


def quota_from(stream):
    rates = []
    for line in stream.read_text().splitlines():
        event = json.loads(line)
        if event.get("type") == "rate_limit_event":
            rates.append(event["rate_limit_info"])
    return rates[-1] if rates else None


def report(output):
    records = [json.loads(p.read_text()) for p in output.glob("*/*/judging.json")]
    votes = [v for r in records for v in r["votes"]]
    result = {"completed_runs": len(records), "expected_runs": 115, "valid_votes": len(votes),
              "complete": len(records) == 115,
              "efforts": {level: {"n": len(rs), "mean_human_like": sum(r["human_like"] for r in rs)/len(rs)}
                          for level in base.LEVELS if (rs := [r for r in records if r["solver_effort"] == level])},
              "updated_at": datetime.now(UTC).isoformat()}
    base.save(output / "summary.json", result)
    return result


def main():  # noqa: PLR0915
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviewer", choices=("astra", "claude"), required=True)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    sources, audit = source_manifest()
    print(base.canonical({"runs": len(sources), "fallback_runs": 11, "reviewer": args.reviewer,
                          "expected_votes": 345}), flush=True)
    if args.dry_run:
        return
    output = OUTPUT / args.reviewer
    output.mkdir(parents=True, exist_ok=True)
    with (output / ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        frozen(output / "sources.json", sources)
        frozen(output / "solver-identity.json", audit)
        executable = CODEX if args.reviewer == "astra" else CLAUDE
        settings = {"protocol": "fable51-equal-panel-v1", "reviewer": args.reviewer,
                    "model": "gpt-6-astra" if args.reviewer == "astra" else "claude-opus-5",
                    "effort": "medium", "codex": str(CODEX), "claude": str(CLAUDE), "timeout": 600,
                    "cli_version": subprocess.check_output([str(executable), "--version"], text=True).strip(),
                    "binary_sha256": base.digest(executable.read_bytes()),
                    "system": base.SYSTEM, "personas": base._PERSONAS, "instruction": base._INSTRUCTION,
                    "full_patch": True, "config": base.CONFIG, "schema": base.SCHEMA,
                    "fallback_policy": "Include all 11 solver fallback runs; user approved disclosure on card",
                    "aggregation": "Mean of three persona votes per reviewer, then equal reviewer mean; code quality weight 20%",
                    "source_code": {str(p.relative_to(ROOT)): base.digest(p.read_bytes()) for p in
                                    [Path(__file__), Path(base.__file__), Path(claude.__file__)]},
                    "retry_policy": "One malformed JSON response retry per vote; archive failures, never retry by score",
                    "claude_quota_stop_fraction": .80}
        frozen(output / "protocol.json", settings)
        if not (output / "execution.json").exists():
            base.save(output / "execution.json", {"started_at": datetime.now(UTC).isoformat()})
        original = base.judge_vote if args.reviewer == "astra" else claude.judge_vote

        def guarded(prompt, folder, name, config):
            assert base.digest(executable.read_bytes()) == config["binary_sha256"], "Reviewer binary changed"
            if args.reviewer == "claude":
                existing = sorted(output.rglob("*.stream.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
                if existing and not quota_ok(quota_from(existing[0])):
                    raise RuntimeError("Claude quota guard paused before next call")
            try:
                vote = original(prompt, folder, name, config)
            except json.JSONDecodeError:
                archive = folder / "retries" / f"{name}-attempt-1"
                archive.mkdir(parents=True, exist_ok=False)
                for suffix in ("prompt.txt", "stream.jsonl", "stderr.txt"):
                    (folder / f"{name}.{suffix}").rename(archive / f"{name}.{suffix}")
                return guarded(prompt, folder, name, config)
            if args.reviewer == "claude":
                stream = folder / f"{name}.stream.jsonl"
                events = [json.loads(line) for line in stream.read_text().splitlines()]
                init = next(e for e in events if e.get("type") == "system" and e.get("subtype") == "init")
                assert init.get("apiKeySource") == "none" and not init.get("mcp_servers")
                assert all(e.get("message", {}).get("model", "claude-opus-5") == "claude-opus-5"
                           for e in events if e.get("type") == "assistant")
                quota = quota_from(stream)
                assert quota and quota.get("isUsingOverage") is False, "Unknown or overage billing"
            return vote

        base.judge_vote = guarded
        base.PROTOCOL = settings["protocol"]
        try:
            for run in list(sources)[:args.limit]:
                assert base.inputs(Path(run), TASKS)["source_hashes"] == sources[run]
                rec = base.judge_run(Path(run), TASKS, output, settings)
                status = report(output)
                print(base.canonical({"reviewer": args.reviewer, "effort": rec["solver_effort"],
                                      "task": rec["task_id"], "completed": status["completed_runs"]}), flush=True)
        except Exception as exc:
            report(output)
            base.save(output / "pause.json", {"error": str(exc), "at": datetime.now(UTC).isoformat()})
            raise


if __name__ == "__main__":
    main()
