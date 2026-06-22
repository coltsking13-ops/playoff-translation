import json, time, hashlib, sys, re
from pathlib import Path
import requests

BASE = "https://api.pbpstats.com"

OUT_DIR = Path("public/data/pbpstats/player_game_all_leverage_adjts")
CACHE = Path("public/data/pbpstats/_cache")
OUT_DIR.mkdir(parents=True, exist_ok=True)
CACHE.mkdir(parents=True, exist_ok=True)

TEAM_IDS = {
    "ATL":"1610612737","BOS":"1610612738","CLE":"1610612739","NOP":"1610612740","NOH":"1610612740",
    "CHI":"1610612741","DAL":"1610612742","DEN":"1610612743","GSW":"1610612744","HOU":"1610612745",
    "LAC":"1610612746","LAL":"1610612747","MIA":"1610612748","MIL":"1610612749","MIN":"1610612750",
    "BKN":"1610612751","NJN":"1610612751","NYK":"1610612752","ORL":"1610612753","IND":"1610612754",
    "PHI":"1610612755","PHX":"1610612756","POR":"1610612757","SAC":"1610612758","SAS":"1610612759",
    "OKC":"1610612760","SEA":"1610612760","TOR":"1610612761","UTA":"1610612762","MEM":"1610612763",
    "WAS":"1610612764","DET":"1610612765","CHA":"1610612766"
}

session = requests.Session()
session.headers.update({"User-Agent":"playoff-translation-adjts-backfill/1.0"})

def season_from_year(y):
    return f"{int(y)-1}-{str(y)[-2:]}"

def cache_file(path, params):
    raw = json.dumps({"path": path, "params": params}, sort_keys=True)
    h = hashlib.sha1(raw.encode()).hexdigest()[:20]
    return CACHE / f"all_leverage_adjts__{h}.json"

def api_get(path, params, retries=10):
    c = cache_file(path, params)
    if c.exists():
        return json.loads(c.read_text())

    wait = 1
    last = ""

    for attempt in range(1, retries + 1):
        r = session.get(BASE + path, params=params, timeout=60)
        print("API", r.status_code, params, flush=True)

        if r.status_code == 200:
            data = r.json()
            c.write_text(json.dumps(data), encoding="utf-8")
            return data

        last = r.text[:500]

        if r.status_code in {429, 500, 502, 503, 504}:
            time.sleep(wait)
            wait = min(wait * 2, 20)
            continue

        break

    print("FAILED", params, last, flush=True)
    return {}

def num(v):
    if v in [None, "", [], {}]:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace("%", "")
    if re.match(r"^\d+:\d\d$", s):
        m, sec = s.split(":")
        return float(m) + float(sec) / 60
    try:
        return float(s)
    except:
        return None

def val(row, *names):
    for n in names:
        if n in row and row[n] not in [None, "", [], {}]:
            return row[n]
    return None

def get_pid(row):
    return str(val(row, "PlayerId", "EntityId", "playerId", "nbaId", "NbaId") or "")

def get_name(row):
    return val(row, "Name", "ShortName", "playerName", "PlayerName") or ""


