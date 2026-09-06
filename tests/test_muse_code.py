import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from harness.agent.cli_agents import _subscription_env, get_cli_agent_adapter
from harness.agent.muse_code import (
    MuseCodeAdapter,
    boundary_profile,
    collect_usage,
    pinned_executable,
)
from harness.agent.providers import ProviderError
from harness.effort import effort_config


def test_muse_efforts_and_subscription_env(monkeypatch):
    monkeypatch.setenv("META_API_KEY", "must-not-leak")
    assert "META_API_KEY" not in _subscription_env()
    assert get_cli_agent_adapter("muse-code:muse-spark-1.3").harness_id == "muse-code"
    for effort, sent in [
        ("minimal", "minimal"),
        ("low", "low"),
        ("medium", "medium"),
        ("high", "high"),
        ("extra-high", "xhigh"),
        ("max", "max"),
        ("ultra", "ultra"),
    ]:
        config = effort_config("muse-code", effort)
        assert config.supported and config.provider_value == sent


def test_usage_deduplicates_mirrors_not_children(tmp_path):
    def event(record_id, kind="model_completed", model="muse-spark-1.3"):
        return {
            "id": record_id,
            "payload": {
                "run_id": "parent",
                "source_run_record_id": record_id,
                "event": {
                    "kind": kind,
                    "model": model,
                    "usage": {
                        "input_tokens": 100,
                        "output_tokens": 20,
                        "cached_tokens": 30,
                        "reasoning_tokens": 5,
                    },
                },
            },
        }

    main = tmp_path / "main.jsonl"
    child = tmp_path / "child.jsonl"
    main.write_text(
        "\n".join(json.dumps(r) for r in [event("a"), event("b", "goal_usage_attribution")])
    )
    child.write_text("\n".join(json.dumps(r) for r in [event("a"), event("c")]))
    assert collect_usage([main, child], "muse-spark-1.3") == {
        "input_tokens": 200,
        "output_tokens": 40,
        "cached_tokens": 60,
        "reasoning_tokens": 10,
        "calls": 2,
    }
    child.write_text(json.dumps(event("c", model="muse-spark-1.3-contributor")))
    with pytest.raises(ProviderError, match="mismatch"):
        collect_usage([main, child], "muse-spark-1.3")


def receipt(run="parent", record="1", tokens=100):
    return {
        "id": record,
        "payload": {
            "run_id": run,
            "source_run_record_id": record,
            "event": {
                "kind": "model_completed",
                "model": "muse-spark-1.3-contributor",
                "usage": {
                    "input_tokens": tokens,
                    "output_tokens": 20,
                    "cached_tokens": 30,
                    "reasoning_tokens": 5,
                },
            },
        },
    }


def test_record_id_collisions_across_child_runs_and_mirrors(tmp_path):
    first, second = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    first.write_text(json.dumps(receipt()) + "\n" + json.dumps(receipt("child", tokens=200)))
    second.write_text(json.dumps(receipt("child", tokens=200)))
    expected = dict(
        input_tokens=300, output_tokens=40, cached_tokens=60, reasoning_tokens=10, calls=2
    )
    for paths in ([first, second], [second, first]):
        assert collect_usage(paths, "muse-spark-1.3-contributor") == expected
    second.write_text(json.dumps(receipt("child", tokens=201)))
    with pytest.raises(ProviderError, match="Conflicting"):
        collect_usage([first, second], "muse-spark-1.3-contributor")


def test_ambiguous_run_identity_rejected(tmp_path):
    row = receipt()
    del row["payload"]["run_id"]
    path = tmp_path / "session.jsonl"
    path.write_text(json.dumps(row))
    with pytest.raises(ProviderError, match="run identity"):
        collect_usage([path], "muse-spark-1.3-contributor")


def test_contributor_max_rejected_before_any_process():
    with pytest.raises(ProviderError, match="Standard-only"):
        MuseCodeAdapter().run_task(
            workspace="unused",
            prompt="unused",
            model="muse-spark-1.3-contributor",
            priced_spec="unused",
            max_turns=1,
            collector=None,
            effort="max",
            timeout_s=1,
        )


