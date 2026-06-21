#!/usr/bin/env python3
"""
Build verified player-game adjusted true shooting ingredients with pbpstats.

Why this exists:
Gabriel1200's player game rows contain the box-score pieces (PTS/FGA/FTA/TOV),
but not every adjusted true shooting ingredient at the player-game level. This
script uses pbpstats' enhanced play-by-play parser to get the missing ingredients.

Outputs:
  data/player_game_adjts_ingredients.csv
  data-package.json + data/data-package.json + embedded index.html when --apply is used

Definition used by Playoff Translation Lab:
  Scoring TOV = total TOV - bad-pass TOV - bad-pass-out-of-bounds TOV
  AdjFGA = FGA + scoring TOV - heave attempts - Z Bounds
  AdjFTA = FTA - technical FTA
  AdjTS% = PTS / (2 * (AdjFGA + 0.44 * AdjFTA))

Notes:
- This no longer calls stats.nba.com/playbyplayv3 directly.
- It uses the pbpstats Python package, which normalizes play-by-play events and
  exposes bad-pass turnovers, bad-pass out-of-bounds turnovers, heaves, technical
  free throws, and self offensive rebounds/Z Bounds in a much cleaner way.
- pbpstats itself may fetch underlying raw PBP from data.nba.com. That is okay;
  the important change is that this script is no longer hand-parsing raw NBA.com
  play-by-play text.
"""

from __future__ import annotations

import argparse
import csv
import importlib
import json
import math
import os
import re
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent
DATA_PACKAGE = ROOT / "data-package.json"
DATA_COPY = ROOT / "data" / "data-package.json"
INDEX_FILE = ROOT / "index.html"
OUT_CSV = ROOT / "data" / "player_game_adjts_ingredients.csv"
CACHE_DIR = ROOT / "data" / "pbpstats_cache"


NBA_WEB_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
    "Referer": "https://www.nba.com/",
    "Origin": "https://www.nba.com",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
}

_REQUESTS_PATCHED = False


def patch_requests_for_nba_hosts() -> None:
    """Make pbpstats' underlying requests look like normal browser NBA requests.

    Codespaces often gets 403 responses from data.nba.com when Python requests uses
    its default user-agent. pbpstats is still doing the parsing, but this patch adds
    the headers needed for its data.nba.com schedule/PBP fetches.
    """
    global _REQUESTS_PATCHED
    if _REQUESTS_PATCHED:
        return
    try:
        import requests  # type: ignore
    except Exception:
        return

    original_request = requests.sessions.Session.request

    def patched_request(self, method, url, **kwargs):  # type: ignore[no-untyped-def]
        url_text = str(url)
        if "data.nba.com" in url_text or "stats.nba.com" in url_text or "nba.com" in url_text:
            existing = kwargs.pop("headers", None) or {}
            headers = dict(NBA_WEB_HEADERS)
            headers.update(existing)
            kwargs["headers"] = headers
        return original_request(self, method, url, **kwargs)

    requests.sessions.Session.request = patched_request
    _REQUESTS_PATCHED = True

