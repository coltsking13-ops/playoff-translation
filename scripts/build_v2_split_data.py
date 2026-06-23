#!/usr/bin/env python3
import json
import re
from pathlib import Path

SRC = Path("data-package.json")
OUT = Path("v2/data")
PLAYERS_DIR = OUT / "players"
INDEX_DIR = OUT / "indexes"
REPORT_DIR = Path("v2/reports")

PLAYERS_DIR.mkdir(parents=True, exist_ok=True)
INDEX_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)

def slugify(name):
    s = str(name or "").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "unknown-player"

def get_name(r):
    return str(r.get("playerName") or r.get("PLAYER_NAME") or r.get("name") or "").strip()

def get_year(r):
    return str(r.get("year") or r.get("season") or r.get("SEASON") or "").strip()

def get_team(r):
    return str(r.get("team") or r.get("TEAM") or r.get("teamAbbr") or r.get("TEAM_ABBREVIATION") or "").strip()

def get_pid(r):
    return str(r.get("playerId") or r.get("PLAYER_ID") or r.get("nbaId") or r.get("NBA_ID") or "").strip()

data = json.loads(SRC.read_text(errors="ignore"))

player_games = data.get("playerGames", [])
player_series = data.get("playerSeries", data.get("seriesPlayers", []))

players = {}

def ensure(row):
    name = get_name(row)
    if not name:
        return None

    slug = slugify(name)

    if slug not in players:
        players[slug] = {
            "slug": slug,
            "name": name,
            "playerIds": set(),
            "teams": set(),
            "years": set(),
            "games": [],
            "series": [],
        }

    p = players[slug]

    pid = get_pid(row)
    team = get_team(row)
    year = get_year(row)

    if pid:
        p["playerIds"].add(pid)
    if team:
        p["teams"].add(team)
    if year:
        p["years"].add(year)

    return p

for r in player_games:
    if isinstance(r, dict):
        p = ensure(r)
        if p:
            p["games"].append(r)

for r in player_series:
    if isinstance(r, dict):
        p = ensure(r)
        if p:
            p["series"].append(r)

index = []
sizes = []

for slug, p in sorted(players.items(), key=lambda kv: kv[1]["name"].lower()):
    years = sorted(p["years"], key=lambda x: int(x) if x.isdigit() else 9999)
    teams = sorted(p["teams"])
    ids = sorted(p["playerIds"])

    payload = {
        "meta": {
            "slug": slug,
            "name": p["name"],
            "playerIds": ids,
            "teams": teams,
            "years": years,
            "gameCount": len(p["games"]),
            "seriesCount": len(p["series"]),
            "source": "data-package.json",
            "dataMode": "Base / All-Leverage",
        },
        "games": p["games"],
        "series": p["series"],
    }

    out_file = PLAYERS_DIR / f"{slug}.json"
    out_file.write_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
    sizes.append((out_file.stat().st_size, out_file.name))

    index.append({
        "slug": slug,
        "name": p["name"],
        "playerIds": ids[:5],
        "teams": teams,
        "yearMin": years[0] if years else "",
        "yearMax": years[-1] if years else "",
        "gameCount": len(p["games"]),
        "seriesCount": len(p["series"]),
        "file": f"players/{slug}.json",
    })

(INDEX_DIR / "players.json").write_text(json.dumps(index, separators=(",", ":"), ensure_ascii=False))

summary = {
    "source": str(SRC),
    "players": len(index),
    "playerGames": len(player_games),
    "playerSeries": len(player_series),
    "largestPlayerFiles": [
        {"file": name, "mb": round(size / 1024 / 1024, 2)}
        for size, name in sorted(sizes, reverse=True)[:25]
    ],
}

(REPORT_DIR / "split_data_summary.json").write_text(json.dumps(summary, indent=2))

print("V2 split complete.")
print("players:", len(index))
print("playerGames:", len(player_games))
print("playerSeries:", len(player_series))
print("index:", INDEX_DIR / "players.json")
print("players folder:", PLAYERS_DIR)
print("")
print("Largest files:")
for x in summary["largestPlayerFiles"][:10]:
    print(x["file"], x["mb"], "MB")
