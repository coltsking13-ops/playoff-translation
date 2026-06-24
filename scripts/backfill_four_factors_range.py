#!/usr/bin/env python3
import argparse, json, time
from pathlib import Path
from collections import Counter
import requests

OUT = Path("public/data/on_court_all_leverage")
PLAYERS = Path("v2/data/players")
RAW = OUT / "raw_years" / "four_factor_on_off_range"
URL = "https://api.pbpstats.com/get-four-factor-on-off/nba"

TEAM_IDS = {
    "ATL":1610612737,"BOS":1610612738,"CLE":1610612739,"NOP":1610612740,"NOH":1610612740,"NOK":1610612740,
    "CHI":1610612741,"DAL":1610612742,"DEN":1610612743,"GSW":1610612744,"HOU":1610612745,"LAC":1610612746,
    "LAL":1610612747,"MIA":1610612748,"MIL":1610612749,"MIN":1610612750,"BKN":1610612751,"NJN":1610612751,
    "NYK":1610612752,"ORL":1610612753,"IND":1610612754,"PHI":1610612755,"PHX":1610612756,"POR":1610612757,
    "SAC":1610612758,"SAS":1610612759,"OKC":1610612760,"SEA":1610612760,"TOR":1610612761,"UTA":1610612762,
    "MEM":1610612763,"VAN":1610612763,"WAS":1610612764,"DET":1610612765,"CHA":1610612766,"CHH":1610612766
}

def season_str(year):
    return f"{year-1}-{str(year)[-2:]}"

def norm(x):
    if x is None:
        return ""
    s = str(x).strip()
    return s[:-2] if s.endswith(".0") else s

def player_id_api(x):
    s = norm(x)
    # V2 sometimes stores IDs like "aaron_gordon_203932"; PBPStats needs "203932"
    if "_" in s:
        last = s.split("_")[-1]
        if last.isdigit():
            return last
    return s

def get(row, keys):
    for k in keys:
        if isinstance(row, dict) and row.get(k) not in [None, "", "—"]:
            return row.get(k)
    return None

def row_year(row):
    y = get(row, ["year", "season", "SEASON", "YEAR"])
    if isinstance(y, str) and "-" in y:
        try:
            return int(y[:4]) + 1
        except Exception:
            return None
    try:
        return int(y)
    except Exception:
        return None

def row_team(row):
    return norm(get(row, ["team", "TEAM", "teamAbbr", "TEAM_ABBREVIATION"]))

def pct(x):
    if x is None:
        return None
    try:
        n = float(x)
        if 0 <= n <= 1:
            n *= 100
        return round(n, 3)
    except Exception:
        return None

def parse_stats(items):
    out = {}
    for it in items or []:
        stat = str(it.get("stat", "")).lower().replace(" ", "")
        on, off = pct(it.get("On")), pct(it.get("Off"))
        if stat in ["efg", "efg%"]:
            out["EFG"] = (on, off)
        elif stat in ["oreb", "oreb%", "orb", "orb%"]:
            out["OREBPct"] = (on, off)
        elif stat in ["ftr", "ftarate", "ft/fga"]:
            out["FTr"] = (on, off)
        elif stat in ["tov", "tov%"]:
            out["TOVPct"] = (on, off)
    return out

def build_rows(year):
    path = OUT / f"player_on_season_four_factors_{year}.json"
    if path.exists():
        rows = json.loads(path.read_text(errors="ignore"))
    else:
        rows = []

    seen = {(player_id_api(r.get("playerId")), norm(r.get("team"))) for r in rows}

    for pf in sorted(PLAYERS.glob("*.json")):
        data = json.loads(pf.read_text(errors="ignore"))
        meta = data.get("meta", {})
        name = meta.get("name") or pf.stem.replace("-", " ").title()
        ids = [player_id_api(x) for x in meta.get("playerIds", []) if player_id_api(x)]

        teams = sorted({
            row_team(g)
            for g in data.get("games", [])
            if row_year(g) == year and row_team(g)
        })

        for pid in ids:
            for team in teams:
                if not pid or not team or (pid, team) in seen:
                    continue
                if team not in TEAM_IDS:
                    continue
                rows.append({
                    "playerId": pid,
                    "playerName": name,
                    "team": team,
                    "teamId": TEAM_IDS[team],
                    "year": year,
                    "season": season_str(year),
                    "onMinutes": None,
                    "offMinutes": None,
                    "hasOnCourtFourFactors": False,
                    "hasOnCourtWOWY": False
                })
                seen.add((pid, team))

    path.write_text(json.dumps(rows, separators=(",", ":"), ensure_ascii=False))
    return path, rows

