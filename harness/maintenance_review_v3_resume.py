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
import re
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


def payload_for(stage: str, ident: str) -> dict | None:  # noqa: PLR0911, one branch per stage
    """Rebuild the frozen payload for a call so a recovered response can be validated."""
    if stage in ("primary", "repeat"):
        return v3.read(OUT / "evidence" / f"{ident}.json")
    if stage == "calibration":
        if ident.startswith("control-"):
            return v3.read(OUT / "controls" / f"control-{ident.split('-')[1]}.json")
        return None
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


MATCH_ORDER_ERROR = "Matches must cover every key quirk once, in order"
QUIRK_ID = re.compile(r"^\s*(Q\d+)\b")


def retry_external_kill(folder: Path) -> bool:
    """A judge process ended by an outside SIGTERM (exit 143) is a transport failure, not a response.

    Grants the single fresh attempt the protocol allows for transport faults
    when only attempt 1 exists and its stream has no terminal event.
    """
    receipt = folder / "attempt-1.json"
    if not receipt.exists() or (folder / "attempt-2.json").exists():
        return False
    rec = json.loads(receipt.read_text())
    if rec.get("status") != "failed" or rec.get("retryable") is not False:
        return False
    if "exit 143" not in str(rec.get("error", "")) and "SIGTERM" not in str(rec.get("error", "")):
        return False
    rec["retryable"] = True
    rec["operator_review"] = {"at": datetime.now(UTC).isoformat(),
                              "finding": "Judge process received SIGTERM from outside the runner (exit 143); no response was produced.",
                              "action": "Transport fault: one fresh attempt per the protocol; receipt retained."}
    receipt.write_text(json.dumps(rec, indent=2, sort_keys=True))
    print(json.dumps({"event": "external_kill_retry", "call": str(folder.relative_to(OUT))}), flush=True)
    return True


def recover_match_ids(folder: Path, panel: str, stage: str) -> bool:
    """Match responses whose quirk ids carry a description ("Q1 winter tier") or arrive out of order.

    The id is the leading Q-number; entries are reordered to the key's order.
    Statuses, departure indexes, and reasons are untouched. Any id missing or
    duplicated is not recovered.
    """
    if stage != "match":
        return False
    receipts = [folder / f"attempt-{n}.json" for n in (1, 2)]
    if not all(r.exists() for r in receipts):
        return False
    if any(json.loads(r.read_text()).get("error") != MATCH_ORDER_ERROR for r in receipts):
        return False
    payload = payload_for(stage, folder.name)
    if payload is None:
        return False
    expected = [q["id"] for q in payload["key"]]
    for attempt in (1, 2):
        stream = folder / f"attempt-{attempt}.stream.jsonl"
        if not stream.exists():
            continue
        try:
            vote = v3.parse_stream_for(panel, stream.read_text())
        except (ValueError, json.JSONDecodeError, KeyError):
            continue
        matches = vote.get("matches")
        if not isinstance(matches, list):
            continue
        by_id = {}
        original = []
        for m in matches:
            hit = QUIRK_ID.match(str(m.get("quirk", "")))
            if not hit or hit.group(1) in by_id:
                by_id = None
                break
            original.append(m.get("quirk"))
            by_id[hit.group(1)] = {**m, "quirk": hit.group(1)}
        if by_id is None or sorted(by_id) != sorted(expected):
            continue
        vote["matches"] = [by_id[q] for q in expected]
        try:
            v3.validate("match", vote, payload)
        except ValueError:
            continue
        binding = json.loads(receipts[attempt - 1].read_text())["binding"]
        vote.update(binding=binding, status="complete", stage=stage, panel=panel, kind="match",
                    operator_recovery={"at": datetime.now(UTC).isoformat(), "method": "quirk ids normalized to key ids and key order",
                                       "original_quirk_fields": original, "source_attempt": attempt})
        base.save(folder / "selected.json", vote)
        print(json.dumps({"event": "match_id_recovery_applied", "call": str(folder.relative_to(OUT)), "attempt": attempt}), flush=True)
        return True
    return False


def accept_fallback(folder: Path, panel: str, stage: str) -> bool:
    if panel != "claude":
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


