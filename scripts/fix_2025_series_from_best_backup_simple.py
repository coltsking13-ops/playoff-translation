import json, time
from pathlib import Path
from collections import defaultdict

YEAR = 2025

def filled(v):
    return v not in [None, "", [], {}]

def num(v):
    if not filled(v):
        return None
    try:
        return float(str(v).replace("+", "").replace("%", ""))
    except:
        return None

def yr(r):
    try:
        return int(r.get("year") or 0)
    except:
        return 0

def nm(v):
    return str(v or "").lower().strip()

def games(r):
    for k in ["games", "Games", "GAMES"]:
        v = num(r.get(k))
        if v is not None:
            return int(v)
    return 1

def score_file(p):
    try:
        data = json.loads(p.read_text(errors="ignore"))
    except Exception:
        return -1, None

    rows = [r for r in data.get("playerSeries", []) if yr(r) == YEAR]
    curry = [r for r in rows if "curry" in nm(r.get("playerName") or r.get("name"))]

    curry_hou_first_game_rows = [
        r for r in curry
        if str(r.get("opponent") or "") == "HOU"
        and "first" in nm(r.get("round"))
        and games(r) == 1
    ]

    return len(curry_hou_first_game_rows), data

def weighted_avg(rows, field):
    vals = []
    for r in rows:
        v = num(r.get(field))
        if v is None:
            continue
        w = num(r.get("MIN")) or games(r) or 1
        vals.append((v, w))
    if not vals:
        return None
    tw = sum(w for _, w in vals)
    return sum(v*w for v, w in vals) / tw if tw else None

def weighted_total(rows, field):
    vals = []
    for r in rows:
        v = num(r.get(field))
        if v is None:
            continue
        vals.append(v * games(r))
    return sum(vals) if vals else None

def make_series(rows):
    rows = list(rows)
    first = rows[0]
    total_games = sum(games(r) for r in rows)

    out = {
        "year": YEAR,
        "playerId": first.get("playerId"),
        "nbaId": first.get("nbaId"),
        "playerName": first.get("playerName") or first.get("name"),
        "team": first.get("team"),
        "opponent": first.get("opponent"),
        "round": first.get("round"),
        "seriesCode": first.get("seriesCode") or first.get("round"),
        "games": total_games,
        "Games": total_games,
        "GAMES": total_games,
    }

    skip = {
        "year","playerId","nbaId","playerName","name","team","opponent",
        "round","seriesCode","games","Games","GAMES","date","gameId","nbaGameId"
    }

    sum_fields = {
        "PTS","REB","AST","STL","BLK","TOV","FGM","FGA","FG3M","FG3A","FTM","FTA",
        "AdjFGA","AdjFTA","POSS","ScoringTOV","Heaves","ZBounds","ZBoards","TechFTA"
    }

    fields = set()
    for r in rows:
        fields.update(r.keys())

    for f in fields:
        if f in skip:
            continue
        v = weighted_total(rows, f) if f in sum_fields else weighted_avg(rows, f)
        if v is not None:
            out[f] = round(v, 2)

    pts = num(out.get("PTS"))
    fga = num(out.get("FGA"))
    fta = num(out.get("FTA"))
    adjfga = num(out.get("AdjFGA"))
    adjfta = num(out.get("AdjFTA"))

    if pts is not None and fga is not None and fta is not None:
        denom = 2 * (fga + 0.44 * fta)
        if denom > 0:
            out["TS%"] = round(100 * pts / denom, 2)

    if pts is not None and adjfga is not None and adjfta is not None:
        denom = 2 * (adjfga + 0.44 * adjfta)
        if denom > 0:
            out["AdjTS%"] = round(100 * pts / denom, 2)

    out["series_rebuilt_from_best_backup"] = True
    return out

candidates = sorted(Path("backups").glob("*.json"))
best_path = None
best_data = None
best_score = -1

print("Scanning backups for Curry 2025 HOU game rows...")
for p in candidates:
    score, data = score_file(p)
    if score > 0:
        print(p, "Curry HOU First Round game rows:", score)
    if score > best_score:
        best_score = score
        best_path = p
        best_data = data

if best_score < 5:
    print("Could not find a backup with 5 Curry HOU First Round game rows.")
    print("Best found:", best_path, "score:", best_score)
    raise SystemExit(1)

print("Using best backup:", best_path)
print("Curry HOU First Round game rows found:", best_score)

source_rows = [r for r in best_data.get("playerSeries", []) if yr(r) == YEAR]

# Remove generic Playoff Series rows when real round rows exist for same player/team/opponent.
by_player_opp = defaultdict(list)
for r in source_rows:
    if not (r.get("playerName") or r.get("name")):
        continue
    if not r.get("team") or not r.get("opponent"):
        continue
    k = (
        str(r.get("playerId") or ""),
        str(r.get("nbaId") or ""),
        nm(r.get("playerName") or r.get("name")),
        str(r.get("team") or ""),
        str(r.get("opponent") or "")
    )
    by_player_opp[k].append(r)

usable = []
for rows in by_player_opp.values():
    real_rounds = [r for r in rows if "playoff series" not in nm(r.get("round"))]
    usable.extend(real_rounds if real_rounds else rows)

groups = defaultdict(list)
for r in usable:
    k = (
        str(r.get("playerId") or ""),
        str(r.get("nbaId") or ""),
        nm(r.get("playerName") or r.get("name")),
        str(r.get("team") or ""),
        str(r.get("opponent") or ""),
        str(r.get("round") or r.get("seriesCode") or "")
    )
    groups[k].append(r)

rebuilt = [make_series(rows) for rows in groups.values()]
print("Rebuilt 2025 series rows:", len(rebuilt))

def patch(path):
    p = Path(path)
    if not p.exists():
        return

    raw = p.read_text(errors="ignore")
    backup = Path("backups") / f"{p.name}.before-final-2025-series-fix.{int(time.time())}.json"
    backup.write_text(raw, encoding="utf-8")

    data = json.loads(raw)
    kept = [r for r in data.get("playerSeries", []) if yr(r) != YEAR]
    data["playerSeries"] = kept + rebuilt
    p.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    print("PATCHED", path)

patch("data-package.json")
patch("data/data-package.json")
patch("public/data/data-package.embedded.json")

for path in ["data-package.json", "public/data/data-package.embedded.json"]:
    p = Path(path)
    if not p.exists():
        continue
    data = json.loads(p.read_text())
    curry = [
        r for r in data.get("playerSeries", [])
        if yr(r) == YEAR and "curry" in nm(r.get("playerName") or r.get("name"))
    ]
    print("\nCURRY 2025 AUDIT:", path)
    for r in curry:
        print(r.get("year"), r.get("round"), r.get("opponent"), "games=" + str(r.get("games") or r.get("Games") or r.get("GAMES")), "MIN=" + str(r.get("MIN")), "AdjTS=" + str(r.get("AdjTS%")), "rAdjTS=" + str(r.get("rAdjTS")))
