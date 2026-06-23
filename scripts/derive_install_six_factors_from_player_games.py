#!/usr/bin/env python3
import json
import time
from pathlib import Path
from collections import defaultdict

PACKAGE_FILES = [
    Path("data-package.json"),
    Path("data/data-package.json"),
    Path("public/data/data-package.embedded.json"),
    Path("public/data/data-package.json"),
]

YEAR_KEYS = ["year", "season", "SEASON"]
GAME_KEYS = ["gameId", "GAME_ID", "nbaGameId", "game_id"]
TEAM_KEYS = ["team", "TEAM", "teamAbbr", "TEAM_ABBREVIATION"]
OPP_KEYS = ["opponent", "opp", "OPP", "opponentTeam"]
SERIES_KEYS = ["seriesCode", "series", "seriesId"]

STAT_ALIASES = {
    "pts": ["PTS", "points", "Points"],
    "fgm": ["FGM", "fgm", "fieldGoalsMade", "fgMade"],
    "fga": ["FGA", "fga", "fieldGoalsAttempted", "fgAttempts"],
    "fg3m": ["3PM", "FG3M", "fg3m", "threePM", "threePointersMade"],
    "fg3a": ["3PA", "FG3A", "fg3a", "threePA", "threePointersAttempted"],
    "ftm": ["FTM", "ftm", "freeThrowsMade"],
    "fta": ["FTA", "fta", "freeThrowsAttempted"],
    "oreb": ["OREB", "ORB", "offReb", "offensiveRebounds"],
    "dreb": ["DREB", "DRB", "defReb", "defensiveRebounds"],
    "tov": ["TOV", "TO", "turnovers"],
}

PAIR_KEYS = {
    "fg": ["FG", "fg", "fieldGoals", "FGM-A"],
    "fg3": ["3P", "3PT", "FG3", "threePointers", "3PM-A"],
    "ft": ["FT", "ft", "freeThrows", "FTM-A"],
}

def norm_team(x):
    x = str(x or "").strip().upper()
    aliases = {
        "OKLAHOMA CITY THUNDER": "OKC",
        "SAN ANTONIO SPURS": "SAS",
        "NEW YORK KNICKS": "NYK",
        "MINNESOTA TIMBERWOLVES": "MIN",
        "PORTLAND TRAIL BLAZERS": "POR",
    }
    return aliases.get(x, x)

def get_any(row, keys):
    for k in keys:
        if k in row and row[k] not in [None, ""]:
            return row[k]
    return ""

def num(v):
    if v in [None, "", "—"]:
        return 0.0
    try:
        return float(str(v).replace("%", "").replace(",", "").strip())
    except Exception:
        return 0.0

def get_num(row, aliases):
    for k in aliases:
        if k in row and row[k] not in [None, ""]:
            return num(row[k])
    return 0.0

def parse_pair(v):
    if v in [None, ""]:
        return None
    s = str(v).strip().replace(" ", "")
    for sep in ["-", "/", "–"]:
        if sep in s:
            a, b = s.split(sep, 1)
            try:
                return float(a), float(b)
            except Exception:
                return None
    return None

def get_pair(row, pair_names):
    for k in pair_names:
        if k in row:
            p = parse_pair(row[k])
            if p:
                return p
    return None

def empty_totals():
    return {
        "pts": 0.0,
        "fgm": 0.0,
        "fga": 0.0,
        "fg3m": 0.0,
        "fg3a": 0.0,
        "ftm": 0.0,
        "fta": 0.0,
        "oreb": 0.0,
        "dreb": 0.0,
        "tov": 0.0,
    }

def add_totals(a, b, sign=1):
    for k in a:
        a[k] += sign * b.get(k, 0.0)

def row_totals(row):
    t = empty_totals()

    for stat, aliases in STAT_ALIASES.items():
        t[stat] = get_num(row, aliases)

    fg = get_pair(row, PAIR_KEYS["fg"])
    if fg and not t["fgm"] and not t["fga"]:
        t["fgm"], t["fga"] = fg

    fg3 = get_pair(row, PAIR_KEYS["fg3"])
    if fg3 and not t["fg3m"] and not t["fg3a"]:
        t["fg3m"], t["fg3a"] = fg3

    ft = get_pair(row, PAIR_KEYS["ft"])
    if ft and not t["ftm"] and not t["fta"]:
        t["ftm"], t["fta"] = ft

    return t

def div(a, b):
    return None if not b else a / b

def pct(a, b):
    x = div(a, b)
    return None if x is None else 100 * x

