import json
from pathlib import Path
from collections import defaultdict, Counter

PLAYER_DIR = Path("public/data/pbpstats/player_game_low_removed")
GAMES_DIR = Path("public/data/pbpstats/games")
OUT = Path("public/data/pbpstats/audit")
OUT.mkdir(parents=True, exist_ok=True)

EXPECTED = {
    "identity": [
        "year", "season", "gameId", "nbaGameId", "date", "playerId", "playerName"
    ],
    "basic_personal": [
        "Minutes", "SecondsPlayed", "Points", "FG2M", "FG2A", "FG3M", "FG3A",
        "FTA", "FtPoints", "Assists", "Rebounds", "OffRebounds", "DefRebounds",
        "Steals", "Blocks", "Turnovers", "PlusMinus", "OffPoss", "DefPoss"
    ],
    "adj_ts_ingredients": [
        "FGA_Recalc", "AdjFGA", "AdjFTA", "AdjTS%", "TS_Recalc",
        "ScoringTOV", "BadPassTOV_Total", "BadPassTurnovers",
        "BadPassOutOfBoundsTurnovers", "Heaves_Est", "NonHeaveArc3FGA",
        "TechFTA_Est", "Technical Free Throw Trips", "SelfOReb", "ZBounds", "ZBoards"
    ],
    "six_factor_inputs": [
        "OffPoss", "DefPoss", "TotalPoss", "Points", "EfgPct", "EfgPct_Recalc",
        "TsPct", "AdjTS%", "Turnovers", "LiveBallTurnovers", "OffRebounds",
        "DefRebounds", "FTA", "FtPoints", "Usage", "ShotQualityAvg"
    ],
    "shot_locations": [
        "AtRimFGA", "AtRimFGM", "AtRimFrequency", "AtRimAccuracy",
        "ShortMidRangeFGA", "ShortMidRangeFGM", "ShortMidRangeFrequency", "ShortMidRangeAccuracy",
        "LongMidRangeFGA", "LongMidRangeFGM", "LongMidRangeFrequency", "LongMidRangeAccuracy",
        "Corner3FGA", "Corner3FGM", "Corner3Frequency", "Corner3Accuracy",
        "Arc3FGA", "Arc3FGM", "Arc3Frequency", "Arc3Accuracy",
        "ShotQualityAvg"
    ],
}

COUNT_FIELDS_SHOULD_NOT_BE_NEGATIVE = [
    "Points", "FG2A", "FG3A", "FGA_Recalc", "FTA", "AdjFGA", "AdjFTA",
    "AtRimFGA", "ShortMidRangeFGA", "LongMidRangeFGA", "Corner3FGA", "Arc3FGA",
    "Turnovers", "ScoringTOV", "OffRebounds", "DefRebounds", "SelfOReb", "ZBounds"
]

def read_json(path):
    try:
        return json.loads(path.read_text())
    except Exception as e:
        return {"_error": repr(e)}

def nonnull(v):
    return v not in [None, "", [], {}]

def is_negative(v):
    try:
        return float(v) < -0.000001
    except Exception:
        return False

def season_file_for_year(year):
    start = int(year) - 1
    return GAMES_DIR / f"{start}_{str(year)[-2:]}.json"

report = {}
all_bad_years = []

