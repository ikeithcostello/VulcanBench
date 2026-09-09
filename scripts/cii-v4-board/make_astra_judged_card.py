"""Reproducible revised Astra card, preserving the original unjudged card.

Chart contract: compare five efforts on 23 matched tasks each, September 2026.
Exact lookup table for functional results, resources, and retrospective review.
Comparison bars: combined task means, zero baseline, task-level sample SE.
Single OpenAI green root, direct labels; static PNG, inspected after rendering.
Explicit revised profile excludes efficiency and keeps legacy scores unchanged.
"""
import json
import argparse
import math
import statistics
import sys
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from harness.evaluator.reviewed_score import PROFILE, WEIGHTS, reviewed_score
OUT = ROOT / "docs/results/cii-v4-astra-2026-09/report23-gpt6-astra-vulcanbench-swe-v4-combined.png"
LEVELS = ["low", "medium", "high", "extra-high", "max"]
PAPER, INK, GREEN = "#f7f5f0", "#171917", "#10A37F"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--panel", action="store_true")
    args = parser.parse_args()
    out = OUT.with_name("report23-gpt6-astra-vulcanbench-swe-v4-panel.png") if args.panel else OUT
    panel_report = json.loads((ROOT / "runs-astra-cii-v4-claude-judging-v1/verification.json").read_text()) if args.panel else None
    if panel_report:
        assert panel_report["runs"] == 115 and panel_report["valid_votes"] == 345
    for p in (ROOT / "scripts/rankings-chart").glob("*.ttf"):
        font_manager.fontManager.addfont(p)
    plt.rcParams.update({"font.family": "Geist", "text.color": INK})
    judge_root = ROOT / "runs-astra-cii-v4-judging-v2"
    summary = json.loads((judge_root / "summary.json").read_text())
    verification = json.loads((judge_root / "verification.json").read_text())
    assert summary["complete"] and verification["source_hashes_unchanged"]
    rows, all_runs = [], []
    for level in LEVELS:
        judged = [json.loads(p.read_text()) for p in (judge_root / level).glob("*/judging.json")]
        assert len(judged) == 23 and len({r["task_id"] for r in judged}) == 23
        runs = [json.loads((Path(r["source_directory"]) / "summary.json").read_text()) for r in judged]
        assert all(r["status"] == "complete" and len(r["votes"]) == 3 for r in judged)
        values = [r["human_like"] * 100 for r in judged]
        mean = statistics.mean(values)
        claude_mean = None
        if panel_report:
            panel_rows = [r for r in panel_report["rows"] if r["effort"] == level]
            assert {r["run_id"] for r in panel_rows} == {r["run_id"] for r in judged}
            mean = statistics.mean(r["panel"] * 100 for r in panel_rows)
            claude_mean = statistics.mean(r["claude"] * 100 for r in panel_rows)
        combined = [reviewed_score({**run["scores"], "human_like": judge["human_like"]}) * 100
                    for run, judge in zip(runs, judged)]
        if panel_report:
            combined = [r["combined"] * 100 for r in panel_rows]
        else:
            assert abs(mean / 100 - summary["efforts"][level]["mean_human_like"]) < .000051
        rows.append(dict(effort=level.title(), solved=sum(r["scores"]["functional"] == 1 for r in runs),
                         tokens=sum(r["total_tokens"] for r in runs),
                         minutes=statistics.mean(r["duration_s"] for r in runs) / 60,
                         mean=mean, astra=statistics.mean(values), claude=claude_mean, combined=statistics.mean(combined),
                         se=statistics.stdev(combined) / math.sqrt(23)))
        all_runs.extend(runs)
    wall = (max(datetime.fromisoformat(r["finished_at"]) for r in all_runs)
            - min(datetime.fromisoformat(r["started_at"]) for r in all_runs)).total_seconds()
    assert round(wall) == 43232
    assert sum(r["tokens"] for r in rows) == 97043705
    fig = plt.figure(figsize=(18, 11), dpi=150, facecolor=PAPER)

    def text(x, y, s, size=15, bold=False, ha="left", heading=False):
        fig.text(x, y, s, fontsize=size, weight="bold" if bold else "normal",
                 ha=ha, va="center", fontfamily="Chakra Petch" if heading else "Geist", color=INK)

    def rule(y, left=.045, right=.955):
        fig.add_artist(plt.Line2D([left, right], [y, y], transform=fig.transFigure, color=INK, lw=.8))

    logo = fig.add_axes([.045, .919, .033, .054])
    logo.imshow(plt.imread(ROOT / "docs/assets/vulcanbench-logo.png")); logo.axis("off")
    text(.088, .946, "VULCANBENCH", 22, True, heading=True)
    text(.955, .946, "TECHNICAL REPORT 23  /  SEPTEMBER 5, 2026", 13, ha="right")
    rule(.903)
    text(.045, .857, "GPT-6 Astra, Effort Sweep", 34, True, heading=True)
    text(.045, .811, "VulcanBench-SWE v4  |  23 tasks per effort  |  115 scored solutions", 18)
    text(.045, .758, "Combined scores include 20% human-like review. Task pass counts are reported separately.", 18, True)

    text(.045, .683, "FUNCTIONAL RESULTS AND SOLVER RESOURCES", 16, True, heading=True)
    cols = [(.045, "Effort"), (.205, "Review /100"), (.315, "Passed"), (.399, "Tokens"), (.49, "Min/task")]
    if panel_report:
        cols = [(.045, "Effort"), (.18, "Astra"), (.26, "Claude"), (.35, "Panel"), (.44, "Passed"), (.51, "Tokens")]
    rule(.658, right=.565)
    for x, title in cols: text(x, .633, title, 15, True)
    rule(.61, right=.565)
    for i, r in enumerate(rows):
        y = .573 - i * .047
        vals = [r["effort"], f"{r['mean']:.2f}", f"{r['solved']}/23", f"{r['tokens']/1e6:.2f} M", f"{r['minutes']:.2f}"]
        if panel_report:
            vals = [r["effort"], f"{r['astra']:.2f}", f"{r['claude']:.2f}", f"{r['mean']:.2f}", f"{r['solved']}/23", f"{r['tokens']/1e6:.2f}M"]
        for (x, _), val in zip(cols, vals): text(x, y, val, 16)
    rule(.354, right=.565)
    text(.045, .327, "Low partial: PaddockCore, 14/15 functional families passed.", 13)

    text(.62, .683, "COMBINED BENCHMARK SCORE", 16, True, heading=True)
    text(.62, .652, "Mean /100; whiskers: ±1 SE across 23 tasks", 13)
    ax = fig.add_axes([.68, .371, .264, .245], facecolor=PAPER)
    for i, r in enumerate(rows):
        ax.barh(i, r["combined"], height=.55, color=GREEN, xerr=r["se"],
                error_kw={"ecolor": INK, "capsize": 4, "elinewidth": 1.2})
        ax.text(3, i, f"{r['combined']:.2f} ± {r['se']:.2f}", va="center", fontsize=13, color="#101510", weight="bold")
    ax.set_xlim(0, 100); ax.set_ylim(4.65, -.65)
    ax.set_yticks(range(5), [r["effort"] for r in rows], fontsize=13)
    ax.set_xticks([0, 25, 50, 75, 100]); ax.tick_params(length=0, labelsize=12, pad=8)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.grid(axis="x", color="#d8d7d0", lw=.6); ax.set_axisbelow(True)
    text(.62, .327, "Combined score, not a task pass percentage.", 13, True)

    rule(.292)
    text(.045, .263, "ORIGINAL SOLVER SWEEP", 14, True, heading=True)
    text(.045, .228, "12 h 00 m 32 s", 24, True)
    text(.045, .195, "97.04 M tokens across all five efforts", 15)
    text(.515, .263, "ADDITIONAL RETROSPECTIVE JUDGING", 14, True, heading=True)
    if panel_report:
        total_tokens = 4000039 + panel_report["total_tokens"]
        cost = summary["api_equivalent_estimate_usd"] + panel_report["cli_api_equivalent_estimate_usd"]
        text(.515, .228, f"690 valid ratings  |  {total_tokens/1e6:.2f} M tokens", 23, True)
        text(.515, .195, f"${cost:.2f} API-equivalent estimate, not a cash charge", 15)
    else:
        text(.515, .228, "25 m 54 s  |  4.00 M tokens", 24, True)
        text(.515, .195, f"${summary['api_equivalent_estimate_usd']:.2f} API-equivalent estimate, not a cash charge", 15)
    rule(.165)
    text(.045, .14, "Method: Codex on Apple Silicon; one completed scored run per task/effort. Functional pass@1 uses hidden tests.", 13)
    text(.045, .114, "Review: equal-weight Astra + Claude Opus 5, both Medium; 3 personas each. Review columns use a 0 to 100 scale." if panel_report else "Review: Astra Medium; 3 personas per solution (correctness, readability, maintainability); 345 valid votes, full patches.", 13)
    text(.045, .088, "Retrospective full-patch review; solver labels hidden, test outcomes supplied. Model bias remains possible; no solver reruns.", 13)
    text(.045, .062, "Weights: functional 50%, quality 15%, security 15%, review 20%. Efficiency reported separately; no step score used.", 13, True)
    foot = "Judging estimate: $10 / $1 / $50 per M uncached input / cached input / output tokens; OpenAI API pricing, Sept. 5, 2026."
    if panel_report:
        foot = f"Review time: Astra 25m54s elapsed; Claude {panel_report['claude_active_request_seconds']/60:.1f}m active requests, {panel_report['claude_elapsed_seconds_including_pauses']/3600:.2f}h elapsed incl. pauses. Costs include retries; Claude estimate from CLI."
    text(.045, .031, foot, 11)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, facecolor=PAPER)
    out.with_suffix(".json").write_text(json.dumps({"profile": panel_report["profile"] if panel_report else PROFILE, "weights": WEIGHTS, "rows": rows,
        "source": str(judge_root), "legacy_scores_unchanged": True}, indent=2) + "\n")
    print(out)
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
