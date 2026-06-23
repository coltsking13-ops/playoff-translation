import json
import re
import csv
from pathlib import Path
from collections import defaultdict, Counter

ROOT = Path(".")
PKG = ROOT / "data-package.json"
OUT = ROOT / "public/data/pre2013_audit"
OUT.mkdir(parents=True, exist_ok=True)

START_YEAR = 2001
END_YEAR = 2012

YEAR_KEYS = [
    "year", "Year", "playoffYear", "playoff_year",
    "seasonYear", "season_year", "SeasonYear",
    "season", "Season", "SEASON"
]

GAME_ID_KEYS = [
    "gameId", "GameId", "GAME_ID", "nbaGameId", "nba_game_id"
]

PLAYER_KEYS = [
    "player", "playerName", "Player", "PlayerName", "PLAYER_NAME",
    "name", "Name"
]

TEAM_KEYS = [
    "team", "Team", "TEAM", "teamAbbr", "team_abbr",
    "teamName", "TeamName"
]

OPP_KEYS = [
    "opponent", "Opponent", "opp", "Opp", "OPP",
    "oppTeam", "opponentTeam"
]

CATEGORY_PATTERNS = {
    "basic_box_score": [
        "points", "pts", "rebounds", "assists", "steals", "blocks",
        "turnovers", "minutes", "fga", "fgm", "fta", "ftm", "fg2a", "fg3a"
    ],
    "adj_ts_ingredients": [
        "badpass", "bad_pass", "bad pass",
        "outofbounds", "out_of_bounds", "out of bounds",
        "turnover", "turnovers",
        "heave", "nonheave", "non_heave",
        "technical", "techfta", "technical free throw",
        "selforeb", "self_orb", "self oreb",
        "zbound", "z_bound", "z board", "zboard",
        "fg2a", "fg3a", "fga", "fta", "points", "pts"
    ],
    "six_factor": [
        "adjts", "adj_ts", "adjusted true", "ts", "tspct",
        "efg", "efgpct",
        "ortg", "off_rating", "offrating", "offensive rating",
        "drtg", "def_rating", "defrating", "defensive rating",
        "net", "netrtg", "net_rating",
        "tov%", "tovpct", "turnover rate",
        "orb%", "orbpct", "offensive rebound",
        "ftr", "free throw rate",
        "usage", "poss", "pace"
    ],
    "shot_location": [
        "atrim", "at_rim", "at rim", "rim",
        "shortmid", "short_mid", "short mid",
        "longmid", "long_mid", "long mid",
        "corner3", "corner_3", "corner 3",
        "arc3", "arc_3", "above", "break3",
        "paint", "restricted",
        "shotzone", "shot_zone", "shot location",
        "frequency", "freq", "accuracy",
        "shotquality", "shot_quality"
    ],
    "on_court_team_context": [
        "on", "off", "onoff", "wowy", "lineup",
        "oncourt", "on_court",
        "teamon", "team_on",
        "offposs", "defposs",
        "team_ortg", "team_drtg", "team_net",
        "opp_ortg", "opp_drtg", "opp_net"
    ],
    "opponent_allowed_context": [
        "allowed", "oppallowed", "opp_allowed",
        "vs", "against",
        "oppdef", "opp_def",
        "defense_allowed",
        "allowed_ts", "allowed_efg",
        "allowed_rim", "allowed_corner",
        "allowed_ftr", "forced_tov"
    ]
}

def norm_key(k):
    return re.sub(r"[^a-z0-9]+", "", str(k).lower())

def key_matches_category(key, patterns):
    nk = norm_key(key)
    raw = str(key).lower()
    for pat in patterns:
        np = norm_key(pat)
        if np and np in nk:
            return True
        if pat in raw:
            return True
    return False

def parse_year(v):
    if v is None:
        return None

    if isinstance(v, int):
        if 1990 <= v <= 2035:
            return v

    s = str(v).strip()

    # "2011-12" or "2011-2012" means 2012 playoffs
    m = re.match(r"^(19|20)(\d{2})[-_/](\d{2}|\d{4})$", s)
    if m:
        first = int(s[:4])
        return first + 1

    # "2012"
    m = re.search(r"(19|20)\d{2}", s)
    if m:
        y = int(m.group(0))
        if 1990 <= y <= 2035:
            return y

    return None

def row_year(row):
    for k in YEAR_KEYS:
        if k in row:
            y = parse_year(row.get(k))
            if y:
                return y
    return None

def get_first(row, keys):
    for k in keys:
        if k in row and row.get(k) not in [None, ""]:
            return row.get(k)
    return None

