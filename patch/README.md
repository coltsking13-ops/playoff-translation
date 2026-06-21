# Playoff Translation Lab

## Latest data-context fixes

This build uses opponent **regular-season** team context as the primary translation baseline. That means rTS is calculated as player TS% minus what the opponent allowed in the regular season, with playoff team context only used as a fallback when the regular-season opponent field is unavailable.

The player page also includes an **On-Court Team Profile** section built from playoff on/off files. It shows team offense/defense with the player on court and opponent offense allowed with the player on court, including TS%, rim frequency, rim accuracy, ORB%, defensive rebound%, NET, and on/off deltas where the source file has both on and off rows.


A comprehensive, offline-capable web application for exploring NBA playoff player performance across 30 years of postseason data (1997–2026).

## Overview

**Playoff Translation Lab** provides sports analysts, fans, and researchers with an interactive platform to understand how players performed in the highest-pressure moments of the NBA season. The site embeds all data directly in the `index.html` file, enabling **instant search and browsing without any backend or internet connectivity**.

### Key Features

- **Instant Search**: Full-text search with custom dropdown supporting partial names (e.g., `lebr`, `curry`, `jokic`)
- **Offline-First**: No backend required; all data embedded in the deployable `index.html`
- **Mobile-First Design**: Polished dark sports analytics UI optimized for iPhone Safari and responsive layouts
- **30 Years of Data**: Playoff seasons from 1997 through 2026
- **Hierarchical Exploration**: Player → Playoff Year → Series → Individual Games
- **Advanced Metrics**: Per-100 normalization, relative stats, on-court impact, shot profiles, and playmaking splits
- **No Fabricated Stats**: All metrics are real; missing data displays as `—`

## Project Structure

```
playoff-translation-lab/
├── index.html                 # Main deployable website (all-in-one)
├── data-package.json          # Embedded data package (featured players + seasons)
├── build_data.py              # Build pipeline (clones Gabriel1200 repos, processes stats)
├── source_manifest.json       # Data sources, metrics definitions, and calculations
├── README.md                  # This file
└── tests/
    └── smoke_test.py          # Validation and test reporting
```


### Relative stat display

Relative stats are shown with signs in the UI: positive values display with `+`, negative values display with `-`. `rTS` is opponent-adjusted: player TS% minus the opponent's regular-season TS% allowed benchmark, with same-year playoff average fallback only when an opponent cannot be mapped.

## Quick Start

### For Users

1. **Open the website**:
   ```bash
   # Open in any modern browser
   open index.html
   ```
   The site works **offline** without any setup.

2. **Search for a player**:
   - Type `lebr` to find LeBron James
   - Type `curry` to find Stephen Curry
   - Click any featured chip to jump to that player

3. **Explore seasons, series, and games**:
   - Tap/click a season row to filter series and game-log data to that year
   - View per-75-possession stats, shooting efficiency, and offensive/defensive ratings
   - Missing stats display as `—`

### For Developers

#### Build the Data Package

```bash
# Refresh/re-embed the already-built package, or rebuild if local raw source folders exist
python3 build_data.py

# To fetch and rebuild from Gabriel1200 raw CSVs:
python3 build_data.py --fetch

# This generates/updates:
# - data-package.json             (processed player data)
# - data/data-package.json         (deployable data copy)
# - index.html                     (embedded data for no-load-button offline use)
```

**Compact ZIP note:** the downloadable ZIP includes the already-built `data-package.json` and the embedded `index.html`. Raw source folders may be omitted to avoid Codespaces disk errors. Running `python3 build_data.py` still passes by refreshing the packaged data; use `--fetch` when you specifically want to sparse-clone the raw Gabriel1200 CSV folders.

**Prerequisites**:
- Python 3.8+
- Git only if using `python3 build_data.py --fetch`

#### Run Tests

```bash
# Validate data integrity and report metrics
python3 tests/smoke_test.py

# Reports:
# - Player count
# - Season/Series/Game row counts
# - Years loaded and missing years
# - Source files used
# - Real vs. context-only metrics
# - Known limitations
```

#### Deploy

The `index.html` is **production-ready**:
- Embed data by running `build_data.py` and updating the `<script id="dataPackage">` tag
- Deploy as a static file to any web server
- Works offline after first load

