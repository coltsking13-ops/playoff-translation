import json, time, hashlib, sys, re
from pathlib import Path
import requests

BASE = "https://api.pbpstats.com"

ROOT = Path(".")
OUT_ROOT = Path("public/data/pbpstats")
CACHE = OUT_ROOT / "_cache"
GAMES_DIR = OUT_ROOT / "games"
PLAYER_OUT = OUT_ROOT / "player_game_low_removed"
TEAM_OUT = OUT_ROOT / "team_game_low_removed"

for d in [CACHE, GAMES_DIR, PLAYER_OUT, TEAM_OUT]:
    d.mkdir(parents=True, exist_ok=True)

TEAM_IDS = {
    "ATL": "1610612737", "BOS": "1610612738", "CLE": "1610612739", "NOP": "1610612740",
    "CHI": "1610612741", "DAL": "1610612742", "DEN": "1610612743", "GSW": "1610612744",
    "HOU": "1610612745", "LAC": "1610612746", "LAL": "1610612747", "MIA": "1610612748",
    "MIL": "1610612749", "MIN": "1610612750", "BKN": "1610612751", "NJN": "1610612751",
    "NYK": "1610612752", "ORL": "1610612753", "IND": "1610612754", "PHI": "1610612755",
    "PHX": "1610612756", "POR": "1610612757", "SAC": "1610612758", "SAS": "1610612759",
    "OKC": "1610612760", "SEA": "1610612760", "TOR": "1610612761", "UTA": "1610612762",
    "MEM": "1610612763", "VAN": "1610612763", "WAS": "1610612764", "DET": "1610612765",
    "CHA": "1610612766", "CHH": "1610612766",
}
ID_TO_TEAM = {v: k for k, v in TEAM_IDS.items()}

session = requests.Session()
session.headers.update({
    "User-Agent": "playoff-translation-lab/2.0",
    "Accept": "application/json,text/plain,*/*",
})

def season_key(season):
    return season.replace("-", "_")

def playoff_year(season):
    return 2000 + int(season.split("-")[1])

def cache_name(prefix, path, params):
    clean = json.dumps({"path": path, "params": params}, sort_keys=True)
    h = hashlib.sha1(clean.encode()).hexdigest()[:16]
    return CACHE / f"{prefix}__{h}.json"

def api_get(path, params, prefix, retries=10):
    c = cache_name(prefix, path, params)
    if c.exists():
        return json.loads(c.read_text())

    wait = 1
    last_text = ""
    for _ in range(retries):
        r = session.get(BASE + path, params=params, timeout=60)
        print(r.status_code, path.replace("/nba", ""), params, flush=True)

        if r.status_code == 200:
            try:
                data = r.json()
            except Exception:
                data = {"_raw": r.text}
            c.write_text(json.dumps(data), encoding="utf-8")
            return data

        last_text = r.text[:1200]
        if r.status_code in {429, 500, 502, 503, 504}:
            time.sleep(wait)
            wait = min(wait * 2, 20)
            continue

        break

    data = {"_error": True, "_status": "failed", "_text": last_text, "_params": params}
    c.write_text(json.dumps(data), encoding="utf-8")
    return data

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

def minutes_to_seconds(v):
    if v in [None, "", [], {}]:
        return None
    if isinstance(v, (int, float)):
        return float(v) * 60
    if isinstance(v, str) and re.match(r"^\d+:\d\d$", v.strip()):
        m, sec = v.strip().split(":")
        return int(m) * 60 + int(sec)
    return None

def seconds_to_minsec(sec):
    if sec is None:
        return None
    sec = max(0, int(round(sec)))
    return f"{sec // 60}:{sec % 60:02d}"

def get_pid(row):
    for k in ["PlayerId", "EntityId", "RowId", "playerId", "nbaId"]:
        v = row.get(k)
        if v not in [None, ""]:
            return str(v)
    return None

def get_name(row):
    for k in ["Name", "ShortName", "playerName"]:
        v = row.get(k)
        if v not in [None, ""]:
            return str(v)
    return None

