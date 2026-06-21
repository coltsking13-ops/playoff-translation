Before doing any work, verify that this Codex task is running inside **my own GitHub repository** for the website.

The connected repo should be:

```text
<[coltsking13-ops](https://github.com/coltsking13-ops)>/playoff-translation-lab
```

or whatever repo I selected for this project.

Do **not** edit Gabriel1200’s repositories.

First, tell me:

```text
Active repository:
Active branch:
Can you write files here? yes/no
```

If the active repository is not my own website repo, stop immediately and tell me to select the correct repo/environment in Codex before continuing.

Once the correct repo is active, build the website files inside my repo.

Use Gabriel1200’s public GitHub repositories only as **external read-only data sources**. Clone/fetch them during the build process, but do not try to commit to them, open PRs on them, or modify them.

External data source repos to clone/read from:

```text
https://github.com/gabriel1200/site_Data
https://github.com/gabriel1200/player_sheets
https://github.com/gabriel1200/merged_playbyplay
https://github.com/gabriel1200/pbpbacklog
https://github.com/gabriel1200/legacy_pbp
```

Use sparse checkout or partial clone for large repos when possible.

For Gabriel1200’s `player_sheets`, prioritize these folders:

```text
game_report/
teamgame_report/
series/
series/team/
year_totals/
totals/
team_totals/
```

Again:

* My repo = where you write the Playoff Translation Lab website.
* Gabriel’s repos = read-only data sources.
* Do not edit Gabriel’s repos.
* Do not proceed if you are not connected to my website repo.


Before doing any work, verify that this Codex task is running inside my own GitHub repository for the website.

The repo should be something like:

`<MY_GITHUB_USERNAME>/playoff-translation-lab`

First reply with:

Active repository:
Active branch:
Can you write files here? yes/no

If the active repo is not my own website repo, stop and tell me to select the correct Codex repo/environment.

Build a deployable website called **Playoff Translation Lab** inside my repo.

Use Gabriel1200’s public GitHub repos only as external read-only data sources. Do not edit Gabriel’s repos.

Clone/read these as data sources:

`https://github.com/gabriel1200/site_Data`
`https://github.com/gabriel1200/player_sheets`
`https://github.com/gabriel1200/merged_playbyplay`
`https://github.com/gabriel1200/pbpbacklog`
`https://github.com/gabriel1200/legacy_pbp`

Use sparse checkout/partial clone for large repos. For `player_sheets`, prioritize:

`game_report/`
`teamgame_report/`
`series/`
`series/team/`
`year_totals/`
`totals/`
`team_totals/`

Build from scratch. Do not patch any old broken version.

Project rules:

* Not RAPM2K.
* Not 2K-related.
* Do not use Brescou/Breacou.
* Do not fabricate stats.
* Missing stats show `—`.
* Target years: 1997–2026.
* If 2026 data does not exist, mark 2026 missing.
* Search must work immediately from embedded data.
* Final `index.html` must be deployable/offline after build.
* No “Load Data” button.
* Mobile-first, polished dark sports analytics UI.
* Must work on iPhone Safari.

Important stat correction:

If Gabriel scoring stats are already per 100 possessions, do not label them directly as PTS/75.

Use:

`PTS/75 = PTS_per_100 * 0.75`
`AST/75 = AST_per_100 * 0.75`
`REB/75 = REB_per_100 * 0.75`
`TOV/75 = TOV_per_100 * 0.75`

If using possession totals:

`PTS/75 = Points / OffPoss * 75`
`AST/75 = Assists / OffPoss * 75`
`TOV/75 = Turnovers / OffPoss * 75`

Only calculate REB/75 if the needed rebound and possession columns exist.

Required output files:

`index.html`
`data-package.json`
`build_data.py`
`source_manifest.json`
`README.md`
`tests/smoke_test.py`

Build a compact embedded `DATA_PACKAGE` with:

`players`
`playerSeasons`
`playerSeries`
`playerGames`
`teamBenchmarks`
`playerImpact`
`playerSkillSplits`
`rankings`

The website hierarchy must be:

`Player → Playoff Year → Series → Individual Games`

Series rows and game rows should show the same categories when real data exists:

MIN, PTS/75, REB/75, AST/75, TOV/75, TS%, eFG%, ORTG, DRTG, NET, opponent context, relative stats, on-court impact, source label.

Do not create fake series or game rows. If game logs are unavailable, show a clean message.

Relative stat formulas:

`rTS = playerTS - opponentAllowedTS`
`rEFG = playerEFG - opponentAllowedEFG`
`rORTG = playerORTG - opponentDefensiveBenchmark`
`rDRTG = opponentOffensiveBenchmark - playerDRTG`

Only calculate these when both the player stat and benchmark exist.

Use Gabriel’s deeper data if real columns exist to build sections like:

On-Court Impact
Scoring Pressure
Shot Profile
Playmaking Pressure
Possession Control
Defensive Activity
Rim/Paint Impact
Team Result Context

Use files like:

`pbp_totals_ps.csv`
`windex_ps.csv`
`poss_ps.csv`
`tracking_ps.csv`
`hustle_ps.csv`
`passing_ps.csv`
`drives.csv`
`pullup.csv`
`paint.csv`
`post.csv`
`elbow.csv`
`catchshoot.csv`
`playtype_p.csv`
`play_style_p.csv`
`dfg_p.csv`
`rimdfg_p.csv`
`rimfreq_p.csv`
`rim_acc_p.csv`
`teamplay_p.csv`
`teamplayd_p.csv`
`defense_master_ps.csv`
`team_shotzone_ps.csv`
`team_shotzone_vs_ps.csv`

Only show metrics that are real. Label whether each metric is season level, series level, game level, or context only.

UI requirements:

Title: Playoff Translation Lab
Subtitle: Search a player. See the playoff context.

Featured chips:

LeBron James, Stephen Curry, Nikola Jokic, Kobe Bryant, Kevin Durant, Giannis Antetokounmpo, Tim Duncan, Shaquille O’Neal, Michael Jordan, Dwyane Wade, James Harden, Luka Doncic.

Build sections:

Hero/Search
Player Header
Season Translation Table
Series Breakdown
Game Log
On-Court Impact
Shot Profile
Playmaking Pressure
Defensive Activity
Rankings
Data Sources

Search requirements:

Custom dropdown, not only datalist.
Dropdown opens on focus, tap, touchstart, input, and keydown.
Search supports partial names like `lebr`, `curry`, `jokic`, `kobe`, `shaq`.

Before finishing, run tests and report:

* Player count
* Season rows
* Series rows
* Game rows
* Team benchmark rows
* Impact rows
* Years loaded
* Missing years
* Source files used
* Metrics that are real
* Metrics that are context only
* Metrics unavailable
* Known limitations

Acceptance checks:

1. `index.html` opens locally with internet off.
2. Search works immediately.
3. `lebr` shows LeBron James.
4. Tapping LeBron renders profile.
5. PTS/75 is correctly calculated.
6. Year rows expand.
7. Series rows appear when real data exists.
8. Series rows expand into game rows when real data exists.
9. No fake game rows.
10. Missing stats show `—`.
11. No Brescou/Breacou labels.
12. No RAPM2K or 2K labels.
13. Mobile 390px view looks good.
14. Data Sources section shows row counts and source files.

Create the final project files, commit them, and open a PR or provide a downloadable ZIP.
