#!/usr/bin/env python3
"""Build validated PBPStats playoff on-court data for the V2 site.

This pipeline intentionally separates true player-ON team context from the
existing whole-team game context fields in v2/data/players/*.json.

Primary source:
  https://api.pbpstats.com/get-wowy-stats/nba

Important behavior:
  PBPStats ignores GameId on several WOWY endpoints. Game-level requests must
  use FromDate/ToDate and must be validated against player game logs before
  they are trusted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import requests


BASE = "https://api.pbpstats.com"
ROOT = Path(".")
PLAYERS_DIR = ROOT / "v2" / "data" / "players"
OUT_ROOT = ROOT / "public" / "data" / "pbpstats" / "on_court_pipeline"
CACHE_DIR = OUT_ROOT / "cache"
RAW_CACHE_DIR = CACHE_DIR / "api"

TEAM_IDS = {
    "ATL": "1610612737",
    "BOS": "1610612738",
    "BKN": "1610612751",
    "BRK": "1610612751",
    "CHA": "1610612766",
    "CHH": "1610612766",
    "CHI": "1610612741",
    "CLE": "1610612739",
    "DAL": "1610612742",
    "DEN": "1610612743",
    "DET": "1610612765",
    "GSW": "1610612744",
    "HOU": "1610612745",
    "IND": "1610612754",
    "LAC": "1610612746",
    "LAL": "1610612747",
    "MEM": "1610612763",
    "MIA": "1610612748",
    "MIL": "1610612749",
    "MIN": "1610612750",
    "NJN": "1610612751",
    "NOH": "1610612740",
    "NOP": "1610612740",
    "NYK": "1610612752",
    "OKC": "1610612760",
    "ORL": "1610612753",
    "PHI": "1610612755",
    "PHX": "1610612756",
    "POR": "1610612757",
    "SAC": "1610612758",
    "SAS": "1610612759",
    "SEA": "1610612760",
    "TOR": "1610612761",
    "UTA": "1610612762",
    "VAN": "1610612763",
    "WAS": "1610612764",
}

SHOT_ZONES = [
    ("Rim", "AtRim"),
    ("ShortMid", "ShortMidRange"),
    ("LongMid", "LongMidRange"),
    ("Corner3", "Corner3"),
    ("AboveBreak3", "Arc3"),
]


@dataclass(frozen=True)
class PlayerGame:
    slug: str
    source_file: Path
    game_row_id: str
    player_id: str
    player_name: str
    year: int
    season: str
    date: str
    nba_game_id: str
    team: str
    opponent: str
    series_code: str
    round_label: str
    repo_minutes: Optional[float]
    repo_poss: Optional[float]


def season_string(playoff_year: int) -> str:
    return f"{playoff_year - 1}-{str(playoff_year)[-2:]}"


def safe_float(value: Any) -> Optional[float]:
    if value in (None, "", "-", "\u2014", "nan", "NaN"):
        return None
    if isinstance(value, (int, float)):
        if math.isnan(float(value)) or math.isinf(float(value)):
            return None
        return float(value)
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    if re.match(r"^\d+:\d\d$", text):
        minutes, seconds = text.split(":")
        return float(minutes) + float(seconds) / 60.0
    try:
        number = float(text)
    except ValueError:
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def minutes_to_seconds(value: Any) -> Optional[float]:
    if value in (None, "", "-", "\u2014"):
        return None
    if isinstance(value, str) and re.match(r"^\d+:\d\d$", value.strip()):
        minutes, seconds = value.strip().split(":")
        return int(minutes) * 60 + int(seconds)
    number = safe_float(value)
    if number is None:
        return None
    return number * 60.0


def pct(value: Any) -> Optional[float]:
    number = safe_float(value)
    if number is None:
        return None
    return round(number * 100.0 if abs(number) <= 1.5 else number, 3)


def round_or_none(value: Optional[float], digits: int = 3) -> Optional[float]:
    if value is None:
        return None
    if math.isnan(value) or math.isinf(value):
        return None
    return round(value, digits)


def clean_id(value: Any) -> str:
    text = str(value or "").strip()
    if "_" in text:
        tail = text.split("_")[-1]
        if tail.isdigit():
            return tail
    digits = re.findall(r"\d+", text)
    return digits[-1] if digits else ""


def norm_team(value: Any) -> str:
    team = str(value or "").strip().upper()
    aliases = {
        "PHO": "PHX",
        "BRK": "BKN",
        "NJN": "BKN",
        "NOH": "NOP",
        "NOK": "NOP",
        "CHH": "CHA",
        "CHO": "CHA",
        "SEA": "OKC",
        "VAN": "MEM",
    }
    return aliases.get(team, team)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8", errors="ignore"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


class PBPStatsClient:
    def __init__(self, sleep: float = 0.35, force: bool = False, timeout: int = 45) -> None:
        self.sleep = sleep
        self.force = force
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "playoff-translation-lab-oncourt-pipeline/1.0",
                "Accept": "application/json,text/plain,*/*",
            }
        )

    def cache_path(self, path: str, params: Dict[str, Any]) -> Path:
        blob = json.dumps({"path": path, "params": params}, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha1(blob.encode("utf-8")).hexdigest()[:20]
        return RAW_CACHE_DIR / f"{path.strip('/').replace('/', '_')}__{digest}.json"

    def get(self, path: str, params: Dict[str, Any], retries: int = 6) -> Dict[str, Any]:
        cache_path = self.cache_path(path, params)
        if cache_path.exists() and not self.force:
            return read_json(cache_path)

        cache_path.parent.mkdir(parents=True, exist_ok=True)
        wait = self.sleep
        last_error: Dict[str, Any] = {}
        for attempt in range(1, retries + 1):
            try:
                response = self.session.get(BASE + path, params=params, timeout=self.timeout)
                if response.status_code == 200:
                    data = response.json()
                    write_json(cache_path, data)
                    time.sleep(self.sleep)
                    return data

                last_error = {
                    "_error": True,
                    "status_code": response.status_code,
                    "text": response.text[:1200],
                    "url": response.url,
                }
                if response.status_code not in {408, 429, 500, 502, 503, 504}:
                    break
            except Exception as exc:  # requests exceptions vary by environment
                last_error = {"_error": True, "exception": repr(exc), "path": path, "params": params}

            time.sleep(wait)
            wait = min(wait * 2, 20.0)

        write_json(cache_path, last_error)
        return last_error


def iter_player_games(years: Sequence[int], selectors: Sequence[str]) -> List[PlayerGame]:
    selector_set = {s.lower().strip() for s in selectors if s.strip()}
    out: List[PlayerGame] = []
    year_set = set(years)

    for path in sorted(PLAYERS_DIR.glob("*.json")):
        data = read_json(path)
        meta = data.get("meta", {}) if isinstance(data, dict) else {}
        slug = str(meta.get("slug") or path.stem)
        player_name = str(meta.get("name") or "")

        if selector_set:
            haystack = {slug.lower(), player_name.lower(), path.stem.lower()}
            ids = {clean_id(v) for v in meta.get("playerIds", []) if clean_id(v)}
            haystack.update(ids)
            if not selector_set.intersection(haystack):
                continue

        for row in data.get("games", []):
            if not isinstance(row, dict):
                continue
            year = int(safe_float(row.get("year")) or 0)
            if year not in year_set:
                continue
            player_id = clean_id(row.get("nbaId") or row.get("playerId"))
            date = str(row.get("date") or "").strip()
            team = norm_team(row.get("team"))
            opponent = norm_team(row.get("opponent"))
            if not player_id or not date or team not in TEAM_IDS:
                continue
            out.append(
                PlayerGame(
                    slug=slug,
                    source_file=path,
                    game_row_id=str(row.get("gameRowId") or ""),
                    player_id=player_id,
                    player_name=str(row.get("playerName") or player_name or slug),
                    year=year,
                    season=season_string(year),
                    date=date,
                    nba_game_id=str(row.get("nbaGameId") or "").strip(),
                    team=team,
                    opponent=opponent,
                    series_code=str(row.get("seriesCode") or ""),
                    round_label=str(row.get("round") or ""),
                    repo_minutes=safe_float(row.get("MIN")),
                    repo_poss=safe_float(row.get("POSS")),
                )
            )

    return out


def game_logs_for_player(client: PBPStatsClient, year: int, player_id: str) -> List[Dict[str, Any]]:
    params = {
        "Season": season_string(year),
        "SeasonType": "Playoffs",
        "EntityType": "Player",
        "EntityId": player_id,
    }
    obj = client.get("/get-game-logs/nba", params)
    rows = obj.get("multi_row_table_data") if isinstance(obj, dict) else []
    return rows if isinstance(rows, list) else []


def find_player_log(game: PlayerGame, logs: Sequence[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    for row in logs:
        if str(row.get("GameId") or "") == game.nba_game_id and game.nba_game_id:
            return row
    for row in logs:
        if (
            str(row.get("Date") or "") == game.date
            and norm_team(row.get("Team")) == game.team
            and norm_team(row.get("Opponent")) == game.opponent
        ):
            return row
    return None


def wowy_stats(
    client: PBPStatsClient,
    year: int,
    team: str,
    stat_type: str,
    player_id: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> Dict[str, Any]:
    params: Dict[str, Any] = {
        "Season": season_string(year),
        "SeasonType": "Playoffs",
        "TeamId": TEAM_IDS[team],
        "Type": stat_type,
    }
    if player_id:
        params["0Exactly1OnFloor"] = player_id
    if from_date:
        params["FromDate"] = from_date
    if to_date:
        params["ToDate"] = to_date
    obj = client.get("/get-wowy-stats/nba", params)
    row = obj.get("single_row_table_data") if isinstance(obj, dict) else None
    return row if isinstance(row, dict) else {}


def fga(row: Dict[str, Any]) -> Optional[float]:
    fg2a = safe_float(row.get("FG2A"))
    fg3a = safe_float(row.get("FG3A"))
    if fg2a is None and fg3a is None:
        return None
    return (fg2a or 0.0) + (fg3a or 0.0)


def made_fg(row: Dict[str, Any]) -> Optional[float]:
    fg2m = safe_float(row.get("FG2M"))
    fg3m = safe_float(row.get("FG3M"))
    if fg2m is None and fg3m is None:
        return None
    return (fg2m or 0.0) + (fg3m or 0.0)


def turnover_pct(row: Dict[str, Any]) -> Optional[float]:
    tov = safe_float(row.get("Turnovers"))
    poss = safe_float(row.get("OffPoss"))
    if tov is None or not poss:
        return None
    return 100.0 * tov / poss


def ftr(row: Dict[str, Any]) -> Optional[float]:
    attempts = fga(row)
    fta = safe_float(row.get("FTA"))
    if fta is None or not attempts:
        return None
    return 100.0 * fta / attempts


def normalize_wowy_row(row: Dict[str, Any], prefix: str, allowed: bool = False) -> Dict[str, Any]:
    suffix = "Allowed" if allowed else ""
    out: Dict[str, Any] = {}
    attempts = fga(row)
    makes = made_fg(row)

    out[f"{prefix}Points{suffix}"] = round_or_none(safe_float(row.get("Points")), 1)
    out[f"{prefix}OffPoss{suffix}"] = round_or_none(safe_float(row.get("OffPoss")), 1)
    out[f"{prefix}DefPoss{suffix}"] = round_or_none(safe_float(row.get("DefPoss")), 1)
    out[f"{prefix}Seconds{suffix}"] = round_or_none(safe_float(row.get("SecondsPlayed")), 1)
    out[f"{prefix}FGM{suffix}"] = round_or_none(makes, 1)
    out[f"{prefix}FGA{suffix}"] = round_or_none(attempts, 1)
    out[f"{prefix}FG3M{suffix}"] = round_or_none(safe_float(row.get("FG3M")), 1)
    out[f"{prefix}FG3A{suffix}"] = round_or_none(safe_float(row.get("FG3A")), 1)
    out[f"{prefix}FTA{suffix}"] = round_or_none(safe_float(row.get("FTA")), 1)
    out[f"{prefix}TOV{suffix}"] = round_or_none(safe_float(row.get("Turnovers")), 1)
    out[f"{prefix}ORB{suffix}"] = round_or_none(safe_float(row.get("OffRebounds")), 1)
    out[f"{prefix}DRB{suffix}"] = round_or_none(safe_float(row.get("DefRebounds")), 1)

    out[f"{prefix}TS{suffix}"] = pct(row.get("TsPct"))
    out[f"{prefix}EFG{suffix}"] = pct(row.get("EfgPct"))
    out[f"{prefix}TOVPct{suffix}"] = round_or_none(turnover_pct(row))
    out[f"{prefix}ORBPct{suffix}"] = pct(row.get("OffFGReboundPct"))
    out[f"{prefix}DRBPct{suffix}"] = pct(row.get("DefFGReboundPct"))
    out[f"{prefix}FTr{suffix}"] = round_or_none(ftr(row))
    out[f"{prefix}3PAr{suffix}"] = pct(row.get("FG3APct"))
    out[f"{prefix}SecondChancePointsPct{suffix}"] = pct(row.get("SecondChancePointsPct"))
    out[f"{prefix}SecondChanceTS{suffix}"] = pct(row.get("SecondChanceTsPct"))

    for out_name, api_name in SHOT_ZONES:
        out[f"{prefix}{out_name}Freq{suffix}"] = pct(row.get(f"{api_name}Frequency"))
        out[f"{prefix}{out_name}FGPct{suffix}"] = pct(row.get(f"{api_name}Accuracy"))
        out[f"{prefix}{out_name}FGA{suffix}"] = round_or_none(safe_float(row.get(f"{api_name}FGA")), 1)
        out[f"{prefix}{out_name}FGM{suffix}"] = round_or_none(safe_float(row.get(f"{api_name}FGM")), 1)

    return {k: v for k, v in out.items() if v is not None}


def add_rating_fields(out: Dict[str, Any], team_row: Dict[str, Any], opp_row: Dict[str, Any]) -> None:
    points = safe_float(team_row.get("Points"))
    off_poss = safe_float(team_row.get("OffPoss"))
    opp_points = safe_float(opp_row.get("Points"))
    def_poss = safe_float(team_row.get("DefPoss")) or safe_float(opp_row.get("OffPoss"))
    if points is not None and off_poss:
        out["onTeamORTG"] = round(100.0 * points / off_poss, 3)
    if opp_points is not None and def_poss:
        out["onTeamDRTG"] = round(100.0 * opp_points / def_poss, 3)
    if "onTeamORTG" in out and "onTeamDRTG" in out:
        out["onTeamNET"] = round(out["onTeamORTG"] - out["onTeamDRTG"], 3)


def validate_wowy(
    game: PlayerGame,
    team_row: Dict[str, Any],
    player_log: Optional[Dict[str, Any]],
    level: str,
    expected_seconds: Optional[float] = None,
    expected_off_poss: Optional[float] = None,
) -> Tuple[str, List[str]]:
    notes: List[str] = []
    seconds = safe_float(team_row.get("SecondsPlayed"))
    off_poss = safe_float(team_row.get("OffPoss"))

    if player_log:
        expected_seconds = minutes_to_seconds(player_log.get("Minutes")) or safe_float(player_log.get("SecondsPlayed"))
        expected_off_poss = safe_float(player_log.get("OffPoss"))
    if expected_seconds is None and game.repo_minutes is not None:
        expected_seconds = game.repo_minutes * 60.0
    if expected_off_poss is None:
        expected_off_poss = game.repo_poss

    if seconds is None or off_poss is None:
        return "invalid_empty_wowy_row", ["missing SecondsPlayed or OffPoss"]

    if expected_seconds is not None and abs(seconds - expected_seconds) > 90:
        notes.append(f"seconds mismatch returned={seconds} expected={expected_seconds}")
    if expected_off_poss is not None and abs(off_poss - expected_off_poss) > 2:
        notes.append(f"off poss mismatch returned={off_poss} expected={expected_off_poss}")

    if notes:
        return f"invalid_{level}_filter_mismatch", notes
    return "validated", notes


def build_context_row(
    game: PlayerGame,
    level: str,
    start_date: Optional[str],
    end_date: Optional[str],
    team_row: Dict[str, Any],
    opp_row: Dict[str, Any],
    baseline: Optional[Dict[str, Any]],
    validation_status: str,
    validation_notes: List[str],
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "playerId": game.player_id,
        "playerName": game.player_name,
        "year": game.year,
        "season": game.season,
        "team": game.team,
        "opponent": game.opponent,
        "contextLevel": level,
        "startDate": start_date,
        "endDate": end_date,
        "source": "pbpstats get-wowy-stats date-filtered",
        "validationStatus": validation_status,
    }
    if validation_notes:
        out["validationNotes"] = validation_notes
    if level == "game":
        out["date"] = game.date
        out["gameId"] = game.nba_game_id
        out["gameRowId"] = game.game_row_id
    else:
        out["seriesCode"] = game.series_code
        out["round"] = game.round_label

    out.update(normalize_wowy_row(team_row, "onTeam"))
    out.update(normalize_wowy_row(opp_row, "onOpp", allowed=True))
    if "onOppTOVPctAllowed" in out:
        out["onOppTOVForcedPct"] = out["onOppTOVPctAllowed"]
    if "onOppORBPctAllowed" in out:
        out["onOppORBAllowedPct"] = out["onOppORBPctAllowed"]
    if "onOppSecondChancePointsPctAllowed" in out:
        out["onOppSecondChanceAllowedPct"] = out["onOppSecondChancePointsPctAllowed"]
    add_rating_fields(out, team_row, opp_row)

    if baseline:
        out["opponentContextLevel"] = level
        out["opponentContextSource"] = "pbpstats opponent Type=Opponent date/range baseline"
        baseline_norm = normalize_wowy_row(baseline, "opp", allowed=True)
        out.update(baseline_norm)
        add_adjusted_fields(out)
    else:
        out["opponentContextLevel"] = None
        out["opponentContextSource"] = "unavailable"

    return out


def add_adjusted_fields(row: Dict[str, Any]) -> None:
    pairs = [
        ("onTeamTS", "oppTSAllowed", "onTeamTS_vs_OppAllowedTS"),
        ("onTeamTOVPct", "oppTOVPctAllowed", "onTeamTOV_vs_OppAllowedTOV"),
        ("onTeamORBPct", "oppORBPctAllowed", "onTeamORB_vs_OppAllowedORB"),
        ("onTeamEFG", "oppEFGAllowed", "onTeamEFG_vs_OppAllowedEFG"),
        ("onTeamFTr", "oppFTrAllowed", "onTeamFTr_vs_OppAllowedFTr"),
        ("onTeam3PAr", "opp3PArAllowed", "onTeam3PAr_vs_OppAllowed3PAr"),
    ]
    for zone, _api in SHOT_ZONES:
        pairs.append((f"onTeam{zone}Freq", f"opp{zone}FreqAllowed", f"onTeam{zone}Freq_vs_OppAllowed{zone}Freq"))
        pairs.append((f"onTeam{zone}FGPct", f"opp{zone}FGPctAllowed", f"onTeam{zone}FG_vs_OppAllowed{zone}FG"))

    for left, right, dest in pairs:
        a = safe_float(row.get(left))
        b = safe_float(row.get(right))
        if a is not None and b is not None:
            row[dest] = round(a - b, 3)


def endpoint_probe(client: PBPStatsClient) -> Dict[str, Any]:
    """Show which filters work on a known player/date.

    Kawhi Leonard, 2019-05-21, TOR-MIL is used because the expected on-court
    result is known to be a one-game row when FromDate/ToDate is supplied.
    """
    base = {
        "Season": "2018-19",
        "SeasonType": "Playoffs",
        "TeamId": TEAM_IDS["TOR"],
        "Type": "Team",
        "0Exactly1OnFloor": "202695",
    }
    tests = {
        "season_no_filter": {},
        "GameId": {"GameId": "0041800304"},
        "GameIds": {"GameIds": "0041800304"},
        "Date": {"Date": "2019-05-21"},
        "FromDate_ToDate": {"FromDate": "2019-05-21", "ToDate": "2019-05-21"},
    }
    results: Dict[str, Any] = {}
    for name, extra in tests.items():
        params = dict(base)
        params.update(extra)
        obj = client.get("/get-wowy-stats/nba", params)
        row = obj.get("single_row_table_data") if isinstance(obj, dict) else {}
        results[name] = {
            "minutes": row.get("Minutes") if isinstance(row, dict) else None,
            "seconds": row.get("SecondsPlayed") if isinstance(row, dict) else None,
            "offPoss": row.get("OffPoss") if isinstance(row, dict) else None,
            "ts": row.get("TsPct") if isinstance(row, dict) else None,
            "worksForGameLevel": bool(isinstance(row, dict) and safe_float(row.get("SecondsPlayed")) == 2046.0),
        }
    results["summary"] = {
        "GameIdIgnored": results["GameId"].get("seconds") == results["season_no_filter"].get("seconds"),
        "FromDateToDateWorks": results["FromDate_ToDate"].get("worksForGameLevel") is True,
    }
    return results


def baseline_allowed(
    client: PBPStatsClient,
    year: int,
    defending_team: str,
    from_date: Optional[str],
    to_date: Optional[str],
) -> Dict[str, Any]:
    if defending_team not in TEAM_IDS:
        return {}
    return wowy_stats(
        client,
        year=year,
        team=defending_team,
        stat_type="Opponent",
        player_id=None,
        from_date=from_date,
        to_date=to_date,
    )


def process_game_level(client: PBPStatsClient, games: Sequence[PlayerGame], limit: Optional[int]) -> Tuple[List[Dict[str, Any]], Dict[int, Dict[str, Any]]]:
    rows: List[Dict[str, Any]] = []
    coverage: Dict[int, Dict[str, Any]] = defaultdict(lambda: defaultdict(int))
    game_logs_cache: Dict[Tuple[int, str], List[Dict[str, Any]]] = {}

    for i, game in enumerate(games, 1):
        if limit and i > limit:
            break
        cov = coverage[game.year]
        cov["game_attempted"] += 1

        logs_key = (game.year, game.player_id)
        if logs_key not in game_logs_cache:
            game_logs_cache[logs_key] = game_logs_for_player(client, game.year, game.player_id)
        player_log = find_player_log(game, game_logs_cache[logs_key])

        team_row = wowy_stats(client, game.year, game.team, "Team", game.player_id, game.date, game.date)
        opp_row = wowy_stats(client, game.year, game.team, "Opponent", game.player_id, game.date, game.date)
        baseline = baseline_allowed(client, game.year, game.opponent, game.date, game.date)
        status, notes = validate_wowy(game, team_row, player_log, "game")

        if status == "validated":
            cov["game_validated"] += 1
        else:
            cov["game_invalid"] += 1

        rows.append(build_context_row(game, "game", game.date, game.date, team_row, opp_row, baseline, status, notes))

        if i % 25 == 0:
            print(f"game rows processed: {i}/{len(games)}", flush=True)

    return rows, coverage


def group_games_for_series(games: Sequence[PlayerGame]) -> List[List[PlayerGame]]:
    groups: Dict[Tuple[str, int, str, str, str, str], List[PlayerGame]] = defaultdict(list)
    for game in games:
        key = (game.player_id, game.year, game.team, game.opponent, game.series_code, game.slug)
        groups[key].append(game)
    return [sorted(v, key=lambda g: g.date) for v in groups.values()]


def process_series_level(client: PBPStatsClient, games: Sequence[PlayerGame], limit: Optional[int]) -> Tuple[List[Dict[str, Any]], Dict[int, Dict[str, Any]]]:
    rows: List[Dict[str, Any]] = []
    coverage: Dict[int, Dict[str, Any]] = defaultdict(lambda: defaultdict(int))
    groups = group_games_for_series(games)
    game_logs_cache: Dict[Tuple[int, str], List[Dict[str, Any]]] = {}

    for i, group in enumerate(groups, 1):
        if limit and i > limit:
            break
        first = group[0]
        start_date = group[0].date
        end_date = group[-1].date
        cov = coverage[first.year]
        cov["series_attempted"] += 1

        expected_seconds = 0.0
        expected_off_poss = 0.0
        found_logs = 0
        logs_key = (first.year, first.player_id)
        if logs_key not in game_logs_cache:
            game_logs_cache[logs_key] = game_logs_for_player(client, first.year, first.player_id)
        for game in group:
            log = find_player_log(game, game_logs_cache[logs_key])
            if not log:
                continue
            found_logs += 1
            expected_seconds += minutes_to_seconds(log.get("Minutes")) or 0.0
            expected_off_poss += safe_float(log.get("OffPoss")) or 0.0

        team_row = wowy_stats(client, first.year, first.team, "Team", first.player_id, start_date, end_date)
        opp_row = wowy_stats(client, first.year, first.team, "Opponent", first.player_id, start_date, end_date)
        baseline = baseline_allowed(client, first.year, first.opponent, start_date, end_date)
        status, notes = validate_wowy(
            first,
            team_row,
            None,
            "series",
            expected_seconds=expected_seconds if found_logs else None,
            expected_off_poss=expected_off_poss if found_logs else None,
        )
        if found_logs != len(group):
            notes.append(f"player game logs matched {found_logs}/{len(group)} games")

        if status == "validated":
            cov["series_validated"] += 1
        else:
            cov["series_invalid"] += 1
        rows.append(build_context_row(first, "series", start_date, end_date, team_row, opp_row, baseline, status, notes))

        if i % 25 == 0:
            print(f"series rows processed: {i}/{len(groups)}", flush=True)

    return rows, coverage


def group_games_for_season(games: Sequence[PlayerGame]) -> List[List[PlayerGame]]:
    groups: Dict[Tuple[str, int, str, str], List[PlayerGame]] = defaultdict(list)
    for game in games:
        key = (game.player_id, game.year, game.team, game.slug)
        groups[key].append(game)
    return [sorted(v, key=lambda g: g.date) for v in groups.values()]


def process_season_level(client: PBPStatsClient, games: Sequence[PlayerGame], limit: Optional[int]) -> Tuple[List[Dict[str, Any]], Dict[int, Dict[str, Any]]]:
    rows: List[Dict[str, Any]] = []
    coverage: Dict[int, Dict[str, Any]] = defaultdict(lambda: defaultdict(int))
    groups = group_games_for_season(games)

    for i, group in enumerate(groups, 1):
        if limit and i > limit:
            break
        first = group[0]
        cov = coverage[first.year]
        cov["season_attempted"] += 1
        start_date = group[0].date
        end_date = group[-1].date

        expected_seconds = sum((g.repo_minutes or 0.0) * 60.0 for g in group) or None
        expected_off_poss = sum(g.repo_poss or 0.0 for g in group) or None

        team_row = wowy_stats(client, first.year, first.team, "Team", first.player_id)
        opp_row = wowy_stats(client, first.year, first.team, "Opponent", first.player_id)
        unique_opponents = {g.opponent for g in group if g.opponent}
        baseline = baseline_allowed(client, first.year, first.opponent, None, None) if len(unique_opponents) == 1 else {}
        status, notes = validate_wowy(
            first,
            team_row,
            None,
            "season",
            expected_seconds=expected_seconds,
            expected_off_poss=expected_off_poss,
        )

        if status == "validated":
            cov["season_validated"] += 1
        else:
            cov["season_invalid"] += 1
        rows.append(build_context_row(first, "season", start_date, end_date, team_row, opp_row, baseline, status, notes))

        if i % 25 == 0:
            print(f"season rows processed: {i}/{len(groups)}", flush=True)

    return rows, coverage


def merge_coverage(*parts: Dict[int, Dict[str, Any]]) -> Dict[str, Any]:
    years = sorted({year for part in parts for year in part})
    out: Dict[str, Any] = {"generatedAt": datetime.utcnow().isoformat(timespec="seconds") + "Z", "years": {}}
    for year in years:
        row: Dict[str, Any] = {"year": year}
        for part in parts:
            for key, value in part.get(year, {}).items():
                row[key] = row.get(key, 0) + value
        row["gameLevelAvailable"] = row.get("game_validated", 0) > 0
        row["seriesLevelAvailable"] = row.get("series_validated", 0) > 0
        row["seasonLevelAvailable"] = row.get("season_validated", 0) > 0
        out["years"][str(year)] = row
    return out


def write_outputs(rows: Sequence[Dict[str, Any]], level: str) -> None:
    by_year: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_year[int(row["year"])].append(row)
    for year, year_rows in sorted(by_year.items()):
        write_json(OUT_ROOT / f"player_on_{level}_{year}.json", year_rows)


def merge_into_v2(rows: Sequence[Dict[str, Any]], level: str) -> Dict[str, int]:
    if level not in {"game", "series"}:
        return {"filesChanged": 0, "rowsMerged": 0}

    by_source: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if level == "game":
            key = row.get("gameRowId")
        else:
            key = (row.get("playerId"), row.get("year"), row.get("team"), row.get("seriesCode"))
        if key:
            by_source[str(key)].append(row)

    files_changed = 0
    rows_merged = 0
    allowed_prefixes = (
        "onTeam",
        "onOpp",
        "opp",
        "opponentContext",
        "validation",
        "source",
        "contextLevel",
        "startDate",
        "endDate",
    )

    for path in sorted(PLAYERS_DIR.glob("*.json")):
        data = read_json(path)
        changed = False
        target_rows = data.get("games" if level == "game" else "series", [])
        for target in target_rows:
            if level == "game":
                lookup = str(target.get("gameRowId") or "")
            else:
                lookup = str((clean_id(target.get("nbaId") or target.get("playerId")), target.get("year"), norm_team(target.get("team")), target.get("seriesCode")))
            matches = by_source.get(lookup)
            if not matches:
                continue
            patch = matches[0]
            for key, value in patch.items():
                if key.startswith(allowed_prefixes) or "_vs_" in key:
                    target[key] = value
            target["hasValidatedOnCourtPbpstats"] = patch.get("validationStatus") == "validated"
            changed = True
            rows_merged += 1

        if changed:
            write_json(path, data)
            files_changed += 1

    return {"filesChanged": files_changed, "rowsMerged": rows_merged}


def parse_years(arg: str) -> List[int]:
    years: List[int] = []
    for part in arg.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = part.split("-", 1)
            years.extend(range(int(start), int(end) + 1))
        else:
            years.append(int(part))
    return sorted(set(years))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", default="1997-2026", help="Year list/range, e.g. 2005 or 2001-2026")
    parser.add_argument("--levels", default="game,series,season", help="Comma list: game,series,season")
    parser.add_argument("--players", default="", help="Comma list of player slugs, names, or NBA ids")
    parser.add_argument("--limit", type=int, default=None, help="Limit rows/groups per level for spot checks")
    parser.add_argument("--probe-only", action="store_true", help="Only test endpoint filter behavior")
    parser.add_argument("--merge-v2", action="store_true", help="Merge validated game/series rows back into v2/data/players")
    parser.add_argument("--force", action="store_true", help="Ignore cached API responses")
    parser.add_argument("--sleep", type=float, default=0.35, help="Delay between uncached API requests")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    years = parse_years(args.years)
    levels = {x.strip().lower() for x in args.levels.split(",") if x.strip()}
    selectors = [x.strip() for x in args.players.split(",") if x.strip()]
    client = PBPStatsClient(sleep=args.sleep, force=args.force)

    probe = endpoint_probe(client)
    write_json(OUT_ROOT / "endpoint_filter_audit.json", probe)
    print(json.dumps({"endpointFilterAudit": probe["summary"]}, indent=2), flush=True)
    if args.probe_only:
        return 0

    if not PLAYERS_DIR.exists():
        raise SystemExit(f"Missing {PLAYERS_DIR}. Run this from the repository root.")

    games = iter_player_games(years, selectors)
    print(f"candidate player-games: {len(games)}", flush=True)
    if not games:
        return 0

    coverage_parts: List[Dict[int, Dict[str, Any]]] = []
    merge_report: Dict[str, Any] = {}

    if "game" in levels:
        game_rows, cov = process_game_level(client, games, args.limit)
        write_outputs(game_rows, "game")
        coverage_parts.append(cov)
        if args.merge_v2:
            merge_report["game"] = merge_into_v2([r for r in game_rows if r.get("validationStatus") == "validated"], "game")

    if "series" in levels:
        series_rows, cov = process_series_level(client, games, args.limit)
        write_outputs(series_rows, "series")
        coverage_parts.append(cov)
        if args.merge_v2:
            merge_report["series"] = merge_into_v2([r for r in series_rows if r.get("validationStatus") == "validated"], "series")

    if "season" in levels:
        season_rows, cov = process_season_level(client, games, args.limit)
        write_outputs(season_rows, "season")
        coverage_parts.append(cov)

    coverage = merge_coverage(*coverage_parts)
    coverage["endpointFilterAudit"] = probe["summary"]
    if merge_report:
        coverage["mergeReport"] = merge_report
    write_json(OUT_ROOT / "coverage_summary.json", coverage)
    print(json.dumps(coverage, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
