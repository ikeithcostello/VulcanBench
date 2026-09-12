"""Three-model effort card for VulcanBench-SWE v4: Astra, Fable 5.1, Opus 5.

Same surface and visual language as the Astra vs Fable v3.4 card (2400x1620
parchment, lab colors with redundant markers, SE whiskers, effort on the x
axis), extended to a third model.

Astra and Fable 5.1 come from the audited comparison bundle in
docs/results/swe-v4-astra-fable51-2026-09/; Opus 5 is computed from its own
run summaries. Only metrics all three share are plotted: functional pass rate
and runtime. The judged Code quality panel covered Astra and Fable only, so
combined score is deliberately absent rather than estimated for Opus.

Sampling differs by model and is labelled on the card: Astra and Fable are one
attempt per task (n=23 per effort), Opus 5 is three attempts per task
(41 to 69 runs per effort), so Opus carries the tighter interval.

    python scripts/cii-v4-board/make_three_model_effort_card.py
"""

from __future__ import annotations

import json
import statistics
import textwrap
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "docs/results/swe-v4-astra-fable51-2026-09/astra-vs-fable51-effort.json"
OUT = ROOT / "docs/results/swe-v4-three-model-effort-2026-09"
LEVELS = ["low", "medium", "high", "extra-high", "max"]
LABELS = ["Low", "Medium", "High", "Extra high", "Max"]

PAPER, INK, RULE, MUTED = "#f7f5f0", "#171917", "#c6c5bc", "#6b675f"
SERIES = [
    ("astra", "GPT-6 Astra", "Codex", "#10A37F", "o"),
    ("fable", "Fable 5.1", "Claude Code", "#D97757", "D"),
    ("opus", "Opus 5", "Claude Code", "#B03A55", "s"),
]


def opus_rows():
    """Per-effort pass rate and runtime for Opus 5 from its run summaries."""
    sources = {
        "low": ("runs-effort-opus5/low/*/summary.json", "low"),
        "medium": ("runs-effort-opus5/medium/*/summary.json", "medium"),
        "high": ("runs-effort-opus5/high/*/summary.json", "high"),
        # No --effort flag means the Claude Code default, which is xhigh.
        "extra-high": (
            "docs/results/cii-v4-fable51-2026-09/opus5-gate-summaries/*/summary.json",
            None,
        ),
        "max": ("runs-effort-opus5/max/*/summary.json", "max"),
    }
    rows = {}
    for level, (pattern, want) in sources.items():
        by = defaultdict(list)
        for path in ROOT.glob(pattern):
            s = json.loads(path.read_text())
            if s.get("model") != "claude-code:claude-opus-5":
                continue
            eff = (s.get("effort") or {}).get("requested")
            if (want is None and eff) or (want and eff != want):
                continue
            by[s["task_id"]].append((s["scores"]["functional"], s["duration_s"] / 60))
        rates = {t: sum(1 for f, _ in v if f == 1.0) / len(v) for t, v in by.items()}
        n = len(rates)
        mean = sum(rates.values()) / n
        var = sum((r - mean) ** 2 for r in rates.values()) / (n - 1)
        mins = [d for v in by.values() for _, d in v]
        rows[level] = {
            "pass": mean * 100,
            "pass_se": (var / n) ** 0.5 * 100,
            "minutes": statistics.mean(mins),
            "minutes_se": statistics.stdev(mins) / len(mins) ** 0.5,
            "runs": len(mins),
        }
    return rows


def bundle_rows():
    groups = json.loads(BUNDLE.read_text())["groups"]
    out = defaultdict(dict)
    for g in groups:
        # passed is a count of runs out of n; one attempt per task here.
        out[g["model"]][g["effort"]] = {
            "pass": 100.0 * g["passed"] / g["n"],
            # A count has no across-task SE in the bundle; binomial SE on the
            # observed proportion is the honest stand-in and is labelled.
            "pass_se": 100.0
            * ((g["passed"] / g["n"]) * (1 - g["passed"] / g["n"]) / g["n"]) ** 0.5,
            "minutes": g["minutes"]["mean"],
            "minutes_se": g["minutes"]["se"],
            "runs": g["n"],
        }
    return out


