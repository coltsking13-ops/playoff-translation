#!/usr/bin/env python3
import json
import re
import time
import requests
from pathlib import Path
from collections import defaultdict

BASE = "https://api.pbpstats.com"

OUT_DIR = Path("public/data/on_court_all_leverage")
RAW_DIR = OUT_DIR / "raw_years"
OUT_DIR.mkdir(parents=True, exist_ok=True)
RAW_DIR.mkdir(parents=True, exist_ok=True)

TEAM_IDS = {
    "ATL": 1610612737, "BOS": 1610612738, "BKN": 1610612751, "BRK": 1610612751,
    "CHA": 1610612766, "CHH": 1610612766, "CHI": 1610612741, "CLE": 1610612739,
    "DAL": 1610612742, "DEN": 1610612743, "DET": 1610612765, "GSW": 1610612744,
    "HOU": 1610612745, "IND": 1610612754, "LAC": 1610612746, "LAL": 1610612747,
    "MEM": 1610612763, "MIA": 1610612748, "MIL": 1610612749, "MIN": 1610612750,
    "NOP": 1610612740, "NOH": 1610612740, "NYK": 1610612752, "OKC": 1610612760,
    "ORL": 1610612753, "PHI": 1610612755, "PHX": 1610612756, "POR": 1610612757,
    "SAC": 1610612758, "SAS": 1610612759, "TOR": 1610612761, "UTA": 1610612762,
    "WAS": 1610612764,
}
ID_TO_TEAM = {str(v): k for k, v in TEAM_IDS.items()}

def season_string(end_year):
    return f"{int(end_year)-1}-{str(end_year)[-2:]}"

def numeric_id(value):
    s = str(value or "")
    nums = re.findall(r"\d+", s)
    return nums[-1] if nums else ""

def pct(v):
    if v in [None, ""]:
        return None
    try:
        return round(float(v) * 100, 3)
    except Exception:
        return None

def num(v):
    if v in [None, ""]:
        return None
    try:
        return round(float(v), 3)
    except Exception:
        return None

def read_package():
    for p in [Path("data-package.json"), Path("public/data/data-package.embedded.json")]:
        if p.exists():
            return json.loads(p.read_text(errors="ignore"))
    raise SystemExit("No package found")

def get_year(row):
    try:
        return int(row.get("year") or row.get("season") or row.get("SEASON") or 0)
    except Exception:
        return 0

def get_team(row):
    return str(row.get("team") or row.get("TEAM") or row.get("teamAbbr") or row.get("TEAM_ABBREVIATION") or "").upper()

def get_name(row):
    return str(row.get("playerName") or row.get("PLAYER_NAME") or row.get("name") or "")

def get_game_id(row):
    return str(row.get("gameId") or row.get("GAME_ID") or "").replace("00", "", 1)

def api_get(path, params, retries=3, sleep=0.35):
    url = BASE + path

    for i in range(retries):
        try:
            r = requests.get(url, params=params, timeout=8)
            if r.ok:
                try:
                    return r.json()
                except Exception:
                    return {"error": "json_parse", "text": r.text[:500], "url": r.url}

            if i == retries - 1:
                return {"error": f"status_{r.status_code}", "text": r.text[:500], "url": r.url}

            time.sleep(1.5 + i)

        except Exception as e:
            if i == retries - 1:
                return {"error": str(e), "url": url, "params": params}
            time.sleep(1.5 + i)

    time.sleep(sleep)
    return {"error": "unknown"}

def parse_four_factor(obj):
    out = {}

    def apply(prefix, rows):
        for r in rows or []:
            stat = str(r.get("stat") or "").lower()
            on = pct(r.get("On"))
            off = pct(r.get("Off"))

            if "efg" in stat:
                out[f"{prefix}EFG"] = on
                out[f"{prefix}EFGOff"] = off
            elif "oreb" in stat:
                out[f"{prefix}OREBPct"] = on
                out[f"{prefix}OREBPctOff"] = off
            elif "ftr" in stat:
                out[f"{prefix}FTr"] = on
                out[f"{prefix}FTrOff"] = off
            elif "tov" in stat:
                out[f"{prefix}TOVPct"] = on
                out[f"{prefix}TOVPctOff"] = off

    apply("onTeam", obj.get("offense_results"))
    apply("onOpp", obj.get("defense_results"))

    out["onMinutes"] = num(obj.get("minutes_on"))
    out["offMinutes"] = num(obj.get("minutes_off"))

    return out

