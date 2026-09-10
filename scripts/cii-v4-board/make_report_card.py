"""VulcanBench Technical Report No. 21 card: Claude Fable 5.1 on CII v4.

House single-model report-card format (see Reports No. 10, 12, 19) in its
wordless variant: 1600x900 parchment, serif, small-caps masthead over a rule,
a title, a strip of headline figures, then numbered tables on the left and a
four-panel figure on the right. No prose headline, no caption sentences, no
Method paragraph: every claim is carried by a table cell, an axis or a
labelled key/value in the footer strip.

    python scripts/cii-v4-board/make_report_card.py

Chart-integrity rules that must survive edits (see CLAUDE.md): run counts stay
visible, the pass@1 bar keeps its +/-1 stderr whisker, the unsolved table keeps
the exact families that failed, and the one-run-per-task and host-execution
caveats stay in the footer strip.
"""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "report21-fable51-cii-v4.png"
MODEL = "claude-code:claude-fable-5-1"

PAPER = "#f7f5f0"
INK = "#1c1a17"
BAND = "#efeade"
RULE = "#1c1a17"
NAVY = "#27425f"
MID = "#5d7ba0"
PALE = "#8ba3c4"
GREY = "#6b675f"

# Fable 5.1 list price; cache reads ($0.25/M) are not modelled, so the
# api-equivalent cost this yields is an upper bound.
IN_RATE, OUT_RATE = 10.00, 50.00

SERIF = "Baskerville"
DATE = "September 2, 2026"
NUMBER = "No. 21"


def load():
    suite = json.loads(
        (ROOT / "tasks" / "coding-intelligence-index-v4" / "suite.json").read_text()
    )["tasks"]
    by_task = defaultdict(list)
    for path in ROOT.glob("runs-board/*/summary.json"):
        try:
            s = json.loads(path.read_text())
        except Exception:
            continue
        if s.get("model") != MODEL or s.get("task_id") not in suite:
            continue
        # xhigh card (Claude Code default): keep explicit-effort sweep runs out.
        if (s.get("effort") or {}).get("requested"):
            continue
        functional = (s.get("scores") or {}).get("functional")
        if functional is None:
            continue
        missed = [k for k, v in (s.get("verifier") or {}).get("fail_to_pass", {}).items() if not v]
        tok = s.get("tokens") or {}
        cost = (
            int(tok.get("prompt") or 0) * IN_RATE + int(tok.get("completion") or 0) * OUT_RATE
        ) / 1e6
        by_task[s["task_id"]].append(
            (
                float(functional),
                s["duration_s"] / 60.0,
                int(s.get("total_tokens") or 0),
                missed,
                cost,
            )
        )
    return by_task


def sliced(by_task, cutoff):
    rates = [
        sum(1 for f, d, *_ in runs if f == 1.0 and (cutoff is None or d <= cutoff)) / len(runs)
        for runs in by_task.values()
    ]
    mean = sum(rates) / len(rates)
    n = len(rates)
    var = sum((r - mean) ** 2 for r in rates) / (n - 1) if n > 1 else 0.0
    return mean, (var / n) ** 0.5


def short(task_id: str) -> str:
    return task_id.replace("legacy-", "").split("-binary")[0].split("-order")[0].split("-store")[0]


