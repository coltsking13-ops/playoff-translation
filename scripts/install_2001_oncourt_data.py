#!/usr/bin/env python3
import json
import time
from pathlib import Path

ROOT = Path(".")
SRC = ROOT / "public/data/pre2013/player_oncourt_game_all/2001.json"

PACKAGE_FILES = [
    ROOT / "data-package.json",
    ROOT / "data/data-package.json",
    ROOT / "public/data/data-package.embedded.json",
    ROOT / "public/data/data-package.json",
]

if not SRC.exists():
    raise SystemExit(f"Missing source file: {SRC}")

rows = json.loads(SRC.read_text(errors="ignore"))
if isinstance(rows, dict):
    rows = rows.get("rows", rows.get("data", []))

if not isinstance(rows, list):
    raise SystemExit("2001 on-court file is not a list/rows object.")

print(f"Loaded 2001 on-court rows: {len(rows):,}")

def row_key(r):
    return "|".join(str(r.get(k, "")) for k in [
        "year", "gameId", "nbaGameId", "game_id", "playerId", "nbaId", "team", "opponent"
    ])

for package in PACKAGE_FILES:
    if not package.exists():
        print(f"Skipping missing package: {package}")
        continue

    backup = package.with_name(package.name + f".before-2001-oncourt.{int(time.time())}.bak")
    backup.write_text(package.read_text(errors="ignore"))

    data = json.loads(package.read_text(errors="ignore"))

    # Main install buckets. Multiple names make it easier for current/future UI scripts to find it.
    existing = data.get("playerOnCourtGameAll", [])
    if not isinstance(existing, list):
        existing = []

    # Remove old installed 2001 rows from this same source, then append fresh rows.
    kept = []
    for r in existing:
        y = str(r.get("year", r.get("season", "")))
        src = str(r.get("_source", ""))
        if y == "2001" and "pre2013" in src:
            continue
        kept.append(r)

    installed_rows = []
    for r in rows:
        if isinstance(r, dict):
            rr = dict(r)
            rr["year"] = int(rr.get("year", 2001) or 2001)
            rr["_source"] = "pre2013/player_oncourt_game_all/2001.json"
            rr["_leverage"] = "all"
            rr["_label"] = "2001 all-leverage on-court"
            installed_rows.append(rr)

    data["playerOnCourtGameAll"] = kept + installed_rows
    data["pre2013PlayerOnCourtGameAll"] = data["playerOnCourtGameAll"]

    # Add manifest/source note.
    data.setdefault("dataSources", {})
    if isinstance(data["dataSources"], dict):
        data["dataSources"]["pre2013_oncourt_2001"] = {
            "path": "public/data/pre2013/player_oncourt_game_all/2001.json",
            "rows": len(installed_rows),
            "leverage": "all",
            "note": "2001 all-leverage player on-court team context"
        }

    # Best-effort enrichment of playerGames rows so old UI can read common on-court fields.
    on_by_key = {}
    for r in installed_rows:
        gid = str(r.get("gameId") or r.get("nbaGameId") or r.get("game_id") or "")
        pid = str(r.get("playerId") or r.get("nbaId") or r.get("PLAYER_ID") or "")
        pname = str(r.get("playerName") or r.get("name") or "").lower().strip()
        if gid and (pid or pname):
            on_by_key[(gid, pid, pname)] = r

    pg = data.get("playerGames", [])
    enriched = 0

    if isinstance(pg, list):
        for g in pg:
            if not isinstance(g, dict):
                continue

            y = str(g.get("year", g.get("season", "")))
            if y != "2001":
                continue

            gid = str(g.get("gameId") or g.get("nbaGameId") or g.get("game_id") or "")
            pid = str(g.get("playerId") or g.get("nbaId") or g.get("PLAYER_ID") or "")
            pname = str(g.get("playerName") or g.get("name") or "").lower().strip()

            match = None
            for key, r in on_by_key.items():
                kgid, kpid, kpname = key
                if gid and kgid == gid and ((pid and kpid == pid) or (pname and kpname == pname)):
                    match = r
                    break

            if not match:
                continue

            g["hasOnCourtAllLeverage"] = True
            g["onCourtLeverage"] = "all"
            g["onCourtSource"] = "pre2013/player_oncourt_game_all/2001.json"

            # Copy common fields if present.
            copy_pairs = {
                "onTeamORTG": ["onTeamORTG", "teamORTG", "ORTG", "OffRtg", "offRtg"],
                "onTeamDRTG": ["onTeamDRTG", "teamDRTG", "DRTG", "DefRtg", "defRtg"],
                "onTeamNET": ["onTeamNET", "teamNET", "NET", "NetRtg", "netRtg"],
                "onOffPoss": ["onOffPoss", "OffPoss", "offPoss", "off_poss"],
                "onDefPoss": ["onDefPoss", "DefPoss", "defPoss", "def_poss"],
                "onTeamPts": ["onTeamPts", "TeamPoints", "pointsFor", "PTS"],
                "onOppPts": ["onOppPts", "OpponentPoints", "pointsAgainst", "oppPTS"],
            }

            for out_key, keys in copy_pairs.items():
                for k in keys:
                    if k in match and match[k] not in [None, ""]:
                        g[out_key] = match[k]
                        break

            enriched += 1

    package.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False))
    print(f"Installed into {package}: +{len(installed_rows):,} rows | enriched playerGames: {enriched:,}")
    print(f"Backup: {backup}")

print("DONE installing 2001 on-court data.")
