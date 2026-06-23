import json
from pathlib import Path
from collections import Counter, defaultdict

data = json.loads(Path("data-package.json").read_text())

TABLES = {
    "playerGames": data.get("playerGames", []),
    "playerSeries": data.get("playerSeries", []),
    "playerSeasons": data.get("playerSeasons", []),
    "teamGameContext": data.get("teamGameContext", []),
    "teamSeriesContext": data.get("teamSeriesContext", []),
    "teamRegularSeasonBenchmarks": data.get("teamRegularSeasonBenchmarks", []),
}

PLAYER_GAME_CORE = [
    "year", "gameId", "nbaGameId", "date", "playerId", "playerName", "team", "opponent",
    "MIN", "PTS", "REB", "AST", "STL", "BLK", "TOV",
    "FGM", "FGA", "FG3M", "FG3A", "FTA",
    "TS%", "eFG%",
    "ORTG", "DRTG", "NET",
    "rORTG", "rDRTG", "rNET",
    "PTS/75", "REB/75", "AST/75", "TOV/75",
    "USG%", "POSS",
    "teamORTG", "teamDRTG", "teamNET",
    "oppTeamORTG", "oppTeamDRTG", "oppTeamNET",
]

PLAYER_SERIES_CORE = [
    "year", "seriesCode", "playerId", "playerName", "team", "opponent",
    "MIN", "PTS", "REB", "AST", "STL", "BLK", "TOV",
    "FGM", "FGA", "FG3M", "FG3A", "FTA",
    "TS%", "eFG%",
    "ORTG", "DRTG", "NET",
    "rORTG", "rDRTG", "rNET",
    "PTS/75", "REB/75", "AST/75", "TOV/75",
    "USG%", "POSS",
]

PLAYER_SEASON_CORE = [
    "year", "playerId", "playerName", "team",
    "MIN", "PTS", "REB", "AST", "STL", "BLK", "TOV",
    "FGM", "FGA", "FG3M", "FG3A", "FTA",
    "TS%", "eFG%",
    "ORTG", "DRTG", "NET",
    "rORTG", "rDRTG", "rNET",
    "PTS/75", "REB/75", "AST/75", "TOV/75",
    "USG%", "POSS",
]

TEAM_CONTEXT_CORE = [
    "year", "gameId", "seriesCode", "team", "opponent",
    "teamORTG", "teamDRTG", "teamNET",
    "oppTeamORTG", "oppTeamDRTG", "oppTeamNET",
    "ORTG", "DRTG", "NET", "PACE",
]

def in_range(rows):
    out = []
    for r in rows:
        try:
            y = int(r.get("year", 0) or r.get("SEASON", 0) or 0)
        except Exception:
            y = 0
        if 2001 <= y <= 2012:
            out.append(r)
    return out

def field_report(name, rows, fields):
    rows = in_range(rows)
    print("\n" + "="*90)
    print(name)
    print("rows 2001-2012:", len(rows))

    years = sorted({int(r.get("year", 0) or 0) for r in rows if str(r.get("year", "")).isdigit()})
    print("years:", years)

    if not rows:
        print("NO ROWS")
        return

    missing = []
    sparse = []

    for f in fields:
        present = sum(1 for r in rows if f in r)
        filled = sum(1 for r in rows if r.get(f) not in [None, "", [], {}])
        pct = 100 * filled / len(rows)

        status = "OK"
        if filled == 0:
            status = "MISSING"
            missing.append(f)
        elif pct < 25:
            status = "SPARSE"
            sparse.append(f)

        print(f"{f:24s} filled={filled:<7} pct={pct:5.1f}% {status}")

    print("missing:", missing if missing else "none")
    print("sparse:", sparse if sparse else "none")

field_report("playerGames core non-shot/non-sixfactor", TABLES["playerGames"], PLAYER_GAME_CORE)
field_report("playerSeries core non-shot/non-sixfactor", TABLES["playerSeries"], PLAYER_SERIES_CORE)
field_report("playerSeasons core non-shot/non-sixfactor", TABLES["playerSeasons"], PLAYER_SEASON_CORE)
field_report("teamGameContext core context", TABLES["teamGameContext"], TEAM_CONTEXT_CORE)
field_report("teamSeriesContext core context", TABLES["teamSeriesContext"], TEAM_CONTEXT_CORE)

# Quick counts by year for most important tables
print("\n" + "="*90)
print("COUNTS BY YEAR")

for name in ["playerGames", "playerSeries", "playerSeasons", "teamGameContext", "teamSeriesContext"]:
    rows = in_range(TABLES[name])
    c = Counter(int(r.get("year", 0) or 0) for r in rows)
    print("\n", name)
    for y in range(2001, 2013):
        print(y, c.get(y, 0))
