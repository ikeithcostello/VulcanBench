"""A recovered first rating is never replaced with a higher retry rating."""

import json

from harness import retrospective_judging as base
from harness.fable_panel_resume import recover_failed


def raw_stream(score):
    result = '{"score":' + str(score) + ',"rationale":"A `"big"` sentinel."}'
    return "\n".join(
        json.dumps(e)
        for e in [
            {
                "type": "system",
                "subtype": "init",
                "model": "claude-opus-5",
                "tools": [],
                "mcp_servers": [],
                "apiKeySource": "none",
            },
            {"type": "assistant", "message": {"model": "claude-opus-5", "content": []}},
            {"type": "rate_limit_event", "rate_limit_info": {"isUsingOverage": False}},
            {
                "type": "result",
                "subtype": "success",
                "is_error": False,
                "result": result,
                "session_id": f"s{score}",
                "duration_ms": 1000,
                "usage": {
                    "input_tokens": 1,
                    "output_tokens": 2,
                    "cache_read_input_tokens": 0,
                    "cache_creation_input_tokens": 0,
                },
            },
        ]
    )


def test_retains_first_rating_and_all_raw_evidence(tmp_path):
    folder = tmp_path / "high" / "queue"
    archive = folder / "retries" / "readability-attempt-1"
    archive.mkdir(parents=True)
    first = archive / "readability.stream.jsonl"
    later = folder / "readability.stream.jsonl"
    first.write_text(raw_stream(70))
    later.write_text(raw_stream(72))
    for parent in (folder, archive):
        (parent / "readability.prompt.txt").write_text("frozen prompt")
    settings = {"claude": "/not/called", "model": "claude-opus-5"}
    data = {"source_hashes": {"summary": "a"}}
    binding = base.digest(
        base.canonical({"sources": data["source_hashes"], "settings": settings}).encode()
    )
    failed = {
        "status": "failed",
        "binding": binding,
        "prompt_sha256": base.digest(b"frozen prompt"),
        "error": "format",
    }
    (folder / "readability.json").write_text(json.dumps(failed))
    originals = (first.read_bytes(), later.read_bytes())
    recover_failed(folder, "readability", settings, data)
    vote = json.loads((folder / "readability.json").read_text())
    assert vote["score"] == 70 and vote["status"] == "complete"
    assert vote["raw_stream_relative"] == "retries/readability-attempt-1/readability.stream.jsonl"
    assert (first.read_bytes(), later.read_bytes()) == originals
    assert json.loads((folder / "readability.failed-before-recovery.json").read_text()) == failed
    # A resumed call leaves the recovered complete vote unchanged.
    before = (folder / "readability.json").read_bytes()
    recover_failed(folder, "readability", settings, data)
    assert (folder / "readability.json").read_bytes() == before
