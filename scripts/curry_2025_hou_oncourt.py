import json, time, requests
from pathlib import Path

API = "https://api.pbpstats.com/get-wowy-stats/nba"

PLAYER_ID = "201939"       # Stephen Curry
TEAM_ID = "1610612744"     # Golden State Warriors
OPP_ID = "1610612745"      # Houston Rockets

PARAMS_BASE = {
    "Season": "2024-25",
    "SeasonType": "Playoffs",
    "TeamId": TEAM_ID,
    "PlayerId": PLAYER_ID,
    "Opponent": OPP_ID,
}

def get_json(params):
    for i in range(12):
        r = requests.get(API, params=params, timeout=30)
        if r.status_code == 200:
            return r.json()
        print("API", r.status_code, params)
        time.sleep(3 + i)
    raise RuntimeError("PBPStats kept failing")

def walk(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk(v)

def find_stat_row(data):
    candidates = []
    for d in walk(data):
        keys = set(d.keys())
        if ("OffPoss" in keys or "OffPossessions" in keys) and ("Points" in keys or "Pts" in keys):
            candidates.append(d)

    # Prefer rows with actual possessions
    candidates = sorted(
        candidates,
        key=lambda d: float(d.get("OffPoss") or d.get("OffPossessions") or 0),
        reverse=True
    )
    return candidates[0] if candidates else None

def f(row, *keys):
    for k in keys:
        if k in row and row[k] not in [None, ""]:
            try:
                return float(row[k])
            except:
                pass
    return None

team_params = dict(PARAMS_BASE)
team_params["Type"] = "Team"

opp_params = dict(PARAMS_BASE)
opp_params["Type"] = "Opponent"

team_data = get_json(team_params)
opp_data = get_json(opp_params)

team_row = find_stat_row(team_data)
opp_row = find_stat_row(opp_data)

print("\nTEAM ROW")
print(json.dumps(team_row, indent=2)[:2500] if team_row else "none")

print("\nOPP ROW")
print(json.dumps(opp_row, indent=2)[:2500] if opp_row else "none")

if not team_row:
    raise SystemExit("Could not find team WOWY row")

off_poss = f(team_row, "OffPoss", "OffPossessions")
def_poss = f(team_row, "DefPoss", "DefPossessions")
pts_for = f(team_row, "Points", "Pts")
pts_allowed = f(team_row, "OpponentPoints", "OppPoints", "OpponentPts")

ortg = 100 * pts_for / off_poss if pts_for is not None and off_poss else None
drtg = 100 * pts_allowed / def_poss if pts_allowed is not None and def_poss else None
net = ortg - drtg if ortg is not None and drtg is not None else None

print("\nCURRY 2025 VS HOU — ON COURT")
print("Off Poss:", off_poss)
print("Def Poss:", def_poss)
print("Team Points:", pts_for)
print("Opponent Points:", pts_allowed)
print("On-court ORTG:", round(ortg, 1) if ortg is not None else "missing")
print("On-court DRTG:", round(drtg, 1) if drtg is not None else "missing")
print("On-court NET:", round(net, 1) if net is not None else "missing")
