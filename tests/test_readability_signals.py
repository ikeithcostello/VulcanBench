from pathlib import Path

from harness.evaluator.readability_signals import analyze_files, analyze_source

CONTROLS = Path(__file__).resolve().parents[1] / "docs" / "judging" / "controls-v3"


def control(n):
    return analyze_source(next(CONTROLS.glob(f"control-{n}-*.py")).read_text())


def test_compressed_control_packs_statements_and_short_names():
    clear, compressed, formatted = control(0), control(1), control(2)
    assert compressed["statements_per_code_line"] > 1.3 > clear["statements_per_code_line"]
    assert compressed["max_statements_on_one_line"] >= 3
    assert compressed["short_name_fraction"] > 0.5 > clear["short_name_fraction"]
    assert compressed["magic_literals"] > clear["magic_literals"]
    # Formatting removes packing but keeps the naming and literal problems.
    assert formatted["statements_per_code_line"] == 1.0
    assert formatted["short_name_fraction"] == compressed["short_name_fraction"]
    assert formatted["magic_literals"] == compressed["magic_literals"]


def test_narration_duplication_and_global_state_are_visible():
    assert control(6)["comment_line_fraction"] > 0.5 > control(0)["comment_line_fraction"]
    assert control(3)["magic_literals"] > control(0)["magic_literals"] * 2
    assert control(3)["max_nesting_depth"] > control(0)["max_nesting_depth"]
    assert control(9)["module_mutable_state"] == 3 and control(0)["module_mutable_state"] == 0


def test_named_constants_are_not_magic():
    assert analyze_source("LIMIT = 500\nx = LIMIT + 3\n")["magic_literals"] == 1
    assert analyze_source("x = 0 + 1 + 2 - 1\n")["magic_literals"] == 0


def test_syntax_errors_are_reported_not_raised(tmp_path):
    bad = tmp_path / "bad.py"
    bad.write_text("def (:\n")
    assert "syntax error" in analyze_files([bad])[str(bad)]["error"]


def test_unknown_metric_is_finite_on_empty_module():
    signals = analyze_source("")
    assert signals["statements"] == 0 and signals["short_name_fraction"] == 0.0
