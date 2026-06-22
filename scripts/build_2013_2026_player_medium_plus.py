import json, time, hashlib, sys, re
from pathlib import Path
from collections import defaultdict, Counter
import requests

BASE = "https://api.pbpstats.com"

OUT_ROOT = Path("public/data/pbpstats")
CACHE = OUT_ROOT / "_cache"
GAMES_DIR = OUT_ROOT / "games"
PLAYER_OUT = OUT_ROOT / "player_game_low_removed"
AUDIT_DIR = OUT_ROOT / "audit"

for d in [CACHE, GAMES_DIR, PLAYER_OUT, AUDIT_DIR]:
    d.mkdir(parents=True, exist_ok=True)

TEAM_IDS = {
    "ATL": "1610612737", "BOS": "1610612738", "CLE": "1610612739", "NOP": "1610612740",
    "NOH": "1610612740", "NOK": "1610612740", "NOL": "1610612740",
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
    "User-Agent": "playoff-translation-lab-medium-plus/1.0",
    "Accept": "application/json,text/plain,*/*",
})

def playoff_year(season):
    return 2000 + int(season.split("-")[1])

def season_from_year(year):
    return f"{int(year)-1}-{str(year)[-2:]}"

def cache_path(prefix, path, params):
    raw = json.dumps({"path": path, "params": params}, sort_keys=True)
    h = hashlib.sha1(raw.encode()).hexdigest()[:18]
    return CACHE / f"{prefix}__{h}.json"

def api_get(path, params, prefix, retries=12):
    c = cache_path(prefix, path, params)
    if c.exists():
        try:
            return json.loads(c.read_text())
        except Exception:
            c.unlink(missing_ok=True)

    wait = 1
    last = ""

    for attempt in range(1, retries + 1):
        try:
            r = session.get(BASE + path, params=params, timeout=75)
            print(r.status_code, path.replace("/nba", ""), params, flush=True)

            if r.status_code == 200:
                try:
                    data = r.json()
                except Exception:
                    data = {"_raw": r.text}
                c.write_text(json.dumps(data), encoding="utf-8")
                return data

            last = r.text[:1500]

            if r.status_code in {429, 500, 502, 503, 504}:
                time.sleep(wait)
                wait = min(wait * 2, 30)
                continue

            break

        except Exception as e:
            last = repr(e)
            print("REQUEST ERROR", path, params, last, flush=True)
            time.sleep(wait)
            wait = min(wait * 2, 30)

    return {"_error": True, "_status": "failed_after_retries", "_text": last, "_params": params}

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

def minsec_to_seconds(v):
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

def footprint(row):
    return (
        (num(row.get("OffPoss")) or 0)
        + (num(row.get("DefPoss")) or 0)
        + (num(row.get("TotalPoss")) or 0)
        + ((num(row.get("SecondsPlayed")) or 0) / 60)
        + ((minsec_to_seconds(row.get("Minutes")) or 0) / 60)
    )

def dedupe_by_player(rows):
    best = {}
    for r in rows:
        pid = get_pid(r)
        name = get_name(r)
        if not pid and not name:
            continue
        key = (pid, name)
        fp = footprint(r)
        old = best.get(key)
        if old is None or fp > old[0]:
            best[key] = (fp, r)
    return [v[1] for v in best.values()]

ALL_ROW_HINTS = {
    "Points", "OffPoss", "DefPoss", "Minutes", "SecondsPlayed",
    "FG2A", "FG3A", "FTA", "Turnovers", "AtRimFGA",
    "Corner3FGA", "Arc3FGA", "TsPct", "EfgPct", "Usage"
}

def looks_like_all_player_row(x):
    if not isinstance(x, dict):
        return False
    if not (get_pid(x) or get_name(x)):
        return False
    hits = sum(1 for k in ALL_ROW_HINTS if k in x)
    return hits >= 3

def walk_all_player_rows(x, rows):
    if isinstance(x, dict):
        if looks_like_all_player_row(x):
            rows.append(normalize_player_row(x))
        for v in x.values():
            walk_all_player_rows(v, rows)
    elif isinstance(x, list):
        for v in x:
            walk_all_player_rows(v, rows)