def extract_player_rows(obj):
    """
    PBPStats responses can change shape. This recursively finds player rows
    anywhere in the response instead of assuming one fixed key.
    """
    candidates = []

    def looks_like_player_row(d):
        if not isinstance(d, dict):
            return False
        keys = set(d.keys())
        has_player = any(k in keys for k in [
            "PlayerId", "EntityId", "playerId", "nbaId", "NbaId", "Name", "ShortName", "playerName", "PlayerName"
        ])
        has_stats = any(k in keys for k in [
            "Points", "PTS", "FG2A", "FG3A", "FGA", "FTA", "Turnovers", "TOV", "OffPoss", "TotalPoss"
        ])
        return has_player and has_stats

    def walk(x, parent_key=None):
        if isinstance(x, dict):
            if looks_like_player_row(x):
                rr = dict(x)
                if parent_key and not get_pid(rr):
                    rr["PlayerId"] = str(parent_key)
                candidates.append(rr)

            for k, v in x.items():
                if isinstance(v, dict):
                    vv = dict(v)
                    if str(k).isdigit() and not get_pid(vv):
                        vv["PlayerId"] = str(k)
                    walk(vv, k)
                elif isinstance(v, list):
                    walk(v, k)

        elif isinstance(x, list):
            for v in x:
                walk(v, parent_key)

    walk(obj)

    best = {}
    for r in candidates:
        pid = get_pid(r)
        name = get_name(r)
        key = pid or name
        if not key:
            continue

        fp = (
            (num(val(r, "OffPoss", "TotalPoss")) or 0)
            + (num(val(r, "SecondsPlayed")) or 0) / 60
            + (num(val(r, "Points", "PTS")) or 0) / 1000
        )

        if key not in best or fp > best[key][0]:
            best[key] = (fp, r)

    return [x[1] for x in best.values()]

def calc_adjts(r):
    fg2a = num(val(r, "FG2A", "Fg2a")) or 0
    fg3a = num(val(r, "FG3A", "Fg3a")) or 0
    fga = fg2a + fg3a
    if fga == 0:
        fga = num(val(r, "FGA", "FieldGoalAttempts")) or 0

    fta = num(val(r, "FTA", "FreeThrowAttempts")) or 0
    pts = num(val(r, "Points", "PTS")) or 0
    tov = num(val(r, "Turnovers", "TOV")) or 0

    bad_pass = num(val(r, "BadPassTurnovers", "BadPassTOV")) or 0
    bad_pass_oob = num(val(r, "BadPassOutOfBoundsTurnovers", "BadPassOutOfBoundsTOV")) or 0
    scoring_tov = max(0, tov - bad_pass - bad_pass_oob)

    arc3 = num(val(r, "Arc3FGA")) or 0
    non_heave_arc3 = num(val(r, "NonHeaveArc3FGA")) or 0
    heaves = max(0, arc3 - non_heave_arc3)

    tech_fta = num(val(r, "Technical Free Throw Trips", "TechFTA")) or 0
    zbounds = num(val(r, "SelfOReb", "ZBounds", "ZBoards")) or 0

    adj_fga = fga + scoring_tov - heaves - zbounds
    adj_fta = max(0, fta - tech_fta)
    denom = 2 * (adj_fga + 0.44 * adj_fta)
    adjts = None if denom <= 0 else round(100 * pts / denom, 2)

    return {
        "AdjTS%": adjts,
        "AdjFGA": round(adj_fga, 6),
        "AdjFTA": round(adj_fta, 6),
        "ScoringTOV": round(scoring_tov, 6),
        "BadPassTOV": round(bad_pass, 6),
        "BadPassOutOfBoundsTOV": round(bad_pass_oob, 6),
        "Heaves": round(heaves, 6),
        "ZBounds": round(zbounds, 6),
        "ZBoards": round(zbounds, 6),
        "TechFTA": round(tech_fta, 6),
    }

def load_data_package():
    return json.loads(Path("data-package.json").read_text())

def build_team_games(data, year):
    team_games = {}
    player_lookup = {}

    for r in data.get("playerGames", []):
        if int(r.get("year", 0) or 0) != year:
            continue

        date = r.get("date")
        team = r.get("team")
        opp = r.get("opponent")
        if not date or not team or not opp:
            continue

        nba_game_id = str(r.get("nbaGameId") or r.get("gameId") or "")
        game_id = str(r.get("gameId") or r.get("nbaGameId") or "")

        if team not in TEAM_IDS or opp not in TEAM_IDS:
            continue

        key = (date, team, opp, game_id, nba_game_id)
        team_games[key] = {
            "year": year,
            "season": season_from_year(year),
            "date": date,
            "team": team,
            "opponent": opp,
            "gameId": game_id,
            "nbaGameId": nba_game_id,
            "teamId": TEAM_IDS[team],
            "opponentId": TEAM_IDS[opp],
        }

        nba_id = str(r.get("nbaId") or "").strip()
        if nba_id:
            player_lookup[(date, team, nba_id)] = r

    return list(team_games.values()), player_lookup

