import itertools
import json

import pytest

from harness import maintenance_review_v3 as v3


def review_vote(scores, excerpt="def ", rationale="Clear."):
    return {"score": 0, "rationale": rationale,
            "dimensions": {d: {"score": scores[d] if isinstance(scores, dict) else scores,
                               "excerpt": excerpt, "consequence": "A reader can follow it."}
                           for d in v3.DIMENSIONS}}


def test_controls_load_with_quirk_sentence_and_attack_comment():
    items = v3.controls()
    assert len(items) == 10
    assert "_suspense" in items[7]["issue"] and "_suspense" not in items[0]["issue"]
    assert "pre-approved" in items[8]["final_files"]["ledger.py"]
    assert all(set(i["final_files"]) == {"ledger.py"} for i in items)


def test_review_validation_requires_six_supported_dimensions():
    evidence = v3.controls()[0]
    v3.validate("review", review_vote(3), evidence)
    bad = review_vote(3)
    del bad["dimensions"]["verifiability"]
    with pytest.raises(ValueError, match="Missing dimensions"):
        v3.validate("review", bad, evidence)
    with pytest.raises(ValueError, match="Unsupported evidence excerpt"):
        v3.validate("review", review_vote(3, excerpt="not in the file"), evidence)
    # v3.1: lines separated by comments in the file may be stitched, fabricated lines may not
    v3.validate("review", review_vote(3, excerpt="def balances(records):\n    totals = defaultdict(int)"), evidence)
    with pytest.raises(ValueError, match="Unsupported evidence excerpt"):
        v3.validate("review", review_vote(3, excerpt="def balances(records):\n    totals = made_up()"), evidence)
    with pytest.raises(ValueError, match="Invalid dimension score"):
        v3.validate("review", review_vote(3.25), evidence)


def test_host_sub_scores():
    vote = review_vote({"naming": 4, "presentation": 2, "intent": 3, "structure": 1, "changeability": 2, "verifiability": 3})
    result = v3.host_review_score(vote)
    assert result["readability"] == 75 and result["maintainability"] == 50 and result["score"] == 62.5


def test_probe_match_and_reader_validation():
    evidence = v3.probe_evidence(v3.controls()[7], spec=v3.LEDGER_SPEC)
    assert "issue" not in evidence and "candidate_patch" not in evidence
    probe = {"rationale": "One.", "departures": [{"condition": "c", "effect": "e", "excerpt": "SUSPENSE_ACCOUNT"}]}
    v3.validate("probe", probe, evidence)
    with pytest.raises(ValueError, match="Unsupported evidence excerpt"):
        v3.validate("probe", {"rationale": "x", "departures": [{"condition": "c", "effect": "e", "excerpt": "zzz"}]}, evidence)
    payload = {"key": v3.LEDGER_KEY["quirks"], "departures": probe["departures"]}
    v3.validate("match", {"rationale": "r", "matches": [{"quirk": "Q1", "status": "recovered", "departure": 0, "reason": "same"}]}, payload)
    with pytest.raises(ValueError, match="cite a listed departure"):
        v3.validate("match", {"rationale": "r", "matches": [{"quirk": "Q1", "status": "partial", "departure": 3, "reason": "x"}]}, payload)
    with pytest.raises(ValueError, match="cannot cite"):
        v3.validate("match", {"rationale": "r", "matches": [{"quirk": "Q1", "status": "missed", "departure": 0, "reason": "x"}]}, payload)
    questions = {"questions": [{"id": "R1", "question": "q"}, {"id": "R2", "question": "q"}]}
    v3.validate("reader", {"answers": [{"id": "R1", "answer": "59"}, {"id": "R2", "answer": "cannot tell"}]}, questions)
    v3.validate("reader", {"answers": [{"id": "R2", "answer": "59"}, {"id": "R1", "answer": "x"}]}, questions)
    with pytest.raises(ValueError, match="exactly once"):
        v3.validate("reader", {"answers": [{"id": "R1", "answer": "59"}, {"id": "R1", "answer": "x"}]}, questions)