def merge_duplicate_player_rows(rows):
    """
    Merge duplicated nested PBPStats rows into one row per player.
    Use the biggest-footprint row as the base, then fill missing fields
    from other rows for the same player. Do not sum duplicate rows.
    """
    groups = {}

    for r in rows:
        pid = get_pid(r)
        name = get_name(r)
        if not pid and not name:
            continue
        key = (pid, name)
        groups.setdefault(key, []).append(r)

    merged_rows = []

    for key, group in groups.items():
        group = sorted(group, key=footprint, reverse=True)
        base = dict(group[0])

        for r in group[1:]:
            for k, v in r.items():
                if k not in base or base.get(k) in [None, "", [], {}]:
                    base[k] = v

        merged_rows.append(base)

    return merged_rows

def extract_game_stat_player_rows(obj):
    """
    Extract one all-leverage row per player from /get-game-stats Type=Player.
    First tries direct tables. If PBPStats nests the rows deeper, it safely
    walks the response and merges duplicates into one row per player.
    """
    if not isinstance(obj, dict):
        return []

    direct = []

    x = obj.get("multi_row_table_data")
    if isinstance(x, list):
        direct.extend([
            normalize_player_row(r)
            for r in x
            if isinstance(r, dict) and looks_like_all_player_row(r)
        ])

    x = obj.get("results")
    if isinstance(x, list):
        direct.extend([
            normalize_player_row(r)
            for r in x
            if isinstance(r, dict) and looks_like_all_player_row(r)
        ])

    if direct:
        return merge_duplicate_player_rows(direct)

    walked = []
    walk_all_player_rows(obj, walked)
    return merge_duplicate_player_rows(walked)


ROW_HINTS = {
    "Points", "OffPoss", "TotalPoss", "SecondsPlayed", "AtRimFGA",
    "FG2A", "FG3A", "FTA", "Turnovers", "Rebounds", "Steals", "Blocks"
}

def looks_like_player_stat_row(x):
    if not isinstance(x, dict):
        return False
    if not (get_pid(x) or get_name(x)):
        return False
    hits = sum(1 for k in ROW_HINTS if k in x)
    return hits >= 2

def walk_low_rows(x, rows):
    if isinstance(x, dict):
        if looks_like_player_stat_row(x):
            rows.append(normalize_player_row(x))
        for v in x.values():
            walk_low_rows(v, rows)
    elif isinstance(x, list):
        for v in x:
            walk_low_rows(v, rows)

def extract_possession_player_rows(obj):
    """
    Low Offense / Low Defense extractor.
    Direct player_results first, then safe fallback walk.
    """
    if not isinstance(obj, dict):
        return []

    x = obj.get("player_results")
    if isinstance(x, dict):
        rows = []
        for k, v in x.items():
            if isinstance(v, dict):
                rows.append(normalize_player_row(v, k))
        direct = dedupe_by_player(rows)
        if direct:
            return direct

    x = obj.get("multi_row_table_data")
    if isinstance(x, list):
        direct = dedupe_by_player([
            normalize_player_row(r)
            for r in x
            if isinstance(r, dict) and (get_pid(r) or get_name(r))
        ])
        if direct:
            return direct

    x = obj.get("results")
    if isinstance(x, list):
        direct = dedupe_by_player([
            normalize_player_row(r)
            for r in x
            if isinstance(r, dict) and (get_pid(r) or get_name(r))
        ])
        if direct:
            return direct

    rows = []
    walk_low_rows(obj, rows)
    return dedupe_by_player(rows)

def map_rows(rows):
    by_pid = {}
    by_name = {}
    for r in rows:
        pid = get_pid(r)
        name = get_name(r)
        if pid:
            by_pid[str(pid)] = r
        if name:
            by_name[str(name).lower()] = r
    return by_pid, by_name

def find_low(row, maps):
    by_pid, by_name = maps
    pid = get_pid(row)
    name = get_name(row)
    if pid and str(pid) in by_pid:
        return by_pid[str(pid)]
    if name and str(name).lower() in by_name:
        return by_name[str(name).lower()]
    return {}

