import json, time, math, re, sys
from pathlib import Path
import requests

BASE = "https://api.pbpstats.com"
OUT = Path("public/data/pbpstats")
CACHE = OUT / "_cache"
GAMES_OUT = OUT / "games"
PLAYER_OUT = OUT / "player_game_low_removed"
TEAM_OUT = OUT / "team_game_low_removed"

for p in [CACHE, GAMES_OUT, PLAYER_OUT, TEAM_OUT]:
    p.mkdir(parents=True, exist_ok=True)

DEFAULT_SEASONS = [f"{y}-{str(y+1)[-2:]}" for y in range(2012, 2026)]
SEASONS = sys.argv[1:] or DEFAULT_SEASONS

session = requests.Session()
session.headers.update({
    "User-Agent": "playoff-translation-lab/1.0",
    "Accept": "application/json,text/plain,*/*",
})

def season_to_year(season):
    return int(season.split("-")[0]) + 1

def safe(x):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(x))

def cache_file(kind, params):
    name = kind + "__" + "__".join(f"{k}-{safe(v)}" for k, v in sorted(params.items()))
    return CACHE / f"{name}.json"

def get_json(path, params, kind, retries=8):
    c = cache_file(kind, params)
    if c.exists():
        try:
            return json.loads(c.read_text())
        except Exception:
            pass

    wait = 1
    for attempt in range(1, retries + 1):
        r = session.get(BASE + path, params=params, timeout=60)
        print(f"{r.status_code} {path} {params}")

        if r.status_code == 200:
            try:
                data = r.json()
            except Exception:
                data = {"_raw": r.text}
            c.write_text(json.dumps(data, indent=2), encoding="utf-8")
            time.sleep(0.25)
            return data

        if r.status_code in {429, 500, 502, 503, 504}:
            time.sleep(wait)
            wait = min(wait * 1.8, 20)
            continue

        data = {"_status": r.status_code, "_text": r.text[:2000], "_params": params}
        c.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return data

    data = {"_status": "failed_after_retries", "_params": params}
    c.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data

def num(v):
    try:
        if v is None or v == "":
            return None
        x = float(v)
        if math.isnan(x):
            return None
        return x
    except Exception:
        return None

def get_name(row):
    for k in ["Name", "PlayerName", "EntityName", "PLAYER_NAME", "player_name"]:
        if row.get(k):
            return str(row.get(k))
    return ""

def get_pid(row):
    for k in ["PlayerId", "EntityId", "Id", "PersonId", "PLAYER_ID", "player_id"]:
        if row.get(k) not in [None, ""]:
            return str(row.get(k))
    return ""

def looks_like_player_row(row):
    if not isinstance(row, dict):
        return False
    keys = set(row.keys())
    stat_keys = {"Points", "OffPoss", "TotalPoss", "FG2A", "FG3A", "TsPct", "Usage", "PlusMinus", "SecondsPlayed"}
    return bool(keys & stat_keys)

def extract_player_rows(obj):
    rows = []

    def walk(x, parent_key=None):
        if isinstance(x, list):
            for item in x:
                walk(item, parent_key)
            return

        if isinstance(x, dict):
            if looks_like_player_row(x):
                row = dict(x)
                if parent_key and not get_pid(row) and str(parent_key).isdigit():
                    row["PlayerId"] = str(parent_key)
                rows.append(row)
                return

            for k, v in x.items():
                if isinstance(v, dict) and looks_like_player_row(v):
                    row = dict(v)
                    if not get_pid(row) and str(k).isdigit():
                        row["PlayerId"] = str(k)
                    rows.append(row)
                else:
                    walk(v, k)

    walk(obj)

    dedup = {}
    for r in rows:
        pid = get_pid(r)
        name = get_name(r)
        key = (pid, name, r.get("Points"), r.get("OffPoss"), r.get("TotalPoss"))
        dedup[key] = r
    return list(dedup.values())

def extract_team_result(obj):
    if isinstance(obj, dict) and isinstance(obj.get("team_results"), dict):
        return dict(obj["team_results"])
    return {}

