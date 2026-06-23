#!/usr/bin/env python3
import csv
import json
import time
from pathlib import Path

ROOT = Path(".")

PACKAGE_FILES = [
    ROOT / "data-package.json",
    ROOT / "data/data-package.json",
    ROOT / "public/data/data-package.embedded.json",
    ROOT / "public/data/data-package.json",
]

SCAN_DIRS = [
    ROOT / "data",
    ROOT / "public/data",
    ROOT,
]

YEAR_KEYS = ["year", "season", "SEASON", "Season"]
TEAM_KEYS = ["team", "TEAM", "teamAbbr", "team_abbr", "TEAM_ABBREVIATION", "Team", "TEAM_NAME"]
OPP_KEYS = ["opponent", "opp", "OPP", "opponentTeam", "Opponent", "VS", "vs"]
GAME_KEYS = ["gameId", "GAME_ID", "nbaGameId", "nba_game_id", "game_id"]
SERIES_KEYS = ["seriesCode", "series", "seriesId", "round"]

SIX_FACTOR_ALIASES = {
    "teamEFG": ["teamEFG", "TeamEFG", "eFG%", "EFG%", "eFG", "EFG", "EffectiveFGPct", "EffectiveFgPct"],
    "teamTOVPct": ["teamTOVPct", "teamTOV%", "TOV%", "TOVPct", "TurnoverPct", "TO%", "TO_PCT"],
    "teamORBPct": ["teamORBPct", "teamORB%", "ORB%", "ORBPct", "OREB%", "OREBPct", "OffRebPct"],
    "teamDRBPct": ["teamDRBPct", "teamDRB%", "DRB%", "DRBPct", "DREB%", "DREBPct", "DefRebPct"],
    "teamFTr": ["teamFTr", "FTr", "FTR", "FT_RATE", "FreeThrowRate", "FTA_RATE", "FTARate"],
    "team3PAr": ["team3PAr", "3PAr", "ThreePAR", "FG3ARate", "ThreePointAttemptRate", "3PA_RATE"],
    "teamTS": ["teamTS", "teamTS%", "TS%", "TSPct", "TrueShootingPct"],
}

OPP_ALLOWED_ALIASES = {
    "oppAllowedEFG": ["oppAllowedEFG", "oppEFGAllowed", "OppEFGAllowed", "OpponentEFG", "OpponentEFGPct", "EFGAllowed", "eFGAllowed"],
    "oppAllowedTOVPct": ["oppAllowedTOVPct", "oppTOVAllowed", "OppTOVAllowed", "OpponentTOVPct", "TOVAllowed", "TOAllowed"],
    "oppAllowedORBPct": ["oppAllowedORBPct", "oppORBAllowed", "OppORBAllowed", "OpponentORBPct", "ORBAllowed", "OREBAllowed"],
    "oppAllowedDRBPct": ["oppAllowedDRBPct", "oppDRBAllowed", "OppDRBAllowed", "OpponentDRBPct", "DRBAllowed", "DREBAllowed"],
    "oppAllowedFTr": ["oppAllowedFTr", "oppFTrAllowed", "OppFTrAllowed", "OpponentFTr", "FTrAllowed", "FTARateAllowed"],
    "oppAllowed3PAr": ["oppAllowed3PAr", "opp3PArAllowed", "Opp3PArAllowed", "Opponent3PAr", "3PArAllowed", "FG3ARateAllowed"],
    "oppAllowedTS": ["oppAllowedTS", "OppRSAdjTSAllowed", "oppTSAllowed", "OppTSAllowed", "OpponentTS", "TSAllowed"],
}

ADJ_PAIRS = [
    ("teamEFG", "oppAllowedEFG", "teamEFG_vsOppAllowed"),
    ("teamTOVPct", "oppAllowedTOVPct", "teamTOVPct_vsOppAllowed"),
    ("teamORBPct", "oppAllowedORBPct", "teamORBPct_vsOppAllowed"),
    ("teamDRBPct", "oppAllowedDRBPct", "teamDRBPct_vsOppAllowed"),
    ("teamFTr", "oppAllowedFTr", "teamFTr_vsOppAllowed"),
    ("team3PAr", "oppAllowed3PAr", "team3PAr_vsOppAllowed"),
    ("teamTS", "oppAllowedTS", "teamTS_vsOppAllowed"),
]

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

