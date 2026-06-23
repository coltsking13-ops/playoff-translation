#!/usr/bin/env python3
import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

WEMBY_ID = "1641705"
WEMBY_NAME_BITS = ["wemb", "victor"]
SAS_TEAM_ID = "1610612759"
OKC_TEAM_ID = "1610612760"

ROOT = Path(".")
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

DATA_PATHS = [
    ROOT / "public/data/data-package.embedded.json",
    ROOT / "public/data/data-package.json",
    ROOT / "data-package.json",
    ROOT / "data/data-package.json",
    ROOT / "public/data/pbpstats/player_game_low_removed/2026.json",
]

SIX_FACTOR_ALIASES = {
    "eFG%": ["EfgPct", "eFG%", "EFG%", "EffectiveFgPct", "TeamEfgPct", "OffEfgPct"],
    "TOV%": ["TovPct", "TOV%", "TurnoverPct", "TeamTovPct", "OffTovPct"],
    "ORB%": ["OffReboundPct", "OREB%", "ORB%", "OrebPct", "TeamOrebPct"],
    "FTr": ["FtRate", "FTr", "FreeThrowRate", "FtaRate", "FTARate"],
    "TS%": ["TsPct", "TS%", "TrueShootingPct", "TeamTsPct"],
    "3PAr": ["ThreePtRate", "3PAr", "Fg3aRate", "ThreePAR", "ThreePointAttemptRate"],
}

SHOT_LOCATION_ALIASES = {
    "Rim Freq": ["AtRimFrequency", "RimFreq", "RimFrequency", "AtRimFreq"],
    "Rim Acc": ["AtRimAccuracy", "RimAccuracy", "RimAcc", "AtRimPct"],
    "Paint Freq": ["PaintFrequency", "PaintFreq", "InThePaintFrequency"],
    "Paint Acc": ["PaintAccuracy", "PaintAcc", "InThePaintAccuracy"],
    "Short Mid Freq": ["ShortMidRangeFrequency", "ShortMidFreq", "ShortMidRangeFreq"],
    "Short Mid Acc": ["ShortMidRangeAccuracy", "ShortMidAcc"],
    "Long Mid Freq": ["LongMidRangeFrequency", "LongMidFreq", "LongMidRangeFreq"],
    "Long Mid Acc": ["LongMidRangeAccuracy", "LongMidAcc"],
    "Corner 3 Freq": ["Corner3Frequency", "CornerThreeFrequency", "Corner3Freq"],
    "Corner 3 Acc": ["Corner3Accuracy", "CornerThreeAccuracy", "Corner3Pct"],
    "Above Break 3 Freq": ["Arc3Frequency", "AboveBreak3Frequency", "AbvBreak3Freq"],
    "Above Break 3 Acc": ["Arc3Accuracy", "AboveBreak3Accuracy", "AbvBreak3Pct"],
}

BASIC_ALIASES = {
    "Off Poss": ["OffPoss", "OffensivePossessions", "OffPossessions"],
    "Def Poss": ["DefPoss", "DefensivePossessions", "DefPossessions"],
    "Points": ["Points", "Pts", "TeamPoints"],
    "Opp Points": ["OpponentPoints", "OppPoints", "OpponentPts"],
    "ORTG": ["OffRtg", "ORTG", "OffRating"],
    "DRTG": ["DefRtg", "DRTG", "DefRating"],
    "NET": ["NetRtg", "NET", "NetRating"],
}

def read_json(path):
    try:
        return json.loads(path.read_text(errors="ignore"))
    except Exception:
        return None

def rows_from_any(obj):
    if obj is None:
        return
    if isinstance(obj, list):
        for x in obj:
            if isinstance(x, dict):
                yield x
            elif isinstance(x, (list, dict)):
                yield from rows_from_any(x)
    elif isinstance(obj, dict):
        for k in ["players", "playerGames", "playerSeries", "games", "rows", "data", "player_game_low_removed"]:
            v = obj.get(k)
            if isinstance(v, list):
                for x in v:
                    if isinstance(x, dict):
                        yield x
            elif isinstance(v, dict):
                yield from rows_from_any(v)
        for v in obj.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                for x in v:
                    yield x