def normalize_player_row(row, fallback_id=None):
    row = dict(row)
    if fallback_id and not get_pid(row):
        row["PlayerId"] = str(fallback_id)
    pid = get_pid(row)
    if pid and not row.get("PlayerId"):
        row["PlayerId"] = str(pid)
    return row

def dedupe_by_player(rows):
    best = {}
    for row in rows:
        pid = get_pid(row)
        name = get_name(row)
        if not pid and not name:
            continue

        key = (pid, name)
        footprint = (
            (num(row.get("OffPoss")) or 0)
            + (num(row.get("DefPoss")) or 0)
            + (num(row.get("TotalPoss")) or 0)
            + (minutes_to_seconds(row.get("Minutes")) or 0) / 60
            + (num(row.get("SecondsPlayed")) or 0) / 60
        )

        old = best.get(key)
        if old is None or footprint > old[0]:
            best[key] = (footprint, row)

    return [v[1] for v in best.values()]

def extract_game_stat_player_rows(obj):
    """
    Main fix: only read direct player rows.
    No recursive walk, because PBPStats nested tables duplicate every player 4-6 times.
    """
    if not isinstance(obj, dict):
        return []

    x = obj.get("multi_row_table_data")
    if isinstance(x, list):
        return dedupe_by_player([
            normalize_player_row(r)
            for r in x
            if isinstance(r, dict) and (get_pid(r) or get_name(r))
        ])

    x = obj.get("results")
    if isinstance(x, list):
        return dedupe_by_player([
            normalize_player_row(r)
            for r in x
            if isinstance(r, dict) and (get_pid(r) or get_name(r))
        ])

    if isinstance(x, dict):
        rows = []
        for k, v in x.items():
            if isinstance(v, dict):
                rows.append(normalize_player_row(v, k))
        return dedupe_by_player(rows)

    return []

def extract_possession_player_rows(obj):
    """
    Direct player rows from /get-possessions.
    Works for both Low Offense and Low Defense.
    """
    if not isinstance(obj, dict):
        return []

    x = obj.get("player_results")
    if isinstance(x, dict):
        rows = []
        for k, v in x.items():
            if isinstance(v, dict):
                rows.append(normalize_player_row(v, k))
        return dedupe_by_player(rows)

    x = obj.get("multi_row_table_data")
    if isinstance(x, list):
        return dedupe_by_player([
            normalize_player_row(r)
            for r in x
            if isinstance(r, dict) and (get_pid(r) or get_name(r))
        ])

    x = obj.get("results")
    if isinstance(x, list):
        return dedupe_by_player([
            normalize_player_row(r)
            for r in x
            if isinstance(r, dict) and (get_pid(r) or get_name(r))
        ])

    return []

def to_map(rows):
    out = {}
    for r in rows:
        pid = get_pid(r)
        name = get_name(r)
        if pid or name:
            out[(pid, name)] = r
    return out

OFF_FIELDS = {
    "Points", "FG2M", "FG2A", "FG3M", "FG3A", "FTA", "FtPoints",
    "Assists", "TwoPtAssists", "ThreePtAssists", "AtRimAssists",
    "Turnovers", "LiveBallTurnovers", "DeadBallTurnovers",
    "BadPassTurnovers", "BadPassOutOfBoundsTurnovers",
    "LostBallTurnovers", "LostBallOutOfBoundsTurnovers",
    "StepOutOfBoundsTurnovers",
    "OffRebounds", "FTOffRebounds", "OffTwoPtRebounds", "OffThreePtRebounds",
    "SelfOReb", "Technical Free Throw Trips",
    "AtRimFGM", "AtRimFGA",
    "ShortMidRangeFGM", "ShortMidRangeFGA",
    "LongMidRangeFGM", "LongMidRangeFGA",
    "Corner3FGM", "Corner3FGA",
    "Arc3FGM", "Arc3FGA",
    "NonHeaveArc3FGM", "NonHeaveArc3FGA",
    "HeaveAttempts",
    "PtsUnassisted2s", "PtsUnassisted3s", "PtsAssisted2s", "PtsAssisted3s",
    "PtsPutbacks",
}

