# Direct 10s PBP resolver patch

Replaces `build_adjts_from_pbp.py` with a patched resolver that probes data.nba individual PBP files under `/data/10s/v2015/` first. The previous direct resolver used `/data/v2015/` only and could find 0 games for older seasons like 2001.

Usage:

```bash
unzip playoff-translation-lab-pbpstats-direct-10s-resolver.zip -d patch5
cp patch5/build_adjts_from_pbp.py .
python3 build_adjts_from_pbp.py --years 2001 --apply --sleep 1.5
```
