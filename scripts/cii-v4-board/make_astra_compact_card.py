"""Compact static card from verified panel evidence.

Contract: five effort means, 23 matched tasks each. Combined and code quality
use explicitly zoomed dot-and-interval charts; runtime bars start at zero.
Direct labels and sample SE preserve exact scores and uncertainty.
Task language counts describe replacement code separately from binary provenance.
One green root plus neutral runtime bars; PNG inspected before delivery.
"""

import argparse
import json
import math
import statistics
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/results/cii-v4-astra-2026-09/report23-gpt6-astra-concise.png"
LEVELS = ["low", "medium", "high", "extra-high", "max"]
PAPER, INK, GREEN = "#f7f5f0", "#171917", "#10A37F"


def main():  # noqa: PLR0915
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--quality-33",
        action="store_true",
        help="Preview 33 percent code quality with other weights scaled proportionally",
    )
    args = parser.parse_args()
    weight = 0.33 if args.quality_33 else 0.20
    scale = (1 - weight) / 0.8
    weights = {
        "functional": 0.5 * scale,
        "quality": 0.15 * scale,
        "security": 0.15 * scale,
        "panel": weight,
    }
    assert abs(sum(weights.values()) - 1) < 1e-12
    out = OUT.with_stem(OUT.stem + "-quality33-preview") if args.quality_33 else OUT
    source = ROOT / "runs-astra-cii-v4-claude-judging-v1/verification.json"
    data = json.loads(source.read_text())
    assert (
        data["runs"] == 115
        and data["valid_votes"] == 345
        and data["raw_votes_and_prompts_verified"]
    )
    suite = ROOT / "tasks/coding-intelligence-index-v4"
    task_ids = json.loads((suite / "suite.json").read_text())["tasks"]
    assert set(task_ids) == {r["task"] for r in data["rows"]}
    language_evidence = []
    for task in task_ids:
        metadata = json.loads((suite / task / "metadata.json").read_text())
        c_sources = list((suite / task / "builder").glob("*.c"))
        assert metadata["languages"] == ["python"] and c_sources
        language_evidence.append({"task": task, "replacement": "Python", "binary_source": "C"})
    rows = []
    for level in LEVELS:
        tasks = [r for r in data["rows"] if r["effort"] == level]
        assert len(tasks) == len({r["task"] for r in tasks}) == 23
        scores = [100 * sum(weights[k] * r[k] for k in weights) for r in tasks]
        reviews = [100 * r["panel"] for r in tasks]
        for r in tasks:
            expected = (
                0.5 * r["functional"]
                + 0.15 * r["quality"]
                + 0.15 * r["security"]
                + 0.1 * r["astra"]
                + 0.1 * r["claude"]
            )
            assert abs(expected - r["combined"]) < 1e-12
        runs = [
            json.loads(
                (ROOT / "runs-astra-cii-v4" / level / r["run_id"] / "summary.json").read_text()
            )
            for r in tasks
        ]
        rows.append(
            {
                "effort": level.capitalize(),
                "score": statistics.mean(scores),
                "baseline_score": statistics.mean(100 * r["combined"] for r in tasks),
                "se": statistics.stdev(scores) / math.sqrt(23),
                "review": statistics.mean(reviews),
                "review_se": statistics.stdev(reviews) / math.sqrt(23),
                "passed": sum(r["functional"] == 1 for r in tasks),
                "minutes": statistics.mean(r["duration_s"] for r in runs) / 60,
                "minutes_se": statistics.stdev(r["duration_s"] / 60 for r in runs) / math.sqrt(23),
                "tokens": sum(r["total_tokens"] for r in runs),
            }
        )
    for p in (ROOT / "scripts/rankings-chart").glob("*.ttf"):
        font_manager.fontManager.addfont(p)
    plt.rcParams.update({"font.family": "Geist", "text.color": INK})
    fig = plt.figure(figsize=(16, 9), dpi=150, facecolor=PAPER)

    def text(x, y, s, size=14, bold=False, ha="left", heading=False):
        family = (
            ("Chakra Petch SemiBold" if bold else "Chakra Petch Medium") if heading else "Geist"
        )
        fig.text(
            x,
            y,
            s,
            fontsize=size,
            weight="bold" if bold and not heading else "normal",
            fontfamily=family,
            color=INK,
            ha=ha,
            va="center",
        )

    def rule(y):
        fig.add_artist(
            plt.Line2D([0.045, 0.955], [y, y], transform=fig.transFigure, color="#b9b8b0", lw=0.8)
        )

    logo = fig.add_axes([0.045, 0.912, 0.034, 0.06])
    mark = logo.imshow(plt.imread(ROOT / "docs/assets/vulcanbench-logo.png"))
    clip = FancyBboxPatch(
        (0, 0), 1, 1, boxstyle="round,pad=0,rounding_size=.22", transform=logo.transAxes
    )
    mark.set_clip_path(clip)
    logo.axis("off")
    text(0.09, 0.944, "VulcanBench", 20, True, heading=True)
    text(0.955, 0.944, "REPORT 23  ·  SEPTEMBER 2026", 11, ha="right")
    rule(0.893)
    text(0.045, 0.839, "GPT-6 Astra", 34, True, heading=True)
    text(0.045, 0.791, "VulcanBench-SWE v4 · 23 tasks × 5 efforts · 115 runs", 16)  # noqa: RUF001
    text(0.955, 0.791, "Python replacements: 23/23 · C-built binaries: 23/23", 12, ha="right")
    if args.quality_33:
        text(0.955, 0.839, "PROPOSED WEIGHTS · 33% CODE QUALITY", 13, True, ha="right")

    score_limits = (89.5, 92) if args.quality_33 else (91, 93)
    text(0.16, 0.706, "Combined score", 20, True, heading=True)
    text(0.16, 0.668, f"/100 · zoom: {score_limits[0]} to {score_limits[1]}", 12)
    text(0.455, 0.706, "Code quality", 20, True, heading=True)
    text(0.455, 0.668, "/100 · zoom: 80 to 88", 12)
    text(0.75, 0.706, "Mean runtime", 20, True, heading=True)
    text(0.75, 0.668, "Minutes/task · lower is better", 12)

    # The same figure-space row centers align chart points and table cells.
    row_y = [0.60, 0.5475, 0.495, 0.4425, 0.39]
    combined = fig.add_axes([0.16, 0.36, 0.195, 0.27], facecolor=PAPER)
    combined.set_xlim(*score_limits)
    combined.set_ylim(0.36, 0.63)
    ax = fig.add_axes([0.455, 0.36, 0.195, 0.27], facecolor=PAPER)
    runtime = fig.add_axes([0.75, 0.36, 0.15, 0.27], facecolor=PAPER)
    ax.set_xlim(80, 88)
    ax.set_ylim(0.36, 0.63)
    runtime.set_xlim(0, 14)
    runtime.set_ylim(0.36, 0.63)
    for r, y in zip(rows, row_y, strict=True):
        assert score_limits[0] <= r["score"] - r["se"] <= r["score"] + r["se"] <= score_limits[1]
        combined.errorbar(
            r["score"],
            y,
            xerr=r["se"],
            fmt="D",
            markersize=8,
            color=GREEN,
            markeredgecolor=INK,
            markeredgewidth=0.6,
            ecolor=INK,
            elinewidth=1.4,
            capsize=4,
        )
        assert 80 <= r["review"] - r["review_se"] <= r["review"] + r["review_se"] <= 88
        assert 0 <= r["minutes"] - r["minutes_se"] <= r["minutes"] + r["minutes_se"] <= 14
        ax.errorbar(
            r["review"],
            y,
            xerr=r["review_se"],
            fmt="o",
            markersize=8,
            color=GREEN,
            markeredgecolor=INK,
            markeredgewidth=0.6,
            ecolor=INK,
            elinewidth=1.4,
            capsize=4,
        )
        text(0.045, y, r["effort"], 15)
        text(0.67, y, f"{r['review']:.2f}", 19, True)
        runtime.barh(
            y,
            r["minutes"],
            height=0.018,
            color="#9caaa5",
            edgecolor=INK,
            linewidth=0.5,
            xerr=r["minutes_se"],
            error_kw={"ecolor": INK, "elinewidth": 1.2, "capsize": 4},
        )
        text(0.955, y, f"{r['minutes']:.2f}", 19, True, ha="right")
        text(0.377, y, f"{r['score']:.2f}", 19, True)
    for chart, ticks in [
        (combined, [90, 91, 92] if args.quality_33 else [91, 92, 93]),
        (ax, [80, 84, 88]),
        (runtime, [0, 6, 12]),
    ]:
        chart.set_yticks([])
        chart.set_xticks(ticks)
        chart.tick_params(axis="x", length=0, labelsize=11, pad=8)
        chart.spines[["top", "left", "right"]].set_visible(False)
        chart.spines["bottom"].set_color("#b9b8b0")
        chart.grid(axis="x", color="#deddd6", lw=0.7)
        chart.set_axisbelow(True)
    spread = max(r["score"] for r in rows) - min(r["score"] for r in rows)
    gain = rows[-1]["review"] - rows[0]["review"]
    ratio = rows[-1]["minutes"] / rows[0]["minutes"]
    text(0.045, 0.303, f"Max vs Low: +{gain:.2f} quality points · {ratio:.2f}× runtime", 17, True)  # noqa: RUF001
    text(0.955, 0.303, f"Combined spread: {spread:.2f} points", 15, True, ha="right")
    rule(0.261)
    formula = (
        "Combined = 41.875% functional + 12.5625% automated quality + 12.5625% security + 33% code quality"
        if args.quality_33
        else "Combined = 50% functional + 15% automated quality + 15% security + 20% code quality"
    )
    text(0.045, 0.224, formula.replace("Combined = ", "Weights: "), 13, True)
    text(
        0.045,
        0.180,
        "Code quality: equal Astra + Claude reviews · 690 ratings · retrospective; bias possible",
        12,
    )
    text(
        0.045,
        0.136,
        "Whiskers: ±1 SE across 23 tasks, not judge uncertainty · Both score charts use zoomed scales",
        12,
    )
    text(0.045, 0.078, "Fully passed: Low 22/23; all others 23/23", 14, True)
    text(0.955, 0.078, "Solver sweep: 12h 00m 32s · 97.04M tokens", 13, ha="right")
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, facecolor=PAPER)
    out.with_suffix(".json").write_text(
        json.dumps(
            {
                "source": str(source),
                "source_profile": data["profile"],
                "profile": "proposed-quality33-proportional-preview"
                if args.quality_33
                else data["profile"],
                "weights": weights,
                "proposed": args.quality_33,
                "task_languages": language_evidence,
                "language_scope": "Replacement implementations, distinct from withheld binary source languages",
                "charts": {
                    "review": {"type": "dot and interval", "range": [80, 88]},
                    "combined": {"type": "dot and interval", "range": score_limits},
                    "runtime": {"type": "bar and interval", "range": [0, 14]},
                },
                "interval": "one sample SE across tasks",
                "rows": rows,
                "score_spread": spread,
                "max_low_review_gain": gain,
                "max_low_runtime_ratio": ratio,
            },
            indent=2,
        )
        + "\n"
    )
    print(out)
    print(
        json.dumps(
            {
                "rows": [{k: r[k] for k in ["effort", "score", "baseline_score"]} for r in rows],
                "spread": spread,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