DEF_FIELDS = {
    "DefRebounds", "FTDefRebounds", "DefTwoPtRebounds", "DefThreePtRebounds",
    "Steals", "BadPassSteals", "LostBallSteals",
    "Blocks", "BlockedAtRim", "BlockedShortMidRange", "BlockedLongMidRange", "BlockedArc3",
    "OpponentPoints",
}

SPECIAL_SKIP = {
    "EfgPct", "TsPct", "Fg2Pct", "Fg3Pct", "NonHeaveFg3Pct",
    "AtRimFrequency", "AtRimAccuracy",
    "ShortMidRangeFrequency", "ShortMidRangeAccuracy",
    "LongMidRangeFrequency", "LongMidRangeAccuracy",
    "Corner3Frequency", "Corner3Accuracy",
    "Arc3Frequency", "Arc3Accuracy",
    "Usage", "ShotQualityAvg",
    "LiveBallTurnoverPct",
    "SecondsPlayed", "Minutes", "OffPoss", "DefPoss", "TotalPoss", "PlusMinus",
}

def sub_value(all_row, low_row, key):
    return round((num(all_row.get(key)) or 0) - (num(low_row.get(key)) or 0), 6)

def safe_div(a, b):
    a = num(a) or 0
    b = num(b) or 0
    if b <= 0:
        return None
    return a / b

def weighted_medium_avg(all_row, low_row, value_key, weight_key):
    av = num(all_row.get(value_key))
    lv = num(low_row.get(value_key))
    aw = num(all_row.get(weight_key)) or 0
    lw = num(low_row.get(weight_key)) or 0
    mw = aw - lw
    if av is None or mw <= 0:
        return None
    if lv is None:
        return av
    return (av * aw - lv * lw) / mw

def recalc_fields(out, all_row, low_off):
    fg2a = num(out.get("FG2A")) or 0
    fg3a = num(out.get("FG3A")) or 0
    fg2m = num(out.get("FG2M")) or 0
    fg3m = num(out.get("FG3M")) or 0
    fga = fg2a + fg3a
    fta = num(out.get("FTA")) or 0
    pts = num(out.get("Points")) or 0

    out["FGA_Recalc"] = round(fga, 6)
    out["EfgPct_Recalc"] = None if fga <= 0 else round((fg2m + fg3m + 0.5 * fg3m) / fga, 6)
    out["TS_Recalc"] = None if (fga + 0.44 * fta) <= 0 else round(pts / (2 * (fga + 0.44 * fta)), 6)
    out["EfgPct"] = out["EfgPct_Recalc"]
    out["TsPct"] = out["TS_Recalc"]
    out["Fg2Pct"] = None if fg2a <= 0 else round(fg2m / fg2a, 6)
    out["Fg3Pct"] = None if fg3a <= 0 else round(fg3m / fg3a, 6)

    non_heave_arc3a = num(out.get("NonHeaveArc3FGA")) or 0
    non_heave_arc3m = num(out.get("NonHeaveArc3FGM")) or 0
    out["NonHeaveFg3Pct"] = None if non_heave_arc3a <= 0 else round(non_heave_arc3m / non_heave_arc3a, 6)

    for prefix in ["AtRim", "ShortMidRange", "LongMidRange", "Corner3", "Arc3"]:
        makes = num(out.get(f"{prefix}FGM")) or 0
        atts = num(out.get(f"{prefix}FGA")) or 0
        out[f"{prefix}Accuracy"] = None if atts <= 0 else round(makes / atts, 6)
        out[f"{prefix}Frequency"] = None if fga <= 0 else round(atts / fga, 6)

    bp = num(out.get("BadPassTurnovers")) or 0
    bpoob = num(out.get("BadPassOutOfBoundsTurnovers")) or 0
    tov = num(out.get("Turnovers")) or 0
    scoring_tov = max(0, tov - bp - bpoob)

    heaves = max(0, (num(out.get("Arc3FGA")) or 0) - (num(out.get("NonHeaveArc3FGA")) or 0))
    tech_fta = num(out.get("Technical Free Throw Trips")) or 0
    self_oreb = num(out.get("SelfOReb")) or 0

    adj_fga = fga + scoring_tov - heaves - self_oreb
    adj_fta = max(0, fta - tech_fta)

    out["BadPassTOV_Total"] = round(bp + bpoob, 6)
    out["ScoringTOV"] = round(scoring_tov, 6)
    out["Heaves_Est"] = round(heaves, 6)
    out["TechFTA_Est"] = round(tech_fta, 6)
    out["SelfOReb"] = round(self_oreb, 6)
    out["ZBounds"] = round(self_oreb, 6)
    out["ZBoards"] = round(self_oreb, 6)
    out["AdjFGA"] = round(adj_fga, 6)
    out["AdjFTA"] = round(adj_fta, 6)

    denom = 2 * (adj_fga + 0.44 * adj_fta)
    out["AdjTS%"] = None if denom <= 0 else round(100 * pts / denom, 2)

    off_poss = num(out.get("OffPoss")) or 0
    out["LiveBallTurnoverPct"] = None if tov <= 0 else round((num(out.get("LiveBallTurnovers")) or 0) / tov, 6)
    out["Usage"] = weighted_medium_avg(all_row, low_off, "Usage", "OffPoss")
    if out["Usage"] is not None:
        out["Usage"] = round(out["Usage"], 6)

    out["ShotQualityAvg"] = weighted_medium_avg(all_row, low_off, "ShotQualityAvg", "FGA_Recalc")
    if out["ShotQualityAvg"] is None:
        out["ShotQualityAvg"] = weighted_medium_avg(all_row, low_off, "ShotQualityAvg", "FG2A")
    if out["ShotQualityAvg"] is not None:
        out["ShotQualityAvg"] = round(out["ShotQualityAvg"], 6)

    out["PTS_PER_75"] = None if off_poss <= 0 else round(75 * pts / off_poss, 2)
    out["TOV_PER_75"] = None if off_poss <= 0 else round(75 * tov / off_poss, 2)
    out["AST_PER_75"] = None if off_poss <= 0 else round(75 * (num(out.get("Assists")) or 0) / off_poss, 2)
    out["REB_PER_75"] = None if off_poss <= 0 else round(75 * (num(out.get("Rebounds")) or 0) / off_poss, 2)