def subtract_rows(all_row, low_row):
    out = {}

    keys = set(all_row.keys()) | set(low_row.keys())

    for k in keys:
        av = num(all_row.get(k))
        lv = num(low_row.get(k))

        if av is not None or lv is not None:
            out[k] = round((av or 0) - (lv or 0), 6)
        else:
            if k in all_row:
                out[k] = all_row.get(k)

    pts = num(out.get("Points")) or 0
    fg2a = num(out.get("FG2A")) or 0
    fg3a = num(out.get("FG3A")) or 0
    fg2m = num(out.get("FG2M")) or 0
    fg3m = num(out.get("FG3M")) or 0
    fta = num(out.get("FTA")) or 0
    tov = num(out.get("Turnovers")) or 0

    fga = fg2a + fg3a

    bad_pass = num(out.get("BadPassTurnovers")) or 0
    bad_pass_oob = num(out.get("BadPassOutOfBoundsTurnovers")) or 0
    scoring_tov = max(0, tov - bad_pass - bad_pass_oob)

    arc3a = num(out.get("Arc3FGA"))
    non_heave_arc3a = num(out.get("NonHeaveArc3FGA"))
    heaves = 0
    if arc3a is not None and non_heave_arc3a is not None:
        heaves = max(0, arc3a - non_heave_arc3a)

    tech_fta = num(out.get("Technical Free Throw Trips")) or 0

    # PBPStats calls z-bounds / z-boards SelfOReb.
    # Use count SelfOReb, not SelfORebPct.
    z_bounds = num(out.get("SelfOReb"))
    z_bounds_available = z_bounds is not None
    if z_bounds is None:
        z_bounds = 0
    z_bounds = max(0, z_bounds)

    adj_fga = max(0, fga + scoring_tov - heaves - z_bounds)
    adj_fta = max(0, fta - tech_fta)

    ts_den = 2 * (fga + 0.44 * fta)
    adj_ts_den = 2 * (adj_fga + 0.44 * adj_fta)

    if fga > 0:
        out["FGA_Recalc"] = round(fga, 6)
        out["EfgPct_Recalc"] = round((fg2m + fg3m + 0.5 * fg3m) / fga, 4)

    out["Points"] = round(pts, 6)
    out["FGA_Recalc"] = round(fga, 6)

    out["BadPassTOV_Total"] = round(bad_pass + bad_pass_oob, 6)
    out["ScoringTOV"] = round(scoring_tov, 6)
    out["Heaves_Est"] = round(heaves, 6)
    out["TechFTA_Est"] = round(tech_fta, 6)

    out["SelfOReb"] = round(z_bounds, 6)
    out["ZBounds"] = round(z_bounds, 6)
    out["ZBoards"] = round(z_bounds, 6)
    out["ZBounds_available"] = z_bounds_available
    out["ZBounds_source_key"] = "SelfOReb" if z_bounds_available else None

    out["AdjFGA"] = round(adj_fga, 6)
    out["AdjFTA"] = round(adj_fta, 6)
    out["TS_Recalc"] = None if ts_den <= 0 else round(pts / ts_den, 4)
    out["AdjTS"] = None if adj_ts_den <= 0 else round(pts / adj_ts_den, 4)
    out["AdjTS%"] = None if adj_ts_den <= 0 else round(100 * pts / adj_ts_den, 2)

    out["AdjTS_source"] = "PBPStats-derived: AdjFGA = FGA + scoring TOV - heaves - SelfOReb; AdjFTA = FTA - technical FT trips"
    out["LowRemoved"] = True

    return out


def fetch_games(season):
    data = get_json("/get-games/nba", {"Season": season, "SeasonType": "Playoffs"}, "games")
    games = data.get("results", []) if isinstance(data, dict) else []
    (GAMES_OUT / f"{season.replace('-', '_')}.json").write_text(json.dumps(games, indent=2), encoding="utf-8")
    return games

def fetch_game_stats(game_id):
    return get_json("/get-game-stats", {"GameId": game_id, "Type": "Player"}, "game_stats_player")

