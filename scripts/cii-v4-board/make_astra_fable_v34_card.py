"""Astra versus Fable 5.1 card under the code-quality-maintenance-v3.4 protocol.

Reads the frozen v3.4 summary (neutral panel: Muse Spark 1.3 and Grok 4.6)
and the private manifest (functional, automated quality, security, runtime per
run). Combined score uses the locked profile: 50% functional, 8.5% automated
quality, 8.5% security, 33% Code quality. Until the measured-maintenance layer
exists, Code quality is 24 points reviewed panel plus 9 points intent recovery,
as the protocol pre-registers.

Coverage rules, applied by the script, not by hand:
- FINAL card: every submission has both panels' reviews and probes. Filename
  has no suffix.
- PRELIMINARY card: anything less. Rows use whatever layers both panels have
  completed (reviewed layer only where probes are missing), the headline strip
  says PRELIMINARY with coverage counts, and the filename carries the suffix.
No takeaway is hard-coded; the headline is computed from the data each run.
"""
from __future__ import annotations

import csv
import json
import math
import statistics
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from harness.evaluator.reviewed_score import WEIGHTS_V3  # noqa: E402
from harness.retrospective_judging import LEVELS, digest, save  # noqa: E402

RUN = ROOT / "runs-code-quality-maintenance-v3.4"
OUTPUT = ROOT / "docs/results/swe-v4-astra-fable51-2026-09"
PAPER, INK, RULE, MUTED = "#f7f5f0", "#171917", "#c6c5bc", "#6b6b66"
COLORS = {"astra": "#10A37F", "fable": "#D97757"}
NAMES = {"astra": "GPT-6 Astra", "fable": "Fable 5.1 with fallbacks*"}
HARNESS = {"astra": "Codex", "fable": "Claude Code"}
PANELS = ("muse", "grok")
PANEL_NAMES = {"muse": "Muse Spark 1.3 (Meta)", "grok": "Grok 4.6 (xAI)"}
SPLIT_WITHOUT_L3 = {"l1": 0.24, "l2": 0.09}


def require(condition, message):
    if not condition:
        raise SystemExit(f"Card refused: {message}")


def mean_se(values):
    values = list(values)
    if not values:
        return {"n": 0, "mean": None, "se": None}
    return {"n": len(values), "mean": statistics.mean(values),
            "se": statistics.stdev(values) / math.sqrt(len(values)) if len(values) > 1 else 0.0}


def code_quality(row):
    """Per-row Code quality on 0 to 100 from both neutral panels, and which layers it used."""
    panels = [row["panels"][p] for p in PANELS]
    if any(p["l1"] is None for p in panels):
        return None, None
    l1 = statistics.mean(p["l1"]["score"] for p in panels)
    l2_values = [p["l2"] for p in panels if p["l2"] is not None]
    probes_complete = all(p["l2"] is not None or p["l2_denominator"] == 0 for p in panels)
    if probes_complete and l2_values:
        return (SPLIT_WITHOUT_L3["l1"] * l1 + SPLIT_WITHOUT_L3["l2"] * statistics.mean(l2_values)) / WEIGHTS_V3["human_like"], "l1+l2"
    if probes_complete:
        return l1, "l1 (no scored quirks)"
    return l1, "l1 only"


def composite(run, quality, weight):
    other = (0.5 - weight) / 2
    return 100 * (.5 * run["functional"] + other * run["quality"] + other * run["security"] + weight * quality / 100)


def load():
    summary = json.loads((RUN / "summary.json").read_text())
    manifest = {r["id"]: r for r in json.loads((RUN / "private-manifest.json").read_text())}
    protocol = json.loads((RUN / "protocol.json").read_text())
    require(summary["protocol"] == "code-quality-maintenance-v3.4", "wrong protocol")
    require(set(summary["passing_panels"]) == set(PANELS), f"passing panels {summary['passing_panels']}")
    require(protocol["weights"]["functional"] == WEIGHTS_V3["functional"]
            and protocol["weights"]["code_quality"]["total"] == WEIGHTS_V3["human_like"], "weights drift")
    rows = []
    for entry in summary["rows"]:
        run = manifest[entry["id"]]
        cq, layers = code_quality(entry)
        if cq is None:
            continue
        rows.append({
            "id": entry["id"], "model": entry["model"], "effort": entry["effort"], "task": entry["task"],
            "fallback": bool(run.get("fallback")), "functional": run["functional"], "minutes": run["duration_s"] / 60,
            "code_quality": cq, "layers": layers,
            "readability": statistics.mean(entry["panels"][p]["l1"]["readability"] for p in PANELS),
            "maintainability": statistics.mean(entry["panels"][p]["l1"]["maintainability"] for p in PANELS),
            "by_panel": {p: entry["panels"][p]["l1"]["score"] for p in PANELS},
            # Intent recovery is shown only once it is scored, i.e. both panels' probes are complete for the row.
            "l2": statistics.mean([entry["panels"][p]["l2"] for p in PANELS if entry["panels"][p]["l2"] is not None])
            if layers == "l1+l2" else None,
            "combined_v3": composite(run, cq, WEIGHTS_V3["human_like"]),
            "combined_20pct": composite(run, cq, 0.20),
        })
    total = len(summary["rows"])
    final = len(rows) == total and all(r["layers"] != "l1 only" for r in rows)
    coverage = {"submissions_with_both_reviews": len(rows), "submissions_total": total,
                "submissions_with_probes": sum(r["layers"] != "l1 only" for r in rows),
                "per_panel_reviews": {p: sum(1 for e in summary["rows"] if e["panels"][p]["l1"]) for p in PANELS},
                "per_panel_probes": {p: sum(1 for e in summary["rows"] if e["panels"][p]["l2"] is not None) for p in PANELS}}
    return summary, protocol, rows, final, coverage


