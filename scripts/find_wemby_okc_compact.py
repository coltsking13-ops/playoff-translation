#!/usr/bin/env python3
import json
from pathlib import Path

FILES = [
    Path("public/data/data-package.embedded.json"),
    Path("public/data/data-package.json"),
    Path("data-package.json"),
    Path("data/data-package.json"),
    Path("public/data/pbpstats/player_game_low_removed/2026.json"),
    Path("public/data/pbpstats/player_game_low_removed/2025.json"),
]

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

def get(row, names):
    for n in names:
        if n in row and row[n] not in [None, ""]:
            return row[n]
    return ""

def is_wemby(row):
    blob = " ".join(str(v) for v in row.values()).lower()
    return "wemb" in blob or "victor wembanyama" in blob or "1641705" in blob

def is_okc(row):
    blob = " ".join(str(v) for v in row.values()).upper()
    return "OKC" in blob or "THUNDER" in blob or "1610612760" in blob

def summarize(row):
    return {
        "player": get(row, ["playerName","PLAYER_NAME","name"]),
        "playerId": get(row, ["playerId","PLAYER_ID","nbaId","NBA_ID"]),
        "year": get(row, ["year","season","SEASON"]),
        "date": get(row, ["date","gameDate","GAME_DATE"]),
        "gameId": get(row, ["gameId","GAME_ID","nbaGameId","nbaGameID","game_id","nba_game_id"]),
        "nbaGameId": get(row, ["nbaGameId","nbaGameID","NBA_GAME_ID"]),
        "gameRowId": get(row, ["gameRowId"]),
        "round": get(row, ["round","series","playoffRound"]),
        "seriesCode": get(row, ["seriesCode"]),
        "team": get(row, ["team","TEAM","teamAbbr"]),
        "opp": get(row, ["opponent","opp","OPP","opponentTeam"]),
        "MIN": get(row, ["MIN","minutes"]),
        "PTS": get(row, ["PTS","points"]),
    }

wemby = []
okc = []

for p in FILES:
    if not p.exists():
        continue

    obj = read_json(p)
    if obj is None:
        continue

    for row in walk(obj):
        if not isinstance(row, dict):
            continue

        if is_wemby(row):
            s = summarize(row)
            s["_file"] = str(p)
            wemby.append(s)
            if is_okc(row):
                okc.append(s)

print("=" * 90)
print("WEMBY ROWS:", len(wemby))
print("WEMBY + OKC ROWS:", len(okc))
print("=" * 90)

print("\nWEMBY + OKC ROWS:")
if not okc:
    print("NONE FOUND")
else:
    for i, r in enumerate(okc[:80], 1):
        print(f"\n--- {i} ---")
        for k, v in r.items():
            if v not in ["", None]:
                print(f"{k}: {v}")

print("\nWEMBY ROW SAMPLE:")
for i, r in enumerate(wemby[:40], 1):
    print(f"\n--- {i} ---")
    for k, v in r.items():
        if v not in ["", None]:
            print(f"{k}: {v}")

print("\nGAME IDS FOUND:")
ids = []
for r in okc:
    gid = r.get("gameId") or r.get("nbaGameId")
    if gid and gid not in ids:
        ids.append(gid)

if ids:
    for gid in ids:
        print(gid)
else:
    print("No real gameId found for Wemby + OKC in current local files.")
    print("That means the 2026 Wemby game rows probably are not built/merged yet.")
