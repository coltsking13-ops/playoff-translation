#!/usr/bin/env python3
import json
import re
from pathlib import Path

ROOT = Path(".")

SEARCH_FILES = [
    "public/data/data-package.embedded.json",
    "public/data/data-package.json",
    "data-package.json",
    "data/data-package.json",
    "public/data/pbpstats/player_game_low_removed/2026.json",
    "public/data/pbpstats/player_game_low_removed/2025.json",
]

def read_json(p):
    try:
        return json.loads(p.read_text(errors="ignore"))
    except Exception as e:
        return None

def walk(obj, path="root"):
    if isinstance(obj, dict):
        yield path, obj
        for k, v in obj.items():
            yield from walk(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk(v, f"{path}[{i}]")

def has_wemby(row):
    blob = " ".join(str(v) for v in row.values()).lower()
    return (
        "wemb" in blob or
        "victor" in blob or
        "1641705" in blob
    )

def has_okc(row):
    blob = " ".join(str(v) for v in row.values()).upper()
    return "OKC" in blob or "THUNDER" in blob or "1610612760" in blob

def has_game_id(row):
    for k in row:
        lk = str(k).lower()
        if "game" in lk and ("id" in lk or lk in ["gameid", "game_id"]):
            if row[k] not in [None, "", "null"]:
                return True
    return False

def game_id_value(row):
    for k in row:
        lk = str(k).lower()
        if "game" in lk and ("id" in lk or lk in ["gameid", "game_id"]):
            if row[k] not in [None, "", "null"]:
                return k, row[k]
    return None, None

def summarize(row):
    keys_want = [
        "year","season","date","gameDate","GAME_DATE",
        "gameId","GAME_ID","nbaGameId","game_id","nba_game_id",
        "seriesGame","gameInSeries","gameNumber","seriesGameNumber","gameLabel",
        "round","series","opponent","opp","OPP","team","TEAM",
        "playerName","PLAYER_NAME","name","playerId","PLAYER_ID","nbaId","NBA_ID",
        "PTS","points","MIN","minutes"
    ]

    out = {}
    for k in keys_want:
        if k in row:
            out[k] = row[k]

    if not out:
        for k in list(row.keys())[:30]:
            out[k] = row[k]

    return out

matches = []
gameid_matches = []

for file in SEARCH_FILES:
    p = ROOT / file
    if not p.exists():
        continue

    obj = read_json(p)
    if obj is None:
        continue

    for path, row in walk(obj):
        if not isinstance(row, dict):
            continue

        if has_wemby(row) and has_okc(row):
            item = {
                "file": file,
                "path": path,
                "has_game_id": has_game_id(row),
                "summary": summarize(row),
                "keys": list(row.keys())[:80],
            }
            matches.append(item)
            if has_game_id(row):
                gameid_matches.append(item)

print("=" * 80)
print("WEMBY + OKC ROWS FOUND:", len(matches))
print("WEMBY + OKC ROWS WITH GAME ID:", len(gameid_matches))
print("=" * 80)

print("\nROWS WITH GAME ID:")
for i, m in enumerate(gameid_matches[:30], 1):
    print("\n---", i, "---")
    print("file:", m["file"])
    print("path:", m["path"])
    print("summary:")
    for k, v in m["summary"].items():
        print(f"  {k}: {v}")
    print("keys:", ", ".join(m["keys"][:40]))

print("\nALL WEMBY + OKC ROWS SAMPLE:")
for i, m in enumerate(matches[:25], 1):
    print("\n---", i, "---")
    print("file:", m["file"])
    print("path:", m["path"])
    print("has_game_id:", m["has_game_id"])
    print("summary:")
    for k, v in m["summary"].items():
        print(f"  {k}: {v}")
    print("keys:", ", ".join(m["keys"][:50]))

if not gameid_matches:
    print("\nNO GAME ID FOUND IN CURRENT LOCAL FILES.")
    print("That means 2026 Wemby game rows might not be built/merged yet, or the data package only has series/team rows.")
    print("Next step: search the 2026 build output once 13-26 finishes, or manually pass the NBA GameId into the WOWY script.")
