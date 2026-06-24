#!/usr/bin/env python3
import json
from pathlib import Path
from collections import Counter, defaultdict

YEAR = "2026"

PLAYERS_DIR = Path("v2/data/players")
OUT_INDEX = Path("v2/data/indexes/on_court_2026_coverage.json")

FF_PATH = Path("public/data/on_court_all_leverage/player_on_season_four_factors_2026.json")
SHOT_PATH = Path("public/data/on_court_all_leverage/player_on_game_shot_locations_2026.json")

FF_FIELDS = [
    "hasOnCourtFourFactors",
    "fourFactorBackfillStatus",
    "fourFactorBackfillSource",
    "onMinutes",
    "offMinutes",

    "onTeamEFG",
    "onTeamEFGOff",
    "onTeamOREBPct",
    "onTeamOREBPctOff",
    "onTeamFTr",
    "onTeamFTrOff",
    "onTeamTOVPct",
    "onTeamTOVPctOff",

    "onOppEFG",
    "onOppEFGOff",
    "onOppOREBPct",
    "onOppOREBPctOff",
    "onOppFTr",
    "onOppFTrOff",
    "onOppTOVPct",
    "onOppTOVPctOff",
]

SHOT_FIELDS = [
    "hasOnCourtShotLocation",

    "onTeamFGA",
    "onTeamFGM",
    "onTeamFGPct",
    "onTeam3PA",
    "onTeam3PM",
    "onTeam3PAr",
    "onTeam3PPct",
    "onTeamRimFGA",
    "onTeamRimFGM",
    "onTeamRimFreq",
    "onTeamRimFGPct",
    "onTeamShortMidFGA",
    "onTeamShortMidFGM",
    "onTeamShortMidFreq",
    "onTeamShortMidFGPct",
    "onTeamLongMidFGA",
    "onTeamLongMidFGM",
    "onTeamLongMidFreq",
    "onTeamLongMidFGPct",
    "onTeamCorner3FGA",
    "onTeamCorner3FGM",
    "onTeamCorner3Freq",
    "onTeamCorner3FGPct",
    "onTeamAboveBreak3FGA",
    "onTeamAboveBreak3FGM",
    "onTeamAboveBreak3Freq",
    "onTeamAboveBreak3FGPct",

    "onOppFGA",
    "onOppFGM",
    "onOppFGPct",
    "onOpp3PA",
    "onOpp3PM",
    "onOpp3PAr",
    "onOpp3PPct",
    "onOppRimFGA",
    "onOppRimFGM",
    "onOppRimFreq",
    "onOppRimFGPct",
    "onOppShortMidFGA",
    "onOppShortMidFGM",
    "onOppShortMidFreq",
    "onOppShortMidFGPct",
    "onOppLongMidFGA",
    "onOppLongMidFGM",
    "onOppLongMidFreq",
    "onOppLongMidFGPct",
    "onOppCorner3FGA",
    "onOppCorner3FGM",
    "onOppCorner3Freq",
    "onOppCorner3FGPct",
    "onOppAboveBreak3FGA",
    "onOppAboveBreak3FGM",
    "onOppAboveBreak3Freq",
    "onOppAboveBreak3FGPct",
]

def norm(v):
    if v is None:
        return ""
    s = str(v).strip()
    return s[:-2] if s.endswith(".0") else s

def api_player_id(v):
    s = norm(v)
    if "_" in s:
        last = s.split("_")[-1]
        if last.isdigit():
            return last
    return s

def get(row, keys):
    for k in keys:
        if isinstance(row, dict) and row.get(k) not in [None, "", "—"]:
            return row.get(k)
    return None

def year_of(row):
    y = get(row, ["year", "season", "SEASON", "YEAR"])
    if isinstance(y, str) and "-" in y:
        try:
            return str(int(y[:4]) + 1)
        except Exception:
            return norm(y)
    return norm(y)

def team_of(row):
    return norm(get(row, ["team", "TEAM", "teamAbbr", "TEAM_ABBREVIATION"]))

def game_id(row):
    return norm(get(row, ["gameId", "GAME_ID", "game_id", "gid", "GameID"]))

def calc_efg(fgm, threes, fga):
    try:
        fgm = float(fgm)
        threes = float(threes)
        fga = float(fga)
        if fga <= 0:
            return None
        return round(100 * (fgm + 0.5 * threes) / fga, 3)
    except Exception:
        return None

ff_rows = json.loads(FF_PATH.read_text(errors="ignore"))
shot_rows = json.loads(SHOT_PATH.read_text(errors="ignore"))

ff_idx = {}
for r in ff_rows:
    if not r.get("hasOnCourtFourFactors"):
        continue

    pid = api_player_id(r.get("playerId"))
    team = team_of(r)
    y = year_of(r)

    if y != YEAR or not pid or not team:
        continue

    patch = {f: r.get(f) for f in FF_FIELDS if f in r}
    patch["playerId"] = pid
    patch["playerName"] = r.get("playerName")
    patch["team"] = team
    patch["year"] = 2026
    patch["season"] = "2025-26"
    patch["source"] = "pbpstats get-four-factor-on-off"
    ff_idx[(pid, team)] = patch

shot_idx_team = {}
shot_idx_no_team = defaultdict(list)

for r in shot_rows:
    if not r.get("hasOnCourtShotLocation"):
        continue

    pid = api_player_id(r.get("playerId"))
    y = year_of(r)
    gid = game_id(r)
    team = team_of(r)

    if y != YEAR or not pid or not gid:
        continue

    patch = {f: r.get(f) for f in SHOT_FIELDS if f in r}
    patch["onTeamEFG_fromShots"] = calc_efg(r.get("onTeamFGM"), r.get("onTeam3PM"), r.get("onTeamFGA"))
    patch["onOppEFG_fromShots"] = calc_efg(r.get("onOppFGM"), r.get("onOpp3PM"), r.get("onOppFGA"))
    patch["onCourtShotProfileSource"] = "pbpstats shot-location while player ON"

    if team:
        shot_idx_team[(pid, gid, team)] = patch

    shot_idx_no_team[(pid, gid)].append((team, patch))

