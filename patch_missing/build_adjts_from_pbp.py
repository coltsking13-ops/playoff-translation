#!/usr/bin/env python3
"""
Build verified player-game adjusted true shooting ingredients from pbpstats.com API game logs.

This version intentionally avoids stats.nba.com scoreboard lookup and data.nba.com schedule lookup.
It requests game-log rows directly from https://api.pbpstats.com and matches them back to the
site's playerGames rows by player id + date + teams.

Definition used by Playoff Translation Lab:
  Scoring TOV = total TOV - bad-pass TOV - bad-pass-out-of-bounds TOV
  AdjFGA = FGA + scoring TOV - heave attempts - Z Bounds
  AdjFTA = FTA - technical FTA
  AdjTS% = PTS / (2 * (AdjFGA + 0.44 * AdjFTA))
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests

ROOT = Path(__file__).resolve().parent
DATA_PACKAGE = ROOT / "data-package.json"
DATA_COPY = ROOT / "data" / "data-package.json"
INDEX_FILE = ROOT / "index.html"
OUT_CSV = ROOT / "data" / "player_game_adjts_ingredients.csv"
CACHE_DIR = ROOT / "data" / "pbpstats_api_cache"
API_BASE = "https://api.pbpstats.com/get-game-logs/nba"

PBPSTATS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.pbpstats.com",
    "Referer": "https://www.pbpstats.com/",
    "Connection": "keep-alive",
}

TEAM_ALIASES = {
    "ATL": "ATL", "BOS": "BOS", "BKN": "BKN", "BRK": "BKN", "NJN": "NJN",
    "CHA": "CHA", "CHH": "CHH", "CHO": "CHA", "CHI": "CHI", "CLE": "CLE",
    "DAL": "DAL", "DEN": "DEN", "DET": "DET", "GS": "GSW", "GSW": "GSW",
    "HOU": "HOU", "IND": "IND", "LAC": "LAC", "LAL": "LAL", "MEM": "MEM",
    "MIA": "MIA", "MIL": "MIL", "MIN": "MIN", "NOH": "NOH", "NOK": "NOH",
    "NOR": "NOH", "NOP": "NOP", "NY": "NYK", "NYK": "NYK", "ORL": "ORL",
    "PHI": "PHI", "PHO": "PHX", "PHX": "PHX", "POR": "POR", "SAC": "SAC",
    "SA": "SAS", "SAS": "SAS", "SEA": "SEA", "OKC": "OKC", "TOR": "TOR",
    "UTA": "UTA", "VAN": "VAN", "WAS": "WAS", "WSB": "WAS",
}


def safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return None if math.isnan(number) or math.isinf(number) else number
    text = str(value).strip()
    if text in {"", "—", "None", "null", "nan", "NaN"}:
        return None
    try:
        number = float(text.replace(",", ""))
    except ValueError:
        return None
    return None if math.isnan(number) or math.isinf(number) else number


def safe_int(value: Any) -> Optional[int]:
    number = safe_float(value)
    if number is None:
        return None
    return int(round(number))


def round_value(value: Optional[float], digits: int = 1) -> Optional[float]:
    if value is None:
        return None
    if math.isnan(value) or math.isinf(value):
        return None
    return round(float(value), digits)


def normalize_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def normalize_team(team: Any) -> str:
    text = str(team or "").strip().upper()
    return TEAM_ALIASES.get(text, text)


def normalize_nba_game_id(value: Any) -> str:
    text = str(value or "").strip()
    if not re.fullmatch(r"\d{7,10}", text):
        return ""
    return text.zfill(10)


def local_game_key(value: Any) -> str:
    real_id = normalize_nba_game_id(value)
    return real_id if real_id else str(value or "").strip()


def parse_generated_game_id(value: Any) -> Optional[Dict[str, str]]:
    text = str(value or "")
    m = re.search(r"gen_(\d{4})_(\d{8})_([A-Za-z]{2,4})_([A-Za-z]{2,4})", text)
    if not m:
        return None
    return {
        "year": m.group(1),
        "date8": m.group(2),
        "team1": normalize_team(m.group(3)),
        "team2": normalize_team(m.group(4)),
    }


def date8(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    # Handles 2001-04-21, 04/21/2001, 20010421, ISO datetimes.
    m = re.search(r"(\d{4})[-/]?(\d{2})[-/]?(\d{2})", text)
    if m:
        return f"{m.group(1)}{m.group(2)}{m.group(3)}"
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", text)
    if m:
        return f"{m.group(3)}{int(m.group(1)):02d}{int(m.group(2)):02d}"
    digits = re.sub(r"\D", "", text)
    return digits[:8] if len(digits) >= 8 else ""


def date_dash(value: Any) -> str:
    d = date8(value)
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}" if len(d) == 8 else ""


def playoff_year_to_season_label(year: int) -> str:
    # 2001 playoff year -> 2000-01 pbpstats season label.
    return f"{year - 1}-{str(year)[-2:]}"


def parse_years(text: str) -> Optional[List[int]]:
    if not text or text.lower() in {"all", "*"}:
        return None
    years: List[int] = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            years.extend(range(int(a), int(b) + 1))
        else:
            years.append(int(part))
    return sorted(set(years))


def row_get(row: Dict[str, Any], names: Iterable[str]) -> Any:
    normalized = {normalize_key(k): v for k, v in row.items()}
    for name in names:
        key = normalize_key(name)
        if key in normalized:
            return normalized[key]
    return None


def row_num(row: Dict[str, Any], names: Iterable[str]) -> float:
    return safe_float(row_get(row, names)) or 0.0


def find_list_of_dicts(payload: Any) -> List[Dict[str, Any]]:
    """Tolerantly find the biggest useful list of dicts in an unknown API JSON shape."""
    candidates: List[List[Dict[str, Any]]] = []

    def walk(obj: Any) -> None:
        if isinstance(obj, list):
            if obj and all(isinstance(x, dict) for x in obj):
                candidates.append(obj)  # type: ignore[arg-type]
            for item in obj:
                walk(item)
        elif isinstance(obj, dict):
            for value in obj.values():
                walk(value)

    walk(payload)
    if not candidates:
        return []

    def score(rows: List[Dict[str, Any]]) -> Tuple[int, int]:
        keys = set()
        for row in rows[:10]:
            keys.update(normalize_key(k) for k in row)
        wanted = {
            "gameid", "date", "gamedate", "team", "teamabbreviation", "opponent",
            "badpassturnovers", "heaveattempts", "selforeb", "technicalfreethrowattempts",
        }
        return (len(keys & wanted), len(rows))

    return max(candidates, key=score)


def fetch_json_cached(url: str, params: Dict[str, Any], cache_path: Path, sleep: float, force: bool) -> Any:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if cache_path.exists() and not force:
        try:
            return json.loads(cache_path.read_text())
        except Exception:
            pass
    last_error: Optional[Exception] = None
    for attempt in range(3):
        try:
            resp = requests.get(url, params=params, headers=PBPSTATS_HEADERS, timeout=45)
            resp.raise_for_status()
            payload = resp.json()
            cache_path.write_text(json.dumps(payload))
            if sleep:
                time.sleep(sleep)
            return payload
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(max(sleep, 0.5) * (attempt + 1))
    raise RuntimeError(str(last_error))


def api_cache_path(year: int, entity_id: Optional[str], all_players: bool = False) -> Path:
    if all_players:
        return CACHE_DIR / f"{year}_all_players_game_logs.json"
    return CACHE_DIR / f"{year}_player_{entity_id}_game_logs.json"


def fetch_pbpstats_game_logs(year: int, player_ids: List[str], sleep: float, force: bool) -> Dict[str, List[Dict[str, Any]]]:
    """Return pbpstats.com API game logs keyed by NBA player id.

    Important: this version intentionally uses per-player requests instead of trusting
    the all-player endpoint. For older seasons the all-player endpoint can return a
    partial set, which left real players like Nash/Payton/Finley without cache rows.
    """
    season_label = playoff_year_to_season_label(year)
    by_player: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for idx, pid in enumerate(player_ids, start=1):
        params = {"Season": season_label, "SeasonType": "Playoffs", "EntityType": "Player", "EntityId": pid}
        try:
            payload = fetch_json_cached(API_BASE, params, api_cache_path(year, pid), sleep=sleep, force=force)
            rows = find_list_of_dicts(payload)
        except Exception as exc:  # noqa: BLE001
            print(f"  player {idx}/{len(player_ids)} {pid}: API failed: {exc}")
            continue
        if rows:
            by_player[pid].extend(rows)
            print(f"  player {idx}/{len(player_ids)} {pid}: {len(rows)} game-log rows")
        else:
            print(f"  player {idx}/{len(player_ids)} {pid}: 0 rows")
    return by_player

def local_match_keys(game: Dict[str, Any]) -> List[Tuple[str, str, str, str]]:
    pid = str(game.get("nbaId") or "")
    if not pid:
        return []
    local_id = game.get("gameId")
    parsed = parse_generated_game_id(local_id)
    d = date8(game.get("date")) or (parsed or {}).get("date8", "")
    team = normalize_team(game.get("team"))
    opp = normalize_team(game.get("opponent"))
    keys = []
    if d and team and opp:
        keys.append((pid, d, team, opp))
        keys.append((pid, d, opp, team))
    if parsed:
        keys.append((pid, parsed["date8"], parsed["team1"], parsed["team2"]))
        keys.append((pid, parsed["date8"], parsed["team2"], parsed["team1"]))
    return list(dict.fromkeys(keys))


def api_match_keys(pid: str, row: Dict[str, Any]) -> List[Tuple[str, str, str, str]]:
    d = date8(row_get(row, ["Date", "GameDate", "Game Date", "date", "game_date", "GameDateTime", "DateTime"]))
    team = normalize_team(row_get(row, ["Team", "TeamAbbreviation", "Team Abbreviation", "team", "team_abbreviation"]))
    opp = normalize_team(row_get(row, ["Opponent", "OpponentAbbreviation", "Opponent Abbreviation", "opp", "opponent_abbreviation"]))
    keys: List[Tuple[str, str, str, str]] = []
    if d and team and opp:
        keys.append((pid, d, team, opp))
        keys.append((pid, d, opp, team))
    # If team/opponent are absent, date-only matching is allowed later only when unique.
    return keys


def api_date_key(pid: str, row: Dict[str, Any]) -> Tuple[str, str]:
    d = date8(row_get(row, ["Date", "GameDate", "Game Date", "date", "game_date", "GameDateTime", "DateTime"]))
    return (pid, d)


def extract_ingredient_values(row: Dict[str, Any]) -> Dict[str, float]:
    bad = row_num(row, ["BadPassTurnovers", "Bad Pass Turnovers", "BadPassTOV", "BadPassTO"])
    bad_oob = row_num(row, [
        "BadPassOutOfBoundsTurnovers", "Bad Pass Out Of Bounds Turnovers",
        "BadPassOutOfBoundsTOV", "BadPassOutOfBoundsTO", "BadPassOutOfBounds",
    ])
    heaves = row_num(row, ["HeaveAttempts", "Heave Attempts", "Heaves"])
    if heaves == 0:
        heaves = row_num(row, ["HeaveMakes", "Heave Makes"]) + row_num(row, ["HeaveMisses", "Heave Misses"])
    z_bounds = row_num(row, ["SelfOReb", "Self OReb", "SelfOffensiveRebounds", "Self Offensive Rebounds", "SelfORebounds", "ZBounds", "Z Bounds"])
    tech_fta = row_num(row, [
        "TechnicalFreeThrowAttempts", "Technical Free Throw Attempts", "TechnicalFTA", "TechFTA",
        "TechnicalFreeThrowTrips", "Technical Free Throw Trips", "TechnicalFTAs", "Technical FTA",
    ])
    return {
        "BadPassTOV": bad,
        "BadPassOutOfBoundsTOV": bad_oob,
        "Heaves": heaves,
        "ZBounds": z_bounds,
        "TechFTA": tech_fta,
    }


def base_games_for_years(data: Dict[str, Any], years: Optional[Iterable[int]]) -> List[Dict[str, Any]]:
    year_set = set(years or [])
    out = []
    for game in data.get("playerGames", []):
        y = safe_int(game.get("year"))
        if not y:
            continue
        if year_set and y not in year_set:
            continue
        if not game.get("nbaId"):
            continue
        out.append(game)
    return out


def build_api_row_lookup(year: int, games: List[Dict[str, Any]], sleep: float, force: bool) -> Dict[Tuple[str, str, str, str], Dict[str, Any]]:
    player_ids = sorted({str(g.get("nbaId")) for g in games if g.get("nbaId")})
    logs = fetch_pbpstats_game_logs(year, player_ids, sleep=sleep, force=force)
    exact: Dict[Tuple[str, str, str, str], Dict[str, Any]] = {}
    by_date: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for pid, rows in logs.items():
        for row in rows:
            for key in api_match_keys(pid, row):
                exact[key] = row
            dk = api_date_key(pid, row)
            if dk[1]:
                by_date[dk].append(row)

    # Date-only fallback when a player only has one API row on that date.
    for (pid, d), rows in by_date.items():
        if len(rows) == 1:
            # Wildcard key uses empty team/opponent.
            exact[(pid, d, "", "")] = rows[0]
    return exact


def match_api_row(game: Dict[str, Any], lookup: Dict[Tuple[str, str, str, str], Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    for key in local_match_keys(game):
        if key in lookup:
            return lookup[key]
    pid = str(game.get("nbaId") or "")
    d = date8(game.get("date"))
    if pid and d:
        return lookup.get((pid, d, "", ""))
    return None


def write_ingredients_csv(data: Dict[str, Any], years: Optional[List[int]], force: bool, sleep: float, limit_games: Optional[int], missing_only: bool = False) -> Path:
    games = base_games_for_years(data, years)
    if missing_only:
        before = len(games)
        games = [
            g for g in games
            if not (str(g.get("AdjTS_source") or "").startswith("verified game-level") and g.get("AdjTS%") not in (None, "", "—"))
        ]
        print(f"Missing-only mode: {len(games)} unresolved player-game rows selected from {before} rows.")
        print(f"Missing-only mode: {len({str(g.get('nbaId')) for g in games if g.get('nbaId')})} players to request.")
    if limit_games:
        # Keep complete player rows for the first N games.
        ordered_game_ids = []
        seen = set()
        for g in games:
            gid = local_game_key(g.get("gameId"))
            if gid not in seen:
                seen.add(gid)
                ordered_game_ids.append(gid)
            if len(ordered_game_ids) >= limit_games:
                break
        keep = set(ordered_game_ids)
        games = [g for g in games if local_game_key(g.get("gameId")) in keep]

    year_values = sorted({safe_int(g.get("year")) for g in games if safe_int(g.get("year"))})
    year_set = set(year_values)

    fieldnames = [
        "gameId", "nbaGameId", "playerId", "nbaId", "playerName", "year", "team", "opponent",
        "PTS", "FGA", "FTA", "TOV",
        "BadPassTOV", "BadPassOutOfBoundsTOV", "ScoringTOV", "Heaves", "ZBounds", "TechFTA",
        "AdjFGA", "AdjFTA", "AdjTS%", "source",
    ]

    existing_rows: Dict[Tuple[str, str], Dict[str, Any]] = {}
    if OUT_CSV.exists():
        with OUT_CSV.open(newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                y = safe_int(row.get("year"))
                if force and y in year_set:
                    continue
                existing_rows[(local_game_key(row.get("gameId")), str(row.get("nbaId") or ""))] = row

    rebuilt = 0
    matched_games = 0
    unmatched_games = 0
    games_by_year: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for g in games:
        y = safe_int(g.get("year"))
        if y:
            games_by_year[y].append(g)

    for year, year_games in sorted(games_by_year.items()):
        print(f"Fetching pbpstats.com API game logs for playoff year {year} ({playoff_year_to_season_label(year)})...")
        lookup = build_api_row_lookup(year, year_games, sleep=sleep, force=force)
        print(f"pbpstats.com API lookup keys for {year}: {len(lookup):,}")

        by_local_game = defaultdict(list)
        for g in year_games:
            by_local_game[local_game_key(g.get("gameId"))].append(g)

        for idx, (gid, rows) in enumerate(sorted(by_local_game.items()), start=1):
            game_matched = 0
            for game in rows:
                nba_id = str(game.get("nbaId") or "")
                key = (local_game_key(game.get("gameId")), nba_id)
                if key in existing_rows and not force:
                    continue
                api_row = match_api_row(game, lookup)
                if not api_row:
                    continue
                vals = extract_ingredient_values(api_row)
                pts = safe_float(game.get("PTS"))
                fga = safe_float(game.get("FGA"))
                fta = safe_float(game.get("FTA"))
                tov = safe_float(game.get("TOV"))
                if pts is None or fga is None or fta is None or tov is None:
                    continue
                bad = vals["BadPassTOV"]
                bad_oob = vals["BadPassOutOfBoundsTOV"]
                heaves = vals["Heaves"]
                z_bounds = vals["ZBounds"]
                tech_fta = vals["TechFTA"]
                scoring_tov = max(tov - bad - bad_oob, 0.0)
                adj_fga = max(fga + scoring_tov - heaves - z_bounds, 0.0)
                adj_fta = max(fta - tech_fta, 0.0)
                denom = 2 * (adj_fga + 0.44 * adj_fta)
                adj_ts = 100 * pts / denom if denom > 0 else None
                real_gid = normalize_nba_game_id(row_get(api_row, ["GameId", "GameID", "game_id"])) or ""
                existing_rows[key] = {
                    "gameId": key[0],
                    "nbaGameId": real_gid,
                    "playerId": game.get("playerId"),
                    "nbaId": nba_id,
                    "playerName": game.get("playerName"),
                    "year": game.get("year"),
                    "team": game.get("team"),
                    "opponent": game.get("opponent"),
                    "PTS": round_value(pts, 1),
                    "FGA": round_value(fga, 1),
                    "FTA": round_value(fta, 1),
                    "TOV": round_value(tov, 1),
                    "BadPassTOV": round_value(bad, 1),
                    "BadPassOutOfBoundsTOV": round_value(bad_oob, 1),
                    "ScoringTOV": round_value(scoring_tov, 1),
                    "Heaves": round_value(heaves, 1),
                    "ZBounds": round_value(z_bounds, 1),
                    "TechFTA": round_value(tech_fta, 1),
                    "AdjFGA": round_value(adj_fga, 1),
                    "AdjFTA": round_value(adj_fta, 1),
                    "AdjTS%": round_value(adj_ts, 1),
                    "source": "pbpstats.com API game logs",
                }
                rebuilt += 1
                game_matched += 1
            if game_matched:
                matched_games += 1
                print(f"  [{idx}/{len(by_local_game)}] {gid}: matched {game_matched}/{len(rows)} player rows")
            else:
                unmatched_games += 1
                print(f"  [{idx}/{len(by_local_game)}] {gid}: no pbpstats.com API match")

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for key in sorted(existing_rows.keys()):
            row = existing_rows[key]
            writer.writerow({name: row.get(name, "") for name in fieldnames})

    print(
        f"Wrote {OUT_CSV} with {len(existing_rows):,} rows. "
        f"Newly rebuilt rows: {rebuilt:,}. Matched games: {matched_games}. Unmatched games: {unmatched_games}."
    )
    return OUT_CSV


def weighted_average(pairs: Iterable[Tuple[Optional[float], Optional[float]]]) -> Optional[float]:
    num = 0.0
    den = 0.0
    for value, weight in pairs:
        if value is None:
            continue
        w = weight if weight and weight > 0 else 1.0
        num += value * w
        den += w
    return num / den if den else None


def ts_from_totals(points: Optional[float], fga: Optional[float], fta: Optional[float]) -> Optional[float]:
    if points is None or fga is None or fta is None:
        return None
    denom = 2 * (fga + 0.44 * fta)
    return 100 * points / denom if denom > 0 else None


def apply_ingredients(data: Dict[str, Any], ingredients_csv: Path = OUT_CSV) -> Dict[str, Any]:
    lookup: Dict[Tuple[str, str], Dict[str, Any]] = {}
    if not ingredients_csv.exists():
        raise FileNotFoundError(f"Missing {ingredients_csv}")
    with ingredients_csv.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            lookup[(local_game_key(row.get("gameId")), str(row.get("nbaId") or ""))] = row

    updated_games = 0
    for game in data.get("playerGames", []):
        key = (local_game_key(game.get("gameId")), str(game.get("nbaId") or ""))
        row = lookup.get(key)
        if not row:
            continue
        adj_ts = safe_float(row.get("AdjTS%"))
        if adj_ts is None:
            continue
        game["AdjTS%"] = round_value(adj_ts, 1)
        game["AdjTS_source"] = "verified game-level pbpstats.com API game logs"
        if row.get("nbaGameId"):
            game["nbaGameId"] = row.get("nbaGameId")
        for key_name in ["AdjFGA", "AdjFTA", "ScoringTOV", "BadPassTOV", "BadPassOutOfBoundsTOV", "Heaves", "ZBounds", "TechFTA"]:
            game[key_name] = round_value(safe_float(row.get(key_name)), 1)
        allowed = safe_float(game.get("OppRSAdjTSAllowed"))
        game["rAdjTS"] = round_value(adj_ts - allowed, 1) if allowed is not None else None
        updated_games += 1

    # Rebuild series AdjTS only where every game in the series has verified game-level AdjTS.
    series_groups: Dict[Tuple[str, int, str, str, str], List[Dict[str, Any]]] = defaultdict(list)
    for game in data.get("playerGames", []):
        group_key = (
            str(game.get("playerId") or ""),
            safe_int(game.get("year")) or 0,
            str(game.get("team") or ""),
            str(game.get("opponent") or ""),
            str(game.get("seriesCode") or ""),
        )
        series_groups[group_key].append(game)

    by_series_id = {s.get("seriesId"): s for s in data.get("playerSeries", [])}
    updated_series = 0
    for _group_key, rows in series_groups.items():
        if not rows:
            continue
        first = rows[0]
        sid = f"{first.get('playerId')}_{first.get('year')}_{first.get('seriesCode')}_{first.get('opponent')}"
        series = by_series_id.get(sid)
        if not series:
            continue
        verified = [r for r in rows if str(r.get("AdjTS_source") or "").startswith("verified game-level") and r.get("AdjTS%") is not None]
        if len(verified) != len(rows):
            if "AdjTS_source" in series:
                series["AdjTS%"] = None
                series["rAdjTS"] = None
                series["AdjTS_source"] = "unavailable: not every game in series has verified PBP AdjTS ingredients"
            continue
        pts = sum(safe_float(r.get("PTS")) or 0 for r in rows)
        adj_fga = sum(safe_float(r.get("AdjFGA")) or 0 for r in rows)
        adj_fta = sum(safe_float(r.get("AdjFTA")) or 0 for r in rows)
        adj_ts = ts_from_totals(pts, adj_fga, adj_fta)
        series["AdjTS%"] = round_value(adj_ts, 1)
        series["AdjTS_source"] = "verified series aggregation of game-level pbpstats.com API AdjTS"
        series["AdjFGA"] = round_value(adj_fga, 1)
        series["AdjFTA"] = round_value(adj_fta, 1)
        series["ScoringTOV"] = round_value(sum(safe_float(r.get("ScoringTOV")) or 0 for r in rows), 1)
        series["Heaves"] = round_value(sum(safe_float(r.get("Heaves")) or 0 for r in rows), 1)
        series["ZBounds"] = round_value(sum(safe_float(r.get("ZBounds")) or 0 for r in rows), 1)
        series["TechFTA"] = round_value(sum(safe_float(r.get("TechFTA")) or 0 for r in rows), 1)
        allowed = safe_float(series.get("OppRSAdjTSAllowed"))
        if allowed is None:
            allowed = weighted_average((safe_float(r.get("OppRSAdjTSAllowed")), safe_float(r.get("POSS")) or safe_float(r.get("MIN"))) for r in rows)
            series["OppRSAdjTSAllowed"] = round_value(allowed, 1)
        series["rAdjTS"] = round_value(adj_ts - allowed, 1) if adj_ts is not None and allowed is not None else None
        updated_series += 1

    # Rebuild season AdjTS only where every player-game in that player/team/year group is verified.
    season_groups: Dict[Tuple[str, int, str], List[Dict[str, Any]]] = defaultdict(list)
    for game in data.get("playerGames", []):
        season_groups[(str(game.get("playerId") or ""), safe_int(game.get("year")) or 0, str(game.get("team") or ""))].append(game)
    season_lookup = {(str(s.get("playerId") or ""), safe_int(s.get("year")) or 0, str(s.get("team") or "")): s for s in data.get("playerSeasons", [])}
    updated_seasons = 0
    for group_key, rows in season_groups.items():
        season = season_lookup.get(group_key)
        if not season or not rows:
            continue
        verified = [r for r in rows if str(r.get("AdjTS_source") or "").startswith("verified game-level") and r.get("AdjTS%") is not None]
        if len(verified) != len(rows):
            continue
        pts = sum(safe_float(r.get("PTS")) or 0 for r in rows)
        adj_fga = sum(safe_float(r.get("AdjFGA")) or 0 for r in rows)
        adj_fta = sum(safe_float(r.get("AdjFTA")) or 0 for r in rows)
        adj_ts = ts_from_totals(pts, adj_fga, adj_fta)
        season["AdjTS%"] = round_value(adj_ts, 1)
        season["AdjTS_source"] = "verified season aggregation of game-level pbpstats.com API AdjTS"
        season["AdjFGA"] = round_value(adj_fga, 1)
        season["AdjFTA"] = round_value(adj_fta, 1)
        season["ScoringTOV"] = round_value(sum(safe_float(r.get("ScoringTOV")) or 0 for r in rows), 1)
        season["Heaves"] = round_value(sum(safe_float(r.get("Heaves")) or 0 for r in rows), 1)
        season["ZBounds"] = round_value(sum(safe_float(r.get("ZBounds")) or 0 for r in rows), 1)
        season["TechFTA"] = round_value(sum(safe_float(r.get("TechFTA")) or 0 for r in rows), 1)
        allowed = safe_float(season.get("OppRSAdjTSAllowed"))
        if allowed is None:
            allowed = weighted_average((safe_float(r.get("OppRSAdjTSAllowed")), safe_float(r.get("POSS")) or safe_float(r.get("MIN"))) for r in rows)
            season["OppRSAdjTSAllowed"] = round_value(allowed, 1)
        season["rAdjTS"] = round_value(adj_ts - allowed, 1) if adj_ts is not None and allowed is not None else None
        updated_seasons += 1

    metadata = data.setdefault("metadata", {})
    counts = metadata.setdefault("counts", {})
    counts["verifiedGameAdjTSRows"] = updated_games
    counts["verifiedSeriesAdjTSRows"] = updated_series
    counts["verifiedSeasonAdjTSRowsFromGames"] = updated_seasons
    notes = metadata.setdefault("notes", [])
    note = "Game/series AdjTS uses pbpstats.com API game-log ingredients when available; rows stay blank/unavailable when pbpstats.com does not return the required ingredients."
    if note not in notes:
        notes.append(note)
    return data


def embed_data_in_index(data: Dict[str, Any]) -> None:
    if not INDEX_FILE.exists():
        return
    html = INDEX_FILE.read_text()
    payload = json.dumps(data, separators=(",", ":"))
    marker = '<script type="application/json" id="ptl-data">'
    start = html.find(marker)
    if start == -1:
        return
    content_start = start + len(marker)
    end = html.find("</script>", content_start)
    if end == -1:
        return
    INDEX_FILE.write_text(html[:content_start] + "\n" + payload + "\n" + html[end:])


def write_data_package(data: Dict[str, Any]) -> None:
    DATA_PACKAGE.write_text(json.dumps(data, indent=2))
    DATA_COPY.parent.mkdir(parents=True, exist_ok=True)
    DATA_COPY.write_text(json.dumps(data, indent=2))
    embed_data_in_index(data)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build/apply verified AdjTS from direct pbpstats.com API game logs.")
    parser.add_argument("--years", default="2020", help="Year list/range, e.g. 2001 or 2001-2026 or all")
    parser.add_argument("--sleep", type=float, default=0.5, help="Delay between pbpstats.com API requests")
    parser.add_argument("--force", action="store_true", help="Refetch and replace rows for selected years")
    parser.add_argument("--limit-games", type=int, default=None, help="Debug: limit number of local games")
    parser.add_argument("--missing-only", action="store_true", help="Only fetch/apply player-game rows that are not already verified")
    parser.add_argument("--apply", action="store_true", help="Apply generated ingredients to data-package.json, data/data-package.json, and index.html")
    parser.add_argument("--apply-only", action="store_true", help="Skip fetching; only apply existing CSV")
    args = parser.parse_args()

    data = json.loads(DATA_PACKAGE.read_text())
    years = parse_years(args.years)
    if not args.apply_only:
        write_ingredients_csv(data, years=years, force=args.force, sleep=args.sleep, limit_games=args.limit_games, missing_only=args.missing_only)
    if args.apply or args.apply_only:
        data = json.loads(DATA_PACKAGE.read_text())
        data = apply_ingredients(data)
        write_data_package(data)
        print("Applied verified pbpstats.com API AdjTS to data-package.json, data/data-package.json, and index.html.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
