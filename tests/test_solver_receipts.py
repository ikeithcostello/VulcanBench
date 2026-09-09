import pytest

from harness.solver_receipts import claude_receipts


def receipt(ident, cost, output=10):
    return {
        "uuid": ident,
        "session_id": "s",
        "subtype": "success",
        "is_error": False,
        "total_cost_usd": cost,
        "usage": {
            "input_tokens": 1,
            "cache_read_input_tokens": 100,
            "cache_creation_input_tokens": 20,
            "output_tokens": output,
        },
    }


def test_raw_tokens_not_price_discounted():
    assert claude_receipts([receipt("a", 2)])["raw_tokens"] == 131


def test_multiturn_usage_summed_but_cumulative_cost_not_doubled():
    result = claude_receipts([receipt("a", 2), receipt("b", 3)])
    assert result["raw_tokens"] == 262
    assert result["cli_api_equivalent_estimate_usd"] == 3


def test_duplicate_receipt_rejected():
    with pytest.raises(ValueError, match="Duplicate"):
        claude_receipts([receipt("a", 2), receipt("a", 2)])


def test_decreasing_cumulative_cost_rejected():
    with pytest.raises(ValueError, match="cumulative"):
        claude_receipts([receipt("a", 3), receipt("b", 2)])
