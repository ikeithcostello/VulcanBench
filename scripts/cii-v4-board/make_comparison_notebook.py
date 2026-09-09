"""Create and execute a small, stdlib-only companion audit notebook.

The local environment has no Jupyter packages. Execute every code cell in
order with Python, retain stdout, and write notebook-format 4.5 structure.
No model calls or writes to original benchmark/reviewer artifacts occur.
"""

import contextlib
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/results/swe-v4-astra-fable51-2026-09"


def main():
    data = json.loads((OUT / "comparison.json").read_text())
    assert data["complete"] and data["runs"] == 230
    cells = []

    def cell(kind, source):
        value = {
            "cell_type": kind,
            "id": f"audit-{len(cells):02d}",
            "metadata": {},
            "source": source,
        }
        if kind == "code":
            value.update({"execution_count": None, "outputs": []})
        cells.append(value)

    cell(
        "markdown",
        "# VulcanBench-SWE v4 comparison audit\n\n## tl;dr\n\n"
        "This notebook independently recomputes the ten model/effort aggregates and checks raw token receipts. "
        "The card includes Fable solver fallbacks and Claude reviewer fallbacks. No solver results are changed.\n\n"
        "## Context & Methods\n\n230 runs: two solver/harness combinations, five efforts, 23 matched tasks each. "
        "Code quality is the equal mean of three Astra and three Claude ratings. "
        "Combined = 50% functional + 15% automated quality + 15% security + 20% Code quality.\n\n"
        "### Key Assumptions\n\nCLI usage receipts are the token-accounting authority. Claude's per-turn usage "
        "is summed; its session cost is cumulative. Cached input is counted once as input, not as a second "
        "category on top of total input. Native CLI auxiliary accounting can differ. "
        "LLM reviewers may be biased; SE describes variation across tasks, not judge uncertainty.\n\n"
        "This companion runs offline with the Python standard library. The generator executes all code cells "
        "top-to-bottom without a Jupyter kernel and retains their output.",
    )
    cell(
        "markdown",
        "## Data\n\n### 1. Load audited evidence\n\n"
        "Source: `comparison.json` next to this notebook. Raw paths and SHA-256 bindings are retained per run. "
        "Run from this output folder or from the repository root.",
    )
    cell(
        "code",
        """import json, math, statistics, hashlib
from pathlib import Path
folder = Path.cwd()
if not (folder / "comparison.json").exists():
    folder = folder / "docs/results/swe-v4-astra-fable51-2026-09"
data = json.loads((folder / "comparison.json").read_text())
assert data["complete"] and data["runs"] == 230 and data["valid_votes"] == 1380
assert data["weights"] == {"functional": .5, "quality": .15, "security": .15, "human_like": .2}
rows = data["rows"]
assert len({(r["model"], r["effort"], r["task"]) for r in rows}) == 230
assert len({r["task"] for r in rows}) == 23
print(f"Verified population: {len(rows)} runs, {data['valid_votes']} ratings")
print(f"Fable solver fallback runs: {sum(r['fallback'] for r in rows)}")
print(f"Claude reviewer fallback ratings: {data['reviewer_fallback_votes']}")""",
    )
    cell(
        "markdown",
        "## Results\n\n### 2. Recompute scores and error bars\n\n"
        "All rows use the same task set and fixed weights. Full passes require functional = 1.0; "
        "partial functional scores remain partial.",
    )
    cell(
        "code",
        """print("Model   Effort       Combined  Quality  Mean min  Passed")
for group in data["groups"]:
    subset = [r for r in rows if r["model"] == group["model"] and r["effort"] == group["effort"]]
    assert len(subset) == 23
    values = []
    for row in subset:
        quality = (row["astra"] + row["claude"]) / 2
        score = .5*row["functional"] + .15*row["quality"] + .15*row["security"] + .2*quality
        assert math.isclose(score, row["combined"], abs_tol=1e-12)
        values.append(100*score)
    assert math.isclose(statistics.mean(values), group["combined"]["mean"], abs_tol=1e-12)
    assert math.isclose(statistics.stdev(values)/math.sqrt(23), group["combined"]["se"], abs_tol=1e-12)
    print(f"{group['model']:7} {group['effort']:12} {statistics.mean(values):8.2f}  "
          f"{group['panel']['mean']:7.2f}  {group['minutes']['mean']:8.2f}  {group['passed']:2}/23")""",
    )
    cell(
        "markdown",
        "### 3. Check original token receipts\n\n"
        "Fable's old summary field represents cache-price-weighted units from its last result. "
        "It is not comparable to Astra's raw token total. The card uses summed raw CLI usage instead. "
        "All original streams must still match the recorded hash.",
    )
    cell(
        "code",
        """totals = {"astra": 0, "fable": 0}
multi_result = 0
for row in rows:
    path = Path(row["source_directory"]) / "cli-agent-stream.jsonl"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == row["solver_receipt"]["stream_sha256"]
    events = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if row["model"] == "astra":
        usage = [e["usage"] for e in events if e.get("type") == "turn.completed"]
        assert len(usage) == 1
        total = usage[0]["input_tokens"] + usage[0]["output_tokens"]
    else:
        receipts = [e for e in events if e.get("type") == "result"]
        multi_result += len(receipts) > 1
        total = sum(e["usage"][key] for e in receipts for key in
                    ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens", "output_tokens"))
    assert total == row["solver_receipt"]["raw_tokens"]
    totals[row["model"]] += total
for model, total in totals.items():
    seconds = sum(r["duration_s"] for r in rows if r["model"] == model)
    print(f"{model}: {total:,} raw tokens; {seconds/3600:.4f} summed solver hours")
print(f"Fable runs with multiple usage receipts: {multi_result}")""",
    )
    cell(
        "markdown",
        "## Takeaways\n\n"
        "Use the paired component scores and runtime, not full-pass counts alone. "
        "Fable solver and Claude reviewer fallbacks remain included and separately disclosed. "
        "Historical summaries are preserved, but their unlike token units are not compared on the card. "
        "See `reviewer-accounting.json` for post-hoc judging time, usage, retries, and raw call provenance.",
    )
    namespace = {}
    for index, value in enumerate((c for c in cells if c["cell_type"] == "code"), 1):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exec(compile(value["source"], f"comparison-audit-cell-{index}", "exec"), namespace)
        value["execution_count"] = index
        value["outputs"] = [{"output_type": "stream", "name": "stdout", "text": output.getvalue()}]
    notebook = {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.14"},
            "execution_engine": "All code cells executed in order with Python exec, without a Jupyter kernel",
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    path = OUT / "comparison-audit.ipynb"
    path.write_text(json.dumps(notebook, indent=2) + "\n")
    saved = json.loads(path.read_text())
    assert saved["nbformat"] == 4 and len({c["id"] for c in saved["cells"]}) == len(cells)
    assert all(
        c["execution_count"] and c["outputs"] for c in saved["cells"] if c["cell_type"] == "code"
    )
    print(path)


if __name__ == "__main__":
    main()