OFF_FIELDS = {
    "Points", "FG2M", "FG2A", "FG3M", "FG3A", "FTA", "FtPoints",
    "Assists", "TwoPtAssists", "ThreePtAssists", "AtRimAssists", "AssistPoints",
    "Turnovers", "LiveBallTurnovers", "DeadBallTurnovers",
    "BadPassTurnovers", "BadPassOutOfBoundsTurnovers",
    "LostBallTurnovers", "LostBallOutOfBoundsTurnovers", "StepOutOfBoundsTurnovers",
    "OffRebounds", "FTOffRebounds", "OffTwoPtRebounds", "OffThreePtRebounds",
    "SelfOReb", "Technical Free Throw Trips",
    "AtRimFGM", "AtRimFGA",
    "ShortMidRangeFGM", "ShortMidRangeFGA",
    "LongMidRangeFGM", "LongMidRangeFGA",
    "Corner3FGM", "Corner3FGA",
    "Arc3FGM", "Arc3FGA",
    "NonHeaveArc3FGM", "NonHeaveArc3FGA",
    "HeaveAttempts",
    "PtsUnassisted2s", "PtsUnassisted3s", "PtsAssisted2s", "PtsAssisted3s", "PtsPutbacks",
}

DEF_FIELDS = {
    "DefRebounds", "FTDefRebounds", "DefTwoPtRebounds", "DefThreePtRebounds",
    "Steals", "BadPassSteals", "LostBallSteals",
    "Blocks", "BlockedAtRim", "BlockedShortMidRange", "BlockedLongMidRange", "BlockedArc3",
    "OpponentPoints",
}

SKIP_DIRECT = {
    "EfgPct", "TsPct", "Fg2Pct", "Fg3Pct", "NonHeaveFg3Pct",
    "AtRimFrequency", "AtRimAccuracy",
    "ShortMidRangeFrequency", "ShortMidRangeAccuracy",
    "LongMidRangeFrequency", "LongMidRangeAccuracy",
    "Corner3Frequency", "Corner3Accuracy",
    "Arc3Frequency", "Arc3Accuracy",
    "Usage", "ShotQualityAvg", "LiveBallTurnoverPct",
    "SecondsPlayed", "Minutes", "OffPoss", "DefPoss", "TotalPoss", "PlusMinus",
}

COUNT_FIELDS = {
    "Points", "FG2M", "FG2A", "FG3M", "FG3A", "FTA", "FtPoints",
    "Assists", "Turnovers", "LiveBallTurnovers", "DeadBallTurnovers",
    "BadPassTurnovers", "BadPassOutOfBoundsTurnovers", "LostBallTurnovers",
    "OffRebounds", "DefRebounds", "Rebounds", "Steals", "Blocks",
    "AtRimFGM", "AtRimFGA", "ShortMidRangeFGM", "ShortMidRangeFGA",
    "LongMidRangeFGM", "LongMidRangeFGA", "Corner3FGM", "Corner3FGA",
    "Arc3FGM", "Arc3FGA", "NonHeaveArc3FGM", "NonHeaveArc3FGA",
    "SelfOReb", "Technical Free Throw Trips", "OpponentPoints",
}

def sub(all_row, low_row, key):
    return round((num(all_row.get(key)) or 0) - (num(low_row.get(key)) or 0), 6)

def weighted_minus_avg(all_row, low_row, value_key, weight_key):
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

def clamp_counts(out):
    flags = []
    for k in COUNT_FIELDS:
        if k in out and num(out.get(k)) is not None and num(out.get(k)) < 0:
            flags.append({"field": k, "value": out.get(k)})
            out[k] = 0
    out["negativeBeforeClamp"] = flags
    return out

