"""Recovery is deterministic and changes neither rating nor quoted code."""
import json

import pytest

from harness.review_format import escape_code_quotes, parse_claude_preserving_rating


def stream(result):
    return "\n".join(json.dumps(e) for e in [
        {"type": "system", "subtype": "init", "model": "claude-opus-5", "tools": []},
        {"type": "result", "subtype": "success", "is_error": False, "result": result,
         "session_id": "s", "usage": {"input_tokens": 1, "output_tokens": 2,
                                      "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}},
    ])


def test_recovers_backtick_quotes_preserving_score():
    raw = '{"score":70,"rationale":"A `"big"` sentinel."}'
    vote = parse_claude_preserving_rating(stream(raw))
    assert vote["score"] == 70
    assert vote["rationale"] == 'A `"big"` sentinel.'


def test_already_escaped_quotes_not_double_escaped():
    raw = json.dumps({"score": 72, "rationale": 'A `"big"` sentinel.'})
    assert escape_code_quotes(raw) == raw
    assert parse_claude_preserving_rating(stream(raw))["score"] == 72


@pytest.mark.parametrize("raw", [
    '{"score":70,"rationale":"A "big" sentinel."}',
    '{"score":"70","rationale":"A `"big"` sentinel."}',
    '{"score":70,"rationale":"A `"big"` sentinel.","extra":1}',
    '{"score":70,"rationale":"unfinished',
])
def test_refuses_broader_or_ambiguous_repairs(raw):
    with pytest.raises((ValueError, json.JSONDecodeError)):
        parse_claude_preserving_rating(stream(raw))