def parse_wowy(obj, player_name):
    rows = obj.get("results") if isinstance(obj, dict) else []
    if not isinstance(rows, list):
        return {}

    target = None
    pn = player_name.lower()

    for r in rows:
        on = str(r.get("On") or "").lower()
        off = str(r.get("Off") or "").lower()

        if pn in on and pn not in off:
            target = r
            break

    if not target:
        for r in rows:
            on = str(r.get("On") or "")
            off = str(r.get("Off") or "")
            if on and not off:
                target = r
                break

    if not target:
        return {}

    return {
        "onTeamORTG": num(target.get("OffRtg")),
        "onTeamDRTG": num(target.get("DefRtg")),
        "onTeamNET": num(target.get("NetRtg")),
        "onMinutesWOWY": num(target.get("Minutes")),
        "onTeamFg3Pct": pct(target.get("Fg3Pct")),
        "onTeamFg2Pct": pct(target.get("Fg2Pct")),
        "onOppFg3Pct": pct(target.get("OppFg3Pct")),
        "onOppFg2Pct": pct(target.get("OppFg2Pct")),
    }

def shot_zone(shot):
    st = str(shot.get("shot_type") or "").lower()
    sv = int(float(shot.get("shot_value") or 0))
    try:
        d = float(shot.get("shot_distance") or 0)
    except Exception:
        d = 0

    if "rim" in st or "dunk" in st or "layup" in st or d <= 4:
        return "rim"
    if "short mid" in st or (sv == 2 and 4 < d <= 14):
        return "shortMid"
    if "long mid" in st or (sv == 2 and d > 14):
        return "longMid"
    if "corner" in st and sv == 3:
        return "corner3"
    if sv == 3:
        return "aboveBreak3"
    return "other"

def init_shot_obj():
    return {
        "fga": 0,
        "fgm": 0,
        "threePA": 0,
        "threePM": 0,
        "zones": defaultdict(lambda: {"fga": 0, "fgm": 0})
    }

def add_shot(obj, shot):
    made = bool(shot.get("made"))
    sv = int(float(shot.get("shot_value") or 0))
    zone = shot_zone(shot)

    obj["fga"] += 1
    obj["fgm"] += 1 if made else 0

    if sv == 3:
        obj["threePA"] += 1
        obj["threePM"] += 1 if made else 0

    obj["zones"][zone]["fga"] += 1
    obj["zones"][zone]["fgm"] += 1 if made else 0

def finalize_shots(prefix, obj):
    fga = obj["fga"]
    fgm = obj["fgm"]
    out = {
        f"{prefix}FGA": fga,
        f"{prefix}FGM": fgm,
        f"{prefix}FGPct": round(fgm / fga * 100, 3) if fga else None,
        f"{prefix}3PA": obj["threePA"],
        f"{prefix}3PM": obj["threePM"],
        f"{prefix}3PAr": round(obj["threePA"] / fga * 100, 3) if fga else None,
        f"{prefix}3PPct": round(obj["threePM"] / obj["threePA"] * 100, 3) if obj["threePA"] else None,
    }

    for z in ["rim", "shortMid", "longMid", "corner3", "aboveBreak3", "other"]:
        zfga = obj["zones"][z]["fga"]
        zfgm = obj["zones"][z]["fgm"]
        label = z[0].upper() + z[1:]
        out[f"{prefix}{label}FGA"] = zfga
        out[f"{prefix}{label}FGM"] = zfgm
        out[f"{prefix}{label}Freq"] = round(zfga / fga * 100, 3) if fga else None
        out[f"{prefix}{label}FGPct"] = round(zfgm / zfga * 100, 3) if zfga else None

    return out

def lineup_ids(value):
    return [x for x in str(value or "").split("-") if x]

def fetch_team_year_shots(year, team, team_id):
    season = season_string(year)
    all_shots = {}
    errors = []

    # Split by period so we avoid API result caps.
    for period in range(1, 11):
        params = {
            "Season": season,
            "SeasonType": "Playoffs",
            "EntityType": "Team",
            "EntityId": str(team_id),
            "PeriodEquals": period,
        }

        obj = api_get("/get-shots/nba", params)
        rows = obj.get("results") if isinstance(obj, dict) else []

        if not isinstance(rows, list):
            errors.append(obj)
            continue

        for s in rows:
            key = (
                str(s.get("gid")),
                str(s.get("event_num")),
                str(s.get("player_id")),
                str(s.get("period")),
            )
            all_shots[key] = s

        print(f"{year} {team} period {period}: {len(rows)} shots")

        time.sleep(0.25)

    return list(all_shots.values()), errors

