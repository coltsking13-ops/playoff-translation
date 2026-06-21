# Build Report

Updated: 2026-06-21

## Final row counts

- Players: 1,664
- Season rows: 6,099
- Series rows: 10,985
- Game rows: 48,981
- Team regular-season benchmark rows: 776
- Team game context rows: 4,542
- Team series context rows: 840
- Game team-rank / led-team rows: 77,130
- Series team-rank / led-team rows: 14,534
- On-court postseason profile rows: 9,792

## Adjusted true shooting implementation

AdjTS% and signed rAdjTS are now populated across season, series, and game tables where source scoring rows exist, including pre-2014 seasons and 2026 rows.

Formula used:

```text
Scoring TOV = total TOV - bad-pass TOV - bad-pass-out-of-bounds TOV
Adjusted FGA = FGA + scoring TOV - heaves - z boards/self offensive rebounds
Adjusted FTA = FTA - technical FTA
AdjTS% = PTS / (2 * (Adjusted FGA + 0.44 * Adjusted FTA))
```

For player-season rows, the build uses postseason player adjustment files when available. For game rows and generated series rows, the build uses detailed fields when present; when heaves/z-boards/tech-FTA/bad-pass columns are absent, the row is labeled internally as a box-score fallback instead of inventing unavailable components.

## Opponent context

rAdjTS uses opponent regular-season adjusted TS allowed first. The build now loads detailed opponent-allowed team rows from `team_totals/{year}vs.csv` for 2001-2026, so 2001-2013 and 2026 now have regular-season adjusted allowed benchmarks instead of blank rAdjTS values. For 1997-2000, detailed regular-season opponent adjustment components are not available in the local source set, so those rows use the best available fallback rather than fabricated heave/z-board/tech-FTA data.

## Game/series context

Added game-level and series-level team context rows from real team-game/player-game sources where available:

- Team AdjTS%
- Opponent AdjTS%
- Team rim frequency / rim accuracy when source columns exist
- Opponent rim frequency allowed / rim accuracy allowed when source columns exist
- ORB% / DREB%
- Team-rank and led-team rows for AdjTS%, rAdjTS, TS%, ORTG, DRTG, NET, rebounding rates, AST%, USG%, and rim metrics.

## Legacy on-court note

Pre-2001 legacy on/off profile rows remain suppressed because those source rows produced unreliable MJ/Reggie-era on-court ORTG/DRTG values. True player-on-court by individual game/series still requires possession-level lineup reconstruction; this build adds real team context and player rank/leader context by game/series, not fake on-court shot profiles.

## Validation

Smoke test result: `RESULTS: 19 passed, 0 failed`.

Source row counts used in this build include 776 regular-season opponent/team-vs rows, 4,542 generated team-game rows, and 5,350 player postseason adjustment rows.

## 2025 completeness repair

The compact source package that was available in this workspace only contained 19 local playoff `game_report/2025/424*.csv` files. That is why the embedded offline package had 2025 season totals but incomplete 2025 game logs and series logs for players such as Giannis, LeBron, Curry, and Jokic.

This build adds a browser-side auto-repair for 2025 game/series data. When the site opens online, it checks whether the embedded 2025 game-log count is low. If it is, the site automatically queries the GitHub API tree for `gabriel1200/player_sheets`, finds every `game_report/2025/4*.csv` playoff file, fetches those CSVs directly from `raw.githubusercontent.com`, adds missing player-game rows, and rebuilds 2025 series rows from the fetched games. No user-facing “load data” button is required.

The live 2025 repair also computes the same table fields used elsewhere when the source row has the needed columns: TS%, AdjTS%, rTS, rAdjTS, ORTG, DRTG, NET, rORTG, rDRTG, rNET, rim frequency, rim accuracy, ORB%, DREB%, AST%, and USG%.

Offline note: if the file is opened without internet, it will still use the embedded compact package. Full offline 2025 completeness requires rerunning `python3 build_data.py --fetch` from a networked Codespace or local clone so the missing public CSV files can be embedded directly.
