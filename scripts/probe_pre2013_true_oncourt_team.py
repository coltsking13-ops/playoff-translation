import json, time, re
from pathlib import Path
import requests

BASE = "https://api.pbpstats.com"
OUT = Path("public/data/pre2013_audit/true_oncourt_team_probe")
OUT.mkdir(parents=True, exist_ok=True)

TEAM_IDS = {
    "ATL": "1610612737", "BOS": "1610612738", "CLE": "1610612739", "NOP": "1610612740",
    "CHI": "1610612741", "DAL": "1610612742", "DEN": "1610612743", "GSW": "1610612744",
    "HOU": "1610612745", "LAC": "1610612746", "LAL": "1610612747", "MIA": "1610612748",
    "MIL": "1610612749", "MIN": "1610612750", "BKN": "1610612751", "NJN": "1610612751",
    "NYK": "1610612752", "ORL": "1610612753", "IND": "1610612754", "PHI": "1610612755",
    "PHX": "1610612756", "POR": "1610612757", "SAC": "1610612758", "SAS": "1610612759",
    "OKC": "1610612760", "SEA": "1610612760", "TOR": "1610612761", "UTA": "1610612762",
    "MEM": "1610612763", "VAN": "1610612763", "WAS": "1610612764", "DET": "1610612765",
    "CHA": "1610612766", "CHH": "1610612766",
}

s = requests.Session()
s.headers.update({
    "User-Agent": "playoff-translation-lab/1.0",
    "Accept": "application/json,text/plain,*/*",
})

def request(path, params, retries=4):
    wait = 1
    for _ in range(retries):
        r = s.get(BASE + path, params=params, timeout=45)
        print(r.status_code, path, params)
        if r.status_code == 200:
            try:
                return r.status_code, r.json()
            except Exception:
                return r.status_code, {"_raw": r.text[:3000]}
        if r.status_code in {429, 500, 502, 503, 504}:
            time.sleep(wait)
            wait = min(wait * 2, 12)
            continue
        return r.status_code, {"_text": r.text[:3000]}
    return "failed", {}

def first_lebron_2006_game():
    data = json.loads(Path("data-package.json").read_text())
    for r in data.get("playerGames", []):
        if int(r.get("year", 0) or 0) == 2006 and "lebron" in str(r.get("playerName","")).lower():
            return r
    raise SystemExit("No 2006 LeBron game found")

def collect_keys(x, keys):
    if isinstance(x, dict):
        keys.update(x.keys())
        for v in x.values():
            collect_keys(v, keys)
    elif isinstance(x, list):
        for v in x:
            collect_keys(v, keys)

def get_rows(data):
    if isinstance(data, dict):
        for key in ["single_row_table_data", "multi_row_table_data", "results", "team_results"]:
            v = data.get(key)
            if isinstance(v, list):
                return v
            if isinstance(v, dict) and v:
                return [v]
    return []

def summarize(label, status, params, data):
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", label)
    out = OUT / f"{safe}_status_{status}.json"
    out.write_text(json.dumps({"status": status, "params": params, "data": data}, indent=2), encoding="utf-8")

    if status != 200:
        return

    keys = set()
    collect_keys(data, keys)
    rows = get_rows(data)

    print("\n" + "="*100)
    print("GOOD:", label)
    print("saved:", out)
    print("row count:", len(rows))

    if rows:
        print("first row identity:")
        for k in ["Name", "TeamAbbreviation", "TeamId", "EntityId", "RowId", "OffPoss", "DefPoss", "Points", "OpponentPoints"]:
            if k in rows[0]:
                print(" ", k, "=", rows[0].get(k))

        print("first row useful fields:")
        for k in [
            "OffPoss", "DefPoss", "TotalPoss", "Points", "OpponentPoints",
            "EfgPct", "TsPct", "Turnovers", "OffRebounds", "FTA", "FtPoints",
            "AtRimFGA", "AtRimFGM", "AtRimFrequency", "AtRimAccuracy",
            "ShortMidRangeFGA", "ShortMidRangeFGM", "ShortMidRangeFrequency", "ShortMidRangeAccuracy",
            "LongMidRangeFGA", "LongMidRangeFGM", "LongMidRangeFrequency", "LongMidRangeAccuracy",
            "Corner3FGA", "Corner3FGM", "Corner3Frequency", "Corner3Accuracy",
            "Arc3FGA", "Arc3FGM", "Arc3Frequency", "Arc3Accuracy",
            "ShotQualityAvg"
        ]:
            if k in rows[0]:
                print(" ", k, "=", rows[0].get(k))

    print("interesting keys:")
    for k in sorted(keys):
        lk = k.lower()
        if any(t in lk for t in ["rim", "corner", "arc3", "midrange", "shotquality", "offposs", "defposs", "points", "opponentpoints", "ts", "efg", "turnover", "rebound", "fta"]):
            print(" ", k)

game = first_lebron_2006_game()

season = "2005-06"
player_id = str(game.get("nbaId") or "2544")
team = game.get("team")
opp = game.get("opponent")
team_id = TEAM_IDS.get(team)
opp_id = TEAM_IDS.get(opp)
date = game.get("date")
game_id = game.get("nbaGameId") or game.get("gameId")

print("Sample:")
print(json.dumps({
    "season": season,
    "player_id": player_id,
    "team": team,
    "team_id": team_id,
    "opponent": opp,
    "opp_id": opp_id,
    "date": date,
    "game_id": game_id,
}, indent=2))

# Important:
# 01-12 = all-leverage only. No Leverage parameter here.
endpoints = [
    "/get-wowy-stats/nba",
    "/get-wowy-combination-stats/nba",
]

types = ["Team", "Opponent", "Player"]

player_param_variants = [
    {"PlayerIds": player_id},
    {"PlayerId": player_id},
    {"PlayerIds": [player_id]},
    {"PlayerIds": f"{player_id},"},
]

scope_variants = {
    "season_all": {
        "Season": season, "SeasonType": "Playoffs", "TeamId": team_id,
    },
    "opponent_all": {
        "Season": season, "SeasonType": "Playoffs", "TeamId": team_id, "Opponent": opp_id,
    },
    "game_date_opp": {
        "Season": season, "SeasonType": "Playoffs", "TeamId": team_id,
        "Opponent": opp_id, "FromDate": date, "ToDate": date,
    },
    "game_id": {
        "Season": season, "SeasonType": "Playoffs", "TeamId": team_id,
        "GameId": game_id,
    },
}

summary = []

for endpoint in endpoints:
    for typ in types:
        for player_variant in player_param_variants:
            for scope_name, base in scope_variants.items():
                params = dict(base)
                params.update(player_variant)
                params["Type"] = typ

                label = f"{endpoint}__{typ}__{scope_name}__{list(player_variant.keys())[0]}"

                status, data = request(endpoint, params)
                summarize(label, status, params, data)

                summary.append({
                    "label": label,
                    "status": status,
                    "params": params,
                })

(OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print("\nDONE")
print("summary:", OUT / "summary.json")