def process_year(year):
    data = load_data_package()
    team_games, player_lookup = build_team_games(data, year)

    out_file = OUT_DIR / f"{year}.json"
    rows = []
    if out_file.exists():
        try:
            rows = json.loads(out_file.read_text())
        except:
            rows = []

    done = {(r.get("date"), r.get("team")) for r in rows}

    print(f"YEAR {year}: team-games={len(team_games)} existing_rows={len(rows)}", flush=True)

    for i, tg in enumerate(team_games, 1):
        if (tg["date"], tg["team"]) in done:
            continue

        print(f"{year} {i}/{len(team_games)} {tg['date']} {tg['team']} vs {tg['opponent']}", flush=True)

        params = {
            "Season": tg["season"],
            "SeasonType": "Playoffs",
            "TeamId": tg["teamId"],
            "OffDef": "Offense",
            "FromDate": tg["date"],
            "ToDate": tg["date"],
            "Opponent": tg["opponentId"],
        }

        obj = api_get("/get-possessions/nba", params)
        player_rows = extract_player_rows(obj)
        print("player rows:", len(player_rows), flush=True)

        for pr in player_rows:
            pid = get_pid(pr)
            src = player_lookup.get((tg["date"], tg["team"], pid), {})

            out = {
                "year": year,
                "season": tg["season"],
                "filter": "All",
                "source": "PBPStats all-leverage game-level AdjTS backfill",
                "gameId": tg["gameId"],
                "nbaGameId": tg["nbaGameId"],
                "date": tg["date"],
                "team": tg["team"],
                "opponent": tg["opponent"],
                "teamId": tg["teamId"],
                "opponentId": tg["opponentId"],
                "playerId": src.get("playerId") or pid,
                "nbaId": pid,
                "playerName": src.get("playerName") or get_name(pr),
                "PTS": num(val(pr, "Points", "PTS")) or src.get("PTS"),
                "FGA": (num(val(pr, "FG2A")) or 0) + (num(val(pr, "FG3A")) or 0),
                "FTA": num(val(pr, "FTA")) or src.get("FTA"),
                "TOV": num(val(pr, "Turnovers", "TOV")) or src.get("TOV"),
                "OffPoss": num(val(pr, "OffPoss", "TotalPoss")),
                "SecondsPlayed": num(val(pr, "SecondsPlayed")),
                "OppRSAdjTSAllowed": src.get("OppRSAdjTSAllowed"),
                "AdjTS_source": "verified all-leverage game-level PBPStats possessions backfill",
            }

            if not out["FGA"]:
                out["FGA"] = src.get("FGA")

            out.update(calc_adjts(pr))

            if out.get("AdjTS%") is not None and out.get("OppRSAdjTSAllowed") not in [None, "", [], {}]:
                try:
                    out["rAdjTS"] = round(float(out["AdjTS%"]) - float(out["OppRSAdjTSAllowed"]), 2)
                except:
                    out["rAdjTS"] = None
            else:
                out["rAdjTS"] = None

            rows.append(out)

        done.add((tg["date"], tg["team"]))
        out_file.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    out_file.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print("WROTE", out_file, "rows", len(rows), flush=True)

def parse_years(args):
    if not args:
        return [2023, 2024, 2025, 2026]
    years = []
    for a in args:
        if "-" in a:
            s, e = a.split("-", 1)
            years.extend(range(int(s), int(e) + 1))
        else:
            years.append(int(a))
    return sorted(set(years))

if __name__ == "__main__":
    for y in parse_years(sys.argv[1:]):
        process_year(y)
