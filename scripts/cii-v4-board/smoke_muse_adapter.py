"""Synthetic contributor validation. Never loads or grades a benchmark task."""

import argparse
import json
import subprocess
import tempfile
import time
from pathlib import Path

from run_muse_sweep import BINARY_SHA256, LEVELS, MODEL, configure_binary

from harness.agent.muse_code import MuseCodeAdapter
from harness.effort import effort_config
from harness.pricing import cost_usd


class Collector:
    def __init__(self):
        self.trace = []

    def record(self, kind, data):
        self.trace.append({"kind": kind, "data": data})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--efforts", nargs="+", choices=LEVELS, default=LEVELS)
    args = parser.parse_args()
    configure_binary()
    args.output.mkdir(parents=True, exist_ok=True)
    for effort in args.efforts:
        output = args.output / effort
        output.mkdir(exist_ok=False)
        root = Path(tempfile.mkdtemp(prefix="vb-muse-synthetic-")).resolve()
        workspace = root / "workspace"
        workspace.mkdir()
        collector = Collector()

        started = time.monotonic()
        try:
            outcome = MuseCodeAdapter().run_task(
                workspace=workspace,
                prompt=(
                    "Synthetic CLI validation only. Do not use subagents. "
                    "Create add.py with add(a,b) returning a+b, then use python3 "
                    "to assert add(2,3)==5 and add(-2,2)==0. "
                    "Also create a temporary file with mktemp using the explicit "
                    "$TMPDIR template described above, write OK to it and verify "
                    "its contents. Stop once these checks pass. Do not commit."
                ),
                model=MODEL.split(":", 1)[1],
                priced_spec=MODEL,
                max_turns=12,
                collector=collector,
                stream_log_path=output / "stream.jsonl",
                timeout_s=240,
                effort=effort_config("muse-code", effort).provider_value,
            )
            assert outcome.finished and outcome.prompt_tokens > 0
            subprocess.run(
                [
                    "/opt/homebrew/bin/python3",
                    "-c",
                    "from add import add; assert add(2,3)==5; assert add(-2,2)==0",
                ],
                cwd=workspace,
                check=True,
                timeout=10,
            )
            result = {
                "effort": effort,
                "state": "passed",
                "duration_s": time.monotonic() - started,
                "binary_sha256": BINARY_SHA256,
                "outcome": outcome.summary(),
                "api_equivalent_usd": cost_usd(
                    MODEL,
                    outcome.prompt_tokens,
                    outcome.completion_tokens,
                    cached_input_tokens=outcome.cached_input_tokens,
                ),
            }
        except Exception as exc:
            result = {
                "effort": effort,
                "state": "failed",
                "error": str(exc),
                "duration_s": time.monotonic() - started,
            }
        (output / "trace.json").write_text(json.dumps(collector.trace, indent=2) + "\n")
        (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result), flush=True)
        if result["state"] != "passed":
            raise RuntimeError(f"Synthetic validation failed at {effort}; see {output}")


if __name__ == "__main__":
    main()