def recalc(out, all_row, low_off):
    fg2m = num(out.get("FG2M")) or 0
    fg2a = num(out.get("FG2A")) or 0
    fg3m = num(out.get("FG3M")) or 0
    fg3a = num(out.get("FG3A")) or 0
    fta = num(out.get("FTA")) or 0
    pts = num(out.get("Points")) or 0
    fga = fg2a + fg3a

    out["FGA_Recalc"] = round(fga, 6)
    out["FGM_Recalc"] = round(fg2m + fg3m, 6)

    out["EfgPct_Recalc"] = None if fga <= 0 else round((fg2m + fg3m + 0.5 * fg3m) / fga, 6)
    out["TS_Recalc"] = None if (fga + 0.44 * fta) <= 0 else round(pts / (2 * (fga + 0.44 * fta)), 6)

    out["EfgPct"] = out["EfgPct_Recalc"]
    out["TsPct"] = out["TS_Recalc"]
    out["Fg2Pct"] = None if fg2a <= 0 else round(fg2m / fg2a, 6)
    out["Fg3Pct"] = None if fg3a <= 0 else round(fg3m / fg3a, 6)

    for prefix in ["AtRim", "ShortMidRange", "LongMidRange", "Corner3", "Arc3"]:
        makes = num(out.get(f"{prefix}FGM")) or 0
        atts = num(out.get(f"{prefix}FGA")) or 0
        out[f"{prefix}Accuracy"] = None if atts <= 0 else round(makes / atts, 6)
        out[f"{prefix}Frequency"] = None if fga <= 0 else round(atts / fga, 6)

    non_heave_a = num(out.get("NonHeaveArc3FGA")) or 0
    non_heave_m = num(out.get("NonHeaveArc3FGM")) or 0
    out["NonHeaveFg3Pct"] = None if non_heave_a <= 0 else round(non_heave_m / non_heave_a, 6)

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
    def_poss = num(out.get("DefPoss")) or 0

    out["PTS_PER_75"] = None if off_poss <= 0 else round(75 * pts / off_poss, 2)
    out["AST_PER_75"] = None if off_poss <= 0 else round(75 * (num(out.get("Assists")) or 0) / off_poss, 2)
    out["REB_PER_75"] = None if off_poss <= 0 else round(75 * (num(out.get("Rebounds")) or 0) / off_poss, 2)
    out["TOV_PER_75"] = None if off_poss <= 0 else round(75 * tov / off_poss, 2)

    out["TOVRate"] = None if off_poss <= 0 else round(100 * tov / off_poss, 2)
    out["FTr"] = None if fga <= 0 else round(fta / fga, 4)

    out["LiveBallTurnoverPct"] = None if tov <= 0 else round((num(out.get("LiveBallTurnovers")) or 0) / tov, 6)

    usage = weighted_minus_avg(all_row, low_off, "Usage", "OffPoss")
    out["Usage"] = None if usage is None else round(usage, 6)

    shot_q = weighted_minus_avg(all_row, low_off, "ShotQualityAvg", "FG2A")
    if shot_q is None:
        shot_q = weighted_minus_avg(all_row, low_off, "ShotQualityAvg", "OffPoss")
    out["ShotQualityAvg"] = None if shot_q is None else round(shot_q, 6)

def build_row(all_row, low_off, low_def, meta):
    out = dict(meta)

    pid = get_pid(all_row)
    name = get_name(all_row)
    team = all_row.get("TeamAbbreviation") or ID_TO_TEAM.get(str(all_row.get("TeamId") or ""))

    out["playerId"] = pid
    out["playerName"] = name
    out["team"] = team
    out["teamId"] = str(all_row.get("TeamId") or TEAM_IDS.get(team or "", ""))
    out["filter"] = "Medium+"
    out["source"] = "PBPStats: player All minus Low Offense and Low Defense"

    for k, v in all_row.items():
        if k in SKIP_DIRECT:
            continue

        if num(v) is None:
            continue

        if k in OFF_FIELDS:
            out[k] = sub(all_row, low_off, k)
        elif k in DEF_FIELDS:
            out[k] = sub(all_row, low_def, k)
        else:
            if k in low_off:
                out[k] = sub(all_row, low_off, k)
            elif k in low_def:
                out[k] = sub(all_row, low_def, k)
            else:
                out[k] = v

    all_off = num(all_row.get("OffPoss")) or 0
    all_def = num(all_row.get("DefPoss")) or 0

    low_off_poss = num(low_off.get("OffPoss"))
    if low_off_poss is None:
        low_off_poss = num(low_off.get("TotalPoss")) or 0

    low_def_poss = num(low_def.get("DefPoss"))
    if low_def_poss is None:
        low_def_poss = num(low_def.get("TotalPoss")) or 0

    out["OffPoss"] = round(max(0, all_off - low_off_poss), 6)
    out["DefPoss"] = round(max(0, all_def - low_def_poss), 6)
    out["TotalPoss"] = round(out["OffPoss"] + out["DefPoss"], 6)

    all_sec = minsec_to_seconds(all_row.get("Minutes"))
    if all_sec is None:
        all_sec = num(all_row.get("SecondsPlayed"))

    low_off_sec = num(low_off.get("SecondsPlayed")) or 0
    low_def_sec = num(low_def.get("SecondsPlayed")) or 0
    low_sec = max(low_off_sec, low_def_sec)

    out["SecondsPlayed"] = None if all_sec is None else round(max(0, all_sec - low_sec), 3)
    out["Minutes"] = seconds_to_minsec(out["SecondsPlayed"])

    out["lowOffPossRemoved"] = round(low_off_poss, 6)
    out["lowDefPossRemoved"] = round(low_def_poss, 6)
    out["lowOffSecondsRemoved"] = round(low_off_sec, 3)
    out["lowDefSecondsRemoved"] = round(low_def_sec, 3)
    out["lowOffRowFound"] = bool(low_off)
    out["lowDefRowFound"] = bool(low_def)

    for k in COUNT_FIELDS:
        if k not in out or out[k] is None:
            out[k] = 0

    out["Rebounds"] = round((num(out.get("OffRebounds")) or 0) + (num(out.get("DefRebounds")) or 0), 6)

    clamp_counts(out)
    recalc(out, all_row, low_off)

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
    local = GAMES_DIR / f"{season.replace('-', '_')}.json"
    if local.exists():
        return extract_games(json.loads(local.read_text()))

    data = api_get("/get-games/nba", {"Season": season, "SeasonType": "Playoffs"}, "games")
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

