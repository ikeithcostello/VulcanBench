import pytest

from harness.api_equivalent_costs import astra_cost, claude_cost, claude_model_cost


def test_astra_cache_and_reasoning_not_double_counted():
    result = astra_cost(
        {
            "input_tokens": 1000000,
            "cached_input_tokens": 900000,
            "cache_write_input_tokens": 0,
            "output_tokens": 10000,
            "reasoning_output_tokens": 8000,
        }
    )
    assert result["estimated_usd"] == pytest.approx(2.4)
    assert result["long_context_upper_usd"] == pytest.approx(4.55)


def test_short_run_cannot_have_long_context_premium():
    result = astra_cost(
        {"input_tokens": 200000, "cached_input_tokens": 100000, "output_tokens": 1000}
    )
    assert result["estimated_usd"] == result["long_context_upper_usd"]


def test_invalid_astra_cache_rejected():
    with pytest.raises(Exception, match="subset"):
        astra_cost({"input_tokens": 10, "cached_input_tokens": 11, "output_tokens": 1})


def test_fable_mixed_cache_duration():
    usage = {
        "inputTokens": 1000000,
        "cacheReadInputTokens": 1000000,
        "cacheCreationInputTokens": 1000000,
        "outputTokens": 1000000,
    }
    result = claude_model_cost("claude-fable-5-1", usage, 400000)
    assert result["calculated_usd"] == pytest.approx(77.25)
    assert result["all_5m_usd"] == pytest.approx(72.75)
    assert result["all_1h_usd"] == pytest.approx(80.25)


def test_fallback_uses_its_own_rates():
    usage = {
        "inputTokens": 1000000,
        "cacheReadInputTokens": 1000000,
        "cacheCreationInputTokens": 1000000,
        "outputTokens": 1000000,
    }
    result = claude_model_cost("claude-opus-4-8", usage, 0)
    assert result["calculated_usd"] == pytest.approx(40.5)


def result_receipt(identity, tokens, price):
    return {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "uuid": identity,
        "session_id": "session",
        "total_cost_usd": price,
        "usage": {"service_tier": "standard", "speed": "standard"},
        "fast_mode_state": "off",
        "modelUsage": {
            "claude-fable-5-1": {
                "inputTokens": tokens,
                "cacheReadInputTokens": 0,
                "cacheCreationInputTokens": 0,
                "outputTokens": 0,
                "costUSD": price,
                "costBasis": "list",
                "provider": "firstParty",
            }
        },
    }


def test_cumulative_session_cost_is_not_added_twice():
    result = claude_cost([result_receipt("a", 1000000, 10), result_receipt("b", 2000000, 20)])
    assert result["estimated_usd"] == 20
    assert result["result_receipts"] == 2
    assert result["sessions"] == 1


def test_duplicate_receipt_rejected():
    event = result_receipt("a", 1000000, 10)
    with pytest.raises(Exception, match="Duplicate"):
        claude_cost([event, event])


def test_inconsistent_price_rejected():
    with pytest.raises(Exception, match="outside verified"):
        claude_cost([result_receipt("a", 1000000, 20)])
