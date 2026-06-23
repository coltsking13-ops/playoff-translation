#!/usr/bin/env python3
import json
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

WEMBY_ID = "1641705"
SAS_ID = "1610612759"
OKC_ID = "1610612760"

GAME_IDS_TO_TRY = ["0042500311", "42500311"]
SEASONS_TO_TRY = ["2025-26", "2026"]
SEASON_TYPES = ["Playoffs", "playoffs"]

OUT_DIR = Path("logs/wemby_pbp_api")
OUT_DIR.mkdir(parents=True, exist_ok=True)

def fetch_json(url, params, retries=3):
    full = url + "?" + urlencode(params)
    last = None

    for i in range(retries):
        try:
            req = Request(full, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(req, timeout=45) as r:
                return json.loads(r.read().decode("utf-8")), full
        except Exception as e:
            last = e
            wait = 2 + i * 4
            print(f"Failed: {full}")
            print(f"  {type(e).__name__}: {e}")
            print(f"  retrying in {wait}s...")
            time.sleep(wait)

    return None, full

def walk(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk(v)

def find_possessions(js):
    if isinstance(js, dict):
        for key in ["possessions", "Possessions", "data", "rows", "results"]:
            if isinstance(js.get(key), list):
                rows = [x for x in js[key] if isinstance(x, dict)]
                if rows:
                    return rows

    rows = [x for x in walk(js) if isinstance(x, dict)]
    likely = []
    for r in rows:
        blob = " ".join(str(k).lower() for k in r.keys())
        if "poss" in blob or "offenseteam" in blob or "defenseteam" in blob:
            likely.append(r)
    return likely

def row_text(row):
    return json.dumps(row, default=str)

def has_wemby_on(row):
    # Prefer lineup/on-court fields, not just any random mention.
    lineup_keys = []
    for k in row.keys():
        lk = str(k).lower()
        if any(x in lk for x in ["lineup", "on_court", "oncourt", "players", "playerids"]):
            lineup_keys.append(k)

    if lineup_keys:
        blob = " ".join(str(row.get(k, "")) for k in lineup_keys)
        return WEMBY_ID in blob

    # fallback: if the possession has no lineup fields, this is weak and we should not trust it
    return False

def get_num(row, names):
    keymap = {str(k).lower().replace("_","").replace(" ",""): k for k in row.keys()}
    for name in names:
        nk = name.lower().replace("_","").replace(" ","")
        if nk in keymap:
            try:
                return float(str(row[keymap[nk]]).replace("%",""))
            except:
                return 0.0
    return 0.0

def has_team(row, team_id, side):
    side = side.lower()
    for k, v in row.items():
        lk = str(k).lower()
        if side in lk and "team" in lk and str(v) == team_id:
            return True
    return False

def calculate(rows):
    on_rows = [r for r in rows if has_wemby_on(r)]

    if not on_rows:
        print("\nNO TRUE ON-COURT LINEUP FIELDS FOUND.")
        print("The possession response may not include lineup/player-on-court data.")
        print("Saved raw response so we can inspect keys.")
        return

    off = [r for r in on_rows if has_team(r, SAS_ID, "offense")]
    deff = [r for r in on_rows if has_team(r, SAS_ID, "defense")]

    print("\n" + "="*80)
    print("WEMBY ON POSSESSION COUNTS")
    print("="*80)
    print("Wemby ON rows:", len(on_rows))
    print("SAS offense possessions with Wemby ON:", len(off))
    print("SAS defense possessions with Wemby ON:", len(deff))

    def sum_stat(rows, aliases):
        return sum(get_num(r, aliases) for r in rows)

    pts = sum_stat(off, ["points", "Points", "PointsScored", "OffensePoints"])
    opp_pts = sum_stat(deff, ["points", "Points", "PointsScored", "OffensePoints"])

    fga = sum_stat(off, ["fga", "FGA", "FieldGoalAttempts"])
    fgm = sum_stat(off, ["fgm", "FGM", "FieldGoalsMade"])
    fg3a = sum_stat(off, ["fg3a", "FG3A", "ThreePtAttempts", "ThreePointAttempts"])
    fg3m = sum_stat(off, ["fg3m", "FG3M", "ThreePtMade", "ThreePointMakes"])
    fta = sum_stat(off, ["fta", "FTA", "FreeThrowAttempts"])
    tov = sum_stat(off, ["tov", "TOV", "Turnovers"])
    oreb = sum_stat(off, ["oreb", "OREB", "OffensiveRebounds"])

    rim_fga = sum_stat(off, ["rimfga", "RimFGA", "AtRimFGA", "AtRimAttempts"])
    rim_fgm = sum_stat(off, ["rimfgm", "RimFGM", "AtRimFGM", "AtRimMakes"])

    paint_fga = sum_stat(off, ["paintfga", "PaintFGA"])
    paint_fgm = sum_stat(off, ["paintfgm", "PaintFGM"])

    mid_fga = sum_stat(off, ["midfga", "MidFGA", "MidRangeFGA"])
    mid_fgm = sum_stat(off, ["midfgm", "MidFGM", "MidRangeFGM"])

    corner3a = sum_stat(off, ["corner3a", "Corner3A", "CornerThreeAttempts"])
    corner3m = sum_stat(off, ["corner3m", "Corner3M", "CornerThreeMakes"])

    arc3a = sum_stat(off, ["arc3a", "Arc3A", "AboveBreak3A"])
    arc3m = sum_stat(off, ["arc3m", "Arc3M", "AboveBreak3M"])

    off_poss = len(off)
    def_poss = len(deff)

    def div(a,b):
        return None if not b else a / b

    def pct(a,b):
        x = div(a,b)
        return None if x is None else 100*x

    ortg = None if not off_poss else 100 * pts / off_poss
    drtg = None if not def_poss else 100 * opp_pts / def_poss
    net = None if ortg is None or drtg is None else ortg - drtg

    efg = None if not fga else 100 * ((fgm + 0.5*fg3m) / fga)
    ftr = None if not fga else 100 * fta / fga
    tov_pct = None if not off_poss else 100 * tov / off_poss
    orb_pct = None if not off_poss else 100 * oreb / off_poss
    three_par = None if not fga else 100 * fg3a / fga

    print("\n" + "="*80)
    print("WEMBY ON — SAS TEAM OFFENSE/DEFENSE")
    print("="*80)
    for k,v in [
        ("ORTG", ortg),
        ("DRTG", drtg),
        ("NET", net),
        ("Points For", pts),
        ("Points Against", opp_pts),
        ("FGA", fga),
        ("FTA", fta),
        ("TOV", tov),
        ("OREB", oreb),
    ]:
        print(f"{k:<18}", "—" if v is None else round(v, 2))

    print("\n" + "="*80)
    print("WEMBY ON — SIX FACTORS")
    print("="*80)
    for k,v in [
        ("eFG%", efg),
        ("TOV%", tov_pct),
        ("ORB per 100 poss", orb_pct),
        ("FTr", ftr),
        ("3PAr", three_par),
    ]:
        print(f"{k:<18}", "—" if v is None else round(v, 2))

    print("\n" + "="*80)
    print("WEMBY ON — SHOT LOCATION")
    print("="*80)
    for k,v in [
        ("Rim Freq", pct(rim_fga, fga)),
        ("Rim Acc", pct(rim_fgm, rim_fga)),
        ("Paint Freq", pct(paint_fga, fga)),
        ("Paint Acc", pct(paint_fgm, paint_fga)),
        ("Mid Freq", pct(mid_fga, fga)),
        ("Mid Acc", pct(mid_fgm, mid_fga)),
        ("Corner 3 Freq", pct(corner3a, fga)),
        ("Corner 3 Acc", pct(corner3m, corner3a)),
        ("Arc 3 Freq", pct(arc3a, fga)),
        ("Arc 3 Acc", pct(arc3m, arc3a)),
    ]:
        print(f"{k:<18}", "—" if v is None else round(v, 2))

def main():
    endpoints = [
        "https://api.pbpstats.com/get-possessions/nba",
        "https://api.pbpstats.com/get-game-possessions/nba",
    ]

    attempts = []

    for endpoint in endpoints:
        for gid in GAME_IDS_TO_TRY:
            attempts.append((endpoint, {"GameId": gid}))
            attempts.append((endpoint, {"GameId": gid, "Season": "2025-26", "SeasonType": "Playoffs"}))
            attempts.append((endpoint, {"GameId": gid, "Season": "2026", "SeasonType": "Playoffs"}))

    for endpoint, params in attempts:
        print("\nTrying:", endpoint, params)
        js, url = fetch_json(endpoint, params)

        if js is None:
            continue

        raw_path = OUT_DIR / ("raw_" + params["GameId"] + "_" + endpoint.split("/")[-2] + ".json")
        raw_path.write_text(json.dumps(js, indent=2))
        print("Saved raw:", raw_path)

        rows = find_possessions(js)
        print("Possession-like rows:", len(rows))

        if rows:
            print("\nSample keys:")
            print(", ".join(list(rows[0].keys())[:100]))

            calculate(rows)
            return

    print("\nNo possession data could be pulled from PBPStats for this game.")
    print("That means the game is not available through PBPStats right now, or the local 2026 ID is not recognized by their API.")

if __name__ == "__main__":
    main()
