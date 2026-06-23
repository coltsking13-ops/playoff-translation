#!/usr/bin/env python3
import json
import requests
from pathlib import Path

OUT = Path("logs/pbpstats_api_probe.txt")
SPEC_OUT = Path("logs/pbpstats_openapi.json")

URLS = [
    "https://api.pbpstats.com/openapi.json",
    "https://api.pbpstats.com/swagger.json",
    "https://api.pbpstats.com/docs/openapi.json",
]

def write(s=""):
    with OUT.open("a") as f:
        f.write(str(s) + "\n")
    print(s)

OUT.write_text("PBPStats API probe\n==================\n\n")

spec = None
used = None

for url in URLS:
    try:
        r = requests.get(url, timeout=25)
        write(f"{url} -> {r.status_code}")
        if r.ok:
            spec = r.json()
            used = url
            SPEC_OUT.write_text(json.dumps(spec, indent=2))
            break
    except Exception as e:
        write(f"{url} -> ERROR {e}")

if not spec:
    write("")
    write("Could not fetch OpenAPI JSON directly.")
    write("Next fallback is manual endpoint probing.")
else:
    write("")
    write(f"Loaded spec from: {used}")
    paths = spec.get("paths", {})
    write(f"Total paths: {len(paths)}")
    write("")

    keywords = [
        "on-off",
        "wowy",
        "four",
        "shot",
        "possess",
        "game-stats",
        "lineup",
        "opponent",
    ]

    for path, obj in sorted(paths.items()):
        low = path.lower() + " " + json.dumps(obj).lower()
        if any(k in low for k in keywords):
            write("PATH: " + path)
            for method, info in obj.items():
                if not isinstance(info, dict):
                    continue
                write(f"  {method.upper()}: {info.get('summary') or info.get('description') or ''}")
                params = info.get("parameters", [])
                if params:
                    names = []
                    for p in params:
                        if isinstance(p, dict):
                            names.append(p.get("name", "?"))
                    write("  PARAMS: " + ", ".join(names))
            write("")

write("")
write("Probe saved to logs/pbpstats_api_probe.txt")
if SPEC_OUT.exists():
    write("OpenAPI saved to logs/pbpstats_openapi.json")
