"""Static paired comparison from completely audited, matched-task evidence.

Chart contract: 23 tasks per model/effort, five matched efforts, 230 runs.
Combined score and Code quality are paired dot-and-interval plots with an
explicit focused scale and exact numeric labels. Runtime bars start at zero.
Whiskers show one sample SE over tasks, not judge uncertainty. Green circles
identify Astra and clay diamonds identify Fable with disclosed fallbacks.
No score-driven exclusions, weight changes, rankings from partial coverage,
or claims of statistical significance. PNG requires visual QA before sharing.
"""

from __future__ import annotations

import csv
import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from harness.evaluator.reviewed_score import WEIGHTS  # noqa: E402
from harness.panel_comparison import OUTPUT, aggregate, read, require  # noqa: E402
from harness.retrospective_judging import LEVELS, digest, save  # noqa: E402

PAPER, INK = "#f7f5f0", "#171917"
COLORS = {"astra": "#10A37F", "fable": "#D97757"}
MARKERS = {"astra": "o", "fable": "D"}


def focused_limits(groups, metric):
    lo = min(g[metric]["mean"] - g[metric]["se"] for g in groups)
    hi = max(g[metric]["mean"] + g[metric]["se"] for g in groups)
    return max(0, math.floor((lo - 0.5) / 2) * 2), min(100, math.ceil((hi + 0.5) / 2) * 2)


