#!/usr/bin/env bash
set -euo pipefail

INTERVAL_SECONDS="${1:-900}" # default 15 min
BRANCH="$(git branch --show-current)"
REMOTE="${REMOTE:-origin}"

mkdir -p logs

echo "Autosaving on-court progress every ${INTERVAL_SECONDS}s on branch ${BRANCH}"
echo "Ctrl+C to stop."

while true; do
  ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

  git add \
    public/data/pbpstats/on_court_pipeline \
    logs/oncourt_game_*.log \
    logs/oncourt_game_*.start \
    scripts/build_pbpstats_oncourt_pipeline.py \
    scripts/run_oncourt_scrape_batch.sh \
    scripts/monitor_oncourt_scrape.sh \
    scripts/autosave_oncourt_progress.sh \
    2>/dev/null || true

  if git diff --cached --quiet; then
    echo "[$ts] No scrape changes to save."
  else
    git commit -m "Autosave PBPStats on-court scrape progress ${ts}"
    git push "$REMOTE" "$BRANCH"
    echo "[$ts] Saved and pushed scrape progress."
  fi

  sleep "$INTERVAL_SECONDS"
done
