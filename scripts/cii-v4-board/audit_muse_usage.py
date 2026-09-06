"""Reconcile retained Muse receipts without changing solver or grading artifacts."""

import argparse
import hashlib
import json
from pathlib import Path

from harness.agent.muse_code import collect_usage
from harness.pricing import cost_usd


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Choose a new audit output; existing artifacts are preserved")
    results = []
    for path in sorted(args.run_root.glob("*/*/summary.json")):
        summary = json.loads(path.read_text())
        model = summary["model"].split(":", 1)[1]
        logs = sorted((path.parent / "muse-session-logs").rglob("session.jsonl"))
        usage = collect_usage(logs, model)
        if not usage["calls"]:
            raise ValueError(f"No auditable receipts: {path}")
        results.append(
            {
                "task_id": summary["task_id"],
                "run_id": summary["run_id"],
                "summary_path": str(path.resolve()),
                "summary_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "original_tokens": summary["total_tokens"],
                "audited_tokens": usage["input_tokens"] + usage["output_tokens"],
                "usage": usage,
                "api_equivalent_usd": cost_usd(
                    summary["model"],
                    usage["input_tokens"],
                    usage["output_tokens"],
                    cached_input_tokens=usage["cached_tokens"],
                ),
            }
        )
    audit = {
        "scope": "Completed runs only; incomplete calls without receipts cannot be reconstructed",
        "method": "Deduplicate model_completed by run_id and source_run_record_id, including retained frames",
        "originals_modified": False,
        "results": results,
        "completed_runs": len(results),
        "original_tokens": sum(r["original_tokens"] for r in results),
        "audited_tokens": sum(r["audited_tokens"] for r in results),
        "api_equivalent_usd": sum(r["api_equivalent_usd"] for r in results),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as output:
        output.write(json.dumps(audit, indent=2) + "\n")
    print(json.dumps({k: v for k, v in audit.items() if k != "results"}))


if __name__ == "__main__":
    main()