def main():  # noqa: PLR0915
    source = OUTPUT / "comparison.json"
    data = read(source)
    require(
        data["complete"] and data["runs"] == 230 and data["valid_votes"] == 1380,
        "Final card requires all 230 runs and 1,380 verified ratings",
    )
    require(
        data["weights"] == WEIGHTS
        and data["raw_votes_and_prompts_verified"]
        and data["source_hashes_unchanged"],
        "Wrong or unverified scoring profile",
    )
    require(data["fallback_runs"] == 11, "Solver fallback disclosure mismatch")
    require(
        data["reviewer_fallbacks_included"] or data["reviewer_fallback_votes"] == 0,
        "Reviewer fallbacks have no approved disclosure policy",
    )
    groups = data["groups"]
    task_ids = {r["task"] for r in data["rows"]}
    require(groups == aggregate(data["rows"], task_ids, complete=True), "Stale aggregate")
    require(all(g["n"] == 23 for g in groups), "Partial coverage")
    lookup = {(g["model"], g["effort"]): g for g in groups}
    for font in (ROOT / "scripts/rankings-chart").glob("*.ttf"):
        font_manager.fontManager.addfont(font)
    plt.rcParams.update({"font.family": "Geist", "text.color": INK})
    fig = plt.figure(figsize=(16, 10), dpi=150, facecolor=PAPER)

    def text(x, y, s, size=13, bold=False, ha="left", heading=False, color=INK, numeric=False):
        family = (
            ("Chakra Petch SemiBold" if bold else "Chakra Petch Medium") if heading else "Geist"
        )
        if numeric:
            family = "IBM Plex Mono"
        weight = (
            (500 if bold else 400)
            if numeric
            else (600 if bold else 500)
            if heading
            else (700 if bold else 400)
        )
        return fig.text(
            x,
            y,
            s,
            fontsize=size,
            weight=weight,
            fontfamily=family,
            color=color,
            ha=ha,
            va="center",
        )

    def rule(y):
        fig.add_artist(
            plt.Line2D([0.04, 0.96], [y, y], transform=fig.transFigure, color="#b9b8b0", lw=0.8)
        )

    logo = fig.add_axes([0.04, 0.921, 0.034, 0.0544])
    mark = logo.imshow(plt.imread(ROOT / "docs/assets/vulcanbench-logo.png"))
    clip = FancyBboxPatch(
        (0, 0), 1, 1, boxstyle="round,pad=0,rounding_size=.22", transform=logo.transAxes
    )
    mark.set_clip_path(clip)
    logo.axis("off")
    text(0.085, 0.947, "VulcanBench", 21, True, heading=True)
    text(0.96, 0.947, "SEPTEMBER 2026", 12, ha="right")
    rule(0.9)
    text(0.04, 0.854, "Astra vs Fable 5.1", 34, True, heading=True)
    text(0.04, 0.81, "VulcanBench-SWE v4 · 23 tasks × 5 efforts × 2 models · 230 runs", 16)  # noqa: RUF001
    for x, model, label in [
        (0.04, "astra", "GPT-6 Astra · Codex"),
        (0.40, "fable", "Fable 5.1 with fallbacks · Claude Code"),
    ]:
        fig.add_artist(
            plt.Line2D(
                [x + 0.006],
                [0.755],
                transform=fig.transFigure,
                marker=MARKERS[model],
                color=COLORS[model],
                markeredgecolor=INK,
                markeredgewidth=0.5,
                markersize=8,
                linestyle="none",
            )
        )
        text(x + 0.02, 0.755, label, 14, True)
    score_range = focused_limits(groups, "combined")
    quality_range = focused_limits(groups, "panel")
    max_minutes = math.ceil(max(g["minutes"]["mean"] + g["minutes"]["se"] for g in groups) / 5) * 5
    for x, title, subtitle in [
        (0.16, "Combined score", f"/100 · focus: {score_range[0]} to {score_range[1]}"),
        (0.43, "Code quality", f"/100 · focus: {quality_range[0]} to {quality_range[1]}"),
        (0.695, "Mean runtime", "Minutes/task · lower is better"),
        (0.945, "Passed", "n=23 each"),
    ]:
        text(x, 0.683, title, 18, True, heading=True, ha="center" if title == "Passed" else "left")
        text(x, 0.651, subtitle, 10.5, ha="center" if title == "Passed" else "left")
    bottom, top = 0.219, 0.609
    specs = [
        ("combined", 0.16, 0.17, 0.395, score_range),
        ("panel", 0.43, 0.15, 0.645, quality_range),
        ("minutes", 0.695, 0.15, 0.905, (0, max_minutes)),
    ]
    axes = {}
    for metric, left, width, _value_x, limits in specs:
        ax = fig.add_axes([left, bottom, width, top - bottom], facecolor=PAPER)
        ax.set_xlim(*limits)
        ax.set_ylim(bottom, top)
        ax.set_yticks([])
        ax.set_xticks([limits[0], sum(limits) / 2, limits[1]])
        ax.tick_params(axis="x", length=0, labelsize=10, pad=8)
        ax.spines[["top", "left", "right"]].set_visible(False)
        ax.spines["bottom"].set_color("#b9b8b0")
        ax.grid(axis="x", color="#deddd6", lw=0.7)
        ax.set_axisbelow(True)
        axes[metric] = ax
    centers = [0.567, 0.491, 0.415, 0.339, 0.263]
    for effort, center in zip(LEVELS, centers, strict=True):
        text(0.04, center, effort.capitalize(), 14, True)
        for model, offset in (("astra", 0.015), ("fable", -0.015)):
            g = lookup[model, effort]
            y = center + offset
            for metric, _left, _width, value_x, limits in specs:
                mean, se = g[metric]["mean"], g[metric]["se"]
                require(limits[0] <= mean - se <= mean + se <= limits[1], "Clipped error bar")
                ax = axes[metric]
                if metric == "minutes":
                    ax.barh(
                        y,
                        mean,
                        height=0.018,
                        color=COLORS[model],
                        edgecolor=INK,
                        linewidth=0.4,
                        xerr=se,
                        error_kw={"ecolor": INK, "elinewidth": 1, "capsize": 3},
                    )
                else:
                    ax.errorbar(
                        mean,
                        y,
                        xerr=se,
                        fmt=MARKERS[model],
                        markersize=7,
                        color=COLORS[model],
                        markeredgecolor=INK,
                        markeredgewidth=0.5,
                        ecolor=INK,
                        elinewidth=1,
                        capsize=3,
                    )
                text(value_x, y, f"{mean:.2f}", 14, True, ha="right", numeric=True)
            text(0.96, y, f"{g['passed']}/23", 12, True, ha="right", numeric=True)
    rule(0.168)
    totals = {m: sum(g["solver_seconds"] for g in groups if g["model"] == m) for m in COLORS}
    tokens = {m: sum(g["raw_tokens"] for g in groups if g["model"] == m) for m in COLORS}
    text(0.04, 0.139, "Summed solver time", 12, True)
    text(
        0.235,
        0.139,
        f"Astra {totals['astra'] / 3600:.2f} h · Fable {totals['fable'] / 3600:.2f} h",
        12,
    )
    text(
        0.96,
        0.139,
        f"Raw tokens, incl. cache: {tokens['astra'] / 1e6:.2f}M / {tokens['fable'] / 1e6:.2f}M",
        12,
        ha="right",
    )
    text(
        0.04,
        0.107,
        "Weights: 50% functional + 15% automated quality + 15% security + 20% code quality",
        11.5,
        True,
    )
    text(
        0.04,
        0.079,
        "Code quality: equal Astra + Claude panels · 1,380 ratings · ±1 task SE, not judge uncertainty",
        11,
    )
    count = data["reviewer_fallback_votes"]
    text(
        0.04,
        0.052,
        f"Opus 4.8 fallbacks included: 11/115 Fable solver runs; {count}/690 Claude ratings across both models.",
        11,
    )
    text(
        0.04,
        0.025,
        "23 Python replacements; C-built binaries · LLM judgment may be biased · Runtime excludes post-hoc judging",
        10.5,
    )
    out = OUTPUT / "astra-vs-fable51.png"
    fig.savefig(out, facecolor=PAPER)
    fig.savefig(out.with_suffix(".svg"), facecolor=PAPER)
    plt.close(fig)
    with (OUTPUT / "effort-comparison.csv").open("w", newline="") as handle:
        fields = [
            "model",
            "effort",
            "n",
            "combined",
            "code_quality",
            "functional",
            "automated_quality",
            "security",
            "passed",
            "mean_minutes",
            "summed_solver_hours",
            "raw_tokens",
            "historical_summary_units",
            "solver_fallback_runs",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for g in groups:
            writer.writerow(
                {
                    "model": data["labels"][g["model"]],
                    "effort": g["effort"],
                    "n": g["n"],
                    "combined": g["combined"]["mean"],
                    "code_quality": g["panel"]["mean"],
                    "functional": g["functional"]["mean"],
                    "automated_quality": g["quality"]["mean"],
                    "security": g["security"]["mean"],
                    "passed": g["passed"],
                    "mean_minutes": g["minutes"]["mean"],
                    "summed_solver_hours": g["solver_seconds"] / 3600,
                    "raw_tokens": g["raw_tokens"],
                    "historical_summary_units": g["reported_tokens"],
                    "solver_fallback_runs": g["fallback_runs"],
                }
            )
    save(
        out.with_suffix(".json"),
        {
            "source": str(source),
            "source_sha256": digest(source.read_bytes()),
            "combined_axis": score_range,
            "code_quality_axis": quality_range,
            "runtime_axis": [0, max_minutes],
            "groups": groups,
            "notes": data["caveats"],
            "visual_qa": "See visual-qa.json for inspected output hashes",
        },
    )
    table = [
        "| Model | Effort | Combined /100 | Code quality /100 | Fully passed | Mean minutes | Raw tokens |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for g in groups:
        table.append(
            f"| {data['labels'][g['model']]} | {g['effort']} | {g['combined']['mean']:.2f} | "
            f"{g['panel']['mean']:.2f} | {g['passed']}/23 | {g['minutes']['mean']:.2f} | {g['raw_tokens']:,} |"
        )
    report = [
        "# Astra and Fable 5.1 comparison",
        "",
        "## Scope",
        "",
        "VulcanBench-SWE v4: 23 matched tasks, five efforts, two solver/harness combinations, "
        "230 original solver runs and 1,380 selected retrospective ratings. All saved solver "
        "summaries, patches, task definitions, and issue text passed source-hash checks.",
        "",
        "## Results",
        "",
        *table,
        "",
        "## Time and tokens",
        "",
        f"Summed solver time: Astra {totals['astra'] / 3600:.4f} hours; Fable {totals['fable'] / 3600:.4f} hours; "
        f"combined {(totals['astra'] + totals['fable']) / 3600:.4f} hours. "
        "These totals exclude post-hoc judging and gaps between solver runs, and are not calendar time.",
        "",
        "Raw tokens include cache reads and cache writes. Astra's input count already includes cached input. "
        "Fable's per-turn raw usage receipts are summed across all result events; auxiliary CLI model "
        "accounting may differ. The old Fable summary field is a cache-price-weighted quantity, not raw "
        "tokens, and four runs' summaries account only for their last result. Original summaries are "
        "preserved; the card uses receipt-level accounting. No new API-price comparison is claimed.",
        "",
        "## Scoring and review",
        "",
        "Each run uses 50% partial-credit functional score, 15% automated quality, 15% security, and "
        "20% Code quality. Code quality averages three Astra and three Claude persona ratings equally. "
        "The personas examine correctness, readability, and maintainability, using the issue, complete "
        "saved patch, and verifier outcome. Solver model/effort labels are omitted; reviewer effort is "
        "Medium, tools are disabled, and sessions are separate. LLM judgment is not human ground truth. "
        "Persona ratings are not independent human evaluations. The fixed 20% weight is a policy choice.",
        "",
        f"All 11 Fable solver fallback runs are included: Low 1, Medium 3, High 2, Extra-high 3, Max 2. "
        f"All {count} Claude reviewer fallback ratings are also included and disclosed. "
        "Fallbacks switched to Opus 4.8 after explicit session-level refusal events. The audit checks "
        "assistant-message model identities, not only each session's initial model. Astra model identity "
        "is requested-only because its stream does not contain a returned model identifier.",
        "",
        "Reviewer prompts and scoring match across populations. Claude's reviewer CLI was 2.1.260 for "
        "Astra and 2.1.261 for Fable; Fable solver CLI versions also varied. This is a model-plus-harness "
        "comparison, not a controlled measurement of base models alone.",
        "",
        "## Recovery and accounting",
        "",
        "High QueueCore readability on Fable used the first returned rating, 70, after deterministic "
        "escaping of unescaped quotes inside inline code in its rationale. The later retry, 72, is "
        "excluded. Both original streams and the failed-vote artifact remain intact; no new call was "
        "needed for this recovery. See reviewer-accounting.json for every selected/excluded raw call, "
        "hash, model fallback, usage, and judging time. Original Astra combined scores are unchanged.",
        "",
        "## Reading the card",
        "",
        "Dots and intervals use explicitly focused score axes; runtime bars begin at zero. Whiskers "
        "show one sample standard error across 23 tasks, not judge uncertainty or a significance test. "
        "Full passes require functional = 1.0 and remain distinct from combined scores. All replacement "
        "implementations are Python; opaque binaries were built from C.",
        "",
        "## Reproduce",
        "",
        "Run from the repository root:",
        "",
        "```sh",
        ".venv/bin/python -m harness.panel_comparison --include-reviewer-fallbacks",
        ".venv/bin/python -m harness.panel_receipts",
        ".venv/bin/python scripts/cii-v4-board/make_astra_fable_card.py",
        ".venv/bin/python scripts/cii-v4-board/make_comparison_notebook.py",
        "```",
        "",
        "Sources and outputs: comparison.json (per-run data and audit), reviewer-accounting.json "
        "(all review calls), effort-comparison.csv (ten effort rows), comparison-audit.ipynb "
        "(executed calculation checks), astra-vs-fable51.png, and astra-vs-fable51.svg. "
        "The notebook's code cells execute top-to-bottom with Python without a Jupyter kernel. "
        "This generator does not commit, push, deploy, or publish results.",
        "",
    ]
    (OUTPUT / "README.md").write_text("\n".join(report))
    accounting = read(OUTPUT / "reviewer-accounting.json")
    audit_note = [
        "",
        "## Final validation",
        "",
        "Share with caveats: all 230 runs and 1,380 selected ratings passed the evidence audit. "
        "The static card requires visual inspection after rendering; see visual-qa.json for the "
        "inspected output hashes. The companion notebook independently recalculates all ten "
        "score means and standard errors, and verifies raw solver-token receipts.",
        "",
    ]
    for panel, a in accounting.items():
        audit_note.append(
            f"- {panel}: {a['selected_ratings']} selected ratings from {a['all_calls']} calls; "
            f"{a['excluded_calls']} excluded, {a['format_recovered_ratings']} format-recovered, "
            f"{a['fallback_ratings']} fallback ratings. Elapsed review time, including pauses: "
            f"{a['elapsed_seconds_including_pauses'] / 60:.2f} minutes."
        )
    (OUTPUT / "README.md").write_text("\n".join(report + audit_note) + "\n")
    print(out)


if __name__ == "__main__":
    main()
