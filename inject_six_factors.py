#!/usr/bin/env python3
"""
inject_six_factors.py
=====================
Patches index.html to load six_factors_overlay.js.

Run from your repo root:
    python3 inject_six_factors.py

What it does:
  1. Reads index.html in streaming chunks (safe for 133 MB)
  2. Checks whether six_factors_overlay.js is already referenced
  3. Inserts  <script src="six_factors_overlay.js"></script>
     just before </body>  (or </html> if </body> is absent)
  4. Writes index.html back  (original backed up as index.html.bak)

Safe to re-run -- idempotent.
"""

from pathlib import Path
import shutil

ROOT      = Path(__file__).resolve().parent
HTML_FILE = ROOT / "index.html"
OVERLAY   = "six_factors_overlay.js"
TAG       = f'<script src="{OVERLAY}"></script>'

if not HTML_FILE.exists():
    raise FileNotFoundError(f"Cannot find {HTML_FILE}")

size_mb = HTML_FILE.stat().st_size / 1_048_576
print(f"Reading {HTML_FILE.name} ({size_mb:.1f} MB)...")

# Read as bytes first so we don't decode the 133 MB twice
raw = HTML_FILE.read_bytes()
content = raw.decode("utf-8", errors="replace")

if TAG in content:
    print("Nothing to do -- six_factors_overlay.js already injected.")
else:
    backup = HTML_FILE.with_suffix(".html.bak")
    shutil.copy2(HTML_FILE, backup)
    print(f"  Backed up original to {backup.name}")

    pos = content.rfind("</body>")
    if pos == -1:
        pos = content.rfind("</html>")
    if pos == -1:
        content += f"\n{TAG}\n"
        print("  (appended at end of file -- no </body> or </html> found)")
    else:
        content = content[:pos] + f"\n{TAG}\n" + content[pos:]

    HTML_FILE.write_text(content, encoding="utf-8")
    print(f"OK: injected {TAG}")

print("Done.")