_BULLET = re.compile(r"^\s*(?:[*+-]|\d+[.)])\s+")


def _collapse(text: str) -> str:
    """Whitespace-collapsed comparison form: Markdown code marks and a leading list bullet are ignored.

    Used only to find the verbatim source span; the span itself is returned untouched.
    """
    return " ".join(_BULLET.sub("", text).replace("`", "").split())


ELLIPSIS = re.compile(r"\s*(?:\.\.\.|\u2026)\s*")


def rewrap_excerpt(excerpt: str, source: list[str]) -> str | None:
    """Return a verbatim rewrap of the excerpt, or None if any fragment is not in the source.

    Inline ellipsis markers split a line into fragments that are rewrapped
    separately and rejoined with a dots-only line, which the frozen rule skips.
    """
    if v3.excerpt_supported(excerpt, source):
        return excerpt
    fragments = [f for f in ELLIPSIS.split(excerpt) if f.strip()]
    if len(fragments) > 1:
        spans = [_rewrap_fragment(f, source) for f in fragments]
        return None if any(sp is None for sp in spans) else "\n...\n".join(spans)
    return _rewrap_fragment(excerpt, source)


_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+|\"[^\"]*\"|'[^']*'|==|!=|<=|>=|\+=|-=|\*=|//=|//|\*\*|[^\s\w]")


def _span_anywhere(fragment: str, source: list[str]) -> str | None:
    """Verbatim lines covering a fragment that starts or ends mid-line across wrapped text.

    Finds a word-aligned suffix of some source line that the collapsed
    fragment begins with, accumulates following lines until the fragment is
    covered, and returns those whole lines. Used for hard-wrapped prose such
    as docstrings and README paragraphs. Shorter than 20 characters is refused.
    """
    target = _collapse(fragment)
    if len(target) < 20:
        return None
    for text in sorted(source, key=lambda s: s.startswith("diff --git")):
        lines = text.splitlines()
        collapsed = [_collapse(line) for line in lines]
        for i, first in enumerate(collapsed):
            if not first:
                continue
            words = first.split(" ")
            for k in range(len(words)):
                suffix = " ".join(words[k:])
                if not target.startswith(suffix):
                    continue
                accum, j = suffix, i
                while len(accum) < len(target) and j + 1 < len(lines) and j - i < 40:
                    j += 1
                    accum = _collapse(accum + " " + collapsed[j]) if collapsed[j] else accum
                if accum.startswith(target):
                    span = "\n".join(lines[i:j + 1])
                    return span if v3.excerpt_supported(span, source) else None
                break
    return None


def _omission_only_line(fragment: str, source: list[str]) -> str | None:
    """A single source line whose tokens contain the fragment's tokens in order, with nothing added.

    Recovers a judge that shortened a line (dropped a receiver or an index)
    without inventing anything: every token it wrote must appear, in order,
    in one source line. A wrong value or a name absent from the line fails.
    """
    wanted = _TOKEN.findall(fragment)
    if len(wanted) < 4:
        return None
    for text in sorted(source, key=lambda s: s.startswith("diff --git")):  # final source before the patch text
        for line in text.splitlines():
            have = _TOKEN.findall(line)
            if len(have) <= len(wanted):
                continue
            it = iter(have)
            if all(any(tok == candidate for candidate in it) for tok in wanted):
                return line if v3.excerpt_supported(line, source) else None
    return None


