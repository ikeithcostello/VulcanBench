"""Takeaway-led static card, using the unchanged audited comparison.

Question: which solver/harness should a reader choose? Compare each model's
highest observed combined-score effort, selected symmetrically from five
fully covered efforts. Astra uses less runtime; Fable has the highest score.
Two intentionally selected model/effort groups, n=23 matched tasks each, from
230 runs in September 2026. No new weighting, exclusion, or significance claim.
Static scorecard with identical focused dot-and-SE score axes and zero-based
runtime bars. Two lab colors, direct labels, different point markers. Supporting
ten-group table stays in effort-comparison.csv. Export PNG/SVG, inspect PNG.
"""
from __future__ import annotations

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

PAPER, INK, RULE = "#f7f5f0", "#171917", "#c6c5bc"
COLORS = {"astra": "#10A37F", "fable": "#D97757"}


def validated_selection(data):
    require(data["complete"] and data["runs"] == 230 and data["valid_votes"] == 1380,
            "Incomplete comparison")
    require(data["weights"] == WEIGHTS and data["raw_votes_and_prompts_verified"]
            and data["source_hashes_unchanged"], "Unverified scoring profile")
    require(data["fallback_runs"] == 11 and data["reviewer_fallback_votes"] == 10
            and data["reviewer_fallbacks_included"], "Fallback disclosure mismatch")
    groups = data["groups"]
    require(groups == aggregate(data["rows"], {r["task"] for r in data["rows"]}, complete=True),
            "Stale aggregate")
    require({(g["model"], g["effort"]) for g in groups}
            == {(m, e) for m in COLORS for e in LEVELS}, "Incomplete effort sweep")
    require(all(g["n"] == 23 for g in groups), "Partial task coverage")
    best = {m: max((g for g in groups if g["model"] == m),
                   key=lambda g: g["combined"]["mean"]) for m in COLORS}
    lookup = {(g["model"], g["effort"]): g for g in groups}
    wins = {metric: sum(lookup["astra", e][metric]["mean"]
                       > lookup["fable", e][metric]["mean"] for e in LEVELS)
            for metric in ("combined", "panel")}
    wins["runtime"] = sum(lookup["astra", e]["minutes"]["mean"]
                          < lookup["fable", e]["minutes"]["mean"] for e in LEVELS)
    require(wins == {"combined": 4, "panel": 5, "runtime": 5}, "Takeaway changed")
    return best, wins


