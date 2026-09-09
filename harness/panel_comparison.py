"""Verify saved Astra/Fable evidence and derive the fixed 20% review profile.

Read-only with respect to solver and reviewer artifacts. No regrading, solver
retries, score-based exclusions, or imputation. Partial audits cannot be used
to render a final comparison card.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from harness import claude_retrospective as claude
from harness import retrospective_judging as base
from harness.evaluator.reviewed_score import WEIGHTS, reviewed_score
from harness.fable_panel import source_manifest
from harness.review_format import parse_claude_preserving_rating
from harness.solver_receipts import solver_receipt

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "tasks/coding-intelligence-index-v4"
OUTPUT = ROOT / "docs/results/swe-v4-astra-fable51-2026-09"
PANELS = {
    "astra": (ROOT / "runs-astra-cii-v4-judging-v2", ROOT / "runs-astra-cii-v4-claude-judging-v1"),
    "fable": (ROOT / "runs-fable51-cii-v4-panel-v1/astra", ROOT / "runs-fable51-cii-v4-panel-v1/claude"),
}
SOLVERS = {"astra": "codex:gpt-6-astra", "fable": "claude-code:claude-fable-5-1"}


def read(path):
    return json.loads(path.read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def average_panel(astra, opus):
    for value in (astra, opus):
        require(type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1,
                "Missing or invalid reviewer score")
    return (astra + opus) / 2


def mean_se(values):
    require(len(values) > 1 and all(math.isfinite(v) for v in values), "Invalid metric series")
    return {"mean": statistics.mean(values), "se": statistics.stdev(values) / math.sqrt(len(values))}


def protocol_check(settings, reviewer):
    require(settings["system"] == base.SYSTEM, "Changed system prompt")
    require(settings.get("instruction", settings.get("rubric")) == base._INSTRUCTION, "Changed rubric")
    require(settings["personas"] == [list(p) for p in base._PERSONAS], "Changed personas")
    require(settings["effort"] == "medium", "Changed reviewer effort")
    require(settings["model"] in ({"gpt-6-astra"} if reviewer == "astra" else {"opus", "claude-opus-5"}),
            "Changed reviewer model")
    if reviewer == "astra":
        require(settings["full_patch"] and settings["config"] == list(base.CONFIG)
                and settings["schema"] == base.SCHEMA, "Changed Astra transport protocol")
    for rel, digest in settings.get("source_code", {}).items():
        require(base.digest((ROOT / rel).read_bytes()) == digest, f"Changed frozen code: {rel}")


def claude_model_evidence(events, allow_fallbacks):
    models = {e.get("message", {}).get("model") for e in events if e.get("type") == "assistant"}
    fallbacks = [e for e in events if e.get("subtype") == "model_refusal_fallback"]
    allowed = {"claude-opus-5"}
    if fallbacks:
        require(allow_fallbacks, "Claude reviewer fallback requires disclosed-policy approval")
        require(all(e.get("original_model") == "claude-opus-5" and e.get("fallback_model") == "claude-opus-4-8"
                    and e.get("scope") == "session" and e.get("trigger") == "refusal" for e in fallbacks),
                "Unexpected reviewer fallback")
        allowed.add("claude-opus-4-8")
    require(models and models <= allowed, "Claude assistant model drift")
    return {"assistant_models": sorted(models), "fallback": bool(fallbacks)}


def audit_record(folder, data, settings, reviewer, sessions, allow_fallbacks=False):
    record = read(folder / "judging.json")
    hashes = data["source_hashes"]
    binding = base.digest(base.canonical({"sources": hashes, "settings": settings}).encode())
    require(record["status"] == "complete" and record["source_hashes"] == hashes, "Invalid review record")
    require(record["task_id"] == data["summary"]["task_id"] and record["run_id"] == data["summary"]["run_id"],
            "Review assigned to wrong task/run")
    require(record["solver_effort"] == data["summary"]["effort"]["requested"], "Review effort misassigned")
    votes, identities = [], []
    for name, persona in base._PERSONAS:
        vote = read(folder / f"{name}.json")
        prompt = base.prompt_for(data, persona)
        require((folder / f"{name}.prompt.txt").read_text() == prompt, f"Changed prompt: {folder}/{name}")
        require(vote["binding"] == binding and vote["prompt_sha256"] == base.digest(prompt.encode()),
                "Unbound reviewer evidence")
        stream_path = folder / vote.get("raw_stream_relative", f"{name}.stream.jsonl")
        require(stream_path.resolve().is_relative_to(folder.resolve()), "Raw response path escapes review folder")
        stream = stream_path.read_text()
        if vote.get("format_recovery"):
            require(reviewer == "claude", "Unexpected recovery provider")
            require(base.digest(stream_path.read_bytes()) == vote["raw_stream_sha256"], "Changed recovered raw evidence")
            require(stream_path.with_name(f"{name}.prompt.txt").read_text() == prompt, "Recovery prompt changed")
            parsed = parse_claude_preserving_rating(stream)
        else:
            parsed = base.parse_stream(stream) if reviewer == "astra" else claude.parse(stream)
        for key in ("score", "rationale", "usage", "session_id"):
            require(parsed[key] == vote[key], f"Raw/saved mismatch: {key}")
        # The original Claude panel froze the alias before its operational
        # guard pinned Opus 5. The raw model receipt below is authoritative.
        requested_models = {settings["model"]}
        if reviewer == "claude" and settings["model"] == "opus":
            requested_models.add("claude-opus-5")
        require(vote["status"] == "complete" and vote["judge_effort_requested"] == "medium"
                and vote["judge_model_requested"] in requested_models and vote["persona"] == name,
                "Invalid vote identity or status")
        require(vote["session_id"] not in sessions, "Reused reviewer session")
        sessions.add(vote["session_id"])
        argv = vote["argv"]
        require(argv[argv.index("--model") + 1] == vote["judge_model_requested"], "Model argv mismatch")
        if reviewer == "astra":
            require(all(flag in argv for flag in ("--ephemeral", "--ignore-user-config", "read-only")),
                    "Missing isolated Astra controls")
            require(all(config in argv for config in base.CONFIG), "Missing disabled-tool config")
        else:
            require(parsed["model_reported"] == "claude-opus-5", "Claude model drift")
            events = [json.loads(line) for line in stream.splitlines() if line.strip()]
            init = next(e for e in events if e.get("type") == "system" and e.get("subtype") == "init")
            require(init.get("apiKeySource") == "none" and not init.get("mcp_servers"),
                    "Claude billing or tool configuration changed")
            identities.append({"persona": name, **claude_model_evidence(events, allow_fallbacks)})
            rates = [e["rate_limit_info"] for e in events if e.get("type") == "rate_limit_event"]
            require(rates and all(r.get("isUsingOverage") is False for r in rates), "Unknown/overage billing")
        votes.append(vote)
    require(record["votes"] == votes, "Record does not contain verified votes")
    require(record["human_like"] == round(sum(v["score"] for v in votes) / 300, 4), "Wrong review mean")
    return {**record, "reviewer_model_evidence": identities}


def aggregate(rows, task_ids, complete):
    groups = []
    for model in SOLVERS:
        for effort in base.LEVELS:
            rs = [r for r in rows if r["model"] == model and r["effort"] == effort]
            require(len(rs) == len({r["task"] for r in rs}), "Duplicate task in model/effort")
            if complete:
                require({r["task"] for r in rs} == set(task_ids), "Incomplete matched task coverage")
            if len(rs) < 2:
                continue
            group = {"model": model, "effort": effort, "n": len(rs),
                     "passed": sum(r["functional"] == 1 for r in rs),
                     "fallback_runs": sum(r["fallback"] for r in rs),
                     "solver_seconds": sum(r["duration_s"] for r in rs),
                     "reported_tokens": sum(r["reported_tokens"] for r in rs)}
            group["raw_tokens"] = sum(r["solver_receipt"]["raw_tokens"] for r in rs)
            for metric in ("combined", "panel", "functional", "quality", "security", "astra", "claude"):
                group[metric] = mean_se([100 * r[metric] for r in rs])
            group["minutes"] = mean_se([r["duration_s"] / 60 for r in rs])
            groups.append(group)
    return groups


def main():  # noqa: PLR0912, PLR0915
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-incomplete", action="store_true", help="Audit available pairs without finalizing")
    parser.add_argument("--include-reviewer-fallbacks", action="store_true",
                        help="Include disclosed Opus 4.8 reviewer fallbacks only after user approval")
    args = parser.parse_args()
    task_ids = read(TASKS / "suite.json")["tasks"]
    require(len(task_ids) == len(set(task_ids)) == 23, "Wrong suite")
    fable_sources, identities = source_manifest()
    fallback_ids = {r["run_id"] for r in identities if r["fallback"]}
    rows, audits, sessions = [], {}, set()
    for model, outputs in PANELS.items():
        settings = [read(p / "protocol.json") for p in outputs]
        sources = [read(p / "sources.json") for p in outputs]
        require(sources[0] == sources[1] and len(sources[0]) == 115, "Mismatched reviewer populations")
        if model == "fable":
            require(sources[0] == fable_sources, "Fable solver evidence changed")
            policy = read(outputs[1] / "continuation-policy.json")
            for filename, expected in policy["source_sha256"].items():
                require(filename in {"fable_panel_resume.py", "review_format.py"}, "Unexpected continuation source")
                require(base.digest((ROOT / "harness" / filename).read_bytes()) == expected,
                        "Continuation code changed after freezing")
        for reviewer, setting in zip(("astra", "claude"), settings, strict=True):
            protocol_check(setting, reviewer)
        all_votes = [[], []]
        for run_path, hashes in sources[0].items():
            run = Path(run_path)
            data = base.inputs(run, TASKS)
            summary = data["summary"]
            require(data["source_hashes"] == hashes, "Original source hash changed")
            require(summary["model"] == SOLVERS[model] and summary["effort"]["requested"] == run.parent.name
                    and summary["effort"]["supported"], "Wrong solver model or effort")
            folders = [out / run.parent.name / run.name for out in outputs]
            if not all((folder / "judging.json").exists() for folder in folders):
                require(args.allow_incomplete, f"Judging not finished: {run}")
                continue
            records = [audit_record(folder, data, setting, reviewer, sessions, args.include_reviewer_fallbacks)
                       for folder, setting, reviewer in zip(folders, settings, ("astra", "claude"), strict=True)]
            panel = average_panel(*(r["human_like"] for r in records))
            scores = summary["scores"]
            score = reviewed_score({**scores, "human_like": panel})
            row = {"model": model, "effort": run.parent.name, "task": summary["task_id"], "run_id": run.name,
                   "astra": records[0]["human_like"], "claude": records[1]["human_like"], "panel": panel,
                   "combined": score, "functional": scores["functional"], "quality": scores["quality"],
                   "security": scores["security"], "fallback": run.name in fallback_ids,
                   "claude_reviewer_models": records[1]["reviewer_model_evidence"],
                   "duration_s": summary["duration_s"], "reported_tokens": summary["total_tokens"],
                   "solver_receipt": solver_receipt(run, summary),
                   "source_directory": str(run), "source_hashes": hashes,
                   "started_at": summary["started_at"], "finished_at": summary["finished_at"],
                   "solver_cli_version": summary["cli_agent"]["harness_version"]}
            rows.append(row)
            for i, record in enumerate(records):
                all_votes[i].extend(record["votes"])
        for i, reviewer in enumerate(("astra", "claude")):
            votes = all_votes[i]
            audits[f"{model}/{reviewer}"] = {
                "source": str(outputs[i]), "protocol_sha256": base.digest((outputs[i] / "protocol.json").read_bytes()),
                "valid_votes_in_paired_runs": len(votes), "cli_version": settings[i]["cli_version"],
                "model": settings[i]["model"], "model_identity": "requested-only" if reviewer == "astra" else "CLI-reported",
                "active_seconds_valid_votes": sum(v["duration_s"] for v in votes),
                "first_started_at": read(outputs[i] / "execution.json")["started_at"],
                "last_completed_at": max((v["completed_at"] for v in votes), default=None),
                "usage_valid_votes": dict(sum((Counter({k: value for k, value in v["usage"].items()
                                                        if k.endswith("tokens") and isinstance(value, int)})
                                               for v in votes), Counter())),
            }
            continuation = outputs[i] / "continuation-policy.json"
            if continuation.exists():
                audits[f"{model}/{reviewer}"]["continuation_policy_sha256"] = base.digest(continuation.read_bytes())
    complete = len(rows) == 230
    require(complete or args.allow_incomplete, "Incomplete comparison")
    groups = aggregate(rows, task_ids, complete)
    if complete:
        require(len(sessions) == 1380 and sum(r["fallback"] for r in rows) == 11, "Wrong vote/fallback coverage")
        previous = read(ROOT / "runs-astra-cii-v4-claude-judging-v1/verification.json")
        lookup = {(r["effort"], r["task"]): r for r in previous["rows"]}
        for row in rows:
            if row["model"] == "astra":
                for metric in ("combined", "panel", "astra", "claude", "functional", "quality", "security"):
                    require(row[metric] == lookup[row["effort"], row["task"]][metric], "Changed published Astra metric")
    languages = []
    for task in task_ids:
        require(read(TASKS / task / "metadata.json")["languages"] == ["python"], "Language scope changed")
        require(list((TASKS / task / "builder").glob("*.c")), "Missing binary language evidence")
        languages.append({"task": task, "replacement": "Python", "binary_source": "C"})
    result = {"complete": complete, "checked_at": datetime.now(UTC).isoformat(), "suite": "VulcanBench-SWE v4",
              "profile": "swe-v4-reviewed-equal-panel", "weights": WEIGHTS, "runs": len(rows),
              "valid_votes": len(sessions), "fallback_runs": sum(r["fallback"] for r in rows),
              "reviewer_fallbacks_included": args.include_reviewer_fallbacks,
              "reviewer_fallback_votes": sum(v["fallback"] for r in rows for v in r["claude_reviewer_models"]),
              "source_hashes_unchanged": True, "raw_votes_and_prompts_verified": True,
              "labels": {"astra": "GPT-6 Astra", "fable": "Fable 5.1 with fallbacks"},
              "groups": groups, "rows": rows, "reviewer_audits": audits, "task_languages": languages,
              "fable_solver_identity": identities,
              "caveats": ["11 of 115 Fable runs switched to Opus 4.8 after refusal; all are included.",
                          "Model plus harness comparison, not isolated base-model performance.",
                          "Code quality is an equal Astra/Claude LLM panel, not human ground truth; bias remains possible.",
                          "Reviewer prompts and effort match; Claude CLI was 2.1.260 for Astra and 2.1.261 for Fable.",
                          "Astra reviewer identity is requested-only because its stream lacks a model receipt.",
                          "Runtime is summed solver duration or mean per task, excluding post-hoc judging and pauses between tasks.",
                          "Raw tokens are reconstructed from CLI result receipts, including cache reads and writes. Auxiliary model accounting may differ by CLI.",
                          "Fable historical summaries contain cache-price-weighted units and omit earlier usage in four multi-result runs; these summaries are preserved but not compared as raw tokens.",
                          "Whiskers show one sample SE across 23 tasks, not judge uncertainty or a significance test."]}
    path = OUTPUT / ("comparison.json" if complete else "comparison-progress.json")
    base.save(path, result)
    print(base.canonical({"complete": complete, "runs": len(rows), "valid_votes": len(sessions), "output": str(path)}))


if __name__ == "__main__":
    main()
