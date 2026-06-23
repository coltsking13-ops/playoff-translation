from pathlib import Path
import re

html = Path("index.html").read_text(errors="ignore")

needles = [
    "teamAdjTS_source",
    '"playerName":"P.J. Brown"',
    '"ScoringTOV"',
    '"ZBounds"',
    '"AdjTS_source"',
    '"playerGames"',
    '"playerSeasons"',
]

scripts = list(re.finditer(r"<script\b([^>]*)>(.*?)</script\s*>", html, flags=re.I | re.S))

print("index size:", len(html))
print("script tags:", len(scripts))

for i, m in enumerate(scripts):
    attrs = m.group(1).strip()
    content = m.group(2)
    hits = [n for n in needles if n in content]
    if len(content) > 10000 or hits:
        print("\nSCRIPT", i)
        print("span:", m.start(), m.end())
        print("size:", len(content))
        print("attrs:", attrs[:300])
        print("hits:", hits)
        print("start:", content[:400].replace("\n", " "))

print("\nOUTSIDE SCRIPT HITS")
protected = [(m.start(), m.end()) for m in scripts]

def inside_script(pos):
    return any(a <= pos <= b for a, b in protected)

for n in needles:
    positions = [m.start() for m in re.finditer(re.escape(n), html)]
    outside = [p for p in positions if not inside_script(p)]
    print(n, "total=", len(positions), "outside=", len(outside))
    for p in outside[:5]:
        print("outside pos", p, html[max(0,p-200):p+300].replace("\n"," ")[:700])

print("\nPOSSIBLE DUMP CODE")
patterns = ["JSON.stringify", ".textContent", ".innerText", ".innerHTML", "raw-json", "debug", "appendChild"]
for pat in patterns:
    locs = [m.start() for m in re.finditer(re.escape(pat), html)]
    print(pat, "count=", len(locs))
    for p in locs[:8]:
        print("pos", p, html[max(0,p-200):p+350].replace("\n", " ")[:700])