@pytest.mark.parametrize("value", [-1, 1.5, "100", True, None])
def test_invalid_receipts_fail_closed(tmp_path, value):
    row = receipt()
    row["payload"]["event"]["usage"]["input_tokens"] = value
    path = tmp_path / "session.jsonl"
    path.write_text(json.dumps(row))
    with pytest.raises(ProviderError, match="token count"):
        collect_usage([path], "muse-spark-1.3-contributor")


def test_retained_receipt_and_plain_mirror_count_once(tmp_path):
    path = tmp_path / "session.jsonl"
    path.write_text(
        json.dumps(
            {
                "retained_frame": "session_permission_transaction",
                "children": [{"record_json": json.dumps(receipt())}],
            }
        )
        + "\n"
        + json.dumps(receipt())
    )
    assert collect_usage([path], "muse-spark-1.3-contributor")["calls"] == 1


def test_pin_required_and_rechecked(tmp_path, monkeypatch):
    binary = tmp_path / "muse-bin-test"
    binary.write_bytes(b"fake binary, never executed")
    binary.chmod(0o700)
    monkeypatch.setenv("VULCANBENCH_MUSE_BINARY", str(binary))
    monkeypatch.setenv("VULCANBENCH_MUSE_SHA256", hashlib.sha256(binary.read_bytes()).hexdigest())
    assert pinned_executable()[0] == binary.resolve()
    binary.write_bytes(b"changed")
    with pytest.raises(ProviderError, match="SHA256 mismatch"):
        pinned_executable()
    binary.write_bytes(b"#!/bin/sh\nexit 0\n")
    with pytest.raises(ProviderError, match="launcher"):
        pinned_executable()


def test_preflight_reports_missing_pin_without_running_launcher(monkeypatch):

    monkeypatch.delenv("VULCANBENCH_MUSE_BINARY", raising=False)
    checked = MuseCodeAdapter().preflight()
    assert not checked.ready and "VULCANBENCH_MUSE_BINARY" in checked.detail


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS kernel sandbox")
def test_real_sandbox_scratch_and_stale_temp_isolation(tmp_path):
    workspace, scratch = tmp_path / "workspace", tmp_path / "scratch"
    workspace.mkdir()
    scratch.mkdir()
    (scratch / "tmp").mkdir()
    profile = tmp_path / "test.sb"
    profile.write_text(boundary_profile(workspace, scratch))
    with tempfile.TemporaryDirectory(prefix="vb-muse-canary-", dir="/private/tmp") as other:
        stale = Path(other) / "stale.txt"
        stale.write_text("synthetic isolation canary")
        sibling = tmp_path / "other-run.txt"
        sibling.write_text("another synthetic canary")
        (workspace / "stale-link").symlink_to(stale)
        (workspace / "outside-link").symlink_to(sibling)
        # No provider call. Exercise real subprocesses, compiler and temp tools.
        code = """
set -eu
printf valid > "$TMPDIR/probe.txt"
test "$(cat "$TMPDIR/probe.txt")" = valid
mktemp "$TMPDIR/probe.XXXXXX" > scratch-name.txt
printf 'int main(void) { return 0; }' > main.c
clang main.c -o main
./main
if cat stale-link >/dev/null 2>&1; then exit 71; fi
if cat outside-link >/dev/null 2>&1; then exit 72; fi
if printf bad > outside-link 2>/dev/null; then exit 73; fi
if cat "$VB_PROTECTED_REPO/README.md" >/dev/null 2>&1; then exit 74; fi
"""
        proc = subprocess.run(
            ["/usr/bin/sandbox-exec", "-f", str(profile), "/bin/sh", "-c", code],
            cwd=workspace,
            env={
                **_subscription_env(),
                "TMPDIR": str((scratch / "tmp").resolve()),
                "VB_PROTECTED_REPO": str(Path(__file__).resolve().parents[1]),
            },
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr
        assert sibling.read_text() == "another synthetic canary"
        assert Path((workspace / "scratch-name.txt").read_text().strip()).is_relative_to(
            scratch.resolve()
        )
