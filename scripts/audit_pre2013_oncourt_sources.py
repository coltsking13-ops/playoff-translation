import csv, json, re, zipfile
from pathlib import Path
from collections import Counter

ROOT = Path(".")
OUT = Path("public/data/pre2013_audit")
OUT.mkdir(parents=True, exist_ok=True)

EXCLUDE_DIRS = {".git", "node_modules", "__pycache__", "_cache"}

KEY_TERMS = [
    "pbp", "playbyplay", "play_by_play", "lineup", "on_off", "onoff", "wowy",
    "poss", "possession", "shot", "shotzone", "shot_zone", "tracking",
    "game_report", "teamgame_report", "totals", "player_sheets"
]

FIELD_GROUPS = {
    "game_level": [
        "gameid", "game_id", "nbaGameId", "date", "gamedate", "seriesCode",
        "round", "opponent", "team", "home", "away"
    ],
    "player_identity": [
        "playerid", "player_id", "nbaid", "personid", "player", "name",
        "playername", "PLAYER_ID", "PLAYER_NAME"
    ],
    "on_court_or_lineup": [
        "lineup", "lineupid", "oncourt", "on_court", "on", "off",
        "player1", "player2", "player3", "player4", "player5",
        "homeplayers", "awayplayers", "players", "floor"
    ],
    "six_factor": [
        "ortg", "drtg", "net", "ts", "efg", "tov", "turnover",
        "orb", "oreb", "ftr", "fta_rate", "3pa_rate", "poss",
        "offposs", "defposs", "pace", "usage"
    ],
    "shot_location": [
        "rim", "restricted", "paint", "interior",
        "mid", "midrange", "shortmid", "longmid",
        "corner", "corner3", "arc3", "above", "break",
        "shotzone", "shot_zone", "location", "x", "y",
        "distance", "shotdistance", "shot_quality", "shotquality"
    ],
    "events_needed_to_build": [
        "event", "eventtype", "event_type", "description", "actiontype",
        "period", "clock", "time", "points", "shot", "miss", "make",
        "rebound", "turnover", "foul", "freethrow", "free_throw"
    ],
}

def norm(s):
    return re.sub(r"[^a-z0-9]+", "", str(s).lower())

def field_hits(headers, terms):
    hits = []
    nh = {h: norm(h) for h in headers}
    for h, n in nh.items():
        raw = str(h).lower()
        for t in terms:
            nt = norm(t)
            if nt and nt in n:
                hits.append(h)
                break
            if str(t).lower() in raw:
                hits.append(h)
                break
    return sorted(set(hits))

def score_headers(headers):
    groups = {}
    score = 0
    for group, terms in FIELD_GROUPS.items():
        hits = field_hits(headers, terms)
        groups[group] = hits
        mult = 3 if group in ["game_level", "on_court_or_lineup", "shot_location"] else 2
        score += len(hits) * mult
    return score, groups

def should_skip(path):
    parts = set(path.parts)
    return bool(parts & EXCLUDE_DIRS)

def likely_candidate(path):
    s = str(path).lower()
    return any(t in s for t in KEY_TERMS)

def read_csv_header(path):
    try:
        with path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
            snip = f.read(4096)
            f.seek(0)
            dialect = csv.Sniffer().sniff(snip) if snip.strip() else csv.excel
            reader = csv.reader(f, dialect)
            return next(reader, [])
    except Exception:
        try:
            with path.open("r", encoding="latin-1", errors="ignore", newline="") as f:
                reader = csv.reader(f)
                return next(reader, [])
        except Exception:
            return []

def sample_csv_rows(path, n=2):
    rows = []
    try:
        with path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                rows.append(row)
                if i + 1 >= n:
                    break
    except Exception:
        pass
    return rows

def main():
    results = []

    for path in ROOT.rglob("*"):
        if not path.is_file() or should_skip(path):
            continue

        suffix = path.suffix.lower()
        if suffix not in [".csv", ".json", ".zip"]:
            continue

        if not likely_candidate(path):
            continue

        # CSV headers
        if suffix == ".csv":
            headers = read_csv_header(path)
            if not headers:
                continue

            score, groups = score_headers(headers)
            if score <= 0:
                continue

            results.append({
                "path": str(path),
                "kind": "csv",
                "size": path.stat().st_size,
                "score": score,
                "headers": headers[:250],
                "groups": groups,
                "sample_rows": sample_csv_rows(path, 2),
            })

        # ZIP names only, because patches may hold useful CSVs
        elif suffix == ".zip":
            try:
                with zipfile.ZipFile(path) as z:
                    names = z.namelist()
                hits = [n for n in names if any(t in n.lower() for t in KEY_TERMS)]
                if hits:
                    results.append({
                        "path": str(path),
                        "kind": "zip",
                        "size": path.stat().st_size,
                        "score": len(hits),
                        "candidate_members": hits[:120],
                    })
            except Exception:
                pass

        # small JSON only
        elif suffix == ".json" and path.stat().st_size < 20_000_000:
            try:
                txt = path.read_text(encoding="utf-8", errors="ignore")[:50000]
            except Exception:
                continue
            hits = [t for t in KEY_TERMS if t in txt.lower() or t in str(path).lower()]
            if hits:
                results.append({
                    "path": str(path),
                    "kind": "json",
                    "size": path.stat().st_size,
                    "score": len(hits),
                    "terms": hits,
                })

    results = sorted(results, key=lambda r: (-r["score"], r["path"]))
    (OUT / "pre2013_oncourt_source_candidates.json").write_text(json.dumps(results, indent=2), encoding="utf-8")

    print("Found candidates:", len(results))
    print("Wrote:", OUT / "pre2013_oncourt_source_candidates.json")

    print("\n=== TOP CANDIDATES ===")
    for r in results[:40]:
        print("\n" + "="*100)
        print(r["score"], r["kind"], r["path"], "size", r["size"])

        if r["kind"] == "csv":
            for group in ["game_level", "player_identity", "on_court_or_lineup", "six_factor", "shot_location", "events_needed_to_build"]:
                hits = r["groups"].get(group, [])
                print(group + ":", len(hits), ", ".join(hits[:35]))

            print("headers:", ", ".join(r["headers"][:80]))

            if r.get("sample_rows"):
                print("sample:")
                sample = r["sample_rows"][0]
                keep = {}
                useful = set()
                for hits in r["groups"].values():
                    useful.update(hits)
                for k in list(sample.keys()):
                    if k in useful:
                        keep[k] = sample.get(k)
                print(json.dumps(keep, indent=2)[:2000])

        elif r["kind"] == "zip":
            print("members:")
            for n in r["candidate_members"][:40]:
                print(" ", n)

        else:
            print("terms:", r.get("terms"))

if __name__ == "__main__":
    main()
