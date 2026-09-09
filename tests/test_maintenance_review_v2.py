from harness import maintenance_review_v2 as review
from harness.maintenance_summary import composite


def test_host_aggregation_weights():
    row = {"functional": 1, "quality": 1, "security": 1}
    assert composite(row, 100, .33) == 100
    assert composite(row, 0, .33) == 67
    assert composite(row, 0, .20) == 80


def test_model_aggregate_is_not_authoritative():
    vote = {"score": 0, "rationale": "Clear small interface.",
            "dimensions": {d: {"score": 3, "excerpt": "def fee(kind, units):",
                               "consequence": "The interface is explicit."}
                           for d in review.DIMENSIONS}}
    review.validate(vote, review.controls()[0])
    assert 6.25 * sum(v["score"] for v in vote["dimensions"].values()) == 75
