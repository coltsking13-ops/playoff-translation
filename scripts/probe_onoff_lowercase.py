#!/usr/bin/env python3
import json
import requests
import time
from pathlib import Path

BASE = "https://api.pbpstats.com"
OUT = Path("public/data/on_court_all_leverage/raw_probes/onoff_lowercase_probe.json")
OUT.parent.mkdir(parents=True, exist_ok=True)

SAMPLE = {
    "Season": "2012-13",
    "SeasonType": "Playoffs",
    "TeamId": 1610612748,
    "PlayerId": 2544,
    "Leverage": "All",
}

def get(path, params):
    url = BASE + path
    r = requests.get(url, params=params, timeout=35)
    print("")
    print("GET", r.url)
    print("STATUS", r.status_code)
    print("TEXT", r.text[:350].replace("\n", " "))
    if not r.ok:
        return {"status": r.status_code, "url": r.url, "text": r.text[:1500]}
    try:
        return r.json()
    except Exception:
        return {"status": r.status_code, "url": r.url, "text": r.text[:1500]}

def summarize(label, obj):
    print("")
    print("====", label, "====")
    if isinstance(obj, dict):
        print("top keys:", list(obj.keys())[:60])
        for k, v in obj.items():
            if isinstance(v, list):
                print("list:", k, "len:", len(v))
                if v and isinstance(v[0], dict):
                    print("first keys:", list(v[0].keys())[:120])
                    print("first row:", json.dumps(v[0], indent=2)[:2000])
                return
            if isinstance(v, dict):
                print("dict:", k, "keys:", list(v.keys())[:80])
                print("dict sample:", json.dumps(v, indent=2)[:2000])
                return
    elif isinstance(obj, list):
        print("list len:", len(obj))
        if obj and isinstance(obj[0], dict):
            print("first keys:", list(obj[0].keys())[:120])
            print("first row:", json.dumps(obj[0], indent=2)[:2000])
    else:
        print(type(obj), str(obj)[:500])

calls = {}

# These were the valid enum values from the API error.
for stat_type in ["team", "player", "stat"]:
    params = dict(SAMPLE)
    if stat_type == "stat":
        # Probe a few likely Stat values. Some may fail; that is fine.
        for stat in ["OffRtg", "DefRtg", "NetRtg", "EfgPct", "TsPct", "TovPct", "OrebPct", "Ftr", "Fg3Pct", "Fg2Pct"]:
            p = dict(params)
            p["Stat"] = stat
            calls[f"on_off_stat_{stat}"] = get(f"/get-on-off/nba/{stat_type}", p)
            time.sleep(0.5)
    else:
        calls[f"on_off_{stat_type}"] = get(f"/get-on-off/nba/{stat_type}", params)
        time.sleep(0.75)

# Try four factor without Leverage and with IDs as strings, just in case.
for label, params in {
    "four_factor_normal": {
        "Season": SAMPLE["Season"],
        "SeasonType": SAMPLE["SeasonType"],
        "TeamId": SAMPLE["TeamId"],
        "PlayerId": SAMPLE["PlayerId"],
    },
    "four_factor_string_ids": {
        "Season": SAMPLE["Season"],
        "SeasonType": SAMPLE["SeasonType"],
        "TeamId": str(SAMPLE["TeamId"]),
        "PlayerId": str(SAMPLE["PlayerId"]),
    },
}.items():
    calls[label] = get("/get-four-factor-on-off/nba", params)
    time.sleep(0.75)

OUT.write_text(json.dumps(calls, indent=2, ensure_ascii=False))
print("")
print("Saved:", OUT)

for label, obj in calls.items():
    summarize(label, obj)
