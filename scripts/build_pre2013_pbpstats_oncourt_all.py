import json, time, hashlib, sys, re
from pathlib import Path
import requests

BASE = "https://api.pbpstats.com"

OUT_ROOT = Path("public/data/pre2013")
CACHE = OUT_ROOT / "_cache"
PLAYER_OUT = OUT_ROOT / "player_oncourt_game_all"

for d in [CACHE, PLAYER_OUT]:
    d.mkdir(parents=True, exist_ok=True)

TEAM_IDS = {
    "ATL": "1610612737", "BOS": "1610612738", "CLE": "1610612739",
    "NOH": "1610612740", "NOK": "1610612740", "NOP": "1610612740", "NOL": "1610612740",
    "CHI": "1610612741", "DAL": "1610612742", "DEN": "1610612743", "GSW": "1610612744",
    "HOU": "1610612745", "LAC": "1610612746", "LAL": "1610612747", "MIA": "1610612748",
    "MIL": "1610612749", "MIN": "1610612750", "NJN": "1610612751", "BKN": "1610612751",
    "NYK": "1610612752", "ORL": "1610612753", "IND": "1610612754", "PHI": "1610612755",
    "PHX": "1610612756", "POR": "1610612757", "SAC": "1610612758", "SAS": "1610612759",
    "SEA": "1610612760", "OKC": "1610612760", "TOR": "1610612761", "UTA": "1610612762",
    "VAN": "1610612763", "MEM": "1610612763", "WAS": "1610612764", "DET": "1610612765",
    "CHH": "1610612766", "CHA": "1610612766",
}

session = requests.Session()
session.headers.update({
    "User-Agent": "playoff-translation-lab-pre2013/1.0",
    "Accept": "application/json,text/plain,*/*",
})

def season_from_year(year):
    year = int(year)
    return f"{year - 1}-{str(year)[-2:]}"

def cache_path(path, params):
    raw = json.dumps({"path": path, "params": params}, sort_keys=True)
    h = hashlib.sha1(raw.encode()).hexdigest()[:18]
    return CACHE / f"wowy__{h}.json"

def api_get(path, params, retries=10):
    c = cache_path(path, params)

    if c.exists():
        return json.loads(c.read_text())

    wait = 1
    last = ""

    for _ in range(retries):
        r = session.get(BASE + path, params=params, timeout=60)
        print(r.status_code, path, params, flush=True)

        if r.status_code == 200:
            try:
                data = r.json()
            except Exception:
                data = {"_raw": r.text}
            c.write_text(json.dumps(data), encoding="utf-8")
            return data

        last = r.text[:1200]

        if r.status_code in {429, 500, 502, 503, 504}:
            time.sleep(wait)
            wait = min(wait * 2, 20)
            continue

        break

    # Do not cache permanent failure as successful data.
    return {"_error": True, "_status": "failed", "_text": last, "_params": params}

def first(v, keys):
    for k in keys:
        x = v.get(k)
        if x not in [None, "", [], {}]:
            return x
    return None

def clean_team(t):
    if t is None:
        return None
    return str(t).upper().strip()

def numeric_player_id(row):
    for k in ["nbaId", "PlayerId", "playerId", "EntityId", "RowId"]:
        v = row.get(k)
        if v not in [None, ""]:
            s = str(v).strip()
            if s.isdigit():
                return s
    return None

def num(v):
    if v in [None, "", [], {}]:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.strip()
        if re.match(r"^\d+:\d\d$", s):
            m, sec = s.split(":")
            return float(m) + float(sec) / 60
        try:
            return float(s)
        except Exception:
            return None
    return None

def get_row(data):
    if not isinstance(data, dict):
        return {}

    x = data.get("single_row_table_data")
    if isinstance(x, dict) and x:
        return x

    x = data.get("multi_row_table_data")
    if isinstance(x, list) and x:
        for r in x:
            if isinstance(r, dict) and r:
                return r

    x = data.get("results")
    if isinstance(x, list) and x:
        for r in x:
            if isinstance(r, dict) and r:
                return r
    if isinstance(x, dict) and x:
        return x

    return {}

def fga(row):
    return (num(row.get("FG2A")) or 0) + (num(row.get("FG3A")) or 0)

def safe_rate(a, b, mult=1):
    a = num(a) or 0
    b = num(b) or 0
    if b <= 0:
        return None
    return round(mult * a / b, 6)

