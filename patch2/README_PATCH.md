# pbpstats AdjTS Headers Patch

This patch keeps the pbpstats-based AdjTS builder, but adds browser-like headers to pbpstats' underlying `requests` calls when it accesses NBA/data.nba.com hosts. This is intended to fix Codespaces `403 Client Error: Forbidden` errors from the data.nba schedule endpoint.

Run:

```bash
cp patch/build_adjts_from_pbp.py .
python3 build_adjts_from_pbp.py --years 2020 --apply --sleep 0.5 --force
python3 tests/smoke_test.py
```

If it still writes 0 rows, do not trust rAdjTS yet; send the error log.
