"""Offline guardrails for the additive comparison; no provider calls."""
import math

import pytest

from harness.evaluator.reviewed_score import reviewed_score
from harness.panel_comparison import aggregate, average_panel, claude_model_evidence, mean_se


@pytest.mark.parametrize("value", [None, True, -1, 1.1, float("nan"), float("inf"), "0.8"])
def test_missing_or_invalid_reviewer_never_reweighted(value):
    with pytest.raises(ValueError):
        average_panel(.8, value)


def test_equal_panel_and_fixed_twenty_percent_weight():
    panel = average_panel(.9, .7)
    assert panel == .8
    assert reviewed_score({"functional": 1, "quality": .8, "security": .9, "human_like": panel}) == pytest.approx(.915)


def test_one_sample_standard_error():
    result = mean_se([1., 2., 3.])
    assert result["mean"] == 2
    assert result["se"] == pytest.approx(1 / math.sqrt(3))


def test_incomplete_coverage_refuses_final_card_data():
    with pytest.raises(ValueError, match="Incomplete"):
        aggregate([], ["a", "b"], complete=True)


def test_duplicate_tasks_rejected():
    row = {"model": "astra", "effort": "low", "task": "a"}
    with pytest.raises(ValueError, match="Duplicate"):
        aggregate([row, row], ["a"], complete=False)


def events(model, fallback=False):
    result = [{"type": "assistant", "message": {"model": model}}]
    if fallback:
        result.append({"subtype": "model_refusal_fallback", "original_model": "claude-opus-5",
                       "fallback_model": "claude-opus-4-8", "scope": "session", "trigger": "refusal"})
    return result


def test_initial_model_is_not_enough_to_establish_reviewer_identity():
    with pytest.raises(ValueError, match="drift"):
        claude_model_evidence(events("claude-opus-4-8"), allow_fallbacks=True)


def test_reviewer_fallback_requires_explicit_policy():
    with pytest.raises(ValueError, match="approval"):
        claude_model_evidence(events("claude-opus-4-8", True), allow_fallbacks=False)
    assert claude_model_evidence(events("claude-opus-4-8", True), allow_fallbacks=True) == {
        "assistant_models": ["claude-opus-4-8"], "fallback": True}


def test_pure_opus_is_not_labeled_a_fallback():
    assert not claude_model_evidence(events("claude-opus-5"), allow_fallbacks=False)["fallback"]


def test_unexpected_models_rejected_even_with_fallback_policy():
    with pytest.raises(ValueError, match="drift"):
        claude_model_evidence(events("unknown", True), allow_fallbacks=True)