def fetch_low(season, game, home=True):
    if home:
        team_id = str(game["HomeTeamId"])
        opp_id = str(game["AwayTeamId"])
    else:
        team_id = str(game["AwayTeamId"])
        opp_id = str(game["HomeTeamId"])

    return get_json(
        "/get-possessions/nba",
        {
            "Season": season,
            "SeasonType": "Playoffs",
            "TeamId": team_id,
            "OffDef": "Offense",
            "FromDate": game["Date"],
            "ToDate": game["Date"],
            "Opponent": opp_id,
            "Leverage": "Low",
        },
        "poss_low"
    )

manifest_path = OUT / "pbpstats_manifest.json"
manifest = {"description": "PBPStats low leverage removed build", "seasons": [], "errors": []}

for season in SEASONS:
    year = season_to_year(season)
    print("\n" + "=" * 100)
    print("BUILDING", season, "=>", year)
    print("=" * 100)

    games = fetch_games(season)
    print("games:", len(games))

    player_rows = []
    team_rows = []

    for i, game in enumerate(games, 1):
        gid = game.get("GameId")
        print(f"\n{season} {i}/{len(games)} {gid} {game.get('AwayTeamAbbreviation')} @ {game.get('HomeTeamAbbreviation')}")

        try:
            all_stats = fetch_game_stats(gid)
            all_players = extract_player_rows(all_stats)

            low_home = fetch_low(season, game, True)
            low_away = fetch_low(season, game, False)
            low_players = extract_player_rows(low_home) + extract_player_rows(low_away)

            low_by_id = {}
            for r in low_players:
                pid = get_pid(r)
                if pid:
                    low_by_id[pid] = r

            made = 0
            for r in all_players:
                pid = get_pid(r)
                if not pid:
                    continue

                low = low_by_id.get(pid, {})
                out = subtract_rows(r, low)

                out.update({
                    "year": year,
                    "season": season,
                    "gameId": gid,
                    "nbaGameId": gid,
                    "date": game.get("Date"),
                    "playerId": pid,
                    "playerName": get_name(r),
                    "leverageFilter": "lowRemoved",
                    "leverageLabel": "Low Leverage Removed",
                    "source": "PBPStats get-game-stats minus get-possessions Leverage=Low",
                })
                player_rows.append(out)
                made += 1

            for side, obj in [("home", low_home), ("away", low_away)]:
                tr = extract_team_result(obj)
                tr.update({
                    "year": year,
                    "season": season,
                    "gameId": gid,
                    "nbaGameId": gid,
                    "date": game.get("Date"),
                    "team": game.get("HomeTeamAbbreviation") if side == "home" else game.get("AwayTeamAbbreviation"),
                    "opponent": game.get("AwayTeamAbbreviation") if side == "home" else game.get("HomeTeamAbbreviation"),
                    "teamId": str(game.get("HomeTeamId") if side == "home" else game.get("AwayTeamId")),
                    "opponentId": str(game.get("AwayTeamId") if side == "home" else game.get("HomeTeamId")),
                    "leverageFilter": "low",
                    "leverageLabel": "Low",
                    "source": "PBPStats get-possessions Leverage=Low team_results"
                })
                team_rows.append(tr)

            print("player rows:", made, "team rows:", 2)

            if made == 0:
                manifest["errors"].append({"season": season, "gameId": gid, "error": "zero player rows parsed"})

        except Exception as e:
            print("GAME ERROR", season, gid, repr(e))
            manifest["errors"].append({"season": season, "gameId": gid, "error": repr(e)})

    (PLAYER_OUT / f"{year}.json").write_text(json.dumps(player_rows, indent=2), encoding="utf-8")
    (TEAM_OUT / f"{year}.json").write_text(json.dumps(team_rows, indent=2), encoding="utf-8")

    manifest["seasons"].append({
        "season": season,
        "year": year,
        "games": len(games),
        "player_rows": len(player_rows),
        "team_rows": len(team_rows),
    })

    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

print("\nDONE")
print(json.dumps(manifest, indent=2)[:5000])
