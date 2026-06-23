#!/usr/bin/env python3
import json
from pathlib import Path

SRC_FILES = [
    Path("data-package.json"),
    Path("data/data-package.json"),
    Path("public/data/data-package.embedded.json"),
]

OUT = Path("public/data/player-search-index.json")

def read_json(p):
    try:
        return json.loads(p.read_text(errors="ignore"))
    except Exception:
        return None

def walk(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk(v)

def get(row, keys):
    for k in keys:
        if k in row and row[k] not in [None, ""]:
            return row[k]
    return ""

players = {}

for src in SRC_FILES:
    if not src.exists():
        continue

    data = read_json(src)
    if not data:
        continue

    for row in walk(data):
        if not isinstance(row, dict):
            continue

        name = str(get(row, ["playerName", "PLAYER_NAME", "name", "fullName"])).strip()
        if not name or len(name) < 3 or len(name) > 60:
            continue

        pid = str(get(row, ["playerId", "PLAYER_ID", "nbaId", "NBA_ID", "id"])).strip()
        team = str(get(row, ["team", "TEAM", "teamAbbr", "TEAM_ABBREVIATION"])).strip()
        year = str(get(row, ["year", "season", "SEASON"])).strip()

        key = name.lower()

        if key not in players:
            players[key] = {
                "name": name,
                "id": pid,
                "teams": set(),
                "years": set(),
                "games": 0,
            }

        if pid and not players[key]["id"]:
            players[key]["id"] = pid

        if team:
            players[key]["teams"].add(team)

        if year and year.isdigit():
            players[key]["years"].add(year)

        if row.get("gameId") or row.get("GAME_ID"):
            players[key]["games"] += 1

out = []

for p in players.values():
    years = sorted(p["years"])
    teams = sorted(p["teams"])

    out.append({
        "name": p["name"],
        "id": p["id"],
        "teams": teams[:10],
        "yearMin": years[0] if years else "",
        "yearMax": years[-1] if years else "",
        "games": p["games"],
    })

out.sort(key=lambda x: (-x["games"], x["name"]))

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False))

print("Built:", OUT)
print("Players:", len(out))