def prefix_fields(prefix, row):
    keep = [
        "SecondsPlayed", "Minutes", "PlusMinus",
        "OffPoss", "DefPoss", "TotalPoss",
        "Points", "OpponentPoints",
        "FG2M", "FG2A", "FG3M", "FG3A", "FTA", "FtPoints",
        "Assists", "Turnovers", "LiveBallTurnovers",
        "OffRebounds", "DefRebounds", "Rebounds",
        "EfgPct", "TsPct",
        "AtRimFGM", "AtRimFGA", "AtRimFrequency", "AtRimAccuracy",
        "ShortMidRangeFGM", "ShortMidRangeFGA", "ShortMidRangeFrequency", "ShortMidRangeAccuracy",
        "LongMidRangeFGM", "LongMidRangeFGA", "LongMidRangeFrequency", "LongMidRangeAccuracy",
        "Corner3FGM", "Corner3FGA", "Corner3Frequency", "Corner3Accuracy",
        "Arc3FGM", "Arc3FGA", "Arc3Frequency", "Arc3Accuracy",
        "NonHeaveArc3FGM", "NonHeaveArc3FGA", "NonHeaveFg3Pct",
        "ShotQualityAvg",
        "PenaltyPoints", "PenaltyOffPoss", "PenaltyDefPoss",
        "SecondChancePoints", "SecondChanceOffPoss",
    ]

    out = {}
    for k in keep:
        if k in row:
            out[f"{prefix}{k}"] = row.get(k)
    return out

def derived_team(prefix, row):
    pts = num(row.get("Points")) or 0
    opp_pts = num(row.get("OpponentPoints")) or 0
    off_poss = num(row.get("OffPoss")) or 0
    def_poss = num(row.get("DefPoss")) or 0
    tov = num(row.get("Turnovers")) or 0
    orb = num(row.get("OffRebounds")) or 0
    attempts = fga(row)
    fta = num(row.get("FTA")) or 0

    return {
        f"{prefix}ORTG": None if off_poss <= 0 else round(100 * pts / off_poss, 2),
        f"{prefix}DRTG": None if def_poss <= 0 else round(100 * opp_pts / def_poss, 2),
        f"{prefix}NET": None if off_poss <= 0 or def_poss <= 0 else round((100 * pts / off_poss) - (100 * opp_pts / def_poss), 2),
        f"{prefix}TOVRate": None if off_poss <= 0 else round(100 * tov / off_poss, 2),
        f"{prefix}ORBPerOffPoss": None if off_poss <= 0 else round(100 * orb / off_poss, 2),
        f"{prefix}FTr": None if attempts <= 0 else round(fta / attempts, 4),
        f"{prefix}FGA": round(attempts, 6),
    }

def fetch_wowy(season, team_id, opp_id, date, gid, player_id, typ):
    params = {
        "Season": season,
        "SeasonType": "Playoffs",
        "TeamId": team_id,
        "PlayerId": player_id,
        "Type": typ,
    }

    if opp_id:
        params["Opponent"] = opp_id

    if date:
        params["FromDate"] = date
        params["ToDate"] = date
    elif gid:
        params["GameId"] = gid

    data = api_get("/get-wowy-stats/nba", params)
    return get_row(data), data

def load_player_games():
    data = json.loads(Path("data-package.json").read_text())
    rows = data.get("playerGames", [])
    if not isinstance(rows, list):
        raise SystemExit("data-package.json playerGames is missing or not a list")
    return rows

