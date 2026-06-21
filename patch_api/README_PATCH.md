# pbpstats.com API AdjTS patch

This patch replaces `build_adjts_from_pbp.py` with a direct pbpstats.com API game-log builder.

It intentionally avoids:
- `stats.nba.com` scoreboard lookup
- `data.nba.com` season schedule lookup
- hand-parsed NBA play-by-play text

Run:

```bash
unzip playoff-translation-lab-pbpstats-com-api.zip -d patch_api
cp patch_api/build_adjts_from_pbp.py .
python3 build_adjts_from_pbp.py --years 2001 --apply --sleep 1.0 --force
```

Then verify:

```bash
python3 - <<'PY'
import csv
from collections import Counter
rows=list(csv.DictReader(open('data/player_game_adjts_ingredients.csv')))
print(Counter(r.get('year') for r in rows))
PY
```

If pbpstats.com returns a different JSON shape, run with `--limit-games 1` and send the output.
