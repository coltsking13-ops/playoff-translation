#!/usr/bin/env python3
import re
import json
from pathlib import Path

HTML_FILES = [
    p for p in Path(".").rglob("*.html")
    if ".git" not in p.parts
    and "node_modules" not in p.parts
    and "backups" not in p.parts
]

OUT = Path("v2/reports/embedded_html_data_audit.txt")
OUT.parent.mkdir(parents=True, exist_ok=True)

KEYWORDS = [
    "playerGames",
    "playerSeries",
    "seriesPlayers",
    "teamGames",
    "players",
    "games",
    "data-package",
    "DATA_PACKAGE",
    "__DATA__",
    "SITE_DATA",
]

def size_mb(n):
    return round(n / 1024 / 1024, 2)

lines = []
lines.append("EMBEDDED HTML DATA AUDIT")
lines.append("=" * 80)
lines.append("")

for p in HTML_FILES:
    text = p.read_text(errors="ignore")
    size = p.stat().st_size

    hits = []
    for kw in KEYWORDS:
        c = text.count(kw)
        if c:
            hits.append((kw, c))

    scripts = re.findall(r"<script\b[^>]*>(.*?)</script>", text, flags=re.I | re.S)
    json_scripts = re.findall(
        r"<script\b[^>]*type=[\"']application/json[\"'][^>]*>(.*?)</script>",
        text,
        flags=re.I | re.S,
    )

    big_scripts = []
    for i, s in enumerate(scripts):
        if len(s) > 100_000:
            big_scripts.append((i, len(s), [kw for kw in KEYWORDS if kw in s]))

    if hits or big_scripts or json_scripts or size > 1_000_000:
        lines.append(f"FILE: {p}")
        lines.append(f"SIZE: {size_mb(size)} MB")
        lines.append(f"SCRIPT TAGS: {len(scripts)}")
        lines.append(f"APPLICATION/JSON SCRIPT TAGS: {len(json_scripts)}")

        if hits:
            lines.append("KEYWORD HITS:")
            for kw, c in hits:
                lines.append(f"  {kw}: {c}")

        if big_scripts:
            lines.append("BIG SCRIPT TAGS:")
            for idx, n, kws in big_scripts[:20]:
                lines.append(f"  script #{idx}: {size_mb(n)} MB | keywords: {', '.join(kws) if kws else 'none'}")

        lines.append("")

OUT.write_text("\n".join(lines))
print(OUT.read_text())
