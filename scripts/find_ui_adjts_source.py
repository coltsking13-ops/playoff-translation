from pathlib import Path
import re

needles = [
    "2022-05-26",
    "42.3",
    "RADJTS",
    "rAdjTS",
    "AdjTS%",
    "player_game_adjts_ingredients",
    "playerGames",
]

paths = []
for root in ["index.html", "public", "data", "patch", "patch2", "patch3", "patch4", "patch5", "scripts"]:
    p = Path(root)
    if p.is_file():
        paths.append(p)
    elif p.exists():
        paths.extend([x for x in p.rglob("*") if x.is_file() and x.suffix.lower() in [".html",".js",".json",".csv",".py"]])

for p in paths:
    try:
        txt = p.read_text(errors="ignore")
    except Exception:
        continue

    hits = [n for n in needles if n in txt]
    if hits:
        print("\n" + "="*100)
        print(p, "size", p.stat().st_size, "hits", hits)

        for n in hits[:4]:
            idx = txt.find(n)
            if idx >= 0:
                start = max(0, idx - 180)
                end = min(len(txt), idx + 260)
                snippet = txt[start:end].replace("\n", " ")
                print(f"\n--- around {n} ---")
                print(snippet[:700])
