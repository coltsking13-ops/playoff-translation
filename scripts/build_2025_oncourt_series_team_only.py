import json, time, requests
from pathlib import Path

API = "https://api.pbpstats.com/get-wowy-stats/nba"
YEAR = 2025
SEASON = "2024-25"

OUT = Path("public/data/pbpstats/player_oncourt_series_all/2025.json")
CACHE = Path("public/data/pbpstats/_cache_wowy_series")
CACHE.mkdir(parents=True, exist_ok=True)

TEAM_IDS = {
    "ATL":"1610612737","BOS":"1610612738","BKN":"1610612751","BRK":"1610612751",
    "CHA":"1610612766","CHI":"1610612741","CLE":"1610612739","DAL":"1610612742",
    "DEN":"1610612743","DET":"1610612765","GSW":"1610612744","HOU":"1610612745",
    "IND":"1610612754","LAC":"1610612746","LAL":"1610612747","MEM":"1610612763",
    "MIA":"1610612748","MIL":"1610612749","MIN":"1610612750","NOP":"1610612740",
    "NOH":"1610612740","NYK":"1610612752","OKC":"1610612760","ORL":"1610612753",
    "PHI":"1610612755","PHX":"1610612756","POR":"1610612757","SAC":"1610612758",
    "SAS":"1610612759","SA":"1610612759","TOR":"1610612761","UTA":"1610612762",
    "WAS":"1610612764"
}

def filled(v):
    return v not in [None, "", [], {}]

def norm(v):
    return str(v or "").strip()

def lower(v):
    return str(v or "").lower().strip()

def year(r):
    try:
        return int(r.get("year") or r.get("season") or 0)
    except:
        return 0

def get_players(data):
    out = {}
    players = data.get("players", {})
    if isinstance(players, dict):
        for pid, p in players.items():
            if not isinstance(p, dict):
                continue
            name = p.get("name") or p.get("playerName")
            nba = p.get("nbaId") or p.get("NBA_ID") or p.get("playerId")
            if name:
                out[lower(name)] = {
                    "playerId": str(pid),
                    "playerName": name,
                    "nbaId": str(nba) if filled(nba) else ""
                }
    return out

def candidate_rows(data):
    players = get_players(data)
    cands = {}

    sources = []
    sources += data.get("playerSeries", []) or []
    sources += data.get("playerGames", []) or []

    for r in sources:
        if not isinstance(r, dict) or year(r) != YEAR:
            continue

        player_name = r.get("playerName") or r.get("name")
        team = norm(r.get("team"))
        opp = norm(r.get("opponent"))

        if not player_name or not team or not opp:
            continue

        if team not in TEAM_IDS or opp not in TEAM_IDS:
            continue

        pinfo = players.get(lower(player_name), {})
        nba_id = r.get("nbaId") or r.get("NBA_ID") or pinfo.get("nbaId")
        player_id = r.get("playerId") or pinfo.get("playerId")

        if not filled(nba_id):
            continue

        round_name = r.get("round") or r.get("seriesCode") or "Playoff Series"

        key = (
            str(nba_id),
            lower(player_name),
            team,
            opp,
            str(round_name)
        )

        cands[key] = {
            "year": YEAR,
            "season": SEASON,
            "playerId": player_id,
            "nbaId": str(nba_id),
            "playerName": player_name,
            "team": team,
            "opponent": opp,
            "round": round_name,
            "seriesCode": r.get("seriesCode") or round_name,
            "teamId": TEAM_IDS[team],
            "opponentId": TEAM_IDS[opp]
        }

    return list(cands.values())

def cache_path(c):
    name = f'{SEASON}_{c["teamId"]}_{c["opponentId"]}_{c["nbaId"]}_Team.json'
    return CACHE / name

def get_json(c):
    p = cache_path(c)
    if p.exists() and p.stat().st_size > 2:
        try:
            return json.loads(p.read_text())
        except:
            pass

    params = {
        "Season": SEASON,
        "SeasonType": "Playoffs",
        "TeamId": c["teamId"],
        "PlayerId": c["nbaId"],
        "Opponent": c["opponentId"],
        "Type": "Team"
    }

    for i in range(12):
        try:
            r = requests.get(API, params=params, timeout=30)
            if r.status_code == 200:
                p.write_text(r.text)
                return r.json()
            print("API", r.status_code, params, flush=True)
        except Exception as e:
            print("ERR", e, params, flush=True)
        time.sleep(3 + i)

    return None

def walk(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk(v)

def best_row(data):
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
        if k in row and filled(row.get(k)):
            try:
                return float(row.get(k))
            except:
                pass
    return None

def build_row(c, row):
    off_poss = f(row, "OffPoss", "OffPossessions")
    def_poss = f(row, "DefPoss", "DefPossessions")
    pts_for = f(row, "Points", "Pts")
    pts_allowed = f(row, "OpponentPoints", "OppPoints", "OpponentPts")

    ortg = 100 * pts_for / off_poss if off_poss and pts_for is not None else None
    drtg = 100 * pts_allowed / def_poss if def_poss and pts_allowed is not None else None
    net = ortg - drtg if ortg is not None and drtg is not None else None

    out = dict(c)
    out.update({
        "onOffPoss": off_poss,
        "onDefPoss": def_poss,
        "onTeamPoints": pts_for,
        "onOpponentPoints": pts_allowed,
        "onTeamORTG": round(ortg, 2) if ortg is not None else None,
        "onTeamDRTG": round(drtg, 2) if drtg is not None else None,
        "onTeamNET": round(net, 2) if net is not None else None,
        "source": "PBPStats get-wowy-stats Type=Team, player ON court"
    })

    return out

def main():
    data = json.loads(Path("data-package.json").read_text())
    cands = candidate_rows(data)

    print("Candidates:", len(cands), flush=True)

    existing = []
    if OUT.exists() and OUT.stat().st_size > 2:
        existing = json.loads(OUT.read_text())

    done = {
        (str(r.get("nbaId")), r.get("team"), r.get("opponent"), str(r.get("round")))
        for r in existing
    }

    rows = list(existing)

    for i, c in enumerate(cands, 1):
        k = (str(c.get("nbaId")), c.get("team"), c.get("opponent"), str(c.get("round")))
        if k in done:
            continue

        print(f'{i}/{len(cands)} {c["playerName"]} {c["team"]} vs {c["opponent"]} {c["round"]}', flush=True)

        data = get_json(c)
        if not data:
            print("  no data", flush=True)
            continue

        row = best_row(data)
        if not row:
            print("  no stat row", flush=True)
            continue

        out = build_row(c, row)
        print("  ORTG", out["onTeamORTG"], "DRTG", out["onTeamDRTG"], "NET", out["onTeamNET"], flush=True)

        rows.append(out)
        done.add(k)

        OUT.write_text(json.dumps(rows, separators=(",", ":")))

        time.sleep(0.7)

    OUT.write_text(json.dumps(rows, separators=(",", ":")))
    print("WROTE", OUT, "rows", len(rows), flush=True)

if __name__ == "__main__":
    main()
