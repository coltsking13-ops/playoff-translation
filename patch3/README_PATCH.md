# pbpstats AdjTS scoreboard resolver patch

This patch keeps pbpstats for enhanced PBP parsing, but changes generated game-id resolution.

Instead of using the full data.nba.com season schedule first, it tries stats.nba.com scoreboardv2 by exact date and teams. That should reduce 403 errors for older generated game IDs such as `gen_2001_20010615_LAL_PHI`.

Install:

```bash
unzip playoff-translation-lab-pbpstats-scoreboard-resolver.zip -d patch3
cp patch3/build_adjts_from_pbp.py .
```

Run one old year first:

```bash
python3 build_adjts_from_pbp.py --years 2001 --apply --sleep 2.0
```