TEAM_ALIASES = {
    "BRK": "BKN",
    "BKN": "BKN",
    "PHO": "PHX",
    "PHX": "PHX",
    "CHO": "CHA",
    "CHA": "CHA",
    "NOH": "NOP",
    "NOK": "NOP",
    "NOR": "NOP",
    "NOP": "NOP",
    "GS": "GSW",
    "GSW": "GSW",
    "SA": "SAS",
    "SAS": "SAS",
    "NY": "NYK",
    "NYK": "NYK",
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


def normalize_team(team: Any) -> str:
    text = str(team or "").strip().upper()
    return TEAM_ALIASES.get(text, text)


def normalize_nba_game_id(value: Any) -> str:
    """Return a 10-digit NBA game id only for real all-digit game ids."""
    text = str(value or "").strip()
    if not re.fullmatch(r"\d{7,10}", text):
        return ""
    return text.zfill(10)


def local_game_key(value: Any) -> str:
    """Stable key for matching the site's row game ids to the ingredients CSV."""
    real_id = normalize_nba_game_id(value)
    if real_id:
        return real_id
    return str(value or "").strip()


def parse_generated_game_id(value: Any) -> Optional[Dict[str, str]]:
    """Parse IDs like gen_2020_20200817_BKN_TOR."""
    text = str(value or "")
    match = re.search(r"gen_(\d{4})_(\d{8})_([A-Za-z]{2,4})_([A-Za-z]{2,4})", text)
    if not match:
        return None
    return {
        "year": match.group(1),
        "date": match.group(2),
        "team1": normalize_team(match.group(3)),
        "team2": normalize_team(match.group(4)),
    }


def playoff_year_to_season_label(year: int) -> str:
    """2020 playoff year -> 2019-20 pbpstats season label."""
    start = year - 1
    return f"{start}-{str(year)[-2:]}"



def nba_stats_result_sets(payload: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """Parse NBA Stats resultSets into list-of-dicts by resultSet name."""
    result_sets = payload.get("resultSets") or payload.get("resultSet") or []
    if isinstance(result_sets, dict):
        result_sets = [result_sets]
    out: Dict[str, List[Dict[str, Any]]] = {}
    for item in result_sets or []:
        name = item.get("name") or item.get("resultSetName") or item.get("Name")
        headers = item.get("headers") or item.get("Headers") or []
        rows = item.get("rowSet") or item.get("RowSet") or []
        if name and headers:
            out[str(name)] = [dict(zip(headers, row)) for row in rows]
    return out


def nba_date_for_scoreboard(yyyymmdd: str) -> str:
    """YYYYMMDD -> MM/DD/YYYY for stats.nba.com scoreboardv2."""
    text = str(yyyymmdd)
    return f"{text[4:6]}/{text[6:8]}/{text[0:4]}"

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


def ensure_pbpstats(auto_install: bool = True) -> Any:
    """Import pbpstats, optionally installing it in Codespaces if missing."""
    try:
        return importlib.import_module("pbpstats")
    except ImportError:
        if not auto_install:
            raise SystemExit("Missing dependency: run `python3 -m pip install pbpstats` first.")
        print("pbpstats is not installed. Installing it now...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pbpstats"])
        return importlib.import_module("pbpstats")


def ensure_cache_dirs() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    (CACHE_DIR / "pbp").mkdir(parents=True, exist_ok=True)
    (CACHE_DIR / "schedule").mkdir(parents=True, exist_ok=True)


def get_bool_attr(obj: Any, attr: str) -> bool:
    try:
        value = getattr(obj, attr)
        if callable(value):
            value = value()
        return bool(value)
    except Exception:
        return False


def get_player_id(obj: Any, attr: str = "player1_id") -> str:
    try:
        value = getattr(obj, attr, None)
    except Exception:
        value = None
    digits = re.sub(r"\D", "", str(value or ""))
    return digits


class PbpStatsFetcher:
    def __init__(self, auto_install: bool = True):
        ensure_cache_dirs()
        self.pbpstats = ensure_pbpstats(auto_install=auto_install)
        patch_requests_for_nba_hosts()
        from pbpstats.client import Client

        self.Client = Client
        self._pbp_client = Client(
            {
                "dir": str(CACHE_DIR),
                "EnhancedPbp": {"source": "web", "data_provider": "data_nba"},
            }
        )
        self._schedule_client = Client(
            {
                "dir": str(CACHE_DIR),
                "Games": {"source": "web", "data_provider": "data_nba"},
            }
        )
        self._schedule_maps: Dict[int, Dict[Tuple[str, str, str], str]] = {}
        self._scoreboard_date_maps: Dict[str, Dict[Tuple[str, str, str], str]] = {}
        self._candidate_year_maps: Dict[int, Dict[Tuple[str, str, str], str]] = {}


    def possible_playoff_game_ids(self, playoff_year: int) -> List[str]:
        """Generate likely NBA playoff game ids for a playoff year.

        NBA playoff ids follow this pattern for this era:
          004 + season_start_YY + 00 + round + series + game
        Example: 2020 Finals Game 6 = 0041900406.
        This lets us avoid the blocked full-season schedule endpoint when the site
        only has generated local ids such as gen_2001_20010615_LAL_PHI.
        """
        season_code = (int(playoff_year) - 1) % 100
        ids: List[str] = []
        for round_no, series_count in ((1, 8), (2, 4), (3, 2), (4, 1)):
            for series_no in range(1, series_count + 1):
                series_digit = 0 if round_no == 4 else series_no
                for game_no in range(1, 8):
                    ids.append(f"004{season_code:02d}00{round_no}{series_digit}{game_no}")
        return ids

    def direct_data_nba_game_metadata(self, nba_game_id: str, playoff_year: int) -> Optional[Tuple[str, str, str]]:
        """Fetch tiny metadata from data.nba individual PBP JSON.

        This does NOT use the full data.nba season schedule endpoint, which is the
        endpoint returning 403s in Codespaces. Individual PBP URLs usually work
        after the browser-header patch and are enough to learn date/away/home.
        """
        ensure_cache_dirs()
        gid = normalize_nba_game_id(nba_game_id)
        if not gid:
            return None
        cache_file = CACHE_DIR / "schedule" / f"direct_meta_{gid}.json"
        try:
            if cache_file.exists():
                payload = json.loads(cache_file.read_text())
            else:
                import requests  # type: ignore
                season_start = int(playoff_year) - 1
                # data.nba individual PBP files normally live under /data/10s/v2015/.
                # The previous direct resolver used /data/v2015/ only, which returns
                # no metadata for older seasons and made the map find 0 games.
                urls = [
                    f"https://data.nba.com/data/10s/v2015/json/mobile_teams/nba/{season_start}/scores/pbp/{gid}_full_pbp.json",
                    f"https://data.nba.com/data/v2015/json/mobile_teams/nba/{season_start}/scores/pbp/{gid}_full_pbp.json",
                ]
                payload = None
                for url in urls:
                    response = requests.get(url, headers=NBA_WEB_HEADERS, timeout=20)
                    if response.status_code in {400, 404, 403}:
                        continue
                    response.raise_for_status()
                    payload = response.json()
                    cache_file.write_text(json.dumps(payload))
                    break
                if payload is None:
                    return None
        except Exception:
            return None

        g = payload.get("g") or payload.get("game") or payload
        if not isinstance(g, dict):
            return None

        # Most data.nba PBP files use gcode like 20201011/LALMIA.
        date_text = ""
        for key in ("gdte", "gdtutc", "date", "gamedate"):
            val = str(g.get(key) or "").strip()
            m = re.search(r"(\d{4})[-/]?(\d{2})[-/]?(\d{2})", val)
            if m:
                date_text = f"{m.group(1)}{m.group(2)}{m.group(3)}"
                break
        if not date_text:
            gcode = str(g.get("gcode") or g.get("gameCode") or "")
            m = re.search(r"(\d{8})", gcode)
            if m:
                date_text = m.group(1)

        v = g.get("v") or g.get("visitor") or {}
        h = g.get("h") or g.get("home") or {}
        away = normalize_team(v.get("ta") or v.get("abbrev") or v.get("teamAbbreviation") or g.get("vta")) if isinstance(v, dict) else ""
        home = normalize_team(h.get("ta") or h.get("abbrev") or h.get("teamAbbreviation") or g.get("hta")) if isinstance(h, dict) else ""

        if not date_text or not away or not home:
            # Last resort: parse the team pair from gcode suffix like 20201011/LALMIA.
            gcode = str(g.get("gcode") or g.get("gameCode") or "")
            m = re.search(r"\d{8}/([A-Z]{3})([A-Z]{3})", gcode.upper())
            if m:
                away = normalize_team(m.group(1))
                home = normalize_team(m.group(2))
        if date_text and away and home:
            return date_text, away, home
        return None

    def candidate_map_for_year(self, playoff_year: int) -> Dict[Tuple[str, str, str], str]:
        """Build date/team -> NBA game id map by probing likely playoff ids.

        This is the fallback that avoids both problematic endpoints:
        - stats.nba.com scoreboardv2 timeouts
        - data.nba.com full-season schedule 403s
        """
        playoff_year = int(playoff_year)
        if playoff_year in self._candidate_year_maps:
            return self._candidate_year_maps[playoff_year]

        mapping: Dict[Tuple[str, str, str], str] = {}
        unordered_seen: Dict[Tuple[str, str, str], List[str]] = defaultdict(list)
        checked = 0
        found = 0
        for gid in self.possible_playoff_game_ids(playoff_year):
            checked += 1
            meta = self.direct_data_nba_game_metadata(gid, playoff_year)
            if not meta:
                continue
            date_text, away, home = meta
            mapping[(date_text, away, home)] = gid
            pair = tuple(sorted([away, home]))
            unordered_seen[(date_text, pair[0], pair[1])].append(gid)
            found += 1

        for key, gids in unordered_seen.items():
            if len(set(gids)) == 1:
                mapping[key] = gids[0]

        print(f"Built direct playoff-id map for {playoff_year}: found {found} games from {checked} candidates")
        self._candidate_year_maps[playoff_year] = mapping
        return mapping

    def resolve_from_candidate_map(self, parsed: Dict[str, str]) -> Optional[str]:
        year = int(parsed["year"])
        date_text = parsed["date"]
        team1 = parsed["team1"]
        team2 = parsed["team2"]
        mapping = self.candidate_map_for_year(year)
        exact = mapping.get((date_text, team1, team2)) or mapping.get((date_text, team2, team1))
        if exact:
            return exact
        pair = tuple(sorted([team1, team2]))
        return mapping.get((date_text, pair[0], pair[1]))

    def scoreboard_map_for_date(self, date_text: str) -> Dict[Tuple[str, str, str], str]:
        """Resolve real NBA game IDs from stats.nba.com scoreboardv2 for a single date.

        This is the preferred resolver for generated IDs because it avoids fetching the
        full data.nba.com season schedule, which is the endpoint that often 403s in
        Codespaces for older seasons.
        """
        date_text = str(date_text)
        if date_text in self._scoreboard_date_maps:
            return self._scoreboard_date_maps[date_text]
        ensure_cache_dirs()
        cache_file = CACHE_DIR / "schedule" / f"scoreboardv2_{date_text}.json"
        if cache_file.exists():
            payload = json.loads(cache_file.read_text())
        else:
            import requests  # type: ignore
            url = "https://stats.nba.com/stats/scoreboardv2"
            params = {"GameDate": nba_date_for_scoreboard(date_text), "LeagueID": "00", "DayOffset": "0"}
            response = requests.get(url, params=params, headers=NBA_WEB_HEADERS, timeout=30)
            response.raise_for_status()
            payload = response.json()
            cache_file.write_text(json.dumps(payload))
        sets = nba_stats_result_sets(payload)
        game_headers = sets.get("GameHeader") or sets.get("GameHeaderStats") or []
        line_score = sets.get("LineScore") or sets.get("LineScoreStats") or []

        team_by_game: Dict[str, Dict[str, str]] = defaultdict(dict)
        team_id_to_abbr: Dict[str, str] = {}
        for row in line_score:
            gid = normalize_nba_game_id(row.get("GAME_ID"))
            team_id = str(row.get("TEAM_ID") or "")
            abbr = normalize_team(row.get("TEAM_ABBREVIATION") or row.get("TEAM_ABBR"))
            if gid and team_id and abbr:
                team_by_game[gid][team_id] = abbr
                team_id_to_abbr[team_id] = abbr

        mapping: Dict[Tuple[str, str, str], str] = {}
        unordered_seen: Dict[Tuple[str, str, str], List[str]] = defaultdict(list)
        for row in game_headers:
            gid = normalize_nba_game_id(row.get("GAME_ID"))
            if not gid:
                continue
            home_id = str(row.get("HOME_TEAM_ID") or "")
            away_id = str(row.get("VISITOR_TEAM_ID") or row.get("AWAY_TEAM_ID") or "")
            home = normalize_team(team_by_game.get(gid, {}).get(home_id) or team_id_to_abbr.get(home_id))
            away = normalize_team(team_by_game.get(gid, {}).get(away_id) or team_id_to_abbr.get(away_id))
            if not home or not away:
                # Last resort: if LineScore has exactly two teams for this game, use unordered only.
                teams = sorted(set(team_by_game.get(gid, {}).values()))
                if len(teams) == 2:
                    pair = tuple(sorted([normalize_team(teams[0]), normalize_team(teams[1])]))
                    unordered_seen[(date_text, pair[0], pair[1])].append(gid)
                continue
            mapping[(date_text, away, home)] = gid
            pair = tuple(sorted([away, home]))
            unordered_seen[(date_text, pair[0], pair[1])].append(gid)

        for key, gids in unordered_seen.items():
            if len(set(gids)) == 1:
                mapping[key] = gids[0]

        self._scoreboard_date_maps[date_text] = mapping
        return mapping

    def resolve_from_scoreboard(self, parsed: Dict[str, str]) -> Optional[str]:
        date_text = parsed["date"]
        team1 = parsed["team1"]
        team2 = parsed["team2"]
        mapping = self.scoreboard_map_for_date(date_text)
        exact = mapping.get((date_text, team1, team2)) or mapping.get((date_text, team2, team1))
        if exact:
            return exact
        pair = tuple(sorted([team1, team2]))
        return mapping.get((date_text, pair[0], pair[1]))

    def schedule_map_for_year(self, playoff_year: int) -> Dict[Tuple[str, str, str], str]:
        if playoff_year in self._schedule_maps:
            return self._schedule_maps[playoff_year]
        season_label = playoff_year_to_season_label(playoff_year)
        season = self._schedule_client.Season("nba", season_label, "Playoffs")
        schedule: Dict[Tuple[str, str, str], str] = {}
        unordered_seen: Dict[Tuple[str, str, str], List[str]] = defaultdict(list)

        for game in season.games.data:
            gid = normalize_nba_game_id(game.get("game_id"))
            date_text = str(game.get("date") or "").replace("-", "")[:8]
            away = normalize_team(game.get("away_team_abbreviation"))
            home = normalize_team(game.get("home_team_abbreviation"))
            if not gid or not date_text or not away or not home:
                continue
            schedule[(date_text, away, home)] = gid
            pair = tuple(sorted([away, home]))
            unordered_seen[(date_text, pair[0], pair[1])].append(gid)

        # Add unordered keys only when unique for that date/team pair.
        for key, gids in unordered_seen.items():
            if len(set(gids)) == 1:
                schedule[key] = gids[0]

        self._schedule_maps[playoff_year] = schedule
        return schedule

    def resolve_nba_game_id(self, local_id: Any, sample_row: Optional[Dict[str, Any]] = None) -> Optional[str]:
        real_id = normalize_nba_game_id(local_id)
        if real_id:
            return real_id

        parsed = parse_generated_game_id(local_id)
        if not parsed and sample_row:
            # Last-resort fallback if a row has separate date/team fields later.
            return None
        if not parsed:
            return None

        # First try direct candidate probing. This avoids both endpoints that get
        # blocked/time out in Codespaces for old generated ids: scoreboardv2 and the
        # full data.nba season schedule.
        candidate_error: Optional[Exception] = None
        try:
            resolved = self.resolve_from_candidate_map(parsed)
            if resolved:
                return resolved
        except Exception as exc:  # noqa: BLE001
            candidate_error = exc

        # Then try stats.nba.com scoreboardv2 by date.
        scoreboard_error: Optional[Exception] = None
        try:
            resolved = self.resolve_from_scoreboard(parsed)
            if resolved:
                return resolved
        except Exception as exc:  # noqa: BLE001
            scoreboard_error = exc

        # Final fallback to pbpstats season schedule only if both direct candidates
        # and scoreboard lookup fail.
        year = int(parsed["year"])
        try:
            schedule = self.schedule_map_for_year(year)
            date_text = parsed["date"]
            team1 = parsed["team1"]
            team2 = parsed["team2"]
            exact = schedule.get((date_text, team1, team2)) or schedule.get((date_text, team2, team1))
            if exact:
                return exact
            pair = tuple(sorted([team1, team2]))
            return schedule.get((date_text, pair[0], pair[1]))
        except Exception as schedule_error:  # noqa: BLE001
            parts = []
            if candidate_error:
                parts.append(f"direct candidate probe failed: {candidate_error}")
            if scoreboard_error:
                parts.append(f"scoreboardv2 failed: {scoreboard_error}")
            parts.append(f"data.nba schedule failed: {schedule_error}")
            raise RuntimeError("; ".join(parts))

    def fetch_enhanced_pbp(self, nba_game_id: str, sleep: float = 0.0) -> Any:
        game = self._pbp_client.Game(nba_game_id)
        if sleep:
            time.sleep(sleep)
        return game.enhanced_pbp


def parse_pbpstats_ingredients(enhanced_pbp: Any) -> Dict[str, Dict[str, float]]:
    """Return ingredients keyed by NBA person/player id for one game."""
    stats: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))

    for turnover in getattr(enhanced_pbp, "turnovers", []):
        pid = get_player_id(turnover)
        if not pid:
            continue
        if get_bool_attr(turnover, "is_bad_pass_out_of_bounds"):
            stats[pid]["BadPassOutOfBoundsTOV"] += 1
        elif get_bool_attr(turnover, "is_bad_pass"):
            stats[pid]["BadPassTOV"] += 1

    for shot in getattr(enhanced_pbp, "fgas", []):
        pid = get_player_id(shot)
        if pid and get_bool_attr(shot, "is_heave"):
            stats[pid]["Heaves"] += 1

    for rebound in getattr(enhanced_pbp, "rebounds", []):
        if not get_bool_attr(rebound, "is_real_rebound"):
            continue
        if not get_bool_attr(rebound, "oreb"):
            continue
        if not get_bool_attr(rebound, "self_reb"):
            continue
        pid = get_player_id(rebound)
        if not pid:
            try:
                missed = getattr(rebound, "missed_shot", None)
                pid = get_player_id(missed)
            except Exception:
                pid = ""
        if pid:
            stats[pid]["ZBounds"] += 1

    for free_throw in getattr(enhanced_pbp, "ftas", []):
        pid = get_player_id(free_throw)
        if pid and get_bool_attr(free_throw, "is_technical_ft"):
            stats[pid]["TechFTA"] += 1

    return {pid: dict(values) for pid, values in stats.items()}


