from pathlib import Path
import re, time

p = Path("index.html")
html = p.read_text(errors="ignore")
low = html.lower()

KEYS = [
    '"playerId"', '"playerName"', '"nbaId"', '"gameId"', '"seriesCode"',
    '"AdjTS%"', '"rAdjTS"', '"teamAdjTS_source"', '"ScoringTOV"',
    '"Heaves"', '"ZBounds"', '"TechFTA"', '"team"', '"opponent"'
]

def inside_tag(tag, pos):
    open_pos = low.rfind(f"<{tag}", 0, pos)
    close_pos = low.rfind(f"</{tag}", 0, pos)
    return open_pos > close_pos

def looks_like_raw_json_text(txt):
    s = txt.strip()
    if len(s) < 500:
        return False
    hits = sum(1 for k in KEYS if k in s)
    if hits >= 3:
        return True
    if s.startswith('{"') and '"playerName"' in s:
        return True
    if s.startswith('[{"') and '"playerName"' in s:
        return True
    return False

replacements = []

# Remove big text chunks between tags, but not script/style contents.
for m in re.finditer(r">([^<>]{500,})<", html, flags=re.S):
    s, e = m.span(1)
    txt = m.group(1)
    if inside_tag("script", s) or inside_tag("style", s):
        continue
    if looks_like_raw_json_text(txt):
        replacements.append((s, e, txt[:140].replace("\n", " ")))

# Also remove raw JSON after </html> if it got appended outside the document.
end_html = low.rfind("</html>")
if end_html != -1:
    tail_start = end_html + len("</html>")
    tail = html[tail_start:]
    if looks_like_raw_json_text(tail):
        replacements.append((tail_start, len(html), tail[:140].replace("\n", " ")))

print("raw JSON text chunks found:", len(replacements))
for i, (s, e, sample) in enumerate(replacements[:10], 1):
    print(f"{i}. bytes {s}-{e}: {sample}")

if not replacements:
    print("No removable raw text chunks found. Need deeper inspection.")
    raise SystemExit(0)

for s, e, sample in sorted(replacements, reverse=True):
    html = html[:s] + "" + html[e:]

p.write_text(html)
print("Cleaned index.html")
