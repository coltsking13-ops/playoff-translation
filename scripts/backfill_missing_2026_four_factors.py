#!/usr/bin/env python3
import json
import time
from pathlib import Path
from collections import Counter
import requests

YEAR = 2026
SEASON = "2025-26"
SEASON_TYPE = "Playoffs"

SRC = Path("public/data/on_court_all_leverage/player_on_season_four_factors_2026.json")
RAW_DIR = Path("public/data/on_court_all_leverage/raw_years/four_factor_on_off_2026")
RAW_DIR.mkdir(parents=True, exist_ok=True)

URL = "https://api.pbpstats.com/get-four-factor-on-off/nba"

def pct(v):
    if v is None:
        return None
    try:
        n = float(v)
        if 0 <= n <= 1:
            n *= 100
        return round(n, 3)
    except Exception:
        return None

def stat_map(results):
    out = {}
    for item in results or []:
        stat = str(item.get("stat", "")).lower().replace(" ", "")
        on = pct(item.get("On"))
        off = pct(item.get("Off"))

        if stat in ["efg%", "efg"]:
            out["EFG"] = (on, off)
        elif stat in ["oreb%", "oreb", "orb%", "orb"]:
            out["OREBPct"] = (on, off)
        elif stat == "ftr":
            out["FTr"] = (on, off)
        elif stat in ["tov%", "tov"]:
            out["TOVPct"] = (on, off)

    return out

def fetch_one(row, force=False):
    pid = str(row.get("playerId") or "")
    team_id = str(row.get("teamId") or "")
    name = row.get("playerName")
    team = row.get("team")

    raw_path = RAW_DIR / f"{pid}_{team_id}.json"

    if raw_path.exists() and not force:
        try:
            return json.loads(raw_path.read_text(errors="ignore"))
        except Exception:
            pass

    params = {
        "Season": SEASON,
        "SeasonType": SEASON_TYPE,
        "TeamId": team_id,
        "PlayerId": pid,
    }

    print(f"FETCH {name} {team} playerId={pid} teamId={team_id}")

    try:
        res = requests.get(
            URL,
            params=params,
            timeout=40,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        payload = {
            "ok": res.ok,
            "status_code": res.status_code,
            "url": res.url,
            "playerId": pid,
            "teamId": team_id,
            "playerName": name,
            "team": team,
            "response": None,
            "text_head": None,
        }

        try:
            payload["response"] = res.json()
        except Exception:
            payload["text_head"] = res.text[:500]

        raw_path.write_text(json.dumps(payload, indent=2))
        return payload

    except Exception as e:
        payload = {
            "ok": False,
            "status_code": None,
            "playerId": pid,
            "teamId": team_id,
            "playerName": name,
            "team": team,
            "error": repr(e),
        }
        raw_path.write_text(json.dumps(payload, indent=2))
        return payload

def patch_row(row, payload):
    data = payload.get("response")
    if not isinstance(data, dict):
        return False

    offense = stat_map(data.get("offense_results"))
    defense = stat_map(data.get("defense_results"))

    needed = ["EFG", "OREBPct", "FTr", "TOVPct"]
    if not all(k in offense for k in needed) or not all(k in defense for k in needed):
        row["hasOnCourtFourFactors"] = False
        row["fourFactorBackfillStatus"] = "missing required offense/defense four-factor fields"
        return False

    row["onTeamEFG"], row["onTeamEFGOff"] = offense["EFG"]
    row["onTeamOREBPct"], row["onTeamOREBPctOff"] = offense["OREBPct"]
    row["onTeamFTr"], row["onTeamFTrOff"] = offense["FTr"]
    row["onTeamTOVPct"], row["onTeamTOVPctOff"] = offense["TOVPct"]

    row["onOppEFG"], row["onOppEFGOff"] = defense["EFG"]
    row["onOppOREBPct"], row["onOppOREBPctOff"] = defense["OREBPct"]
    row["onOppFTr"], row["onOppFTrOff"] = defense["FTr"]
    row["onOppTOVPct"], row["onOppTOVPctOff"] = defense["TOVPct"]

    row["onMinutes"] = data.get("minutes_on")
    row["offMinutes"] = data.get("minutes_off")

    row["hasOnCourtFourFactors"] = True
    row["fourFactorBackfillStatus"] = "verified pbpstats get-four-factor-on-off"
    row["fourFactorBackfillSource"] = payload.get("url")

    return True

def main():
    data = json.loads(SRC.read_text(errors="ignore"))

    missing = [r for r in data if not r.get("hasOnCourtFourFactors")]

    print("Before:", Counter(r.get("hasOnCourtFourFactors") for r in data))
    print("Missing targets:", len(missing))

    updated = 0
    failed = 0

    for i, row in enumerate(missing, 1):
        payload = fetch_one(row)

        if patch_row(row, payload):
            updated += 1
            print(f"OK {i}/{len(missing)}:", row.get("playerName"), row.get("team"))
        else:
            failed += 1
            print(f"MISS {i}/{len(missing)}:", row.get("playerName"), row.get("team"), payload.get("status_code"), payload.get("error") or payload.get("text_head"))

        SRC.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False))

        # be polite to API / avoid rate-limit
        time.sleep(4.0)

    print()
    print("Updated:", updated)
    print("Failed:", failed)
    print("After:", Counter(r.get("hasOnCourtFourFactors") for r in data))

if __name__ == "__main__":
    main()
