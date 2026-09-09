"""Resume the frozen Fable panel with disclosed fallbacks and format recovery.

Additive operational policy authorized September 6, 2026. Preserves all
existing complete votes, raw responses, prompts, and frozen protocol bindings.
"""

from __future__ import annotations

import fcntl
import json
from datetime import UTC, datetime
from pathlib import Path

from harness import claude_retrospective as claude
from harness import fable_panel as original
from harness import retrospective_judging as base
from harness.claude_review_guard import quota_ok
from harness.panel_comparison import claude_model_evidence, protocol_check, read, require
from harness.review_format import parse_claude_preserving_rating

OUTPUT = original.OUTPUT / "claude"


def checked_stream(path):
    stream = path.read_text()
    events = [json.loads(line) for line in stream.splitlines() if line.strip()]
    vote = parse_claude_preserving_rating(stream)
    init = next(e for e in events if e.get("type") == "system" and e.get("subtype") == "init")
    require(
        init.get("apiKeySource") == "none" and not init.get("mcp_servers"), "Billing/tools changed"
    )
    require(vote["model_reported"] == "claude-opus-5", "Initial reviewer model changed")
    evidence = claude_model_evidence(events, allow_fallbacks=True)
    quota = original.quota_from(path)
    require(quota and quota.get("isUsingOverage") is False, "Unknown/overage billing")
    return vote, events, evidence


def recovered_vote(path, folder, name, settings):
    vote, events, identity = checked_stream(path)
    result = next(e for e in events if e.get("type") == "result")
    # This argv is exactly the constant transport invocation in the frozen
    # Claude utility. Flag reconstruction instead of claiming a saved receipt.
    argv = [
        settings["claude"],
        "-p",
        "--verbose",
        "--output-format",
        "stream-json",
        "--model",
        settings["model"],
        "--effort",
        "medium",
        "--safe-mode",
        "--tools",
        "",
        "--strict-mcp-config",
        "--mcp-config",
        '{"mcpServers":{}}',
        "--no-session-persistence",
        "--disable-slash-commands",
        "--no-chrome",
        "--setting-sources",
        "",
        "--system-prompt",
        base.SYSTEM,
    ]
    return {
        **vote,
        "persona": name,
        "judge_model_requested": settings["model"],
        "judge_effort_requested": "medium",
        "duration_s": result["duration_ms"] / 1000,
        "duration_basis": "CLI receipt, recovered call only",
        "completed_at": datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(),
        "completed_at_basis": "original stream file modification time",
        "argv": argv,
        "argv_reconstructed_from_frozen_transport": True,
        "raw_stream_relative": str(path.relative_to(folder)),
        "raw_stream_sha256": base.digest(path.read_bytes()),
        "reviewer_model_evidence": identity,
        "format_recovery": "Escape unescaped double quotes inside backtick-delimited code; score unchanged",
        "selection_policy": "First recoverable response in chronological attempt order; no new call",
    }


def recover_failed(folder, name, settings, data):
    saved = folder / f"{name}.json"
    if not saved.exists() or read(saved).get("status") != "failed":
        return
    failed = read(saved)
    binding = base.digest(
        base.canonical({"sources": data["source_hashes"], "settings": settings}).encode()
    )
    require(failed["binding"] == binding, "Failed vote binding changed")
    paths = sorted(folder.glob(f"retries/{name}-attempt-*"))
    candidates = [p / f"{name}.stream.jsonl" for p in paths] + [folder / f"{name}.stream.jsonl"]
    errors = []
    for path in candidates:
        try:
            vote = recovered_vote(path, folder, name, settings)
        except (ValueError, KeyError) as exc:
            errors.append(str(exc))
            continue
        require(
            path.with_name(f"{name}.prompt.txt").read_text()
            == (folder / f"{name}.prompt.txt").read_text(),
            "Retry prompt changed",
        )
        original.frozen(folder / f"{name}.failed-before-recovery.json", failed)
        base.save(
            saved,
            {
                **vote,
                "status": "complete",
                "binding": binding,
                "prompt_sha256": failed["prompt_sha256"],
            },
        )
        print(
            base.canonical(
                {
                    "event": "recovered",
                    "folder": str(folder),
                    "persona": name,
                    "score": vote["score"],
                    "selected_raw": str(path),
                }
            ),
            flush=True,
        )
        return
    raise ValueError(f"No format-only recovery possible: {errors}")


def main():
    with (OUTPUT / ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        settings = read(OUTPUT / "protocol.json")
        sources, identities = original.source_manifest()
        original.frozen(OUTPUT / "sources.json", sources)
        original.frozen(OUTPUT / "solver-identity.json", identities)
        protocol_check(settings, "claude")
        policy = {
            "authorized": "User confirmed reviewer fallback inclusion and continuation September 6, 2026",
            "allowed_fallback": "Opus 5 to Opus 4.8, explicit session-level refusal event required",
            "format_recovery": "Only escape unescaped quotes in backtick code; retain earliest recoverable rating",
            "new_calls_for_existing_recoverable_votes": 0,
            "malformed_retry_limit": 1,
            "quota_stop_fraction": 0.80,
            "source_sha256": {
                p.name: base.digest(p.read_bytes())
                for p in (Path(__file__), Path(__file__).with_name("review_format.py"))
            },
        }
        original.frozen(OUTPUT / "continuation-policy.json", policy)
        if (OUTPUT / "pause.json").exists():
            (OUTPUT / "pause.json").rename(OUTPUT / "pause-before-continuation.json")

        def guarded(prompt, folder, name, config):
            executable = Path(config["claude"])
            require(
                base.digest(executable.read_bytes()) == config["binary_sha256"],
                "Reviewer binary changed",
            )
            latest = max(OUTPUT.rglob("*.stream.jsonl"), key=lambda p: p.stat().st_mtime)
            require(quota_ok(original.quota_from(latest)), "Claude quota guard paused")
            try:
                vote = claude.judge_vote(prompt, folder, name, config)
            except json.JSONDecodeError:
                stream = folder / f"{name}.stream.jsonl"
                try:
                    return recovered_vote(stream, folder, name, config)
                except json.JSONDecodeError:
                    archive = folder / "retries" / f"{name}-attempt-1"
                    archive.mkdir(parents=True, exist_ok=False)
                    for suffix in ("prompt.txt", "stream.jsonl", "stderr.txt"):
                        (folder / f"{name}.{suffix}").rename(archive / f"{name}.{suffix}")
                    return guarded(prompt, folder, name, config)
            _, _, identity = checked_stream(folder / f"{name}.stream.jsonl")
            return {**vote, "reviewer_model_evidence": identity}

        base.judge_vote = guarded
        base.PROTOCOL = settings["protocol"]
        try:
            for run_path, hashes in sources.items():
                run = Path(run_path)
                data = base.inputs(run, original.TASKS)
                require(data["source_hashes"] == hashes, "Source changed")
                folder = OUTPUT / run.parent.name / run.name
                for name, _ in base._PERSONAS:
                    recover_failed(folder, name, settings, data)
                rec = base.judge_run(run, original.TASKS, OUTPUT, settings)
                status = original.report(OUTPUT)
                print(
                    base.canonical(
                        {
                            "reviewer": "claude",
                            "effort": rec["solver_effort"],
                            "task": rec["task_id"],
                            "completed": status["completed_runs"],
                        }
                    ),
                    flush=True,
                )
        except Exception as exc:
            original.report(OUTPUT)
            base.save(
                OUTPUT / "pause.json", {"error": str(exc), "at": datetime.now(UTC).isoformat()}
            )
            raise


if __name__ == "__main__":
    main()
