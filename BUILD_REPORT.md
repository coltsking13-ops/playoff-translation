# Playoff Translation Lab — PBP AdjTS Builder Patch

## What changed

Added `build_adjts_from_pbp.py`, a play-by-play reconstruction pipeline for verified game-level and series-level adjusted true shooting.

## Why

The previous strict patch correctly blanked game/series AdjTS because normal game-report rows did not include the full ingredient set. The only honest way to populate those cells is to reconstruct the ingredients from play-by-play.

## Ingredient definitions

- Bad-pass TOV: turnover description/action contains bad pass.
- Bad-pass out-of-bounds TOV: bad-pass turnover with out-of-bounds language.
- Heaves: field goal attempts from 40+ feet with 2.0 seconds or less left in the period.
- Technical FTA: free throws labeled technical.
- Z Bounds: self offensive rebounds, where the player rebounds his own missed field goal.

## Formula

```text
Scoring TOV = TOV - bad-pass TOV - bad-pass-out-of-bounds TOV
AdjFGA = FGA + scoring TOV - heave attempts - Z Bounds
AdjFTA = FTA - technical FTA
AdjTS% = PTS / (2 * (AdjFGA + 0.44 * AdjFTA))
```

## How to run

```bash
python3 build_adjts_from_pbp.py --years 2025 --apply
```

For a complete rebuild:

```bash
python3 build_adjts_from_pbp.py --years 2001-2026 --apply --sleep 0.75
```

## Current data state

The included offline `data-package.json` still keeps unverified game/series AdjTS blank. This patch adds the working reconstruction pipeline. In this sandbox, live NBA Stats requests could not be executed because the container has no outbound DNS/network access, so I did not claim newly computed game-level AdjTS rows.

## Validation

`python3 tests/smoke_test.py` passes: 19 passed, 0 failed.
