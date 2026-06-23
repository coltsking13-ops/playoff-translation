import json, re
from pathlib import Path

YEAR = 2025

def n(v):
    try:
        return float(str(v).replace("+","").replace("%",""))
    except:
        return None

def yr(r):
    try:
        return int(r.get("year") or r.get("season") or r.get("Year") or 0)
    except:
        return 0

def norm(v):
    return str(v or "").lower().strip()

def games(r):
    for k in ["games","Games","GAMES"]:
        x = n(r.get(k))
        if x is not None:
            return int(x)
    return 1

def load_data(path):
    txt = path.read_text(errors="ignore")

    if path.suffix.lower() == ".html":
        m = re.search(
            r'<script\s+id=["\']dataPackage["\']\s+type=["\']application/json["\']\s*>(.*?)</script>',
            txt,
            flags=re.I | re.S
        )
        if not m:
            return None
        txt = m.group(1).strip()

    if "Stephen Curry" not in txt and "curry" not in txt.lower():
        return None

    try:
        obj = json.loads(txt)
    except Exception:
        return None

    if isinstance(obj, dict) and obj.get("external"):
        return None

    return obj

def find_curry_ids(data):
    ids = set()
    nba_ids = set()

    players = data.get("players", {})
    if isinstance(players, dict):
        for pid, p in players.items():
            if isinstance(p, dict) and "curry" in norm(p.get("name") or p.get("playerName")):
                ids.add(str(pid))
                if p.get("playerId"): ids.add(str(p.get("playerId")))
                if p.get("nbaId"): nba_ids.add(str(p.get("nbaId")))
                if p.get("NBA_ID"): nba_ids.add(str(p.get("NBA_ID")))

    return ids, nba_ids

def row_matches(r, ids, nba_ids, nested_curry=False):
    if not isinstance(r, dict):
        return False
    if yr(r) != YEAR:
        return False

    name_hit = "curry" in norm(r.get("playerName") or r.get("name") or r.get("PLAYER_NAME"))
    id_hit = str(r.get("playerId") or "") in ids
    nba_hit = str(r.get("nbaId") or r.get("NBA_ID") or r.get("PLAYER_ID") or "") in nba_ids

    return nested_curry or name_hit or id_hit or nba_hit

def walk_arrays(obj, label, ids, nba_ids, nested_curry=False):
    found = []

    if isinstance(obj, list):
        for r in obj:
            if isinstance(r, dict) and row_matches(r, ids, nba_ids, nested_curry):
                found.append((label, r))
        return found

    if not isinstance(obj, dict):
        return found

    for k, v in obj.items():
        if k == "players" and isinstance(v, dict):
            for pid, p in v.items():
                if isinstance(p, dict):
                    is_curry = "curry" in norm(p.get("name") or p.get("playerName")) or str(pid) in ids
                    found += walk_arrays(p, f"players.{pid}", ids, nba_ids, is_curry)
        elif isinstance(v, list):
            for r in v:
                if isinstance(r, dict) and row_matches(r, ids, nba_ids, nested_curry):
                    found.append((str(k), r))
        elif isinstance(v, dict):
            found += walk_arrays(v, str(k), ids, nba_ids, nested_curry)

    return found

paths = []
paths += [Path("data-package.json"), Path("data/data-package.json"), Path("public/data/data-package.embedded.json"), Path("index.html")]
paths += sorted(Path("backups").glob("*.json"))
paths += sorted(Path("backups").glob("*.html"))

best = None

for p in paths:
    if not p.exists():
        continue

    data = load_data(p)
    if not data:
        continue

    ids, nba_ids = find_curry_ids(data)
    rows = walk_arrays(data, "root", ids, nba_ids)

    hou = []
    for label, r in rows:
        opp = norm(r.get("opponent") or r.get("OPP") or r.get("Opponent"))
        if opp in ["hou", "houston", "houston rockets"] or "hou" in opp:
            hou.append((label, r))

    if not hou:
        continue

    one_game_hou = [(label,r) for label,r in hou if games(r) == 1]
    score = len(one_game_hou)

    print("\nFILE:", p)
    print("Curry 2025 HOU rows:", len(hou), "one-game rows:", score)
    for label, r in hou[:20]:
        print(
            " ", label,
            "| round=", r.get("round") or r.get("Round") or r.get("seriesCode"),
            "| games=", r.get("games") or r.get("Games") or r.get("GAMES"),
            "| MIN=", r.get("MIN"),
            "| AdjTS=", r.get("AdjTS%"),
            "| rAdjTS=", r.get("rAdjTS"),
            "| date=", r.get("date"),
            "| gameId=", r.get("gameId") or r.get("nbaGameId")
        )

    if best is None or score > best[0]:
        best = (score, str(p))

print("\nBEST:", best)