report = {
    "ffSourceRows": len(ff_rows),
    "ffIndexedTrueRows": len(ff_idx),
    "shotSourceRows": len(shot_rows),
    "shotIndexedRows": len(shot_idx_team),
    "playersTouched": 0,
    "playersWithFourFactors": 0,
    "playersWithShotProfile": 0,
    "gameRowsUpdatedWithShotProfile": 0,
    "playerFilesChecked": 0,
}

coverage = {
    "year": 2026,
    "season": "2025-26",
    "fourFactorPlayers": [],
    "shotProfilePlayers": [],
    "notes": [
        "Four factors are true ON/OFF season-level fields from PBPStats.",
        "Shot profile fields are team/opponent shot profile while the player is ON court, not the player's personal shot diet."
    ]
}

for pf in sorted(PLAYERS_DIR.glob("*.json")):
    data = json.loads(pf.read_text(errors="ignore"))
    meta = data.setdefault("meta", {})
    name = meta.get("name") or pf.stem.replace("-", " ").title()

    report["playerFilesChecked"] += 1

    pids = []
    for x in meta.get("playerIds", []):
        pid = api_player_id(x)
        if pid:
            pids.append(pid)

    if not pids:
        continue

    games_2026 = [g for g in data.get("games", []) if year_of(g) == YEAR]
    teams_2026 = sorted({team_of(g) for g in games_2026 if team_of(g)})
    team_counts = Counter(team_of(g) for g in games_2026 if team_of(g))

    touched = False
    has_ff = False
    shot_count = 0

    # Merge season-level four factors into meta.
    by_team = {}
    for pid in pids:
        for team in teams_2026:
            patch = ff_idx.get((pid, team))
            if patch:
                by_team[team] = patch

    if by_team:
        meta.setdefault("onCourtFourFactorsByTeam", {})
        meta["onCourtFourFactorsByTeam"][YEAR] = by_team

        # Flat convenience field for UI: use team with most 2026 games; if tied, more ON minutes.
        best_team = sorted(
            by_team.keys(),
            key=lambda t: (team_counts.get(t, 0), by_team[t].get("onMinutes") or 0),
            reverse=True
        )[0]

        meta.setdefault("onCourtFourFactors", {})
        meta["onCourtFourFactors"][YEAR] = by_team[best_team]
        meta["hasOnCourtFourFactors2026"] = True

        has_ff = True
        touched = True
        coverage["fourFactorPlayers"].append({
            "slug": pf.stem,
            "name": name,
            "teams": sorted(by_team.keys()),
        })
    else:
        meta["hasOnCourtFourFactors2026"] = False

    # Merge game-level ON shot profile into game rows.
    for g in games_2026:
        gid = game_id(g)
        team = team_of(g)

        if not gid:
            continue

        patch = None

        for pid in pids:
            # Strict match first: player + game + team.
            patch = shot_idx_team.get((pid, gid, team))
            if patch:
                break

            # Fallback only if V2 row has no team and there is exactly one shot row.
            candidates = shot_idx_no_team.get((pid, gid), [])
            if not team and len(candidates) == 1:
                patch = candidates[0][1]
                break

        if patch:
            g.update(patch)
            touched = True
            shot_count += 1
            report["gameRowsUpdatedWithShotProfile"] += 1

    if shot_count:
        meta["hasOnCourtShotProfile2026"] = True
        coverage["shotProfilePlayers"].append({
            "slug": pf.stem,
            "name": name,
            "gameRows": shot_count,
        })
    else:
        meta["hasOnCourtShotProfile2026"] = False

    if has_ff:
        report["playersWithFourFactors"] += 1

    if shot_count:
        report["playersWithShotProfile"] += 1

    if touched:
        pf.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False))
        report["playersTouched"] += 1

coverage["summary"] = report
OUT_INDEX.parent.mkdir(parents=True, exist_ok=True)
OUT_INDEX.write_text(json.dumps(coverage, separators=(",", ":"), ensure_ascii=False))

print(json.dumps(report, indent=2))

for slug in ["victor-wembanyama", "lebron-james", "james-harden", "nikola-jokic", "shai-gilgeous-alexander"]:
    f = PLAYERS_DIR / f"{slug}.json"
    if not f.exists():
        continue

    data = json.loads(f.read_text(errors="ignore"))
    meta = data.get("meta", {})
    games = [g for g in data.get("games", []) if year_of(g) == YEAR]

    shot_hits = [g for g in games if g.get("hasOnCourtShotLocation")]
    print("\n" + slug)
    print("hasOnCourtFourFactors2026:", meta.get("hasOnCourtFourFactors2026"))
    print("hasOnCourtShotProfile2026:", meta.get("hasOnCourtShotProfile2026"))
    print("shot profile game rows:", len(shot_hits))
    print("four factors:", meta.get("onCourtFourFactors", {}).get(YEAR))

    if shot_hits[:1]:
        g = shot_hits[0]
        print("sample shot row:", {
            "year": g.get("year"),
            "team": team_of(g),
            "gameId": game_id(g),
            "onTeamRimFreq": g.get("onTeamRimFreq"),
            "onTeam3PAr": g.get("onTeam3PAr"),
            "onOppRimFreq": g.get("onOppRimFreq"),
            "onOpp3PAr": g.get("onOpp3PAr"),
        })