def main() -> None:  # noqa: PLR0912, PLR0915, linear top-to-bottom page layout
    data = load()
    runs = [(short(t), f, d, tok, m, c) for t, v in data.items() for f, d, tok, m, c in v]
    n = len(runs)
    solved = [r for r in runs if r[1] == 1.0]
    unsolved = sorted((r for r in runs if r[1] < 1.0), key=lambda r: r[1])
    full, err = sliced(data, None)
    w10, _ = sliced(data, 10)
    w30, _ = sliced(data, 30)
    med_solved = statistics.median([r[2] for r in solved])
    med_unsolved = statistics.median([r[2] for r in unsolved])
    med_tok_solved = statistics.median([r[3] for r in solved if r[3]])
    med_tok_unsolved = statistics.median([r[3] for r in unsolved if r[3]])
    med_cost_all = statistics.median([r[5] for r in runs])
    med_time_all = statistics.median([r[2] for r in runs])
    total_h = sum(r[2] for r in runs) / 60
    total_cost = sum(r[5] for r in runs)

    fig = plt.figure(figsize=(16, 9), dpi=100)
    fig.patch.set_facecolor(PAPER)

    def txt(x, y, s, size=9, weight="normal", style="normal", color=INK, ha="left", va="center"):
        return fig.text(
            x,
            y,
            s,
            fontsize=size,
            fontweight=weight,
            fontstyle=style,
            color=color,
            ha=ha,
            va=va,
            fontfamily=SERIF,
        )

    def rule(y, x0=0.045, x1=0.955, lw=1.1, color=RULE):
        fig.add_artist(plt.Line2D([x0, x1], [y, y], lw=lw, color=color, transform=fig.transFigure))

    def dress(ax):
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.spines["bottom"].set_color(INK)
        ax.tick_params(length=0, colors=INK)
        for lab in ax.get_xticklabels():
            lab.set_fontsize(9)
            lab.set_fontfamily(SERIF)
            lab.set_fontstyle("italic")
            lab.set_color(INK)
        for lab in ax.get_yticklabels():
            lab.set_fontsize(8.5)
            lab.set_fontfamily(SERIF)
            lab.set_color(GREY)

    # --- masthead ---------------------------------------------------------
    txt(0.045, 0.955, "V U L C A N B E N C H", 11, "bold")
    txt(0.163, 0.955, f"T E C H N I C A L   R E P O R T   {NUMBER}", 11, color=GREY)
    txt(
        0.955,
        0.955,
        f"S E P T E M B E R   2 0 2 6   ·   2 3   T A S K S   ·   1   M O D E L   ·   "
        f"2 3   R U N S   ·   X H I G H   E F F O R T   ·   {total_h:.1f}  H   ·   "
        f"$ {total_cost:.0f}",
        9,
        color=GREY,
        ha="right",
    )
    rule(0.936, lw=1.6)
    rule(0.9315, lw=0.7)

    # --- title ------------------------------------------------------------
    fig.text(
        0.5,
        0.885,
        "Claude Fable 5.1",
        fontsize=25,
        fontweight="bold",
        color=INK,
        ha="center",
        va="center",
        fontfamily=SERIF,
    )
    fig.text(
        0.5,
        0.845,
        "C O D I N G   I N T E L L I G E N C E   I N D E X   v 4   ·   "
        "2 3   L E G A C Y   B I N A R I E S   ·   X H I G H   E F F O R T",
        fontsize=9,
        color=GREY,
        ha="center",
        va="center",
        fontfamily=SERIF,
    )

    # --- headline figures -------------------------------------------------
    rule(0.812, lw=0.7)
    kpis = [
        (f"{full * 100:.1f}%", f"pass@1  ±{err * 100:.1f}", "n = 23"),
        (f"{len(solved)}/23", "solved", "1 attempt each"),
        (f"{med_time_all:.1f}", "median min / task", "10 h timeout"),
        (f"${med_cost_all:.2f}", "median $ / task", "api-equivalent"),
    ]
    for i, (big, label, sub) in enumerate(kpis):
        x = 0.125 + i * 0.25
        fig.text(
            x,
            0.766,
            big,
            fontsize=23,
            fontweight="bold",
            color=INK,
            ha="center",
            va="center",
            fontfamily=SERIF,
        )
        fig.text(
            x,
            0.727,
            label,
            fontsize=9.5,
            fontstyle="italic",
            color=INK,
            ha="center",
            va="center",
            fontfamily=SERIF,
        )
        fig.text(
            x,
            0.702,
            sub,
            fontsize=8.5,
            color=GREY,
            ha="center",
            va="center",
            fontfamily=SERIF,
        )
        if i:
            fig.add_artist(
                plt.Line2D(
                    [x - 0.125, x - 0.125],
                    [0.694, 0.795],
                    lw=0.7,
                    color=GREY,
                    transform=fig.transFigure,
                )
            )
    rule(0.678, lw=0.7)

    # --- TABLE 1 ----------------------------------------------------------
    txt(0.045, 0.640, "T A B L E   1 .", 9, "bold")
    txt(0.108, 0.640, "pass@1 by wall-clock budget, xhigh effort", 9, style="italic")

    cols = [
        (0.045, "Time budget", "left"),
        (0.190, "pass@1", "right"),
        (0.258, "Solved", "right"),
        (0.345, "Tokens/task", "right"),
        (0.425, "Time/task", "right"),
        (0.500, "$/task", "right"),
    ]
    ty = 0.592
    rule(ty + 0.020, 0.045, 0.500)
    for x, label, ha in cols:
        txt(x, ty, label, 9.5, "bold", ha=ha)
    rule(ty - 0.016, 0.045, 0.500, lw=0.7)

    def within(cutoff, idx):
        vals = [r[idx] for r in runs if cutoff is None or r[2] <= cutoff]
        return statistics.median(vals) if vals else None

    rows = [
        ("within 10 min", w10, sum(1 for r in solved if r[2] <= 10), 10),
        ("within 30 min", w30, sum(1 for r in solved if r[2] <= 30), 30),
        ("full budget (10 h)", full, len(solved), None),
    ]
    for i, (label, rate, ns, cut) in enumerate(rows):
        y = ty - 0.050 - i * 0.040
        last = i == len(rows) - 1
        if last:
            fig.patches.append(
                plt.Rectangle(
                    (0.045, y - 0.017),
                    0.455,
                    0.034,
                    transform=fig.transFigure,
                    facecolor=BAND,
                    edgecolor="none",
                    zorder=0,
                )
            )
        w = "bold" if last else "normal"
        st = "normal" if last else "italic"
        txt(0.045, y, label, 9.5, w, st)
        txt(0.190, y, f"{rate * 100:.1f}%", 9.5, w, ha="right")
        txt(0.258, y, f"{ns}/23", 9.5, w, ha="right")
        txt(0.345, y, f"{within(cut, 2 + 1) / 1000:.0f} K", 9.5, w, ha="right")
        txt(0.425, y, f"{within(cut, 2):.1f} min", 9.5, w, ha="right")
        txt(0.500, y, f"${within(cut, 5):.2f}", 9.5, w, ha="right")
    last_row_y = ty - 0.050 - (len(rows) - 1) * 0.040
    rule(last_row_y - 0.019, 0.045, 0.500)
    txt(
        0.045,
        last_row_y - 0.048,
        f"$\\bf{{1.}}$  1 attempt / task  ·  pass@1 ±{err * 100:.1f} pts  ·  "
        f"medians, not means  ·  budgets re-read from recorded durations",
        8.5,
        color=GREY,
    )

    # --- TABLE 2 ----------------------------------------------------------
    txt(0.045, 0.352, "T A B L E   2 .", 9, "bold")
    txt(0.108, 0.352, "Unsolved tasks, all wave-11 engines", 9, style="italic")
    t2 = [
        (0.045, "Task", "left"),
        (0.190, "Score", "right"),
        (0.258, "Time", "right"),
        (0.310, "Families missed", "left"),
    ]
    ty2 = 0.306
    rule(ty2 + 0.019, 0.045, 0.500)
    for x, label, ha in t2:
        txt(x, ty2, label, 9.5, "bold", ha=ha)
    rule(ty2 - 0.015, 0.045, 0.500, lw=0.7)
    for i, (name, score, dur, _tok, missed, _cost) in enumerate(unsolved):
        y = ty2 - 0.045 - i * 0.034
        txt(0.045, y, name, 9.5, style="italic")
        txt(0.190, y, f"{score:.3f}", 9.5, ha="right")
        txt(0.258, y, f"{dur:.0f} min", 9.5, ha="right")
        txt(0.310, y, ", ".join(missed), 9.5, color=GREY)
    rule(ty2 - 0.045 - (len(unsolved) - 1) * 0.034 - 0.017, 0.045, 0.500)

    # --- FIGURE 1: four panels -------------------------------------------
    txt(0.560, 0.640, "F I G U R E   1 .", 9, "bold")
    txt(0.629, 0.640, "23 runs, one per task, at xhigh effort", 9, style="italic")

    def caption(x, title, units, y_title):
        fig.text(
            x,
            y_title,
            title,
            fontsize=10,
            fontstyle="italic",
            color=INK,
            ha="center",
            fontfamily=SERIF,
        )
        fig.text(
            x,
            y_title - 0.028,
            units,
            fontsize=8.5,
            color=GREY,
            ha="center",
            fontfamily=SERIF,
        )

    # A. accuracy against the clock
    axa = fig.add_axes([0.560, 0.440, 0.170, 0.155])
    axa.set_facecolor(PAPER)
    vals = [w10, w30, full]
    axa.bar(
        [0, 1, 2],
        [v * 100 for v in vals],
        0.62,
        color=[PALE, MID, NAVY],
        zorder=3,
        yerr=[0, 0, err * 100],
        error_kw={"ecolor": INK, "elinewidth": 1.1, "capsize": 4, "zorder": 4},
    )
    tops = [w10 * 100 + 4, w30 * 100 + 4, (full + err) * 100 + 5]
    for x, v, top in zip([0, 1, 2], vals, tops, strict=True):
        axa.text(
            x,
            top,
            f"{v * 100:.1f}",
            ha="center",
            fontsize=9.5,
            fontfamily=SERIF,
            color=INK,
        )
    axa.set_xticks([0, 1, 2])
    axa.set_xticklabels(["10 min", "30 min", "full"])
    axa.set_ylim(0, 108)
    axa.set_yticks([0, 50, 100])
    dress(axa)
    caption(0.645, "Accuracy vs. budget", "pass@1 (%), n = 23", 0.402)

    # B. cumulative tasks solved against wall clock
    axb = fig.add_axes([0.785, 0.440, 0.170, 0.155])
    axb.set_facecolor(PAPER)
    times = sorted(r[2] for r in solved)
    xs, ys = [0.0], [0]
    for i, t in enumerate(times, start=1):
        xs += [t, t]
        ys += [i - 1, i]
    xs.append(240)
    ys.append(len(times))
    axb.step(xs, ys, where="post", color=NAVY, lw=1.6, zorder=3)
    axb.fill_between(xs, ys, step="post", color=NAVY, alpha=0.10, zorder=2)
    for cut, col, lab_y in ((10, PALE, 22.0), (30, MID, 13.5)):
        axb.axvline(cut, color=col, lw=1.0, ls=(0, (3, 2)), zorder=1)
        axb.text(
            cut + 4,
            lab_y,
            f"{cut} min",
            fontsize=8,
            color=GREY,
            rotation=90,
            va="top",
            fontfamily=SERIF,
            fontstyle="italic",
        )
    axb.set_xlim(0, 240)
    axb.set_ylim(0, 23)
    axb.set_xticks([0, 60, 120, 180, 240])
    axb.set_yticks([0, 10, 19])
    dress(axb)
    caption(0.870, "Tasks solved over time", "cumulative solved of 23, minutes", 0.402)

    # C. cost of failure, wall clock
    axc = fig.add_axes([0.560, 0.190, 0.170, 0.135])
    axc.set_facecolor(PAPER)
    axc.bar([0, 1], [med_solved, med_unsolved], 0.62, color=[MID, NAVY], zorder=3)
    for x, v in zip([0, 1], [med_solved, med_unsolved], strict=True):
        axc.text(x, v + 6, f"{v:.0f}", ha="center", fontsize=9.5, fontfamily=SERIF, color=INK)
    axc.set_xticks([0, 1])
    axc.set_xticklabels([f"solved (n={len(solved)})", f"unsolved (n={len(unsolved)})"])
    axc.set_ylim(0, med_unsolved * 1.30)
    axc.set_yticks([0, 75, 150])
    dress(axc)
    caption(0.645, "Cost of failure: time", "median minutes per run", 0.152)

    # D. cost of failure, tokens
    axd = fig.add_axes([0.785, 0.190, 0.170, 0.135])
    axd.set_facecolor(PAPER)
    toks = [med_tok_solved / 1e6, med_tok_unsolved / 1e6]
    axd.bar([0, 1], toks, 0.62, color=[MID, NAVY], zorder=3)
    for x, v, lab in zip(
        [0, 1],
        toks,
        [f"{med_tok_solved / 1e3:.0f} K", f"{med_tok_unsolved / 1e6:.1f} M"],
        strict=True,
    ):
        axd.text(x, v + 0.30, lab, ha="center", fontsize=9.5, fontfamily=SERIF, color=INK)
    axd.set_xticks([0, 1])
    axd.set_xticklabels([f"solved (n={len(solved)})", f"unsolved (n={len(unsolved)})"])
    axd.set_ylim(0, toks[1] * 1.30)
    axd.set_yticks([0, 4, 8])
    dress(axd)
    caption(0.870, "Cost of failure: tokens", "median tokens per run (M)", 0.152)

    txt(
        0.560,
        0.104,
        "All panels zero-based  ·  accuracy carries ±1 stderr  ·  "
        "time slices re-read the same 23 runs",
        8.5,
        style="italic",
        color=GREY,
    )

    # --- method strip -----------------------------------------------------
    rule(0.092)
    fields = [
        ("SUITE", "Coding Intelligence Index v4, 23 tasks"),
        ("TASK", "stripped binary + drifted spec, hidden tests"),
        ("GRADING", "byte parity over generated corpora"),
        ("HARNESS", "Claude Code CLI, Claude Max subscription"),
        ("EXECUTION", "host, one Apple Silicon machine, 10 h timeout"),
        ("ATTEMPTS", "1 per task, judges disabled"),
        ("EFFORT", "xhigh (Claude Code default); low/med/high/max pending"),
        ("ADMISSION", "weaker ref \u2264 1 solve in 3, stronger \u2265 10 min or miss"),
        ("COST", "list price \\$10 / \\$50 per M, upper bound"),
    ]
    xs_field = [0.045, 0.355, 0.665]
    for i, (key, val) in enumerate(fields):
        col, row = i // 3, i % 3
        x = xs_field[col]
        y = 0.070 - row * 0.020
        txt(x, y, key, 7.6, "bold", color=GREY)
        txt(x + 0.062, y, val, 8.0)
    txt(
        0.955,
        0.006,
        f"V U L C A N B E N C H   ·   O P E N   S O U R C E   ·   {DATE}",
        8.5,
        color=GREY,
        ha="right",
    )

    fig.savefig(OUT, facecolor=PAPER)
    print(f"{len(data)}/23 tasks, {n} runs, pass@1 {full:.4f} +/- {err:.4f}")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
