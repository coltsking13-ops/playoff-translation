#!/usr/bin/env python3
import json
import time
from pathlib import Path

PACKAGE_FILES = [
    Path("data-package.json"),
    Path("data/data-package.json"),
    Path("public/data/data-package.embedded.json"),
    Path("public/data/data-package.json"),
]

BAD_IF_ZERO_ONLY = [
    "team3PAr",
    "oppAllowed3PAr",
    "team3PAr_vsOppAllowed",
]

def clean_rows(rows):
    cleaned = 0

    for r in rows:
        if not isinstance(r, dict):
            continue

        # If there is no 3PA/FG3A column, 3PAr cannot be trusted.
        has_3pa = any(k in r and r[k] not in [None, "", "—"] for k in [
            "3PA", "FG3A", "fg3a", "threePA", "threePointersAttempted"
        ])

        if not has_3pa:
            for k in BAD_IF_ZERO_ONLY:
                if k in r:
                    r.pop(k, None)
                    cleaned += 1

        # Team ORB% requires raw team OREB and opponent DREB.
        # Do not remove existing personal ORB%, only team/opp six-factor ORB fields if unsupported.
        has_raw_oreb = any(k in r and r[k] not in [None, "", "—"] for k in [
            "OREB", "ORB", "offReb", "offensiveRebounds"
        ])
        has_raw_dreb = any(k in r and r[k] not in [None, "", "—"] for k in [
            "DREB", "DRB", "defReb", "defensiveRebounds"
        ])

        if not has_raw_oreb or not has_raw_dreb:
            for k in [
                "teamORBPct",
                "oppAllowedORBPct",
                "teamORBPct_vsOppAllowed",
                "teamDRBPct",
                "oppAllowedDRBPct",
                "teamDRBPct_vsOppAllowed",
            ]:
                if k in r:
                    r.pop(k, None)
                    cleaned += 1

    return cleaned

for p in PACKAGE_FILES:
    if not p.exists():
        continue

    backup = p.with_name(p.name + f".before-six-factor-clean.{int(time.time())}.bak")
    backup.write_text(p.read_text(errors="ignore"))

    data = json.loads(p.read_text(errors="ignore"))

    total = 0
    total += clean_rows(data.get("playerGames", []))
    total += clean_rows(data.get("playerSeries", data.get("seriesPlayers", [])))

    data.setdefault("dataSources", {})
    if isinstance(data["dataSources"], dict):
        data["dataSources"]["six_factor_cleanup"] = {
            "installedAt": int(time.time()),
            "note": "Removed fake 3PAr/ORB% fields where raw 3PA or raw rebound ingredients are missing."
        }

    p.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False))

    print("")
    print("Package:", p)
    print("Backup:", backup)
    print("Fields cleaned:", total)

print("")
print("DONE cleaning invalid six-factor fields.")