def get_any(row, keys, default=None):
    for k in keys:
        if k in row and row[k] not in [None, ""]:
            return row[k]
    return default

def clean_team(x):
    return str(x or "").upper().replace(".", "").strip()

def looks_like_wemby(row):
    pid = str(get_any(row, ["playerId", "PLAYER_ID", "nbaId", "NBA_ID", "id"], ""))
    name = str(get_any(row, ["playerName", "PLAYER_NAME", "name", "fullName"], "")).lower()
    return pid == WEMBY_ID or any(bit in name for bit in WEMBY_NAME_BITS)

def looks_like_okc_game(row):
    blob = " ".join(str(v) for v in row.values()).upper()
    opp = clean_team(get_any(row, ["opponent", "opp", "OPP", "opponentTeam", "Opponent", "vs"], ""))
    return "OKC" in blob or "THUNDER" in blob or opp == "OKC"

def looks_like_game_1(row):
    keys = ["seriesGame", "gameInSeries", "gameNumber", "seriesGameNumber", "G", "game", "gameLabel"]
    for k in keys:
        if k in row:
            val = str(row[k]).upper()
            if val in ["1", "G1", "GAME 1"]:
                return True
            if re.search(r"\bG1\b|\bGAME\s*1\b", val):
                return True
    blob = " ".join(str(v) for v in row.values()).upper()
    return bool(re.search(r"\bG1\b|\bGAME\s*1\b", blob))

def find_game_id():
    candidates = []
    for path in DATA_PATHS:
        if not path.exists():
            continue
        obj = read_json(path)
        for row in rows_from_any(obj):
            if looks_like_wemby(row) and looks_like_okc_game(row):
                candidates.append((path, row))

    g1 = [(p, r) for p, r in candidates if looks_like_game_1(r)]
    chosen_pool = g1 or candidates

    if not chosen_pool:
        return None, []

    def sort_key(item):
        _, r = item
        date = str(get_any(r, ["date", "gameDate", "GAME_DATE"], ""))
        gid = str(get_any(r, ["gameId", "GAME_ID", "nbaGameId", "game_id"], ""))
        return (date, gid)

    chosen_pool = sorted(chosen_pool, key=sort_key)
    path, row = chosen_pool[0]
    gid = get_any(row, ["gameId", "GAME_ID", "nbaGameId", "game_id", "nba_game_id"])
    return str(gid) if gid else None, chosen_pool[:10]

