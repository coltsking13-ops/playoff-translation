import json, time, requests

API = "https://api.pbpstats.com/get-wowy-stats/nba"

PLAYER_ID = "201939"       # Stephen Curry
TEAM_ID = "1610612744"     # Warriors
OPP_ID = "1610612745"      # Rockets

params = {
    "Season": "2024-25",
    "SeasonType": "Playoffs",
    "TeamId": TEAM_ID,
    "PlayerId": PLAYER_ID,
    "Opponent": OPP_ID,
    "Type": "Team"
}

def get_json(params):
    for i in range(15):
        r = requests.get(API, params=params, timeout=30)
        if r.status_code == 200:
            return r.json()
        print("API", r.status_code, params)
        time.sleep(3 + i)
    raise RuntimeError("PBPStats kept failing on Type=Team too")

def walk(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk(v)

def find_best_row(data):
    rows = []
    for d in walk(data):
        if not isinstance(d, dict):
            continue
        if ("OffPoss" in d or "OffPossessions" in d) and ("Points" in d or "Pts" in d):
            rows.append(d)

    rows.sort(key=lambda d: float(d.get("OffPoss") or d.get("OffPossessions") or 0), reverse=True)
    return rows[0] if rows else None

def f(row, *keys):
    for k in keys:
        if k in row and row[k] not in [None, ""]:
            try:
                return float(row[k])
            except:
                pass
    return None

data = get_json(params)
row = find_best_row(data)

print("\nRAW BEST TEAM WOWY ROW")
print(json.dumps(row, indent=2)[:3000] if row else "NONE")

if not row:
    raise SystemExit("No usable Type=Team WOWY row found")

off_poss = f(row, "OffPoss", "OffPossessions")
def_poss = f(row, "DefPoss", "DefPossessions")
pts_for = f(row, "Points", "Pts")
pts_allowed = f(row, "OpponentPoints", "OppPoints", "OpponentPts")

ortg = 100 * pts_for / off_poss if off_poss and pts_for is not None else None
drtg = 100 * pts_allowed / def_poss if def_poss and pts_allowed is not None else None
net = ortg - drtg if ortg is not None and drtg is not None else None

print("\nCURRY 2025 VS HOU — ON COURT")
print("Off Poss:", off_poss)
print("Def Poss:", def_poss)
print("Warriors Points while Curry ON:", pts_for)
print("Rockets Points while Curry ON:", pts_allowed)
print("On-court ORTG:", round(ortg, 1) if ortg is not None else "missing")
print("On-court DRTG:", round(drtg, 1) if drtg is not None else "missing")
print("On-court NET:", round(net, 1) if net is not None else "missing")
