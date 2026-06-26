#!/usr/bin/env bash
set -euo pipefail

YEARS="${1:-}"
if [[ -z "$YEARS" ]]; then
  echo "Usage: bash scripts/monitor_oncourt_scrape.sh 2006-2010" >&2
  exit 2
fi

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

SAFE_YEARS="${YEARS//-/_}"
LOG="logs/oncourt_game_${SAFE_YEARS}.log"
START_FILE="logs/oncourt_game_${SAFE_YEARS}.start"
CACHE_DIR="public/data/pbpstats/on_court_pipeline/cache/api"
OUT_DIR="public/data/pbpstats/on_court_pipeline"

process_line="$(pgrep -af "build_pbpstats_oncourt_pipeline.py.*--years ${YEARS}.*--levels game" | head -n 1 || true)"
running="no"
if [[ -n "$process_line" ]]; then
  running="yes"
fi

current=0
total=0
latest_progress=""
if [[ -f "$LOG" ]]; then
  latest_progress="$(grep -E "game rows processed: [0-9]+/[0-9]+" "$LOG" | tail -n 1 || true)"
  if [[ -n "$latest_progress" ]]; then
    current="$(echo "$latest_progress" | sed -E 's/.*game rows processed: ([0-9]+)\/([0-9]+).*/\1/')"
    total="$(echo "$latest_progress" | sed -E 's/.*game rows processed: ([0-9]+)\/([0-9]+).*/\2/')"
  else
    total="$(grep -E "candidate player-games: [0-9]+" "$LOG" | tail -n 1 | sed -E 's/.*candidate player-games: ([0-9]+).*/\1/' || true)"
    total="${total:-0}"
  fi
fi

cache_count=0
cache_recent=0
if [[ -d "$CACHE_DIR" ]]; then
  cache_count="$(find "$CACHE_DIR" -type f -name "*.json" | wc -l | tr -d ' ')"
  cache_recent="$(find "$CACHE_DIR" -type f -name "*.json" -mmin -10 | wc -l | tr -d ' ')"
fi

progress="n/a"
if [[ "$total" =~ ^[0-9]+$ && "$current" =~ ^[0-9]+$ && "$total" -gt 0 ]]; then
  progress="$(awk -v c="$current" -v t="$total" 'BEGIN { printf "%.1f%%", (100*c/t) }')"
fi

speed="n/a"
eta="n/a"
if [[ -f "$START_FILE" && "$current" =~ ^[0-9]+$ && "$current" -gt 0 ]]; then
  now="$(date +%s)"
  start="$(cat "$START_FILE" 2>/dev/null || echo "$now")"
  elapsed=$((now - start))
  if [[ "$elapsed" -gt 0 ]]; then
    speed="$(awk -v c="$current" -v e="$elapsed" 'BEGIN { printf "%.2f rows/min", (60*c/e) }')"
    if [[ "$total" =~ ^[0-9]+$ && "$total" -gt "$current" ]]; then
      eta_seconds="$(awk -v c="$current" -v t="$total" -v e="$elapsed" 'BEGIN { printf "%.0f", ((t-c)/(c/e)) }')"
      eta="$(awk -v s="$eta_seconds" 'BEGIN { h=int(s/3600); m=int((s%3600)/60); printf "%dh %dm", h, m }')"
    else
      eta="0h 0m"
    fi
  fi
fi

output_files=""
if [[ "$YEARS" == *-* ]]; then
  start_year="${YEARS%-*}"
  end_year="${YEARS#*-}"
  for ((year=start_year; year<=end_year; year++)); do
    path="$OUT_DIR/player_on_game_${year}.json"
    if [[ -f "$path" ]]; then
      output_files+=$(ls -lh "$path" | awk '{print $9 " " $5}')$'\n'
    fi
  done
else
  path="$OUT_DIR/player_on_game_${YEARS}.json"
  if [[ -f "$path" ]]; then
    output_files+=$(ls -lh "$path" | awk '{print $9 " " $5}')$'\n'
  fi
fi

echo "PBPStats ${YEARS} Progress"
echo "---------------------------"
echo "Running: $running"
if [[ -n "$process_line" ]]; then
  echo "Process: $process_line"
fi
if [[ -f "$LOG" ]]; then
  echo "Log: $LOG"
else
  echo "Log: $LOG (missing)"
fi
echo "Rows processed: ${current} / ${total}"
echo "Cache files: $cache_count"
echo "Last 10 min: $cache_recent"
echo "Progress: $progress"
echo "Speed: $speed"
echo "ETA: $eta"
echo "Output files:"
if [[ -n "$output_files" ]]; then
  printf "%s" "$output_files"
else
  echo "none yet"
fi
echo "Latest log lines:"
if [[ -f "$LOG" ]]; then
  tail -n 8 "$LOG"
else
  echo "No log found yet."
fi
