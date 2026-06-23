import json
from pathlib import Path
from collections import Counter, defaultdict

CACHE = Path("public/data/pbpstats/_cache")
OUT = Path("public/data/pbpstats/audit")
OUT.mkdir(parents=True, exist_ok=True)

NEEDED = {
    "basic": [
        "Points", "FG2M", "FG2A", "FG3M", "FG3A", "FTA", "FtPoints",
        "Assists", "Rebounds", "OffRebounds", "DefRebounds",
        "Steals", "Blocks", "Turnovers", "Minutes", "SecondsPlayed",
        "OffPoss", "DefPoss", "TotalPoss", "PlusMinus"
    ],
    "adj_ts_ingredients": [
        "BadPassTurnovers", "BadPassOutOfBoundsTurnovers",
        "Turnovers", "Arc3FGA", "NonHeaveArc3FGA",
        "Technical Free Throw Trips", "SelfOReb",
        "FG2A", "FG3A", "FTA", "Points"
    ],
    "shot_locations": [
        "AtRimFGA", "AtRimFGM", "AtRimFrequency", "AtRimAccuracy",
        "ShortMidRangeFGA", "ShortMidRangeFGM", "ShortMidRangeFrequency", "ShortMidRangeAccuracy",
        "LongMidRangeFGA", "LongMidRangeFGM", "LongMidRangeFrequency", "LongMidRangeAccuracy",
        "Corner3FGA", "Corner3FGM", "Corner3Frequency", "Corner3Accuracy",
        "Arc3FGA", "Arc3FGM", "Arc3Frequency", "Arc3Accuracy",
        "ShotQualityAvg"
    ],
    "efficiency_usage": [
        "EfgPct", "TsPct", "Usage", "LiveBallTurnoverPct",
        "Fg2Pct", "Fg3Pct", "NonHeaveFg3Pct"
    ]
}

def read(p):
    try:
        return json.loads(p.read_text())
    except Exception:
        return None

def get_game_stat_rows(obj):
    if not isinstance(obj, dict):
        return []
    x = obj.get("multi_row_table_data")
    if isinstance(x, list):
        return [r for r in x if isinstance(r, dict)]
    x = obj.get("results")
    if isinstance(x, list):
        return [r for r in x if isinstance(r, dict)]
    if isinstance(x, dict):
        return [v for v in x.values() if isinstance(v, dict)]
    return []

def get_low_rows(obj):
    if not isinstance(obj, dict):
        return []
    x = obj.get("player_results")
    if isinstance(x, dict):
        return [v for v in x.values() if isinstance(v, dict)]
    x = obj.get("multi_row_table_data")
    if isinstance(x, list):
        return [r for r in x if isinstance(r, dict)]
    x = obj.get("results")
    if isinstance(x, list):
        return [r for r in x if isinstance(r, dict)]
    return []

def summarize_rows(rows):
    keys = Counter()
    filled = Counter()

    for r in rows:
        for k, v in r.items():
            keys[k] += 1
            if v not in [None, "", [], {}]:
                filled[k] += 1

    return keys, filled

game_files = sorted(CACHE.glob("game_stats_player__*.json"))
low_files = sorted(CACHE.glob("poss_low__*.json"))

game_rows = []
low_rows = []

for p in game_files:
    obj = read(p)
    game_rows.extend(get_game_stat_rows(obj))

for p in low_files:
    obj = read(p)
    low_rows.extend(get_low_rows(obj))

game_keys, game_filled = summarize_rows(game_rows)
low_keys, low_filled = summarize_rows(low_rows)

report = {
    "raw_game_stats_files": len(game_files),
    "raw_low_possession_files": len(low_files),
    "raw_game_player_rows_seen": len(game_rows),
    "raw_low_player_rows_seen": len(low_rows),
    "groups": {}
}

print("=== RAW PLAYER MEDIUM+ FIELD AUDIT ===")
print("game_stats_player cache files:", len(game_files))
print("poss_low cache files:", len(low_files))
print("All/player raw rows seen:", len(game_rows))
print("Low/player raw rows seen:", len(low_rows))

for group, fields in NEEDED.items():
    print("\nGROUP:", group)
    group_report = {}

    for f in fields:
        all_seen = game_filled.get(f, 0)
        low_seen = low_filled.get(f, 0)

        status = "OK"
        if all_seen == 0 and low_seen == 0:
            status = "MISSING BOTH"
        elif all_seen == 0:
            status = "MISSING ALL"
        elif low_seen == 0:
            status = "MISSING LOW"

        group_report[f] = {
            "all_filled_rows": all_seen,
            "low_filled_rows": low_seen,
            "status": status
        }

        print(f"{f:35s} all={all_seen:<8} low={low_seen:<8} {status}")

    report["groups"][group] = group_report

# Show the fields we have that look useful.
interesting_terms = [
    "rim", "midrange", "corner", "arc3", "shotquality",
    "turnover", "badpass", "heave", "technical", "selforeb",
    "efg", "ts", "usage", "poss", "rebound", "fta"
]

print("\n=== Useful raw ALL keys ===")
for k, n in sorted(game_filled.items()):
    if any(t in k.lower().replace(" ", "") for t in interesting_terms):
        print(k, n)

print("\n=== Useful raw LOW keys ===")
for k, n in sorted(low_filled.items()):
    if any(t in k.lower().replace(" ", "") for t in interesting_terms):
        print(k, n)

out = OUT / "raw_player_medium_plus_field_audit.json"
out.write_text(json.dumps(report, indent=2), encoding="utf-8")
print("\nWrote:", out)