def build_medium_player_row(all_row, low_off, low_def, meta):
    out = {}

    pid = get_pid(all_row)
    name = get_name(all_row)

    out.update(meta)
    out["playerId"] = pid
    out["playerName"] = name
    out["team"] = all_row.get("TeamAbbreviation") or ID_TO_TEAM.get(str(all_row.get("TeamId", "")))
    out["teamId"] = str(all_row.get("TeamId") or TEAM_IDS.get(out["team"], ""))
    out["filter"] = "Medium+"
    out["source"] = "PBPStats player all minus low offense and low defense"

    for k, v in all_row.items():
        if k in SPECIAL_SKIP:
            continue

        if num(v) is None:
            continue

        if k in OFF_FIELDS:
            out[k] = sub_value(all_row, low_off, k)
        elif k in DEF_FIELDS:
            out[k] = sub_value(all_row, low_def, k)
        else:
            # Mostly harmless box/player fields. If low offense has it, subtract that.
            # If only low defense has it, subtract that.
            if k in low_off:
                out[k] = sub_value(all_row, low_off, k)
            elif k in low_def:
                out[k] = sub_value(all_row, low_def, k)
            else:
                out[k] = v

    all_off = num(all_row.get("OffPoss")) or 0
    all_def = num(all_row.get("DefPoss")) or 0
    low_off_poss = num(low_off.get("OffPoss")) or num(low_off.get("TotalPoss")) or 0
    low_def_poss = num(low_def.get("DefPoss")) or num(low_def.get("TotalPoss")) or 0

    out["OffPoss"] = round(max(0, all_off - low_off_poss), 6)
    out["DefPoss"] = round(max(0, all_def - low_def_poss), 6)
    out["TotalPoss"] = round(out["OffPoss"] + out["DefPoss"], 6)

    all_sec = minutes_to_seconds(all_row.get("Minutes")) or num(all_row.get("SecondsPlayed"))
    low_sec = max(num(low_off.get("SecondsPlayed")) or 0, num(low_def.get("SecondsPlayed")) or 0)
    out["SecondsPlayed"] = None if all_sec is None else round(max(0, all_sec - low_sec), 3)
    out["Minutes"] = seconds_to_minsec(out["SecondsPlayed"])

    out["lowOffPossRemoved"] = round(low_off_poss, 6)
    out["lowDefPossRemoved"] = round(low_def_poss, 6)
    out["lowOffSecondsRemoved"] = num(low_off.get("SecondsPlayed")) or 0
    out["lowDefSecondsRemoved"] = num(low_def.get("SecondsPlayed")) or 0

    # PlusMinus is only approximate if low possession side does not provide both scoring sides.
    all_pm = num(all_row.get("PlusMinus"))
    low_pm_candidates = [num(low_off.get("PlusMinus")), num(low_def.get("PlusMinus"))]
    low_pm_candidates = [x for x in low_pm_candidates if x is not None]
    if all_pm is not None and low_pm_candidates:
        out["PlusMinus"] = round(all_pm - max(low_pm_candidates), 6)

    # Make sure common missing fields are 0 before formulas.
    for k in [
        "Points", "FG2M", "FG2A", "FG3M", "FG3A", "FTA", "FtPoints",
        "Turnovers", "BadPassTurnovers", "BadPassOutOfBoundsTurnovers",
        "Arc3FGA", "NonHeaveArc3FGA", "SelfOReb", "Technical Free Throw Trips",
        "AtRimFGM", "AtRimFGA", "ShortMidRangeFGM", "ShortMidRangeFGA",
        "LongMidRangeFGM", "LongMidRangeFGA", "Corner3FGM", "Corner3FGA",
        "Arc3FGM", "Arc3FGA",
        "Assists", "Rebounds", "OffRebounds", "DefRebounds", "Steals", "Blocks",
    ]:
        if k not in out or out[k] is None:
            out[k] = 0

    out["Rebounds"] = round((num(out.get("OffRebounds")) or 0) + (num(out.get("DefRebounds")) or 0), 6)

    recalc_fields(out, all_row, low_off)

    return out