def calc_factors(off, defense=None):
    fga = off["fga"]
    fgm = off["fgm"]
    fg3m = off["fg3m"]
    fg3a = off["fg3a"]
    fta = off["fta"]
    pts = off["pts"]
    tov = off["tov"]
    oreb = off["oreb"]

    poss_est = fga + 0.44 * fta + tov
    out = {}

    if fga:
        out["teamEFG"] = 100 * ((fgm + 0.5 * fg3m) / fga)
        out["teamFTr"] = 100 * (fta / fga)
        out["team3PAr"] = 100 * (fg3a / fga)
        out["teamTS"] = 100 * (pts / (2 * (fga + 0.44 * fta))) if (fga + 0.44 * fta) else None

    if poss_est:
        out["teamTOVPct"] = 100 * (tov / poss_est)

    if defense and (oreb + defense["dreb"]):
        out["teamORBPct"] = 100 * (oreb / (oreb + defense["dreb"]))

    return {k: round(v, 3) for k, v in out.items() if v is not None}

def rename_allowed(factors):
    return {
        "oppAllowedEFG": factors.get("teamEFG"),
        "oppAllowedTOVPct": factors.get("teamTOVPct"),
        "oppAllowedORBPct": factors.get("teamORBPct"),
        "oppAllowedFTr": factors.get("teamFTr"),
        "oppAllowed3PAr": factors.get("team3PAr"),
        "oppAllowedTS": factors.get("teamTS"),
    }

def add_adjusted(row):
    pairs = [
        ("teamEFG", "oppAllowedEFG", "teamEFG_vsOppAllowed"),
        ("teamTOVPct", "oppAllowedTOVPct", "teamTOVPct_vsOppAllowed"),
        ("teamORBPct", "oppAllowedORBPct", "teamORBPct_vsOppAllowed"),
        ("teamFTr", "oppAllowedFTr", "teamFTr_vsOppAllowed"),
        ("team3PAr", "oppAllowed3PAr", "team3PAr_vsOppAllowed"),
        ("teamTS", "oppAllowedTS", "teamTS_vsOppAllowed"),
    ]

    for a, b, c in pairs:
        if row.get(a) is not None and row.get(b) is not None:
            row[c] = round(float(row[a]) - float(row[b]), 3)

def build_context(player_games):
    game_totals = {}
    game_meta = {}
    seen = set()

    for row in player_games:
        if not isinstance(row, dict):
            continue

        year = str(get_any(row, YEAR_KEYS)).strip()
        game_id = str(get_any(row, GAME_KEYS)).strip()
        team = norm_team(get_any(row, TEAM_KEYS))
        opp = norm_team(get_any(row, OPP_KEYS))
        series = str(get_any(row, SERIES_KEYS)).strip()

        if not year or not game_id or not team:
            continue

        pid = str(row.get("playerId") or row.get("PLAYER_ID") or row.get("nbaId") or row.get("name") or row.get("playerName") or "")
        dedupe = row.get("gameRowId") or f"{year}|{game_id}|{team}|{pid}"

        if dedupe in seen:
            continue
        seen.add(dedupe)

        key = (year, game_id, team)
        if key not in game_totals:
            game_totals[key] = empty_totals()

        add_totals(game_totals[key], row_totals(row))

        game_meta[key] = {
            "year": year,
            "gameId": game_id,
            "team": team,
            "opp": opp,
            "seriesCode": series,
        }

    game_ctx = {}

    for key, totals in game_totals.items():
        meta = game_meta[key]
        opp_key = (meta["year"], meta["gameId"], meta["opp"])
        opp_totals = game_totals.get(opp_key)

        factors = calc_factors(totals, opp_totals)
        if factors:
            game_ctx[key] = dict(factors)
            game_ctx[key]["_sixFactorSource"] = "derived_from_player_game_box_scores"
            game_ctx[key]["_sixFactorLabel"] = "Team Game Six Factors"

    # Build opponent allowed benchmark by year/team defense, using all playoff games in package.
    allowed_buckets = {}
    allowed_games = defaultdict(set)

    for key, totals in game_totals.items():
        meta = game_meta[key]
        defense_team = meta["opp"]
        defense_key = (meta["year"], defense_team)

        if defense_key not in allowed_buckets:
            allowed_buckets[defense_key] = {
                "off": empty_totals(),
                "def": empty_totals(),
            }

        defense_totals = game_totals.get((meta["year"], meta["gameId"], defense_team), empty_totals())
        add_totals(allowed_buckets[defense_key]["off"], totals)
        add_totals(allowed_buckets[defense_key]["def"], defense_totals)
        allowed_games[defense_key].add(meta["gameId"])

    for key, ctx in game_ctx.items():
        meta = game_meta[key]
        defense_key = (meta["year"], meta["opp"])
        bucket = allowed_buckets.get(defense_key)

        if bucket:
            allowed = calc_factors(bucket["off"], bucket["def"])
            allowed = rename_allowed(allowed)
            ctx.update({k: v for k, v in allowed.items() if v is not None})
            add_adjusted(ctx)

    # Series context from game totals.
    series_raw = {}

    for key, totals in game_totals.items():
        meta = game_meta[key]
        if not meta["seriesCode"]:
            continue

        skey = (meta["year"], meta["seriesCode"], meta["team"], meta["opp"])

        if skey not in series_raw:
            series_raw[skey] = {
                "off": empty_totals(),
                "def": empty_totals(),
                "games": set(),
            }

        add_totals(series_raw[skey]["off"], totals)

        opp_totals = game_totals.get((meta["year"], meta["gameId"], meta["opp"]), empty_totals())
        add_totals(series_raw[skey]["def"], opp_totals)
        series_raw[skey]["games"].add(meta["gameId"])

    series_ctx = {}

    for skey, raw in series_raw.items():
        year, series_code, team, opp = skey

        factors = calc_factors(raw["off"], raw["def"])
        if not factors:
            continue

        allowed_bucket = allowed_buckets.get((year, opp))
        if allowed_bucket:
            allowed = calc_factors(allowed_bucket["off"], allowed_bucket["def"])
            factors.update({k: v for k, v in rename_allowed(allowed).items() if v is not None})

        add_adjusted(factors)

        factors["_sixFactorSource"] = "derived_from_player_game_box_scores"
        factors["_sixFactorLabel"] = "Team Series Six Factors"
        factors["_seriesGamesCount"] = len(raw["games"])

        series_ctx[skey] = factors

    return game_ctx, series_ctx