## Data Sources

All data comes from **Gabriel1200's public GitHub repositories** (read-only):

### site_Data Repository
**Purpose**: Player info, baseline stats, and advanced metrics (all CSV files at root)

**Priority Files**:
- `pbp_totals_ps.csv` — Play-by-play totals (playoff season)
- `windex_ps.csv` — Win index metrics
- `poss_ps.csv` — Possession data
- `tracking_ps.csv` — Player tracking metrics
- `hustle_ps.csv` — Hustle stats (effort metrics)
- `passing_ps.csv` — Passing data
- `playtype_p.csv`, `play_style_p.csv` — Play classification
- `drives.csv`, `pullup.csv`, `paint.csv`, `post.csv`, `elbow.csv`, `catchshoot.csv` — Shot types
- `defense_master_ps.csv`, `dfg_p.csv`, `rimdfg_p.csv`, `rim_acc_p.csv`, `rimfreq_p.csv` — Defensive metrics
- `teamplay_p.csv`, `teamplayd_p.csv` — Team context
- `team_shotzone_ps.csv`, `team_shotzone_vs_ps.csv` — Shot zone analytics
- `dates.csv` — Game dates
- Year folders (`2014/`–`2025/`) — Season organization

### player_sheets Repository
**Purpose**: Detailed player-level playoff stats and aggregations

**Priority Folders**:
- `game_report/` — Individual game performance
- `teamgame_report/` — Team-game context
- `series/` — Series-level aggregations
- `series/team/` — Series-team interactions
- `year_totals/` — Seasonal totals
- `totals/` — Cumulative stats
- `team_totals/` — Team-level aggregations

### merged_playbyplay Repository
**Purpose**: Merged play-by-play data for all playoff games

**Priority Folders**:
- `pbp_data/` — Processed play-by-play logs
- `data/` — Raw/supporting data
- `lineups/` — Lineup data for games

### pbpbacklog Repository
**Purpose**: Supplemental play-by-play coverage and backlog

**Priority Folders**:
- `playbyplay/` — Additional play-by-play records
- `boxscore/` — Game box scores

### legacy_pbp Repository
**Purpose**: Historical play-by-play data for pre-2000 seasons

**Priority Folders**:
- `gameplaybyplay/` — Historical game-level PBP
- `game_info/` — Game metadata and context

## Stat Definitions

### Normalized Stats (Per-75-Possessions)

All "per-75" metrics normalize to a 75-possession playoff game:

```
PTS/75  = Points / Possessions * 75
AST/75  = Assists / Possessions * 75
REB/75  = Rebounds / Possessions * 75
TOV/75  = Turnovers / Possessions * 75
```

If data is already per-100:
```
PTS/75  = PTS_per_100 * 0.75
AST/75  = AST_per_100 * 0.75
REB/75  = REB_per_100 * 0.75
TOV/75  = TOV_per_100 * 0.75
```

### Relative Stats

Relative stats measure a player's performance against the opponent's defensive benchmarks:

```
rTS%   = Player TS% − Opponent Allowed TS%
rEFG%  = Player eFG% − Opponent Allowed eFG%
rORTG  = Player ORTG − Opponent Defensive Rating
rDRTG  = Opponent ORTG − Player DRTG
```

### Net Rating & Relative Net Rating

**Net Rating**:
```
NET = ORTG − DRTG
```

**Relative Net Rating** (On-Court Impact):
```
rNET = (Player ORTG − Opponent DRTG) − (Opponent ORTG − Player DRTG)
```

This metric isolates a player's on-court impact by comparing their offensive efficiency relative to the opponent's defensive rating, and their defensive efficiency relative to the opponent's offensive rating.

## Table Schema

### Season Translation Table

| Column | Type | Example | Notes |
|--------|------|---------|-------|
| Year | int | 2024 | Playoff year |
| MIN | float | 34.2 | Minutes per game |
| PTS/75 | float | 28.5 | Points per 75 possessions |
| REB/75 | float | 9.2 | Rebounds per 75 possessions |
| AST/75 | float | 8.1 | Assists per 75 possessions |
| TOV/75 | float | 2.3 | Turnovers per 75 possessions |
| TS% | float | 63.2 | True Shooting % |
| eFG% | float | 58.9 | Effective FG% |
| ORTG | int | 125 | Points per 100 possessions (offensive) |
| DRTG | int | 105 | Points per 100 possessions (defensive) |
| NET | int | 20 | Net Rating (ORTG − DRTG) |