def team_abbr_from_id(v):
    if v in [None, ""]:
        return None
    return ID_TO_TEAM.get(str(v))

def teams_from_game(g):
    home = None
    away = None

    for k in ["HomeTeamAbbreviation", "homeTeamAbbreviation", "HomeTeam", "home_team"]:
        if g.get(k):
            home = str(g.get(k)).upper()[:3]

    for k in ["AwayTeamAbbreviation", "awayTeamAbbreviation", "AwayTeam", "away_team", "VisitorTeamAbbreviation"]:
        if g.get(k):
            away = str(g.get(k)).upper()[:3]

    if not home:
        for k in ["HomeTeamId", "homeTeamId", "HOME_TEAM_ID"]:
            home = team_abbr_from_id(g.get(k)) or home

    if not away:
        for k in ["AwayTeamId", "awayTeamId", "VisitorTeamId", "AWAY_TEAM_ID"]:
            away = team_abbr_from_id(g.get(k)) or away

    matchup = str(g.get("Matchup") or g.get("matchup") or "")
    if "@" in matchup and (not home or not away):
        a, h = [x.strip().upper() for x in matchup.split("@", 1)]
        away = away or a[:3]
        home = home or h[:3]

    return home, away

def team_of_row(r):
    t = r.get("TeamAbbreviation")
    if t:
        return str(t).upper()
    tid = str(r.get("TeamId") or "")
    return ID_TO_TEAM.get(tid)

def merge_off_def_all_rows(off_row, def_row, team, team_id):
    """
    Build a single all-leverage player row from team-specific possession pulls:
    All Offense row + All Defense row.
    """
    off_row = dict(off_row or {})
    def_row = dict(def_row or {})
    out = {}

    # Identity
    for r in [off_row, def_row]:
        for k, v in r.items():
            if v not in [None, "", [], {}] and k not in out:
                out[k] = v

    out["TeamAbbreviation"] = team
    out["TeamId"] = team_id

    # Offensive fields come from all-offense.
    for k in OFF_FIELDS:
        if k in off_row:
            out[k] = off_row.get(k)

    # Defensive fields come from all-defense.
    for k in DEF_FIELDS:
        if k in def_row:
            out[k] = def_row.get(k)

    # Possessions
    off_poss = num(off_row.get("OffPoss"))
    if off_poss is None:
        off_poss = num(off_row.get("TotalPoss")) or 0

    def_poss = num(def_row.get("DefPoss"))
    if def_poss is None:
        def_poss = num(def_row.get("TotalPoss")) or 0

    out["OffPoss"] = off_poss
    out["DefPoss"] = def_poss
    out["TotalPoss"] = off_poss + def_poss

    # Seconds/minutes
    off_sec = num(off_row.get("SecondsPlayed")) or 0
    def_sec = num(def_row.get("SecondsPlayed")) or 0
    sec = max(off_sec, def_sec)

    out["SecondsPlayed"] = sec
    out["Minutes"] = seconds_to_minsec(sec)

    # Percent/quality fields from offense where available.
    for k in [
        "EfgPct", "TsPct", "Fg2Pct", "Fg3Pct", "NonHeaveFg3Pct",
        "AtRimFrequency", "AtRimAccuracy",
        "ShortMidRangeFrequency", "ShortMidRangeAccuracy",
        "LongMidRangeFrequency", "LongMidRangeAccuracy",
        "Corner3Frequency", "Corner3Accuracy",
        "Arc3Frequency", "Arc3Accuracy",
        "Usage", "ShotQualityAvg", "LiveBallTurnoverPct",
    ]:
        if k in off_row:
            out[k] = off_row.get(k)

    return out


