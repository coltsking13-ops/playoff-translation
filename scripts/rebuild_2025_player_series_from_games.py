import json, re, time
from pathlib import Path
from collections import defaultdict

YEAR = 2025

ID_FIELDS = {
    "year", "season", "playerId", "nbaId", "playerName", "name",
    "team", "opponent", "round", "seriesCode", "date", "gameId", "nbaGameId",
    "result", "homeAway"
}

SUM_FIELDS = {
    "PTS", "REB", "AST", "STL", "BLK", "TOV",
    "FGM", "FGA", "FG3M", "FG3A", "FTM", "FTA",
    "AdjFGA", "AdjFTA", "ScoringTOV", "BadPassTOV", "BadPassOutOfBoundsTOV",
    "Heaves", "ZBounds", "ZBoards", "TechFTA", "POSS"
}

AVG_FIELDS = {
    "MIN", "PTS/75", "PP75", "TS%", "AdjTS%", "rTS", "rAdjTS",
    "teamAdjTS", "oppAdjTS", "OppRSAdjTSAllowed",
    "teamRimFreq", "oppRimFreq",
    "ORTG", "DRTG", "NET", "rORTG", "rDRTG", "rNET",
    "USG%", "eFG%", "FG%", "3P%", "FT%"
}

ROUND_ORDER = {
    "First Round": 1,
    "Conference Semifinals": 2,
    "Conference Finals": 3,
    "Finals": 4,
    "NBA Finals": 4,
    "Playoff Series": 99
}

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
        return int(r.get("year") or r.get("season") or 0)
    except:
        return 0

def name(v):
    return str(v or "").lower().strip()

def round_val(x, places=2):
    if x is None:
        return None
    return round(float(x), places)

def weighted_avg(rows, field):
    vals = []
    for r in rows:
        v = num(r.get(field))
        if v is None:
            continue
        w = num(r.get("MIN")) or num(r.get("POSS")) or 1
        vals.append((v, w))
    if not vals:
        return None
    tw = sum(w for _, w in vals)
    if not tw:
        return None
    return sum(v*w for v, w in vals) / tw

def sum_field(rows, field):
    vals = [num(r.get(field)) for r in rows if num(r.get(field)) is not None]
    if not vals:
        return None
    return sum(vals)

def game_identity(r):
    return (
        str(r.get("gameId") or r.get("nbaGameId") or ""),
        str(r.get("date") or ""),
        str(r.get("team") or ""),
        str(r.get("opponent") or ""),
        name(r.get("playerName") or r.get("name")),
    )

def series_key(r):
    return (
        str(r.get("year") or ""),
        str(r.get("playerId") or ""),
        str(r.get("nbaId") or ""),
        name(r.get("playerName") or r.get("name")),
        str(r.get("team") or ""),
        str(r.get("opponent") or ""),
        str(r.get("seriesCode") or r.get("round") or ""),
    )

def dedupe_games(rows):
    out = []
    seen = set()
    for r in rows:
        k = game_identity(r)
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out

def make_series_row(rows):
    rows = dedupe_games(rows)
    first = dict(rows[0])

    out = {}
    out["year"] = YEAR
    out["playerId"] = first.get("playerId")
    out["nbaId"] = first.get("nbaId")
    out["playerName"] = first.get("playerName") or first.get("name")
    out["team"] = first.get("team")
    out["opponent"] = first.get("opponent")
    out["round"] = first.get("round")
    out["seriesCode"] = first.get("seriesCode") or first.get("round")

    games = len(rows)
    out["games"] = games
    out["Games"] = games
    out["GAMES"] = games

    all_fields = set()
    for r in rows:
        all_fields.update(r.keys())

    for f in sorted(all_fields):
        if f in ID_FIELDS:
            continue

        if f in SUM_FIELDS:
            v = sum_field(rows, f)
            if v is not None:
                out[f] = round_val(v, 6)
            continue

        if f in AVG_FIELDS or any(token in f.lower() for token in ["%", "rate", "freq", "ortg", "drtg", "net", "adjts", "rts"]):
            v = weighted_avg(rows, f)
            if v is not None:
                out[f] = round_val(v, 2)
            continue

        v = weighted_avg(rows, f)
        if v is not None:
            out[f] = round_val(v, 2)

    pts = sum_field(rows, "PTS")
    poss = sum_field(rows, "POSS")
    fga = sum_field(rows, "FGA")
    fta = sum_field(rows, "FTA")
    adjfga = sum_field(rows, "AdjFGA")
    adjfta = sum_field(rows, "AdjFTA")

    if pts is not None and poss and poss > 0:
        out["PTS/75"] = round(pts / poss * 75, 2)
        out["PP75"] = round(pts / poss * 75, 2)

    if pts is not None and fga is not None and fta is not None:
        denom = 2 * (fga + 0.44 * fta)
        if denom > 0:
            out["TS%"] = round(100 * pts / denom, 2)

    if pts is not None and adjfga is not None and adjfta is not None:
        denom = 2 * (adjfga + 0.44 * adjfta)
        if denom > 0:
            out["AdjTS%"] = round(100 * pts / denom, 2)

    out["series_rebuilt_from_games"] = True
    out["series_rebuild_note"] = "2025 playerSeries rebuilt from game-level rows to fix game rows showing as series rows"

    return out

