#!/usr/bin/env python3
import json
from pathlib import Path
from collections import defaultdict

PLAYERS_DIR = Path("v2/data/players")
OUT = Path("v2/data/indexes/season-context.json")
OUT.parent.mkdir(parents=True, exist_ok=True)

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

by_year = defaultdict(lambda: {
    "points": 0.0,
    "fga": 0.0,
    "fta": 0.0,
    "playerRows": 0,
    "weightedTS": None,
    "oppAllowedTSValues": []
})

for file in PLAYERS_DIR.glob("*.json"):
    pdata = json.loads(file.read_text(errors="ignore"))

    for row in pdata.get("games", []):
        year = str(get(row, ["year", "season", "SEASON"]) or "")
        if not year:
            continue

        pts = num(get(row, ["PTS", "points"]))
        fga = num(get(row, ["FGA", "fga"]))
        fta = num(get(row, ["FTA", "fta"]))
        opp_ts = num(get(row, ["oppAllowedTS", "opponentAllowedTS", "oppTSAllowed", "defenseAllowedTS"]))

        by_year[year]["playerRows"] += 1

        if pts is not None:
            by_year[year]["points"] += pts
        if fga is not None:
            by_year[year]["fga"] += fga
        if fta is not None:
            by_year[year]["fta"] += fta
        if opp_ts is not None:
            by_year[year]["oppAllowedTSValues"].append(opp_ts)

out = {"byYear": {}}

for year, row in sorted(by_year.items()):
    denom = 2 * (row["fga"] + 0.44 * row["fta"])
    league_ts = 100 * row["points"] / denom if denom else None

    opp_vals = row["oppAllowedTSValues"]
    avg_opp_allowed_ts = sum(opp_vals) / len(opp_vals) if opp_vals else None

    out["byYear"][year] = {
        "leagueTS": round(league_ts, 3) if league_ts is not None else None,
        "avgOppAllowedTS": round(avg_opp_allowed_ts, 3) if avg_opp_allowed_ts is not None else None,
        "playerRows": row["playerRows"],
        "points": round(row["points"], 3),
        "fga": round(row["fga"], 3),
        "fta": round(row["fta"], 3),
    }

OUT.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False))

print("Wrote", OUT)
for y, r in out["byYear"].items():
    print(y, "leagueTS:", r["leagueTS"], "rows:", r["playerRows"])
