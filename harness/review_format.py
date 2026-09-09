"""Narrow, deterministic recovery of unescaped quotes inside inline code.

Never change a numeric rating or choose among ratings by value. The original
stream remains untouched; normalization is performed only in memory. Other
malformed JSON remains an error.
"""
import json
import re

from harness import claude_retrospective as claude


def escape_code_quotes(text):
    def fix(match):
        result, slashes = [], 0
        for char in match.group(0):
            if char == '"' and slashes % 2 == 0:
                result.append("\\")
            result.append(char)
            slashes = slashes + 1 if char == "\\" else 0
        return "".join(result)

    return re.sub(r"`[^`\n]+`", fix, text)


def parse_claude_preserving_rating(stream):
    try:
        return claude.parse(stream)
    except json.JSONDecodeError:
        events = [json.loads(line) for line in stream.splitlines() if line.strip()]
        results = [e for e in events if e.get("type") == "result"]
        if len(results) != 1 or results[0].get("structured_output") is not None:
            raise
        result = results[0]
        raw = result["result"]
        match = re.fullmatch(r'\s*\{\s*"score"\s*:\s*(\d+(?:\.\d+)?)\s*,\s*"rationale"\s*:\s*"(.*)"\s*\}\s*', raw)
        if not match:
            raise
        normalized = escape_code_quotes(raw)
        decoded = json.loads(normalized)
        if set(decoded) != {"score", "rationale"} or decoded["score"] != float(match[1]):
            raise ValueError("Format recovery changed score or fields") from None
        result["result"] = normalized
        return claude.parse("\n".join(json.dumps(e) for e in events))
