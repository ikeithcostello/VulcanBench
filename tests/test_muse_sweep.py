"""Regression coverage for the Muse launchd grading/reporting fixes."""

import importlib.util
import json
from pathlib import Path

import pytest

from harness.verifier import RunnerOutcome, _infrastructure_reason

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "muse_sweep", ROOT / "scripts/cii-v4-board/run_muse_sweep.py"
)
sweep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sweep)


def test_env_prefixed_missing_python_is_infrastructure():
    assert _infrastructure_reason(
        "PYTHONPATH=. python -m pytest t.py",
        RunnerOutcome(127, stderr="/bin/sh: python: command not found"),
    )
    assert (
        _infrastructure_reason(
            "PYTHONPATH=. python -m pytest t.py",
            RunnerOutcome(1, stdout="AssertionError: mismatch"),
        )
        is None
    )


def test_envelope_and_idempotent_reporting(tmp_path, monkeypatch):
    monkeypatch.setattr(sweep, "OUT", tmp_path)
    summary = {
        "run_id": "run-1",
        "task_id": "task-1",
        "scores": {"functional": 0.4, "quality": 0.7835, "security": 1},
        "total_tokens": 123,
        "duration_s": 12,
    }
    assert sweep.result_summary({"run_id": "run-1", "summary": summary}) is summary
    sweep.record_result(summary, "minimal")
    sweep.record_result(summary, "minimal")
    rows = [json.loads(line) for line in (tmp_path / "results.jsonl").read_text().splitlines()]
    assert len(rows) == 1 and rows[0]["functional"] == 0.4
    summary["scores"]["quality"] = None
    with pytest.raises(AssertionError, match="Missing quality"):
        sweep.result_summary({"run_id": "run-1", "summary": summary})


def test_grader_preflight_repairs_sparse_launchd_path(monkeypatch):
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    sweep.grader_preflight()


def test_contributor_run_separate_and_protocol_immutable(tmp_path):
    assert sweep.MODEL == "muse-code:muse-spark-1.3-contributor"
    assert sweep.OUT.name != "runs-muse13-cii-v4"
    path = tmp_path / "protocol.json"
    original = {"model": sweep.MODEL, "hash": "first"}
    sweep.save_protocol(path, original)
    sweep.save_protocol(path, original)
    with pytest.raises(AssertionError, match="Protocol changed"):
        sweep.save_protocol(path, {**original, "hash": "changed"})
    assert json.loads(path.read_text()) == original
