#!/usr/bin/env python3
"""
Build pipeline for Playoff Translation Lab.

This script creates a compact, offline-ready data package from Gabriel1200's
player_sheets exports when they are already present in external_data/. If the
folder is missing, it can fetch only the required folders with sparse checkout,
avoiding the giant full-repo clone that caused Codespaces disk issues.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import shutil
import unicodedata
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
EXTERNAL_DIR = ROOT / "external_data"
PLAYER_SHEETS_DIR = EXTERNAL_DIR / "player_sheets"
GEN_TOTALS_DIR = PLAYER_SHEETS_DIR / "gen_totals"
OUTPUT_FILE = ROOT / "data-package.json"
MANIFEST_FILE = ROOT / "source_manifest.json"
INDEX_FILE = ROOT / "index.html"
DATA_COPY_FILE = DATA_DIR / "data-package.json"

GABRIEL_REPOS = {
    "site_Data": "https://github.com/gabriel1200/site_Data",
    "player_sheets": "https://github.com/gabriel1200/player_sheets",
    "merged_playbyplay": "https://github.com/gabriel1200/merged_playbyplay",
    "pbpbacklog": "https://github.com/gabriel1200/pbpbacklog",
    "legacy_pbp": "https://github.com/gabriel1200/legacy_pbp",
}

PLAYER_SHEETS_SPARSE_PATHS = [
    "totals/",
    "team_totals/",
    "game_report/",
    "on_off/",
    "offensive_role_summaries/",
    "gen_totals/",
]

TARGET_YEARS = list(range(1997, 2027))
FEATURED_PLAYERS = [
    "LeBron James",
    "Stephen Curry",
    "Nikola Jokic",
    "Kobe Bryant",
    "Kevin Durant",
    "Giannis Antetokounmpo",
    "Tim Duncan",
    "Shaquille O'Neal",
    "Michael Jordan",
    "Dwyane Wade",
    "James Harden",
    "Luka Doncic",
]

ROUND_LABELS = {
    "1": "First Round",
    "2": "Conference Semifinals",
    "3": "Conference Finals",
    "4": "NBA Finals",
}

METRIC_FIELDS = [
    "MIN", "PTS/75", "REB/75", "AST/75", "TOV/75", "TS%", "eFG%",
    "ORTG", "DRTG", "NET", "rORTG", "rDRTG", "rNET", "rTS",
]


def run(cmd: List[str], cwd: Optional[Path] = None) -> Tuple[int, str, str]:
    proc = subprocess.run(cmd, cwd=str(cwd) if cwd else None, text=True, capture_output=True)
    return proc.returncode, proc.stdout, proc.stderr


def ensure_player_sheets(fetch: bool = False) -> Path:
    """Return local player_sheets folder, optionally sparse-fetching if missing."""
    if PLAYER_SHEETS_DIR.exists() and any(PLAYER_SHEETS_DIR.glob("totals/*_ps.csv")):
        return PLAYER_SHEETS_DIR

    if not fetch:
        raise FileNotFoundError(
            "external_data/player_sheets with totals/*_ps.csv was not found. "
            "Run `python3 build_data.py --fetch` to sparse-clone the required data."
        )

    EXTERNAL_DIR.mkdir(parents=True, exist_ok=True)
    if PLAYER_SHEETS_DIR.exists():
        shutil.rmtree(PLAYER_SHEETS_DIR)

    print("Sparse-cloning Gabriel1200/player_sheets required folders only...")
    code, out, err = run([
        "git", "clone", "--depth", "1", "--filter=blob:none", "--sparse",
        GABRIEL_REPOS["player_sheets"], str(PLAYER_SHEETS_DIR)
    ])
    if code != 0:
        raise RuntimeError(f"git clone failed:\n{out}\n{err}")

    code, out, err = run(["git", "sparse-checkout", "set", *PLAYER_SHEETS_SPARSE_PATHS], cwd=PLAYER_SHEETS_DIR)
    if code != 0:
        raise RuntimeError(f"git sparse-checkout failed:\n{out}\n{err}")
    return PLAYER_SHEETS_DIR


def canonical_player_name(name: str) -> str:
    text = str(name or "Unknown Player").strip()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text


def slugify(name: str, nba_id: Optional[str] = None) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", (name or "player").lower()).strip("_") or "player"
    if nba_id:
        clean_id = re.sub(r"\D", "", str(nba_id))
        if clean_id:
            return f"{base}_{clean_id}"
    return base


def safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if math.isnan(value) or math.isinf(value):
            return None
        return float(value)
    text = str(value).strip()
    if text in {"", "—", "None", "nan", "NaN", "null"}:
        return None
    text = text.replace(",", "")
    try:
        number = float(text)
    except ValueError:
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def safe_int(value: Any) -> Optional[int]:
    number = safe_float(value)
    if number is None:
        return None
    return int(round(number))


def pick(row: Dict[str, Any], *names: str) -> Optional[str]:
    for name in names:
        if name in row and str(row.get(name, "")).strip() != "":
            return row.get(name)
    # case-insensitive fallback. Cache the lower-key map on the row because
    # the build loops call this thousands of times across wide CSV rows.
    lower = row.get("__lower_key_cache")
    if lower is None:
        lower = {k.lower(): k for k in row.keys()}
        row["__lower_key_cache"] = lower
    for name in names:
        key = lower.get(name.lower())
        if key and str(row.get(key, "")).strip() != "":
            return row.get(key)
    return None


def round_value(value: Optional[float], digits: int = 1) -> Optional[float]:
    if value is None:
        return None
    if math.isnan(value) or math.isinf(value):
        return None
    return round(float(value), digits)


def pct(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return value * 100 if abs(value) <= 1.5 else value


def ts_from_points_attempts(points: Optional[float], fga: Optional[float], fta: Optional[float]) -> Optional[float]:
    """Return TS% from points, FGA, and FTA. Works with totals or per-game values."""
    if points is None or fga is None or fta is None:
        return None
    denom = 2 * (fga + 0.44 * fta)
    if denom <= 0:
        return None
    return 100 * points / denom


def scoring_turnovers_from_row(row: Dict[str, Any]) -> Optional[float]:
    """Turnovers that used a scoring chance.

    Important: if a row only has total TOV but not bad-pass / bad-pass-out-of-bounds
    splits, do NOT treat every turnover as a scoring turnover. That was making
    game/series AdjTS and rAdjTS look far too low. Return None when the detailed
    turnover split is unavailable; adjusted TS will then use normal FGA plus any
    other verified components that are present.
    """
    explicit = safe_float(pick(row, "ScoringTurnovers", "SCORING_TOV", "ScoringTOV"))
    if explicit is not None:
        return max(explicit, 0.0)
    turnovers = safe_float(pick(row, "Turnovers", "TOV", "TO"))
    if turnovers is None:
        return None
    bad_raw = pick(row, "BadPassTurnovers", "BAD_PASS_TOV", "BadPassTOV")
    bad_oob_raw = pick(row, "BadPassOutOfBoundsTurnovers", "BadPassOOBTurnovers")
    if bad_raw is None and bad_oob_raw is None:
        return None
    bad_pass = safe_float(bad_raw) or 0.0
    bad_pass_oob = safe_float(bad_oob_raw) or 0.0
    scoring = turnovers - bad_pass - bad_pass_oob
    return max(scoring, 0.0)


def adjusted_fga_from_row(row: Dict[str, Any], allow_partial: bool = False) -> Optional[float]:
    """Modified FGA for adjusted TS: FGA + verified scoring TOV - heaves - self/Z Bounds."""
    base_fga = row_total_fga(row)
    if base_fga is None:
        return None
    scoring_tov = scoring_turnovers_from_row(row)
    heaves = safe_float(pick(row, "HeaveAttempts", "HEAVE_ATTEMPTS", "Heaves"))
    # Some pbp rows expose only total arc 3PA and non-heave arc 3PA. Infer heaves from the gap.
    if heaves is None:
        arc3 = safe_float(pick(row, "Arc3FGA"))
        non_heave_arc3 = safe_float(pick(row, "NonHeaveArc3FGA"))
        if arc3 is not None and non_heave_arc3 is not None:
            heaves = max(arc3 - non_heave_arc3, 0.0)
    z_boards = safe_float(pick(row, "SelfOReb", "SelfORebounds", "Z Bounds", "ZBounds", "Z_Bounds", "ZBoards", "Z_Boards", "ZORB"))
    has_any_adjustment = any(v is not None for v in (scoring_tov, heaves, z_boards))
    if not allow_partial and not has_any_adjustment:
        return None
    # Unknown scoring turnovers are not zero in reality, but using total TOV here is wrong.
    # For game rows without the split, leave the scoring-TOV adjustment at 0 and label the source.
    adj_fga = base_fga + (scoring_tov or 0.0) - (heaves or 0.0) - (z_boards or 0.0)
    return adj_fga if adj_fga > 0 else None


def adjusted_fta_from_row(row: Dict[str, Any], allow_partial: bool = False) -> Optional[float]:
    """FTA with technical free throw trips removed because they do not use possessions."""
    fta = safe_float(pick(row, "FTA", "FreeThrowAttempts"))
    if fta is None:
        return None
    tech_fta = safe_float(pick(row, "Technical Free Throw Trips", "TechnicalFreeThrowTrips", "TechFTA", "TechnicalFTA"))
    if tech_fta is None and not allow_partial:
        # If a detailed row has other adjustment fields but lacks tech trips, treat as zero.
        detailed_signals = ["Turnovers", "TOV", "TO", "BadPassTurnovers", "BadPassOutOfBoundsTurnovers", "HeaveAttempts", "HEAVE_ATTEMPTS", "SelfOReb", "SelfORebounds", "Z Bounds", "ZBounds", "Z_Bounds", "ZBoards", "Z_Boards"]
        if not any(pick(row, key) is not None for key in detailed_signals):
            return None
    return max(fta - (tech_fta or 0.0), 0.0)


def adjusted_ts_from_row(row: Dict[str, Any], points_names: Tuple[str, ...] = ("PTS", "Points", "POINTS"), allow_partial: bool = False) -> Optional[float]:
    """Adjusted TS% using modified FGA and non-technical FTA."""
    pts = safe_float(pick(row, *points_names))
    adj_fga = adjusted_fga_from_row(row, allow_partial=allow_partial)
    adj_fta = adjusted_fta_from_row(row, allow_partial=allow_partial)
    if pts is None or adj_fga is None or adj_fta is None:
        return None
    return ts_from_points_attempts(pts, adj_fga, adj_fta)


def adjustment_components_from_row(row: Dict[str, Any]) -> Dict[str, Optional[float]]:
    base_fga = row_total_fga(row)
    scoring_tov = scoring_turnovers_from_row(row)
    heaves = safe_float(pick(row, "HeaveAttempts", "HEAVE_ATTEMPTS", "Heaves"))
    if heaves is None:
        arc3 = safe_float(pick(row, "Arc3FGA"))
        non_heave_arc3 = safe_float(pick(row, "NonHeaveArc3FGA"))
        if arc3 is not None and non_heave_arc3 is not None:
            heaves = max(arc3 - non_heave_arc3, 0.0)
    z_boards = safe_float(pick(row, "SelfOReb", "SelfORebounds", "Z Bounds", "ZBounds", "Z_Bounds", "ZBoards", "Z_Boards", "ZORB"))
    fta = safe_float(pick(row, "FTA", "FreeThrowAttempts"))
    tech_fta = safe_float(pick(row, "Technical Free Throw Trips", "TechnicalFreeThrowTrips", "TechFTA", "TechnicalFTA"))
    return {
        "baseFGA": round_value(base_fga, 1),
        "scoringTOV": round_value(scoring_tov, 1),
        "heaves": round_value(heaves, 1),
        "zBoards": round_value(z_boards, 1),
        "adjFGA": round_value(adjusted_fga_from_row(row, allow_partial=True), 1),
        "FTA": round_value(fta, 1),
        "techFTA": round_value(tech_fta, 1),
        "adjFTA": round_value(adjusted_fta_from_row(row, allow_partial=True), 1),
    }


def allowed_ts_from_row(row: Dict[str, Any]) -> Optional[float]:
    """Opponent defensive TS% allowed from team-level opponent fields when available."""
    opp_ts = pct(safe_float(pick(row, "OPP_TS_PCT", "OppTsPct", "OpponentTsPct", "opp_TS_PCT")))
    if opp_ts is not None:
        return opp_ts
    opp_pts = safe_float(pick(row, "OPP_PTS", "OpponentPoints", "OpponentPTS"))
    opp_fga = safe_float(pick(row, "OPP_FGA", "OpponentFGA"))
    opp_fta = safe_float(pick(row, "OPP_FTA", "OpponentFTA"))
    return ts_from_points_attempts(opp_pts, opp_fga, opp_fta)



def allowed_adjusted_ts_from_row(row: Dict[str, Any]) -> Optional[float]:
    """Opponent allowed adjusted TS from opponent box fields when detailed opponent fields are unavailable."""
    # Exact opponent adjustment fields are not present in all_teamyears, so this is
    # a conservative allowed benchmark: opponent FGA + opponent TOV, with missing
    # detailed heave/Z Bound/bad-pass splits treated as zero.
    opp_pts = safe_float(pick(row, "OPP_PTS", "OpponentPoints", "OpponentPTS"))
    opp_fga = safe_float(pick(row, "OPP_FGA", "OpponentFGA"))
    opp_fta = safe_float(pick(row, "OPP_FTA", "OpponentFTA"))
    opp_tov = safe_float(pick(row, "OPP_TOV", "OpponentTurnovers", "OpponentTOV")) or 0.0
    if opp_pts is None or opp_fga is None or opp_fta is None:
        return None
    return ts_from_points_attempts(opp_pts, opp_fga + opp_tov, opp_fta)

def row_total_fga(row: Dict[str, Any]) -> Optional[float]:
    """Total FGA from pbpstats-style rows where 2PA/3PA may be split."""
    fga = safe_float(pick(row, "FGA", "FieldGoalAttempts"))
    if fga is not None:
        return fga
    fg2a = safe_float(pick(row, "FG2A", "TwoPtAttempts"))
    fg3a = safe_float(pick(row, "FG3A", "ThreePtAttempts"))
    if fg2a is None and fg3a is None:
        return None
    return (fg2a or 0) + (fg3a or 0)


def team_ts_from_row(row: Dict[str, Any]) -> Optional[float]:
    ts = pct(safe_float(pick(row, "TS_PCT", "TsPct", "TS%")))
    if ts is not None:
        return ts
    pts = safe_float(pick(row, "PTS", "Points", "POINTS"))
    fga = row_total_fga(row)
    fta = safe_float(pick(row, "FTA"))
    return ts_from_points_attempts(pts, fga, fta)


def efg_from_row(row: Dict[str, Any]) -> Optional[float]:
    efg = pct(safe_float(pick(row, "EFG_PCT", "eFG%", "EFF_FG_PCT")))
    if efg is not None:
        return efg
    fgm = safe_float(pick(row, "FGM"))
    fg3m = safe_float(pick(row, "FG3M"))
    fga = row_total_fga(row)
    if fgm is None or fg3m is None or not fga:
        return None
    return 100 * (fgm + 0.5 * fg3m) / fga


def rim_frequency_from_row(row: Dict[str, Any]) -> Optional[float]:
    freq = pct(safe_float(pick(row, "AtRimFrequency", "RA_FGA_FREQUENCY", "RIM_FREQUENCY")))
    if freq is not None:
        return freq
    rim_fga = safe_float(pick(row, "AtRimFGA", "RA_FGA", "FGA_LT_5", "FGA_LT_06"))
    fga = row_total_fga(row)
    if rim_fga is None or not fga:
        return None
    return 100 * rim_fga / fga


def rim_accuracy_from_row(row: Dict[str, Any]) -> Optional[float]:
    acc = pct(safe_float(pick(row, "AtRimAccuracy", "RA_FG_PCT", "FGP_LT_5", "LT_06_PCT")))
    if acc is not None:
        return acc
    rim_fgm = safe_float(pick(row, "AtRimFGM", "RA_FGM", "FGM_LT_5", "FGM_LT_06"))
    rim_fga = safe_float(pick(row, "AtRimFGA", "RA_FGA", "FGA_LT_5", "FGA_LT_06"))
    if rim_fgm is None or not rim_fga:
        return None
    return 100 * rim_fgm / rim_fga


def ratio_pct(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return 100 * numerator / denominator


def per75(total: Optional[float], poss: Optional[float]) -> Optional[float]:
    if total is None or poss is None or poss <= 0:
        return None
    return total / poss * 75


def weighted_average(pairs: Iterable[Tuple[Optional[float], Optional[float]]]) -> Optional[float]:
    numerator = 0.0
    denominator = 0.0
    for value, weight in pairs:
        if value is None:
            continue
        w = weight if weight and weight > 0 else 1.0
        numerator += value * w
        denominator += w
    if denominator <= 0:
        return None
    return numerator / denominator


def read_csv(path: Path) -> List[Dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            return list(csv.DictReader(handle))
    except Exception as exc:
        print(f"Warning: skipped unreadable CSV {path}: {exc}")
        return []


def playoff_round_from_game_id(game_id: str) -> Tuple[str, str, int]:
    digits = re.sub(r"\D", "", str(game_id or ""))
    padded = digits.zfill(10)
    # NBA playoff ids look like 004YYSSSGG. The SSS block encodes round/series.
    series_code = padded[5:8] if len(padded) >= 8 else ""
    round_code = series_code[:1] if series_code else ""
    label = ROUND_LABELS.get(round_code, "Playoff Series")
    try:
        sort_key = int(round_code or 9)
    except ValueError:
        sort_key = 9
    return series_code or digits, label, sort_key


def clean_date(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    text = str(value).strip()
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    return text or None


class DataBuilder:
    def __init__(self, player_sheets: Path):
        self.player_sheets = player_sheets
        self.players: Dict[str, Dict[str, Any]] = {}
        self.player_id_by_nba_id: Dict[str, str] = {}
        self.player_id_by_name: Dict[str, str] = {}
        self.seasons: List[Dict[str, Any]] = []
        self.games: List[Dict[str, Any]] = []
        self.series: List[Dict[str, Any]] = []
        self.team_benchmarks: List[Dict[str, Any]] = []
        self.team_benchmarks_by_key: Dict[Tuple[int, str], Dict[str, Any]] = {}
        self.rs_team_benchmarks: List[Dict[str, Any]] = []
        self.rs_team_benchmarks_by_key: Dict[Tuple[int, str], Dict[str, Any]] = {}
        self.rs_team_benchmarks_by_year: Dict[int, Dict[str, Any]] = {}
        self.impact: List[Dict[str, Any]] = []
        self.on_court: List[Dict[str, Any]] = []
        self.skill_splits: List[Dict[str, Any]] = []
        self.rankings: List[Dict[str, Any]] = []
        self.player_team_ranks_game: List[Dict[str, Any]] = []
        self.player_team_ranks_series: List[Dict[str, Any]] = []
        self.source_summary: Dict[str, Any] = defaultdict(int)
        self.source_files: Dict[str, List[str]] = defaultdict(list)
        self.team_abbr_by_id_year: Dict[Tuple[int, str], str] = {}
        self.team_id_by_abbr_year: Dict[Tuple[int, str], str] = {}
        self.team_benchmarks_by_year: Dict[int, Dict[str, Any]] = {}
        self.team_game_context: Dict[Tuple[int, str, str], Dict[str, Any]] = {}
        self.detailed_player_pbp_by_key: Dict[Tuple[int, str, str], Dict[str, Any]] = {}
        self.detailed_player_pbp_by_year_id: Dict[Tuple[int, str], Dict[str, Any]] = {}
        self.game_keys_seen: set[Tuple[str, int, str, str, str]] = set()

    def player_id(self, name: str, nba_id: Optional[str]) -> str:
        name = canonical_player_name(name or "Unknown Player")
        clean_nba_id = re.sub(r"\D", "", str(nba_id or "")) or None
        if clean_nba_id and clean_nba_id in self.player_id_by_nba_id:
            player_id = self.player_id_by_nba_id[clean_nba_id]
        elif name.lower() in self.player_id_by_name:
            player_id = self.player_id_by_name[name.lower()]
        else:
            player_id = slugify(name, clean_nba_id)
            self.players[player_id] = {
                "id": player_id,
                "nbaId": clean_nba_id,
                "name": name,
                "featured": name in FEATURED_PLAYERS,
                "teams": [],
                "years": [],
                "seasonCount": 0,
                "gameRowCount": 0,
                "lastTeam": None,
            }
            if clean_nba_id:
                self.player_id_by_nba_id[clean_nba_id] = player_id
            self.player_id_by_name[name.lower()] = player_id
        return player_id

    def touch_player(self, player_id: str, year: Optional[int] = None, team: Optional[str] = None):
        player = self.players[player_id]
        if year and year not in player["years"]:
            player["years"].append(year)
        if team and team not in player["teams"]:
            player["teams"].append(team)
        if team:
            player["lastTeam"] = team

    def fallback_team_abbr(self, team_id: Optional[str], year: Optional[int] = None) -> Optional[str]:
        clean = re.sub(r"\D", "", str(team_id or ""))
        current = {
            "1610612737": "ATL", "1610612738": "BOS", "1610612739": "CLE",
            "1610612740": "NOP", "1610612741": "CHI", "1610612742": "DAL",
            "1610612743": "DEN", "1610612744": "GSW", "1610612745": "HOU",
            "1610612746": "LAC", "1610612747": "LAL", "1610612748": "MIA",
            "1610612749": "MIL", "1610612750": "MIN", "1610612751": "BKN",
            "1610612752": "NYK", "1610612753": "ORL", "1610612754": "IND",
            "1610612755": "PHI", "1610612756": "PHX", "1610612757": "POR",
            "1610612758": "SAC", "1610612759": "SAS", "1610612760": "OKC",
            "1610612761": "TOR", "1610612762": "UTA", "1610612763": "MEM",
            "1610612764": "WAS", "1610612765": "DET", "1610612766": "CHA",
        }
        if clean == "1610612751" and year and year <= 2012:
            return "NJN"
        if clean == "1610612760" and year and year <= 2008:
            return "SEA"
        if clean == "1610612766" and year and year <= 2002:
            return "CHH"
        if clean == "1610612740" and year:
            if year <= 2005:
                return "NOH"
            if year in (2006, 2007):
                return "NOK"
            if year <= 2013:
                return "NOH"
            return "NOP"
        return current.get(clean)

    def register_team(self, year: Optional[int], team_id: Optional[str], abbr: Optional[str]):
        if year not in TARGET_YEARS or not team_id or not abbr:
            return
        clean_id = re.sub(r"\D", "", str(team_id))
        clean_abbr = str(abbr).strip().upper()
        if not clean_id or not clean_abbr or len(clean_abbr) > 4:
            return
        self.team_abbr_by_id_year[(year, clean_id)] = clean_abbr
        self.team_id_by_abbr_year[(year, clean_abbr)] = clean_id

    def team_abbr(self, team_id: Optional[str], year: Optional[int], fallback: Optional[str] = None) -> Optional[str]:
        clean_id = re.sub(r"\D", "", str(team_id or ""))
        if year in TARGET_YEARS and clean_id:
            found = self.team_abbr_by_id_year.get((year, clean_id))
            if found:
                return found
        if fallback:
            text = str(fallback).strip().upper()
            # Accept already-abbreviated values, but avoid treating full team names as abbreviations.
            if 2 <= len(text) <= 4 and " " not in text:
                return text
        return self.fallback_team_abbr(clean_id, year)

    def prepare_team_maps(self):
        print("Preparing team abbreviation maps...")
        sources = []
        sources.extend(sorted((self.player_sheets / "totals").glob("*_ps.csv")))
        if GEN_TOTALS_DIR.exists():
            sources.extend(sorted(GEN_TOTALS_DIR.glob("[12][0-9][0-9][0-9].csv")))
            sources.extend(sorted(GEN_TOTALS_DIR.glob("[12][0-9][0-9][0-9]_ps_avg.csv")))
        for path in sources:
            for row in read_csv(path):
                year = safe_int(pick(row, "year", "SEASON", "Season", "YEAR"))
                if year not in TARGET_YEARS:
                    continue
                self.register_team(
                    year,
                    pick(row, "TEAM_ID", "TeamId"),
                    pick(row, "TEAM_ABBREVIATION", "TeamAbbreviation", "TeamAbbr", "team", "TEAM"),
                )


    def load_detailed_player_pbp_adjustments(self):
        """Load postseason player pbp aggregate rows for adjusted TS components."""
        if self.detailed_player_pbp_by_key or not GEN_TOTALS_DIR.exists():
            return
        files = sorted(GEN_TOTALS_DIR.glob("[12][0-9][0-9][0-9]_ps_pbp.csv"))
        print(f"Loading detailed player pbp adjustment rows from {len(files)} postseason files...")
        for path in files:
            year = safe_int(path.name[:4])
            if year not in TARGET_YEARS:
                continue
            rows = read_csv(path)
            self.source_summary["player_pbp_adjustment_files"] += 1
            self.source_summary["player_pbp_adjustment_rows"] += len(rows)
            self.source_files["player_pbp_adjustments"].append(f"gen_totals/{path.name}")
            for row in rows:
                nba_id = re.sub(r"\D", "", str(pick(row, "PLAYER_ID", "EntityId", "nba_id") or ""))
                if not nba_id:
                    continue
                team = self.team_abbr(pick(row, "TeamId", "TEAM_ID"), year, pick(row, "TeamAbbreviation", "TEAM_ABBREVIATION"))
                if team:
                    self.detailed_player_pbp_by_key[(year, nba_id, team)] = row
                self.detailed_player_pbp_by_year_id[(year, nba_id)] = row

    def detailed_player_row(self, year: Optional[int], nba_id: Optional[str], team: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if year not in TARGET_YEARS or not nba_id:
            return None
        clean_id = re.sub(r"\D", "", str(nba_id))
        if not clean_id:
            return None
        if team:
            row = self.detailed_player_pbp_by_key.get((year, clean_id, str(team).strip().upper()))
            if row:
                return row
        return self.detailed_player_pbp_by_year_id.get((year, clean_id))

    def upsert_team_benchmark(self, benchmark: Dict[str, Any], overwrite: bool = False):
        year = benchmark.get("year")
        team = benchmark.get("team")
        if year not in TARGET_YEARS or not team:
            return
        key = (year, team)
        existing = self.team_benchmarks_by_key.get(key)
        if not existing:
            self.team_benchmarks.append(benchmark)
            self.team_benchmarks_by_key[key] = benchmark
            return
        for field, value in benchmark.items():
            if field in {"benchmarkId", "year", "team"}:
                continue
            if overwrite or existing.get(field) is None:
                if value is not None:
                    existing[field] = value

    def aggregate_gen_team_benchmarks(self):
        folder = GEN_TOTALS_DIR
        if not folder.exists():
            return
        files = sorted(folder.glob("[12][0-9][0-9][0-9]team.csv"))
        print(f"Loading playoff team benchmarks from {len(files)} gen_totals team-game files...")
        for path in files:
            year = safe_int(path.stem.replace("team", ""))
            if year not in TARGET_YEARS:
                continue
            rows = read_csv(path)
            self.source_summary["gen_team_files"] += 1
            self.source_summary["gen_team_rows"] += len(rows)
            self.source_files["gen_totals_team"].append(f"gen_totals/{path.name}")
            groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
            rows_by_date: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
            for row in rows:
                team = self.team_abbr(pick(row, "TEAM_ID", "TeamId"), year, pick(row, "TEAM_ABBREVIATION", "TeamAbbreviation"))
                if team:
                    groups[team].append(row)
                    item = {
                        "row": row,
                        "team": team,
                        "date": clean_date(pick(row, "date", "GAME_DATE")) or "unknown",
                        "pm": safe_float(pick(row, "PLUS_MINUS", "PlusMinus")),
                        "pts": safe_float(pick(row, "PTS", "Points", "POINTS")),
                        "fga": safe_float(pick(row, "FGA")),
                        "fta": safe_float(pick(row, "FTA")),
                        "off": safe_float(pick(row, "OFF_RATING", "sp_work_OFF_RATING", "E_OFF_RATING")),
                        "def": safe_float(pick(row, "DEF_RATING", "sp_work_DEF_RATING", "E_DEF_RATING")),
                        "w": safe_int(pick(row, "W")) or 0,
                        "l": safe_int(pick(row, "L")) or 0,
                    }
                    rows_by_date[item["date"]].append(item)

            allowed_components: Dict[str, Dict[str, float]] = defaultdict(lambda: {"pts": 0.0, "fga": 0.0, "fta": 0.0})
            for date, teams in rows_by_date.items():
                candidates: List[Tuple[float, int, int]] = []
                for i in range(len(teams)):
                    for j in range(i + 1, len(teams)):
                        a, b = teams[i], teams[j]
                        if a["team"] == b["team"]:
                            continue
                        pm_score = 0.0
                        if a["pm"] is not None and b["pm"] is not None:
                            pm_score = abs(a["pm"] + b["pm"])
                            if pm_score > 0.75:
                                continue
                        score = pm_score
                        if a["pts"] is not None and b["pts"] is not None and a["pm"] is not None:
                            score += abs((a["pts"] - b["pts"]) - a["pm"])
                        if a["off"] is not None and b["def"] is not None:
                            score += abs(a["off"] - b["def"]) / 10
                        if a["def"] is not None and b["off"] is not None:
                            score += abs(a["def"] - b["off"]) / 10
                        if a["w"] == b["w"] and a["l"] == b["l"]:
                            score += 25
                        candidates.append((score, i, j))
                used = set()
                for score, i, j in sorted(candidates):
                    if i in used or j in used:
                        continue
                    used.add(i); used.add(j)
                    a, b = teams[i], teams[j]
                    if b["pts"] is not None and b["fga"] is not None and b["fta"] is not None:
                        allowed_components[a["team"]]["pts"] += b["pts"]
                        allowed_components[a["team"]]["fga"] += b["fga"]
                        allowed_components[a["team"]]["fta"] += b["fta"]
                    if a["pts"] is not None and a["fga"] is not None and a["fta"] is not None:
                        allowed_components[b["team"]]["pts"] += a["pts"]
                        allowed_components[b["team"]]["fga"] += a["fga"]
                        allowed_components[b["team"]]["fta"] += a["fta"]

            for team, team_rows in groups.items():
                games = sum((safe_float(pick(r, "GP", "GamesPlayed")) or 1.0) for r in team_rows)
                def w(row: Dict[str, Any]) -> Optional[float]:
                    return safe_float(pick(row, "POSS", "OffPoss", "OffPossessions")) or safe_float(pick(row, "MIN", "Minutes")) or 1.0
                off = weighted_average((safe_float(pick(r, "OFF_RATING", "sp_work_OFF_RATING", "E_OFF_RATING")), w(r)) for r in team_rows)
                deff = weighted_average((safe_float(pick(r, "DEF_RATING", "sp_work_DEF_RATING", "E_DEF_RATING")), w(r)) for r in team_rows)
                net = weighted_average((safe_float(pick(r, "NET_RATING", "sp_work_NET_RATING", "E_NET_RATING")), w(r)) for r in team_rows)
                if net is None and off is not None and deff is not None:
                    net = off - deff
                ts = weighted_average((pct(safe_float(pick(r, "TS_PCT", "TsPct", "TS%"))), w(r)) for r in team_rows)
                efg = weighted_average((pct(safe_float(pick(r, "EFG_PCT", "eFG%"))), w(r)) for r in team_rows)
                pace = weighted_average((safe_float(pick(r, "PACE", "sp_work_PACE", "E_PACE")), w(r)) for r in team_rows)
                allowed = allowed_components.get(team, {})
                ts_allowed = ts_from_points_attempts(allowed.get("pts"), allowed.get("fga"), allowed.get("fta"))
                benchmark = {
                    "benchmarkId": f"{year}_{team}",
                    "year": year,
                    "team": team,
                    "teamName": team,
                    "games": safe_int(games),
                    "ORTG": round_value(off, 1),
                    "DRTG": round_value(deff, 1),
                    "NET": round_value(net, 1),
                    "PACE": round_value(pace, 1),
                    "TS%": round_value(ts, 1),
                    "TS_ALLOWED": round_value(ts_allowed, 1),
                    "eFG%": round_value(efg, 1),
                    "source": f"gen_totals/{path.name}",
                }
                self.upsert_team_benchmark(benchmark, overwrite=True)

    def upsert_rs_team_benchmark(self, benchmark: Dict[str, Any], overwrite: bool = False):
        year = benchmark.get("year")
        team = benchmark.get("team")
        if year not in TARGET_YEARS or not team:
            return
        key = (year, team)
        existing = self.rs_team_benchmarks_by_key.get(key)
        if not existing:
            self.rs_team_benchmarks.append(benchmark)
            self.rs_team_benchmarks_by_key[key] = benchmark
            return
        for field, value in benchmark.items():
            if field in {"benchmarkId", "year", "team"}:
                continue
            if overwrite or existing.get(field) is None:
                if value is not None:
                    existing[field] = value

    def build_regular_season_team_benchmarks(self):
        """Load regular-season opponent benchmarks for playoff translation context.

        rTS should be player TS% minus what the opponent allowed during the
        regular season, not what the opponent allowed in the same playoff run.
        The all_teamyears.csv file is Gabriel's regular-season team page export.
        """
        path = self.player_sheets / "team_totals" / "all_teamyears.csv"
        if not path.exists():
            print("Regular-season team benchmarks unavailable; falling back to playoff context.")
            return
        rows = read_csv(path)
        print(f"Loading regular-season team context from {path.relative_to(self.player_sheets)} ({len(rows)} rows)...")
        self.source_summary["rs_team_rows"] += len(rows)
        self.source_files["regular_season_team_context"].append("team_totals/all_teamyears.csv")

        # Gabriel's all_teamyears.csv carries regular-season team offense and, for newer years,
        # some opponent box columns. For 2001-2013 those OPP_* columns are blank, but the
        # matching {year}vs.csv files contain exactly what opponents produced against each team.
        # Use those vs rows as the primary source for adjusted TS allowed so rAdjTS exists before 2014 too.
        rs_vs_by_key: Dict[Tuple[int, str], Dict[str, Any]] = {}
        team_totals_dir = self.player_sheets / "team_totals"
        for vs_path in sorted(team_totals_dir.glob("[12][0-9][0-9][0-9]vs.csv")):
            year_vs = safe_int(vs_path.name[:4])
            if year_vs not in TARGET_YEARS:
                continue
            vs_rows = read_csv(vs_path)
            if vs_rows:
                self.source_summary["rs_team_vs_rows"] += len(vs_rows)
                self.source_files["regular_season_team_context"].append(f"team_totals/{vs_path.name}")
            for vs_row in vs_rows:
                vs_team = pick(vs_row, "TeamAbbreviation", "TEAM_ABBREVIATION", "ShortName", "Name")
                if vs_team:
                    rs_vs_by_key[(year_vs, str(vs_team).strip().upper())] = vs_row

        for row in rows:
            year = safe_int(pick(row, "year", "season", "SEASON", "YEAR"))
            if year not in TARGET_YEARS:
                continue
            team = pick(row, "TeamAbbreviation", "TEAM_ABBREVIATION", "ShortName", "Name")
            if not team:
                continue
            team = str(team).strip().upper()
            games = safe_int(pick(row, "GamesPlayed", "GP"))
            off_poss = safe_float(pick(row, "OffPoss", "OffPossessions", "POSS"))
            def_poss = safe_float(pick(row, "DefPoss", "DefPossessions"))
            off = safe_float(pick(row, "o_rating", "OFF_RATING", "OffRating", "E_OFF_RATING"))
            deff = safe_float(pick(row, "d_rating", "DEF_RATING", "DefRating", "E_DEF_RATING"))
            net = safe_float(pick(row, "NET_RATING", "net_rating"))
            if net is None and off is not None and deff is not None:
                net = off - deff
            fga = row_total_fga(row)
            fg2a = safe_float(pick(row, "FG2A"))
            fg3a = safe_float(pick(row, "FG3A"))
            fta = safe_float(pick(row, "FTA"))
            fg3_rate = ratio_pct(fg3a, fga)
            ft_rate = fta / fga if fta is not None and fga else None
            opp_fga = safe_float(pick(row, "OPP_FGA"))
            opp_fg3a = safe_float(pick(row, "OPP_FG3A"))
            opp_fta = safe_float(pick(row, "OPP_FTA"))
            opp_fg3_rate = ratio_pct(opp_fg3a, opp_fga)
            opp_ft_rate = opp_fta / opp_fga if opp_fta is not None and opp_fga else None
            vs_row = rs_vs_by_key.get((year, team))
            ts_allowed = team_ts_from_row(vs_row) if vs_row else allowed_ts_from_row(row)
            adj_ts_allowed = adjusted_ts_from_row(vs_row, allow_partial=True) if vs_row else allowed_adjusted_ts_from_row(row)
            adj_allowed_source = f"team_totals/{year}vs.csv opponent allowed adjusted profile" if vs_row else "opponent box fallback: OPP_PTS / [2*(OPP_FGA+OPP_TOV+0.44*OPP_FTA)]"
            benchmark = {
                "benchmarkId": f"RS_{year}_{team}",
                "year": year,
                "team": team,
                "teamName": pick(row, "Name", "TeamName") or team,
                "games": games,
                "ORTG": round_value(off, 1),
                "DRTG": round_value(deff, 1),
                "NET": round_value(net, 1),
                "PACE": round_value(safe_float(pick(row, "Pace", "PACE")), 1),
                "TS%": round_value(team_ts_from_row(row), 1),
                "ADJ_TS%": round_value(adjusted_ts_from_row(row, allow_partial=True), 1),
                "TS_ALLOWED": round_value(ts_allowed, 1),
                "ADJ_TS_ALLOWED": round_value(adj_ts_allowed, 1),
                "ADJ_TS_ALLOWED_SOURCE": adj_allowed_source,
                "eFG%": round_value(efg_from_row(row), 1),
                "RIM_FREQ": round_value(rim_frequency_from_row(row), 1),
                "RIM_ACC": round_value(rim_accuracy_from_row(row), 1),
                "ORB%": round_value(pct(safe_float(pick(row, "OffFGReboundPct", "OREB_PCT", "ORebPct"))), 1),
                "DREB%": round_value(pct(safe_float(pick(row, "DefFGReboundPct", "DREB_PCT", "DRebPct"))), 1),
                "3PA_RATE": round_value(fg3_rate, 1),
                "FTA_RATE": round_value(ft_rate, 2),
                "OPP_3PA_RATE": round_value(opp_fg3_rate, 1),
                "OPP_FTA_RATE": round_value(opp_ft_rate, 2),
                "context": "regular season",
                "source": "team_totals/all_teamyears.csv",
            }
            self.upsert_rs_team_benchmark(benchmark, overwrite=True)

        by_year: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
        for b in self.rs_team_benchmarks:
            by_year[b["year"]].append(b)
        self.rs_team_benchmarks_by_year = {}
        for year, rows_for_year in by_year.items():
            def w(row: Dict[str, Any]) -> Optional[float]:
                return safe_float(row.get("games")) or 1.0
            self.rs_team_benchmarks_by_year[year] = {
                "year": year,
                "team": "LEAGUE_RS",
                "teamName": "Regular Season League Average",
                "ORTG": weighted_average((r.get("ORTG"), w(r)) for r in rows_for_year),
                "DRTG": weighted_average((r.get("DRTG"), w(r)) for r in rows_for_year),
                "TS%": weighted_average((r.get("TS%"), w(r)) for r in rows_for_year),
                "ADJ_TS%": weighted_average((r.get("ADJ_TS%"), w(r)) for r in rows_for_year),
                "TS_ALLOWED": weighted_average((r.get("TS_ALLOWED"), w(r)) for r in rows_for_year),
                "ADJ_TS_ALLOWED": weighted_average((r.get("ADJ_TS_ALLOWED"), w(r)) for r in rows_for_year),
                "eFG%": weighted_average((r.get("eFG%"), w(r)) for r in rows_for_year),
                "context": "regular season league average",
            }

    def build_league_benchmarks(self):
        by_year: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
        for b in self.team_benchmarks:
            if b.get("year") in TARGET_YEARS:
                by_year[b["year"]].append(b)
        self.team_benchmarks_by_year = {}
        for year, rows in by_year.items():
            def w(row: Dict[str, Any]) -> Optional[float]:
                return safe_float(row.get("games")) or 1.0
            off = weighted_average((r.get("ORTG"), w(r)) for r in rows)
            deff = weighted_average((r.get("DRTG"), w(r)) for r in rows)
            ts = weighted_average((r.get("TS%"), w(r)) for r in rows)
            ts_allowed = weighted_average((r.get("TS_ALLOWED"), w(r)) for r in rows)
            efg = weighted_average((r.get("eFG%"), w(r)) for r in rows)
            self.team_benchmarks_by_year[year] = {
                "year": year,
                "team": "PLAYOFF_AVG",
                "ORTG": off,
                "DRTG": deff,
                "TS%": ts,
                "TS_ALLOWED": ts_allowed,
                "eFG%": efg,
            }

    def context_benchmark(self, year: Optional[int], opponent: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if year not in TARGET_YEARS:
            return None
        if opponent:
            team = str(opponent).strip().upper()
            # Primary translation context: the opponent's regular-season team page.
            # This fixes inflated/deflated rTS from using tiny playoff-series samples.
            rs_bench = self.rs_team_benchmarks_by_key.get((year, team))
            if rs_bench and (rs_bench.get("ORTG") is not None or rs_bench.get("DRTG") is not None or rs_bench.get("TS_ALLOWED") is not None):
                return rs_bench
            # Fallback for years/teams where regular-season context is missing.
            bench = self.team_benchmarks_by_key.get((year, team))
            if bench and (bench.get("ORTG") is not None or bench.get("DRTG") is not None):
                return bench
        return self.rs_team_benchmarks_by_year.get(year) or self.team_benchmarks_by_year.get(year)

    def relative_stats(self, year: Optional[int], opponent: Optional[str], off: Optional[float], deff: Optional[float], ts: Optional[float]) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
        bench = self.context_benchmark(year, opponent)
        r_ortg = off - bench["DRTG"] if off is not None and bench and bench.get("DRTG") is not None else None
        r_drtg = bench["ORTG"] - deff if deff is not None and bench and bench.get("ORTG") is not None else None
        r_net = r_ortg + r_drtg if r_ortg is not None and r_drtg is not None else None
        ts_allowed = bench.get("TS_ALLOWED") if bench else None
        if ts_allowed is None and bench:
            ts_allowed = bench.get("TS%")
        r_ts = ts - ts_allowed if ts is not None and ts_allowed is not None else None
        return r_ortg, r_drtg, r_net, r_ts

    def adjusted_ts_allowed_benchmark(self, year: Optional[int], opponent: Optional[str]) -> Optional[float]:
        bench = self.context_benchmark(year, opponent)
        if not bench:
            return None
        allowed = bench.get("ADJ_TS_ALLOWED")
        if allowed is None:
            allowed = bench.get("TS_ALLOWED") or bench.get("TS%")
        return allowed

    def relative_adjusted_ts(self, year: Optional[int], opponent: Optional[str], adj_ts: Optional[float]) -> Optional[float]:
        if adj_ts is None:
            return None
        allowed = self.adjusted_ts_allowed_benchmark(year, opponent)
        return adj_ts - allowed if allowed is not None else None

    def build_team_benchmarks(self):
        self.build_regular_season_team_benchmarks()
        self.aggregate_gen_team_benchmarks()
        folder = self.player_sheets / "team_totals"
        files = sorted(folder.glob("*ps_team_totals.csv"))
        print(f"Loading playoff team benchmarks from {len(files)} team_totals files...")
        for path in files:
            year_match = re.search(r"(\d{4})ps_team_totals", path.name)
            if not year_match:
                continue
            year = int(year_match.group(1))
            if year not in TARGET_YEARS:
                continue
            rows = read_csv(path)
            self.source_summary["team_totals_files"] += 1
            self.source_summary["team_totals_rows"] += len(rows)
            self.source_files["team_totals"].append(f"team_totals/{path.name}")
            for row in rows:
                team = pick(row, "TEAM_ABBREVIATION", "TeamAbbreviation", "Name", "ShortName")
                if not team:
                    continue
                team = str(team).strip()
                team_name = pick(row, "TEAM_NAME", "Name", "ShortName") or team
                off = safe_float(pick(row, "OFF_RATING", "sp_work_OFF_RATING", "E_OFF_RATING", "ortg"))
                deff = safe_float(pick(row, "DEF_RATING", "sp_work_DEF_RATING", "E_DEF_RATING", "drtg"))
                net = safe_float(pick(row, "NET_RATING", "sp_work_NET_RATING", "E_NET_RATING"))
                if net is None and off is not None and deff is not None:
                    net = off - deff
                ts = pct(safe_float(pick(row, "TS_PCT", "TsPct", "TS%")))
                ts_allowed = allowed_ts_from_row(row)
                efg = pct(safe_float(pick(row, "EFG_PCT", "eFG%")))
                benchmark = {
                    "benchmarkId": f"{year}_{team}",
                    "year": year,
                    "team": team,
                    "teamName": str(team_name),
                    "games": safe_int(pick(row, "GP", "GamesPlayed")),
                    "ORTG": round_value(off, 1),
                    "DRTG": round_value(deff, 1),
                    "NET": round_value(net, 1),
                    "PACE": round_value(safe_float(pick(row, "PACE", "sp_work_PACE", "E_PACE")), 1),
                    "TS%": round_value(ts, 1),
                    "TS_ALLOWED": round_value(ts_allowed, 1),
                    "eFG%": round_value(efg, 1),
                    "source": f"team_totals/{path.name}",
                }
                self.upsert_team_benchmark(benchmark, overwrite=False)
        self.build_league_benchmarks()

    def build_seasons(self):
        files = sorted((self.player_sheets / "totals").glob("*_ps.csv"))
        print(f"Loading playoff season totals from {len(files)} player files...")
        seen: set[Tuple[str, int, str]] = set()
        for path in files:
            rows = read_csv(path)
            self.source_summary["totals_files"] += 1
            self.source_summary["totals_rows"] += len(rows)
            if rows:
                self.source_files["totals"].append(f"totals/{path.name}")
            for row in rows:
                year = safe_int(pick(row, "year", "SEASON", "Season", "YEAR"))
                if year not in TARGET_YEARS:
                    continue
                name = pick(row, "PLAYER_NAME", "Player", "player", "Name")
                nba_id = pick(row, "PLAYER_ID", "nba_id", "EntityId")
                if not name:
                    continue
                player_id = self.player_id(str(name), str(nba_id) if nba_id is not None else None)
                team = pick(row, "TEAM_ABBREVIATION", "TeamAbbreviation", "team", "TEAM")
                team = str(team).strip() if team else None
                key = (player_id, year, team or "")
                if key in seen:
                    continue
                seen.add(key)
                gp = safe_float(pick(row, "GP", "GamesPlayed"))
                poss = safe_float(pick(row, "POSS", "OffPoss", "OffPossessions"))
                minutes_total = safe_float(pick(row, "MIN", "Minutes"))
                minutes_pg = minutes_total / gp if minutes_total is not None and gp and gp > 0 else minutes_total
                pts = safe_float(pick(row, "PTS", "Points", "POINTS"))
                reb = safe_float(pick(row, "REB", "Rebounds"))
                ast = safe_float(pick(row, "AST", "Assists"))
                tov = safe_float(pick(row, "TOV", "Turnovers"))
                fgm = safe_float(pick(row, "FGM"))
                fga = row_total_fga(row)
                fg3m = safe_float(pick(row, "FG3M"))
                fta = safe_float(pick(row, "FTA"))
                ts = pct(safe_float(pick(row, "TS_PCT", "TsPct", "TS%")))
                if ts is None and pts is not None and fga and fta is not None and (fga + 0.44 * fta) > 0:
                    ts = 100 * pts / (2 * (fga + 0.44 * fta))
                efg = pct(safe_float(pick(row, "EFG_PCT", "eFG%")))
                if efg is None and fgm is not None and fga and fg3m is not None and fga > 0:
                    efg = 100 * (fgm + 0.5 * fg3m) / fga
                detail_row = self.detailed_player_row(year, self.players[player_id].get("nbaId") or nba_id, team)
                if detail_row:
                    adj_source = detail_row
                    adj_ts = adjusted_ts_from_row(adj_source, allow_partial=True)
                    adj_components = adjustment_components_from_row(adj_source) if adj_ts is not None else {}
                    adj_ts_source = "season-level verified gen_totals postseason PBP adjustment (scoring TOV, heaves, Z Bounds, tech FTA)" if adj_ts is not None else None
                else:
                    adj_source = None
                    adj_ts = None
                    adj_components = {}
                    adj_ts_source = "unavailable: detailed postseason PBP adjustment ingredients are not present for this player-season"
                rim_freq = rim_frequency_from_row(row)
                rim_acc = rim_accuracy_from_row(row)
                orb_pct = pct(safe_float(pick(row, "OREB_PCT", "OffFGReboundPct", "ORebPct")))
                dreb_pct = pct(safe_float(pick(row, "DREB_PCT", "DefFGReboundPct", "DRebPct")))
                ast_pct = pct(safe_float(pick(row, "AST_PCT", "AstPct")))
                usg_pct = pct(safe_float(pick(row, "USG_PCT", "Usage", "UsagePct")))
                off = safe_float(pick(row, "OFF_RATING", "sp_work_OFF_RATING", "E_OFF_RATING"))
                deff = safe_float(pick(row, "DEF_RATING", "sp_work_DEF_RATING", "E_DEF_RATING"))
                net = safe_float(pick(row, "NET_RATING", "sp_work_NET_RATING", "E_NET_RATING"))
                if net is None and off is not None and deff is not None:
                    net = off - deff
                season = {
                    "playerId": player_id,
                    "nbaId": self.players[player_id].get("nbaId"),
                    "playerName": self.players[player_id]["name"],
                    "year": year,
                    "team": team,
                    "GP": safe_int(gp),
                    "W": safe_int(pick(row, "W")),
                    "MIN": round_value(minutes_pg, 1),
                    "PTS/75": round_value(per75(pts, poss), 1),
                    "REB/75": round_value(per75(reb, poss), 1),
                    "AST/75": round_value(per75(ast, poss), 1),
                    "TOV/75": round_value(per75(tov, poss), 1),
                    "TS%": round_value(ts, 1),
                    "AdjTS%": round_value(adj_ts, 1),
                    "AdjTS_source": adj_ts_source if adj_ts is not None else None,
                    "AdjFGA": adj_components.get("adjFGA"),
                    "ScoringTOV": adj_components.get("scoringTOV"),
                    "Heaves": adj_components.get("heaves"),
                    "ZBoards": adj_components.get("zBoards"),
                    "AdjFTA": adj_components.get("adjFTA"),
                    "TechFTA": adj_components.get("techFTA"),
                    "eFG%": round_value(efg, 1),
                    "RIM_FREQ": round_value(rim_freq, 1),
                    "RIM_ACC": round_value(rim_acc, 1),
                    "ORB%": round_value(orb_pct, 1),
                    "DREB%": round_value(dreb_pct, 1),
                    "AST%": round_value(ast_pct, 1),
                    "USG%": round_value(usg_pct, 1),
                    "ORTG": round_value(off, 1),
                    "DRTG": round_value(deff, 1),
                    "NET": round_value(net, 1),
                    "PTS": round_value(pts, 0),
                    "REB": round_value(reb, 0),
                    "AST": round_value(ast, 0),
                    "TOV": round_value(tov, 0),
                    "POSS": round_value(poss, 0),
                    "source": f"totals/{path.name}",
                    "sourceLevel": "season",
                }
                self.seasons.append(season)
                self.touch_player(player_id, year, team)

        # finalize player season counts
        for player in self.players.values():
            player["years"] = sorted(player["years"])
            player["teams"] = sorted(player["teams"])
            player["seasonCount"] = len(player["years"])

    def build_gen_team_game_context(self):
        if self.team_game_context or not GEN_TOTALS_DIR.exists():
            return
        print("Inferring playoff game opponents and series rounds from gen_totals team-game files...")
        team_pair_dates: Dict[Tuple[int, str, str], str] = {}
        for path in sorted(GEN_TOTALS_DIR.glob("[12][0-9][0-9][0-9]team.csv")):
            year = safe_int(path.stem.replace("team", ""))
            if year not in TARGET_YEARS:
                continue
            rows_by_date: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
            for row in read_csv(path):
                date = clean_date(pick(row, "date", "GAME_DATE"))
                team = self.team_abbr(pick(row, "TEAM_ID", "TeamId"), year, pick(row, "TEAM_ABBREVIATION", "TeamAbbreviation"))
                if not date or not team:
                    continue
                item = {
                    "date": date,
                    "team": team,
                    "pm": safe_float(pick(row, "PLUS_MINUS", "PlusMinus")),
                    "pts": safe_float(pick(row, "PTS", "Points")),
                    "off": safe_float(pick(row, "OFF_RATING", "sp_work_OFF_RATING", "E_OFF_RATING")),
                    "def": safe_float(pick(row, "DEF_RATING", "sp_work_DEF_RATING", "E_DEF_RATING")),
                    "net": safe_float(pick(row, "NET_RATING", "sp_work_NET_RATING", "E_NET_RATING")),
                    "ts": team_ts_from_row(row),
                    "adj_ts": adjusted_ts_from_row(row, allow_partial=False),
                    "efg": efg_from_row(row),
                    "rim_freq": rim_frequency_from_row(row),
                    "rim_acc": rim_accuracy_from_row(row),
                    "orb": pct(safe_float(pick(row, "OffFGReboundPct", "OREB_PCT", "ORebPct"))),
                    "dreb": pct(safe_float(pick(row, "DefFGReboundPct", "DREB_PCT", "DRebPct"))),
                    "fga": row_total_fga(row),
                    "fta": safe_float(pick(row, "FTA")),
                    "w": safe_int(pick(row, "W")) or 0,
                    "l": safe_int(pick(row, "L")) or 0,
                }
                rows_by_date[date].append(item)

            for date, teams in rows_by_date.items():
                candidates: List[Tuple[float, int, int]] = []
                for i in range(len(teams)):
                    for j in range(i + 1, len(teams)):
                        a, b = teams[i], teams[j]
                        if a["team"] == b["team"]:
                            continue
                        pm_score = 0.0
                        if a["pm"] is not None and b["pm"] is not None:
                            pm_score = abs(a["pm"] + b["pm"])
                            if pm_score > 0.75:
                                continue
                        score = pm_score
                        if a["pts"] is not None and b["pts"] is not None and a["pm"] is not None:
                            score += abs((a["pts"] - b["pts"]) - a["pm"])
                        if a["off"] is not None and b["def"] is not None:
                            score += abs(a["off"] - b["def"]) / 10
                        if a["def"] is not None and b["off"] is not None:
                            score += abs(a["def"] - b["off"]) / 10
                        if a["w"] == b["w"] and a["l"] == b["l"]:
                            score += 25
                        candidates.append((score, i, j))
                used = set()
                for score, i, j in sorted(candidates):
                    if i in used or j in used:
                        continue
                    used.add(i); used.add(j)
                    a, b = teams[i], teams[j]
                    pair = tuple(sorted([a["team"], b["team"]]))
                    game_id = f"gen_{year}_{date.replace('-', '')}_{pair[0]}_{pair[1]}"
                    for src, dst in [(a, b), (b, a)]:
                        src_net = src.get("net")
                        if src_net is None and src.get("off") is not None and src.get("def") is not None:
                            src_net = src["off"] - src["def"]
                        dst_net = dst.get("net")
                        if dst_net is None and dst.get("off") is not None and dst.get("def") is not None:
                            dst_net = dst["off"] - dst["def"]
                        self.team_game_context[(year, date, src["team"])] = {
                            "opponent": dst["team"],
                            "gameId": game_id,
                            "result": "W" if src["w"] > src["l"] else "L" if src["l"] > src["w"] else None,
                            "teamORTG": round_value(src.get("off"), 1),
                            "teamDRTG": round_value(src.get("def"), 1),
                            "teamNET": round_value(src_net, 1),
                            "teamTS%": round_value(src.get("ts"), 1),
                            "teamAdjTS%": round_value(src.get("adj_ts"), 1),
                            "teamEFG%": round_value(src.get("efg"), 1),
                            "teamRimFreq": round_value(src.get("rim_freq"), 1),
                            "teamRimAcc": round_value(src.get("rim_acc"), 1),
                            "teamORB%": round_value(src.get("orb"), 1),
                            "teamDREB%": round_value(src.get("dreb"), 1),
                            "oppTeamORTG": round_value(dst.get("off"), 1),
                            "oppTeamDRTG": round_value(dst.get("def"), 1),
                            "oppTeamNET": round_value(dst_net, 1),
                            "oppTeamTS%": round_value(dst.get("ts"), 1),
                            "oppTeamAdjTS%": round_value(dst.get("adj_ts"), 1),
                            "oppRimFreqAllowed": round_value(dst.get("rim_freq"), 1),
                            "oppRimAccAllowed": round_value(dst.get("rim_acc"), 1),
                            "teamContextSource": "gen_totals team-game context",
                        }
                        matchup_key = (year, src["team"], dst["team"])
                        if matchup_key not in team_pair_dates:
                            team_pair_dates[matchup_key] = date

        # Assign audience-friendly round labels based on each team's opponent order.
        by_team: Dict[Tuple[int, str], List[Tuple[str, str]]] = defaultdict(list)
        for (year, team, opp), first_date in team_pair_dates.items():
            by_team[(year, team)].append((first_date, opp))
        round_context: Dict[Tuple[int, str, str], Dict[str, Any]] = {}
        for (year, team), entries in by_team.items():
            seen_opps = []
            for first_date, opp in sorted(entries):
                if opp not in seen_opps:
                    seen_opps.append(opp)
            for idx, opp in enumerate(seen_opps, 1):
                round_context[(year, team, opp)] = {
                    "roundSort": idx,
                    "round": ROUND_LABELS.get(str(idx), "NBA Finals" if idx == 4 else "Playoff Series"),
                    "seriesCode": f"R{idx}_{opp}",
                }
        for key, ctx in list(self.team_game_context.items()):
            year, date, team = key
            opp = ctx.get("opponent")
            ctx.update(round_context.get((year, team, opp), {"roundSort": 9, "round": "Playoff Series", "seriesCode": "series"}))

    def add_game_row(self, game: Dict[str, Any]):
        key = (
            game.get("playerId"),
            game.get("year"),
            game.get("date") or "",
            game.get("team") or "",
            game.get("opponent") or "",
        )
        if key in self.game_keys_seen:
            return
        self.game_keys_seen.add(key)
        self.games.append(game)
        player_id = game.get("playerId")
        if player_id in self.players:
            self.players[player_id]["gameRowCount"] = self.players[player_id].get("gameRowCount", 0) + 1
            self.touch_player(player_id, game.get("year"), game.get("team"))

    def build_games_from_gen_totals(self):
        folder = GEN_TOTALS_DIR
        if not folder.exists():
            return
        self.build_gen_team_game_context()
        files = sorted(folder.glob("[12][0-9][0-9][0-9].csv"))
        print(f"Loading playoff game logs from {len(files)} gen_totals player-game files...")
        for path in files:
            year = safe_int(path.stem)
            if year not in TARGET_YEARS:
                continue
            rows = read_csv(path)
            if not rows:
                continue
            self.source_summary["gen_game_files"] += 1
            self.source_summary["gen_game_rows"] += len(rows)
            self.source_files["gen_totals_games"].append(f"gen_totals/{path.name}")
            for row in rows:
                name = pick(row, "PLAYER_NAME", "Player", "Name")
                nba_id = pick(row, "PLAYER_ID", "nba_id", "EntityId")
                if not name:
                    continue
                player_id = self.player_id(str(name), str(nba_id) if nba_id is not None else None)
                team = pick(row, "TEAM_ABBREVIATION", "TeamAbbreviation", "TeamAbbr")
                team = str(team).strip() if team else self.team_abbr(pick(row, "TEAM_ID", "TeamId"), year)
                date = clean_date(pick(row, "date", "GAME_DATE"))
                ctx = self.team_game_context.get((year, date or "", team or ""), {})
                opp = ctx.get("opponent")
                poss = safe_float(pick(row, "POSS", "OffPoss", "OffPossessions"))
                pts = safe_float(pick(row, "PTS", "Points", "POINTS"))
                reb = safe_float(pick(row, "REB", "Rebounds"))
                ast = safe_float(pick(row, "AST", "Assists"))
                tov = safe_float(pick(row, "TOV", "Turnovers"))
                minv = safe_float(pick(row, "MIN", "Minutes"))
                fgm = safe_float(pick(row, "FGM"))
                fga = row_total_fga(row)
                fg3m = safe_float(pick(row, "FG3M"))
                fta = safe_float(pick(row, "FTA"))
                ts = pct(safe_float(pick(row, "TS_PCT", "TsPct", "TS%")))
                if ts is None and pts is not None and fga and fta is not None and (fga + 0.44 * fta) > 0:
                    ts = 100 * pts / (2 * (fga + 0.44 * fta))
                efg = pct(safe_float(pick(row, "EFG_PCT", "eFG%", "EFF_FG_PCT")))
                if efg is None and fgm is not None and fga and fg3m is not None and fga > 0:
                    efg = 100 * (fgm + 0.5 * fg3m) / fga
                # Game rows currently do not carry the full adjusted-TS component set.
                # Do not show AdjTS = TS or total-turnover fallbacks as real adjusted TS.
                adj_ts = adjusted_ts_from_row(row, allow_partial=False)
                adj_components = adjustment_components_from_row(row) if adj_ts is not None else {}
                adj_ts_source = "verified game-level adjusted TS components" if adj_ts is not None else "unavailable: game rows do not include scoring-TOV/heave/Z Bound/tech-FTA ingredients"
                rim_freq = rim_frequency_from_row(row)
                rim_acc = rim_accuracy_from_row(row)
                orb_pct = pct(safe_float(pick(row, "OREB_PCT", "OffFGReboundPct", "ORebPct")))
                dreb_pct = pct(safe_float(pick(row, "DREB_PCT", "DefFGReboundPct", "DRebPct")))
                ast_pct = pct(safe_float(pick(row, "AST_PCT", "AstPct")))
                usg_pct = pct(safe_float(pick(row, "USG_PCT", "Usage", "UsagePct")))
                off = safe_float(pick(row, "OFF_RATING", "sp_work_OFF_RATING", "E_OFF_RATING"))
                deff = safe_float(pick(row, "DEF_RATING", "sp_work_DEF_RATING", "E_DEF_RATING"))
                net = safe_float(pick(row, "NET_RATING", "sp_work_NET_RATING", "E_NET_RATING"))
                if net is None and off is not None and deff is not None:
                    net = off - deff
                r_ortg, r_drtg, r_net, r_ts = self.relative_stats(year, opp, off, deff, ts)
                r_adj_ts = self.relative_adjusted_ts(year, opp, adj_ts)
                opp_adj_allowed = self.adjusted_ts_allowed_benchmark(year, opp)
                win = safe_int(pick(row, "W")) or 0
                loss = safe_int(pick(row, "L")) or 0
                result = ctx.get("result") or ("W" if win > loss else "L" if loss > win else None)
                game_id = ctx.get("gameId") or f"gen_{year}_{(date or 'date').replace('-', '')}_{team or 'TEAM'}"
                game = {
                    "gameRowId": f"{game_id}_{player_id}",
                    "gameId": game_id,
                    "playerId": player_id,
                    "nbaId": self.players[player_id].get("nbaId"),
                    "playerName": self.players[player_id]["name"],
                    "year": year,
                    "date": date,
                    "round": ctx.get("round") or "Playoff Series",
                    "roundSort": ctx.get("roundSort") or 9,
                    "seriesCode": ctx.get("seriesCode") or "series",
                    "team": team,
                    "opponent": opp,
                    "result": result,
                    "MIN": round_value(minv, 1),
                    "PTS": round_value(pts, 0),
                    "REB": round_value(reb, 0),
                    "AST": round_value(ast, 0),
                    "TOV": round_value(tov, 0),
                    "PTS/75": round_value(per75(pts, poss), 1),
                    "REB/75": round_value(per75(reb, poss), 1),
                    "AST/75": round_value(per75(ast, poss), 1),
                    "TOV/75": round_value(per75(tov, poss), 1),
                    "TS%": round_value(ts, 1),
                    "AdjTS%": round_value(adj_ts, 1),
                    "AdjTS_source": adj_ts_source,
                    "AdjFGA": adj_components.get("adjFGA"),
                    "ScoringTOV": adj_components.get("scoringTOV"),
                    "Heaves": adj_components.get("heaves"),
                    "ZBoards": adj_components.get("zBoards"),
                    "AdjFTA": adj_components.get("adjFTA"),
                    "TechFTA": adj_components.get("techFTA"),
                    "eFG%": round_value(efg, 1),
                    "RIM_FREQ": round_value(rim_freq, 1),
                    "RIM_ACC": round_value(rim_acc, 1),
                    "ORB%": round_value(orb_pct, 1),
                    "DREB%": round_value(dreb_pct, 1),
                    "AST%": round_value(ast_pct, 1),
                    "USG%": round_value(usg_pct, 1),
                    "ORTG": round_value(off, 1),
                    "DRTG": round_value(deff, 1),
                    "NET": round_value(net, 1),
                    "rORTG": round_value(r_ortg, 1),
                    "rDRTG": round_value(r_drtg, 1),
                    "rNET": round_value(r_net, 1),
                    "rTS": round_value(r_ts, 1),
                    "rAdjTS": round_value(r_adj_ts, 1),
                    "OppRSAdjTSAllowed": round_value(opp_adj_allowed, 1),
                    "POSS": round_value(poss, 0),
                    "FGM": round_value(fgm, 0),
                    "FGA": round_value(fga, 0),
                    "FG3M": round_value(fg3m, 0),
                    "FTA": round_value(fta, 0),
                    "teamORTG": ctx.get("teamORTG"),
                    "teamDRTG": ctx.get("teamDRTG"),
                    "teamNET": ctx.get("teamNET"),
                    "teamTS%": ctx.get("teamTS%"),
                    "teamAdjTS%": ctx.get("teamAdjTS%"),
                    "teamRimFreq": ctx.get("teamRimFreq"),
                    "teamRimAcc": ctx.get("teamRimAcc"),
                    "teamORB%": ctx.get("teamORB%"),
                    "teamDREB%": ctx.get("teamDREB%"),
                    "oppTeamTS%": ctx.get("oppTeamTS%"),
                    "oppTeamAdjTS%": ctx.get("oppTeamAdjTS%"),
                    "oppRimFreqAllowed": ctx.get("oppRimFreqAllowed"),
                    "oppRimAccAllowed": ctx.get("oppRimAccAllowed"),
                    "teamContextSource": ctx.get("teamContextSource"),
                    "source": f"gen_totals/{path.name}",
                    "sourceLevel": "game",
                }
                self.add_game_row(game)

    def build_games(self):
        self.build_games_from_gen_totals()
        folder = self.player_sheets / "game_report"
        # gen_totals has stronger normalized game logs for 1997–2024.
        # Use game_report only for years not already covered there (mainly latest seasons)
        # so rebuilds stay fast and duplicate/incompatible box rows do not override normalized rows.
        gen_game_years = {safe_int(p.stem) for p in GEN_TOTALS_DIR.glob("[12][0-9][0-9][0-9].csv")} if GEN_TOTALS_DIR.exists() else set()
        files = sorted(p for p in folder.glob("*/*.csv") if p.name[:1] == "4" and safe_int(p.parent.name) not in gen_game_years)
        print(f"Loading supplemental playoff game logs from {len(files)} game_report files...")
        for path in files:
            rows = read_csv(path)
            if not rows:
                continue
            year = safe_int(path.parent.name)
            if year not in TARGET_YEARS:
                continue
            game_id = path.stem
            series_code, round_label, round_sort = playoff_round_from_game_id(game_id)
            teams_in_file = sorted({str(pick(r, "TEAM_ABBREVIATION", "TeamAbbreviation") or "").strip() for r in rows if str(pick(r, "TEAM_ABBREVIATION", "TeamAbbreviation") or "").strip()})
            file_opponents = {}
            if len(teams_in_file) == 2:
                file_opponents = {teams_in_file[0]: teams_in_file[1], teams_in_file[1]: teams_in_file[0]}
            self.source_summary["game_report_files"] += 1
            self.source_summary["game_report_rows"] += len(rows)
            self.source_files["game_report"].append(f"game_report/{year}/{path.name}")
            for row in rows:
                name = pick(row, "PLAYER_NAME", "Player", "Name")
                nba_id = pick(row, "PLAYER_ID", "nba_id")
                if not name:
                    continue
                player_id = self.player_id(str(name), str(nba_id) if nba_id is not None else None)
                team = pick(row, "TEAM_ABBREVIATION", "TeamAbbreviation")
                opp = pick(row, "opp_team", "OPP", "Opponent")
                team = str(team).strip() if team else None
                opp = str(opp).strip() if opp else file_opponents.get(team)
                poss = safe_float(pick(row, "POSS", "OffPoss"))
                pts = safe_float(pick(row, "PTS", "Points", "POINTS"))
                reb = safe_float(pick(row, "REB"))
                ast = safe_float(pick(row, "AST"))
                tov = safe_float(pick(row, "TOV", "Turnovers"))
                minv = safe_float(pick(row, "MIN", "Minutes"))
                fgm = safe_float(pick(row, "FGM"))
                fga = row_total_fga(row)
                fg3m = safe_float(pick(row, "FG3M"))
                fta = safe_float(pick(row, "FTA"))
                ts = pct(safe_float(pick(row, "TS_PCT", "TsPct", "TS%")))
                if ts is None and pts is not None and fga and fta is not None and (fga + 0.44 * fta) > 0:
                    ts = 100 * pts / (2 * (fga + 0.44 * fta))
                efg = pct(safe_float(pick(row, "EFG_PCT", "eFG%")))
                if efg is None and fgm is not None and fga and fg3m is not None and fga > 0:
                    efg = 100 * (fgm + 0.5 * fg3m) / fga
                # Game rows currently do not carry the full adjusted-TS component set.
                # Do not show AdjTS = TS or total-turnover fallbacks as real adjusted TS.
                adj_ts = adjusted_ts_from_row(row, allow_partial=False)
                adj_components = adjustment_components_from_row(row) if adj_ts is not None else {}
                adj_ts_source = "verified game-level adjusted TS components" if adj_ts is not None else "unavailable: game rows do not include scoring-TOV/heave/Z Bound/tech-FTA ingredients"
                rim_freq = rim_frequency_from_row(row)
                rim_acc = rim_accuracy_from_row(row)
                orb_pct = pct(safe_float(pick(row, "OREB_PCT", "OffFGReboundPct", "ORebPct")))
                dreb_pct = pct(safe_float(pick(row, "DREB_PCT", "DefFGReboundPct", "DRebPct")))
                ast_pct = pct(safe_float(pick(row, "AST_PCT", "AstPct")))
                usg_pct = pct(safe_float(pick(row, "USG_PCT", "Usage", "UsagePct")))
                off = safe_float(pick(row, "OFF_RATING", "sp_work_OFF_RATING", "E_OFF_RATING"))
                deff = safe_float(pick(row, "DEF_RATING", "sp_work_DEF_RATING", "E_DEF_RATING"))
                net = safe_float(pick(row, "NET_RATING", "sp_work_NET_RATING", "E_NET_RATING"))
                if net is None and off is not None and deff is not None:
                    net = off - deff
                r_ortg, r_drtg, r_net, r_ts = self.relative_stats(year, opp, off, deff, ts)
                r_adj_ts = self.relative_adjusted_ts(year, opp, adj_ts)
                opp_adj_allowed = self.adjusted_ts_allowed_benchmark(year, opp)
                win = safe_int(pick(row, "W")) or 0
                loss = safe_int(pick(row, "L")) or 0
                result = "W" if win > loss else "L" if loss > win else None
                game = {
                    "gameRowId": f"{game_id}_{player_id}",
                    "gameId": game_id,
                    "playerId": player_id,
                    "nbaId": self.players[player_id].get("nbaId"),
                    "playerName": self.players[player_id]["name"],
                    "year": year,
                    "date": clean_date(pick(row, "date", "GAME_DATE")),
                    "round": round_label,
                    "roundSort": round_sort,
                    "seriesCode": series_code,
                    "team": team,
                    "opponent": opp,
                    "result": result,
                    "MIN": round_value(minv, 1),
                    "PTS": round_value(pts, 0),
                    "REB": round_value(reb, 0),
                    "AST": round_value(ast, 0),
                    "TOV": round_value(tov, 0),
                    "PTS/75": round_value(per75(pts, poss), 1),
                    "REB/75": round_value(per75(reb, poss), 1),
                    "AST/75": round_value(per75(ast, poss), 1),
                    "TOV/75": round_value(per75(tov, poss), 1),
                    "TS%": round_value(ts, 1),
                    "AdjTS%": round_value(adj_ts, 1),
                    "AdjTS_source": adj_ts_source,
                    "AdjFGA": adj_components.get("adjFGA"),
                    "ScoringTOV": adj_components.get("scoringTOV"),
                    "Heaves": adj_components.get("heaves"),
                    "ZBoards": adj_components.get("zBoards"),
                    "AdjFTA": adj_components.get("adjFTA"),
                    "TechFTA": adj_components.get("techFTA"),
                    "eFG%": round_value(efg, 1),
                    "RIM_FREQ": round_value(rim_freq, 1),
                    "RIM_ACC": round_value(rim_acc, 1),
                    "ORB%": round_value(orb_pct, 1),
                    "DREB%": round_value(dreb_pct, 1),
                    "AST%": round_value(ast_pct, 1),
                    "USG%": round_value(usg_pct, 1),
                    "ORTG": round_value(off, 1),
                    "DRTG": round_value(deff, 1),
                    "NET": round_value(net, 1),
                    "rORTG": round_value(r_ortg, 1),
                    "rDRTG": round_value(r_drtg, 1),
                    "rNET": round_value(r_net, 1),
                    "rTS": round_value(r_ts, 1),
                    "rAdjTS": round_value(r_adj_ts, 1),
                    "OppRSAdjTSAllowed": round_value(opp_adj_allowed, 1),
                    "POSS": round_value(poss, 0),
                    "FGM": round_value(fgm, 0),
                    "FGA": round_value(fga, 0),
                    "FG3M": round_value(fg3m, 0),
                    "FTA": round_value(fta, 0),
                    "source": f"game_report/{year}/{path.name}",
                    "sourceLevel": "game",
                }
                self.add_game_row(game)

    def add_relative_stats_to_seasons(self):
        print("Adding opponent-adjusted rORTG/rDRTG/rNET/rTS to season rows...")
        games_by_exact: Dict[Tuple[str, int, str], List[Dict[str, Any]]] = defaultdict(list)
        games_by_player_year: Dict[Tuple[str, int], List[Dict[str, Any]]] = defaultdict(list)
        for game in self.games:
            if game.get("year") in TARGET_YEARS:
                games_by_player_year[(game["playerId"], game["year"])].append(game)
                games_by_exact[(game["playerId"], game["year"], game.get("team") or "")].append(game)
        for season in self.seasons:
            player_id = season.get("playerId")
            year = season.get("year")
            team = season.get("team") or ""
            rows = games_by_exact.get((player_id, year, team)) or games_by_player_year.get((player_id, year)) or []
            if rows:
                r_ortg = weighted_average((g.get("rORTG"), g.get("POSS") or g.get("MIN")) for g in rows)
                r_drtg = weighted_average((g.get("rDRTG"), g.get("POSS") or g.get("MIN")) for g in rows)
                r_ts = weighted_average((g.get("rTS"), g.get("POSS") or g.get("MIN")) for g in rows)
                r_adj_ts = weighted_average((g.get("rAdjTS"), g.get("POSS") or g.get("MIN")) for g in rows)
                allowed_adj = weighted_average((self.adjusted_ts_allowed_benchmark(year, g.get("opponent") or None), g.get("POSS") or g.get("MIN")) for g in rows)
                if r_adj_ts is None and season.get("AdjTS%") is not None:
                    if allowed_adj is not None:
                        r_adj_ts = season.get("AdjTS%") - allowed_adj
                r_net = r_ortg + r_drtg if r_ortg is not None and r_drtg is not None else None
                season["rORTG"] = round_value(r_ortg, 1)
                season["rDRTG"] = round_value(r_drtg, 1)
                season["rNET"] = round_value(r_net, 1)
                season["rTS"] = round_value(r_ts, 1)
                season["rAdjTS"] = round_value(r_adj_ts, 1)
                season["OppRSAdjTSAllowed"] = round_value(allowed_adj, 1)
                season["relativeSource"] = "weighted game opponent context"
            else:
                r_ortg, r_drtg, r_net, r_ts = self.relative_stats(year, None, season.get("ORTG"), season.get("DRTG"), season.get("TS%"))
                r_adj_ts = self.relative_adjusted_ts(year, None, season.get("AdjTS%"))
                allowed_adj = self.adjusted_ts_allowed_benchmark(year, None)
                season["rORTG"] = round_value(r_ortg, 1)
                season["rDRTG"] = round_value(r_drtg, 1)
                season["rNET"] = round_value(r_net, 1)
                season["rTS"] = round_value(r_ts, 1)
                season["rAdjTS"] = round_value(r_adj_ts, 1)
                season["OppRSAdjTSAllowed"] = round_value(allowed_adj, 1)
                season["relativeSource"] = "regular-season average fallback" if r_net is not None else "unavailable"

    def build_series(self):
        print("Aggregating player-series rows from game logs...")
        groups: Dict[Tuple[str, int, str, str, str], List[Dict[str, Any]]] = defaultdict(list)
        for game in self.games:
            key = (
                game["playerId"],
                game["year"],
                game.get("seriesCode") or "series",
                game.get("team") or "",
                game.get("opponent") or "",
            )
            groups[key].append(game)

        for (player_id, year, series_code, team, opp), rows in groups.items():
            poss = sum((g.get("POSS") or 0) for g in rows)
            pts = sum((g.get("PTS") or 0) for g in rows)
            reb = sum((g.get("REB") or 0) for g in rows)
            ast = sum((g.get("AST") or 0) for g in rows)
            tov = sum((g.get("TOV") or 0) for g in rows)
            fgm = sum((g.get("FGM") or 0) for g in rows)
            fga = sum((g.get("FGA") or 0) for g in rows)
            fg3m = sum((g.get("FG3M") or 0) for g in rows)
            fta = sum((g.get("FTA") or 0) for g in rows)
            minutes_total = sum((g.get("MIN") or 0) for g in rows)
            games = len(rows)
            round_label = rows[0].get("round") or "Playoff Series"
            round_sort = rows[0].get("roundSort") or 9
            ts = 100 * pts / (2 * (fga + 0.44 * fta)) if fga and (fga + 0.44 * fta) > 0 else None
            efg = 100 * (fgm + 0.5 * fg3m) / fga if fga else None
            adj_fga_values = [g.get("AdjFGA") for g in rows if g.get("AdjFGA") is not None]
            adj_fta_values = [g.get("AdjFTA") for g in rows if g.get("AdjFTA") is not None]
            has_verified_game_adjts = rows and len(adj_fga_values) == len(rows) and len(adj_fta_values) == len(rows)
            adj_ts = ts_from_points_attempts(pts, sum(adj_fga_values), sum(adj_fta_values)) if has_verified_game_adjts else None
            r_adj_ts = weighted_average((g.get("rAdjTS"), g.get("POSS") or g.get("MIN")) for g in rows) if has_verified_game_adjts else None
            opp_adj_allowed = weighted_average((g.get("OppRSAdjTSAllowed") or self.adjusted_ts_allowed_benchmark(year, g.get("opponent") or opp or None), g.get("POSS") or g.get("MIN")) for g in rows)
            if r_adj_ts is None:
                r_adj_ts = self.relative_adjusted_ts(year, opp or None, adj_ts)
                if r_adj_ts is not None and opp_adj_allowed is None and adj_ts is not None:
                    opp_adj_allowed = adj_ts - r_adj_ts
            rim_freq = weighted_average((g.get("RIM_FREQ"), g.get("FGA") or g.get("POSS") or g.get("MIN")) for g in rows)
            rim_acc = weighted_average((g.get("RIM_ACC"), g.get("FGA") or g.get("POSS") or g.get("MIN")) for g in rows)
            orb_pct = weighted_average((g.get("ORB%"), g.get("POSS") or g.get("MIN")) for g in rows)
            dreb_pct = weighted_average((g.get("DREB%"), g.get("POSS") or g.get("MIN")) for g in rows)
            ast_pct = weighted_average((g.get("AST%"), g.get("POSS") or g.get("MIN")) for g in rows)
            usg_pct = weighted_average((g.get("USG%"), g.get("POSS") or g.get("MIN")) for g in rows)
            team_ts = weighted_average((g.get("teamTS%"), g.get("POSS") or g.get("MIN")) for g in rows)
            team_adj_ts = weighted_average((g.get("teamAdjTS%"), g.get("POSS") or g.get("MIN")) for g in rows)
            team_rim_freq = weighted_average((g.get("teamRimFreq"), g.get("POSS") or g.get("MIN")) for g in rows)
            team_rim_acc = weighted_average((g.get("teamRimAcc"), g.get("POSS") or g.get("MIN")) for g in rows)
            team_orb = weighted_average((g.get("teamORB%"), g.get("POSS") or g.get("MIN")) for g in rows)
            team_dreb = weighted_average((g.get("teamDREB%"), g.get("POSS") or g.get("MIN")) for g in rows)
            opp_team_ts = weighted_average((g.get("oppTeamTS%"), g.get("POSS") or g.get("MIN")) for g in rows)
            opp_team_adj_ts = weighted_average((g.get("oppTeamAdjTS%"), g.get("POSS") or g.get("MIN")) for g in rows)
            opp_rim_freq_allowed = weighted_average((g.get("oppRimFreqAllowed"), g.get("POSS") or g.get("MIN")) for g in rows)
            opp_rim_acc_allowed = weighted_average((g.get("oppRimAccAllowed"), g.get("POSS") or g.get("MIN")) for g in rows)
            off = weighted_average((g.get("ORTG"), g.get("POSS") or g.get("MIN")) for g in rows)
            deff = weighted_average((g.get("DRTG"), g.get("POSS") or g.get("MIN")) for g in rows)
            net = off - deff if off is not None and deff is not None else weighted_average((g.get("NET"), g.get("POSS") or g.get("MIN")) for g in rows)
            r_ortg = weighted_average((g.get("rORTG"), g.get("POSS") or g.get("MIN")) for g in rows)
            r_drtg = weighted_average((g.get("rDRTG"), g.get("POSS") or g.get("MIN")) for g in rows)
            r_ts = weighted_average((g.get("rTS"), g.get("POSS") or g.get("MIN")) for g in rows)
            if r_ortg is None or r_drtg is None:
                fallback_r_ortg, fallback_r_drtg, fallback_r_net, fallback_r_ts = self.relative_stats(year, opp or None, off, deff, ts)
                r_ortg = r_ortg if r_ortg is not None else fallback_r_ortg
                r_drtg = r_drtg if r_drtg is not None else fallback_r_drtg
                r_ts = r_ts if r_ts is not None else fallback_r_ts
            r_net = r_ortg + r_drtg if r_ortg is not None and r_drtg is not None else None
            wins = sum(1 for g in rows if g.get("result") == "W")
            losses = sum(1 for g in rows if g.get("result") == "L")
            player = self.players[player_id]
            self.series.append({
                "seriesId": f"{player_id}_{year}_{series_code}_{opp}",
                "playerId": player_id,
                "nbaId": player.get("nbaId"),
                "playerName": player.get("name"),
                "year": year,
                "round": round_label,
                "roundSort": round_sort,
                "seriesCode": series_code,
                "team": team or None,
                "opponent": opp or None,
                "games": games,
                "wins": wins,
                "losses": losses,
                "result": f"{wins}-{losses}",
                "MIN": round_value(minutes_total / games if games else None, 1),
                "PTS/75": round_value(per75(pts, poss), 1),
                "REB/75": round_value(per75(reb, poss), 1),
                "AST/75": round_value(per75(ast, poss), 1),
                "TOV/75": round_value(per75(tov, poss), 1),
                "TS%": round_value(ts, 1),
                "AdjTS%": round_value(adj_ts, 1),
                "AdjFGA": round_value(sum(adj_fga_values), 1) if adj_fga_values else None,
                "AdjFTA": round_value(sum(adj_fta_values), 1) if adj_fta_values else None,
                "eFG%": round_value(efg, 1),
                "RIM_FREQ": round_value(rim_freq, 1),
                "RIM_ACC": round_value(rim_acc, 1),
                "ORB%": round_value(orb_pct, 1),
                "DREB%": round_value(dreb_pct, 1),
                "AST%": round_value(ast_pct, 1),
                "USG%": round_value(usg_pct, 1),
                "teamTS%": round_value(team_ts, 1),
                "teamAdjTS%": round_value(team_adj_ts, 1),
                "teamRimFreq": round_value(team_rim_freq, 1),
                "teamRimAcc": round_value(team_rim_acc, 1),
                "teamORB%": round_value(team_orb, 1),
                "teamDREB%": round_value(team_dreb, 1),
                "oppTeamTS%": round_value(opp_team_ts, 1),
                "oppTeamAdjTS%": round_value(opp_team_adj_ts, 1),
                "oppRimFreqAllowed": round_value(opp_rim_freq_allowed, 1),
                "oppRimAccAllowed": round_value(opp_rim_acc_allowed, 1),
                "ORTG": round_value(off, 1),
                "DRTG": round_value(deff, 1),
                "NET": round_value(net, 1),
                "rORTG": round_value(r_ortg, 1),
                "rDRTG": round_value(r_drtg, 1),
                "rNET": round_value(r_net, 1),
                "rTS": round_value(r_ts, 1),
                "rAdjTS": round_value(r_adj_ts, 1),
                "OppRSAdjTSAllowed": round_value(opp_adj_allowed, 1),
                "source": "game_report aggregation",
                "sourceLevel": "series",
            })

    def on_off_delta(self, on: Dict[str, Any], off: Optional[Dict[str, Any]], *fields: str, percentage: bool = True) -> Optional[float]:
        if not off:
            return None
        on_value = pct(safe_float(pick(on, *fields))) if percentage else safe_float(pick(on, *fields))
        off_value = pct(safe_float(pick(off, *fields))) if percentage else safe_float(pick(off, *fields))
        if on_value is None or off_value is None:
            return None
        return on_value - off_value

    def add_impact_metric(self, player_id: str, year: int, metric: str, value: Optional[float], level: str, source: str, signed: bool = False):
        if value is None:
            return
        self.impact.append({
            "playerId": player_id,
            "year": year,
            "metric": metric,
            "value": round_value(value, 1),
            "level": level,
            "source": source,
            "signed": signed,
        })

    def add_on_court_row(self, player_id: str, year: int, side: str, row: Dict[str, Any], off_row: Optional[Dict[str, Any]], source: str):
        on_ortg = safe_float(pick(row, "ortg", "OFF_RATING", "OffRating"))
        on_drtg = safe_float(pick(row, "drtg", "DEF_RATING", "DefRating"))
        off_ortg = safe_float(pick(off_row, "ortg", "OFF_RATING", "OffRating")) if off_row else None
        off_drtg = safe_float(pick(off_row, "drtg", "DEF_RATING", "DefRating")) if off_row else None
        on_net = on_ortg - on_drtg if on_ortg is not None and on_drtg is not None else None
        off_net = off_ortg - off_drtg if off_ortg is not None and off_drtg is not None else None
        ts = pct(safe_float(pick(row, "TsPct", "TS_PCT", "TS%")))
        off_ts = pct(safe_float(pick(off_row, "TsPct", "TS_PCT", "TS%"))) if off_row else None
        rim_freq = rim_frequency_from_row(row)
        off_rim_freq = rim_frequency_from_row(off_row) if off_row else None
        rim_acc = rim_accuracy_from_row(row)
        off_rim_acc = rim_accuracy_from_row(off_row) if off_row else None
        orb = pct(safe_float(pick(row, "OffFGReboundPct", "OREB_PCT", "ORB%")))
        off_orb = pct(safe_float(pick(off_row, "OffFGReboundPct", "OREB_PCT", "ORB%"))) if off_row else None
        def_reb = pct(safe_float(pick(row, "DefFGReboundPct", "DREB_PCT", "DREB%")))
        def_at_rim_reb = pct(safe_float(pick(row, "DefAtRimReboundPct")))
        fga = row_total_fga(row)
        fg3a = safe_float(pick(row, "FG3A"))
        fta = safe_float(pick(row, "FTA"))
        tov = safe_float(pick(row, "Turnovers", "TOV"))
        off_poss = safe_float(pick(row, "OffPoss", "POSS"))
        self.on_court.append({
            "playerId": player_id,
            "year": year,
            "side": side,
            "ORTG": round_value(on_ortg, 1),
            "DRTG": round_value(on_drtg, 1),
            "NET": round_value(on_net, 1),
            "NET_DELTA": round_value(on_net - off_net, 1) if on_net is not None and off_net is not None else None,
            "TS%": round_value(ts, 1),
            "TS_DELTA": round_value(ts - off_ts, 1) if ts is not None and off_ts is not None else None,
            "RIM_FREQ": round_value(rim_freq, 1),
            "RIM_FREQ_DELTA": round_value(rim_freq - off_rim_freq, 1) if rim_freq is not None and off_rim_freq is not None else None,
            "RIM_ACC": round_value(rim_acc, 1),
            "RIM_ACC_DELTA": round_value(rim_acc - off_rim_acc, 1) if rim_acc is not None and off_rim_acc is not None else None,
            "ORB%": round_value(orb, 1),
            "ORB_DELTA": round_value(orb - off_orb, 1) if orb is not None and off_orb is not None else None,
            "DEF_REB%": round_value(def_reb, 1),
            "DEF_RIM_REB%": round_value(def_at_rim_reb, 1),
            "3PA_RATE": round_value(ratio_pct(fg3a, fga), 1),
            "FTA_RATE": round_value(fta / fga, 2) if fta is not None and fga else None,
            "TOV_PER_100": round_value(tov / off_poss * 100, 1) if tov is not None and off_poss else None,
            "level": "playoff on/off",
            "source": source,
        })

    def build_impact(self):
        print("Loading on/off impact and team-on-court profile rows...")
        folder = self.player_sheets / "on_off"
        on_files = sorted(folder.glob("*ps.csv"))
        for path in on_files:
            # skip opponent-side vs files in this pass; they are loaded beside the normal file below.
            if "vsps" in path.name:
                continue
            rows = read_csv(path)
            if not rows:
                continue
            self.source_summary["on_off_files"] += 1
            self.source_summary["on_off_rows"] += len(rows)
            if len(self.source_files["on_off"]) < 100:
                self.source_files["on_off"].append(f"on_off/{path.name}")
            nba_id_from_name = re.sub(r"\D", "", path.name.replace("ps.csv", ""))
            vs_path = folder / f"{nba_id_from_name}vsps.csv"
            vs_rows = read_csv(vs_path) if vs_path.exists() else []
            if vs_rows and len(self.source_files["on_off_vs"]) < 100:
                self.source_files["on_off_vs"].append(f"on_off/{vs_path.name}")

            by_year: Dict[int, Dict[str, Dict[str, Any]]] = defaultdict(dict)
            for row in rows:
                year = safe_int(pick(row, "year"))
                nba_id = pick(row, "nba_id") or nba_id_from_name
                if year not in TARGET_YEARS or not nba_id:
                    continue
                player_id = self.player_id_by_nba_id.get(re.sub(r"\D", "", str(nba_id)))
                if not player_id:
                    continue
                state = str(pick(row, "player_on") or "").strip().lower()
                label = "on" if state == "true" else "off" if state == "false" else None
                if not label:
                    continue
                by_year[year][label] = row

            vs_by_year: Dict[int, Dict[str, Dict[str, Any]]] = defaultdict(dict)
            for row in vs_rows:
                year = safe_int(pick(row, "year"))
                nba_id = pick(row, "nba_id") or nba_id_from_name
                if year not in TARGET_YEARS or not nba_id:
                    continue
                player_id = self.player_id_by_nba_id.get(re.sub(r"\D", "", str(nba_id)))
                if not player_id:
                    continue
                state = str(pick(row, "player_on") or "").strip().lower()
                label = "on" if state == "true" else "off" if state == "false" else None
                if label:
                    vs_by_year[year][label] = row

            for year, pair in by_year.items():
                on = pair.get("on")
                off = pair.get("off")
                if year < 2001:
                    # Legacy on/off rows before 2001 are not reliable enough for the audience site.
                    # Keep box-score/advanced player data, but suppress misleading on-court profiles.
                    self.source_summary["legacy_pre_2001_on_off_rows_suppressed"] += 1
                    continue
                if not on:
                    continue
                player_id = self.player_id_by_nba_id.get(re.sub(r"\D", "", str(pick(on, "nba_id") or nba_id_from_name)))
                if not player_id:
                    continue
                on_ortg = safe_float(pick(on, "ortg"))
                on_drtg = safe_float(pick(on, "drtg"))
                off_ortg = safe_float(pick(off, "ortg")) if off else None
                off_drtg = safe_float(pick(off, "drtg")) if off else None
                on_net = on_ortg - on_drtg if on_ortg is not None and on_drtg is not None else None
                off_net = off_ortg - off_drtg if off_ortg is not None and off_drtg is not None else None
                delta = on_net - off_net if on_net is not None and off_net is not None else None

                self.add_on_court_row(player_id, year, "Team offense/defense with player ON", on, off, f"on_off/{path.name}")
                metrics = [
                    ("On-court ORTG", on_ortg, False),
                    ("On-court DRTG", on_drtg, False),
                    ("On-court NET", on_net, True),
                    ("On-Off NET", delta, True),
                    ("Team ON TS%", pct(safe_float(pick(on, "TsPct"))), False),
                    ("Team ON rim frequency", rim_frequency_from_row(on), False),
                    ("Team ON rim accuracy", rim_accuracy_from_row(on), False),
                    ("Team ON ORB%", pct(safe_float(pick(on, "OffFGReboundPct"))), False),
                    ("Team ON def-rebound%", pct(safe_float(pick(on, "DefFGReboundPct"))), False),
                    ("Team ON rim-rebound%", pct(safe_float(pick(on, "DefAtRimReboundPct"))), False),
                ]
                for metric, value, signed in metrics:
                    self.add_impact_metric(player_id, year, metric, value, "playoff on/off", f"on_off/{path.name}", signed=signed)

                vs_pair = vs_by_year.get(year, {})
                vs_on = vs_pair.get("on")
                vs_off = vs_pair.get("off")
                if vs_on:
                    self.add_on_court_row(player_id, year, "Opponent offense allowed with player ON", vs_on, vs_off, f"on_off/{vs_path.name}")
                    opp_ortg = safe_float(pick(vs_on, "ortg"))
                    opp_ts = pct(safe_float(pick(vs_on, "TsPct")))
                    opp_rim_freq = rim_frequency_from_row(vs_on)
                    opp_rim_acc = rim_accuracy_from_row(vs_on)
                    opp_orb = pct(safe_float(pick(vs_on, "OffFGReboundPct")))
                    opp_dreb = pct(safe_float(pick(vs_on, "DefFGReboundPct")))
                    defensive_metrics = [
                        ("Opponent ON ORTG allowed", opp_ortg, False),
                        ("Opponent ON TS% allowed", opp_ts, False),
                        ("Opponent ON rim frequency allowed", opp_rim_freq, False),
                        ("Opponent ON rim accuracy allowed", opp_rim_acc, False),
                        ("Opponent ON ORB% allowed", opp_orb, False),
                        ("Opponent ON def-rebound% allowed", opp_dreb, False),
                    ]
                    for metric, value, signed in defensive_metrics:
                        self.add_impact_metric(player_id, year, metric, value, "playoff opponent on/off", f"on_off/{vs_path.name}", signed=signed)

    def build_skill_splits(self):
        print("Building season-level shot and playmaking split rows...")
        # Use the already-loaded season source rows by re-reading totals. This keeps the main
        # season table clean while adding audience-friendly detail cards.
        for path in sorted((self.player_sheets / "totals").glob("*_ps.csv")):
            for row in read_csv(path):
                year = safe_int(pick(row, "year"))
                if year not in TARGET_YEARS:
                    continue
                nba_id = pick(row, "PLAYER_ID", "nba_id")
                name = pick(row, "PLAYER_NAME", "Player", "Name")
                if not name:
                    continue
                player_id = self.player_id(str(name), str(nba_id) if nba_id is not None else None)
                fga = safe_float(pick(row, "FGA"))
                if not fga or fga <= 0:
                    continue

                def add(category: str, makes_names: Tuple[str, ...], att_names: Tuple[str, ...], value_kind: str = "FG%"):
                    makes = sum(safe_float(pick(row, n)) or 0 for n in makes_names)
                    attempts = sum(safe_float(pick(row, n)) or 0 for n in att_names)
                    if attempts <= 0:
                        return
                    frequency = attempts / fga * 100 if fga else None
                    efficiency = makes / attempts * 100 if attempts else None
                    self.skill_splits.append({
                        "playerId": player_id,
                        "year": year,
                        "category": category,
                        "frequency": round_value(frequency, 1),
                        "efficiency": round_value(efficiency, 1),
                        "efficiencyLabel": value_kind,
                        "attempts": round_value(attempts, 0),
                        "level": "season",
                        "source": f"totals/{path.name}",
                    })

                add("Rim / Restricted Area", ("RA_FGM", "AtRimFGM"), ("RA_FGA", "AtRimFGA"))
                add("Interior Paint", ("ITP_FGM",), ("ITP_FGA",))
                add("Midrange", ("MID_FGM",), ("MID_FGA",))
                add("Corner 3", ("CORNER_3_FGM", "Corner3FGM", "LEFT_CORNER_3_FGM", "RIGHT_CORNER_3_FGM"), ("CORNER_3_FGA", "Corner3FGA", "LEFT_CORNER_3_FGA", "RIGHT_CORNER_3_FGA"))
                add("Above Break 3", ("ABOVE_BREAK_3_FGM", "Arc3FGM"), ("ABOVE_BREAK_3_FGA", "Arc3FGA"))

                drives = safe_float(pick(row, "DRIVES"))
                drive_pts = safe_float(pick(row, "DRIVE_PTS"))
                if drives and drives > 0 and drive_pts is not None:
                    self.skill_splits.append({
                        "playerId": player_id,
                        "year": year,
                        "category": "Drives",
                        "frequency": round_value(drives, 0),
                        "efficiency": round_value(drive_pts / drives, 2),
                        "efficiencyLabel": "PTS/drive",
                        "attempts": round_value(drives, 0),
                        "level": "season",
                        "source": f"totals/{path.name}",
                    })
                potential_ast = safe_float(pick(row, "POTENTIAL_AST"))
                touches = safe_float(pick(row, "TOUCHES"))
                if potential_ast and touches and touches > 0:
                    self.skill_splits.append({
                        "playerId": player_id,
                        "year": year,
                        "category": "Potential assists",
                        "frequency": round_value(potential_ast / touches * 100, 1),
                        "efficiency": round_value(potential_ast, 0),
                        "efficiencyLabel": "pot. AST",
                        "attempts": round_value(touches, 0),
                        "level": "season",
                        "source": f"totals/{path.name}",
                    })

    def build_player_team_leaders(self):
        """Build audience-facing rows showing who led his own team in a game/series metric."""
        print("Building player team-leader rows for game and series levels...")
        metric_specs = [
            ("PTS/75", "PTS/75", True),
            ("TS%", "TS%", True),
            ("AdjTS%", "AdjTS%", True),
            ("rTS", "rTS", True),
            ("rAdjTS", "rAdjTS", True),
            ("ORTG", "ORTG", True),
            ("DRTG", "DRTG", False),
            ("NET", "NET", True),
            ("rORTG", "rORTG", True),
            ("rDRTG", "rDRTG", True),
            ("rNET", "rNET", True),
            ("ORB%", "ORB%", True),
            ("DREB%", "DREB%", True),
            ("AST%", "AST%", True),
            ("USG%", "USG%", True),
            ("RIM_FREQ", "Rim Freq", True),
            ("RIM_ACC", "Rim Accuracy", True),
        ]

        def emit(rows: List[Dict[str, Any]], level: str):
            groups: Dict[Tuple[Any, ...], List[Dict[str, Any]]] = defaultdict(list)
            for row in rows:
                if not row.get("team") or not row.get("year"):
                    continue
                if level == "game":
                    key = (row.get("year"), row.get("team"), row.get("gameId"))
                else:
                    key = (row.get("year"), row.get("team"), row.get("seriesCode"), row.get("opponent"))
                groups[key].append(row)
            out = self.player_team_ranks_game if level == "game" else self.player_team_ranks_series
            out.clear()
            for key, group_rows in groups.items():
                # Keep tiny garbage-time rows from leading rate stats on 1 possession.
                eligible = [r for r in group_rows if (r.get("MIN") or 0) >= (2 if level == "game" else 4)] or group_rows
                for field, label, reverse in metric_specs:
                    values = [r for r in eligible if r.get(field) not in (None, "")]
                    if not values:
                        continue
                    values.sort(key=lambda r: r.get(field), reverse=reverse)
                    leader = values[0]
                    out.append({
                        "playerId": leader.get("playerId"),
                        "playerName": leader.get("playerName"),
                        "year": leader.get("year"),
                        "team": leader.get("team"),
                        "level": level,
                        "context": leader.get("round") if level == "series" else leader.get("date"),
                        "opponent": leader.get("opponent"),
                        "metric": label,
                        "value": round_value(leader.get(field), 1),
                        "rank": 1,
                        "teamSize": len(values),
                        "isLeader": True,
                        "gameId": leader.get("gameId") if level == "game" else None,
                        "seriesCode": leader.get("seriesCode"),
                    })

        emit(self.games, "game")
        emit(self.series, "series")

    def team_game_context_rows(self) -> List[Dict[str, Any]]:
        rows = []
        for (year, date, team), ctx in self.team_game_context.items():
            row = {"year": year, "date": date, "team": team}
            row.update(ctx)
            rows.append(row)
        return sorted(rows, key=lambda r: (r.get("year"), r.get("date") or "", r.get("team") or ""))

    def team_series_context_rows(self) -> List[Dict[str, Any]]:
        groups: Dict[Tuple[Any, ...], List[Dict[str, Any]]] = defaultdict(list)
        for row in self.team_game_context_rows():
            key = (row.get("year"), row.get("team"), row.get("seriesCode"), row.get("opponent"))
            groups[key].append(row)
        out = []
        metrics = ["teamORTG", "teamDRTG", "teamNET", "teamTS%", "teamAdjTS%", "teamRimFreq", "teamRimAcc", "teamORB%", "teamDREB%", "oppTeamTS%", "oppTeamAdjTS%", "oppRimFreqAllowed", "oppRimAccAllowed"]
        for (year, team, series_code, opp), rows in groups.items():
            item = {"year": year, "team": team, "seriesCode": series_code, "opponent": opp, "games": len(rows), "round": rows[0].get("round"), "roundSort": rows[0].get("roundSort")}
            for metric in metrics:
                item[metric] = round_value(weighted_average((r.get(metric), 1) for r in rows), 1)
            out.append(item)
        return sorted(out, key=lambda r: (r.get("year"), r.get("team") or "", r.get("roundSort") or 9, r.get("opponent") or ""))

    def build_rankings(self):
        print("Building global season rankings...")
        eligible = [s for s in self.seasons if (s.get("GP") or 0) >= 4 and (s.get("MIN") or 0) >= 10]
        for metric in ["PTS/75", "AST/75", "REB/75", "NET", "TS%"]:
            rows = [s for s in eligible if s.get(metric) is not None]
            reverse = True
            rows.sort(key=lambda s: s.get(metric), reverse=reverse)
            for rank, season in enumerate(rows[:100], 1):
                self.rankings.append({
                    "metric": metric,
                    "rank": rank,
                    "playerId": season["playerId"],
                    "playerName": season["playerName"],
                    "year": season["year"],
                    "team": season.get("team"),
                    "value": season.get(metric),
                    "level": "season",
                })

    def finalize_players(self):
        season_counts = defaultdict(int)
        for season in self.seasons:
            season_counts[season["playerId"]] += 1
        for player_id, count in season_counts.items():
            self.players[player_id]["seasonCount"] = count
        for player in self.players.values():
            player["years"] = sorted(set(player.get("years") or []))
            player["teams"] = sorted(set(player.get("teams") or []))
            if player["years"]:
                player["firstYear"] = min(player["years"])
                player["lastYear"] = max(player["years"])

    def package(self) -> Dict[str, Any]:
        self.finalize_players()
        years_loaded = sorted({s["year"] for s in self.seasons if s.get("year") in TARGET_YEARS})
        missing_years = [y for y in TARGET_YEARS if y not in years_loaded]
        generated = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return {
            "version": "2.4",
            "generated": generated,
            "players": dict(sorted(self.players.items(), key=lambda item: item[1]["name"])),
            "playerSeasons": sorted(self.seasons, key=lambda s: (s["playerName"], s["year"])),
            "playerSeries": sorted(self.series, key=lambda s: (s["playerName"], s["year"], s.get("roundSort", 9), s.get("seriesCode") or "")),
            "playerGames": sorted(self.games, key=lambda g: (g["playerName"], g["year"], g.get("date") or "", g.get("gameId") or "")),
            "teamBenchmarks": sorted(self.team_benchmarks, key=lambda b: (b["year"], b["team"])),
            "teamRegularSeasonBenchmarks": sorted(self.rs_team_benchmarks, key=lambda b: (b["year"], b["team"])),
            "playerImpact": sorted(self.impact, key=lambda i: (self.players.get(i["playerId"], {}).get("name", ""), i["year"], i["metric"])),
            "playerOnCourt": sorted(self.on_court, key=lambda i: (self.players.get(i["playerId"], {}).get("name", ""), i["year"], i["side"])),
            "playerSkillSplits": sorted(self.skill_splits, key=lambda s: (self.players.get(s["playerId"], {}).get("name", ""), s["year"], s["category"])),
            "rankings": self.rankings,
            "teamGameContext": self.team_game_context_rows(),
            "teamSeriesContext": self.team_series_context_rows(),
            "playerTeamRanksGame": sorted(self.player_team_ranks_game, key=lambda r: (r.get("playerName") or "", r.get("year") or 0, r.get("context") or "", r.get("metric") or "")),
            "playerTeamRanksSeries": sorted(self.player_team_ranks_series, key=lambda r: (r.get("playerName") or "", r.get("year") or 0, r.get("context") or "", r.get("metric") or "")),
            "metadata": {
                "targetYears": TARGET_YEARS,
                "yearsLoaded": years_loaded,
                "missingYears": missing_years,
                "featuredPlayers": FEATURED_PLAYERS,
                "sourceRepos": GABRIEL_REPOS,
                "sourceFilesUsed": {k: v[:50] + ([f"... {len(v)-50} more"] if len(v) > 50 else []) for k, v in self.source_files.items()},
                "sourceRowCounts": dict(self.source_summary),
                "counts": {
                    "players": len(self.players),
                    "playerSeasons": len(self.seasons),
                    "playerSeries": len(self.series),
                    "playerGames": len(self.games),
                    "teamBenchmarks": len(self.team_benchmarks),
                    "teamRegularSeasonBenchmarks": len(self.rs_team_benchmarks),
                    "playerImpact": len(self.impact),
                    "playerOnCourt": len(self.on_court),
                    "playerSkillSplits": len(self.skill_splits),
                    "rankings": len(self.rankings),
                    "teamGameContext": len(self.team_game_context_rows()),
                    "teamSeriesContext": len(self.team_series_context_rows()),
                    "playerTeamRanksGame": len(self.player_team_ranks_game),
                    "playerTeamRanksSeries": len(self.player_team_ranks_series),
                },
                "metricsReal": ["MIN", "PTS/75", "REB/75", "AST/75", "TOV/75", "TS%", "AdjTS%", "rAdjTS", "eFG%", "RIM_FREQ", "RIM_ACC", "ORB%", "DREB%", "AST%", "USG%", "ORTG", "DRTG", "NET", "rORTG", "rDRTG", "rNET", "rTS"],
                "metricsContextOnly": ["Opponent", "Round", "Game date", "Team", "Source label"],
                "metricsUnavailable": ["Some 2025/2026 game logs depend on the latest available game_report files", "True player-on-court by individual game/series still requires full lineup reconstruction. The new game/series team context and player-rank sections use real team-game and player-game rows where source fields exist."],
                "notes": [
                    "Season totals are loaded from player_sheets/totals/*_ps.csv.",
                    "Game rows are loaded from real gen_totals playoff logs for 1997–2024 plus available playoff game_report CSVs for newer/supplemental seasons; no fake games are generated.",
                    "Series rows are aggregated from the real game rows, so a season can have season totals even when local game files are not available yet.",
                    "Relative stats use the opponent's regular-season team page as the primary benchmark. Playoff team context is only a fallback when regular-season context is unavailable.",
                    "Team-on-court offense/defense profile rows are loaded from on_off/*ps.csv and on_off/*vsps.csv. These are playoff-year on/off sections; true game-level on-court splits require play-by-play lineup reconstruction.",
                ],
            },
        }


def update_manifest(package: Dict[str, Any]):
    counts = package["metadata"]["counts"]
    manifest = {
        "version": package["version"],
        "generated": package["generated"],
        "sources": {
            "player_sheets": {
                "repo": GABRIEL_REPOS["player_sheets"],
                "description": "Primary playoff player totals, gen_totals game logs, game reports, team totals, on/off impact, and skill split source.",
                "status": "active",
                "priority_folders": PLAYER_SHEETS_SPARSE_PATHS,
                "files_used": package["metadata"].get("sourceFilesUsed", {}),
                "row_count": package["metadata"].get("sourceRowCounts", {}),
            },
            "site_Data": {"repo": GABRIEL_REPOS["site_Data"], "status": "documented external source; not required for this compact build"},
            "merged_playbyplay": {"repo": GABRIEL_REPOS["merged_playbyplay"], "status": "documented external source; not required for this compact build"},
            "pbpbacklog": {"repo": GABRIEL_REPOS["pbpbacklog"], "status": "documented external source; not required for this compact build"},
            "legacy_pbp": {"repo": GABRIEL_REPOS["legacy_pbp"], "status": "documented external source; not required for this compact build"},
        },
        "metrics": {
            "real_metrics": package["metadata"].get("metricsReal", []),
            "context_only_metrics": package["metadata"].get("metricsContextOnly", []),
            "unavailable_metrics": package["metadata"].get("metricsUnavailable", []),
        },
        "rules_applied": {
            "no_2k_related": True,
            "no_brescou_breacou": True,
            "no_fabricated_stats": True,
            "missing_stats_show_em_dash": True,
            "target_years": TARGET_YEARS,
        },
        "stat_calculations": {
            "PTS_75": "Points / POSS * 75 when possession totals exist.",
            "AST_75": "Assists / POSS * 75 when possession totals exist.",
            "REB_75": "Rebounds / POSS * 75 when possession totals exist.",
            "TOV_75": "Turnovers / POSS * 75 when possession totals exist.",
            "rTS": "player TS% - opponent regular-season TS% allowed benchmark. Playoff fallback only when regular-season opponent context is unavailable.",
            "rORTG": "player ORTG - opponent regular-season DRTG benchmark. Playoff fallback only when regular-season opponent context is unavailable.",
            "rDRTG": "opponent regular-season ORTG benchmark - player DRTG. Playoff fallback only when regular-season opponent context is unavailable.",
            "rNET": "rORTG + rDRTG. Positive rDRTG already means the player defense beat opponent offensive context.",
            "AdjTS": "Adjusted true shooting: Points / [2 * (adjusted FGA + 0.44 * non-technical FTA)]. Adjusted FGA = FGA + verified scoring turnovers - heaves - Z Bounds/self offensive rebounds. Scoring turnovers = total TOV - bad-pass TOV - bad-pass-out-of-bounds TOV only when those detailed turnover splits exist; otherwise the row falls back to normal FGA instead of treating every TOV as a scoring TOV.",
            "rAdjTS": "AdjTS% minus opponent regular-season adjusted TS allowed when available. Opponent adjusted allowed is calculated from detailed team-vs rows when present; if detailed turnover splits are missing, it falls back to normal TS allowed instead of adding all turnovers.",
        },
        "data_hierarchy": ["Player", "Playoff Year", "Series", "Individual Games"],
        "ui_sections": ["Hero/Search", "Player Header", "Season Translation Table", "Series Breakdown", "Game Log", "On-Court Team Profile", "On-Court Impact", "Shot Profile", "Playmaking Pressure", "Defensive Activity", "Rankings", "Data Sources"],
        "counts": counts,
        "known_limitations": package["metadata"].get("notes", []),
    }
    MANIFEST_FILE.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def update_index_data(package: Dict[str, Any]):
    if not INDEX_FILE.exists():
        return
    html = INDEX_FILE.read_text(encoding="utf-8")
    start = html.find('<script id="dataPackage" type="application/json">')
    end = html.find('</script>', start)
    if start == -1 or end == -1:
        return
    open_tag_end = html.find('>', start) + 1
    prefix = html[:open_tag_end]
    suffix = html[end:]
    embedded_json = json.dumps(package, separators=(",", ":"))
    INDEX_FILE.write_text(prefix + "\n" + embedded_json + "\n    " + suffix, encoding="utf-8")

def write_outputs(package: Dict[str, Any], embed: bool = True):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(package, indent=2), encoding="utf-8")
    DATA_COPY_FILE.write_text(json.dumps(package, indent=2), encoding="utf-8")
    (DATA_DIR / "README.md").write_text(
        "# Data folder\n\n"
        "`data-package.json` is a copy of the built dataset. The production site also embeds this package directly in `index.html`, so the website opens locally without a server or a Load Data button.\n",
        encoding="utf-8",
    )
    update_manifest(package)
    if embed:
        update_index_data(package)


def main():
    parser = argparse.ArgumentParser(description="Build Playoff Translation Lab data package")
    parser.add_argument("--fetch", action="store_true", help="Sparse-clone player_sheets if the local data folder is missing")
    parser.add_argument("--no-embed", action="store_true", help="Do not embed the package into index.html")
    args = parser.parse_args()

    print("=== Playoff Translation Lab Build ===")
    try:
        player_sheets = ensure_player_sheets(fetch=args.fetch)
    except FileNotFoundError as exc:
        if OUTPUT_FILE.exists() and not args.fetch:
            print("Raw source folders are not included in this compact ZIP.")
            print("Using the already-built data-package.json and re-embedding it into index.html.")
            print("To rebuild from Gabriel1200 source CSVs, run: python3 build_data.py --fetch")
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                package = json.load(f)
            write_outputs(package, embed=not args.no_embed)
            counts = package.get("metadata", {}).get("counts", {})
            print("\n=== Package Refresh Complete ===")
            for key in ["players", "playerSeasons", "playerSeries", "playerGames", "teamBenchmarks", "teamRegularSeasonBenchmarks", "playerImpact", "playerOnCourt", "playerSkillSplits", "rankings"]:
                if key in counts:
                    print(f"{key:18s}: {counts[key]}")
            years = package.get("metadata", {}).get("yearsLoaded", [])
            print(f"Years loaded       : {min(years) if years else 'N/A'}–{max(years) if years else 'N/A'} ({len(years)}/{len(TARGET_YEARS)})")
            print(f"Data package       : {OUTPUT_FILE.relative_to(ROOT)}")
            print(f"Embedded in        : {INDEX_FILE.relative_to(ROOT)}")
            return
        raise exc
    print(f"Using player_sheets data at: {player_sheets.relative_to(ROOT)}")

    builder = DataBuilder(player_sheets)
    builder.prepare_team_maps()
    builder.build_team_benchmarks()
    builder.load_detailed_player_pbp_adjustments()
    builder.build_seasons()
    builder.build_games()
    builder.add_relative_stats_to_seasons()
    builder.build_series()
    builder.build_player_team_leaders()
    builder.build_impact()
    builder.build_skill_splits()
    builder.build_rankings()
    package = builder.package()
    write_outputs(package, embed=not args.no_embed)

    counts = package["metadata"]["counts"]
    print("\n=== Build Complete ===")
    for key in ["players", "playerSeasons", "playerSeries", "playerGames", "teamBenchmarks", "teamRegularSeasonBenchmarks", "playerImpact", "playerOnCourt", "playerSkillSplits", "rankings"]:
        print(f"{key:18s}: {counts[key]}")
    years = package["metadata"].get("yearsLoaded", [])
    print(f"Years loaded       : {min(years) if years else 'N/A'}–{max(years) if years else 'N/A'} ({len(years)}/{len(TARGET_YEARS)})")
    print(f"Data package       : {OUTPUT_FILE.relative_to(ROOT)}")
    print(f"Embedded in        : {INDEX_FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