def base_games_for_years(data: Dict[str, Any], years: Optional[Iterable[int]] = None) -> List[Dict[str, Any]]:
    year_set = set(years or [])
    rows = []
    for game in data.get("playerGames", []):
        year = safe_int(game.get("year"))
        if not year:
            continue
        if year_set and year not in year_set:
            continue
        if not local_game_key(game.get("gameId")):
            continue
        rows.append(game)
    return rows


def write_ingredients_csv(
    data: Dict[str, Any],
    years: Optional[List[int]],
    limit_games: Optional[int],
    force: bool,
    sleep: float,
    auto_install: bool,
) -> Path:
    games = base_games_for_years(data, years)
    by_game: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    raw_local_id: Dict[str, Any] = {}
    for row in games:
        key = local_game_key(row.get("gameId"))
        by_game[key].append(row)
        raw_local_id[key] = row.get("gameId")

    game_keys = sorted(by_game.keys())
    if limit_games:
        game_keys = game_keys[:limit_games]

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "gameId", "nbaGameId", "playerId", "nbaId", "playerName", "year", "team", "opponent",
        "PTS", "FGA", "FTA", "TOV",
        "BadPassTOV", "BadPassOutOfBoundsTOV", "ScoringTOV", "Heaves", "ZBounds", "TechFTA",
        "AdjFGA", "AdjFTA", "AdjTS%", "source",
    ]

    existing_rows: Dict[Tuple[str, str], Dict[str, Any]] = {}
    if OUT_CSV.exists() and not force:
        with OUT_CSV.open(newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                existing_rows[(local_game_key(row.get("gameId")), str(row.get("nbaId") or ""))] = row

    fetcher = PbpStatsFetcher(auto_install=auto_install)
    written = 0
    failed: List[str] = []
    skipped_unresolved: List[str] = []

    for idx, game_key in enumerate(game_keys, start=1):
        needs_game = force or any((game_key, str(g.get("nbaId") or "")) not in existing_rows for g in by_game[game_key])
        if not needs_game:
            continue

        local_id = raw_local_id.get(game_key, game_key)
        try:
            nba_game_id = fetcher.resolve_nba_game_id(local_id, by_game[game_key][0])
        except Exception as exc:  # noqa: BLE001
            print(f"[{idx}/{len(game_keys)}] failed to resolve {local_id}: {exc}")
            failed.append(str(local_id))
            continue

        if not nba_game_id:
            print(f"[{idx}/{len(game_keys)}] skipped {local_id}: could not resolve to real NBA game id")
            skipped_unresolved.append(str(local_id))
            continue

        try:
            enhanced_pbp = fetcher.fetch_enhanced_pbp(nba_game_id, sleep=sleep)
            ingredients = parse_pbpstats_ingredients(enhanced_pbp)
        except Exception as exc:  # noqa: BLE001
            print(f"[{idx}/{len(game_keys)}] failed {local_id} -> {nba_game_id}: {exc}")
            failed.append(f"{local_id}\t{nba_game_id}")
            continue

        for game in by_game[game_key]:
            nba_id = str(game.get("nbaId") or "")
            if not nba_id:
                continue
            vals = ingredients.get(nba_id, {})
            pts = safe_float(game.get("PTS"))
            fga = safe_float(game.get("FGA"))
            fta = safe_float(game.get("FTA"))
            tov = safe_float(game.get("TOV"))
            bad = safe_float(vals.get("BadPassTOV")) or 0.0
            bad_oob = safe_float(vals.get("BadPassOutOfBoundsTOV")) or 0.0
            heaves = safe_float(vals.get("Heaves")) or 0.0
            z_bounds = safe_float(vals.get("ZBounds")) or 0.0
            tech_fta = safe_float(vals.get("TechFTA")) or 0.0
            if pts is None or fga is None or fta is None or tov is None:
                continue
            scoring_tov = max(tov - bad - bad_oob, 0.0)
            adj_fga = max(fga + scoring_tov - heaves - z_bounds, 0.0)
            adj_fta = max(fta - tech_fta, 0.0)
            adj_ts = None
            denom = 2 * (adj_fga + 0.44 * adj_fta)
            if denom > 0:
                adj_ts = 100 * pts / denom
            existing_rows[(game_key, nba_id)] = {
                "gameId": game_key,
                "nbaGameId": nba_game_id,
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
                "source": "pbpstats enhanced PBP reconstruction",
            }
            written += 1
        print(f"[{idx}/{len(game_keys)}] {local_id} -> {nba_game_id}: rebuilt {len(by_game[game_key])} player rows")

    with OUT_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for key in sorted(existing_rows.keys()):
            row = existing_rows[key]
            writer.writerow({name: row.get(name, "") for name in fieldnames})

    print(
        f"Wrote {OUT_CSV} with {len(existing_rows):,} rows. "
        f"Newly rebuilt rows: {written:,}. Failed games: {len(failed)}. Unresolved generated games: {len(skipped_unresolved)}"
    )
    if failed:
        (OUT_CSV.parent / "player_game_adjts_failed_games.txt").write_text("\n".join(failed))
    if skipped_unresolved:
        (OUT_CSV.parent / "player_game_adjts_unresolved_games.txt").write_text("\n".join(skipped_unresolved))
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
    if denom <= 0:
        return None
    return 100 * points / denom


def apply_ingredients(data: Dict[str, Any], ingredients_csv: Path = OUT_CSV) -> Dict[str, Any]:
    if not ingredients_csv.exists():
        raise FileNotFoundError(f"Missing {ingredients_csv}. Run the fetch step first.")
    lookup: Dict[Tuple[str, str], Dict[str, Any]] = {}
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
        game["AdjTS_source"] = "verified game-level pbpstats enhanced PBP reconstruction"
        game["nbaGameId"] = row.get("nbaGameId") or game.get("nbaGameId")
        game["AdjFGA"] = round_value(safe_float(row.get("AdjFGA")), 1)
        game["AdjFTA"] = round_value(safe_float(row.get("AdjFTA")), 1)
        game["ScoringTOV"] = round_value(safe_float(row.get("ScoringTOV")), 1)
        game["BadPassTOV"] = round_value(safe_float(row.get("BadPassTOV")), 1)
        game["BadPassOutOfBoundsTOV"] = round_value(safe_float(row.get("BadPassOutOfBoundsTOV")), 1)
        game["Heaves"] = round_value(safe_float(row.get("Heaves")), 1)
        game["ZBounds"] = round_value(safe_float(row.get("ZBounds")), 1)
        game["TechFTA"] = round_value(safe_float(row.get("TechFTA")), 1)
        allowed = safe_float(game.get("OppRSAdjTSAllowed"))
        game["rAdjTS"] = round_value(adj_ts - allowed, 1) if allowed is not None else None
        updated_games += 1

    # Rebuild series AdjTS from verified game rows only when every row in that series is verified.
    series_groups: Dict[Tuple[str, int, str, str, str], List[Dict[str, Any]]] = defaultdict(list)
    for game in data.get("playerGames", []):
        key = (
            str(game.get("playerId") or ""),
            safe_int(game.get("year")) or 0,
            str(game.get("team") or ""),
            str(game.get("opponent") or ""),
            str(game.get("seriesCode") or ""),
        )
        series_groups[key].append(game)

    by_series_id = {s.get("seriesId"): s for s in data.get("playerSeries", [])}
    updated_series = 0
    for _key, rows in series_groups.items():
        if not rows:
            continue
        first = rows[0]
        sid = f"{first.get('playerId')}_{first.get('year')}_{first.get('seriesCode')}_{first.get('opponent')}"
        series = by_series_id.get(sid)
        if not series:
            continue
        verified = [
            r
            for r in rows
            if str(r.get("AdjTS_source") or "").startswith("verified game-level") and r.get("AdjTS%") is not None
        ]
        if len(verified) != len(rows):
            series["AdjTS%"] = None
            series["rAdjTS"] = None
            series["AdjTS_source"] = "unavailable: not every game in series has verified PBP AdjTS ingredients"
            continue
        pts = sum(safe_float(r.get("PTS")) or 0 for r in rows)
        adj_fga = sum(safe_float(r.get("AdjFGA")) or 0 for r in rows)
        adj_fta = sum(safe_float(r.get("AdjFTA")) or 0 for r in rows)
        adj_ts = ts_from_totals(pts, adj_fga, adj_fta)
        series["AdjTS%"] = round_value(adj_ts, 1)
        series["AdjTS_source"] = "verified series aggregation of game-level pbpstats AdjTS"
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

    metadata = data.setdefault("metadata", {})
    counts = metadata.setdefault("counts", {})
    counts["verifiedGameAdjTSRows"] = updated_games
    counts["verifiedSeriesAdjTSRows"] = updated_series
    notes = metadata.setdefault("notes", [])
    note = "Game/series AdjTS is populated only where build_adjts_from_pbp.py reconstructed bad-pass turnovers, heaves, Z Bounds, and technical FTA from pbpstats enhanced PBP."
    if note not in notes:
        notes.append(note)
    return data


def embed_data_in_index(data: Dict[str, Any]) -> None:
    if not INDEX_FILE.exists():
        return
    html = INDEX_FILE.read_text()
    payload = json.dumps(data, separators=(",", ":"))
    start_marker = '<script type="application/json" id="ptl-data">'
    end_marker = "</script>"
    start = html.find(start_marker)
    if start == -1:
        return
    content_start = start + len(start_marker)
    end = html.find(end_marker, content_start)
    if end == -1:
        return
    html = html[:content_start] + "\n" + payload + "\n" + html[end:]
    INDEX_FILE.write_text(html)


def write_data_package(data: Dict[str, Any]) -> None:
    DATA_PACKAGE.write_text(json.dumps(data, indent=2))
    DATA_COPY.parent.mkdir(parents=True, exist_ok=True)
    DATA_COPY.write_text(json.dumps(data, indent=2))
    embed_data_in_index(data)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build/apply verified game-level AdjTS ingredients from pbpstats enhanced PBP.")
    parser.add_argument("--years", default="2025", help="Year list/range, e.g. 2025 or 2001-2026 or all. Default: 2025")
    parser.add_argument("--limit-games", type=int, default=None, help="Debug limit for number of games to fetch.")
    parser.add_argument("--sleep", type=float, default=0.25, help="Delay between game requests.")
    parser.add_argument("--force", action="store_true", help="Refetch/rebuild matching ingredients and overwrite matching rows.")
    parser.add_argument("--apply", action="store_true", help="Apply generated ingredients to data-package.json and embedded index.html.")
    parser.add_argument("--apply-only", action="store_true", help="Skip fetching and only apply existing data/player_game_adjts_ingredients.csv.")
    parser.add_argument("--no-auto-install", action="store_true", help="Do not auto-install pbpstats when missing.")
    args = parser.parse_args()

    data = json.loads(DATA_PACKAGE.read_text())
    years = parse_years(args.years)
    if not args.apply_only:
        write_ingredients_csv(
            data,
            years=years,
            limit_games=args.limit_games,
            force=args.force,
            sleep=args.sleep,
            auto_install=not args.no_auto_install,
        )
    if args.apply or args.apply_only:
        data = apply_ingredients(data)
        write_data_package(data)
        print("Applied verified game/series AdjTS to data-package.json, data/data-package.json, and index.html.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