def enrich_package(package):
    data = json.loads(package.read_text(errors="ignore"))

    player_games = data.get("playerGames", [])
    player_series = data.get("playerSeries", data.get("seriesPlayers", []))

    if not isinstance(player_games, list):
        print("No playerGames list in", package)
        return 0, 0, 0, 0

    game_ctx, series_ctx = build_context(player_games)

    game_enriched = 0
    series_enriched = 0

    for row in player_games:
        if not isinstance(row, dict):
            continue

        year = str(get_any(row, YEAR_KEYS)).strip()
        game_id = str(get_any(row, GAME_KEYS)).strip()
        team = norm_team(get_any(row, TEAM_KEYS))

        ctx = game_ctx.get((year, game_id, team))
        if not ctx:
            continue

        row.update(ctx)
        row["hasTeamSixFactors"] = True
        row["sixFactorContextLabel"] = "Team Game Six Factors"
        row["sixFactorAdjustmentLabel"] = "Team minus opponent playoff allowed benchmark"
        game_enriched += 1

    if isinstance(player_series, list):
        for row in player_series:
            if not isinstance(row, dict):
                continue

            year = str(get_any(row, YEAR_KEYS)).strip()
            series_code = str(get_any(row, SERIES_KEYS)).strip()
            team = norm_team(get_any(row, TEAM_KEYS))
            opp = norm_team(get_any(row, OPP_KEYS))

            ctx = series_ctx.get((year, series_code, team, opp))
            if not ctx:
                continue

            row.update(ctx)
            row["hasTeamSeriesSixFactors"] = True
            row["sixFactorContextLabel"] = "Team Series Six Factors"
            row["sixFactorAdjustmentLabel"] = "Team minus opponent playoff allowed benchmark"
            series_enriched += 1

    data["playerGames"] = player_games
    if "playerSeries" in data:
        data["playerSeries"] = player_series
    elif "seriesPlayers" in data:
        data["seriesPlayers"] = player_series

    data.setdefault("dataSources", {})
    if isinstance(data["dataSources"], dict):
        data["dataSources"]["derived_six_factors_game_series"] = {
            "installedAt": int(time.time()),
            "note": "Six factors derived from summed player box-score rows. Opponent adjustment uses opponent playoff allowed benchmark from the same package.",
            "gameContextKeys": len(game_ctx),
            "seriesContextKeys": len(series_ctx),
        }

    package.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False))

    return game_enriched, series_enriched, len(game_ctx), len(series_ctx)

def main():
    for package in PACKAGE_FILES:
        if not package.exists():
            print("Skipping missing:", package)
            continue

        backup = package.with_name(package.name + f".before-derived-six-factors.{int(time.time())}.bak")
        backup.write_text(package.read_text(errors="ignore"))

        game_enriched, series_enriched, game_keys, series_keys = enrich_package(package)

        print("")
        print("Package:", package)
        print("Backup:", backup)
        print("Game context keys built:", game_keys)
        print("Series context keys built:", series_keys)
        print("Player game rows enriched:", game_enriched)
        print("Player series rows enriched:", series_enriched)

    print("")
    print("DONE deriving/installing six factors from playerGames.")

if __name__ == "__main__":
    main()
