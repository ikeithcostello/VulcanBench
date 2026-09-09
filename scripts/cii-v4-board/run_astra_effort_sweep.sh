#!/usr/bin/env bash
# GPT-6 Astra effort sweep on the Coding Intelligence Index v4.
#
# Each effort writes to an independent directory. Re-running this script is
# safe: --only-missing resumes incomplete levels without mixing observations.
#
# Usage:
#   bash scripts/cii-v4-board/run_astra_effort_sweep.sh
set -u
cd "$(dirname "$0")/../.."
# launchd starts with only the macOS system PATH. Include the user-installed
# Codex CLI explicitly so detached runs use the same authenticated CLI.
export PATH="/Users/morganlinton/.nvm/versions/node/v22.11.0/bin:$PWD/.venv/bin:$PATH"

MODEL="gpt-6-astra"
SUITE="coding-intelligence-index-v4"
ROOT="runs-astra-cii-v4"
# Astra supports low, medium, high, xhigh, and max. VulcanBench calls xhigh
# "extra-high" in its normalized CLI vocabulary.
LEVELS=${LEVELS:-"low medium high extra-high max"}

for level in $LEVELS; do
  outdir="$ROOT/$level"
  mkdir -p "$outdir"
  done_count=$(find "$outdir" -name summary.json 2>/dev/null | wc -l | tr -d ' ')
  echo "=== GPT-6 Astra effort=$level starting ($done_count/23 complete) $(date '+%F %H:%M:%S')"
  vulcanbench run --suite "$SUITE" --model "$MODEL" --harness codex --billing subscription \
    --sandbox local --no-judges --effort "$level" --only-missing -o "$outdir"
  status=$?
  done_count=$(find "$outdir" -name summary.json 2>/dev/null | wc -l | tr -d ' ')
  if [ "$status" -ne 0 ] || [ "$done_count" -ne 23 ]; then
    echo "=== GPT-6 Astra effort=$level stopped (exit=$status, $done_count/23 complete)."
    echo "=== Resume with: bash scripts/cii-v4-board/run_astra_effort_sweep.sh"
    exit "$status"
  fi
  echo "=== GPT-6 Astra effort=$level complete ($done_count/23) $(date '+%F %H:%M:%S')"
done

echo "=== GPT-6 Astra CII v4 sweep finished $(date '+%F %H:%M:%S')"