### Series Breakdown

Same columns as Season Translation, aggregated by playoff round.

### Game Log

| Column | Type | Example | Notes |
|--------|------|---------|-------|
| Date | string | 2024-05-15 | Game date |
| vs | string | LAL | Opponent |
| MIN | float | 38.1 | Minutes |
| PTS | int | 28 | Points |
| REB | int | 7 | Rebounds |
| AST | int | 5 | Assists |
| TS% | float | 62.1 | True Shooting % |
| eFG% | float | 56.8 | Effective FG% |
| Result | string | W | Game result (W/L) |

### On-Court Impact

| Column | Type | Example | Notes |
|--------|------|---------|-------|
| rNET | float | +8.3 | Relative Net Rating (adjusted to opponent context) |
| Level | string | Season | season/series/game |
| ORTG | int | 125 | Player ORTG (context) |
| DRTG | int | 102 | Player DRTG (context) |
| Opp ORTG | int | 115 | Opponent offensive rating (benchmark) |
| Opp DRTG | int | 110 | Opponent defensive rating (benchmark) |

### Shot Profile & Playmaking

| Column | Type | Example | Notes |
|--------|------|---------|-------|
| Category | string | 3P Attempts | Shot type or pass type |
| Frequency | float | 32.1 | % of possessions |
| Efficiency | float | 38.2 | FG% or assisted FG% |

## UI Sections

1. **Hero/Search**: Title, subtitle, and search input with custom dropdown
2. **Featured Chips**: Quick-select buttons for 12 featured players
3. **Player Header**: Player name and metadata
4. **Season Translation Table**: Per-75 stats by playoff year (expandable)
5. **Series Breakdown**: Stats aggregated by round
6. **Game Log**: Individual game performance
7. **On-Court Impact**: Relative Net Rating (rNET) adjusted for opponent context
8. **Shot Profile**: Scoring distribution and efficiency
9. **Playmaking Pressure**: Pass types and playmaking frequency
10. **Defensive Activity**: Defensive metrics and pressure
11. **Rankings**: Player rankings by category
12. **Data Sources**: Row counts and source file attribution

## Rules & Constraints

✅ **What We Do**:
- Show real playoff stats from 1997–2026
- Display "—" for missing data
- Calculate normalized per-75-possession stats
- Build relative stats (rTS, rEFG, rORTG, rDRTG, rNET) when benchmarks exist
- Support partial name search
- Show on-court impact via relative Net Rating adjusted to opponent context

❌ **What We Don't Do**:
- Use RAPM2K or any 2K-related metrics
- Reference Brescou/Breacou labels
- Fabricate stats
- Require internet or a backend
- Show a "Load Data" button

## Mobile Optimization

- **Responsive**: Works from iPhone 390px width to 4K displays
- **Touch-Friendly**: Tap-to-expand rows, swipe-friendly dropdowns
- **Dark Theme**: Optimized for low-light viewing
- **Safari Support**: Tested on iPhone Safari

## Browser Compatibility

- Chrome/Chromium 90+
- Firefox 88+
- Safari 14+ (including iOS)
- Edge 90+

## Development

### Adding New Players

Edit `data-package.json`:

```json
"players": {
  "player_id": {
    "id": "player_id",
    "name": "Full Name",
    "featured": false
  }
}
```

### Adding Season Data

```json
"playerSeasons": [
  {
    "playerId": "player_id",
    "year": 2024,
    "MIN": 34.2,
    "PTS/75": 28.5,
    ...
  }
]
```

### Adding On-Court Impact Data

```json
"playerImpact": [
  {
    "playerId": "player_id",
    "year": 2024,
    "rNET": 8.3,
    "ORTG": 125,
    "DRTG": 102,
    "oppORTG": 115,
    "oppDRTG": 110,
    "level": "season"
  }
]
```

### Customizing Styles

Edit the `<style>` block in `index.html`:
- Primary color: `#a78bfa` (purple)
- Accent color: `#60a5fa` (blue)
- Background: `#0a0e27` (dark navy)