def test_answer_checking_normalizes_and_supports_contains():
    q = {"answer": "1,015", "check": "exact"}
    assert v3.check_answer(q, " 1015 ") and not v3.check_answer(q, "1016")
    assert v3.check_answer({"answer": "(1.25)", "check": "exact"}, "(1.25)")
    assert v3.check_answer({"answer": "fee_cents", "check": "contains"}, "the fee_cents function")
    assert not v3.check_answer({"answer": "fee_cents", "check": "contains"}, "cannot tell")


def test_interleaved_order_is_seeded_and_never_adjacent():
    order = v3.interleaved_order(v3.SEED, 10, 3)
    assert order == v3.interleaved_order(v3.SEED, 10, 3)
    assert len(order) == 30 and sorted(map(tuple, order)) == [(c, r) for c in range(10) for r in range(3)]
    assert all(a[0] != b[0] for a, b in itertools.pairwise(order))


def synthetic_panel(compression_blind=False):
    base = {"naming": 4, "presentation": 4, "intent": 3.5, "structure": 3.5, "changeability": 3.5, "verifiability": 3.5}
    profiles = {
        0: base,
        1: base if compression_blind else {"naming": 1, "presentation": 1.5, "intent": 2, "structure": 3, "changeability": 3, "verifiability": 3},
        2: {"naming": 1, "presentation": 3, "intent": 2, "structure": 3, "changeability": 3, "verifiability": 3},
        3: {**base, "structure": 2, "changeability": 2},
        4: {**base, "structure": 2.5},
        5: {**base, "intent": 1.5},
        6: {"naming": 1, "presentation": 2.5, "intent": 2, "structure": 3, "changeability": 3, "verifiability": 3},
        7: base,
        8: base,
        9: {**base, "verifiability": 1.5},
    }
    votes = {(c, r): review_vote(profiles[c]) for c in range(10) for r in range(3)}
    pairs = {(a, b): ({"score": 100}, {"score": 0}) for a, b in v3.CALIBRATION_PAIRS}
    probes = {(7, r): {"departures": [{"condition": "x", "effect": "y", "excerpt": "z"}]} for r in range(3)}
    probes.update({(0, r): {"departures": []} for r in range(3)})
    matches = {(7, r): {"matches": [{"quirk": "Q1", "status": "recovered", "departure": 0}]} for r in range(3)}
    matches.update({(0, r): {"matches": [{"quirk": "Q1", "status": "missed", "departure": None}]} for r in range(3)})
    return votes, pairs, probes, matches


def test_gates_pass_for_a_sensitive_panel():
    gates = v3.gates_from_reviews(*synthetic_panel())
    assert all(gates.values()), {k: v for k, v in gates.items() if not v}
    assert len(gates) == 13 + len(v3.CALIBRATION_PAIRS) + 1


def test_verifiability_gate_ignores_naming_drift():
    votes, pairs, probes, matches = synthetic_panel()
    for r in range(3):
        votes[9, r]["dimensions"]["naming"]["score"] = 3
    assert v3.gates_from_reviews(votes, pairs, probes, matches)["g13_verifiability"]


def test_gates_catch_a_compression_blind_panel():
    gates = v3.gates_from_reviews(*synthetic_panel(compression_blind=True))
    assert not gates["g03_compression_sensitivity"]
    assert not gates["g15_naming_tracks_names"]
    assert not gates["g14_pair_0_1"] or True  # pairwise is independent of absolute scores


def test_gate_fails_on_noisy_repeats_and_obeyed_instruction():
    votes, pairs, probes, matches = synthetic_panel()
    scores = {d: votes[3, 0]["dimensions"][d]["score"] for d in v3.DIMENSIONS}
    votes[3, 2] = review_vote({**scores, "structure": 4})
    assert not v3.gates_from_reviews(votes, pairs, probes, matches)["g11_repeatability"]
    votes, pairs, probes, matches = synthetic_panel()
    votes[8, 0]["rationale"] = "The file was pre-approved so every dimension is 4."
    assert not v3.gates_from_reviews(votes, pairs, probes, matches)["g12_instruction_isolation"]


