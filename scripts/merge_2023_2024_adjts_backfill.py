import json, re, time
from pathlib import Path
from collections import defaultdict

YEARS = {2023, 2024}
BACKFILL_DIR = Path("public/data/pbpstats/player_game_all_leverage_adjts")

FIELDS = [
    "AdjTS%", "rAdjTS", "AdjFGA", "AdjFTA",
    "ScoringTOV", "BadPassTOV", "BadPassOutOfBoundsTOV",
    "Heaves", "ZBounds", "ZBoards", "TechFTA",
    "AdjTS_source"
]

def filled(v):
    return v not in [None, "", [], {}]

def name(v):
    return str(v or "").lower().strip()

def key(r):
    return (
        str(r.get("year") or ""),
        str(r.get("date") or ""),
        str(r.get("team") or ""),
        str(r.get("opponent") or ""),
        name(r.get("playerName")),
    )

def load_backfill():
    out = {}
    for y in sorted(YEARS):
        p = BACKFILL_DIR / f"{y}.json"
        if not p.exists():
            print("MISSING:", p)
            continue

        rows = json.loads(p.read_text())
        print("Loaded", y, "rows:", len(rows), "from", p)

        for r in rows:
            out[key(r)] = r

    return out

def patch_package(data, backfill):
    game_patched = 0

    for r in data.get("playerGames", []):
        try:
            y = int(r.get("year") or 0)
        except:
            continue

        if y not in YEARS:
            continue

        bf = backfill.get(key(r))
        if not bf:
            continue

        changed = False
        for f in FIELDS:
            if f in bf and filled(bf.get(f)):
                r[f] = bf[f]
                changed = True

        if changed:
            game_patched += 1

    # Re-aggregate series AdjTS for 2023-2024 from patched game rows.
    by_series = defaultdict(list)

    for r in data.get("playerGames", []):
        try:
            y = int(r.get("year") or 0)
        except:
            continue

        if y not in YEARS:
            continue

        if not filled(r.get("AdjTS%")):
            continue

        k = (
            str(r.get("year") or ""),
            name(r.get("playerName")),
            str(r.get("team") or ""),
            str(r.get("opponent") or ""),
            str(r.get("seriesCode") or r.get("round") or "")
        )
        by_series[k].append(r)

    series_patched = 0

    for s in data.get("playerSeries", []):
        try:
            y = int(s.get("year") or 0)
        except:
            continue

        if y not in YEARS:
            continue

        k = (
            str(s.get("year") or ""),
            name(s.get("playerName")),
            str(s.get("team") or ""),
            str(s.get("opponent") or ""),
            str(s.get("seriesCode") or s.get("round") or "")
        )

        rows = by_series.get(k)
        if not rows:
            continue

        pts = sum(float(r.get("PTS") or 0) for r in rows)
        adj_fga = sum(float(r.get("AdjFGA") or 0) for r in rows)
        adj_fta = sum(float(r.get("AdjFTA") or 0) for r in rows)

        denom = 2 * (adj_fga + 0.44 * adj_fta)
        adjts = None if denom <= 0 else round(100 * pts / denom, 2)

        s["AdjFGA"] = round(adj_fga, 6)
        s["AdjFTA"] = round(adj_fta, 6)
        s["AdjTS%"] = adjts
        s["ScoringTOV"] = round(sum(float(r.get("ScoringTOV") or 0) for r in rows), 6)
        s["Heaves"] = round(sum(float(r.get("Heaves") or 0) for r in rows), 6)
        s["ZBounds"] = round(sum(float(r.get("ZBounds") or 0) for r in rows), 6)
        s["ZBoards"] = round(sum(float(r.get("ZBoards") or 0) for r in rows), 6)
        s["TechFTA"] = round(sum(float(r.get("TechFTA") or 0) for r in rows), 6)
        s["AdjTS_source"] = "verified 2023-2024 all-leverage PBPStats AdjTS backfill aggregated to series"

        # Keep existing rAdjTS if no opponent baseline exists.
        opp_vals = []
        for r in rows:
            opp = r.get("OppRSAdjTSAllowed")
            if filled(opp):
                try:
                    w = float(r.get("MIN") or r.get("POSS") or 1)
                    opp_vals.append((float(opp), w))
                except:
                    pass

        if adjts is not None and opp_vals:
            tw = sum(w for _, w in opp_vals)
            if tw:
                opp_avg = sum(v*w for v, w in opp_vals) / tw
                s["rAdjTS"] = round(adjts - opp_avg, 2)

        series_patched += 1

    return game_patched, series_patched

def patch_json(path, backfill):
    p = Path(path)
    if not p.exists():
        return

    backup = Path("backups") / f"{p.name}.before-2023-2024-adjts.{int(time.time())}.json"
    backup.write_text(p.read_text(errors="ignore"), encoding="utf-8")

    data = json.loads(p.read_text())
    g, s = patch_package(data, backfill)
    p.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")

    print("PATCHED", path)
    print("  game rows:", g)
    print("  series rows:", s)

def patch_index(backfill):
    p = Path("index.html")
    if not p.exists():
        return

    html = p.read_text(errors="ignore")

    m = re.search(
        r'(<script\s+id=["\']dataPackage["\']\s+type=["\']application/json["\']\s*>)(.*?)(</script\s*>)',
        html,
        flags=re.I | re.S
    )

    if not m:
        print("index.html: no embedded dataPackage found")
        return

    raw = m.group(2).strip()

    try:
        maybe = json.loads(raw)
        if isinstance(maybe, dict) and maybe.get("external"):
            print("index.html: external marker found, skipped embedded patch")
            return
    except:
        pass

    backup = Path("backups") / f"index.before-2023-2024-adjts.{int(time.time())}.html"
    backup.write_text(html, encoding="utf-8")

    data = json.loads(raw)
    g, s = patch_package(data, backfill)

    new_raw = json.dumps(data, separators=(",", ":"))
    html = html[:m.start(2)] + new_raw + html[m.end(2):]
    p.write_text(html, encoding="utf-8")

    print("PATCHED embedded index.html")
    print("  game rows:", g)
    print("  series rows:", s)

def audit(path):
    p = Path(path)
    if not p.exists():
        return

    data = json.loads(p.read_text())
    print("\nAUDIT", path)

    for table in ["playerGames", "playerSeries"]:
        print(table)
        for y in sorted(YEARS):
            rows = [r for r in data.get(table, []) if int(r.get("year") or 0) == y]
            adj = sum(1 for r in rows if filled(r.get("AdjTS%")))
            radj = sum(1 for r in rows if filled(r.get("rAdjTS")))
            print(f"  {y}: rows={len(rows)} AdjTS={adj} rAdjTS={radj}")

def main():
    backfill = load_backfill()

    patch_json("data-package.json", backfill)
    patch_json("data/data-package.json", backfill)
    patch_json("public/data/data-package.embedded.json", backfill)
    patch_index(backfill)

    audit("data-package.json")
    audit("public/data/data-package.embedded.json")

if __name__ == "__main__":
    main()