def aggregate(rows):
    groups = {}
    for model in COLORS:
        for effort in LEVELS:
            rs = [r for r in rows if r["model"] == model and r["effort"] == effort]
            groups[model, effort] = {
                "model": model, "effort": effort, "n": len(rs),
                "combined": mean_se(r["combined_v3"] for r in rs), "combined_20pct": mean_se(r["combined_20pct"] for r in rs),
                "code_quality": mean_se(r["code_quality"] for r in rs), "readability": mean_se(r["readability"] for r in rs),
                "maintainability": mean_se(r["maintainability"] for r in rs),
                "l2": mean_se(r["l2"] for r in rs if r["l2"] is not None),
                "by_panel": {p: mean_se(r["by_panel"][p] for r in rs) for p in PANELS},
                "minutes": mean_se(r["minutes"] for r in rs), "passed": sum(r["functional"] == 1 for r in rs),
                "fallbacks": sum(r["fallback"] for r in rs),
            }
    return groups


def fmt(stat, digits=2):
    return "n/a" if stat["mean"] is None else f"{stat['mean']:.{digits}f}"


def main():  # noqa: PLR0915, one linear figure
    summary, protocol, rows, final, coverage = load()
    groups = aggregate(rows)
    complete_efforts = [e for e in LEVELS if all(groups[m, e]["n"] > 0 for m in COLORS)]
    require(complete_efforts, "no effort has rows for both models yet")
    best = {m: max((groups[m, e] for e in complete_efforts), key=lambda g: g["combined"]["mean"]) for m in COLORS}
    wins = {"combined": 0, "code_quality": 0, "runtime": 0}
    for e in complete_efforts:
        a, f = groups["astra", e], groups["fable", e]
        wins["combined"] += a["combined"]["mean"] > f["combined"]["mean"]
        wins["code_quality"] += a["code_quality"]["mean"] > f["code_quality"]["mean"]
        wins["runtime"] += a["minutes"]["mean"] < f["minutes"]["mean"]
    leader = max(COLORS, key=lambda m: best[m]["combined"]["mean"])
    other = "fable" if leader == "astra" else "astra"
    gap = best[leader]["combined"]["mean"] - best[other]["combined"]["mean"]
    cq_leader = max(COLORS, key=lambda m: best[m]["code_quality"]["mean"])
    faster = min(COLORS, key=lambda m: best[m]["minutes"]["mean"])
    ratio = max(best[m]["minutes"]["mean"] for m in COLORS) / max(1e-9, min(best[m]["minutes"]["mean"] for m in COLORS))
    short = {"astra": "Astra", "fable": "Fable"}
    if abs(gap) < 1:
        headline = f"Similar scores. {short[cq_leader]} writes more maintainable code."
    else:
        headline = f"{short[leader]} leads by {gap:.1f} points at 33% Code quality."
    sub = f"{short[leader]}'s best score is +{gap:.2f} points; {short[faster]} is {ratio:.2f}× faster."  # noqa: RUF001

    for font in (ROOT / "scripts/rankings-chart").glob("*.ttf"):
        font_manager.fontManager.addfont(font)
    plt.rcParams.update({"font.family": "Geist", "text.color": INK, "svg.fonttype": "path"})
    fig = plt.figure(figsize=(16, 12), dpi=150, facecolor=PAPER)

    def text(x, y, label, size=16, bold=False, heading=False, numeric=False, ha="left", color=INK):
        family = "IBM Plex Mono" if numeric else (
            "Chakra Petch SemiBold" if bold else "Chakra Petch Medium") if heading else "Geist"
        weight = (500 if bold else 400) if numeric else ((600 if bold else 500) if heading else (700 if bold else 400))
        return fig.text(x, y, label, fontsize=size, fontfamily=family, weight=weight, ha=ha, va="center", color=color)

    def line(x1, x2, y, color=RULE, width=.8):
        fig.add_artist(plt.Line2D([x1, x2], [y, y], transform=fig.transFigure, color=color, lw=width))

    logo = fig.add_axes([.045, .925, .034, .0453])
    mark = logo.imshow(plt.imread(ROOT / "docs/assets/vulcanbench-logo.png"))
    mark.set_clip_path(FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0,rounding_size=.22", transform=logo.transAxes))
    logo.axis("off")
    text(.09, .948, "VulcanBench", 22, True, heading=True)
    text(.955, .948, "VulcanBench-SWE v4  /  September 2026  /  Code quality protocol v3.4", 14, ha="right")
    line(.045, .955, .907)
    if not final:
        fig.patches.append(FancyBboxPatch((.045, .862), .91, .03, boxstyle="round,pad=0,rounding_size=.004",
                                          transform=fig.transFigure, facecolor="#f1d9a8", edgecolor="none"))
        text(.5, .877, f"PRELIMINARY  ·  {coverage['submissions_with_both_reviews']}/{coverage['submissions_total']} submissions "
                       f"reviewed by both panels  ·  {coverage['submissions_with_probes']} with the intent-recovery layer  ·  "
                       f"not for publication", 13, True, ha="center")
    text(.045, .82, headline, 32, True, heading=True)
    text(.045, .775, sub, 20)
    text(.045, .738, f"Each model's highest-scoring effort among {len(complete_efforts)} effort levels covered for both models.", 14, color=MUTED)

    for model, x in (("astra", .045), ("fable", .535)):
        g = best[model]
        right = x + .42
        line(x, right, .700, COLORS[model], 4)
        text(x, .668, NAMES[model], 23, True, heading=True)
        text(x, .634, f"{g['effort'].capitalize()} effort · {HARNESS[model]} · n={g['n']}", 14)
        text(x, .594, "COMBINED SCORE /100  (50 / 8.5 / 8.5 / 33)", 13, True)
        text(x, .540, fmt(g["combined"]), 46, True, numeric=True)
        text(right, .548, f"{g['passed']}/{g['n']}\nfully passed", 14, ha="right")
        text(right, .513, f"at 20% profile: {fmt(g['combined_20pct'])}", 12, ha="right", color=MUTED)
        ax = fig.add_axes([x, .478, .42, .022], facecolor=PAPER)
        lo = math.floor(min(best[m]["combined"]["mean"] - (best[m]["combined"]["se"] or 0) for m in COLORS)) - 1
        hi = math.ceil(max(best[m]["combined"]["mean"] + (best[m]["combined"]["se"] or 0) for m in COLORS)) + 1
        ax.set_xlim(lo, hi)
        ax.set_ylim(-1, 1)
        ax.set_yticks([])
        ax.spines[["top", "left", "right"]].set_visible(False)
        ax.spines["bottom"].set_color(RULE)
        ax.set_xticks(list(range(lo, hi + 1)))
        ax.tick_params(axis="x", length=0, labelsize=10, pad=4)
        ax.errorbar(g["combined"]["mean"], 0, xerr=g["combined"]["se"] or 0, fmt="o" if model == "astra" else "D",
                    color=COLORS[model], markeredgecolor=INK, markeredgewidth=.7, markersize=8, ecolor=INK, elinewidth=1.5, capsize=5)
        text(x, .430, "CODE QUALITY /100", 13, True)
        text(x, .390, f"{fmt(g['code_quality'])} ± {g['code_quality']['se']:.2f}", 30, True, numeric=True)
        intent = fmt(g["l2"], 1) if g["l2"]["mean"] is not None else "pending"
        text(x, .352, f"Readability {fmt(g['readability'], 1)}  ·  Maintainability {fmt(g['maintainability'], 1)}  ·  "
                      f"Intent recovery {intent}", 13)
        text(x, .325, "  ·  ".join(f"{PANEL_NAMES[p].split(' (')[0]} {fmt(g['by_panel'][p], 1)}" for p in PANELS), 13, color=MUTED)
        text(x, .286, "MEAN RUNTIME / TASK", 13, True)
        text(x, .250, f"{fmt(g['minutes'])} min", 26, True, numeric=True)
        ax = fig.add_axes([x, .212, .42, .020], facecolor=PAPER)
        top = 10 * math.ceil(max(best[m]["minutes"]["mean"] + (best[m]["minutes"]["se"] or 0) for m in COLORS) / 10)
        ax.set_xlim(0, top)
        ax.set_ylim(-1, 1)
        ax.set_yticks([])
        ax.spines[["top", "left", "right"]].set_visible(False)
        ax.spines["bottom"].set_color(RULE)
        ax.set_xticks(list(range(0, top + 1, max(5, top // 4))))
        ax.tick_params(axis="x", length=0, labelsize=10, pad=4)
        ax.barh(0, g["minutes"]["mean"], height=.8, color=COLORS[model], edgecolor=INK, linewidth=.5,
                xerr=g["minutes"]["se"] or 0, error_kw={"ecolor": INK, "elinewidth": 1.5, "capsize": 5})

    line(.045, .955, .172)
    text(.045, .150, f"Across {len(complete_efforts)} matched efforts", 18, True, heading=True)
    text(.045, .121, f"Astra: faster at {wins['runtime']}/{len(complete_efforts)} · higher Code quality at "
                     f"{wins['code_quality']}/{len(complete_efforts)} · higher combined score at {wins['combined']}/{len(complete_efforts)}", 15, True)
    line(.045, .955, .098)
    interventions = summary.get("fallback_reviews", {})
    text(.045, .080, "Weights: 50% functional + 8.5% automated quality + 8.5% security + 33% Code quality "
                     "(24 reviewed + 9 intent recovery until the measured-maintenance layer exists)", 11.5)
    text(.045, .060, "Code quality: equal average of Muse Spark 1.3 (Meta) and Grok 4.6 (xAI), labs with no model on this board; "
                     "both passed a 20-gate calibration exam. LLM judgment, not human validation.", 11.5)
    text(.045, .040, "Whiskers and ±: 1 task SE, not significance. Runtime excludes judging. "
                     f"Reviewer fallbacks: {interventions.get('muse', 0)} Muse, {interventions.get('grok', 0)} Grok. "
                     "*Opus 4.8 fallbacks: 11/115 Fable solver runs.", 11.5)
    text(.045, .020, f"Protocols v3.3 (Grok) and v3.4 (Muse), hashes {protocol['scored_siblings']['grok']['protocol_sha256'][:8]} and "
                     f"{digest((RUN / 'protocol.json').read_bytes())[:8]} · 230 runs · 23 Python replacements for C-built binaries · "
                     "docs/judging/code-quality-maintenance-v3.md", 11.5, color=MUTED)

    suffix = "" if final else "-preliminary"
    out = OUTPUT / f"astra-vs-fable51-v34{suffix}.png"
    fig.savefig(out, facecolor=PAPER)
    fig.savefig(out.with_suffix(".svg"), facecolor=PAPER)
    plt.close(fig)
    table = OUTPUT / f"astra-vs-fable51-v34{suffix}-efforts.csv"
    with table.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["model", "effort", "n", "combined_v3", "combined_v3_se", "combined_20pct", "code_quality", "code_quality_se",
                         "readability", "maintainability", "intent_recovery", "muse_l1", "grok_l1", "minutes", "passed", "fallbacks"])
        for (model, effort), g in groups.items():
            writer.writerow([model, effort, g["n"], fmt(g["combined"], 4), fmt({"mean": g["combined"]["se"]}, 4), fmt(g["combined_20pct"], 4),
                             fmt(g["code_quality"], 4), fmt({"mean": g["code_quality"]["se"]}, 4), fmt(g["readability"], 4),
                             fmt(g["maintainability"], 4), fmt(g["l2"], 4), fmt(g["by_panel"]["muse"], 4), fmt(g["by_panel"]["grok"], 4),
                             fmt(g["minutes"], 4), g["passed"], g["fallbacks"]])
    save(out.with_suffix(".json"), {
        "final": final, "coverage": coverage, "headline": headline, "subtitle": sub,
        "selected": {m: {k: v for k, v in best[m].items() if k != "by_panel"} | {"by_panel": best[m]["by_panel"]} for m in COLORS},
        "matched_effort_leads_astra": wins, "complete_efforts": complete_efforts,
        "weights": {"functional": 0.5, "quality": 0.085, "security": 0.085, "code_quality": 0.33, "code_quality_split": SPLIT_WITHOUT_L3},
        "summary_sha256": digest((RUN / "summary.json").read_bytes()), "protocol_sha256": digest((RUN / "protocol.json").read_bytes()),
        "png_sha256": digest(out.read_bytes()), "supporting_table": table.name,
        "visual_qa": "Requires visual inspection after rendering",
    })
    print(out)


if __name__ == "__main__":
    main()
