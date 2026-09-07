"""Operator convenience for the documented v3.2 rule; not part of the frozen judging code.

Rule (docs/judging/maintenance-v3-operations.md): when the Claude CLI exits
non-zero with result subtype error_max_structured_output_retries, the response
is an invalid-schema response and the protocol grants one fresh retry. This
script re-invokes a stage; if it stops on exactly that subtype with only
attempt-1 recorded, it marks the receipt retryable with a review note and
re-invokes. Any other failure, or a second failure on the same call, stops.

Usage: python -m harness.maintenance_review_v3_resume calibrate --panel claude
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from harness.maintenance_review_v3 import OUT

SUBTYPE = "error_max_structured_output_retries"


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
        if folder is None or not apply_rule(folder):
            print(json.dumps({"event": "stopped_for_operator", "call": str(folder) if folder else None,
                              "operator_rule_applications": applied}), flush=True)
            return proc.returncode
        applied += 1


if __name__ == "__main__":
    sys.exit(main())
