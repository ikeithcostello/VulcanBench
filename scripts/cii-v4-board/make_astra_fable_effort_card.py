"""Static effort-first comparison card from the unchanged audited results.

Question: can lower effort preserve performance while reducing resources?
Ten complete groups: two models, five discrete efforts, n=23 matched tasks
each. Grouped zero-based bars compare total score and mean runtime, both with
SE whiskers. Neither interpolates effort categories. Score spans 0 to 100%.
Exact lookup tables
retain Code quality, weighted total score percentages and raw tokens including
cache. Full-pass counts are not displayed; n=23 identifies sample size only.
Optional --with-costs adds a cache-aware API-equivalent cost column and sweep
totals. Astra's unknown per-request long-context premium is bounded explicitly.
Two lab colors and circle/diamond markers provide redundant model identity.
2400x1620 PNG/SVG is the explicit model-card surface. No editorial headline or
subheadline; the benchmark identity and model legend lead. Inspect PNG before handoff.
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
from make_astra_fable_clean_card import validated_selection  # noqa: E402

from harness.panel_comparison import OUTPUT, read, require  # noqa: E402
from harness.retrospective_judging import LEVELS, digest, save  # noqa: E402

PAPER, INK, RULE = "#f7f5f0", "#171917", "#c6c5bc"
COLORS = {"astra": "#10A37F", "fable": "#D97757"}
MARKERS = {"astra": "o", "fable": "D"}


def comparisons(data):
    best, _ = validated_selection(data)
    lookup = {(g["model"], g["effort"]): g for g in data["groups"]}
    result = {}
    for model in COLORS:
        peak = best[model]
        for effort in ("low", "medium"):
            g = lookup[model, effort]
            result[f"{model}_{effort}"] = {
                "baseline_effort": peak["effort"],
                "score_gap": peak["combined"]["mean"] - g["combined"]["mean"],
                "runtime_reduction_pct": 100 * (1 - g["minutes"]["mean"] / peak["minutes"]["mean"]),
                "raw_token_reduction_pct": 100 * (1 - g["raw_tokens"] / peak["raw_tokens"]),
            }
    require(
        round(result["astra_medium"]["runtime_reduction_pct"]) == 53,
        "Astra savings takeaway changed",
    )
    require(
        abs(result["fable_low"]["runtime_reduction_pct"]) < 1
        and result["fable_low"]["raw_token_reduction_pct"] < 0,
        "Fable savings takeaway changed",
    )
    return lookup, result


def main(with_costs=False):  # noqa: PLR0912, PLR0915
    source = OUTPUT / "comparison.json"
    data = read(source)
    lookup, tradeoffs = comparisons(data)
    costs = None
    cost_lookup = {}
    if with_costs:
        costs = read(OUTPUT / "api-equivalent-costs.json")
        require(costs["source_sha256"] == digest(source.read_bytes()), "Stale cost source")
        cost_lookup = {(g["model"], g["effort"]): g for g in costs["groups"]}
        require(
            set(cost_lookup) == set(lookup) and all(g["n"] == 23 for g in costs["groups"]),
            "Partial cost coverage",
        )
    for font in (ROOT / "scripts/rankings-chart").glob("*.ttf"):
        font_manager.fontManager.addfont(font)
    plt.rcParams.update(
        {
            "font.family": "Geist",
            "text.color": INK,
            "svg.fonttype": "path",
            "text.parse_math": False,
        }
    )
    fig = plt.figure(figsize=(16, 10.8), dpi=150, facecolor=PAPER)

    def vertical(y):
        # Remove the former 1.2-inch headline band without shrinking chart text.
        return (y - (0.1 if y > 0.9 else 0)) / 0.9

    def text(x, y, label, size=16, bold=False, heading=False, numeric=False, ha="left"):
        family = (
            "IBM Plex Mono"
            if numeric
            else ("Chakra Petch SemiBold" if bold else "Chakra Petch Medium")
            if heading
            else "Geist"
        )
        weight = (
            (500 if bold else 400)
            if numeric
            else ((600 if bold else 500) if heading else (700 if bold else 400))
        )
        return fig.text(
            x,
            vertical(y),
            label,
            fontsize=size,
            fontfamily=family,
            weight=weight,
            ha=ha,
            va="center",
            color=INK,
        )

    def line(x1, x2, y, color=RULE, width=0.8):
        fig.add_artist(
            plt.Line2D(
                [x1, x2],
                [vertical(y), vertical(y)],
                transform=fig.transFigure,
                color=color,
                lw=width,
            )
        )

    logo = fig.add_axes([0.04, vertical(0.94), 0.032, 0.0427 / 0.9])
    mark = logo.imshow(plt.imread(ROOT / "docs/assets/vulcanbench-logo.png"))
    mark.set_clip_path(
        FancyBboxPatch(
            (0, 0), 1, 1, boxstyle="round,pad=0,rounding_size=.22", transform=logo.transAxes
        )
    )
    logo.axis("off")
    text(0.083, 0.961, "VulcanBench", 22, True, heading=True)
    text(0.96, 0.961, "VulcanBench-SWE v4 / September 2026", 15, ha="right")
    line(0.04, 0.96, 0.925)
    for model, x, label in (
        ("astra", 0.045, "GPT-6 Astra · Codex"),
        ("fable", 0.40, "Fable 5.1 with fallbacks* · Claude Code"),
    ):
        fig.add_artist(
            plt.Line2D(
                [x],
                [vertical(0.806)],
                transform=fig.transFigure,
                marker=MARKERS[model],
                color=COLORS[model],
                markersize=8,
                markeredgecolor=INK,
                markeredgewidth=0.6,
                linestyle="none",
            )
        )
        text(x + 0.014, 0.806, label, 16, True)
    text(0.96, 0.806, "n=23 at every effort", 14, ha="right")
    axes_metadata = {}
    for metric, left, title, subtitle, limits, ticks in (
        (
            "combined",
            0.08,
            "Total score",
            "% · all four metrics · higher is better",
            (0, 100),
            [0, 20, 40, 60, 80, 100],
        ),
        (
            "minutes",
            0.57,
            "Time per task",
            "Mean minutes · lower is better",
            (0, 55),
            [0, 10, 20, 30, 40, 50],
        ),
    ):
        text(left, 0.765, title, 23, True, heading=True)
        text(left, 0.737, subtitle, 13)
        ax = fig.add_axes([left, vertical(0.473), 0.385, 0.237 / 0.9], facecolor=PAPER)
        ax.set_xlim(-0.55, 4.55)
        ax.set_ylim(*limits)
        ax.set_xticks(range(5), [e.capitalize() for e in LEVELS])
        ax.set_yticks(ticks)
        ax.tick_params(axis="both", length=0, labelsize=13, pad=8)
        ax.spines[["top", "right"]].set_visible(False)
        ax.spines[["bottom", "left"]].set_color(RULE)
        ax.grid(axis="y", color="#deddd6", linewidth=0.6)
        ax.set_axisbelow(True)
        for i, effort in enumerate(LEVELS):
            offset = 0.18 if metric == "minutes" else 0.22
            for model, shift in (("astra", -offset), ("fable", offset)):
                g = lookup[model, effort]
                mean, se = g[metric]["mean"], g[metric]["se"]
                require(limits[0] <= mean - se <= mean + se <= limits[1], "Clipped whisker")
                bars = ax.bar(
                    i + shift,
                    mean,
                    width=0.30 if metric == "minutes" else 0.38,
                    bottom=0,
                    color=COLORS[model],
                    edgecolor=INK,
                    linewidth=0.6,
                    hatch="//" if model == "fable" else None,
                    yerr=se,
                    error_kw={"ecolor": INK, "elinewidth": 1, "capsize": 3},
                )
                prefix = "runtime" if metric == "minutes" else "score"
                bars.patches[0].set_gid(f"{prefix}-{model}-{effort}")
                label_y = mean + se
                label = f"{mean:.2f}" if metric == "combined" else f"{mean:.1f}"
                ax.annotate(
                    label,
                    (i + shift, label_y),
                    xytext=(0, 5 if metric == "combined" else 8),
                    textcoords="offset points",
                    ha="center",
                    va="bottom",
                    fontsize=10 if metric == "combined" else 11,
                    fontfamily="IBM Plex Mono",
                    color=INK,
                    bbox={"facecolor": PAPER, "edgecolor": "none", "pad": 0.3},
                )
        axes_metadata[metric] = list(limits)

    for model, effort, left in (("astra", "medium", 0.04), ("fable", "low", 0.535)):
        selected = lookup[model, effort]
        detail = (
            f"API ${cost_lookup[model, effort]['mean_usd']:.2f}/task"
            if costs
            else f"{selected['minutes']['mean']:.2f} min/task"
        )
        text(
            left,
            0.416,
            f"{model.capitalize()} {effort.capitalize()}: total {selected['combined']['mean']:.2f}%; {detail}.",
            16,
            True,
        )
    for model, left in (("astra", 0.04), ("fable", 0.535)):
        right = left + 0.425
        line(left, right, 0.388, COLORS[model], 3)
        text(left, 0.361, "Astra" if model == "astra" else "Fable*", 14, True)
        quality_x, score_x, token_x = (0.17, 0.26, 0.335) if costs else (0.203, 0.306, 0.425)
        text(
            left + quality_x,
            0.361,
            "Code quality" if costs else "Code quality /100",
            12 if costs else 13,
            True,
            ha="right",
        )
        text(left + score_x, 0.361, "Total score", 11 if costs else 13, True, ha="right")
        text(left + token_x, 0.361, "Tokens/task", 11 if costs else 13, True, ha="right")
        if costs:
            text(right, 0.361, "API $/task†", 13, True, ha="right")
        for i, effort in enumerate(LEVELS):
            g = lookup[model, effort]
            y = 0.331 - i * 0.033
            text(
                left,
                y,
                effort.capitalize(),
                14,
                bold=effort == ("medium" if model == "astra" else "max"),
            )
            text(
                left + quality_x,
                y,
                f"{g['panel']['mean']:.2f} ± {g['panel']['se']:.2f}",
                11 if costs else 13,
                numeric=True,
                ha="right",
            )
            text(
                left + score_x,
                y,
                f"{g['combined']['mean']:.2f}%",
                13 if costs else 14,
                True,
                numeric=True,
                ha="right",
            )
            text(
                left + token_x,
                y,
                f"{g['raw_tokens'] / g['n'] / 1e6:.2f}M",
                13 if costs else 14,
                numeric=True,
                ha="right",
            )
            if costs:
                text(
                    right,
                    y,
                    f"${cost_lookup[model, effort]['mean_usd']:.2f}",
                    16,
                    True,
                    numeric=True,
                    ha="right",
                )
    line(0.04, 0.96, 0.17)
    text(
        0.04,
        0.146,
        "Weights: 50% functional + 15% automated quality + 15% security + 20% Code quality",
        13,
    )
    text(
        0.04,
        0.122,
        "Code quality: equal Astra + Claude panels. Whiskers and ±: 1 task SE, not judge uncertainty or significance.",
        12,
    )
    if costs:
        text(
            0.04,
            0.098,
            "†USD API-equivalent estimates, not subscription charges. Official rates checked Sep 6, 2026; cache-aware; judging excluded.",
            12,
        )
        text(
            0.04,
            0.074,
            f"Astra assumes requests ≤272k input tokens. Request sizes are unlogged: conservative sweep upper bound "
            f"${costs['astra_long_context_upper_total_usd']:,.0f}, still {costs['astra_lower_cost_pct_conservative']:.0f}% lower.",
            12,
        )
        text(
            0.04,
            0.05,
            "*11/115 Fable runs include Opus fallback usage; auxiliary calls priced too. 10/690 Claude ratings use Opus 4.8. LLM bias remains possible.",
            12,
        )
        text(
            0.04,
            0.026,
            "Code quality /100 · Raw tokens include cache · 230 runs · 23 Python replacements for C-built binaries · Effort labels are harness-specific",
            12,
        )
    else:
        text(
            0.04,
            0.098,
            "Raw tokens include cache, not API cost. Astra Medium uses 26% fewer raw tokens than Extra-high; Fable Low uses more than Max.",
            12,
        )
        text(
            0.04,
            0.074,
            "*Opus 4.8 fallbacks included: 11/115 Fable solver runs; 10/690 Claude ratings across both models. LLM judgment may be biased.",
            12,
        )
        text(
            0.04,
            0.05,
            "230 runs · 1,380 ratings · 23 Python replacements for C-built binaries · Runtime excludes judging · Effort labels are harness-specific",
            12,
        )
        text(
            0.04,
            0.026,
            "Near peak compares observed combined scores: Astra Medium 91.73 vs Extra-high 92.39. Savings are descriptive, not guaranteed.",
            12,
        )
    out = OUTPUT / ("astra-vs-fable51-effort-cost.png" if costs else "astra-vs-fable51-effort.png")
    fig.savefig(out, facecolor=PAPER)
    fig.savefig(out.with_suffix(".svg"), facecolor=PAPER)
    plt.close(fig)
    save(
        out.with_suffix(".json"),
        {
            "source": str(source),
            "source_sha256": digest(source.read_bytes()),
            "groups": data["groups"],
            "tradeoffs_vs_each_models_highest_observed_score": tradeoffs,
            "axes": axes_metadata,
            "tokens": "Raw mean per task, including cache; not API dollars",
            "chart_types": {
                "combined": "grouped zero-based bars and SE",
                "minutes": "grouped zero-based bars and SE",
            },
            "notes": data["caveats"],
            "png_sha256": digest(out.read_bytes()),
            "svg_sha256": digest(out.with_suffix(".svg").read_bytes()),
            "cost_source_sha256": digest((OUTPUT / "api-equivalent-costs.json").read_bytes())
            if costs
            else None,
            "costs": costs["groups"] if costs else None,
            "visual_qa": "Requires inspection after rendering",
        },
    )
    print(out)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--with-costs", action="store_true")
    main(parser.parse_args().with_costs)