def main() -> None:  # noqa: PLR0912, PLR0915, linear top-to-bottom card layout
    data = bundle_rows()
    data["opus"] = opus_rows()

    for font in (ROOT / "scripts/rankings-chart").glob("*.ttf"):
        font_manager.fontManager.addfont(font)
    plt.rcParams.update({"font.family": "Geist", "text.color": INK, "text.parse_math": False})
    fig = plt.figure(figsize=(16, 11.5), dpi=150, facecolor=PAPER)

    def text(x, y, s, size=16, bold=False, heading=False, numeric=False, ha="left", color=INK):
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
            y,
            s,
            fontsize=size,
            fontfamily=family,
            weight=weight,
            ha=ha,
            va="center",
            color=color,
        )

    def rule(y, x0=0.055, x1=0.945, lw=1.2, color=RULE):
        fig.add_artist(plt.Line2D([x0, x1], [y, y], lw=lw, color=color, transform=fig.transFigure))

    # masthead
    logo = plt.imread(str(ROOT / "scripts/rankings-chart/vb_logo_rounded.png"))
    ax_logo = fig.add_axes([0.055, 0.935, 0.028, 0.042])
    ax_logo.imshow(logo)
    ax_logo.axis("off")
    text(0.091, 0.955, "VulcanBench", 25, bold=True, heading=True)
    text(0.945, 0.955, "September 2026", 17, color=MUTED, ha="right")
    rule(0.925, lw=1.6, color=INK)

    text(
        0.055,
        0.875,
        "VulcanBench-SWE v4: three models across the effort ladder",
        33,
        bold=True,
        heading=True,
    )
    text(
        0.055,
        0.833,
        "Functional pass rate and runtime at every effort level. 23 binary-reconstruction "
        "tasks, graded by deterministic hidden tests.",
        17,
        color=MUTED,
    )

    # legend: measure each name so the harness suffix cannot overlap it
    renderer = fig.canvas.get_renderer()
    x = 0.055
    for _key, name, harness, color, marker in SERIES:
        fig.add_artist(
            plt.Line2D(
                [x],
                [0.783],
                marker=marker,
                color=color,
                markersize=13,
                linestyle="none",
                transform=fig.transFigure,
            )
        )
        label = text(x + 0.018, 0.783, name, 19, bold=True, heading=True)
        w = label.get_window_extent(renderer).width / fig.bbox.width
        text(x + 0.018 + w + 0.008, 0.783, f"·  {harness}", 17, color=MUTED)
        x += 0.30

    # panels
    axl = fig.add_axes([0.055, 0.375, 0.40, 0.345])
    axr = fig.add_axes([0.545, 0.375, 0.40, 0.345])
    for ax in (axl, axr):
        ax.set_facecolor(PAPER)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(RULE)
        ax.tick_params(colors=MUTED, length=0)
        ax.grid(axis="y", color=RULE, lw=0.8, alpha=0.6)
        ax.set_axisbelow(True)
        ax.set_xticks(range(5))
        ax.set_xticklabels(LABELS, fontsize=15, fontfamily="Geist", color=INK)

    text(0.055, 0.748, "Tasks solved", 24, bold=True, heading=True)
    text(0.055, 0.727, "Percent of 23 tasks  ·  higher is better", 15, color=MUTED)
    for key, _name, _h, color, marker in SERIES:
        ys = [data[key][lv]["pass"] for lv in LEVELS]
        es = [data[key][lv]["pass_se"] for lv in LEVELS]
        axl.errorbar(
            range(5),
            ys,
            yerr=es,
            color=color,
            marker=marker,
            markersize=11,
            lw=2.4,
            capsize=4,
            ecolor=color,
            elinewidth=1.2,
            zorder=3,
        )
        dy = -22 if key == "opus" else 13
        for i, v in enumerate(ys):
            axl.annotate(
                f"{v:.1f}",
                (i, v),
                textcoords="offset points",
                xytext=(0, dy),
                ha="center",
                fontsize=13,
                fontfamily="IBM Plex Mono",
                color=INK,
            )
    axl.set_ylim(0, 108)
    axl.set_yticks([0, 25, 50, 75, 100])
    axl.set_yticklabels(["0", "25", "50", "75", "100%"], fontsize=14, fontfamily="Geist")

    text(0.545, 0.748, "Mean runtime", 24, bold=True, heading=True)
    text(0.545, 0.727, "Minutes per task  ·  lower is better", 15, color=MUTED)
    width = 0.26
    for j, (key, _name, _h, color, _m) in enumerate(SERIES):
        ys = [data[key][lv]["minutes"] for lv in LEVELS]
        es = [data[key][lv]["minutes_se"] for lv in LEVELS]
        xs = [i + (j - 1) * width for i in range(5)]
        axr.bar(
            xs,
            ys,
            width,
            color=color,
            zorder=3,
            yerr=es,
            error_kw={"ecolor": INK, "elinewidth": 1.1, "capsize": 3, "zorder": 4},
        )
        for xi, v in zip(xs, ys, strict=True):
            axr.annotate(
                f"{v:.1f}",
                (xi, v),
                textcoords="offset points",
                xytext=(0, 16),
                ha="center",
                fontsize=12,
                fontfamily="IBM Plex Mono",
                color=INK,
            )
    axr.set_ylim(0, 82)
    axr.set_yticks([0, 20, 40, 60, 80])
    axr.set_yticklabels(["0", "20", "40", "60", "80"], fontsize=14, fontfamily="Geist")

    # table
    rule(0.320)
    text(0.055, 0.297, "Table 1", 17, bold=True, heading=True)
    text(0.115, 0.297, "|  Pass rate by effort, with runs behind each cell", 17, color=MUTED)
    cols = [0.42, 0.525, 0.63, 0.735, 0.855]
    text(0.055, 0.258, "Model", 15, bold=True, heading=True)
    for c, lab in zip(cols, LABELS, strict=True):
        text(c, 0.258, lab, 15, bold=True, heading=True, ha="right")
    rule(0.242, lw=0.9)
    y = 0.210
    for key, name, harness, color, _m in SERIES:
        lbl = text(0.055, y, name, 16, bold=True, heading=True, color=color)
        wn = lbl.get_window_extent(renderer).width / fig.bbox.width
        text(0.055 + wn + 0.012, y, harness, 14, color=MUTED)
        for c, lv in zip(cols, LEVELS, strict=True):
            r = data[key][lv]
            text(c, y, f"{r['pass']:.1f}%", 16, numeric=True, ha="right")
            text(c, y - 0.024, f"n={r['runs']}", 12, numeric=True, ha="right", color=MUTED)
        y -= 0.055

    foot = (
        "Astra and Fable 5.1 are the audited v3.4 comparison bundle at one attempt per task; "
        "Opus 5 is three attempts per task, so its interval is tighter and its pass rate is a "
        "mean over attempts. Intervals are one standard error: across tasks for Opus 5, "
        "binomial on the observed proportion for Astra and Fable. The judged Code quality panel "
        "covered Astra and Fable only, so combined score is omitted here rather than estimated "
        "for Opus 5. Host execution, subscription harnesses, uniform 10-hour timeout. Astra and "
        "Fable were measured on a different machine from Opus 5, so the runtime panel compares "
        "across hosts: read the accuracy gaps as robust and the wall-clock gaps as indicative."
    )
    for i, line in enumerate(textwrap.wrap(foot, width=168)):
        text(0.055, 0.052 - i * 0.017, line, 12, color=MUTED)

    OUT.mkdir(parents=True, exist_ok=True)
    png = OUT / "swe-v4-three-model-effort.png"
    fig.savefig(png, facecolor=PAPER)
    print("wrote", png)
    for key, name, *_rest in SERIES:
        print(f"  {name:14} " + "  ".join(f"{data[key][lv]['pass']:5.1f}%" for lv in LEVELS))


if __name__ == "__main__":
    main()
