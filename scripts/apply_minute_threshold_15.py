#!/usr/bin/env python3
import json
import time
import shutil
from pathlib import Path
from collections import defaultdict

THRESHOLD = 15.0

PACKAGE_FILES = [
    Path("data-package.json"),
    Path("data/data-package.json"),
    Path("public/data/data-package.embedded.json"),
    Path("public/data/data-package.json"),
]

YEAR_KEYS = ["year", "season", "SEASON"]
GAME_KEYS = ["gameId", "GAME_ID", "nbaGameId", "game_id"]
PLAYER_KEYS = ["playerId", "PLAYER_ID", "nbaId", "NBA_ID"]
PLAYER_NAME_KEYS = ["playerName", "PLAYER_NAME", "name", "fullName"]
TEAM_KEYS = ["team", "TEAM", "teamAbbr", "TEAM_ABBREVIATION"]
OPP_KEYS = ["opponent", "opp", "OPP", "opponentTeam"]
SERIES_KEYS = ["seriesCode", "series", "seriesId"]

SUM_FIELDS = ["PTS", "REB", "AST", "TOV", "FGM", "FGA", "FG3M", "FTA", "POSS"]
AVG_FIELDS = [
    "TS%", "eFG%", "ORTG", "DRTG", "NET",
    "rTS", "rORTG", "rDRTG", "rNET",
    "AdjTS%", "rAdjTS",
    "RIM_FREQ", "RIM_ACC",
    "AST%", "USG%", "ORB%", "DREB%",
    "OppRSAdjTSAllowed",
    "teamEFG", "teamTOVPct", "teamFTr", "teamTS",
    "oppAllowedEFG", "oppAllowedTOVPct", "oppAllowedFTr", "oppAllowedTS",
    "teamEFGvsOppAllowed", "teamTOVPctvsOppAllowed", "teamFTrvsOppAllowed", "teamTSvsOppAllowed",
]

def get_any(row, keys):
    for k in keys:
        if k in row and row[k] not in [None, ""]:
            return row[k]
    return ""

def num(v):
    if v in [None, "", "—"]:
        return None
    try:
        return float(str(v).replace(",", "").replace("%", "").strip())
    except Exception:
        return None

def key_game(row):
    return (
        str(get_any(row, YEAR_KEYS)),
        str(get_any(row, PLAYER_KEYS)),
        str(get_any(row, TEAM_KEYS)),
        str(get_any(row, OPP_KEYS)),
        str(get_any(row, SERIES_KEYS)),
    )

def row_min(row):
    for k in ["MIN", "minutes", "Minutes"]:
        if k in row and row[k] not in [None, "", "—"]:
            return num(row.get(k))
    return None

def is_eligible_game(row):
    m = row_min(row)
    if m is None:
        return True
    return m >= THRESHOLD

def weighted_avg(rows, field):
    total = 0.0
    weight = 0.0
    for r in rows:
        v = num(r.get(field))
        if v is None:
            continue
        w = row_min(r) or num(r.get("POSS")) or 1.0
        total += v * w
        weight += w
    return round(total / weight, 3) if weight else None

def sum_field(rows, field):
    total = 0.0
    found = False
    for r in rows:
        v = num(r.get(field))
        if v is not None:
            total += v
            found = True
    return round(total, 3) if found else None