def fetch(row, year, retry_503=False):
    pid, team_id = player_id_api(row.get("playerId")), norm(row.get("teamId"))
    row["playerId"] = pid
    raw_dir = RAW / str(year)
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"{pid}_{team_id}.json"

    if raw_path.exists():
        try:
            cached = json.loads(raw_path.read_text(errors="ignore"))
            if not (retry_503 and cached.get("status_code") in [500, 503]):
                return cached
            raw_path.unlink()
        except Exception:
            pass

    params = {
        "Season": season_str(year),
        "SeasonType": "Playoffs",
        "TeamId": team_id,
        "PlayerId": pid
    }

    print(f"FETCH {year} {row.get('playerName')} {row.get('team')} playerId={pid} teamId={team_id}", flush=True)

    try:
        r = requests.get(URL, params=params, timeout=45, headers={"User-Agent": "Mozilla/5.0"})
        payload = {
            "ok": r.ok,
            "status_code": r.status_code,
            "url": r.url,
            "year": year,
            "playerId": pid,
            "teamId": team_id,
            "playerName": row.get("playerName"),
            "team": row.get("team"),
            "response": None,
            "text_head": None
        }
        try:
            payload["response"] = r.json()
        except Exception:
            payload["text_head"] = r.text[:500]
    except Exception as e:
        payload = {
            "ok": False,
            "status_code": None,
            "year": year,
            "playerId": pid,
            "teamId": team_id,
            "playerName": row.get("playerName"),
            "team": row.get("team"),
            "error": repr(e)
        }

    raw_path.write_text(json.dumps(payload, indent=2))
    return payload

def apply(row, payload):
    data = payload.get("response")
    if not isinstance(data, dict):
        row["fourFactorBackfillStatus"] = f"request failed: {payload.get('status_code')}"
        return False

    off = parse_stats(data.get("offense_results"))
    deff = parse_stats(data.get("defense_results"))
    need = ["EFG", "OREBPct", "FTr", "TOVPct"]

    if not all(k in off for k in need) or not all(k in deff for k in need):
        row["fourFactorBackfillStatus"] = "missing required offense/defense four-factor fields"
        return False

    row["onTeamEFG"], row["onTeamEFGOff"] = off["EFG"]
    row["onTeamOREBPct"], row["onTeamOREBPctOff"] = off["OREBPct"]
    row["onTeamFTr"], row["onTeamFTrOff"] = off["FTr"]
    row["onTeamTOVPct"], row["onTeamTOVPctOff"] = off["TOVPct"]

    row["onOppEFG"], row["onOppEFGOff"] = deff["EFG"]
    row["onOppOREBPct"], row["onOppOREBPctOff"] = deff["OREBPct"]
    row["onOppFTr"], row["onOppFTrOff"] = deff["FTr"]
    row["onOppTOVPct"], row["onOppTOVPctOff"] = deff["TOVPct"]

    row["onMinutes"] = data.get("minutes_on")
    row["offMinutes"] = data.get("minutes_off")
    row["hasOnCourtFourFactors"] = True
    row["fourFactorBackfillStatus"] = "verified pbpstats get-four-factor-on-off"
    row["fourFactorBackfillSource"] = payload.get("url")
    return True

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=2001)
    ap.add_argument("--end", type=int, default=2025)
    ap.add_argument("--sleep", type=float, default=2.0)
    ap.add_argument("--retry-503", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    total_ok = total_miss = 0

    for year in range(args.start, args.end + 1):
        path, rows = build_rows(year)
        targets = [r for r in rows if not r.get("hasOnCourtFourFactors")]
        if args.limit:
            targets = targets[:args.limit]

        print("\n" + "="*80, flush=True)
        print(f"YEAR {year} {season_str(year)} | rows {len(rows)} | before {Counter(r.get('hasOnCourtFourFactors') for r in rows)} | targets {len(targets)}", flush=True)
        print("="*80, flush=True)

        ok = miss = 0
        for i, row in enumerate(targets, 1):
            payload = fetch(row, year, retry_503=args.retry_503)
            if apply(row, payload):
                ok += 1
                print(f"OK {i}/{len(targets)}: {row.get('playerName')} {row.get('team')}", flush=True)
            else:
                miss += 1
                print(f"MISS {i}/{len(targets)}: {row.get('playerName')} {row.get('team')} {payload.get('status_code')} {payload.get('error') or payload.get('text_head') or row.get('fourFactorBackfillStatus')}", flush=True)

            path.write_text(json.dumps(rows, separators=(",", ":"), ensure_ascii=False))
            time.sleep(args.sleep)

        print(f"\nYEAR {year} Updated: {ok} Failed: {miss} After: {Counter(r.get('hasOnCourtFourFactors') for r in rows)}", flush=True)
        total_ok += ok
        total_miss += miss

    print("\nDONE")
    print("Total updated:", total_ok)
    print("Total failed:", total_miss)

if __name__ == "__main__":
    main()