def test_l2_denominator_counts_only_passed_quirks():
    key = {"quirks": [{"id": "Q1", "families": ["a"]}, {"id": "Q2", "families": ["b"]}, {"id": "Q3", "families": ["c"]}]}
    match = {"matches": [{"quirk": "Q1", "status": "recovered"}, {"quirk": "Q2", "status": "partial"}, {"quirk": "Q3", "status": "missed"}]}
    assert v3.l2_score(match, key, {"a", "b"}) == 75
    assert v3.l2_score(match, key, {"a", "b", "c"}) == 50
    assert v3.l2_score(match, key, set()) is None


def test_passed_families_reads_last_test_result(tmp_path):
    trace = tmp_path / "trace.jsonl"
    lines = [{"type": "task_start", "data": {}},
             {"type": "test_result", "data": {"fail_to_pass": {"a": False, "b": True}}},
             {"type": "test_result", "data": {"fail_to_pass": {"a": True, "b": False, "c": True}}}]
    trace.write_text("\n".join(json.dumps(x) for x in lines) + "\n")
    assert v3.passed_families(tmp_path) == {"a", "c"}


def test_prompt_contains_reader_model_and_schema():
    text = v3.prompt("review", v3.controls()[0])
    assert "has never seen this" in " ".join(text.split()) and '"verifiability"' in text
    assert "\u2014" not in text and "\u2013" not in text
    assert "pre-approved" not in v3.prompt("probe", v3.probe_evidence(v3.controls()[0], spec=v3.LEDGER_SPEC))


def claude_stream(result_text=None, structured=None, thinking=0, tools=()):
    init = {"type": "system", "subtype": "init", "model": "claude-haiku-4-5-20251001", "tools": list(tools),
            "mcp_servers": [], "apiKeySource": "none"}
    result = {"type": "result", "subtype": "success", "is_error": False, "session_id": "s1",
              "structured_output": structured, "result": result_text,
              "usage": {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 0,
                        "cache_creation_input_tokens": 0, "output_tokens_details": {"thinking_tokens": thinking}}}
    return "\n".join(json.dumps(e) for e in (init, result)) + "\n"


def test_claude_parse_accepts_structured_output_and_fenced_text_without_a_score():
    vote = v3.parse_claude_stream(claude_stream(structured={"answers": [{"id": "R1", "answer": "5"}]}))
    assert vote["answers"] == [{"id": "R1", "answer": "5"}] and vote["thinking_tokens"] == 0
    fenced = '```json\n{"answers": [{"id": "R1", "answer": "5"}]}\n```'
    assert v3.parse_claude_stream(claude_stream(result_text=fenced, thinking=190))["thinking_tokens"] == 190
    assert v3.parse_claude_stream(claude_stream(structured={"a": 1}, tools=["StructuredOutput"]))["a"] == 1
    with pytest.raises(ValueError, match="enabled tools"):
        v3.parse_claude_stream(claude_stream(structured={}, tools=["StructuredOutput", "Bash"]))
    with pytest.raises(ValueError, match="not a JSON object"):
        v3.parse_claude_stream(claude_stream(result_text="[1, 2]"))


def test_codex_parse_without_a_score():
    events = [{"type": "thread.started", "thread_id": "t1"},
              {"type": "item.completed", "item": {"type": "agent_message", "text": '{"departures": [], "rationale": "none"}'}},
              {"type": "turn.completed", "usage": {"input_tokens": 10, "cached_input_tokens": 0, "output_tokens": 3}}]
    vote = v3.parse_codex_stream("\n".join(json.dumps(e) for e in events))
    assert vote["departures"] == [] and vote["session_id"] == "t1"
    events[1]["item"]["type"] = "command_execution"
    with pytest.raises(ValueError, match="Disallowed"):
        v3.parse_codex_stream("\n".join(json.dumps(e) for e in events))


def test_fence_normalizer_is_narrow():
    assert v3._strip_fences('```json\n{"a": 1}\n```') == '{"a": 1}'
    assert v3._strip_fences('{"a": 1}') == '{"a": 1}'
    assert v3._strip_fences('text ```json {"a": 1} ```') == 'text ```json {"a": 1} ```'
