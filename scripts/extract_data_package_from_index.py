from pathlib import Path
import re

index = Path("index.html")
html = index.read_text(errors="ignore")

m = re.search(
    r'<script\s+id=["\']dataPackage["\']\s+type=["\']application/json["\']\s*>(.*?)</script\s*>',
    html,
    flags=re.I | re.S
)

if not m:
    raise SystemExit("Could not find <script id=\"dataPackage\" type=\"application/json\"> block")

raw_json = m.group(1).strip()

out = Path("public/data/data-package.embedded.json")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(raw_json, encoding="utf-8")

small_tag = '<script id="dataPackage" type="application/json">{"external":"./public/data/data-package.embedded.json"}</script>'
html = html[:m.start()] + small_tag + html[m.end():]

old_loader = "function loadData(){ dataPackage = JSON.parse(document.getElementById('dataPackage').textContent); allPlayers = Object.keys(dataPackage.players).map(id=>({id, ...dataPackage.players[id]})).sort((a,b)=>a.name.localeCompare(b.name)); }"

new_loader = """function loadData(){
            const tag = document.getElementById('dataPackage');
            const raw = tag ? tag.textContent.trim() : '';
            let marker = {};
            try { marker = raw ? JSON.parse(raw) : {}; } catch(e) { marker = {}; }

            if(marker && marker.external){
                const xhr = new XMLHttpRequest();
                xhr.open('GET', marker.external + '?v=' + Date.now(), false);
                xhr.send(null);
                if(xhr.status < 200 || xhr.status >= 300){
                    throw new Error('Could not load external data package: ' + marker.external);
                }
                dataPackage = JSON.parse(xhr.responseText);
            } else {
                dataPackage = marker;
            }

            allPlayers = Object.keys(dataPackage.players || {}).map(id=>({id, ...dataPackage.players[id]})).sort((a,b)=>a.name.localeCompare(b.name));
        }"""

if old_loader not in html:
    raise SystemExit("Could not find old loadData() function exactly. No changes written after extraction.")

html = html.replace(old_loader, new_loader, 1)

index.write_text(html, encoding="utf-8")

print("Extracted embedded JSON to:", out)
print("External JSON size:", out.stat().st_size)
print("New index size:", index.stat().st_size)