def main():  # noqa: PLR0915
    source = OUTPUT / "comparison.json"
    data = read(source)
    best, wins = validated_selection(data)
    astra, fable = best["astra"], best["fable"]
    gap = fable["combined"]["mean"] - astra["combined"]["mean"]
    ratio = fable["minutes"]["mean"] / astra["minutes"]["mean"]
    for font in (ROOT / "scripts/rankings-chart").glob("*.ttf"):
        font_manager.fontManager.addfont(font)
    plt.rcParams.update({"font.family": "Geist", "text.color": INK,
                         "svg.fonttype": "path"})
    fig = plt.figure(figsize=(16, 11), dpi=150, facecolor=PAPER)

    def text(x, y, label, size=16, bold=False, heading=False, numeric=False, ha="left"):
        family = "IBM Plex Mono" if numeric else (
            "Chakra Petch SemiBold" if bold else "Chakra Petch Medium") if heading else "Geist"
        weight = (500 if bold else 400) if numeric else (
            (600 if bold else 500) if heading else (700 if bold else 400))
        return fig.text(x, y, label, fontsize=size, fontfamily=family,
                        weight=weight, ha=ha, va="center", color=INK)

    def line(x1, x2, y, color=RULE, width=.8):
        fig.add_artist(plt.Line2D([x1, x2], [y, y], transform=fig.transFigure,
                                 color=color, lw=width))

    logo = fig.add_axes([.045, .92, .034, .0495])
    mark = logo.imshow(plt.imread(ROOT / "docs/assets/vulcanbench-logo.png"))
    mark.set_clip_path(FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0,rounding_size=.22",
                                     transform=logo.transAxes))
    logo.axis("off")
    text(.09, .945, "VulcanBench", 22, True, heading=True)
    text(.955, .945, "VulcanBench-SWE v4  /  September 2026", 15, ha="right")
    line(.045, .955, .9)
    text(.045, .85, "Similar scores. Astra takes less time.", 34, True, heading=True)
    text(.045, .8, f"Fable's best score is +{gap:.2f} points, with {ratio:.2f}× the runtime.", 21)  # noqa: RUF001
    text(.045, .759, "Each model's highest-scoring effort from the same five-effort sweep.", 15)

    for model, x in (("astra", .045), ("fable", .535)):
        g = best[model]
        right = x + .42
        line(x, right, .714, COLORS[model], 4)
        name = "GPT-6 Astra" if model == "astra" else "Fable 5.1 with fallbacks*"
        effort = g["effort"].capitalize()
        harness = "Codex" if model == "astra" else "Claude Code"
        text(x, .68, name, 24, True, heading=True)
        text(x, .642, f"{effort} effort · {harness} · n={g['n']}", 15)
        text(x, .597, "COMBINED SCORE /100", 14, True)
        text(x, .539, f"{g['combined']['mean']:.2f}", 48, True, numeric=True)
        text(right, .541, f"{g['passed']}/23\nfully passed", 15, ha="right")

        ax = fig.add_axes([x, .482, .42, .025], facecolor=PAPER)
        ax.set_xlim(90, 95)
        ax.set_ylim(-1, 1)
        ax.set_yticks([])
        ax.spines[["top", "left", "right"]].set_visible(False)
        ax.spines["bottom"].set_color(RULE)
        ax.set_xticks([90, 91, 92, 93, 94, 95])
        ax.tick_params(axis="x", length=0, labelsize=11, pad=5)
        metric = g["combined"]
        require(90 <= metric["mean"] - metric["se"] <= metric["mean"] + metric["se"] <= 95,
                "Clipped score whisker")
        ax.errorbar(metric["mean"], 0, xerr=metric["se"],
                    fmt="o" if model == "astra" else "D", color=COLORS[model],
                    markeredgecolor=INK, markeredgewidth=.7, markersize=8,
                    ecolor=INK, elinewidth=1.5, capsize=5)
        text(x, .433, "MEAN RUNTIME / TASK", 14, True)
        text(x, .394, f"{g['minutes']['mean']:.2f} min", 29, True, numeric=True)
        ax = fig.add_axes([x, .351, .42, .025], facecolor=PAPER)
        ax.set_xlim(0, 40)
        ax.set_ylim(-1, 1)
        ax.set_yticks([])
        ax.spines[["top", "left", "right"]].set_visible(False)
        ax.spines["bottom"].set_color(RULE)
        ax.set_xticks([0, 10, 20, 30, 40])
        ax.tick_params(axis="x", length=0, labelsize=11, pad=5)
        ax.barh(0, g["minutes"]["mean"], height=.8, color=COLORS[model],
                edgecolor=INK, linewidth=.5, xerr=g["minutes"]["se"],
                error_kw={"ecolor": INK, "elinewidth": 1.5, "capsize": 5})
        text(x, .303, "Code quality /100", 16)
        text(right, .303, f"{g['panel']['mean']:.2f} ± {g['panel']['se']:.2f}",
             18, True, numeric=True, ha="right")

    line(.045, .955, .27)
    text(.045, .24, "Across all five matched efforts", 20, True, heading=True)
    text(.045, .205, "Astra: faster at 5/5 · higher Code quality at 5/5 · higher combined score at 4/5", 17, True)
    line(.045, .955, .173)
    text(.045, .145, "Weights: 50% functional + 15% automated quality + 15% security + 20% Code quality", 13)
    text(.045, .118, "23 tasks per effort. Code quality: equal Astra + Claude panels. LLM judgment may be biased.", 13)
    text(.045, .091, "Whiskers and ±: 1 task SE, not significance. Score axes focus on 90 to 95. Runtime excludes judging.", 13)
    text(.045, .064, "*Opus 4.8 fallbacks: 11/115 Fable solver runs (2/23 at Max); 10/690 Claude ratings across both models.", 12)
    text(.045, .037, "Model + harness comparison · 230 runs · 1,380 ratings · 23 Python replacements for C-built binaries", 12)
    out = OUTPUT / "astra-vs-fable51-clean.png"
    fig.savefig(out, facecolor=PAPER)
    fig.savefig(out.with_suffix(".svg"), facecolor=PAPER)
    plt.close(fig)
    save(out.with_suffix(".json"), {
        "source": str(source), "source_sha256": digest(source.read_bytes()),
        "selection": "Highest observed combined-score effort per model from five complete efforts",
        "selected_groups": best, "astra_matched_effort_leads": wins,
        "fable_best_score_minus_astra_best_score": gap,
        "fable_runtime_divided_by_astra_runtime_at_selected_efforts": ratio,
        "score_axis": [90, 95], "runtime_axis": [0, 40],
        "notes": data["caveats"], "supporting_table": "effort-comparison.csv",
        "png_sha256": digest(out.read_bytes()),
        "svg_sha256": digest(out.with_suffix(".svg").read_bytes()),
        "visual_qa": "Requires visual inspection after rendering",
    })
    print(out)


if __name__ == "__main__":
    main()