def build_year(year):
    season = season_from_year(year)
    year = int(year)

    raw_rows = [
        r for r in load_player_games()
        if int(r.get("year", 0) or 0) == year
    ]

    out_file = PLAYER_OUT / f"{year}.json"

    existing = []
    done = set()

    if out_file.exists():
        try:
            existing = json.loads(out_file.read_text())
            for r in existing:
                done.add((str(r.get("gameId")), str(r.get("playerApiId")), str(r.get("team"))))
        except Exception:
            existing = []
            done = set()

    unique = []
    seen = set()

    for r in raw_rows:
        gid = str(first(r, ["nbaGameId", "gameId", "GameId"]) or "")
        date = first(r, ["date", "gameDate", "GameDate"])
        if date:
            date = str(date)[:10]

        team = clean_team(first(r, ["team", "TEAM", "TeamAbbreviation", "teamAbbreviation"]))
        opp = clean_team(first(r, ["opponent", "opp", "Opponent", "opponentAbbreviation"]))
        pid = numeric_player_id(r)
        pname = first(r, ["playerName", "Name", "ShortName"])

        if not gid or not team or not opp or not pid:
            continue

        key = (gid, pid, team)

        if key in seen:
            continue
        seen.add(key)

        unique.append({
            "sourceRow": r,
            "gameId": gid,
            "date": date,
            "team": team,
            "opponent": opp,
            "playerApiId": pid,
            "playerName": pname,
        })

    print(f"\nYEAR {year} / {season}")
    print("source player-game rows:", len(raw_rows))
    print("unique fetch rows:", len(unique))
    print("already done:", len(done))

    rows = existing[:]

    for i, item in enumerate(unique, 1):
        key = (str(item["gameId"]), str(item["playerApiId"]), str(item["team"]))

        if key in done:
            continue

        team_id = TEAM_IDS.get(item["team"])
        opp_id = TEAM_IDS.get(item["opponent"])

        if not team_id or not opp_id:
            print("SKIP missing team id:", item)
            continue

        print(
            f"\n{year} {i}/{len(unique)} {item['playerName']} "
            f"{item['team']} vs {item['opponent']} {item['gameId']}",
            flush=True
        )

        team_row, team_data = fetch_wowy(
            season, team_id, opp_id, item["date"], item["gameId"], item["playerApiId"], "Team"
        )

        opp_row, opp_data = fetch_wowy(
            season, team_id, opp_id, item["date"], item["gameId"], item["playerApiId"], "Opponent"
        )

        source = item["sourceRow"]

        out = {
            "year": year,
            "season": season,
            "filter": "All",
            "source": "PBPStats WOWY all-leverage player ON-court",
            "gameId": item["gameId"],
            "nbaGameId": item["gameId"],
            "date": item["date"],
            "team": item["team"],
            "opponent": item["opponent"],
            "teamId": team_id,
            "opponentId": opp_id,
            "playerApiId": item["playerApiId"],
            "playerId": source.get("playerId"),
            "nbaId": source.get("nbaId") or item["playerApiId"],
            "playerName": item["playerName"],
            "teamFetchOk": bool(team_row),
            "opponentFetchOk": bool(opp_row),
        }

        out.update(prefix_fields("onTeam", team_row))
        out.update(derived_team("onTeam", team_row))

        out.update(prefix_fields("onOpp", opp_row))
        out.update(derived_team("onOpp", opp_row))

        # Defensive rating allowed. Prefer Type=Opponent Points/OffPoss when available.
        opp_pts = num(opp_row.get("Points"))
        opp_off_poss = num(opp_row.get("OffPoss"))
        if opp_pts is not None and opp_off_poss and opp_off_poss > 0:
            out["onDRTG_allowed"] = round(100 * opp_pts / opp_off_poss, 2)
        else:
            out["onDRTG_allowed"] = out.get("onTeamDRTG")

        out["onNET_final"] = None
        if out.get("onTeamORTG") is not None and out.get("onDRTG_allowed") is not None:
            out["onNET_final"] = round(out["onTeamORTG"] - out["onDRTG_allowed"], 2)

        rows.append(out)
        done.add(key)

        if len(rows) % 10 == 0:
            out_file.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    out_file.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"\nWROTE {out_file} rows={len(rows)}")

    return {
        "year": year,
        "season": season,
        "rows": len(rows),
        "file": str(out_file),
    }

def parse_year_args(args):
    if not args:
        return list(range(2001, 2013))

    years = []
    for a in args:
        a = str(a)
        if "-" in a and len(a.split("-")[0]) == 4:
            start, end = a.split("-", 1)
            years.extend(range(int(start), int(end) + 1))
        else:
            years.append(int(a))
    return sorted(set(years))

def main():
    years = parse_year_args(sys.argv[1:])
    manifest = {
        "source": "PBPStats WOWY",
        "filter": "All leverage only",
        "years": {},
        "description": "2001-2012 player ON-court team/offense and opponent/defense shot profile and six-factor context.",
    }

    for y in years:
        info = build_year(y)
        manifest["years"][str(y)] = info
        (OUT_ROOT / "pre2013_oncourt_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print("\nDONE")
    print(json.dumps(manifest, indent=2))

if __name__ == "__main__":
    main()