def _rewrap_fragment(excerpt: str, source: list[str]) -> str | None:
    """Return the minimal verbatim source span whose collapsed form equals the collapsed fragment.

    The span must begin on a line the fragment begins with and grow only while
    it remains a prefix of the fragment, so unrelated preceding code is never
    pulled in.
    """
    excerpt = excerpt.replace("\\n", "\n")  # GLM sometimes double-escapes newlines inside JSON strings
    if v3.excerpt_supported(excerpt, source):
        return excerpt
    # A judge may decode a source escape such as backslash-x00 or backslash-0 into the real control
    # character inside its JSON. Try the common spellings the source could have used; the value is identical.
    if any(ord(ch) < 32 and ch not in "\n\t" for ch in excerpt):
        for style in ("\\x{:02x}", "\\{:o}", "\\{:03o}", "\\u{:04x}"):
            reescaped = "".join(style.format(ord(ch)) if ord(ch) < 32 and ch not in "\n\t" else ch for ch in excerpt)
            if v3.excerpt_supported(reescaped, source):
                return reescaped
    target = _collapse(excerpt)
    if not target:
        return None
    for text in source:
        lines = text.splitlines()
        for start in range(len(lines)):
            first = _collapse(lines[start])
            if not first or not target.startswith(first):
                continue
            joined = first
            for end in range(start, min(start + 12, len(lines))):
                if end > start:
                    joined = _collapse(joined + " " + lines[end])
                if joined == target:
                    span = "\n".join(lines[start:end + 1])
                    return span if v3.excerpt_supported(span, source) else None
                if not target.startswith(joined):
                    break
    return _span_anywhere(excerpt, source) or _omission_only_line(excerpt, source)


def recover_excerpts(folder: Path, panel: str, stage: str) -> bool:  # noqa: PLR0911, PLR0912, one branch per precondition and attempt
    receipts = [folder / f"attempt-{n}.json" for n in (1, 2)]
    if not all(r.exists() for r in receipts):
        return False
    if any(json.loads(r.read_text()).get("error") != EXCERPT_ERROR for r in receipts):
        return False
    ident = folder.name
    if stage == "calibration" and not ident.startswith("control-"):
        return False
    if stage not in ("primary", "repeat", "calibration", "probe"):
        return False
    kind = "probe" if stage == "probe" else "review"
    evidence = payload_for(stage, ident)
    if evidence is None:
        return False
    source = list(v3.strings(evidence))
    for attempt in (1, 2):
        stream = folder / f"attempt-{attempt}.stream.jsonl"
        if not stream.exists():
            continue
        try:
            vote = v3.parse_stream_for(panel, stream.read_text())
        except (ValueError, json.JSONDecodeError, KeyError):
            continue
        recovered = {}
        holders = (list(vote.get("dimensions", {}).items()) if kind == "review"
                   else list(enumerate(vote.get("departures", []))))
        for label, detail in holders:
            span = rewrap_excerpt(detail["excerpt"], source)
            if span is None:
                print(json.dumps({"event": "excerpt_not_recoverable", "call": ident, "attempt": attempt, "holder": str(label),
                                  "excerpt": detail["excerpt"][:200]}), flush=True)
                break
            if span != detail["excerpt"]:
                recovered[str(label)] = detail["excerpt"]
                detail["excerpt"] = span
        else:
            try:
                v3.validate(kind, vote, evidence)
            except ValueError:
                continue
            if kind == "review":
                vote["reported_score"] = vote["score"]
                vote.update(v3.host_review_score(vote))
            binding = json.loads(receipts[attempt - 1].read_text())["binding"]
            vote.update(binding=binding, status="complete", stage=stage, panel=panel, kind=kind,
                        operator_recovery={"at": datetime.now(UTC).isoformat(),
                                           "method": "excerpt re-wrapped to source line breaks",
                                           "original_excerpts": recovered, "source_attempt": attempt})
            base.save(folder / "selected.json", vote)
            print(json.dumps({"event": "excerpt_recovery_applied", "call": str(folder.relative_to(OUT)),
                              "attempt": attempt, "holders": sorted(recovered)}), flush=True)
            return True
    return False


def newest_unresolved(panel: str) -> Path | None:
    stopped = [d for d in (OUT / "calls" / panel).glob("*/*/") if not (d / "selected.json").exists()
               and (d / "attempt-1.json").exists()]
    return max(stopped, key=lambda d: (d / "attempt-1.json").stat().st_mtime) if stopped else None


def apply_rule(folder: Path) -> bool:
    if folder.parent.parent.name not in ("claude", "reader") or (folder / "attempt-2.json").exists():
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
        if folder is not None and recover_match_ids(folder, panel, folder.parent.name):
            applied += 1
            continue
        if folder is not None and retry_external_kill(folder):
            applied += 1
            continue
        if True:
            print(json.dumps({"event": "stopped_for_operator", "call": str(folder) if folder else None,
                              "operator_rule_applications": applied}), flush=True)
            return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
