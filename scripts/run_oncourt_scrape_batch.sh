#!/usr/bin/env bash
set -euo pipefail

YEARS="${1:-}"
if [[ -z "$YEARS" ]]; then
  echo "Usage: bash scripts/run_oncourt_scrape_batch.sh 2006-2010" >&2
  exit 2
fi

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

if [[ ! -f scripts/build_pbpstats_oncourt_pipeline.py ]]; then
  echo "Missing scripts/build_pbpstats_oncourt_pipeline.py in $ROOT" >&2
  exit 1
fi

SAFE_YEARS="${YEARS//-/_}"
LOG="logs/oncourt_game_${SAFE_YEARS}.log"
START_FILE="logs/oncourt_game_${SAFE_YEARS}.start"

mkdir -p logs

if pgrep -af "build_pbpstats_oncourt_pipeline.py.*--years ${YEARS}.*--levels game" >/dev/null 2>&1; then
  echo "A matching on-court scrape already appears to be running for ${YEARS}." >&2
  pgrep -af "build_pbpstats_oncourt_pipeline.py.*--years ${YEARS}.*--levels game" >&2 || true
  exit 1
fi

date +%s > "$START_FILE"

{
  echo "PBPStats on-court scrape"
  echo "Started: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "Repo: $ROOT"
  echo "Years: $YEARS"
  echo "Log: $LOG"
  echo
  python3 -u scripts/build_pbpstats_oncourt_pipeline.py \
    --years "$YEARS" \
    --levels game \
    --sleep 1
} 2>&1 | tee -a "$LOG"