def build_year(year):
    data = read_package()
    rows = [r for r in data.get("playerGames", []) if isinstance(r, dict) and get_year(r) == year]

    players = {}
    teams = {}

    for r in rows:
        pid = numeric_id(r.get("playerId") or r.get("PLAYER_ID") or r.get("nbaId") or r.get("NBA_ID"))
        team = get_team(r)
        name = get_name(r)

        if not pid or not team or team not in TEAM_IDS:
            continue

        key = (pid, team)
        players[key] = {
            "playerId": pid,
            "playerName": name,
            "team": team,
            "teamId": TEAM_IDS[team],
            "year": year,
            "season": season_string(year),
        }
        teams[team] = TEAM_IDS[team]

    print("")
    print(f"YEAR {year}")
    print("Players:", len(players))
    print("Teams:", len(teams), sorted(teams))

    season_rows = []
    shot_game = defaultdict(lambda: {"off": init_shot_obj(), "def": init_shot_obj()})

    # 1. Season-level ON four factors and WOWY ORTG/DRTG/NET.
    for i, ((pid, team), p) in enumerate(sorted(players.items()), 1):
        ff = api_get("/get-four-factor-on-off/nba", {
            "Season": p["season"],
            "SeasonType": "Playoffs",
            "TeamId": str(p["teamId"]),
            "PlayerId": str(pid),
        })

        wowy = {}  # skipped: fast ON 4 factors + shot-location build

        row = dict(p)
        row.update(parse_four_factor(ff if isinstance(ff, dict) else {}))
        # WOWY skipped
        row["hasOnCourtFourFactors"] = any(k.startswith("onTeam") for k in row)
        row["hasOnCourtWOWY"] = False

        season_rows.append(row)

        print(f"{year} season ON rows {i}/{len(players)}: {p['playerName']} {p['team']}", flush=True)

        time.sleep(0.35)

    # 2. Game-level shot location ON/Opp ON from lineups.
    for team, team_id in sorted(teams.items()):
        shots, errors = fetch_team_year_shots(year, team, team_id)

        raw_path = RAW_DIR / f"{year}_{team}_shots.json"
        raw_path.write_text(json.dumps({"team": team, "teamId": team_id, "shots": shots, "errors": errors}, separators=(",", ":"), ensure_ascii=False))

        for s in shots:
            gid = str(s.get("gid") or "")
            off_team = str(s.get("team") or team).upper()
            def_team = str(s.get("opponent") or "").upper()

            for pid in lineup_ids(s.get("lineup_id")):
                key = (pid, year, off_team, gid)
                add_shot(shot_game[key]["off"], s)

            for pid in lineup_ids(s.get("opponent_lineup_id")):
                key = (pid, year, def_team, gid)
                add_shot(shot_game[key]["def"], s)

    game_rows = []

    name_map = {}
    for r in rows:
        pid = numeric_id(r.get("playerId") or r.get("PLAYER_ID") or r.get("nbaId") or r.get("NBA_ID"))
        if pid:
            name_map[pid] = get_name(r)

    for (pid, y, team, gid), obj in sorted(shot_game.items()):
        row = {
            "playerId": pid,
            "playerName": name_map.get(pid, ""),
            "year": y,
            "season": season_string(y),
            "team": team,
            "gameId": gid,
            "hasOnCourtShotLocation": True,
        }
        row.update(finalize_shots("onTeam", obj["off"]))
        row.update(finalize_shots("onOpp", obj["def"]))
        game_rows.append(row)

    season_path = OUT_DIR / f"player_on_season_four_factors_{year}.json"
    game_path = OUT_DIR / f"player_on_game_shot_locations_{year}.json"

    season_path.write_text(json.dumps(season_rows, separators=(",", ":"), ensure_ascii=False))
    game_path.write_text(json.dumps(game_rows, separators=(",", ":"), ensure_ascii=False))

    print("")
    print("WROTE", season_path, len(season_rows), "rows")
    print("WROTE", game_path, len(game_rows), "rows")

def parse_range(arg):
    if "-" in arg:
        a, b = arg.split("-", 1)
        return range(int(a), int(b) + 1)
    return [int(arg)]

if __name__ == "__main__":
    import sys
    years = parse_range(sys.argv[1]) if len(sys.argv) > 1 else range(2013, 2027)
    for y in years:
        build_year(y)
