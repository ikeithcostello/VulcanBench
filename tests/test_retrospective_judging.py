"""Offline checks for the additive retrospective judging protocol."""

import json

import pytest

import harness.retrospective_judging as retrospective
from harness.retrospective_judging import api_estimate, parse_stream, prompt_for


def stream(score=80, extra=None):
    events = [{"type": "thread.started", "thread_id": "unique"}]
    if extra:
        events.append(extra)
    events.extend(
        [
            {
                "type": "item.completed",
                "item": {
                    "type": "agent_message",
                    "text": json.dumps({"score": score, "rationale": "Clear implementation."}),
                },
            },
            {
                "type": "turn.completed",
                "usage": {"input_tokens": 1000, "cached_input_tokens": 200, "output_tokens": 100},
            },
        ]
    )
    return "\n".join(json.dumps(e) for e in events)


def test_full_patch_and_blinded_labels():
    patch = "+line\n" * 10000 + "END_OF_COMPLETE_PATCH"
    data = {
        "issue": "Fix behavior",
        "patch": patch,
        "summary": {
            "model": "SECRET_MODEL",
            "effort": "SECRET_EFFORT",
            "verifier": {"scores": {"functional": 1}},
        },
    }
    prompt = prompt_for(data, "Review clarity")
    assert "END_OF_COMPLETE_PATCH" in prompt
    assert "SECRET_MODEL" not in prompt
    assert "SECRET_EFFORT" not in prompt
    assert "truncated" not in prompt


def test_usage_is_raw_not_cache_discounted():
    vote = parse_stream(stream())
    assert vote["score"] == 80
    assert vote["usage"]["input_tokens"] == 1000
    assert api_estimate(vote["usage"]) == 0.0132


@pytest.mark.parametrize("score", [True, -1, 101, float("nan"), float("inf"), "80"])
def test_rejects_invalid_scores(score):
    with pytest.raises(ValueError):
        parse_stream(stream(score))


@pytest.mark.parametrize(
    "tool", ["command_execution", "web_search", "file_change", "mcp_tool_call"]
)
def test_rejects_tool_use(tool):
    with pytest.raises(ValueError, match="Disallowed"):
        parse_stream(stream(extra={"type": "item.started", "item": {"type": tool}}))


def test_requires_complete_session():
    with pytest.raises(ValueError):
        parse_stream('{"type":"thread.started","thread_id":"x"}')


def test_rejects_failed_turn():
    with pytest.raises(ValueError, match="failed"):
        parse_stream(stream(extra={"type": "turn.failed", "error": "quota"}))


def test_resume_preserves_sources_and_calls_only_missing_votes(tmp_path, monkeypatch):
    run = tmp_path / "low" / "task-run"
    run.mkdir(parents=True)
    original = b'{"original":true}'
    (run / "summary.json").write_bytes(original)
    data = {
        "source_hashes": {"summary": retrospective.digest(original)},
        "issue": "fix",
        "patch": "+code",
        "summary": {
            "task_id": "task",
            "verifier": {"scores": {"functional": 1}},
            "scores": {"functional": 1},
        },
    }
    monkeypatch.setattr(retrospective, "inputs", lambda *args: data)
    calls = []

    def fake_vote(prompt, folder, name, settings):
        calls.append(name)
        return {"score": 80, "rationale": "clear"}

    monkeypatch.setattr(retrospective, "judge_vote", fake_vote)
    output = tmp_path / "derived"
    first = retrospective.judge_run(run, tmp_path, output, {"protocol": "v2"})
    second = retrospective.judge_run(run, tmp_path, output, {"protocol": "v2"})
    assert first == second
    assert first["human_like"] == 0.8
    assert len(calls) == 3
    assert (run / "summary.json").read_bytes() == original
    with pytest.raises(ValueError, match="Stale"):
        retrospective.judge_run(run, tmp_path, output, {"protocol": "different"})


def test_failed_vote_is_retained_and_not_retried(tmp_path, monkeypatch):
    run = tmp_path / "low" / "task-run"
    run.mkdir(parents=True)
    data = {"source_hashes": {}, "issue": "fix", "patch": "+code", "summary": {"verifier": {}}}
    monkeypatch.setattr(retrospective, "inputs", lambda *args: data)

    def fail(*args):
        raise RuntimeError("quota")

    monkeypatch.setattr(retrospective, "judge_vote", fail)
    output = tmp_path / "derived"
    with pytest.raises(RuntimeError, match="quota"):
        retrospective.judge_run(run, tmp_path, output, {})
    with pytest.raises(ValueError, match="operator review"):
        retrospective.judge_run(run, tmp_path, output, {})
