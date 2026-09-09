"""Render the GPT-6 Astra CII v4 five-effort model card."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/results/cii-v4-astra-2026-09/report23-gpt6-astra-cii-v4-effort-sweep.png"
PAPER, INK, RULE, NAVY, MID, PALE, BAND, GREY = (
    "#f7f5f0",
    "#1c1a17",
    "#1c1a17",
    "#27425f",
    "#5d7ba0",
    "#8ba3c4",
    "#efeade",
    "#6b675f",
)
LEVELS = [
    ("low", "Low"),
    ("medium", "Medium"),
    ("high", "High"),
    ("extra-high", "Extra-high"),
    ("max", "Max"),
]


def suite(level: str) -> dict:
    for path in (ROOT / "runs-astra-cii-v4" / level).glob("*/suite.json"):
        data = json.loads(path.read_text())
        if data.get("n_runs") == 23 and not data.get("errors"):
            return data["aggregate"][0]
    raise RuntimeError(f"no valid suite result for {level}")


def main() -> None:  # noqa: PLR0915
    rows = [(label, suite(level)) for level, label in LEVELS]
    total_tokens = sum(row["total_tokens"] for _, row in rows)
    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=PAPER)

    def text(x, y, value, size=11, weight="normal", color=INK, ha="left", style="normal"):
        fig.text(
            x,
            y,
            value,
            fontsize=size,
            fontweight=weight,
            fontstyle=style,
            color=color,
            ha=ha,
            va="center",
            fontfamily="Baskerville",
        )

    def rule(y, x0=0.045, x1=0.955, lw=1.0):
        fig.add_artist(plt.Line2D([x0, x1], [y, y], lw=lw, color=RULE, transform=fig.transFigure))

    text(0.045, 0.955, "V U L C A N B E N C H", 12, "bold")
    text(0.163, 0.955, "T E C H N I C A L   R E P O R T   N O .  2 3", 12, color=GREY)
    text(
        0.955,
        0.955,
        "S E P T E M B E R   2 0 2 6   ·   2 3   T A S K S   ·   1   M O D E L   ·   5   E F F O R T   L E V E L S   ·   1 2 . 0  H",
        9.5,
        color=GREY,
        ha="right",
    )
    rule(0.936, lw=1.6)
    rule(0.9315, lw=0.7)
    text(0.5, 0.876, "GPT-6 Astra, Effort Sweep", 28, "bold", ha="center")
    text(
        0.5,
        0.828,
        "VulcanBench-SWE v4, twenty-three opaque legacy binaries scored across four computed factors",
        14,
        style="italic",
        ha="center",
    )
    text(
        0.5,
        0.782,
        "100.0% pass@1 (23/23) from Medium through Max; Low reached 95.7% (22/23).",
        15,
        "bold",
        ha="center",
    )

    text(0.045, 0.690, "T A B L E   1 .", 11, "bold")
    text(0.118, 0.690, "Validated results, one attempt per task and effort level.", 11)
    cols = [
        (0.045, "Effort", "left"),
        (0.190, "pass@1", "right"),
        (0.280, "Solved", "right"),
        (0.390, "Tokens", "right"),
        (0.495, "Time/task", "right"),
        (0.580, "Aggregate", "right"),
    ]
    y0 = 0.612
    rule(y0 + 0.020, 0.045, 0.580)
    for x, name, align in cols:
        text(x, y0, name, 11.5, "bold", ha=align)
    rule(y0 - 0.016, 0.045, 0.580, 0.7)
    for i, (label, row) in enumerate(rows):
        y = y0 - 0.050 - i * 0.040
        if i == 4:
            fig.patches.append(
                plt.Rectangle(
                    (0.045, y - 0.017),
                    0.535,
                    0.034,
                    transform=fig.transFigure,
                    facecolor=BAND,
                    edgecolor="none",
                )
            )
        weight = "bold" if i == 4 else "normal"
        text(0.045, y, label, 11.5, weight)
        text(0.190, y, f"{row['pass_at_1'] * 100:.1f}%", 11.5, weight, ha="right")
        text(0.280, y, f"{row['solved']}/23", 11.5, weight, ha="right")
        text(0.390, y, f"{row['total_tokens'] / 1e6:.2f} M", 11.5, weight, ha="right")
        text(0.495, y, f"{row['avg_duration_s'] / 60:.1f} min", 11.5, weight, ha="right")
        text(0.580, y, f"{row['avg_total']:.4f}", 11.5, weight, ha="right")
    rule(y0 - 0.050 - 4 * 0.040 - 0.019, 0.045, 0.580)
    text(0.045, 0.375, "1.", 10.5, "bold")
    text(
        0.065,
        0.375,
        f"Sweep wall-clock: 12 h 00 min 32 s. Total model tokens across all 115 runs: {total_tokens / 1e6:.2f} M.",
        10.5,
    )

    text(0.045, 0.300, "T A B L E   2 .", 11, "bold")
    text(0.118, 0.300, "Interpretation.", 11)
    text(0.045, 0.255, "Low", 11.5, "bold")
    text(
        0.145, 0.255, "Only level below a perfect functional score: PaddockCore was partial.", 11.5
    )
    text(0.045, 0.215, "Medium to Max", 11.5, "bold")
    text(
        0.145,
        0.215,
        "All four levels solved every task. Max used the most tokens and took the longest on average.",
        11.5,
    )
    rule(0.185, 0.045, 0.580)

    text(0.620, 0.690, "F I G U R E   1 .", 11, "bold")
    text(0.720, 0.690, "Functional pass@1 and mean time per task.", 11)
    ax1 = fig.add_axes([0.620, 0.355, 0.155, 0.280], facecolor=PAPER)
    ax2 = fig.add_axes([0.815, 0.355, 0.140, 0.280], facecolor=PAPER)
    labels = [label for label, _ in rows]
    passes = [row["pass_at_1"] * 100 for _, row in rows]
    mins = [row["avg_duration_s"] / 60 for _, row in rows]
    for ax, values, title, top in [
        (ax1, passes, "Functional pass@1", 105),
        (ax2, mins, "Mean minutes per task", 12),
    ]:
        ax.bar(range(5), values, color=[PALE, MID, MID, NAVY, NAVY], width=0.62)
        ax.set_ylim(0, top)
        ax.set_xticks(
            range(5), labels, rotation=40, ha="right", fontsize=8.5, fontfamily="Baskerville"
        )
        ax.set_title(title, fontsize=11, fontfamily="Baskerville", pad=8)
        ax.tick_params(axis="y", labelsize=8.5, length=0, colors=GREY)
        ax.spines[["top", "right", "left"]].set_visible(False)
        ax.spines["bottom"].set_color(RULE)
        ax.grid(axis="y", color="#d9d5cc", linewidth=0.6)
        ax.set_axisbelow(True)
        for j, value in enumerate(values):
            ax.text(
                j,
                value + top * 0.018,
                f"{value:.1f}",
                ha="center",
                va="bottom",
                fontsize=8.5,
                color=INK,
                fontfamily="Baskerville",
            )
    rule(0.115)
    text(0.045, 0.078, "Method.", 10.5, "bold")
    text(
        0.105,
        0.078,
        "VulcanBench-SWE v4, 23 tasks, GPT-6 Astra through Codex, one Apple Silicon machine, one attempt per task and effort level.",
        9.5,
    )
    text(
        0.105,
        0.057,
        "Functional pass@1 uses hidden tests. Aggregate re-normalizes functional, quality, security, and efficiency; human-like judges were disabled.",
        9.5,
    )
    text(
        0.955,
        0.023,
        "V U L C A N B E N C H   ·   O P E N   S O U R C E   ·   September 5, 2026",
        8,
        color=GREY,
        ha="right",
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=100, facecolor=PAPER)


if __name__ == "__main__":
    main()
