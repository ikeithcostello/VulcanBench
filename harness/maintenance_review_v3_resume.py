"""Operator convenience for the documented v3.2 rule; not part of the frozen judging code.

Rule (docs/judging/maintenance-v3-operations.md): when the Claude CLI exits
non-zero with result subtype error_max_structured_output_retries, the response
is an invalid-schema response and the protocol grants one fresh retry. This
script re-invokes a stage; if it stops on exactly that subtype with only
attempt-1 recorded, it marks the receipt retryable with a review note and
re-invokes. Any other failure, or a second failure on the same call, stops.

Second rule (same log): when both attempts of a review failed only on
"Unsupported evidence excerpt" and every rejected excerpt matches the source
once whitespace and line breaks are collapsed, the attempt-1 response is
selected with each such excerpt re-wrapped to the source's own line breaks.
Scores and text are untouched; the original excerpt is recorded. A quote that
does not match the source even after collapsing is not recovered.

Third rule (owner decision, September 7, 2026, evening): retain and disclose
reviewer fallbacks. When an attempt failed only the identity guard, the
session requested and reported claude-opus-5, every assistant message came
from claude-opus-4-8 (the CLI's silent refusal fallback), no tool was used,
and the response validates, it is selected with a reviewer_fallback record.
Any other model, or an invalid response, is not recovered.

Usage: python -m harness.maintenance_review_v3_resume calibrate --panel claude
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from harness import maintenance_review_v3 as v3
from harness import retrospective_judging as base
from harness.maintenance_review_v3 import OUT

SUBTYPE = "error_max_structured_output_retries"
EXCERPT_ERROR = "Unsupported evidence excerpt"
IDENTITY_ERROR = "Claude reviewer identity or fallback guard failed"
FALLBACK_MODEL = "claude-opus-4-8"
REQUESTED_MODEL = "claude-opus-5"


def stage_kind(stage: str) -> str:
    return {"primary": "review", "repeat": "review", "pairwise": "pair", "probe": "probe", "match": "match"}[stage]


def payload_for(stage: str, ident: str) -> dict | None:
    """Rebuild the frozen payload for a call so a recovered response can be validated."""
    if stage in ("primary", "repeat"):
        return v3.read(OUT / "evidence" / f"{ident}.json")
    if stage == "pairwise":
        a, b = ident.split("-submission-")
        b = "submission-" + b
        return {"A": v3.read(OUT / "evidence" / f"{a}.json"), "B": v3.read(OUT / "evidence" / f"{b}.json")}
    if stage == "probe":
        return v3.probe_evidence(v3.read(OUT / "evidence" / f"{ident}.json"))
    if stage == "match":
        probe = OUT / "calls" / "claude" / "probe" / ident / "selected.json"
        if not probe.exists():
            return None
        row = next(r for r in v3.read(OUT / "private-manifest.json") if r["id"] == ident)
        return {"key": v3.load_key(row["task"])["quirks"], "departures": v3.read(probe)["departures"]}
    return None


def assistant_models(stream_text: str) -> set[str]:
    return {json.loads(line)["message"]["model"] for line in stream_text.splitlines()
            if line.strip() and "\"type\":\"assistant\"" in line}


def accept_fallback(folder: Path, panel: str, stage: str) -> bool:
    if panel == "astra":
        return False
    kind = stage_kind(stage)
    payload = payload_for(stage, folder.name)
    if payload is None:
        return False
    for n in (2, 1):
        receipt = folder / f"attempt-{n}.json"
        stream = folder / f"attempt-{n}.stream.jsonl"
        if not receipt.exists() or not stream.exists():
            continue
        rec = json.loads(receipt.read_text())
        if rec.get("status") != "failed" or rec.get("error") != IDENTITY_ERROR:
            continue
        text = stream.read_text()
        if assistant_models(text) != {FALLBACK_MODEL}:
            continue
        try:
            vote = v3.parse_claude_stream(text)
            if vote["model_reported"] != REQUESTED_MODEL:
                continue
            v3.validate(kind, vote, payload)
        except (ValueError, json.JSONDecodeError, KeyError):
            continue
        if kind == "review":
            vote["reported_score"] = vote["score"]
            vote.update(v3.host_review_score(vote))
        vote.update(binding=rec["binding"], status="complete", stage=stage, panel=panel, kind=kind,
                    reviewer_fallback={"at": datetime.now(UTC).isoformat(), "requested": REQUESTED_MODEL,
                                       "served": FALLBACK_MODEL, "source_attempt": n,
                                       "policy": "retain and disclose reviewer fallbacks (owner decision 2026-09-07)"})
        base.save(folder / "selected.json", vote)
        print(json.dumps({"event": "reviewer_fallback_accepted", "call": str(folder.relative_to(OUT)), "attempt": n}), flush=True)
        return True
    return False


def _collapse(text: str) -> str:
    return " ".join(text.split())


def rewrap_excerpt(excerpt: str, source: list[str]) -> str | None:
    """Return the verbatim source span whose collapsed form contains the collapsed excerpt."""
    if v3.excerpt_supported(excerpt, source):
        return excerpt
    target = _collapse(excerpt)
    if not target:
        return None
    for text in source:
        lines = text.splitlines()
        for start in range(len(lines)):
            joined = ""
            for end in range(start, min(start + 12, len(lines))):
                joined = _collapse(joined + " " + lines[end])
                if target in joined:
                    span = "\n".join(lines[start:end + 1])
                    return span if v3.excerpt_supported(span, source) else None
                if len(joined) > len(target) + 400:
                    break
    return None


def recover_excerpts(folder: Path, panel: str, stage: str) -> bool:  # noqa: PLR0911, one early exit per precondition
    receipts = [folder / f"attempt-{n}.json" for n in (1, 2)]
    if not all(r.exists() for r in receipts):
        return False
    if any(json.loads(r.read_text()).get("error") != EXCERPT_ERROR for r in receipts):
        return False
    stream = folder / "attempt-1.stream.jsonl"
    if not stream.exists():
        return False
    ident = folder.name
    evidence = v3.read(OUT / "evidence" / f"{ident}.json") if stage in ("primary", "repeat") else None
    if evidence is None:
        return False
    source = list(v3.strings(evidence))
    vote = v3.parse_claude_stream(stream.read_text()) if panel != "astra" else None
    if vote is None:
        return False
    recovered = {}
    for dim, detail in vote["dimensions"].items():
        span = rewrap_excerpt(detail["excerpt"], source)
        if span is None:
            print(json.dumps({"event": "excerpt_not_recoverable", "call": ident, "dimension": dim}), flush=True)
            return False
        if span != detail["excerpt"]:
            recovered[dim] = detail["excerpt"]
            detail["excerpt"] = span
    v3.validate("review", vote, evidence)
    vote["reported_score"] = vote["score"]
    vote.update(v3.host_review_score(vote))
    binding = json.loads(receipts[0].read_text())["binding"]
    vote.update(binding=binding, status="complete", stage=stage, panel=panel, kind="review",
                operator_recovery={"at": datetime.now(UTC).isoformat(), "method": "excerpt re-wrapped to source line breaks",
                                   "original_excerpts": recovered, "source_attempt": 1})
    base.save(folder / "selected.json", vote)
    print(json.dumps({"event": "excerpt_recovery_applied", "call": str(folder.relative_to(OUT)), "dimensions": sorted(recovered)}), flush=True)
    return True


def newest_unresolved(panel: str) -> Path | None:
    stopped = [d for d in (OUT / "calls" / panel).glob("*/*/") if not (d / "selected.json").exists()
               and (d / "attempt-1.json").exists()]
    return max(stopped, key=lambda d: (d / "attempt-1.json").stat().st_mtime) if stopped else None


def apply_rule(folder: Path) -> bool:
    if (folder / "attempt-2.json").exists():
        return False
    receipt = json.loads((folder / "attempt-1.json").read_text())
    if receipt.get("status") != "failed" or receipt.get("retryable") is not False:
        return False
    stream = folder / "attempt-1.stream.jsonl"
    if not stream.exists():
        return False
    results = [json.loads(line) for line in stream.read_text().splitlines() if line.strip() and "\"type\":\"result\"" in line]
    if not results or results[0].get("subtype") != SUBTYPE:
        return False
    receipt["retryable"] = True
    receipt["operator_review"] = {
        "at": datetime.now(UTC).isoformat(),
        "finding": f"CLI result subtype {SUBTYPE}; invalid-schema response under the protocol text.",
        "action": "Marked retryable by the documented operator rule (maintenance_review_v3_resume); "
                  "single fresh attempt; receipt retained.",
    }
    (folder / "attempt-1.json").write_text(json.dumps(receipt, indent=2, sort_keys=True))
    print(json.dumps({"event": "operator_rule_applied", "call": str(folder.relative_to(OUT))}), flush=True)
    return True


def main() -> int:
    args = sys.argv[1:]
    panel = args[args.index("--panel") + 1]
    applied = 0
    while True:
        proc = subprocess.run([sys.executable, "-u", "-m", "harness.maintenance_review_v3", *args], check=False)
        if proc.returncode == 0:
            print(json.dumps({"event": "stage_complete", "operator_rule_applications": applied}), flush=True)
            return 0
        folder = newest_unresolved(panel)
        if folder is not None and apply_rule(folder):
            applied += 1
            continue
        if folder is not None and recover_excerpts(folder, panel, folder.parent.name):
            applied += 1
            continue
        if folder is not None and accept_fallback(folder, panel, folder.parent.name):
            applied += 1
            continue
        if True:
            print(json.dumps({"event": "stopped_for_operator", "call": str(folder) if folder else None,
                              "operator_rule_applications": applied}), flush=True)
            return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
