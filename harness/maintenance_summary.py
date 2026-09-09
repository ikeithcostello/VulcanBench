"""Read-only aggregation of the separate maintenance-review protocol."""

import json
import math
import statistics
from collections import defaultdict
from datetime import UTC, datetime

from harness import maintenance_review_v2 as review


def average(values):
    return statistics.mean(values) if values else None


def stats(values):
    return {
        "n": len(values),
        "mean": average(values),
        "se": statistics.stdev(values) / math.sqrt(len(values)) if len(values) > 1 else None,
    }


def composite(row, quality, weight):
    other = (0.5 - weight) / 2
    return 100 * (
        0.5 * row["functional"]
        + other * row["quality"]
        + other * row["security"]
        + weight * quality / 100
    )


def summarize():  # noqa: PLR0912, PLR0915
    protocol = review.verify_frozen()
    manifest = review.read(review.OUT / "private-manifest.json")
    selection = review.read(review.OUT / "diagnostic-selection.json")
    panels = ("astra", "claude")
    selected = {}
    for panel in panels:
        for path in (review.OUT / "calls" / panel / "primary").glob("*/selected.json"):
            ident = path.parent.name
            evidence = review.read(review.OUT / "evidence" / f"{ident}.json")
            vote = review.call(panel, "primary", ident, evidence, protocol)
            selected[panel, ident] = vote
    rows = []
    for row in manifest:
        ident = row["id"]
        if not all((panel, ident) in selected for panel in panels):
            continue
        votes = [selected[panel, ident] for panel in panels]
        quality = statistics.mean(v["score"] for v in votes)
        rows.append(
            {
                "id": ident,
                "model": row["model"],
                "effort": row["effort"],
                "task": row["task"],
                "run_id": row["run_id"],
                "fallback": row["fallback"],
                "code_quality": quality,
                "total_33": composite(row, quality, 0.33),
                "total_20": composite(row, quality, 0.20),
                "dimensions": {
                    d: statistics.mean(v["dimensions"][d]["score"] for v in votes)
                    for d in review.DIMENSIONS
                },
                "panels": {p: selected[p, ident]["score"] for p in panels},
            }
        )
    groups = defaultdict(list)
    for row in rows:
        groups[row["model"], row["effort"]].append(row)
    group_stats = [
        {
            "model": model,
            "effort": effort,
            **{
                key: stats([r[key] for r in rs]) for key in ("code_quality", "total_33", "total_20")
            },
        }
        for (model, effort), rs in sorted(groups.items())
    ]
    diagnostics = {}
    for panel in panels:
        differences, consistency, agreement = [], [], []
        for ident in selection["repeats"]:
            path = review.OUT / "calls" / panel / "repeat" / ident / "selected.json"
            if not path.exists() or (panel, ident) not in selected:
                continue
            original = selected[panel, ident]
            repeat = review.call(
                panel,
                "repeat",
                ident,
                review.read(review.OUT / "evidence" / f"{ident}.json"),
                protocol,
            )
            differences.extend(
                abs(original["dimensions"][d]["score"] - repeat["dimensions"][d]["score"])
                for d in review.DIMENSIONS
            )
        for a, b in selection["pairs"]:
            pair_votes = []
            for first, second in [(a, b), (b, a)]:
                path = (
                    review.OUT
                    / "calls"
                    / panel
                    / "pairwise"
                    / f"{first}-{second}"
                    / "selected.json"
                )
                if not path.exists():
                    break
                evidence = {
                    "A": review.read(review.OUT / "evidence" / f"{first}.json"),
                    "B": review.read(review.OUT / "evidence" / f"{second}.json"),
                }
                pair_votes.append(
                    review.call(panel, "pairwise", f"{first}-{second}", evidence, protocol, True)
                )
            if len(pair_votes) != 2 or not all((panel, ident) in selected for ident in (a, b)):
                continue
            consistency.append(pair_votes[0]["score"] == 100 - pair_votes[1]["score"])
            gap = (selected[panel, a]["score"] - selected[panel, b]["score"]) / 25
            ordering = 50 if abs(gap) < 0.5 else (100 if gap > 0 else 0)
            agreement.append(pair_votes[0]["score"] == ordering)
        complete = len(differences) == 40 and len(consistency) == len(agreement) == 5
        diagnostics[panel] = {
            "complete": complete,
            "repeat_dimension_mae": average(differences),
            "order_consistency": average(consistency),
            "pairwise_absolute_agreement": average(agreement),
            "passed": complete
            and average(differences) <= 0.5
            and average(consistency) >= 0.8
            and average(agreement) >= 0.6,
        }
    usage = {p: defaultdict(int) for p in panels}
    unknown_usage, call_counts = [], defaultdict(int)
    for path in (review.OUT / "calls").glob("*/*/*/attempt-*.stream.jsonl"):
        panel = path.relative_to(review.OUT / "calls").parts[0]
        call_counts[panel] += 1
        events = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        receipts = [
            e.get("usage")
            for e in events
            if e.get("type") == ("turn.completed" if panel == "astra" else "result")
        ]
        if len(receipts) != 1 or not receipts[0]:
            unknown_usage.append(str(path.relative_to(review.OUT)))
            continue
        for key, value in receipts[0].items():
            if isinstance(value, int) and not isinstance(value, bool):
                usage[panel][key] += value
    calibration_passed = all(
        (review.OUT / f"calibration-{p}.json").exists()
        and review.read(review.OUT / f"calibration-{p}.json")["passed"]
        for p in panels
    )
    result = {
        "protocol": protocol["id"],
        "human_calibrated": False,
        "expected_submissions": 230,
        "paired_submissions_complete": len(rows),
        "primary_calls_complete": {p: sum(panel == p for panel, _ in selected) for p in panels},
        "calibration_passed": calibration_passed,
        "diagnostics": diagnostics,
        "ready_for_publication": len(rows) == 230
        and calibration_passed
        and all(d["passed"] for d in diagnostics.values()),
        "groups": group_stats,
        "rows": rows,
        "usage_all_attempts": usage,
        "call_counts_all_attempts": call_counts,
        "usage_missing_calls": unknown_usage,
        "updated_at": datetime.now(UTC).isoformat(),
        "caveats": [
            "Automated calibration only; no independent human agreement established.",
            "Existing solver results and old quality scores are unchanged.",
            "Code quality is not proof of future maintenance outcomes.",
            "33 percent is a policy weight, not an optimized estimate.",
            "No API-equivalent estimate is asserted by this summary.",
        ],
    }
    review.base.save(review.OUT / "summary.json", result)
    print(
        review.base.canonical(
            {k: v for k, v in result.items() if k not in ("rows", "groups", "caveats")}
        )
    )


if __name__ == "__main__":
    summarize()