def patch_package(data):
    game_rows = [
        r for r in data.get("playerGames", [])
        if yr(r) == YEAR
    ]

    groups = defaultdict(list)
    for r in game_rows:
        groups[series_key(r)].append(r)

    rebuilt = []
    for rows in groups.values():
        if not rows:
            continue
        rebuilt.append(make_series_row(rows))

    rebuilt.sort(key=lambda r: (
        name(r.get("playerName")),
        ROUND_ORDER.get(str(r.get("round") or ""), 50),
        str(r.get("opponent") or "")
    ))

    old_series = data.get("playerSeries", [])
    kept = [r for r in old_series if yr(r) != YEAR]

    data["playerSeries"] = kept + rebuilt

    return len(game_rows), len([r for r in old_series if yr(r) == YEAR]), len(rebuilt)

def patch_json(path):
    p = Path(path)
    if not p.exists():
        return

    raw = p.read_text(errors="ignore")
    backup = Path("backups") / f"{p.name}.before-rebuild-2025-series.{int(time.time())}.json"
    backup.write_text(raw, encoding="utf-8")

    data = json.loads(raw)
    game_rows, old_series, new_series = patch_package(data)

    p.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")

    print("PATCHED", path)
    print("  2025 game rows:", game_rows)
    print("  old 2025 series rows removed:", old_series)
    print("  rebuilt 2025 series rows:", new_series)

def patch_index():
    p = Path("index.html")
    if not p.exists():
        return

    html = p.read_text(errors="ignore")
    m = re.search(
        r'(<script\s+id=["\']dataPackage["\']\s+type=["\']application/json["\']\s*>)(.*?)(</script\s*>)',
        html,
        flags=re.I | re.S
    )

    if not m:
        print("index.html: no embedded dataPackage found")
        return

    raw = m.group(2).strip()

    try:
        maybe = json.loads(raw)
        if isinstance(maybe, dict) and maybe.get("external"):
            print("index.html: external marker found, skipped embedded patch")
            return
    except:
        pass

    backup = Path("backups") / f"index.before-rebuild-2025-series.{int(time.time())}.html"
    backup.write_text(html, encoding="utf-8")

    data = json.loads(raw)
    game_rows, old_series, new_series = patch_package(data)

    new_raw = json.dumps(data, separators=(",", ":"))
    html = html[:m.start(2)] + new_raw + html[m.end(2):]
    p.write_text(html, encoding="utf-8")

    print("PATCHED embedded index.html")
    print("  2025 game rows:", game_rows)
    print("  old 2025 series rows removed:", old_series)
    print("  rebuilt 2025 series rows:", new_series)

def curry_audit(path):
    p = Path(path)
    if not p.exists():
        return

    data = json.loads(p.read_text())
    rows = [
        r for r in data.get("playerSeries", [])
        if yr(r) == YEAR and "curry" in name(r.get("playerName") or r.get("name"))
    ]

    print("\nCURRY 2025 SERIES AUDIT:", path)
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

patch_json("data-package.json")
patch_json("data/data-package.json")
patch_json("public/data/data-package.embedded.json")
patch_index()

curry_audit("data-package.json")
if Path("public/data/data-package.embedded.json").exists():
    curry_audit("public/data/data-package.embedded.json")
