#!/usr/bin/env python3
"""
Build verified player-game adjusted true shooting ingredients from NBA play-by-play.

Why this exists:
Gabriel1200's game_report player rows have normal box-score fields (PTS/FGA/FTA/TOV),
but not all adjusted-TS ingredients at the player-game level. This script reconstructs
those ingredients from play-by-play when internet access is available.

Outputs:
  data/player_game_adjts_ingredients.csv
  data-package.json + data/data-package.json + embedded index.html when --apply is used

Definition used in this project:
  Scoring TOV = total TOV - bad-pass TOV - bad-pass-out-of-bounds TOV
  AdjFGA = FGA + scoring TOV - heave attempts - Z Bounds
  AdjFTA = FTA - technical FTA
  AdjTS% = PTS / (2 * (AdjFGA + 0.44 * AdjFTA))

Z Bounds are implemented as pbpstats-style self offensive rebounds: a player misses a
field goal and then gets credited with the immediate offensive rebound of that miss.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent
DATA_PACKAGE = ROOT / "data-package.json"
DATA_COPY = ROOT / "data" / "data-package.json"
INDEX_FILE = ROOT / "index.html"
OUT_CSV = ROOT / "data" / "player_game_adjts_ingredients.csv"
CACHE_DIR = ROOT / "data" / "pbp_cache"

NBA_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
    "Referer": "https://www.nba.com/",
    "Origin": "https://www.nba.com",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
    "Connection": "keep-alive",
}


def safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if math.isnan(float(value)) or math.isinf(float(value)):
            return None
        return float(value)
    text = str(value).strip()
    if text in {"", "—", "None", "null", "nan", "NaN"}:
        return None
    try:
        value = float(text.replace(",", ""))
    except ValueError:
        return None
    if math.isnan(value) or math.isinf(value):
        return None
    return value


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


def normalize_game_id(game_id: Any) -> str:
    digits = re.sub(r"\D", "", str(game_id or ""))
    if not digits:
        return ""
    return digits.zfill(10)


def clock_seconds(clock: Any) -> Optional[float]:
    """Parse NBA clock values like 'PT00M01.50S' or '00:01.5' to seconds left."""
    if clock is None:
        return None
    text = str(clock).strip()
    m = re.match(r"PT(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?", text)
    if m:
        minutes = float(m.group(1) or 0)
        seconds = float(m.group(2) or 0)
        return minutes * 60 + seconds
    m = re.match(r"(?:(\d+):)?(\d+(?:\.\d+)?)", text)
    if m:
        minutes = float(m.group(1) or 0)
        seconds = float(m.group(2) or 0)
        return minutes * 60 + seconds
    return None


def fetch_json(url: str, timeout: int = 30, retries: int = 3, sleep: float = 0.75) -> Dict[str, Any]:
    last_error = None
    for attempt in range(retries):
        req = urllib.request.Request(url, headers=NBA_HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
            return json.loads(raw)
        except Exception as exc:  # noqa: BLE001 - we want retry details
            last_error = exc
            time.sleep(sleep * (attempt + 1))
    raise RuntimeError(f"failed to fetch {url}: {last_error}")


def data_sets_from_response(payload: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """Return endpoint result sets as list-of-dicts, tolerant of NBA response shapes."""
    result_sets = payload.get("resultSets") or payload.get("resultSet") or payload.get("resultSets", [])
    if isinstance(result_sets, dict):
        result_sets = [result_sets]
    out: Dict[str, List[Dict[str, Any]]] = {}
    for item in result_sets or []:
        name = item.get("name") or item.get("resultSetName") or item.get("Name")
        headers = item.get("headers") or item.get("Headers") or []
        rows = item.get("rowSet") or item.get("RowSet") or []
        if name and headers:
            out[name] = [dict(zip(headers, row)) for row in rows]
    return out


def fetch_playbyplayv3(game_id: str, sleep: float = 0.75, force: bool = False) -> List[Dict[str, Any]]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    gid = normalize_game_id(game_id)
    cache_file = CACHE_DIR / f"{gid}_playbyplayv3.json"
    if cache_file.exists() and not force:
        payload = json.loads(cache_file.read_text())
    else:
        params = urllib.parse.urlencode({"GameID": gid, "StartPeriod": 0, "EndPeriod": 14})
        url = f"https://stats.nba.com/stats/playbyplayv3?{params}"
        payload = fetch_json(url, sleep=sleep)
        cache_file.write_text(json.dumps(payload))
        time.sleep(sleep)
    data_sets = data_sets_from_response(payload)
    # nba_api exposes this set as PlayByPlay.
    rows = data_sets.get("PlayByPlay") or data_sets.get("playByPlay") or []
    return rows


def is_field_goal(event: Dict[str, Any]) -> bool:
    val = event.get("isFieldGoal")
    if str(val).strip() in {"1", "True", "true"}:
        return True
    text = f"{event.get('actionType','')} {event.get('description','')}".lower()
    return "jump shot" in text or "layup" in text or "dunk" in text or "hook shot" in text or "floating" in text


def is_missed_field_goal(event: Dict[str, Any]) -> bool:
    if not is_field_goal(event):
        return False
    result = str(event.get("shotResult") or "").lower()
    text = f"{event.get('description','')} {event.get('actionType','')} {event.get('subType','')}".lower()
    return result == "missed" or "miss" in text


def is_rebound(event: Dict[str, Any]) -> bool:
    text = f"{event.get('actionType','')} {event.get('description','')} {event.get('subType','')}".lower()
    return "rebound" in text


def is_turnover(event: Dict[str, Any]) -> bool:
    text = f"{event.get('actionType','')} {event.get('description','')} {event.get('subType','')}".lower()
    return "turnover" in text


def is_free_throw(event: Dict[str, Any]) -> bool:
    text = f"{event.get('actionType','')} {event.get('description','')} {event.get('subType','')}".lower()
    return "free throw" in text or "freethrow" in text


def event_person_id(event: Dict[str, Any]) -> Optional[str]:
    val = event.get("personId") or event.get("PLAYER1_ID") or event.get("player1Id")
    if val is None:
        return None
    digits = re.sub(r"\D", "", str(val))
    return digits or None


def event_team_id(event: Dict[str, Any]) -> Optional[str]:
    val = event.get("teamId") or event.get("TEAM_ID")
    if val is None:
        return None
    digits = re.sub(r"\D", "", str(val))
    return digits or None


def event_order(event: Dict[str, Any]) -> Tuple[int, int]:
    period = safe_int(event.get("period")) or 0
    action = safe_int(event.get("actionNumber") or event.get("EVENTNUM")) or 0
    return period, action


def parse_game_ingredients(game_id: str, rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    """Return ingredients keyed by NBA person/player id for one game."""
    stats: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    last_missed_fg: Optional[Dict[str, Any]] = None

    for event in sorted(rows, key=event_order):
        person_id = event_person_id(event)
        team_id = event_team_id(event)
        text = f"{event.get('description','')} {event.get('actionType','')} {event.get('subType','')}".lower()

        if is_missed_field_goal(event):
            if person_id:
                distance = safe_float(event.get("shotDistance"))
                seconds = clock_seconds(event.get("clock") or event.get("PCTIMESTRING"))
                if distance is not None and distance >= 40 and seconds is not None and seconds <= 2.0:
                    stats[person_id]["Heaves"] += 1
                last_missed_fg = {"personId": person_id, "teamId": team_id}
            continue

        if is_rebound(event):
            # Z Bounds = self offensive rebound of your own missed FGA.
            if last_missed_fg and person_id and team_id:
                if person_id == last_missed_fg.get("personId") and team_id == last_missed_fg.get("teamId"):
                    stats[person_id]["ZBounds"] += 1
            last_missed_fg = None
            continue

        # If a new possession-like event comes before a rebound, stop carrying the missed shot.
        if is_turnover(event) or is_free_throw(event) or (is_field_goal(event) and not is_missed_field_goal(event)):
            last_missed_fg = None

        if is_turnover(event) and person_id:
            if "bad pass" in text:
                if "out of bounds" in text or "out-of-bounds" in text or "out bounds" in text:
                    stats[person_id]["BadPassOutOfBoundsTOV"] += 1
                else:
                    stats[person_id]["BadPassTOV"] += 1

        if is_free_throw(event) and person_id:
            if "technical" in text:
                stats[person_id]["TechFTA"] += 1

    # Convert defaultdicts to plain dict and include game id.
    return {pid: dict(values) for pid, values in stats.items()}


def base_games_for_years(data: Dict[str, Any], years: Optional[Iterable[int]] = None) -> List[Dict[str, Any]]:
    year_set = set(years or [])
    rows = []
    for game in data.get("playerGames", []):
        game_id = normalize_game_id(game.get("gameId"))
        year = safe_int(game.get("year"))
        if not game_id or not year:
            continue
        if year_set and year not in year_set:
            continue
        rows.append(game)
    return rows


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


def write_ingredients_csv(data: Dict[str, Any], years: Optional[List[int]], limit_games: Optional[int], force: bool, sleep: float) -> Path:
    games = base_games_for_years(data, years)
    by_game: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in games:
        by_game[normalize_game_id(row.get("gameId"))].append(row)
    game_ids = sorted(by_game.keys())
    if limit_games:
        game_ids = game_ids[:limit_games]

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "gameId", "playerId", "nbaId", "playerName", "year", "team", "opponent",
        "PTS", "FGA", "FTA", "TOV",
        "BadPassTOV", "BadPassOutOfBoundsTOV", "ScoringTOV", "Heaves", "ZBounds", "TechFTA",
        "AdjFGA", "AdjFTA", "AdjTS%", "source",
    ]

    existing_rows: Dict[Tuple[str, str], Dict[str, Any]] = {}
    if OUT_CSV.exists() and not force:
        with OUT_CSV.open(newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                existing_rows[(normalize_game_id(row.get("gameId")), str(row.get("nbaId") or ""))] = row

    written = 0
    failed: List[str] = []
    for idx, game_id in enumerate(game_ids, start=1):
        needs_game = force or any((game_id, str(g.get("nbaId") or "")) not in existing_rows for g in by_game[game_id])
        if not needs_game:
            continue
        try:
            pbp_rows = fetch_playbyplayv3(game_id, sleep=sleep, force=force)
            ingredients = parse_game_ingredients(game_id, pbp_rows)
        except Exception as exc:  # noqa: BLE001
            print(f"[{idx}/{len(game_ids)}] failed {game_id}: {exc}")
            failed.append(game_id)
            continue

        for game in by_game[game_id]:
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
            adj_fga = fga + scoring_tov - heaves - z_bounds
            adj_fta = max(fta - tech_fta, 0.0)
            adj_ts = None
            denom = 2 * (adj_fga + 0.44 * adj_fta)
            if adj_fga > 0 and denom > 0:
                adj_ts = 100 * pts / denom
            existing_rows[(game_id, nba_id)] = {
                "gameId": game_id,
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
                "source": "NBA playbyplayv3 reconstruction",
            }
            written += 1
        print(f"[{idx}/{len(game_ids)}] {game_id}: rebuilt {len(by_game[game_id])} player rows")

    with OUT_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for key in sorted(existing_rows.keys()):
            row = existing_rows[key]
            writer.writerow({name: row.get(name, "") for name in fieldnames})
    print(f"Wrote {OUT_CSV} with {len(existing_rows):,} rows. Newly rebuilt rows: {written:,}. Failed games: {len(failed)}")
    if failed:
        (OUT_CSV.parent / "player_game_adjts_failed_games.txt").write_text("\n".join(failed))
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
            lookup[(normalize_game_id(row.get("gameId")), str(row.get("nbaId") or ""))] = row

    updated_games = 0
    for game in data.get("playerGames", []):
        key = (normalize_game_id(game.get("gameId")), str(game.get("nbaId") or ""))
        row = lookup.get(key)
        if not row:
            continue
        adj_ts = safe_float(row.get("AdjTS%"))
        if adj_ts is None:
            continue
        game["AdjTS%"] = round_value(adj_ts, 1)
        game["AdjTS_source"] = "verified game-level NBA playbyplayv3 reconstruction"
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
    for key, rows in series_groups.items():
        if not rows:
            continue
        first = rows[0]
        sid = f"{first.get('playerId')}_{first.get('year')}_{first.get('seriesCode')}_{first.get('opponent')}"
        series = by_series_id.get(sid)
        if not series:
            continue
        verified = [r for r in rows if str(r.get("AdjTS_source") or "").startswith("verified game-level") and r.get("AdjTS%") is not None]
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
        series["AdjTS_source"] = "verified series aggregation of game-level NBA playbyplayv3 AdjTS"
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
    note = "Game/series AdjTS is populated only where build_adjts_from_pbp.py reconstructed bad-pass turnovers, heaves, Z Bounds, and technical FTA from NBA playbyplayv3."
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
    parser = argparse.ArgumentParser(description="Build/apply verified game-level AdjTS ingredients from NBA play-by-play.")
    parser.add_argument("--years", default="2025", help="Year list/range, e.g. 2025 or 2001-2026 or all. Default: 2025")
    parser.add_argument("--limit-games", type=int, default=None, help="Debug limit for number of games to fetch.")
    parser.add_argument("--sleep", type=float, default=0.75, help="Delay between NBA requests.")
    parser.add_argument("--force", action="store_true", help="Refetch cached games and overwrite matching ingredients.")
    parser.add_argument("--apply", action="store_true", help="Apply generated ingredients to data-package.json and embedded index.html.")
    parser.add_argument("--apply-only", action="store_true", help="Skip fetching and only apply existing data/player_game_adjts_ingredients.csv.")
    args = parser.parse_args()

    data = json.loads(DATA_PACKAGE.read_text())
    years = parse_years(args.years)
    if not args.apply_only:
        write_ingredients_csv(data, years=years, limit_games=args.limit_games, force=args.force, sleep=args.sleep)
    if args.apply or args.apply_only:
        data = apply_ingredients(data)
        write_data_package(data)
        print("Applied verified game/series AdjTS to data-package.json, data/data-package.json, and index.html.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
