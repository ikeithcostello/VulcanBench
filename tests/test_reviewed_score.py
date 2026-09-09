import pytest

from harness.evaluator.reviewed_score import WEIGHTS, WEIGHTS_V3, reviewed_score


def test_weights_and_perfect():
    assert sum(WEIGHTS.values()) == 1
    assert reviewed_score(dict.fromkeys(WEIGHTS, 1)) == 1


def test_review_weight_and_ignored_efficiency():
    assert reviewed_score(dict(functional=1, quality=1, security=1, human_like=.9, efficiency=0)) == pytest.approx(.98)


def test_equal_model_panel_contributes_ten_percent_each():
    panel = (.9 + .7) / 2
    assert reviewed_score(dict(functional=1, quality=.8, security=.8, human_like=panel)) == pytest.approx(.90)


@pytest.mark.parametrize("value", [None, float("nan"), -1, 1.1])
def test_missing_or_invalid(value):
    with pytest.raises(ValueError):
        reviewed_score(dict(functional=1, quality=1, security=1, human_like=value))


def test_v3_weights_lock_code_quality_at_a_third():
    assert sum(WEIGHTS_V3.values()) == pytest.approx(1)
    assert WEIGHTS_V3["human_like"] == .33
    assert WEIGHTS_V3["quality"] == WEIGHTS_V3["security"] == .085
    assert reviewed_score(dict(functional=1, quality=1, security=1, human_like=0), WEIGHTS_V3) == pytest.approx(.67)