def recompute_series_row(base, rows, removed_count):
    out = dict(base)
    gp = len(rows)

    out["GP"] = gp
    out["gamesIncluded"] = gp
    out["gamesRemovedUnder15"] = removed_count
    out["minGameMinutesThreshold"] = THRESHOLD
    out["minuteThresholdLabel"] = f"Games under {int(THRESHOLD)} minutes removed"

    total_min = sum((row_min(r) or 0.0) for r in rows)
    if gp:
        out["MIN"] = round(total_min / gp, 3)

    for f in SUM_FIELDS:
        s = sum_field(rows, f)
        if s is not None:
            out[f] = s

    poss = num(out.get("POSS"))
    if poss and poss > 0:
        for total_key, rate_key in [
            ("PTS", "PTS/75"),
            ("REB", "REB/75"),
            ("AST", "AST/75"),
            ("TOV", "TOV/75"),
        ]:
            v = num(out.get(total_key))
            if v is not None:
                out[rate_key] = round(v / poss * 75, 3)

    pts = num(out.get("PTS"))
    fga = num(out.get("FGA"))
    fgm = num(out.get("FGM"))
    fg3m = num(out.get("FG3M"))
    fta = num(out.get("FTA"))

    if pts is not None and fga and fta is not None and (fga + 0.44 * fta) > 0:
        out["TS%"] = round(100 * pts / (2 * (fga + 0.44 * fta)), 3)

    if fga and fgm is not None:
        out["eFG%"] = round(100 * ((fgm + 0.5 * (fg3m or 0.0)) / fga), 3)

    for f in AVG_FIELDS:
        if f in ["TS%", "eFG%"]:
            continue
        v = weighted_avg(rows, f)
        if v is not None:
            out[f] = v

    out["sourceLevel"] = "series"
    out["minuteThresholdApplied"] = True

    return out

def rebuild_series(player_games, player_series):
    grouped = defaultdict(list)
    all_grouped = defaultdict(int)

    for r in player_games:
        if not isinstance(r, dict):
            continue
        grouped[key_game(r)].append(r)

    # Count removed games from previous full set is unavailable after filtering,
    # so this script records removed count at game-filter step separately where possible.
    # At minimum, series rows are rebuilt from eligible games only.
    rebuilt = []

    for sr in player_series:
        if not isinstance(sr, dict):
            continue

        k = key_game(sr)
        rows = grouped.get(k, [])

        if not rows:
            continue

        rebuilt.append(recompute_series_row(sr, rows, removed_count=0))

    return rebuilt

def apply_to_package(path):
    data = json.loads(path.read_text(errors="ignore"))

    player_games = data.get("playerGames", [])
    if not isinstance(player_games, list):
        print("No playerGames list in", path)
        return

    before_games = len(player_games)
    removed_rows = []
    kept_games = []

    for r in player_games:
        if not isinstance(r, dict):
            kept_games.append(r)
            continue

        m = row_min(r)
        if m is not None and m < THRESHOLD:
            rr = dict(r)
            rr["_removedReason"] = f"MIN under {THRESHOLD}"
            removed_rows.append(rr)
            continue

        r["minuteThresholdApplied"] = True
        r["minGameMinutesThreshold"] = THRESHOLD
        kept_games.append(r)

    data["playerGames"] = kept_games

    series_key = "playerSeries" if isinstance(data.get("playerSeries"), list) else "seriesPlayers" if isinstance(data.get("seriesPlayers"), list) else None
    before_series = len(data.get(series_key, [])) if series_key else 0

    if series_key:
        data[series_key] = rebuild_series(kept_games, data[series_key])

    data.setdefault("siteSettings", {})
    data["siteSettings"]["minGameMinutesThreshold"] = THRESHOLD
    data["siteSettings"]["minuteThresholdLabel"] = f"Games under {int(THRESHOLD)} minutes removed"

    data.setdefault("dataSources", {})
    if isinstance(data["dataSources"], dict):
        data["dataSources"]["minute_threshold_15"] = {
            "installedAt": int(time.time()),
            "thresholdMinutes": THRESHOLD,
            "gamesBefore": before_games,
            "gamesAfter": len(kept_games),
            "gamesRemoved": len(removed_rows),
            "note": "Site-wide game eligibility filter. Games with MIN < 15 are removed from playerGames; series rows are rebuilt from eligible games."
        }

    path.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False))

    print("")
    print("Package:", path)
    print("Games before:", before_games)
    print("Games after:", len(kept_games))
    print("Games removed under 15 MIN:", len(removed_rows))
    print("Series before:", before_series)
    if series_key:
        print("Series after rebuild:", len(data[series_key]))

def main():
    for p in PACKAGE_FILES:
        if not p.exists():
            print("Skipping missing:", p)
            continue

        backup = Path("backups") / f"{p.name}.before-min15.{int(time.time())}.bak"
        backup.parent.mkdir(exist_ok=True)
        shutil.copy2(p, backup)
        print("Backup:", backup)

        apply_to_package(p)

    print("")
    print("DONE applying 15-minute threshold.")

if __name__ == "__main__":
    main()