def norm_key(k):
    return str(k).lower().replace(" ", "").replace("_", "").replace("-", "").replace("%", "pct").replace(".", "")

def get_any(row, keys):
    for k in keys:
        if k in row and row[k] not in [None, ""]:
            return row[k]
    return ""

def num(v):
    if v in [None, "", "—"]:
        return None
    try:
        return float(str(v).replace("%", "").replace(",", "").strip())
    except Exception:
        return None

def read_json(path):
    try:
        return json.loads(path.read_text(errors="ignore"))
    except Exception:
        return None

def walk(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk(v)

def load_rows(path):
    try:
        if path.suffix.lower() == ".csv":
            with path.open(newline="", errors="ignore") as f:
                return list(csv.DictReader(f))
        if path.suffix.lower() == ".json":
            obj = read_json(path)
            return [r for r in walk(obj) if isinstance(r, dict)]
    except Exception:
        return []
    return []

def find_col(row, aliases):
    lookup = {norm_key(k): k for k in row.keys()}
    for a in aliases:
        nk = norm_key(a)
        if nk in lookup:
            return lookup[nk]
    return None

def extract_six_context(row):
    out = {}

    for out_key, aliases in SIX_FACTOR_ALIASES.items():
        col = find_col(row, aliases)
        if col:
            v = num(row.get(col))
            if v is not None:
                out[out_key] = v

    for out_key, aliases in OPP_ALLOWED_ALIASES.items():
        col = find_col(row, aliases)
        if col:
            v = num(row.get(col))
            if v is not None:
                out[out_key] = v

    return out

def add_adjusted(row):
    for team_key, opp_key, out_key in ADJ_PAIRS:
        a = num(row.get(team_key))
        b = num(row.get(opp_key))
        if a is not None and b is not None:
            row[out_key] = a - b

def file_is_context(path):
    name = str(path).lower()
    if any(skip in name for skip in ["node_modules", ".git", "backups", "logs"]):
        return False

    good_words = [
        "team", "teamgame", "series", "advanced", "four_factor", "fourfactor",
        "factor", "allowed", "defense", "offense"
    ]

    bad_words = [
        "shotzone", "shot_zone", "rimfreq", "rim_acc", "paint", "pullup",
        "catchshoot", "drives", "post", "elbow", "tracking", "hustle", "passing"
    ]

    if any(b in name for b in bad_words):
        return False

    return any(w in name for w in good_words)

def scan_context():
    game_ctx = {}
    series_ctx = {}
    files_scanned = 0
    useful_rows = 0

    paths = []
    for base in SCAN_DIRS:
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if p.suffix.lower() in [".csv", ".json"] and file_is_context(p):
                paths.append(p)

    for path in sorted(set(paths)):
        rows = load_rows(path)
        if not rows:
            continue

        files_scanned += 1

        for row in rows:
            ctx = extract_six_context(row)
            if not ctx:
                continue

            # Do not treat pure player box-score rows as team context unless they have explicit team/opp allowed keys.
            keyblob = " ".join(row.keys()).lower()
            if "player" in keyblob and not any(k.startswith("oppAllowed") or k.startswith("team") for k in ctx):
                continue

            year = str(get_any(row, YEAR_KEYS)).strip()
            team = norm_team(get_any(row, TEAM_KEYS))
            opp = norm_team(get_any(row, OPP_KEYS))
            game_id = str(get_any(row, GAME_KEYS)).strip()
            series_code = str(get_any(row, SERIES_KEYS)).strip()

            if year and team and game_id:
                key = (year, game_id, team)
                game_ctx.setdefault(key, {}).update(ctx)
                game_ctx[key].setdefault("_sixFactorSources", set()).add(str(path))
                useful_rows += 1

            if year and team and series_code:
                key = (year, series_code, team, opp)
                series_ctx.setdefault(key, {}).update(ctx)
                series_ctx[key].setdefault("_sixFactorSources", set()).add(str(path))
                useful_rows += 1

    for d in [game_ctx, series_ctx]:
        for row in d.values():
            if isinstance(row.get("_sixFactorSources"), set):
                row["_sixFactorSources"] = sorted(row["_sixFactorSources"])

    print("Six-factor context files scanned:", files_scanned)
    print("Useful six-factor rows indexed:", useful_rows)
    print("Game context keys:", len(game_ctx))
    print("Series context keys:", len(series_ctx))

    return game_ctx, series_ctx

def enrich_package(package, game_ctx, series_ctx):
    data = json.loads(package.read_text(errors="ignore"))

    pg = data.get("playerGames", [])
    ps = data.get("playerSeries", data.get("seriesPlayers", []))

    game_enriched = 0
    series_enriched = 0

    if isinstance(pg, list):
        for row in pg:
            if not isinstance(row, dict):
                continue

            year = str(get_any(row, YEAR_KEYS)).strip()
            game_id = str(get_any(row, GAME_KEYS)).strip()
            team = norm_team(get_any(row, TEAM_KEYS))

            ctx = game_ctx.get((year, game_id, team))

            if ctx:
                row.update(ctx)
                add_adjusted(row)
                row["hasTeamSixFactors"] = True
                row["sixFactorContextLabel"] = "Team Game Six Factors"
                row["sixFactorAdjustmentLabel"] = "Team minus opponent allowed"
                game_enriched += 1

    if isinstance(ps, list):
        for row in ps:
            if not isinstance(row, dict):
                continue

            year = str(get_any(row, YEAR_KEYS)).strip()
            series_code = str(get_any(row, SERIES_KEYS)).strip()
            team = norm_team(get_any(row, TEAM_KEYS))
            opp = norm_team(get_any(row, OPP_KEYS))

            ctx = (
                series_ctx.get((year, series_code, team, opp))
                or series_ctx.get((year, series_code, team, ""))
            )

            if ctx:
                row.update(ctx)
                add_adjusted(row)
                row["hasTeamSeriesSixFactors"] = True
                row["sixFactorContextLabel"] = "Team Series Six Factors"
                row["sixFactorAdjustmentLabel"] = "Team minus opponent allowed"
                series_enriched += 1

    data["playerGames"] = pg
    if "playerSeries" in data:
        data["playerSeries"] = ps
    elif "seriesPlayers" in data:
        data["seriesPlayers"] = ps

    data.setdefault("dataSources", {})
    if isinstance(data["dataSources"], dict):
        data["dataSources"]["six_factors_game_series"] = {
            "installedAt": int(time.time()),
            "gameContextKeys": len(game_ctx),
            "seriesContextKeys": len(series_ctx),
            "note": "Adds team game/series six factors and opponent-allowed adjustments only. No shot-location on-court fields."
        }

    package.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False))

    return game_enriched, series_enriched

def main():
    game_ctx, series_ctx = scan_context()

    if not game_ctx and not series_ctx:
        print("")
        print("No six-factor context found.")
        print("Check if team advanced / teamgame / series files exist locally.")
        return

    for package in PACKAGE_FILES:
        if not package.exists():
            print("Skipping missing package:", package)
            continue

        backup = package.with_name(package.name + f".before-six-factors.{int(time.time())}.bak")
        backup.write_text(package.read_text(errors="ignore"))

        game_count, series_count = enrich_package(package, game_ctx, series_ctx)

        print("")
        print("Package:", package)
        print("Backup:", backup)
        print("Player game rows enriched:", game_count)
        print("Player series rows enriched:", series_count)

    print("")
    print("DONE installing six factors only.")

if __name__ == "__main__":
    main()
