#!/usr/bin/env python3
import json
import re
from pathlib import Path
from collections import defaultdict

SRC = Path("public/data/data-package.embedded.json")
PLAYERS_DIR = Path("v2/data/players")
REPORT = Path("v2/reports/merge_embedded_adjts_report.json")
REPORT.parent.mkdir(parents=True, exist_ok=True)

FIELDS = [
    "AdjTS%",
    "rAdjTS",
    "AdjFGA",
    "AdjFTA",
    "ScoringTOV",
    "Heaves",
    "ZBoards",
    "TechFTA",
    "OppRSAdjTSAllowed",
    "AdjTS_source",
    "relativeSource",
]

def slugify(name):
    s = str(name or "").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "unknown-player"

def get(row, keys):
    for k in keys:
        if isinstance(row, dict) and row.get(k) not in [None, "", "—"]:
            return row.get(k)
    return None

def key_game(row):
    return (
        str(get(row, ["playerId", "PLAYER_ID"]) or ""),
        str(get(row, ["year", "season", "SEASON"]) or ""),
        str(get(row, ["gameId", "GAME_ID", "gid"]) or ""),
        str(get(row, ["team", "TEAM", "teamAbbr", "TEAM_ABBREVIATION"]) or ""),
        str(get(row, ["opponent", "opp", "OPP"]) or ""),
    )

def key_series(row):
    return (
        str(get(row, ["playerId", "PLAYER_ID"]) or ""),
        str(get(row, ["year", "season", "SEASON"]) or ""),
        str(get(row, ["team", "TEAM", "teamAbbr", "TEAM_ABBREVIATION"]) or ""),
        str(get(row, ["opponent", "opp", "OPP"]) or ""),
        str(get(row, ["seriesCode", "series", "round"]) or ""),
    )

print("Loading", SRC)
src = json.loads(SRC.read_text(errors="ignore"))

src_games = src.get("playerGames", [])
src_series = src.get("playerSeries", src.get("seriesPlayers", []))

game_idx = {}
series_idx = {}

for r in src_games:
    if isinstance(r, dict):
        k = key_game(r)
        if any(r.get(f) not in [None, "", "—"] for f in FIELDS):
            game_idx[k] = {f: r.get(f) for f in FIELDS if f in r}

for r in src_series:
    if isinstance(r, dict):
        k = key_series(r)
        if any(r.get(f) not in [None, "", "—"] for f in FIELDS):
            series_idx[k] = {f: r.get(f) for f in FIELDS if f in r}

report = {
    "srcGamesIndexed": len(game_idx),
    "srcSeriesIndexed": len(series_idx),
    "playersTouched": 0,
    "gamesUpdated": 0,
    "seriesUpdated": 0,
    "missingGameMatches": 0,
    "missingSeriesMatches": 0,
}

for p in sorted(PLAYERS_DIR.glob("*.json")):
    data = json.loads(p.read_text(errors="ignore"))
    touched = False

    for r in data.get("games", []):
        k = key_game(r)
        patch = game_idx.get(k)

        if not patch:
            report["missingGameMatches"] += 1
            continue

        for f, v in patch.items():
            r[f] = v

        touched = True
        report["gamesUpdated"] += 1

    for r in data.get("series", []):
        k = key_series(r)
        patch = series_idx.get(k)

        # fallback if seriesCode mismatch/blank
        if not patch:
            loose = (
                str(get(r, ["playerId", "PLAYER_ID"]) or ""),
                str(get(r, ["year", "season", "SEASON"]) or ""),
                str(get(r, ["team", "TEAM", "teamAbbr", "TEAM_ABBREVIATION"]) or ""),
                str(get(r, ["opponent", "opp", "OPP"]) or ""),
                "",
            )
            patch = series_idx.get(loose)

        if not patch:
            report["missingSeriesMatches"] += 1
            continue

        for f, v in patch.items():
            r[f] = v

        touched = True
        report["seriesUpdated"] += 1

    if touched:
        p.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False))
        report["playersTouched"] += 1

REPORT.write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))

# direct verification
harden = PLAYERS_DIR / "james-harden.json"
if harden.exists():
    data = json.loads(harden.read_text(errors="ignore"))
    print("\nHarden 2015 GSW after merge:")
    for r in data.get("series", []):
        if str(get(r, ["year", "season"]) or "") == "2015" and str(get(r, ["opponent", "opp"]) or "") == "GSW":
            print({
                "TS%": r.get("TS%"),
                "AdjTS%": r.get("AdjTS%"),
                "rTS": r.get("rTS"),
                "rAdjTS": r.get("rAdjTS"),
                "AdjFGA": r.get("AdjFGA"),
                "AdjFTA": r.get("AdjFTA"),
                "AdjTS_source": r.get("AdjTS_source"),
            })
