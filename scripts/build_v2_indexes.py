#!/usr/bin/env python3
import json
from pathlib import Path
from collections import defaultdict

PLAYERS_DIR = Path("v2/data/players")
INDEX_DIR = Path("v2/data/indexes")
INDEX_DIR.mkdir(parents=True, exist_ok=True)

def num(v):
    try:
        if v in [None, "", "—"]:
            return None
        return float(v)
    except Exception:
        return None

def get(row, keys):
    for k in keys:
        if isinstance(row, dict) and row.get(k) not in [None, "", "—"]:
            return row.get(k)
    return None

players = []
seasons = defaultdict(lambda: {"year": "", "players": set(), "teams": set(), "games": 0, "series": 0})
teams = defaultdict(lambda: {"team": "", "players": set(), "years": set(), "games": 0, "series": 0})

leader_games = []
leader_series = []

for file in PLAYERS_DIR.glob("*.json"):
    pdata = json.loads(file.read_text(errors="ignore"))
    meta = pdata.get("meta", {})
    name = meta.get("name", file.stem)
    slug = meta.get("slug", file.stem)

    players.append({
        "name": name,
        "slug": slug,
        "file": f"players/{file.name}",
        "teams": meta.get("teams", []),
        "years": meta.get("years", []),
        "gameCount": meta.get("gameCount", 0),
        "seriesCount": meta.get("seriesCount", 0),
    })

    for g in pdata.get("games", []):
        year = str(get(g, ["year", "season", "SEASON"]) or "")
        team = str(get(g, ["team", "TEAM", "teamAbbr", "TEAM_ABBREVIATION"]) or "")
        pts = num(get(g, ["PTS", "points"]))
        ts = num(get(g, ["TS", "TS%", "tsPct"]))
        ortg = num(get(g, ["ORTG", "offRtg", "OFF_RATING"]))

        if year:
            seasons[year]["year"] = year
            seasons[year]["players"].add(name)
            seasons[year]["games"] += 1
            if team:
                seasons[year]["teams"].add(team)

        if team:
            teams[team]["team"] = team
            teams[team]["players"].add(name)
            teams[team]["games"] += 1
            if year:
                teams[team]["years"].add(year)

        if pts is not None:
            leader_games.append({
                "name": name,
                "slug": slug,
                "year": year,
                "team": team,
                "opponent": get(g, ["opponent", "opp", "OPP"]),
                "PTS": pts,
                "TS": ts,
                "ORTG": ortg,
                "gameId": get(g, ["gameId", "GAME_ID"]),
            })

    for s in pdata.get("series", []):
        year = str(get(s, ["year", "season", "SEASON"]) or "")
        team = str(get(s, ["team", "TEAM", "teamAbbr", "TEAM_ABBREVIATION"]) or "")
        pts = num(get(s, ["PTS", "points"]))
        ts = num(get(s, ["TS", "TS%", "tsPct"]))
        ortg = num(get(s, ["ORTG", "offRtg", "OFF_RATING"]))

        if year:
            seasons[year]["year"] = year
            seasons[year]["series"] += 1

        if team:
            teams[team]["series"] += 1

        if pts is not None:
            leader_series.append({
                "name": name,
                "slug": slug,
                "year": year,
                "team": team,
                "opponent": get(s, ["opponent", "opp", "OPP"]),
                "seriesCode": get(s, ["seriesCode", "series"]),
                "PTS": pts,
                "TS": ts,
                "ORTG": ortg,
                "GP": get(s, ["GP", "games"]),
            })

season_index = []
for y, row in seasons.items():
    season_index.append({
        "year": y,
        "playerCount": len(row["players"]),
        "teamCount": len(row["teams"]),
        "games": row["games"],
        "series": row["series"],
        "teams": sorted(row["teams"]),
    })

team_index = []
for t, row in teams.items():
    team_index.append({
        "team": t,
        "playerCount": len(row["players"]),
        "years": sorted(row["years"]),
        "games": row["games"],
        "series": row["series"],
    })

leaderboards = {
    "topScoringGames": sorted(leader_games, key=lambda r: r["PTS"], reverse=True)[:250],
    "topScoringSeries": sorted(leader_series, key=lambda r: r["PTS"], reverse=True)[:250],
    "topTSGames": sorted([r for r in leader_games if r["TS"] is not None], key=lambda r: r["TS"], reverse=True)[:250],
    "topTSSeries": sorted([r for r in leader_series if r["TS"] is not None], key=lambda r: r["TS"], reverse=True)[:250],
    "topORTGGames": sorted([r for r in leader_games if r["ORTG"] is not None], key=lambda r: r["ORTG"], reverse=True)[:250],
    "topORTGSeries": sorted([r for r in leader_series if r["ORTG"] is not None], key=lambda r: r["ORTG"], reverse=True)[:250],
}

(INDEX_DIR / "seasons.json").write_text(json.dumps(sorted(season_index, key=lambda r: r["year"]), separators=(",", ":"), ensure_ascii=False))
(INDEX_DIR / "teams.json").write_text(json.dumps(sorted(team_index, key=lambda r: r["team"]), separators=(",", ":"), ensure_ascii=False))
(INDEX_DIR / "leaderboards.json").write_text(json.dumps(leaderboards, separators=(",", ":"), ensure_ascii=False))

print("Built V2 indexes:")
print("seasons:", len(season_index))
print("teams:", len(team_index))
print("leaderboard game rows:", len(leader_games))
print("leaderboard series rows:", len(leader_series))
