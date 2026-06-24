#!/usr/bin/env python3
import json
from pathlib import Path
from collections import defaultdict

PLAYERS_DIR = Path("v2/data/players")
OUT = Path("v2/data/indexes/team-context.json")
OUT.parent.mkdir(parents=True, exist_ok=True)

def num(v):
    try:
        if v in [None, "", "—"]:
            return None
        n = float(v)
        if 0 < n < 1:
            n *= 100
        return n
    except Exception:
        return None

def get(row, keys):
    for k in keys:
        if isinstance(row, dict) and row.get(k) not in [None, "", "—"]:
            return row.get(k)
    return None

team_games = {}

for file in PLAYERS_DIR.glob("*.json"):
    data = json.loads(file.read_text(errors="ignore"))

    for row in data.get("games", []):
        year = str(get(row, ["year", "season", "SEASON"]) or "")
        game_id = str(get(row, ["gameId", "GAME_ID", "gid"]) or "")
        team = str(get(row, ["team", "TEAM", "teamAbbr", "TEAM_ABBREVIATION"]) or "")
        opp = str(get(row, ["opponent", "opp", "OPP"]) or "")

        if not year or not game_id or not team or not opp:
            continue

        key = (year, game_id, team)

        if key not in team_games:
            team_games[key] = {
                "year": year,
                "gameId": game_id,
                "team": team,
                "opp": opp,
                "teamTS": num(get(row, ["teamTS"])),
                "teamEFG": num(get(row, ["teamEFG"])),
                "teamFTr": num(get(row, ["teamFTr"])),
                "teamTOVPct": num(get(row, ["teamTOVPct"])),
                "teamORTG": num(get(row, ["teamORTG", "teamOffRtg", "ORTG"])),
                "teamDRTG": num(get(row, ["teamDRTG", "teamDefRtg", "DRTG"])),
            }

allowed = defaultdict(lambda: defaultdict(lambda: {
    "games": 0,
    "allowedTS": [],
    "allowedEFG": [],
    "allowedFTr": [],
    "allowedTOVPct": [],
    "allowedORTG": [],
    "oppOffORTG": [],
}))

for tg in team_games.values():
    year = tg["year"]
    opponent_defense = tg["opp"]

    bucket = allowed[year][opponent_defense]
    bucket["games"] += 1

    if tg["teamTS"] is not None:
        bucket["allowedTS"].append(tg["teamTS"])
    if tg["teamEFG"] is not None:
        bucket["allowedEFG"].append(tg["teamEFG"])
    if tg["teamFTr"] is not None:
        bucket["allowedFTr"].append(tg["teamFTr"])
    if tg["teamTOVPct"] is not None:
        bucket["allowedTOVPct"].append(tg["teamTOVPct"])
    if tg["teamORTG"] is not None:
        bucket["allowedORTG"].append(tg["teamORTG"])

# opponent offense = that team’s own offensive rating in its team-games
for tg in team_games.values():
    year = tg["year"]
    team = tg["team"]
    bucket = allowed[year][team]
    if tg["teamORTG"] is not None:
        bucket["oppOffORTG"].append(tg["teamORTG"])

def avg(vals):
    vals = [v for v in vals if v is not None]
    return round(sum(vals) / len(vals), 3) if vals else None

out = {"byYearOpponent": {}}

for year, teams in sorted(allowed.items()):
    out["byYearOpponent"][year] = {}

    for team, row in sorted(teams.items()):
        out["byYearOpponent"][year][team] = {
            "games": row["games"],
            "oppAllowedTS": avg(row["allowedTS"]),
            "oppAllowedEFG": avg(row["allowedEFG"]),
            "oppAllowedFTr": avg(row["allowedFTr"]),
            "oppAllowedTOVPct": avg(row["allowedTOVPct"]),
            "oppAllowedORTG": avg(row["allowedORTG"]),
            "oppOffORTG": avg(row["oppOffORTG"]),
        }

OUT.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False))

print("Wrote", OUT)
print("Years:", ", ".join(sorted(out["byYearOpponent"].keys())))

# validation target
ctx = out["byYearOpponent"].get("2015", {}).get("GSW")
print("\n2015 GSW context:", ctx)

harden = PLAYERS_DIR / "james-harden.json"
if harden.exists():
    data = json.loads(harden.read_text(errors="ignore"))
    for s in data.get("series", []):
        year = str(get(s, ["year", "season"]) or "")
        opp = str(get(s, ["opponent", "opp", "OPP"]) or "")
        if year == "2015" and opp in ["GSW", "GS"]:
            player_ts = num(get(s, ["TS", "TS%", "tsPct"]))
            opp_ts = ctx.get("oppAllowedTS") if ctx else None
            print("\nHarden 2015 vs GSW")
            print("Player TS:", player_ts)
            print("GSW playoff allowed TS:", opp_ts)
            print("rAdj TS:", round(player_ts - opp_ts, 1) if player_ts is not None and opp_ts is not None else None)
            print("Row old oppAllowedTS:", get(s, ["oppAllowedTS"]))