def extract_games(obj):
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        for k in ["games", "results", "data"]:
            if isinstance(obj.get(k), list):
                return obj[k]
    return []

def get_games(season):
    key = season_key(season)
    local = GAMES_DIR / f"{key}.json"
    if local.exists():
        return extract_games(json.loads(local.read_text()))

    data = api_get("/get-games/nba", {"Season": season, "SeasonType": "Playoffs"}, f"games_{key}")
    games = extract_games(data)
    local.write_text(json.dumps(games, indent=2), encoding="utf-8")
    return games

def game_id(g):
    for k in ["GameId", "gameId", "GAME_ID", "nbaGameId"]:
        if g.get(k):
            return str(g.get(k))
    return None

def game_date(g):
    for k in ["Date", "date", "GameDate", "GAME_DATE"]:
        if g.get(k):
            return str(g.get(k))[:10]
    return None

def teams_from_game(g):
    home = None
    away = None

    for k in ["HomeTeamAbbreviation", "homeTeamAbbreviation", "HomeTeam", "home_team"]:
        if g.get(k):
            home = str(g.get(k)).upper()
    for k in ["AwayTeamAbbreviation", "awayTeamAbbreviation", "AwayTeam", "away_team", "VisitorTeamAbbreviation"]:
        if g.get(k):
            away = str(g.get(k)).upper()

    matchup = str(g.get("Matchup") or g.get("matchup") or "")
    if "@" in matchup and (not home or not away):
        a, h = [x.strip().upper() for x in matchup.split("@", 1)]
        away = away or a[:3]
        home = home or h[:3]

    return home, away

def team_of_row(row):
    team = row.get("TeamAbbreviation")
    if team:
        return str(team).upper()
    tid = str(row.get("TeamId") or "")
    return ID_TO_TEAM.get(tid)

