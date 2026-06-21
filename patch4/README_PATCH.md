# Direct Playoff ID Resolver Patch

This patch keeps pbpstats, but avoids the blocked full data.nba schedule and slow stats.nba scoreboard by probing the standard NBA playoff GameID pattern directly.

Use:

```bash
unzip playoff-translation-lab-pbpstats-direct-id-resolver.zip -d patch4
cp patch4/build_adjts_from_pbp.py .
python3 build_adjts_from_pbp.py --years 2001 --apply --sleep 1.5
```
