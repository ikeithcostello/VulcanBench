"""Offline tests for the frozen review path and synthetic control behavior."""

import copy
import json

import pytest

from harness import maintenance_review as review


def example():
    return {
        "score": 75,
        "rationale": "Readable small implementation.",
        "dimensions": {
            d: {
                "score": 3,
                "excerpt": "def fee(kind, units):",
                "consequence": "The interface is explicit.",
            }
            for d in review.DIMENSIONS
        },
    }


def test_controls_preserve_functionality():
    # Only these locally authored fixtures are executed, never saved submissions.
    for evidence in review.controls():
        scope = {}
        exec(evidence["final_files"]["fee.py"], scope)
        for kind, rate in [("a", 2), ("b", 3), ("other", 5)]:
            for units in (0, 1, 2, 9, 1000):
                assert scope["fee"](kind, units) == rate * units + 1


def test_score_and_evidence_validation():
    review.validate(example(), review.controls()[0])
    bad = example()
    bad["dimensions"]["readability"]["excerpt"] = "not present in source"
    with pytest.raises(ValueError, match="Unsupported evidence"):
        review.validate(bad, review.controls()[0])
    bad = example()
    bad["score"] = 99
    with pytest.raises(ValueError, match="equal dimension"):
        review.validate(bad, review.controls()[0])


@pytest.mark.parametrize("score", [True, -1, 4.5, float("nan"), "3"])
def test_invalid_dimensions(score):
    bad = example()
    bad["dimensions"]["intent"]["score"] = score
    with pytest.raises(ValueError):
        review.validate(bad, review.controls()[0])


def test_freeze_is_immutable(tmp_path):
    path = tmp_path / "frozen.json"
    review.freeze(path, {"x": 1})
    review.freeze(path, {"x": 1})
    with pytest.raises(ValueError, match="Frozen"):
        review.freeze(path, {"x": 2})


def test_prompt_has_no_analyst_metadata():
    text = review.prompt(review.controls()[0])
    assert "source_directory" not in text
    assert "solver_seconds" not in text
    assert "gpt-6-astra" not in text
    assert "claude-opus-5" not in text
    assert "gold_patch" not in text


def test_pair_response():
    for score in [0, 50, 100]:
        review.validate({"score": score, "rationale": "A concrete comparison"}, {}, True)
    with pytest.raises(ValueError):
        review.validate({"score": 75, "rationale": "Invalid tie"}, {}, True)


def test_saved_vote_bound_to_prompt(tmp_path, monkeypatch):
    monkeypatch.setattr(review, "OUT", tmp_path)
    review.freeze(tmp_path / "protocol.json", {"id": "test"})
    evidence = review.controls()[0]
    folder = tmp_path / "calls/astra/primary/submission-001"
    folder.mkdir(parents=True)
    vote = example()
    vote["binding"] = {
        "protocol_sha256": review.sha(tmp_path / "protocol.json"),
        "prompt_sha256": review.base.digest(review.prompt(evidence).encode()),
    }
    review.freeze(folder / "selected.json", vote)
    assert review.call("astra", "primary", "submission-001", evidence, {})["score"] == 75
    changed = copy.deepcopy(evidence)
    changed["issue"] += " Changed."
    with pytest.raises(ValueError, match="binding"):
        review.call("astra", "primary", "submission-001", changed, {})


def test_claude_fallback_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(review, "OUT", tmp_path)
    events = [
        {"type": "system", "subtype": "init", "apiKeySource": "none"},
        {"type": "assistant", "message": {"model": "claude-opus-4-8"}},
    ]
    with pytest.raises(RuntimeError, match="identity"):
        review.claude_identity_and_quota("\n".join(json.dumps(e) for e in events))