def process_game(season, idx, total, g):
    gid = game_id(g)
    date = game_date(g)
    home, away = teams_from_game(g)

    if not gid or not date or not home or not away:
        print("SKIP bad game row:", g, flush=True)
        return []

    home_id = TEAM_IDS.get(home)
    away_id = TEAM_IDS.get(away)

    if not home_id or not away_id:
        print("SKIP missing team ID:", gid, away, "@", home, flush=True)
        return []

    print(f"\n{season} {idx}/{total} {gid} {away} @ {home}", flush=True)

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

    for team, tid, opp, oppid in [
        (home, home_id, away, away_id),
        (away, away_id, home, home_id),
    ]:
        # ALL offense, no leverage filter.
        all_off_data = api_get("/get-possessions/nba", {
            "Season": season,
            "SeasonType": "Playoffs",
            "TeamId": tid,
            "OffDef": "Offense",
            "FromDate": date,
            "ToDate": date,
            "Opponent": oppid,
        }, "poss_all_offense")

        # ALL defense, no leverage filter.
        all_def_data = api_get("/get-possessions/nba", {
            "Season": season,
            "SeasonType": "Playoffs",
            "TeamId": tid,
            "OffDef": "Defense",
            "FromDate": date,
            "ToDate": date,
            "Opponent": oppid,
        }, "poss_all_defense")

        # LOW offense.
        low_off_data = api_get("/get-possessions/nba", {
            "Season": season,
            "SeasonType": "Playoffs",
            "TeamId": tid,
            "OffDef": "Offense",
            "FromDate": date,
            "ToDate": date,
            "Opponent": oppid,
            "Leverage": "Low",
        }, "poss_low")

        # LOW defense.
        low_def_data = api_get("/get-possessions/nba", {
            "Season": season,
            "SeasonType": "Playoffs",
            "TeamId": tid,
            "OffDef": "Defense",
            "FromDate": date,
            "ToDate": date,
            "Opponent": oppid,
            "Leverage": "Low",
        }, "poss_low_defense")

        all_off_rows = extract_possession_player_rows(all_off_data)
        all_def_rows = extract_possession_player_rows(all_def_data)
        low_off_rows = extract_possession_player_rows(low_off_data)
        low_def_rows = extract_possession_player_rows(low_def_data)

        all_off_maps = map_rows(all_off_rows)
        all_def_maps = map_rows(all_def_rows)
        low_off_maps = map_rows(low_off_rows)
        low_def_maps = map_rows(low_def_rows)

        candidates = merge_duplicate_player_rows(all_off_rows + all_def_rows)

        print(
            f"{team} all_off={len(all_off_rows)} all_def={len(all_def_rows)} "
            f"low_off={len(low_off_rows)} low_def={len(low_def_rows)} candidates={len(candidates)}",
            flush=True
        )

        for cand in candidates:
            off_row = find_low(cand, all_off_maps)
            def_row = find_low(cand, all_def_maps)

            if not off_row and not def_row:
                continue

            all_row = merge_off_def_all_rows(off_row, def_row, team, tid)

            low_off = find_low(cand, low_off_maps)
            low_def = find_low(cand, low_def_maps)

            meta = dict(meta_base)
            meta["opponent"] = opp

            rows.append(build_row(all_row, low_off, low_def, meta))

    print("player rows:", len(rows), flush=True)
    return rows