def iter_tables(obj, prefix=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            name = f"{prefix}.{k}" if prefix else str(k)

            if isinstance(v, list) and v and isinstance(v[0], dict):
                yield name, v

            elif isinstance(v, dict):
                yield from iter_tables(v, name)

def collect_keys(rows, max_rows=5000):
    keys = set()
    nonnull = Counter()

    for i, row in enumerate(rows):
        if i >= max_rows:
            break
        if not isinstance(row, dict):
            continue
        for k, v in row.items():
            keys.add(k)
            if v not in [None, "", [], {}]:
                nonnull[k] += 1

    return keys, nonnull

def category_keys(keys, category):
    pats = CATEGORY_PATTERNS[category]
    return sorted([k for k in keys if key_matches_category(k, pats)])

def main():
    if not PKG.exists():
        raise SystemExit("data-package.json not found")

    print("Loading data-package.json. This may take a little bit...")
    data = json.loads(PKG.read_text())

    # If the JSON has a wrapped dataPackage, inspect that too.
    roots = [("root", data)]
    if isinstance(data, dict):
        for possible in ["dataPackage", "data", "package"]:
            if possible in data and isinstance(data[possible], dict):
                roots.append((possible, data[possible]))

    summary_rows = []
    inventory = {}
    samples = {}

    seen_names = set()

    for root_name, root_obj in roots:
        for table_name, rows in iter_tables(root_obj, root_name):
            if table_name in seen_names:
                continue
            seen_names.add(table_name)

            if not rows:
                continue

            by_year_count = Counter()
            pre_rows = []

            for row in rows:
                if not isinstance(row, dict):
                    continue
                y = row_year(row)
                if y:
                    by_year_count[y] += 1
                    if START_YEAR <= y <= END_YEAR:
                        pre_rows.append(row)

            if not pre_rows:
                continue

            keys, nonnull = collect_keys(pre_rows)

            cats = {}
            for cat in CATEGORY_PATTERNS:
                matched = category_keys(keys, cat)
                cats[cat] = matched

            years_present = sorted([y for y, c in by_year_count.items() if START_YEAR <= y <= END_YEAR and c > 0])

            score = (
                len(cats["adj_ts_ingredients"]) * 3
                + len(cats["six_factor"]) * 3
                + len(cats["shot_location"]) * 3
                + len(cats["on_court_team_context"]) * 2
                + len(cats["opponent_allowed_context"]) * 2
                + len(cats["basic_box_score"])
            )

            inventory[table_name] = {
                "rows_2001_2012": len(pre_rows),
                "years_present": years_present,
                "all_keys_count": len(keys),
                "category_matches": cats,
                "top_nonnull_keys": nonnull.most_common(80),
                "score": score,
            }

            for y in years_present:
                rows_y = [r for r in pre_rows if row_year(r) == y]
                sample = rows_y[0] if rows_y else {}
                candidate_sample = {}
                wanted_keys = set()
                for cat_keys in cats.values():
                    wanted_keys.update(cat_keys)
                for k in sorted(wanted_keys):
                    if k in sample:
                        candidate_sample[k] = sample.get(k)

                samples[f"{table_name}__{y}"] = {
                    "sample_identity": {
                        "year": y,
                        "gameId": get_first(sample, GAME_ID_KEYS),
                        "player": get_first(sample, PLAYER_KEYS),
                        "team": get_first(sample, TEAM_KEYS),
                        "opponent": get_first(sample, OPP_KEYS),
                    },
                    "candidate_fields": candidate_sample,
                    "all_keys": sorted(sample.keys())
                }

            for y in years_present:
                summary_rows.append({
                    "table": table_name,
                    "year": y,
                    "rows": by_year_count[y],
                    "basic_box_score_keys": len(cats["basic_box_score"]),
                    "adj_ts_ingredient_keys": len(cats["adj_ts_ingredients"]),
                    "six_factor_keys": len(cats["six_factor"]),
                    "shot_location_keys": len(cats["shot_location"]),
                    "on_court_context_keys": len(cats["on_court_team_context"]),
                    "opponent_allowed_keys": len(cats["opponent_allowed_context"]),
                    "score": score,
                })

    inventory_path = OUT / "field_inventory_2001_2012.json"
    samples_path = OUT / "samples_2001_2012.json"
    csv_path = OUT / "coverage_summary_2001_2012.csv"

    inventory_path.write_text(json.dumps(inventory, indent=2), encoding="utf-8")
    samples_path.write_text(json.dumps(samples, indent=2), encoding="utf-8")

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "table", "year", "rows",
            "basic_box_score_keys",
            "adj_ts_ingredient_keys",
            "six_factor_keys",
            "shot_location_keys",
            "on_court_context_keys",
            "opponent_allowed_keys",
            "score"
        ]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(sorted(summary_rows, key=lambda r: (-r["score"], r["table"], r["year"])))

    print("\n=== TOP PRE-2013 GAME-LEVEL CANDIDATE TABLES ===")
    ranked = sorted(inventory.items(), key=lambda kv: -kv[1]["score"])
    for name, info in ranked[:20]:
        print("\nTABLE:", name)
        print("rows 2001-2012:", info["rows_2001_2012"])
        print("years:", info["years_present"])
        print("score:", info["score"])

        for cat in [
            "basic_box_score",
            "adj_ts_ingredients",
            "six_factor",
            "shot_location",
            "on_court_team_context",
            "opponent_allowed_context"
        ]:
            keys = info["category_matches"][cat]
            print(f"{cat}: {len(keys)}")
            if keys:
                print("  " + ", ".join(keys[:35]))

    print("\nWrote:")
    print(inventory_path)
    print(samples_path)
    print(csv_path)

if __name__ == "__main__":
    main()
