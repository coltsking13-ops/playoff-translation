#!/usr/bin/env python3
import csv
import json
from pathlib import Path

GAME_IDS = {"42500311", "0042500311"}
PLAYER_BITS = ["victor_wembanyama_1641705", "1641705", "wembanyama", "victor"]
OUT = Path("logs/wemby_g1_okc_local_context.csv")

FILES = [
    Path("public/data/data-package.embedded.json"),
    Path("public/data/data-package.json"),
    Path("data-package.json"),
    Path("data/data-package.json"),
    Path("public/data/pbpstats/player_game_low_removed/2026.json"),
]

def read_json(p):
    try:
        return json.loads(p.read_text(errors="ignore"))
    except Exception:
        return None

def walk(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk(v)

def s(x):
    return str(x or "")

def norm_key(k):
    return str(k).lower().replace(" ", "").replace("_", "").replace("-", "").replace("%", "pct")

def is_wemby(row):
    blob = " ".join(s(v).lower() for v in row.values())
    return any(bit in blob for bit in PLAYER_BITS)

def is_game(row):
    vals = [s(row.get(k)) for k in ["gameId", "GAME_ID", "nbaGameId", "nbaGameID", "game_id", "gameRowId"]]
    blob = " ".join(vals)
    return any(gid in blob for gid in GAME_IDS)

def num(v):
    if v in [None, "", "—"]:
        return None
    try:
        return float(str(v).replace("%", "").replace(",", "").strip())
    except Exception:
        return None

def fmt(v):
    if v is None:
        return "—"
    return f"{v:.1f}"

def merge_rows(rows):
    merged = {}
    sources = []
    for file, row in rows:
        sources.append(file)
        for k, v in row.items():
            if v in [None, ""]:
                continue
            if k not in merged:
                merged[k] = v
    merged["_sources"] = sorted(set(sources))
    return merged

def get_first(row, names):
    keymap = {norm_key(k): k for k in row.keys()}
    for name in names:
        nk = norm_key(name)
        if nk in keymap:
            return row.get(keymap[nk]), keymap[nk]
    return None, None

def find_by_patterns(row, must_have=(), any_have=(), avoid=()):
    out = []
    for k, v in row.items():
        nk = norm_key(k)
        if any(a in nk for a in avoid):
            continue
        if must_have and not all(m in nk for m in must_have):
            continue
        if any_have and not any(a in nk for a in any_have):
            continue
        if num(v) is not None:
            out.append((k, num(v)))
    return out

def print_pair(label, team_names, opp_names, row):
    team_v, team_k = get_first(row, team_names)
    opp_v, opp_k = get_first(row, opp_names)
    team_n = num(team_v)
    opp_n = num(opp_v)
    adj = None
    if team_n is not None and opp_n is not None:
        adj = team_n - opp_n

    print(f"{label:<24} {fmt(team_n):>10}   {fmt(opp_n):>10}   {fmt(adj):>10}   {team_k or ''} / {opp_k or ''}")
    return {
        "metric": label,
        "team_or_on": team_n,
        "opp_allowed": opp_n,
        "adjusted": adj,
        "team_key": team_k or "",
        "opp_key": opp_k or "",
    }

rows = []

for p in FILES:
    if not p.exists():
        continue
    obj = read_json(p)
    if obj is None:
        continue
    for row in walk(obj):
        if not isinstance(row, dict):
            continue
        if is_wemby(row) and is_game(row):
            rows.append((str(p), row))

print("=" * 90)
print("WEMBY GAME 1 VS OKC LOCAL ROWS FOUND:", len(rows))
print("=" * 90)

if not rows:
    print("No local rows found for Wemby Game 1 vs OKC.")
    raise SystemExit(1)

merged = merge_rows(rows)

print("\nSources:")
for src in merged["_sources"]:
    print(" -", src)

print("\nBasic row:")
for k in ["playerName","playerId","year","date","gameId","gameRowId","round","seriesCode","team","opponent","opp","MIN","PTS"]:
    if k in merged:
        print(f"{k}: {merged[k]}")

# Detect true ON-court fields
on_keys = []
for k in merged:
    nk = norm_key(k)
    if ("on" in nk or "wowy" in nk) and any(x in nk for x in ["team","opp","poss","rtg","rim","shot","freq","acc","efg","tov","orb","dreb"]):
        on_keys.append(k)

print("\n" + "=" * 90)
print("ON-COURT FIELD CHECK")
print("=" * 90)
if on_keys:
    print("Found possible ON-court/WOWY keys:")
    for k in on_keys[:80]:
        print(" -", k, "=", merged[k])
else:
    print("No obvious ON-court/WOWY fields found in the local row.")
    print("So this script can show Wemby game/team/opponent context, but it will NOT fake true ON-court 6 factors.")
    print("True ON-court needs a possession/WOWY source for this local 2026 game.")

print("\n" + "=" * 90)
print("SIX FACTORS / TEAM CONTEXT / OPPONENT-ADJUSTED WHERE AVAILABLE")
print("=" * 90)
print(f"{'Metric':<24} {'Team/ON':>10}   {'Opp Allow':>10}   {'Adj':>10}   Keys")
print("-" * 90)

results = []

pairs = [
    ("AdjTS%", ["teamAdjTS%","teamAdjTS","onTeamAdjTS%","onTeamAdjTS"], ["oppRSAdjTSAllowed","oppAdjTSAllowed","oppTeamAdjTSAllowed"]),
    ("TS%", ["teamTS%","teamTS","onTeamTS%","onTeamTS"], ["oppTeamTS%","oppTSAllowed","oppTeamTSAllowed"]),
    ("eFG%", ["teameFG%","teamEFG%","eFG%","onTeamEFG%"], ["oppeFGAllowed","oppEFGAllowed","oppTeameFGAllowed"]),
    ("TOV%", ["teamTOV%","teamTOV","onTeamTOV%"], ["oppTOVAllowed","oppTeamTOVAllowed"]),
    ("ORB%", ["teamORB%","teamORB","onTeamORB%"], ["oppORBAllowed","oppTeamORBAllowed"]),
    ("DREB%", ["teamDREB%","teamDREB","onTeamDREB%"], ["oppDREBAllowed","oppTeamDREBAllowed"]),
    ("AST%", ["teamAST%","teamAST","AST%","onTeamAST%"], ["oppASTAllowed","oppTeamASTAllowed"]),
    ("USG%", ["USG%","usage","USG"], ["oppUSGAllowed"]),
    ("ORTG", ["teamORTG","teamORtg","onTeamORTG","ORTG"], ["oppORTGAllowed","oppTeamORTGAllowed"]),
    ("DRTG", ["teamDRTG","teamDRtg","onTeamDRTG","DRTG"], ["oppDRTGAllowed","oppTeamDRTGAllowed"]),
    ("NET", ["teamNET","onTeamNET","NET"], ["oppNETAllowed","oppTeamNETAllowed"]),
]

for label, team_names, opp_names in pairs:
    results.append(print_pair(label, team_names, opp_names, merged))

print("\n" + "=" * 90)
print("SHOT LOCATION / OPPONENT-ADJUSTED WHERE AVAILABLE")
print("=" * 90)
print(f"{'Metric':<24} {'Team/ON':>10}   {'Opp Allow':>10}   {'Adj':>10}   Keys")
print("-" * 90)

shot_pairs = [
    ("Rim Freq", ["teamRimFreq","teamRimFrequency","onTeamRimFreq"], ["oppRimFreqAllowed","oppRimFrequencyAllowed"]),
    ("Rim Acc", ["teamRimAcc","teamRimAccuracy","onTeamRimAcc"], ["oppRimAccAllowed","oppRimAccuracyAllowed"]),
    ("Paint Freq", ["teamPaintFreq","teamPaintFrequency","onTeamPaintFreq"], ["oppPaintFreqAllowed","oppPaintFrequencyAllowed"]),
    ("Paint Acc", ["teamPaintAcc","teamPaintAccuracy","onTeamPaintAcc"], ["oppPaintAccAllowed","oppPaintAccuracyAllowed"]),
    ("Mid Freq", ["teamMidFreq","teamMidFrequency","onTeamMidFreq"], ["oppMidFreqAllowed","oppMidFrequencyAllowed"]),
    ("Mid Acc", ["teamMidAcc","teamMidAccuracy","onTeamMidAcc"], ["oppMidAccAllowed","oppMidAccuracyAllowed"]),
    ("Corner 3 Freq", ["teamCorner3Freq","teamCornerThreeFreq","onTeamCorner3Freq"], ["oppCorner3FreqAllowed","oppCornerThreeFreqAllowed"]),
    ("Corner 3 Acc", ["teamCorner3Acc","teamCornerThreeAcc","onTeamCorner3Acc"], ["oppCorner3AccAllowed","oppCornerThreeAccAllowed"]),
    ("Arc 3 Freq", ["teamArc3Freq","teamAboveBreak3Freq","onTeamArc3Freq"], ["oppArc3FreqAllowed","oppAboveBreak3FreqAllowed"]),
    ("Arc 3 Acc", ["teamArc3Acc","teamAboveBreak3Acc","onTeamArc3Acc"], ["oppArc3AccAllowed","oppAboveBreak3AccAllowed"]),
]

for label, team_names, opp_names in shot_pairs:
    results.append(print_pair(label, team_names, opp_names, merged))

print("\n" + "=" * 90)
print("ALL CONTEXT KEYS FOUND ON MERGED ROW")
print("=" * 90)
interesting = []
for k, v in merged.items():
    nk = norm_key(k)
    if any(x in nk for x in ["team", "opp", "rim", "paint", "mid", "corner", "arc", "freq", "acc", "adjts", "ts", "efg", "orb", "dreb", "ast", "usg", "ortg", "drtg", "net"]):
        interesting.append((k, v))

for k, v in sorted(interesting):
    print(f"{k}: {v}")

OUT.parent.mkdir(exist_ok=True)
with OUT.open("w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["metric","team_or_on","opp_allowed","adjusted","team_key","opp_key"])
    w.writeheader()
    w.writerows(results)

print("\nSaved CSV:", OUT)