def audit_year(year):
    p = PLAYER_OUT / f"{year}.json"

    if not p.exists():
        return {"year": year, "error": "missing output file"}

    rows = json.loads(p.read_text())

    by_game = defaultdict(list)
    for r in rows:
        by_game[r.get("gameId")].append(r)

    dup_games = []
    neg_flags = []

    for gid, rs in by_game.items():
        ids = [(r.get("playerId"), r.get("playerName")) for r in rs]
        c = Counter(ids)
        dups = [(k, v) for k, v in c.items() if v > 1 and k != (None, None)]
        if dups:
            dup_games.append({"gameId": gid, "rows": len(rs), "dups": dups[:10]})

        for r in rs:
            if r.get("negativeBeforeClamp"):
                neg_flags.append({
                    "gameId": gid,
                    "playerId": r.get("playerId"),
                    "playerName": r.get("playerName"),
                    "flags": r.get("negativeBeforeClamp")[:5],
                })

    row_counts = [len(v) for v in by_game.values()]
    uniq_counts = [len(set((r.get("playerId"), r.get("playerName")) for r in v)) for v in by_game.values()]

    return {
        "year": year,
        "rows": len(rows),
        "games": len(by_game),
        "avg_rows_per_game": round(sum(row_counts) / len(row_counts), 1) if row_counts else 0,
        "min_rows_per_game": min(row_counts) if row_counts else 0,
        "max_rows_per_game": max(row_counts) if row_counts else 0,
        "avg_unique_players_per_game": round(sum(uniq_counts) / len(uniq_counts), 1) if uniq_counts else 0,
        "duplicate_games": len(dup_games),
        "duplicate_examples": dup_games[:5],
        "negative_before_clamp_rows": len(neg_flags),
        "negative_examples": neg_flags[:10],
    }

def build_season(season, fresh=False):
    year = playoff_year(season)
    out_file = PLAYER_OUT / f"{year}.json"

    if fresh and out_file.exists():
        out_file.unlink()

    done_games = set()
    all_output_rows = []

    if out_file.exists():
        try:
            all_output_rows = json.loads(out_file.read_text())
            done_games = {str(r.get("gameId")) for r in all_output_rows if r.get("gameId")}
            print(f"RESUME {season}: loaded {len(all_output_rows)} rows, {len(done_games)} games done", flush=True)
        except Exception:
            all_output_rows = []
            done_games = set()

    games = get_games(season)

    for i, g in enumerate(games, 1):
        gid = game_id(g)

        if gid and gid in done_games:
            print(f"{season} {i}/{len(games)} {gid} already done, skipping", flush=True)
            continue

        rows = process_game(season, i, len(games), g)

        all_output_rows.extend(rows)

        if gid:
            done_games.add(gid)

        out_file.write_text(json.dumps(all_output_rows, indent=2), encoding="utf-8")

    report = audit_year(year)
    return {
        "season": season,
        "year": year,
        "games_expected": len(games),
        "output_file": str(out_file),
        "audit": report,
    }

def parse_args(args):
    fresh = "--fresh" in args
    args = [a for a in args if a != "--fresh"]

    seasons = []
    years = []

    if not args:
        years = list(range(2013, 2027))
    else:
        for a in args:
            a = str(a).strip()

            # Exact NBA season format, like 2017-18
            if re.match(r"^\d{4}-\d{2}$", a):
                seasons.append(a)

            # Year range format, like 2013-2026
            elif re.match(r"^\d{4}-\d{4}$", a):
                s, e = a.split("-", 1)
                years.extend(range(int(s), int(e) + 1))

            # Single playoff year, like 2018
            elif re.match(r"^\d{4}$", a):
                years.append(int(a))

            else:
                raise SystemExit(f"Bad season/year argument: {a}")

    seasons.extend([season_from_year(y) for y in sorted(set(years))])
    seasons = list(dict.fromkeys(seasons))

    return seasons, fresh

def main():
    seasons, fresh = parse_args(sys.argv[1:])

    manifest = {
        "source": "PBPStats API",
        "filter": "Medium+ / Low Leverage Removed",
        "method": "Player all-leverage game stats minus Low Offense and Low Defense possession player rows",
        "seasons": {},
    }

    for season in seasons:
        info = build_season(season, fresh=fresh)
        manifest["seasons"][str(info["year"])] = info
        (OUT_ROOT / "pbpstats_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    audits = {str(playoff_year(s)): audit_year(playoff_year(s)) for s in seasons}
    (AUDIT_DIR / "player_medium_plus_integrity.json").write_text(json.dumps(audits, indent=2), encoding="utf-8")

    print("\nDONE")
    print(json.dumps(manifest, indent=2))
    print("\nAUDIT")
    print(json.dumps(audits, indent=2))

if __name__ == "__main__":
    main()
