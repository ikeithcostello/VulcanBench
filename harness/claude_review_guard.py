"""Operational guard around the frozen Claude review rubric and saved votes.

Pause before another call at 80% subscription use, on missing quota evidence,
or on overage. Allow one authorized malformed-JSON retry per vote.
"""
import json
from datetime import UTC, datetime
from pathlib import Path

from harness import claude_retrospective as review

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "runs-astra-cii-v4-claude-judging-v1"


def quota_ok(info):
    if not info or info.get("isUsingOverage") is not False:
        return False
    if info.get("status") not in {"allowed", "allowed_warning"}:
        return False
    windows = info.get("unifiedWindows", {})
    if not windows:
        return False
    return all(isinstance(w.get("utilization"), (int, float))
               and 0 <= w["utilization"] < .80 for w in windows.values())


def latest_quota():
    paths = sorted(OUTPUT.glob("*/*/*.stream.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in paths:
        events = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        rates = [e["rate_limit_info"] for e in events if e.get("type") == "rate_limit_event"]
        if rates:
            return rates[-1]
    return None


def main():
    original = review.judge_vote

    def guarded(prompt, folder, name, settings):
        quota = latest_quota()
        if not quota_ok(quota):
            review.base.save(OUTPUT / "pause.json", {"reason": "Quota guard: no further calls",
                "quota": quota, "at": datetime.now(UTC).isoformat()})
            raise SystemExit("Subscription guard paused review before next call")
        try:
            result = original(prompt, folder, name, {**settings, "model": "claude-opus-5"})
        except json.JSONDecodeError as exc:
            archive = folder / "retries" / f"{name}-attempt-1"
            if archive.exists():
                raise
            archive.mkdir(parents=True)
            for suffix in ("prompt.txt", "stream.jsonl", "stderr.txt"):
                (folder / f"{name}.{suffix}").rename(archive / f"{name}.{suffix}")
            review.base.save(archive / "authorization.json", {
                "authorization": "User approved one malformed-response retry per call on September 5, 2026",
                "error": str(exc), "include_in_usage_totals": True, "include_in_score": False})
            return guarded(prompt, folder, name, settings)
        # Original parser verifies the pinned returned model. Evidence remains
        # blinded and identical; only the transport alias is made explicit.
        return result

    review.judge_vote = guarded
    review.base.save(OUTPUT / "execution-policy.json", {
        "model_pinned": "claude-opus-5", "effort": "medium", "quota_stop_fraction": .80,
        "malformed_json_retries_per_vote": 1, "rubric_unchanged": True,
        "guard_sha256": review.base.digest(Path(__file__).read_bytes())})
    review.main()


if __name__ == "__main__":
    main()
