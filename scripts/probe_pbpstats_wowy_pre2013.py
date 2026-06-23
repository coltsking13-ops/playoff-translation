import json, time, re
from pathlib import Path
import requests

BASE = "https://api.pbpstats.com"
OUT = Path("public/data/pre2013_audit/pbpstats_wowy_probe")
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

session = requests.Session()
session.headers.update({
    "User-Agent": "playoff-translation-lab/1.0",
    "Accept": "application/json,text/plain,*/*",
})

def get_json(path, params=None, retries=4):
    wait = 1
    url = BASE + path
    for _ in range(retries):
        r = session.get(url, params=params or {}, timeout=45)
        print(r.status_code, path, params or {})
        if r.status_code == 200:
            try:
                return r.status_code, r.json()
            except Exception:
                return r.status_code, {"_raw": r.text[:5000]}
        if r.status_code in {429, 500, 502, 503, 504}:
            time.sleep(wait)
            wait = min(wait * 2, 12)
            continue
        return r.status_code, {"_text": r.text[:3000]}
    return "failed", {}

def allowed_params(schema, template):
    try:
        return {p.get("name") for p in schema["paths"][template]["get"].get("parameters", []) if p.get("name")}
    except Exception:
        return set()

def keep(params, allowed):
    return {k: v for k, v in params.items() if k in allowed and v not in [None, ""]}

def find_lebron_2006_game():
    data = json.loads(Path("data-package.json").read_text())
    for r in data.get("playerGames", []):
        if int(r.get("year", 0) or 0) == 2006 and "lebron" in str(r.get("playerName", "")).lower():
            return r
    return None

def collect_keys(x, keys):
    if isinstance(x, dict):
        keys.update(x.keys())
        for v in x.values():
            collect_keys(v, keys)
    elif isinstance(x, list):
        for v in x:
            collect_keys(v, keys)

def print_interesting(label, data):
    keys = set()
    collect_keys(data, keys)

    print("\nGOOD RESPONSE:", label)
    print("interesting keys:")
    for k in sorted(keys):
        lk = str(k).lower()
        if any(t in lk for t in [
            "on", "off", "rtg", "poss", "rim", "corner", "arc", "mid",
            "shot", "quality", "ts", "efg", "tov", "turnover",
            "orb", "oreb", "ftr", "fta", "frequency", "accuracy",
            "team", "opponent", "player", "name"
        ]):
            print(" ", k)

    def walk(x, depth=0, path="root"):
        if depth > 3:
            return
        pad = "  " * depth
        if isinstance(x, dict):
            print(pad + path, "dict keys:", list(x.keys())[:50])
            for kk, vv in list(x.items())[:5]:
                walk(vv, depth + 1, path + "." + str(kk))
        elif isinstance(x, list):
            print(pad + path, "list len:", len(x))
            if x:
                walk(x[0], depth + 1, path + "[0]")
        else:
            print(pad + path, type(x).__name__, repr(x)[:120])

    print("\nsample structure:")
    walk(data)

def main():
    status, schema = get_json("/openapi.json")
    if status != 200:
        raise SystemExit("Could not fetch OpenAPI schema")

    print("\nRelevant endpoints:")
    for path in sorted(schema.get("paths", {})):
        if any(t in path.lower() for t in ["wowy", "on-off", "onoff"]):
            print(" ", path)

    game = find_lebron_2006_game()
    print("\nSample row:")
    print(json.dumps(game, indent=2)[:2500])

    if not game:
        raise SystemExit("No LeBron 2006 game row found")

    season = "2005-06"
    player_id = str(game.get("nbaId") or "2544")
    team = game.get("team")
    opp = game.get("opponent")
    date = game.get("date")
    game_id = game.get("nbaGameId") or game.get("gameId")
    team_id = TEAM_IDS.get(str(team))
    opp_id = TEAM_IDS.get(str(opp))

    print("\nResolved:")
    print("season:", season)
    print("player_id:", player_id)
    print("team:", team, team_id)
    print("opponent:", opp, opp_id)
    print("date:", date)
    print("game_id:", game_id)

    endpoint_pairs = [
        ("/get-wowy-stats/{league}", "/get-wowy-stats/nba"),
        ("/get-wowy-combination-stats/{league}", "/get-wowy-combination-stats/nba"),
    ]

    type_values = ["Team", "Opponent", "Player", "Lineup", "LineupOpponent"]

    summary = {}

    for template, actual in endpoint_pairs:
        allowed = allowed_params(schema, template)
        print("\n" + "="*100)
        print("Testing", actual)
        print("allowed params:", sorted(allowed))

        base = {
            "Season": season,
            "SeasonType": "Playoffs",
            "TeamId": team_id,
            "Opponent": opp_id,
            "PlayerIds": player_id,
            "PlayerId": player_id,
            "GameId": game_id,
            "FromDate": date,
            "ToDate": date,
        }

        variants = {
            "season_all": base | {"GameId": None, "FromDate": None, "ToDate": None, "Opponent": None},
            "opponent_all": base | {"GameId": None, "FromDate": None, "ToDate": None},
            "game_date_opp": base | {"GameId": None},
            "game_id": base | {"FromDate": None, "ToDate": None, "Opponent": None},
        }

        for typ in type_values:
            for label, params in variants.items():
                params2 = dict(params)
                params2["Type"] = typ

                final = keep(params2, allowed)

                # 2001-2012 is ALL LEVERAGE ONLY.
                final.pop("Leverage", None)

                if "Season" not in final or "SeasonType" not in final:
                    continue

                test_name = f"{actual}_{typ}_{label}"
                status, data = get_json(actual, final)

                safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", test_name)
                out = OUT / f"{safe}_status_{status}.json"
                out.write_text(json.dumps({
                    "status": status,
                    "params": final,
                    "data": data,
                }, indent=2), encoding="utf-8")

                summary[test_name] = {"status": status, "params": final, "file": str(out)}

                if status == 200:
                    print_interesting(test_name, data)
                    print("saved:", out)

    (OUT / "probe_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("\nDONE")
    print("summary:", OUT / "probe_summary.json")

if __name__ == "__main__":
    main()
