#!/usr/bin/env python3
import json
import re
import time
import requests
from pathlib import Path

BASE = "https://api.pbpstats.com"

TEAM_IDS = {
    "ATL": 1610612737, "BOS": 1610612738, "BKN": 1610612751, "BRK": 1610612751,
    "CHA": 1610612766, "CHH": 1610612766, "CHI": 1610612741, "CLE": 1610612739,
    "DAL": 1610612742, "DEN": 1610612743, "DET": 1610612765, "GSW": 1610612744,
    "HOU": 1610612745, "IND": 1610612754, "LAC": 1610612746, "LAL": 1610612747,
    "MEM": 1610612763, "MIA": 1610612748, "MIL": 1610612749, "MIN": 1610612750,
    "NOP": 1610612740, "NOH": 1610612740, "NYK": 1610612752, "OKC": 1610612760,
    "ORL": 1610612753, "PHI": 1610612755, "PHX": 1610612756, "POR": 1610612757,
    "SAC": 1610612758, "SAS": 1610612759, "TOR": 1610612761, "UTA": 1610612762,
    "WAS": 1610612764,
}

OUT = Path("public/data/on_court_all_leverage/raw_probes")
OUT.mkdir(parents=True, exist_ok=True)


def numeric_id(value):
    s = str(value or "")
    nums = re.findall(r"\d+", s)
    if not nums:
        return None
    return int(nums[-1])

def season_string(end_year):
    start = int(end_year) - 1
    return f"{start}-{str(end_year)[-2:]}"

def read_package():
    for p in [Path("data-package.json"), Path("public/data/data-package.embedded.json")]:
        if p.exists():
            return json.loads(p.read_text(errors="ignore"))
    raise SystemExit("No package found")

def find_sample():
    data = read_package()
    rows = data.get("playerGames", [])

    # LeBron 2013 is a reliable test because player/team IDs usually exist.
    for target_name, target_year in [("LeBron James", 2013), ("Stephen Curry", 2015), ("Kevin Durant", 2017)]:
        for r in rows:
            if not isinstance(r, dict):
                continue
            name = str(r.get("playerName") or r.get("PLAYER_NAME") or "")
            year = int(r.get("year") or r.get("season") or 0)
            if name.lower() == target_name.lower() and year == target_year:
                pid = r.get("playerId") or r.get("PLAYER_ID") or r.get("nbaId") or r.get("NBA_ID")
                team = r.get("team") or r.get("TEAM") or r.get("teamAbbr") or r.get("TEAM_ABBREVIATION")
                if pid and team:
                    return {
                        "name": target_name,
                        "year": target_year,
                        "season": season_string(target_year),
                        "playerId": numeric_id(pid),
                        "team": str(team),
                        "teamId": TEAM_IDS.get(str(team))
                    }

    raise SystemExit("Could not find a sample player row with playerId/team.")

def get(path, params):
    url = BASE + path
    try:
        r = requests.get(url, params=params, timeout=35)
        txt = r.text[:500]
        print("")
        print("GET", r.url)
        print("STATUS", r.status_code)
        print("TEXT", txt.replace("\n", " ")[:300])
        if not r.ok:
            return {"status": r.status_code, "url": r.url, "errorText": txt}
        try:
            return r.json()
        except Exception:
            return {"status": r.status_code, "url": r.url, "rawText": r.text[:2000]}
    except Exception as e:
        print("ERROR", path, e)
        return {"error": str(e), "path": path, "params": params}

def summarize_obj(label, obj):
    print("")
    print("====", label, "SUMMARY ====")
    if isinstance(obj, dict):
        print("top keys:", list(obj.keys())[:40])
        for k, v in obj.items():
            if isinstance(v, list):
                print("list key:", k, "len:", len(v))
                if v and isinstance(v[0], dict):
                    print("first row keys:", list(v[0].keys())[:80])
                break
            if isinstance(v, dict):
                print("dict key:", k, "keys:", list(v.keys())[:40])
    elif isinstance(obj, list):
        print("list len:", len(obj))
        if obj and isinstance(obj[0], dict):
            print("first row keys:", list(obj[0].keys())[:80])
    else:
        print(type(obj), str(obj)[:300])

def main():
    sample = find_sample()
    print("SAMPLE:", sample)

    if not sample["playerId"]:
        raise SystemExit("Could not extract numeric NBA playerId from sample row.")

    if not sample["teamId"]:
        raise SystemExit(f"No teamId mapping for team {sample['team']}")

    season = sample["season"]
    player_id = sample["playerId"]
    team_id = sample["teamId"]

    calls = {}

    calls["four_factor_on_off"] = get("/get-four-factor-on-off/nba", {
        "Season": season,
        "SeasonType": "Playoffs",
        "TeamId": team_id,
        "PlayerId": player_id,
    })
    time.sleep(1)

    # Test likely stat types for /get-on-off.
    for stat_type in ["Team", "Opponent", "Player"]:
        calls[f"on_off_{stat_type}"] = get(f"/get-on-off/nba/{stat_type}", {
            "Season": season,
            "SeasonType": "Playoffs",
            "TeamId": team_id,
            "PlayerId": player_id,
            "Leverage": "All",
        })
        time.sleep(1)

    # WOWY may give team offense/defense when the player is ON.
    calls["wowy_stats"] = get("/get-wowy-stats/nba", {
        "Season": season,
        "SeasonType": "Playoffs",
        "TeamId": team_id,
        "PlayerIds": str(player_id),
        "Type": "Team",
        "Leverage": "All",
    })
    time.sleep(1)

    calls["wowy_combinations"] = get("/get-wowy-combination-stats/nba", {
        "Season": season,
        "SeasonType": "Playoffs",
        "TeamId": team_id,
        "PlayerIds": str(player_id),
        "Leverage": "All",
        "OnlyCommonGames": "false",
    })
    time.sleep(1)

    # Shot endpoints. We need to see if shots include lineup/on-court fields.
    calls["team_shots"] = get("/get-shots/nba", {
        "Season": season,
        "SeasonType": "Playoffs",
        "EntityType": "Team",
        "EntityId": team_id,
    })
    time.sleep(1)

    calls["player_shots"] = get("/get-shots/nba", {
        "Season": season,
        "SeasonType": "Playoffs",
        "EntityType": "Player",
        "EntityId": player_id,
    })
    time.sleep(1)

    calls["possessions_offense"] = get("/get-possessions/nba", {
        "Season": season,
        "SeasonType": "Playoffs",
        "TeamId": team_id,
        "OffDef": "Offense",
        "Leverage": "All",
    })

    payload = {"sample": sample, "calls": calls}
    out_path = OUT / f"sample_{sample['name'].replace(' ', '_')}_{sample['year']}.json"
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))

    print("")
    print("Saved:", out_path)

    for label, obj in calls.items():
        summarize_obj(label, obj)

if __name__ == "__main__":
    main()
