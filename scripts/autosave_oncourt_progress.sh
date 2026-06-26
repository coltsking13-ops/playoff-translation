#!/usr/bin/env bash
set -euo pipefail

INTERVAL_SECONDS="${1:-900}"

cd "$(git rev-parse --show-toplevel)"
mkdir -p logs

echo "Autosave started: every ${INTERVAL_SECONDS}s"
echo "Tracking scrape cache, outputs, and logs only."
echo "Stop with Ctrl+C."

while true; do
  stamp="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"

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
    echo "[$stamp] No scrape changes to save."
  else
    git commit -m "Autosave PBPStats on-court scrape progress ${stamp}"
    git push
    echo "[$stamp] Saved and pushed scrape progress."
  fi

  sleep "$INTERVAL_SECONDS"
done
