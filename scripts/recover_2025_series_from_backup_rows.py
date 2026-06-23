import json, time
from pathlib import Path
from collections import defaultdict

YEAR = 2025

def filled(v):
    return v not in [None, "", [], {}]

def n(v):
    if not filled(v):
        return None
    try:
        return float(str(v).replace("+","").replace("%",""))
    except:
        return None

def name(v):
    return str(v or "").lower().strip()

def year(r):
    try:
        return int(r.get("year") or 0)
    except:
        return 0

def get_games(r):
    for k in ["games", "Games", "GAMES"]:
        if n(r.get(k)) is not None:
            return int(n(r.get(k)))
    return 1

def latest_backup(stem):
    files = sorted(Path("backups").glob(f"{stem}.before-rebuild-2025-series.*.json"), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None

def weighted_avg(rows, field):
    vals = []
    for r in rows:
        v = n(r.get(field))
        if v is None:
            continue
        w = n(r.get("MIN")) or get_games(r) or 1
        vals.append((v, w))
    if not vals:
        return None
    tw = sum(w for _, w in vals)
    return sum(v*w for v,w in vals) / tw if tw else None

def sum_weighted_games(rows, field):
    vals = []
    for r in rows:
        v = n(r.get(field))
        if v is None:
            continue
        g = get_games(r)
        vals.append(v * g)
    return sum(vals) if vals else None

def make_series(rows):
    rows = list(rows)
    first = rows[0]

    games = sum(get_games(r) for r in rows)

    out = {}
    out["year"] = YEAR
    out["playerId"] = first.get("playerId")
    out["nbaId"] = first.get("nbaId")
    out["playerName"] = first.get("playerName") or first.get("name")
    out["team"] = first.get("team")
    out["opponent"] = first.get("opponent")
    out["round"] = first.get("round")
    out["seriesCode"] = first.get("seriesCode") or first.get("round")
    out["games"] = games
    out["Games"] = games
    out["GAMES"] = games

    fields = set()
    for r in rows:
        fields.update(r.keys())

    skip = {"year","playerId","nbaId","playerName","name","team","opponent","round","seriesCode","games","Games","GAMES","date","gameId","nbaGameId"}

    for f in fields:
        if f in skip:
            continue

        if f in ["PTS","REB","AST","STL","BLK","TOV","FGM","FGA","FG3M","FG3A","FTM","FTA","AdjFGA","AdjFTA","POSS","ScoringTOV","Heaves","ZBounds","ZBoards","TechFTA"]:
            v = sum_weighted_games(rows, f)
        else:
            v = weighted_avg(rows, f)

        if v is not None:
            out[f] = round(v, 2)

    # Recalculate TS/AdjTS if enough totals exist
    pts = n(out.get("PTS"))
    fga = n(out.get("FGA"))
    fta = n(out.get("FTA"))
    adjfga = n(out.get("AdjFGA"))
    adjfta = n(out.get("AdjFTA"))

    if pts is not None and fga is not None and fta is not None:
        denom = 2 * (fga + 0.44 * fta)
        if denom > 0:
            out["TS%"] = round(100 * pts / denom, 2)

    if pts is not None and adjfga is not None and adjfta is not None:
        denom = 2 * (adjfga + 0.44 * adjfta)
        if denom > 0:
            out["AdjTS%"] = round(100 * pts / denom, 2)

    out["series_recovered_from_backup_rows"] = True
    return out

def recover_rows_from_backup():
    b = latest_backup("data-package.json")
    if not b:
        raise SystemExit("No backup found for data-package.json before rebuild")

    print("Using backup:", b)
    old = json.loads(b.read_text())

    old_series = [
        r for r in old.get("playerSeries", [])
        if year(r) == YEAR
    ]

    # Use old rows that were clearly game-row style series rows too.
    # The bad rows often have Games=1 and round/opponent filled.
    groups = defaultdict(list)

    for r in old_series:
        if not r.get("playerName") and not r.get("name"):
            continue
        if not r.get("team") or not r.get("opponent"):
            continue

        # Drop weird combined rows when there are real 1-game rows for same player/opponent/round.
        # We'll handle that by preferring rows with Games=1 if they exist in a group.
        k = (
            str(r.get("year") or ""),
            str(r.get("playerId") or ""),
            str(r.get("nbaId") or ""),
            name(r.get("playerName") or r.get("name")),
            str(r.get("team") or ""),
            str(r.get("opponent") or ""),
            str(r.get("round") or r.get("seriesCode") or "")
        )
        groups[k].append(r)

    rebuilt = []
    for k, rows in groups.items():
        one_game_rows = [r for r in rows if get_games(r) == 1]

        # If there are real game-level rows, use those and ignore weird Games=2 "Playoff Series" rows.
        source = one_game_rows if one_game_rows else rows

        rebuilt.append(make_series(source))

    print("Recovered/rebuilt 2025 series rows:", len(rebuilt))
    return rebuilt

def patch_file(path, rebuilt):
    p = Path(path)
    if not p.exists():
        return

    raw = p.read_text(errors="ignore")
    backup = Path("backups") / f"{p.name}.before-recover-2025-series.{int(time.time())}.json"
    backup.write_text(raw, encoding="utf-8")

    data = json.loads(raw)

    kept = [r for r in data.get("playerSeries", []) if year(r) != YEAR]
    data["playerSeries"] = kept + rebuilt

    p.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")

    print("PATCHED", path, "2025 series now:", len(rebuilt))

def audit(path):
    p = Path(path)
    if not p.exists():
        return

    data = json.loads(p.read_text())
    rows = [
        r for r in data.get("playerSeries", [])
        if year(r) == YEAR and "curry" in name(r.get("playerName") or r.get("name"))
    ]

    print("\nCURRY AUDIT", path)
    for r in rows:
        print(
            r.get("year"),
            r.get("round"),
            r.get("opponent"),
            "games=" + str(r.get("games") or r.get("Games") or r.get("GAMES")),
            "MIN=" + str(r.get("MIN")),
            "AdjTS=" + str(r.get("AdjTS%")),
            "rAdjTS=" + str(r.get("rAdjTS"))
        )

rebuilt = recover_rows_from_backup()

patch_file("data-package.json", rebuilt)
patch_file("data/data-package.json", rebuilt)
patch_file("public/data/data-package.embedded.json", rebuilt)

audit("data-package.json")
audit("public/data/data-package.embedded.json")