def http_json(url, params, retries=4):
    full = url + "?" + urlencode(params)
    last_err = None
    for i in range(retries):
        try:
            req = Request(full, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(req, timeout=45) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            last_err = e
            wait = 2 + i * 3
            print(f"Request failed ({e}); retrying in {wait}s...")
            time.sleep(wait)
    raise RuntimeError(f"Failed after retries: {full}\n{last_err}")

def flatten_dicts(obj):
    out = []
    if isinstance(obj, dict):
        # common containers
        for k in ["results", "data", "rows", "WowyCombinations", "wowys", "items"]:
            if isinstance(obj.get(k), list):
                out.extend([x for x in obj[k] if isinstance(x, dict)])
        # if the dict itself looks like a stat row
        if any(k.lower().endswith("poss") or "points" in k.lower() or "efg" in k.lower() for k in obj):
            out.append(obj)
        for v in obj.values():
            if isinstance(v, (dict, list)):
                out.extend(flatten_dicts(v))
    elif isinstance(obj, list):
        for x in obj:
            out.extend(flatten_dicts(x))
    return out

def get_wowy_row(game_id, season):
    base = "https://api.pbpstats.com/get-wowy-combinations/nba"
    attempts = [
        {"Season": season, "SeasonType": "Playoffs", "TeamId": SAS_TEAM_ID, "PlayerIds": WEMBY_ID, "Type": "Team", "GameId": game_id},
        {"Season": season, "SeasonType": "Playoffs", "TeamId": SAS_TEAM_ID, "PlayerIds": WEMBY_ID, "Type": "Team", "GameIds": game_id},
        {"Season": season, "SeasonType": "Playoffs", "TeamId": SAS_TEAM_ID, "PlayerIds": WEMBY_ID, "Type": "Team", "GameID": game_id},
    ]

    for params in attempts:
        print("Trying PBPStats WOWY:", params)
        try:
            js = http_json(base, params)
            raw_path = LOG_DIR / f"wemby_g1_okc_wowy_raw_{game_id}.json"
            raw_path.write_text(json.dumps(js, indent=2))
            rows = flatten_dicts(js)
            if rows:
                # pick row with most relevant stat keys
                rows = sorted(rows, key=lambda r: sum(1 for k in r if any(x in k.lower() for x in ["poss", "point", "efg", "rim", "corner", "mid"])), reverse=True)
                return rows[0], raw_path
        except Exception as e:
            print("WOWY attempt failed:", e)

    return None, None

def num(v):
    if v is None or v == "":
        return None
    if isinstance(v, str):
        v = v.replace("%", "").replace(",", "").strip()
    try:
        return float(v)
    except Exception:
        return None

def metric(row, aliases):
    v = get_any(row, aliases)
    return num(v)

def fmt(v, pct=False):
    if v is None:
        return "—"
    # if it is a pct stored as decimal, convert it
    if pct and abs(v) <= 1.5:
        v *= 100
    return f"{v:.1f}"

def find_benchmark_rows():
    # Tries to find OKC allowed/defense/shot-zone rows from local CSV/JSON files.
    files = []
    for base in [ROOT, ROOT / "data", ROOT / "public/data"]:
        if not base.exists():
            continue
        for p in base.rglob("*"):
            low = p.name.lower()
            if p.suffix.lower() in [".csv", ".json"] and any(s in low for s in ["shotzone", "shot_zone", "defense", "teamplayd", "teamgame", "allowed", "vs"]):
                files.append(p)

    matches = []
    for p in files:
        try:
            if p.suffix.lower() == ".csv":
                with p.open(newline="", errors="ignore") as f:
                    for row in csv.DictReader(f):
                        blob = " ".join(str(v) for v in row.values()).upper()
                        if ("OKC" in blob or "THUNDER" in blob) and ("2026" in blob or "2025-26" in blob or "2025" in blob):
                            matches.append((p, row))
            elif p.suffix.lower() == ".json":
                obj = read_json(p)
                for row in rows_from_any(obj):
                    blob = " ".join(str(v) for v in row.values()).upper()
                    if ("OKC" in blob or "THUNDER" in blob) and ("2026" in blob or "2025-26" in blob or "2025" in blob):
                        matches.append((p, row))
        except Exception:
            pass

    return matches[:30]

def bench_value(bench_rows, aliases):
    # Prefer allowed/vs/opponent-style columns when aliases match.
    expanded = []
    for a in aliases:
        expanded.extend([
            a,
            "Opp" + a,
            "Opponent" + a,
            a + "Allowed",
            a + "_allowed",
            a + " Allowed",
            "Allowed" + a,
            "VS_" + a,
            "vs_" + a,
        ])

    for path, row in bench_rows:
        lower_map = {str(k).lower().replace(" ", "").replace("_", ""): k for k in row.keys()}
        for a in expanded:
            key = a.lower().replace(" ", "").replace("_", "")
            if key in lower_map:
                return num(row[lower_map[key]]), path.name
    return None, None

def print_group(title, aliases_map, wowy_row, bench_rows):
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)
    print(f"{'Metric':<22} {'Wemby ON':>12} {'OKC Allowed':>14} {'Adj':>10}  Source")
    print("-" * 72)

    for name, aliases in aliases_map.items():
        v = metric(wowy_row, aliases)
        b, src = bench_value(bench_rows, aliases)
        pct_like = name.endswith("%") or "Freq" in name or "Acc" in name or name in ["eFG%", "TOV%", "ORB%", "TS%", "3PAr"]

        adj = None
        if v is not None and b is not None:
            vv = v * 100 if pct_like and abs(v) <= 1.5 else v
            bb = b * 100 if pct_like and abs(b) <= 1.5 else b
            adj = vv - bb

        print(f"{name:<22} {fmt(v, pct_like):>12} {fmt(b, pct_like):>14} {fmt(adj):>10}  {src or ''}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game-id", default=None, help="Manual NBA game id if auto-find misses")
    ap.add_argument("--season", default="2025-26")
    args = ap.parse_args()

    game_id = args.game_id
    candidates = []

    if not game_id:
        game_id, candidates = find_game_id()

    if not game_id:
        print("Could not auto-find Wemby Game 1 vs OKC in local data.")
        print("Run again with: python3 scripts/wemby_g1_okc_on_context.py --game-id 00XXXXXXXX")
        if candidates:
            print("\nCandidates found:")
            for p, r in candidates:
                print(p, get_any(r, ["gameId", "GAME_ID", "nbaGameId"]), get_any(r, ["date", "gameDate"]), get_any(r, ["opponent", "opp", "OPP"]), get_any(r, ["gameLabel", "seriesGame"]))
        sys.exit(1)

    print("Using GameId:", game_id)
    print("Season:", args.season)

    wowy_row, raw_path = get_wowy_row(game_id, args.season)
    if not wowy_row:
        print("Could not pull WOWY row from PBPStats.")
        sys.exit(1)

    print("Saved raw WOWY response:", raw_path)
    print("WOWY keys sample:", ", ".join(list(wowy_row.keys())[:60]))

    # Derived basic ratings if possible
    off_poss = metric(wowy_row, BASIC_ALIASES["Off Poss"])
    def_poss = metric(wowy_row, BASIC_ALIASES["Def Poss"])
    pts = metric(wowy_row, BASIC_ALIASES["Points"])
    opp_pts = metric(wowy_row, BASIC_ALIASES["Opp Points"])

    print("\n" + "=" * 72)
    print("WEMBY ON — BASIC TEAM CONTEXT")
    print("=" * 72)
    print("Off Poss:", fmt(off_poss))
    print("Def Poss:", fmt(def_poss))
    print("Team Points:", fmt(pts))
    print("Opp Points:", fmt(opp_pts))

    if off_poss and pts is not None:
        print("ORTG:", fmt(100 * pts / off_poss))
    else:
        print("ORTG:", fmt(metric(wowy_row, BASIC_ALIASES["ORTG"])))

    if def_poss and opp_pts is not None:
        print("DRTG:", fmt(100 * opp_pts / def_poss))
    else:
        print("DRTG:", fmt(metric(wowy_row, BASIC_ALIASES["DRTG"])))

    if off_poss and def_poss and pts is not None and opp_pts is not None:
        print("NET:", fmt(100 * pts / off_poss - 100 * opp_pts / def_poss))
    else:
        print("NET:", fmt(metric(wowy_row, BASIC_ALIASES["NET"])))

    bench_rows = find_benchmark_rows()
    print("\nBenchmark rows found:", len(bench_rows))
    if bench_rows:
        print("Benchmark files:")
        for p, _ in bench_rows[:8]:
            print(" -", p)

    print_group("WEMBY ON — SIX FACTORS, OPPONENT ADJUSTED IF BENCHMARK EXISTS", SIX_FACTOR_ALIASES, wowy_row, bench_rows)
    print_group("WEMBY ON — SHOT LOCATION, OPPONENT ADJUSTED IF BENCHMARK EXISTS", SHOT_LOCATION_ALIASES, wowy_row, bench_rows)

    print("\nDone.")
    print("If many benchmark cells are blank, the script still got the ON-court WOWY row, but it could not find matching OKC allowed benchmark columns locally.")
    print("Raw response saved at:", raw_path)

if __name__ == "__main__":
    main()