def process_game(season, idx, total, g):
    gid = game_id(g)
    date = game_date(g)
    home, away = teams_from_game(g)

    if not gid or not date or not home or not away:
        print("SKIP bad game row:", g)
        return [], []

    home_id = TEAM_IDS.get(home)
    away_id = TEAM_IDS.get(away)

    if not home_id or not away_id:
        print("SKIP missing team id:", gid, away, "@", home)
        return [], []

    print(f"\n{season} {idx}/{total} {gid} {away} @ {home}", flush=True)

    all_stats = api_get("/get-game-stats", {"GameId": gid, "Type": "Player"}, "game_stats_player")
    all_players = extract_game_stat_player_rows(all_stats)

    low_maps = {}

    for team, tid, opp, oppid in [(home, home_id, away, away_id), (away, away_id, home, home_id)]:
        low_off = api_get("/get-possessions/nba", {
            "Season": season,
            "SeasonType": "Playoffs",
            "TeamId": tid,
            "OffDef": "Offense",
            "FromDate": date,
            "ToDate": date,
            "Opponent": oppid,
            "Leverage": "Low",
        }, "poss_low_offense")

        low_def = api_get("/get-possessions/nba", {
            "Season": season,
            "SeasonType": "Playoffs",
            "TeamId": tid,
            "OffDef": "Defense",
            "FromDate": date,
            "ToDate": date,
            "Opponent": oppid,
            "Leverage": "Low",
        }, "poss_low_defense")

        low_maps[team] = {
            "off": to_map(extract_possession_player_rows(low_off)),
            "def": to_map(extract_possession_player_rows(low_def)),
        }

    rows = []
    meta_base = {
        "year": playoff_year(season),
        "season": season,
        "gameId": gid,
        "nbaGameId": gid,
        "date": date,
        "homeTeam": home,
        "awayTeam": away,
    }

    for all_row in all_players:
        team = team_of_row(all_row)
        if team not in low_maps:
            continue

        pid = get_pid(all_row)
        name = get_name(all_row)
        key = (pid, name)

        low_off = low_maps[team]["off"].get(key, {})
        low_def = low_maps[team]["def"].get(key, {})

        meta = dict(meta_base)
        meta["opponent"] = away if team == home else home
        rows.append(build_medium_player_row(all_row, low_off, low_def, meta))

    team_rows = [
        {
            "year": playoff_year(season),
            "season": season,
            "gameId": gid,
            "date": date,
            "team": home,
            "opponent": away,
            "filter": "Medium+",
            "source": "placeholder; player build uses low offense + low defense",
        },
        {
            "year": playoff_year(season),
            "season": season,
            "gameId": gid,
            "date": date,
            "team": away,
            "opponent": home,
            "filter": "Medium+",
            "source": "placeholder; player build uses low offense + low defense",
        },
    ]

    print("player rows:", len(rows), "team rows:", len(team_rows), flush=True)
    return rows, team_rows

def main():
    seasons = sys.argv[1:] or ["2017-18"]

    manifest = {
        "source": "PBPStats API",
        "filter": "Medium+ / Low Leverage Removed",
        "method": "All player stats minus Low Offense and Low Defense possession pulls",
        "seasons": {},
    }

    for season in seasons:
        year = playoff_year(season)
        games = get_games(season)

        all_rows = []
        all_team_rows = []

        for i, g in enumerate(games, 1):
            rows, team_rows = process_game(season, i, len(games), g)
            all_rows.extend(rows)
            all_team_rows.extend(team_rows)

            # Save every game so Codespaces stopping does not lose progress.
            (PLAYER_OUT / f"{year}.json").write_text(json.dumps(all_rows, indent=2), encoding="utf-8")
            (TEAM_OUT / f"{year}.json").write_text(json.dumps(all_team_rows, indent=2), encoding="utf-8")

        manifest["seasons"][str(year)] = {
            "season": season,
            "games": len(games),
            "player_rows": len(all_rows),
            "team_rows": len(all_team_rows),
            "player_file": str(PLAYER_OUT / f"{year}.json"),
            "team_file": str(TEAM_OUT / f"{year}.json"),
        }

    (OUT_ROOT / "pbpstats_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("\nDONE")
    print(json.dumps(manifest, indent=2))

if __name__ == "__main__":
    main()
