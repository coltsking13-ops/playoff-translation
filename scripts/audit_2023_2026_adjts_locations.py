import json
from pathlib import Path
from collections import Counter

FIELDS = [
    "AdjTS%", "rAdjTS", "AdjFGA", "AdjFTA", "AdjTS_source",
    "ScoringTOV", "BadPassTOV", "BadPassTurnovers", "BadPassOutOfBoundsTOV", "BadPassOutOfBoundsTurnovers",
    "Heaves", "Heaves_Est", "TechFTA", "TechFTA_Est",
    "ZBounds", "ZBoards", "SelfOReb",
    "teamAdjTS%", "oppTeamAdjTS%", "OppRSAdjTSAllowed",
    "PTS", "FGA", "FTA", "TOV", "TS%"
]

def filled(v):
    return v not in [None, "", [], {}]

def audit_rows(name, rows):
    print("\n" + "="*90)
    print(name)
    for y in range(2023, 2027):
        yr = [r for r in rows if int(r.get("year", 0) or 0) == y]
        print(f"\nYEAR {y} rows={len(yr)}")
        if not yr:
            continue
        for f in FIELDS:
            n = sum(1 for r in yr if filled(r.get(f)))
            pct = round(100*n/len(yr), 1)
            if n:
                print(f"{f:32s} {n:6d}/{len(yr):6d} {pct:5.1f}%")
        missing = [f for f in FIELDS if sum(1 for r in yr if filled(r.get(f))) == 0]
        print("missing completely:", missing)

def load_json(path):
    try:
        return json.loads(Path(path).read_text())
    except Exception as e:
        return None

data = load_json("data-package.json")
if not data:
    raise SystemExit("Could not load data-package.json")

print("data-package tables:", [k for k,v in data.items() if isinstance(v, list)][:30])

for table in ["playerGames", "playerSeries", "playerSeasons"]:
    rows = data.get(table, [])
    if isinstance(rows, list):
        audit_rows(f"data-package.json::{table}", rows)

print("\n" + "="*90)
print("Separate PBPStats all-leverage AdjTS files")
folder = Path("public/data/pbpstats/player_game_all_leverage_adjts")
if not folder.exists():
    print("folder does not exist:", folder)
else:
    for p in sorted(folder.glob("*.json")):
        if p.stem not in ["2023", "2024", "2025", "2026"]:
            continue
        rows = load_json(p) or []
        print(f"\n{p} rows={len(rows)} size={p.stat().st_size}")
        for f in FIELDS:
            n = sum(1 for r in rows if filled(r.get(f)))
            if n:
                print(f"{f:32s} {n:6d}/{len(rows):6d} {round(100*n/len(rows),1) if rows else 0:5.1f}%")

print("\n" + "="*90)
print("Current Medium+ files, just to avoid confusion")
folder = Path("public/data/pbpstats/player_game_low_removed")
for p in sorted(folder.glob("*.json")):
    if p.stem in ["2023", "2024", "2025", "2026"]:
        rows = load_json(p) or []
        print(f"{p} rows={len(rows)} size={p.stat().st_size}")
