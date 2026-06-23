import json
from pathlib import Path
from collections import Counter

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

ROW_HINTS = set()
for fields in NEEDED.values():
    ROW_HINTS.update(fields)

def read(path):
    try:
        return json.loads(path.read_text())
    except Exception:
        return None

def looks_like_stat_row(x):
    if not isinstance(x, dict):
        return False
    hits = sum(1 for k in ROW_HINTS if k in x)
    return hits >= 3 and ("Points" in x or "OffPoss" in x or "AtRimFGA" in x or "TsPct" in x)

def walk_rows(x, rows):
    if isinstance(x, dict):
        if looks_like_stat_row(x):
            rows.append(x)
        for v in x.values():
            walk_rows(v, rows)
    elif isinstance(x, list):
        for v in x:
            walk_rows(v, rows)

def collect_rows(files):
    rows = []
    for p in files:
        obj = read(p)
        walk_rows(obj, rows)
    return rows

def field_counts(rows):
    filled = Counter()
    present = Counter()

    for r in rows:
        for k, v in r.items():
            present[k] += 1
            if v not in [None, "", [], {}]:
                filled[k] += 1

    return present, filled

game_files = sorted(CACHE.glob("game_stats_player__*.json"))
low_files = sorted(CACHE.glob("poss_low__*.json"))

all_rows = collect_rows(game_files)
low_rows = collect_rows(low_files)

all_present, all_filled = field_counts(all_rows)
low_present, low_filled = field_counts(low_rows)

print("=== RAW PLAYER MEDIUM+ FIELD AUDIT V2 ===")
print("game_stats_player cache files:", len(game_files))
print("poss_low cache files:", len(low_files))
print("raw stat-like ALL rows seen:", len(all_rows))
print("raw stat-like LOW rows seen:", len(low_rows))

for group, fields in NEEDED.items():
    print("\nGROUP:", group)

    for f in fields:
        a = all_filled.get(f, 0)
        l = low_filled.get(f, 0)

        if a > 0 and l > 0:
            status = "OK"
        elif a > 0 and l == 0:
            status = "MISSING LOW"
        elif a == 0 and l > 0:
            status = "MISSING ALL"
        else:
            status = "MISSING BOTH"

        print(f"{f:35s} all={a:<8} low={l:<8} {status}")

print("\n=== Sample ALL row ===")
for r in all_rows[:1]:
    keep = {k: r.get(k) for k in sorted(r.keys()) if k in ROW_HINTS or k in ["Name", "PlayerId", "EntityId", "TeamAbbreviation"]}
    print(json.dumps(keep, indent=2)[:3000])

print("\n=== Sample LOW row ===")
for r in low_rows[:1]:
    keep = {k: r.get(k) for k in sorted(r.keys()) if k in ROW_HINTS or k in ["Name", "PlayerId", "EntityId", "TeamAbbreviation"]}
    print(json.dumps(keep, indent=2)[:3000])

report = {
    "game_stats_player_cache_files": len(game_files),
    "poss_low_cache_files": len(low_files),
    "all_rows_seen": len(all_rows),
    "low_rows_seen": len(low_rows),
    "groups": {
        group: {
            f: {
                "all_filled": all_filled.get(f, 0),
                "low_filled": low_filled.get(f, 0)
            }
            for f in fields
        }
        for group, fields in NEEDED.items()
    }
}

out = OUT / "raw_player_medium_plus_field_audit_v2.json"
out.write_text(json.dumps(report, indent=2), encoding="utf-8")
print("\nWrote:", out)