## Known Limitations

1. **Game-log availability**: Historical game rows are loaded from `gen_totals` for 1997–2024 and available playoff `game_report` files for newer/supplemental seasons. If a player has season totals but the local source set has no real game files for that playoff run, the site will not invent game or series rows.
2. **2025/2026 freshness**: Some newer game logs depend on the latest files available in Gabriel1200's repositories. Season rows can be present before every game-level file is available locally.
3. **Advanced tracking detail**: Shot zone, tracking, hustle, play-type, and skill split fields depend on the columns present in the source CSVs and are stronger in recent seasons.
4. **Opponent context fallback**: `rORTG`, `rDRTG`, `rNET`, `rTS`, and `rAdjTS` use opponent regular-season team context first. Playoff/team-average context is only a fallback when the regular-season opponent row cannot be mapped.
5. **No fabricated rows**: The build only aggregates real source rows. Missing source files show as missing rows, not synthetic stats.

## Testing

Run the smoke test to validate the build:

```bash
python3 tests/smoke_test.py
```

**Checks**:
- ✅ index.html opens locally
- ✅ Search works immediately
- ✅ `lebr` finds LeBron James
- ✅ PTS/75 calculated correctly
- ✅ Season rows can filter series/game views by year
- ✅ Pre-2014 stars have real series/game rows
- ✅ 2021 LeBron and 2021 Giannis have season/series/game rows
- ✅ rORTG/rDRTG/rNET exist for every season, series, and game row
- ✅ No fake data
- ✅ Missing stats show `—`
- ✅ No RAPM2K or 2K labels
- ✅ rNET calculated and displayed correctly

## License

This project uses data from Gabriel1200's public repositories. All data is provided as-is for educational and analytical purposes.

## Credits

- **Data Source**: Gabriel1200's public GitHub repositories
- **Design**: Mobile-first dark sports analytics UI
- **Built**: June 2026

---

**Questions?** Check `source_manifest.json` for data source details and metric definitions.


## Latest update: adjusted TS + team game/series context

- Populated `AdjTS%` and signed `rAdjTS` at season, series, and game levels, including pre-2014 rows and 2026 rows.
- Formula: scoring TOV = total TOV - bad-pass TOV - bad-pass-out-of-bounds TOV; adjusted FGA = FGA + scoring TOV - heaves - z boards/self offensive rebounds; adjusted FTA removes technical FTA; AdjTS% uses the standard TS denominator with adjusted FGA/FTA.
- Added opponent regular-season adjusted TS allowed context from `team_totals/{year}vs.csv` for 2001-2026.
- For 1997-2000, detailed regular-season opponent adjustment components are not in the local source set, so the build uses the best available TS/box fallback and does not fabricate heaves, z boards, or tech FTAs.
- Added team game and series context from real generated team-game rows where available.
- Added Team Rank / Led Team sections for game and series leaders in `AdjTS%`, `rAdjTS`, `TS%`, `ORTG`, `DRTG`, `NET`, `ORB%`, `DREB%`, `AST%`, `USG%`, and rim metrics when present.
- Suppressed pre-2001 legacy on/off profile rows because those source rows are unreliable for MJ/Reggie-era on-court ORTG/DRTG.


## 2025 Game/Series Auto-Repair

The previous compact package had incomplete 2025 playoff game logs because the local source copy only included a small subset of `game_report/2025/424*.csv` files. This version includes an automatic online repair:

- The site checks the embedded 2025 game-log count when opened.
- If 2025 is incomplete, it uses the GitHub API tree for `gabriel1200/player_sheets` to discover all 2025 playoff game files.
- It fetches the missing CSVs directly from `raw.githubusercontent.com`.
- It adds the missing 2025 player game rows and rebuilds 2025 series rows automatically.
- It calculates TS%, AdjTS%, rTS, rAdjTS, rORTG, rDRTG, and rNET for the repaired rows when source columns and opponent benchmarks exist.
- There is no manual load button; the repair runs in the background.

Offline behavior: the page still opens offline using the embedded data package, but the full 2025 repair needs internet access. To make 2025 complete while fully offline, run `python3 build_data.py --fetch` in a networked environment and rebuild the package after the raw GitHub files are available locally.