for p in sorted(PLAYER_DIR.glob("*.json")):
    year = p.stem
    rows = read_json(p)

    if isinstance(rows, dict) and "_error" in rows:
        report[year] = {"error": rows["_error"]}
        all_bad_years.append(year)
        continue

    if not isinstance(rows, list):
        report[year] = {"error": "not a list"}
        all_bad_years.append(year)
        continue

    by_game = defaultdict(list)
    for r in rows:
        by_game[r.get("gameId")].append(r)

    expected_games = None
    gf = season_file_for_year(year)
    if gf.exists():
        gdata = read_json(gf)
        if isinstance(gdata, list):
            expected_games = len(gdata)

    field_coverage = {}
    for group, fields in EXPECTED.items():
        group_report = {}
        for f in fields:
            present = sum(1 for r in rows if f in r)
            filled = sum(1 for r in rows if nonnull(r.get(f)))
            group_report[f] = {
                "present_rows": present,
                "filled_rows": filled,
                "filled_pct": round(100 * filled / len(rows), 1) if rows else 0
            }
        field_coverage[group] = group_report

    duplicate_games = []
    row_counts = []
    unique_counts = []

    for gid, rs in by_game.items():
        ids = [(r.get("playerId"), r.get("playerName")) for r in rs]
        c = Counter(ids)
        dups = [(k, v) for k, v in c.items() if v > 1 and k != (None, None)]

        row_counts.append(len(rs))
        unique_counts.append(len(set(ids)))

        if dups:
            duplicate_games.append({
                "gameId": gid,
                "rows": len(rs),
                "unique_players": len(set(ids)),
                "duplicates": dups[:10]
            })

    negatives = []
    for r in rows:
        for f in COUNT_FIELDS_SHOULD_NOT_BE_NEGATIVE:
            if f in r and is_negative(r.get(f)):
                negatives.append({
                    "gameId": r.get("gameId"),
                    "playerId": r.get("playerId"),
                    "playerName": r.get("playerName"),
                    "field": f,
                    "value": r.get(f),
                })
                if len(negatives) >= 50:
                    break
        if len(negatives) >= 50:
            break

    missing_core_groups = {}
    for group, fields in EXPECTED.items():
        missing = []
        weak = []
        for f in fields:
            filled = field_coverage[group][f]["filled_rows"]
            if filled == 0:
                missing.append(f)
            elif rows and filled / len(rows) < 0.05:
                weak.append(f)
        missing_core_groups[group] = {
            "missing_completely": missing,
            "very_sparse_under_5pct": weak
        }

    bad = bool(duplicate_games or negatives)
    if bad:
        all_bad_years.append(year)

    report[year] = {
        "file": str(p),
        "rows": len(rows),
        "games_in_output": len(by_game),
        "expected_games_from_games_file": expected_games,
        "min_rows_per_game": min(row_counts) if row_counts else 0,
        "max_rows_per_game": max(row_counts) if row_counts else 0,
        "avg_rows_per_game": round(sum(row_counts) / len(row_counts), 1) if row_counts else 0,
        "min_unique_players_per_game": min(unique_counts) if unique_counts else 0,
        "max_unique_players_per_game": max(unique_counts) if unique_counts else 0,
        "avg_unique_players_per_game": round(sum(unique_counts) / len(unique_counts), 1) if unique_counts else 0,
        "duplicate_games_count": len(duplicate_games),
        "duplicate_examples": duplicate_games[:5],
        "negative_count_examples": negatives[:20],
        "negative_examples_count_capped": len(negatives),
        "missing_core_groups": missing_core_groups,
        "field_coverage": field_coverage,
    }

summary_path = OUT / "low_removed_coverage_report.json"
summary_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

print("Wrote:", summary_path)
print()
print("=== LOW REMOVED COVERAGE SUMMARY ===")

for year, info in sorted(report.items()):
    print("\nYEAR", year)

    if "error" in info:
        print("ERROR:", info["error"])
        continue

    print("rows:", info["rows"])
    print("games:", info["games_in_output"], "expected:", info["expected_games_from_games_file"])
    print("rows/game avg:", info["avg_rows_per_game"], "range:", info["min_rows_per_game"], "-", info["max_rows_per_game"])
    print("unique players/game avg:", info["avg_unique_players_per_game"], "range:", info["min_unique_players_per_game"], "-", info["max_unique_players_per_game"])
    print("duplicate games:", info["duplicate_games_count"])
    print("negative count examples:", info["negative_examples_count_capped"])

    for group, detail in info["missing_core_groups"].items():
        missing = detail["missing_completely"]
        sparse = detail["very_sparse_under_5pct"]
        if missing or sparse:
            print(" ", group)
            if missing:
                print("   missing:", ", ".join(missing[:20]))
            if sparse:
                print("   sparse:", ", ".join(sparse[:20]))

    if info["duplicate_examples"]:
        print(" duplicate example:", info["duplicate_examples"][0])

    if info["negative_count_examples"]:
        print(" negative example:", info["negative_count_examples"][0])

print("\nYears with duplicate or negative-count issues:", ", ".join(all_bad_years) if all_bad_years else "none")
