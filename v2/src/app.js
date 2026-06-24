const state = {
  index: [],
  current: null,
  tab: "overview",
};

const els = {
  indexStatus: document.getElementById("indexStatus"),
  search: document.getElementById("playerSearch"),
  results: document.getElementById("searchResults"),
  view: document.getElementById("playerView"),
};

const num = (v) => {
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
};

const fmt = (v, d = 1) => {
  const n = num(v);
  return n === null ? "—" : n.toFixed(d);
};

const pct = (v) => {
  const n = num(v);
  return n === null ? "—" : `${n.toFixed(1)}%`;
};

const get = (row, keys) => {
  for (const k of keys) {
    if (row && row[k] !== undefined && row[k] !== null && row[k] !== "") return row[k];
  }
  return "";
};

const unique = (arr) => [...new Set(arr.filter(Boolean))];

async function loadIndex() {
  const res = await fetch("./data/indexes/players.json?v=" + Date.now());
  state.index = await res.json();
  els.indexStatus.textContent = `${state.index.length.toLocaleString()} players indexed`;
  initGlobalLeaderboards();
}

function searchPlayers(q) {
  q = q.trim().toLowerCase();
  if (!q) return [];
  return state.index
    .filter(p => p.name.toLowerCase().includes(q))
    .sort((a, b) => (b.gameCount || 0) - (a.gameCount || 0))
    .slice(0, 12);
}

function renderSearchResults(rows) {
  if (!rows.length) {
    els.results.classList.remove("open");
    els.results.innerHTML = "";
    return;
  }

  els.results.classList.add("open");
  els.results.innerHTML = rows.map(p => `
    <div class="result" data-slug="${p.slug}">
      <strong>${p.name}</strong>
      <span>${p.yearMin || "—"}–${p.yearMax || "—"} • ${p.gameCount} games • ${p.seriesCount} series • ${p.teams.join(", ")}</span>
    </div>
  `).join("");
}

async function loadPlayer(slug) {
  const idx = state.index.find(p => p.slug === slug);
  if (!idx) return;

  els.results.classList.remove("open");
  els.search.value = idx.name;
  els.view.classList.remove("empty");
  els.view.innerHTML = `<div class="panel">Loading ${idx.name}...</div>`;

  const res = await fetch(`./data/${idx.file}?v=${Date.now()}`);
  state.current = await res.json();
  state.tab = "overview";
  renderPlayer();
}

function playerYears(player) {
  return player.meta.years || unique(player.games.map(g => String(get(g, ["year", "season"]))));
}

function yearOptions(rows) {
  const years = unique(rows.map(r => String(get(r, ["year", "season"])))).sort((a,b) => Number(b)-Number(a));
  return `<option value="">All years</option>` + years.map(y => `<option value="${y}">${y}</option>`).join("");
}

function rowYear(row) {
  return String(get(row, ["year", "season"]));
}

function renderPlayer() {
  const p = state.current;
  const meta = p.meta;
  const years = playerYears(p);

  els.view.innerHTML = `
    <section class="player-header">
      <div class="player-title">
        <h2>${meta.name}</h2>
        <div class="meta-line">${years[0] || "—"}–${years[years.length - 1] || "—"} • ${meta.teams.join(", ")} • Base / All-Leverage</div>
      </div>
      <div class="cards">
        ${card("Games", meta.gameCount)}
        ${card("Series", meta.seriesCount)}
        ${card("Teams", meta.teams.length)}
        ${card("Years", years.length)}
      </div>
    </section>

    <nav class="tabs">
      ${tabButton("overview", "Overview")}
      ${tabButton("games", "Game Logs")}
      ${tabButton("series", "Series Logs")}
      ${tabButton("translator", "Series Translator")}
      ${tabButton("stretch", "Stretch Lab")}
    </nav>

    <section id="tabPanel"></section>
  `;

  document.querySelectorAll(".tab").forEach(btn => {
    btn.addEventListener("click", () => {
      state.tab = btn.dataset.tab;
      renderPlayer();
    });
  });

  renderTab();
}

function card(label, value) {
  return `
    <div class="card">
      <div class="label">${label}</div>
      <div class="value">${value ?? "—"}</div>
    </div>
  `;
}

function tabButton(id, label) {
  return `<button class="tab ${state.tab === id ? "active" : ""}" data-tab="${id}">${label}</button>`;
}

function renderTab() {
  const panel = document.getElementById("tabPanel");
  if (state.tab === "overview") panel.innerHTML = renderOverview();
  if (state.tab === "games") panel.innerHTML = renderGames();
  if (state.tab === "series") panel.innerHTML = renderSeries();
  if (state.tab === "translator") panel.innerHTML = renderTranslator();
  if (state.tab === "stretch") panel.innerHTML = renderStretch();

  attachFilters();
}

function renderOverview() {
  const p = state.current;
  const latestYear = Math.max(...p.games.map(g => Number(rowYear(g))).filter(Boolean));
  const latestGames = p.games.filter(g => Number(rowYear(g)) === latestYear);

  const pts = avg(latestGames, ["PTS", "points"]);
  const min = avg(latestGames, ["MIN", "minutes"]);
  const ts = avg(latestGames, ["TS", "TS%", "tsPct"]);

  return `
    <div class="panel">
      <h3>Overview</h3>
      <div class="cards">
        ${card(`Latest Year`, latestYear || "—")}
        ${card(`Latest PPG`, fmt(pts))}
        ${card(`Latest MIN`, fmt(min))}
        ${card(`Latest TS`, ts === null ? "—" : fmt(ts))}
      </div>
      <p class="note">This V2 page loads only this player's JSON file, not the full 133MB data package.</p>
    </div>
  `;
}



const GAME_CORE_COLS = [
  ["year", "Year"], ["date", "Date"], ["team", "Team"], ["opponent", "Opp"],
  ["MIN", "MIN"], ["PTS", "PTS"], ["REB", "REB"], ["AST", "AST"],
  ["STL", "STL"], ["BLK", "BLK"], ["TOV", "TOV"],
  ["FG", "FG"], ["FGA", "FGA"], ["FG%", "FG%"],
  ["3P", "3P"], ["3PA", "3PA"], ["3P%", "3P%"],
  ["FT", "FT"], ["FTA", "FTA"], ["FT%", "FT%"],
  ["TS", "TS"], ["ORTG", "ORTG"], ["DRTG", "DRTG"], ["gameId", "Game ID"]
];

const SERIES_CORE_COLS = [
  ["year", "Year"], ["team", "Team"], ["opponent", "Opp"], ["seriesCode", "Series"],
  ["GP", "GP"], ["MIN", "MIN"], ["PTS", "PTS"], ["REB", "REB"], ["AST", "AST"],
  ["STL", "STL"], ["BLK", "BLK"], ["TOV", "TOV"],
  ["FG", "FG"], ["FGA", "FGA"], ["FG%", "FG%"],
  ["3P", "3P"], ["3PA", "3PA"], ["3P%", "3P%"],
  ["FT", "FT"], ["FTA", "FTA"], ["FT%", "FT%"],
  ["TS", "TS"], ["ORTG", "ORTG"], ["DRTG", "DRTG"]
];

const ADVANCED_COL_KEYS = [
  "POSS", "poss", "PP75", "PTS75", "AST75", "REB75",
  "TS", "TS%", "eFG", "eFG%", "USG", "USG%",
  "ORTG", "DRTG", "NET", "NETRTG",
  "rORTG", "rDRTG", "rNET", "rTS",
  "BPM", "GmSc", "gameScore", "PIE"
];

const SIX_FACTOR_COL_KEYS = [
  "teamEFG", "teamTOVPct", "teamFTr", "teamTS",
  "oppAllowedEFG", "oppAllowedTOVPct", "oppAllowedFTr", "oppAllowedTS",
  "teamEFGvsOppAllowed", "teamTOVPctvsOppAllowed", "teamFTrvsOppAllowed", "teamTSvsOppAllowed",
  "onTeamEFG", "onTeamOREBPct", "onTeamFTr", "onTeamTOVPct",
  "onOppEFG", "onOppOREBPct", "onOppFTr", "onOppTOVPct",
  "onTeamRimFreq", "onTeamRimFGPct", "onTeamShortMidFreq", "onTeamShortMidFGPct",
  "onTeamLongMidFreq", "onTeamLongMidFGPct", "onTeamCorner3Freq", "onTeamCorner3FGPct", "onTeamAboveBreak3Freq", "onTeamAboveBreak3FGPct",
  "onOppRimFreq", "onOppRimFGPct", "onOppShortMidFreq", "onOppShortMidFGPct",
  "onOppLongMidFreq", "onOppLongMidFGPct", "onOppCorner3Freq", "onOppCorner3FGPct", "onOppAboveBreak3Freq", "onOppAboveBreak3FGPct"
];

const ALIASES = {
  "date": ["date", "gameDate", "GAME_DATE"],
  "team": ["team", "TEAM", "teamAbbr", "TEAM_ABBREVIATION"],
  "opponent": ["opponent", "opp", "OPP"],
  "seriesCode": ["seriesCode", "series", "round"],
  "GP": ["GP", "games", "G"],
  "MIN": ["MIN", "minutes"],
  "PTS": ["PTS", "points"],
  "REB": ["REB", "TRB", "rebounds"],
  "AST": ["AST", "assists"],
  "STL": ["STL", "steals"],
  "BLK": ["BLK", "blocks"],
  "TOV": ["TOV", "TO", "turnovers"],
  "FG": ["FG", "FGM", "fgm"],
  "FGA": ["FGA", "fga"],
  "FG%": ["FG%", "FG_PCT", "fgPct"],
  "3P": ["3P", "FG3M", "fg3m"],
  "3PA": ["3PA", "FG3A", "fg3a"],
  "3P%": ["3P%", "FG3_PCT", "fg3Pct"],
  "FT": ["FT", "FTM", "ftm"],
  "FTA": ["FTA", "fta"],
  "FT%": ["FT%", "FT_PCT", "ftPct"],
  "TS": ["TS", "TS%", "tsPct"],
  "ORTG": ["ORTG", "offRtg", "OFF_RATING"],
  "DRTG": ["DRTG", "defRtg", "DEF_RATING"],
  "gameId": ["gameId", "GAME_ID", "gid"]
};

function firstValue(row, key) {
  const keys = ALIASES[key] || [key];
  for (const k of keys) {
    if (row && row[k] !== undefined && row[k] !== null && row[k] !== "") return row[k];
  }
  return "";
}

function hasAnyValue(rows, key) {
  return rows.some(r => firstValue(r, key) !== "");
}

function prettyLabel(key) {
  return String(key)
    .replace(/^team/, "Team ")
    .replace(/^oppAllowed/, "Opp Allowed ")
    .replace(/^onTeam/, "ON Team ")
    .replace(/^onOpp/, "ON Opp ")
    .replace(/Pct/g, "%")
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/_/g, " ")
    .trim();
}

function allKeysFromRows(rows) {
  const skip = new Set(["_raw", "__proto__"]);
  const preferred = [
    "year","season","date","gameDate","team","opponent","opp","seriesCode","gameId",
    "MIN","PTS","REB","AST","STL","BLK","TOV","FG","FGA","FG%","3P","3PA","3P%","FT","FTA","FT%",
    "TS","ORTG","DRTG","NET","PP75","POSS","USG","rTS","rORTG","rDRTG","rNET",
    ...SIX_FACTOR_COL_KEYS
  ];

  const seen = new Set();
  const keys = [];

  for (const k of preferred) {
    if (!seen.has(k) && hasAnyValue(rows, k)) {
      keys.push(k);
      seen.add(k);
    }
  }

  for (const r of rows) {
    if (!r || typeof r !== "object") continue;
    for (const k of Object.keys(r)) {
      if (skip.has(k) || seen.has(k)) continue;
      if (hasAnyValue(rows, k)) {
        keys.push(k);
        seen.add(k);
      }
    }
  }

  return keys.map(k => [k, prettyLabel(k)]);
}

function tableColumnsFor(rows, type, baseCols) {
  const mode = document.getElementById("statViewFilter")?.value || "core";

  if (mode === "all") return allKeysFromRows(rows);

  if (mode === "advanced") {
    const cols = [...baseCols];
    for (const k of ADVANCED_COL_KEYS) {
      if (!cols.some(c => c[0] === k) && hasAnyValue(rows, k)) cols.push([k, prettyLabel(k)]);
    }
    return cols;
  }

  if (mode === "context") {
    const cols = [...baseCols.slice(0, 4)];
    for (const k of SIX_FACTOR_COL_KEYS) {
      if (hasAnyValue(rows, k)) cols.push([k, prettyLabel(k)]);
    }
    return cols.length > 4 ? cols : [...baseCols];
  }

  return baseCols.filter(([k]) => hasAnyValue(rows, k) || ["year","date","team","opponent","seriesCode","gameId"].includes(k));
}

function tableValue(row, key) {
  const v = firstValue(row, key);
  if (v === undefined || v === null || v === "") return "—";
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : v.toFixed(1);
  const n = Number(v);
  if (Number.isFinite(n) && String(v).trim() !== "" && !String(v).startsWith("0") && Math.abs(n) < 100000) {
    return Number.isInteger(n) ? String(n) : n.toFixed(1);
  }
  return String(v);
}

function richTable(rows, cols) {
  if (!rows.length) return `<p class="note">No rows found.</p>`;
  return `
    <div class="table-wrap">
      <table>
        <thead>
          <tr>${cols.map(c => `<th>${c[1]}</th>`).join("")}</tr>
        </thead>
        <tbody>
          ${rows.map(r => `
            <tr>
              ${cols.map(([key]) => `<td>${tableValue(r, key)}</td>`).join("")}
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}


function renderGames() {
  const rows = state.current.games;
  return `
    <section class="panel court-section-panel">
      <h3>Game Logs</h3>
      <div class="toolbar">
        <select id="yearFilter">${yearOptions(rows)}</select>
        <input id="oppFilter" placeholder="Filter opponent/team...">
        <select id="sortFilter">
          <option value="date">Sort: Date/Game</option>
          <option value="PTS">Sort: Points</option>
          <option value="MIN">Sort: Minutes</option>
          <option value="TS">Sort: TS</option>
          <option value="ORTG">Sort: ORTG</option>
        </select>
        <select id="statViewFilter">
          <option value="core">View: Core Box + Advanced</option>
          <option value="advanced">View: Advanced / Relative</option>
          <option value="context">View: Team Context / ON-Court</option>
          <option value="all">View: All Stats</option>
        </select>
      </div>
      <div id="gamesTable"></div>
    </section>
  `;
}



function renderSeries() {
  const rows = state.current.series;
  return `
    <section class="panel court-section-panel">
      <h3>Series Logs</h3>
      <div class="toolbar">
        <select id="yearFilter">${yearOptions(rows)}</select>
        <input id="oppFilter" placeholder="Filter opponent/team...">
        <select id="sortFilter">
          <option value="year">Sort: Year</option>
          <option value="PTS">Sort: Points</option>
          <option value="MIN">Sort: Minutes</option>
          <option value="TS">Sort: TS</option>
          <option value="ORTG">Sort: ORTG</option>
        </select>
        <select id="statViewFilter">
          <option value="core">View: Core Box + Advanced</option>
          <option value="advanced">View: Advanced / Relative</option>
          <option value="context">View: Team Context / ON-Court</option>
          <option value="all">View: All Stats</option>
        </select>
      </div>
      <div id="seriesTable"></div>
    </section>
  `;
}





/* Real Series Translation Consistency Tool */
function __ptlRTGet(row, keys) {
  for (const k of keys) {
    if (row && row[k] !== undefined && row[k] !== null && row[k] !== "" && row[k] !== "—") return row[k];
  }
  return null;
}

function __ptlRTNum(row, keys) {
  const v = __ptlRTGet(row, keys);
  if (v === null) return null;
  const n = Number(String(v).replace("+", ""));
  return Number.isFinite(n) ? n : null;
}

function __ptlRTYear(row) {
  return String(__ptlRTGet(row, ["year", "season", "YEAR", "SEASON"]) || "");
}

function __ptlRTTeam(row) {
  return String(__ptlRTGet(row, ["team", "TEAM", "teamAbbr", "TEAM_ABBREVIATION"]) || "");
}

function __ptlRTOpp(row) {
  return String(__ptlRTGet(row, ["opponent", "opp", "OPP", "Opponent"]) || "");
}

function __ptlRTRound(row) {
  return String(__ptlRTGet(row, ["round", "ROUND", "seriesRound", "series", "seriesCode"]) || "Playoff Series");
}

function __ptlRTGames(row) {
  return __ptlRTNum(row, ["GAMES", "GP", "games", "gp"]) || 0;
}

function __ptlRTLeague(row, key) {
  const y = __ptlRTYear(row);
  return state.seasonContext?.byYear?.[y]?.[key] ?? null;
}

function __ptlRTMetric(row, key) {
  if (key === "rORTG") {
    const direct = __ptlRTNum(row, ["rORTG", "relORTG"]);
    if (direct !== null) return direct;

    const ortg = __ptlRTNum(row, ["onORTG", "onORTGStrict", "ORTG", "offRtg", "OFF_RATING"]);
    const lg = __ptlRTLeague(row, "leagueORTG");
    if (ortg === null || lg === null || lg === undefined) return null;
    return ortg - Number(lg);
  }

  if (key === "rDRTG") {
    const direct = __ptlRTNum(row, ["rDRTG", "relDRTG"]);
    if (direct !== null) return direct;

    const drtg = __ptlRTNum(row, ["onDRTG", "onDRTGStrict", "DRTG", "defRtg", "DEF_RATING"]);
    const lg = __ptlRTLeague(row, "leagueDRTG");
    if (drtg === null || lg === null || lg === undefined) return null;

    // positive = better defense
    return Number(lg) - drtg;
  }

  if (key === "rNET") {
    const direct = __ptlRTNum(row, ["rNET", "relNET", "rNet"]);
    if (direct !== null) return direct;

    const ro = __ptlRTMetric(row, "rORTG");
    const rd = __ptlRTMetric(row, "rDRTG");
    if (ro === null || rd === null) return null;
    return ro + rd;
  }

  return null;
}

function __ptlRTSeriesKey(row) {
  return [
    __ptlRTYear(row),
    __ptlRTTeam(row),
    __ptlRTOpp(row),
    __ptlRTRound(row)
  ].join("|");
}

function __ptlRTGamesForSeries(seriesRow) {
  const exact = (state.current?.games || []).filter(g => __ptlRTSeriesKey(g) === __ptlRTSeriesKey(seriesRow));
  if (exact.length) return exact;

  return (state.current?.games || []).filter(g =>
    __ptlRTYear(g) === __ptlRTYear(seriesRow) &&
    __ptlRTOpp(g) === __ptlRTOpp(seriesRow) &&
    (!__ptlRTTeam(seriesRow) || __ptlRTTeam(g) === __ptlRTTeam(seriesRow))
  );
}

function __ptlRTAvg(vals) {
  const good = vals.filter(v => v !== null && Number.isFinite(v));
  if (!good.length) return null;
  return good.reduce((a, b) => a + b, 0) / good.length;
}

function __ptlRTFmt(v, signed = false) {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return "—";
  return `${signed && v > 0 ? "+" : ""}${Number(v).toFixed(1)}`;
}

function __ptlRTTranslated(gameVals, seriesVal, threshold, cushion) {
  const vals = gameVals.filter(v => v !== null && Number.isFinite(v));
  if (!vals.length) return false;

  const hits = vals.filter(v => v >= threshold).length;
  const majorityNeeded = Math.floor(vals.length / 2) + 1;

  if (hits >= majorityNeeded) return true;

  if (vals.length % 2 === 0 && hits === vals.length / 2) {
    return seriesVal !== null && seriesVal >= threshold - cushion;
  }

  return false;
}

function __ptlRTBuild() {
  const from = Number(document.getElementById("rtFrom")?.value || 2001);
  const to = Number(document.getElementById("rtTo")?.value || 2026);
  const offT = Number(document.getElementById("rtOff")?.value || 3);
  const defT = Number(document.getElementById("rtDef")?.value || 5);
  const netT = Number(document.getElementById("rtNet")?.value || 4);
  const cushion = Number(document.getElementById("rtCushion")?.value || 0.2);
  const minGames = Number(document.getElementById("rtMinGames")?.value || 3);

  const series = (state.current?.series || [])
    .filter(s => {
      const y = Number(__ptlRTYear(s));
      const gp = __ptlRTGames(s);
      return y >= from && y <= to && gp >= minGames;
    })
    .sort((a, b) => Number(__ptlRTYear(a)) - Number(__ptlRTYear(b)));

  const rows = series.map(s => {
    const games = __ptlRTGamesForSeries(s);

    const gOff = games.map(g => __ptlRTMetric(g, "rORTG"));
    const gDef = games.map(g => __ptlRTMetric(g, "rDRTG"));
    const gNet = games.map(g => __ptlRTMetric(g, "rNET"));

    const sOff = __ptlRTMetric(s, "rORTG") ?? __ptlRTAvg(gOff);
    const sDef = __ptlRTMetric(s, "rDRTG") ?? __ptlRTAvg(gDef);
    const sNet = __ptlRTMetric(s, "rNET") ?? __ptlRTAvg(gNet);

    const off = __ptlRTTranslated(gOff, sOff, offT, cushion);
    const def = __ptlRTTranslated(gDef, sDef, defT, cushion);
    const net = __ptlRTTranslated(gNet, sNet, netT, cushion);

    return {
      year: __ptlRTYear(s),
      round: __ptlRTRound(s),
      opp: __ptlRTOpp(s),
      games: __ptlRTGames(s) || games.length,
      rORTG: sOff,
      rDRTG: sDef,
      rNET: sNet,
      offHits: gOff.filter(v => v !== null && v >= offT).length + "/" + gOff.filter(v => v !== null).length,
      defHits: gDef.filter(v => v !== null && v >= defT).length + "/" + gDef.filter(v => v !== null).length,
      netHits: gNet.filter(v => v !== null && v >= netT).length + "/" + gNet.filter(v => v !== null).length,
      off,
      def,
      net,
      all3: off && def && net,
    };
  });

  return { rows, from, to, offT, defT, netT, cushion, minGames };
}

function __ptlRTCard(label, value, note) {
  return `
    <div class="stat-card">
      <div class="label">${label}</div>
      <div class="value">${value}</div>
      <p class="note">${note}</p>
    </div>
  `;
}

function __ptlRTUpdate() {
  const out = document.getElementById("rtOutput");
  if (!out || !state.current) return;

  const { rows, from, to, offT, defT, netT, cushion, minGames } = __ptlRTBuild();
  const total = rows.length;

  const offCount = rows.filter(r => r.off).length;
  const defCount = rows.filter(r => r.def).length;
  const netCount = rows.filter(r => r.net).length;
  const all3Count = rows.filter(r => r.all3).length;

  const tableRows = rows.map(r => ({
    year: r.year,
    round: r.round,
    opp: r.opp,
    games: r.games,
    rORTG: __ptlRTFmt(r.rORTG, true),
    rDRTG: __ptlRTFmt(r.rDRTG, true),
    rNET: __ptlRTFmt(r.rNET, true),
    offHits: r.offHits,
    defHits: r.defHits,
    netHits: r.netHits,
    off: r.off ? "YES" : "NO",
    def: r.def ? "YES" : "NO",
    net: r.net ? "YES" : "NO",
    all3: r.all3 ? "YES" : "NO",
  }));

  out.innerHTML = `
    <div class="stat-grid">
      ${__ptlRTCard("OFFENSE TRANSLATES", `${offCount}/${total}`, `${from}–${to}: rORTG ≥ +${offT}. Cushion: ${cushion}.`)}
      ${__ptlRTCard("DEFENSE TRANSLATES", `${defCount}/${total}`, `${from}–${to}: rDRTG ≥ +${defT}. Positive is better.`)}
      ${__ptlRTCard("NET TRANSLATES", `${netCount}/${total}`, `${from}–${to}: rNET ≥ +${netT}.`)}
      ${__ptlRTCard("TWO-WAY / ALL 3", `${all3Count}/${total}`, `All 3 translated in ${all3Count}/${total} series. Min games: ${minGames}.`)}
    </div>

    <div style="height:14px"></div>

    <h3>Series Breakdown</h3>
    ${richTable(tableRows, [
      ["year", "Year"],
      ["round", "Round"],
      ["opp", "Opp"],
      ["games", "Games"],
      ["rORTG", "rORTG"],
      ["rDRTG", "rDRTG"],
      ["rNET", "rNET"],
      ["offHits", "Off Games"],
      ["defHits", "Def Games"],
      ["netHits", "Net Games"],
      ["off", "Off"],
      ["def", "Def"],
      ["net", "Net"],
      ["all3", "All 3"],
    ])}
  `;
}

function __ptlRTRenderTool() {
  const years = [...new Set((state.current?.series || []).map(__ptlRTYear).filter(Boolean))]
    .sort((a, b) => Number(a) - Number(b));

  const minY = years[0] || "2001";
  const maxY = years[years.length - 1] || "2026";

  setTimeout(() => __ptlRTUpdate(), 80);

  return `
    <section class="panel court-section-panel">
      <h3>Series Translation Consistency</h3>
      <p class="note">
        Counts translation from game-by-game impact inside each series. Majority of games hitting the threshold counts automatically.
        Exactly half only counts when the series average is close enough to the threshold.
      </p>

      <div class="toolbar">
        <label class="note">From <input id="rtFrom" type="number" value="${minY}" style="width:90px"></label>
        <label class="note">To <input id="rtTo" type="number" value="${maxY}" style="width:90px"></label>
        <label class="note">rORTG ≥ <input id="rtOff" type="number" value="3" step="0.1" style="width:90px"></label>
        <label class="note">rDRTG ≥ <input id="rtDef" type="number" value="5" step="0.1" style="width:90px"></label>
        <label class="note">rNET ≥ <input id="rtNet" type="number" value="4" step="0.1" style="width:90px"></label>
        <label class="note">Cushion <input id="rtCushion" type="number" value="0.2" step="0.1" style="width:90px"></label>
        <label class="note">Min Games <input id="rtMinGames" type="number" value="3" step="1" style="width:90px"></label>
      </div>

      <div id="rtOutput"></div>
    </section>
  `;
}

document.addEventListener("input", function(e) {
  if (!e.target) return;
  if (["rtFrom", "rtTo", "rtOff", "rtDef", "rtNet", "rtCushion", "rtMinGames"].includes(e.target.id)) {
    __ptlRTUpdate();
  }
});


function renderTranslator() {
  return __ptlRTRenderTool();
}




function stretchSortDate(row) {
  return String(get(row, ["date", "gameDate", "GAME_DATE", "gameId", "GAME_ID"]) || "");
}

function stretchSeriesKey(row) {
  const y = rowYear(row);
  const team = rowTeam(row);
  const opp = rowOpp(row);
  const code = get(row, ["seriesCode", "series", "round"]) || "";
  return code ? `${y}|${code}|${team}|${opp}` : `${y}|${team}|${opp}`;
}

function stretchSeriesLabel(row) {
  const y = rowYear(row);
  const team = rowTeam(row);
  const opp = rowOpp(row);
  const code = get(row, ["seriesCode", "series", "round"]) || "";
  return `${y} ${team} vs ${opp}${code ? " • " + code : ""}`;
}

function stretchMetricNumber(row, key) {
  // supports normal fields and computed patch fields like adjTS/rAdjTS if tableValue knows them
  if (typeof tableValue === "function") {
    const rendered = tableValue(row, key);
    if (rendered !== "—" && rendered !== undefined && rendered !== null) {
      const n = Number(String(rendered).replace("+", ""));
      if (Number.isFinite(n)) return n;
    }
  }

  const v = firstValue ? firstValue(row, key) : get(row, [key]);
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

function stretchAvg(rows, key) {
  const vals = rows.map(r => stretchMetricNumber(r, key)).filter(v => v !== null);
  if (!vals.length) return null;
  return vals.reduce((a,b) => a + b, 0) / vals.length;
}

function stretchFmt(v, signed=false) {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const sign = signed && v > 0 ? "+" : "";
  return sign + Number(v).toFixed(1);
}

function getGamesForSeriesPick(games, pick) {
  if (!pick || pick === "all") return games;
  return games.filter(g => stretchSeriesKey(g) === pick);
}

function buildStretchOptionsForYear(mode, year) {
  const pick = document.getElementById("stretchPick");
  const len = document.getElementById("stretchLen");
  if (!pick || !len || !state.current) return;

  const currentPick = pick.value;

  if (mode === "games") {
    const games = state.current.games.filter(g => !year || rowYear(g) === year);
    const bySeries = new Map();

    games.forEach(g => {
      const key = stretchSeriesKey(g);
      if (!bySeries.has(key)) bySeries.set(key, g);
    });

    pick.innerHTML =
      `<option value="all">All games in selected year</option>` +
      [...bySeries.entries()]
        .sort((a,b) => stretchSeriesLabel(a[1]).localeCompare(stretchSeriesLabel(b[1])))
        .map(([key,row]) => `<option value="${key}">${stretchSeriesLabel(row)}</option>`)
        .join("");

    len.innerHTML = `
      <option value="3">3-game stretches</option>
      <option value="5" selected>5-game stretches</option>
      <option value="10">10-game stretches</option>
      <option value="20">20-game stretches</option>
    `;
  } else {
    const series = state.current.series.filter(s => !year || rowYear(s) === year);

    pick.innerHTML =
      `<option value="all">All series in selected year</option>` +
      series
        .slice()
        .sort((a,b) => stretchSeriesLabel(a).localeCompare(stretchSeriesLabel(b)))
        .map((row, i) => `<option value="${stretchSeriesKey(row)}">${stretchSeriesLabel(row)}</option>`)
        .join("");

    len.innerHTML = `
      <option value="1" selected>1-series view</option>
      <option value="2">2-series stretches</option>
      <option value="3">3-series stretches</option>
      <option value="4">4-series stretches</option>
    `;
  }

  if ([...pick.options].some(o => o.value === currentPick)) {
    pick.value = currentPick;
  }
}

function stretchRowsTable(rows, metricLabel) {
  return richTable ? richTable(rows, [
    ["rank", "Rank"],
    ["range", "Range"],
    ["count", "Count"],
    ["metric", metricLabel],
    ["detail", "Detail"],
  ]) : table(rows, [
    ["rank", "Rank"],
    ["range", "Range"],
    ["count", "Count"],
    ["metric", metricLabel],
    ["detail", "Detail"],
  ]);
}





function rangeYearOptions() {
  const years = [...new Set((state.current?.games || []).map(rowYear).filter(Boolean))]
    .sort((a,b) => Number(b) - Number(a));

  return years.map((y, i) => `<option value="${y}" ${i === 0 ? "selected" : ""}>${y}</option>`).join("");
}

function rangeDate(row) {
  return String(get(row, ["date", "gameDate", "GAME_DATE", "gameId", "GAME_ID"]) || "");
}

function rangeSeriesLabel(row) {
  const y = rowYear(row);
  const team = rowTeam(row);
  const opp = rowOpp(row);
  const code = get(row, ["seriesCode", "series", "round"]) || "";
  return `${y} ${team} vs ${opp}${code ? " • " + code : ""}`;
}

function rangeGameLabel(row, i) {
  const date = rangeDate(row);
  const team = rowTeam(row);
  const opp = rowOpp(row);
  const pts = tableValue ? tableValue(row, "PTS") : get(row, ["PTS"]);
  return `G${i + 1} • ${date} • ${team} vs ${opp} • ${pts} PTS`;
}

function rangeMetricNumber(row, key) {
  if (typeof tableValue === "function") {
    const rendered = tableValue(row, key);
    if (rendered !== "—" && rendered !== undefined && rendered !== null) {
      const n = Number(String(rendered).replace("+", ""));
      if (Number.isFinite(n)) return n;
    }
  }

  const v = typeof firstValue === "function" ? firstValue(row, key) : get(row, [key]);
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

function rangeAvg(rows, key) {
  const vals = rows.map(r => rangeMetricNumber(r, key)).filter(v => v !== null);
  if (!vals.length) return null;
  return vals.reduce((a,b) => a + b, 0) / vals.length;
}

function rangeSum(rows, key) {
  const vals = rows.map(r => rangeMetricNumber(r, key)).filter(v => v !== null);
  if (!vals.length) return null;
  return vals.reduce((a,b) => a + b, 0);
}

function rangeFmt(v, signed=false) {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const sign = signed && v > 0 ? "+" : "";
  return sign + Number(v).toFixed(1);
}

function rangeRowsForSelection(mode, year) {
  if (mode === "series") {
    return (state.current?.series || [])
      .filter(r => rowYear(r) === year)
      .slice()
      .sort((a,b) => rangeSeriesLabel(a).localeCompare(rangeSeriesLabel(b)));
  }

  return (state.current?.games || [])
    .filter(r => rowYear(r) === year)
    .slice()
    .sort((a,b) => rangeDate(a).localeCompare(rangeDate(b)));
}

function rangeUpdatePickers(force=false) {
  const year = document.getElementById("stretchYear")?.value || "";
  const mode = document.getElementById("stretchMode")?.value || "games";
  const start = document.getElementById("stretchStart");
  const end = document.getElementById("stretchEnd");
  if (!start || !end) return;

  const key = `${mode}|${year}`;
  if (!force && start.dataset.rangeKey === key && end.dataset.rangeKey === key) return;

  const rows = rangeRowsForSelection(mode, year);

  if (!rows.length) {
    start.innerHTML = `<option value="">No rows</option>`;
    end.innerHTML = `<option value="">No rows</option>`;
    start.dataset.rangeKey = key;
    end.dataset.rangeKey = key;
    return;
  }

  const options = rows.map((r, i) => {
    const label = mode === "series" ? rangeSeriesLabel(r) : rangeGameLabel(r, i);
    return `<option value="${i}">${label}</option>`;
  }).join("");

  start.innerHTML = options;
  end.innerHTML = options;

  start.value = "0";
  end.value = String(rows.length - 1);

  start.dataset.rangeKey = key;
  end.dataset.rangeKey = key;
}




/* Clean Stretch Lab helpers */
function cleanStretchRows(mode, year) {
  const rows = mode === "series" ? (state.current?.series || []) : (state.current?.games || []);

  return rows
    .filter(r => String(rowYear(r)) === String(year))
    .slice()
    .sort((a, b) => {
      const ad = String(get(a, ["date", "gameDate", "GAME_DATE", "gameId", "GAME_ID"]) || "");
      const bd = String(get(b, ["date", "gameDate", "GAME_DATE", "gameId", "GAME_ID"]) || "");
      return ad.localeCompare(bd);
    });
}

function cleanStretchLabel(row, i, mode) {
  if (mode === "series") {
    const round = get(row, ["round", "seriesRound", "ROUND"]) || "Series";
    const opp = rowOpp(row) || get(row, ["OPP", "opp"]) || "";
    const pts = typeof tableValue === "function" ? tableValue(row, "PTS/75") : (get(row, ["PTS/75"]) || "");
    return `S${i + 1} • ${rowYear(row)} • ${round} • vs ${opp} • ${pts} PTS/75`;
  }

  const date = get(row, ["date", "gameDate", "GAME_DATE"]) || get(row, ["gameId", "GAME_ID"]) || "Game";
  const opp = rowOpp(row) || get(row, ["OPP", "opp"]) || "";
  const pts = typeof tableValue === "function" ? tableValue(row, "PTS") : (get(row, ["PTS"]) || "");
  return `G${i + 1} • ${date} • vs ${opp} • ${pts} PTS`;
}

function cleanPopulateStretchDropdowns() {
  const year = document.getElementById("stretchYear")?.value || "";
  const mode = document.getElementById("stretchMode")?.value || "games";
  const start = document.getElementById("stretchStart");
  const end = document.getElementById("stretchEnd");

  if (!start || !end) return;

  const rows = cleanStretchRows(mode, year);

  if (!rows.length) {
    start.innerHTML = `<option value="">No ${mode === "series" ? "series" : "games"} found for ${year}</option>`;
    end.innerHTML = `<option value="">No ${mode === "series" ? "series" : "games"} found for ${year}</option>`;
    return;
  }

  const options = rows.map((row, i) => {
    const label = cleanStretchLabel(row, i, mode);
    return `<option value="${i}">${label}</option>`;
  }).join("");

  const oldStart = start.value;
  const oldEnd = end.value;

  start.innerHTML = options;
  end.innerHTML = options;

  start.value = oldStart && Number(oldStart) < rows.length ? oldStart : "0";
  end.value = oldEnd && Number(oldEnd) < rows.length ? oldEnd : String(rows.length - 1);
}

function cleanMetricNumber(row, key) {
  const v = typeof tableValue === "function" ? tableValue(row, key) : get(row, [key]);
  const n = Number(String(v).replace("+", ""));
  return Number.isFinite(n) ? n : null;
}

function cleanAvg(rows, key) {
  const vals = rows.map(r => cleanMetricNumber(r, key)).filter(v => v !== null);
  if (!vals.length) return null;
  return vals.reduce((a, b) => a + b, 0) / vals.length;
}

function cleanSum(rows, key) {
  const vals = rows.map(r => cleanMetricNumber(r, key)).filter(v => v !== null);
  if (!vals.length) return null;
  return vals.reduce((a, b) => a + b, 0);
}

function cleanFmt(v, signed=false) {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return "—";
  return `${signed && v > 0 ? "+" : ""}${Number(v).toFixed(1)}`;
}


function renderStretch() {
  const years = [...new Set((state.current?.games || []).concat(state.current?.series || []).map(rowYear).filter(Boolean))]
    .sort((a, b) => Number(b) - Number(a));

  const yearOptions = years.map(y => `<option value="${y}">${y}</option>`).join("");

  setTimeout(() => {
    cleanPopulateStretchDropdowns();
    updateStretch();
  }, 50);

  return `
    <section class="panel court-section-panel">
      <h3>Stretch Lab</h3>

      <div class="toolbar">
        <select id="stretchYear">${yearOptions}</select>

        <select id="stretchMode">
          <option value="games">Game Stretch</option>
          <option value="series">Series Stretch</option>
        </select>

        <select id="stretchMetric">
          <option value="PTS">Points</option>
          <option value="PTS/75">PTS/75</option>
          <option value="TS%">TS%</option>
          <option value="AdjTS%">AdjTS%</option>
          <option value="rTS">rTS</option>
          <option value="rAdjTS">rAdjTS</option>
          <option value="ORTG">ORTG</option>
          <option value="DRTG">DRTG</option>
          <option value="REB">Rebounds</option>
          <option value="AST">Assists</option>
        </select>
      </div>

      <div class="toolbar">
        <select id="stretchStart"></select>
        <select id="stretchEnd"></select>
      </div>

      <p class="note">Top dropdown = stretch start. Bottom dropdown = stretch end.</p>

      <div id="stretchOutput" style="margin-top:14px"></div>
    </section>
  `;
}







function attachFilters() {
  if (state.tab === "games") {
    ["yearFilter", "oppFilter", "sortFilter", "statViewFilter"].forEach(id => document.getElementById(id)?.addEventListener("input", updateGamesTable));
    updateGamesTable();
  }

  if (state.tab === "series") {
    ["yearFilter", "oppFilter", "sortFilter", "statViewFilter"].forEach(id => document.getElementById(id)?.addEventListener("input", updateSeriesTable));
    updateSeriesTable();
  }

  if (state.tab === "translator") {
    document.getElementById("translatorPick")?.addEventListener("input", updateTranslator);
    updateTranslator();
  }

  if (state.tab === "stretch") {
    ["stretchYear", "stretchMode", "stretchMetric", "stretchStart", "stretchEnd"].forEach(id => document.getElementById(id)?.addEventListener("input", updateStretch));
    updateStretch();
  }
}

function filterRows(rows) {
  const y = document.getElementById("yearFilter")?.value || "";
  const opp = (document.getElementById("oppFilter")?.value || "").toLowerCase();
  const sort = document.getElementById("sortFilter")?.value || "";

  let out = rows.filter(r => {
    const ry = rowYear(r);
    const hay = JSON.stringify({
      team: get(r, ["team", "TEAM"]),
      opp: get(r, ["opponent", "opp", "OPP"]),
      series: get(r, ["seriesCode", "series"])
    }).toLowerCase();

    return (!y || ry === y) && (!opp || hay.includes(opp));
  });

  out.sort((a, b) => {
    if (sort === "year" || sort === "date") return Number(rowYear(b)) - Number(rowYear(a));
    return (num(get(b, [sort])) ?? -999999) - (num(get(a, [sort])) ?? -999999);
  });

  return out;
}

function updateGamesTable() {
  const rows = filterRows(state.current.games);
  const cols = tableColumnsFor(rows, "games", GAME_CORE_COLS);
  document.getElementById("gamesTable").innerHTML = richTable(rows, cols);
}



function updateSeriesTable() {
  const rows = filterRows(state.current.series);
  const cols = tableColumnsFor(rows, "series", SERIES_CORE_COLS);
  document.getElementById("seriesTable").innerHTML = richTable(rows, cols);
}



function updateTranslator() {
  const idx = Number(document.getElementById("translatorPick")?.value || 0);
  const r = state.current.series[idx];
  const out = document.getElementById("translatorOutput");
  if (!r) return out.innerHTML = "";

  out.innerHTML = `
    <div class="cards">
      ${card("Year", rowYear(r))}
      ${card("Matchup", `${get(r, ["team"])} vs ${get(r, ["opponent", "opp"]) || "—"}`)}
      ${card("PTS", fmt(get(r, ["PTS", "points"])))}
      ${card("TS", fmt(get(r, ["TS", "TS%"])))}
      ${card("ORTG", fmt(get(r, ["ORTG", "offRtg"])))}
      ${card("DRTG", fmt(get(r, ["DRTG", "defRtg"])))}
      ${card("MIN", fmt(get(r, ["MIN", "minutes"])))}
      ${card("GP", get(r, ["GP", "games"]) || "—")}
    </div>
  `;
}

function updateStretch() {
  const year = document.getElementById("stretchYear")?.value || "";
  const mode = document.getElementById("stretchMode")?.value || "games";
  const metric = document.getElementById("stretchMetric")?.value || "PTS";
  const out = document.getElementById("stretchOutput");

  if (!out || !state.current) return;

  cleanPopulateStretchDropdowns();

  const rows = cleanStretchRows(mode, year);
  if (!rows.length) {
    out.innerHTML = `<p class="note">No ${mode === "series" ? "series" : "games"} found for ${year}.</p>`;
    return;
  }

  let startIdx = Number(document.getElementById("stretchStart")?.value || 0);
  let endIdx = Number(document.getElementById("stretchEnd")?.value || rows.length - 1);

  if (startIdx > endIdx) {
    const tmp = startIdx;
    startIdx = endIdx;
    endIdx = tmp;
  }

  const selected = rows.slice(startIdx, endIdx + 1);
  const signed = metric.toLowerCase().includes("radj") || metric.toLowerCase().includes("rts") || metric.toLowerCase().includes("net");

  const summaryRows = [
    { label: "Start", value: cleanStretchLabel(selected[0], startIdx, mode) },
    { label: "End", value: cleanStretchLabel(selected[selected.length - 1], endIdx, mode) },
    { label: mode === "series" ? "Series Count" : "Game Count", value: selected.length },
    { label: `${metric} Avg`, value: cleanFmt(cleanAvg(selected, metric), signed) },
    { label: "Total Points", value: cleanFmt(cleanSum(selected, "PTS")) },
    { label: "Total Minutes", value: cleanFmt(cleanSum(selected, "MIN")) },
  ];

  const detailCols = mode === "series"
    ? [
        ["year", "Year"], ["round", "Round"], ["opponent", "Opp"], ["GAMES", "Games"],
        ["MIN", "MIN"], ["PTS/75", "PTS/75"], ["TS%", "TS%"],
        ["AdjTS%", "AdjTS%"], ["rTS", "rTS"], ["rAdjTS", "rAdjTS"]
      ]
    : [
        ["year", "Year"], ["date", "Date"], ["opponent", "Opp"],
        ["MIN", "MIN"], ["PTS", "PTS"], ["PTS/75", "PTS/75"], ["TS%", "TS%"],
        ["AdjTS%", "AdjTS%"], ["rTS", "rTS"], ["rAdjTS", "rAdjTS"], ["gameId", "Game ID"]
      ];

  out.innerHTML = `
    <h3>Selected ${mode === "series" ? "Series" : "Game"} Stretch</h3>
    ${richTable(summaryRows, [["label", "Item"], ["value", "Value"]])}

    <div style="height:14px"></div>

    <h3>Rows Included</h3>
    ${richTable(selected, detailCols)}
  `;
}







function avg(rows, keys) {
  const vals = rows.map(r => num(get(r, keys))).filter(v => v !== null);
  if (!vals.length) return null;
  return vals.reduce((a, b) => a + b, 0) / vals.length;
}

function table(rows, cols) {
  if (!rows.length) return `<p class="note">No rows found.</p>`;
  return `
    <div class="table-wrap">
      <table>
        <thead>
          <tr>${cols.map(c => `<th>${c[1]}</th>`).join("")}</tr>
        </thead>
        <tbody>
          ${rows.map(r => `
            <tr>
              ${cols.map(([key]) => `<td>${formatCell(r, key)}</td>`).join("")}
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function formatCell(row, key) {
  const v = row[key];
  if (v === undefined || v === null || v === "") return "—";
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : v.toFixed(1);
  return String(v);
}

els.search.addEventListener("input", () => renderSearchResults(searchPlayers(els.search.value)));

els.results.addEventListener("click", (e) => {
  const result = e.target.closest(".result");
  if (result) loadPlayer(result.dataset.slug);
});



async function loadGlobalLeaderboards() {
  if (state.globalLeaderboards) return state.globalLeaderboards;

  const res = await fetch("./data/indexes/leaderboards.json?v=" + Date.now());
  state.globalLeaderboards = await res.json();
  return state.globalLeaderboards;
}

async function updateGlobalLeaderboard() {
  const tableBox = document.getElementById("globalLeaderboardTable");
  const picker = document.getElementById("globalLeaderboardType");
  if (!tableBox || !picker) return;

  tableBox.innerHTML = `<p class="note">Loading...</p>`;

  try {
    const data = await loadGlobalLeaderboards();
    const type = picker.value;
    const rows = data[type] || [];

    const isSeries = type.toLowerCase().includes("series");

    const cols = isSeries
      ? [
          ["name", "Player"],
          ["year", "Year"],
          ["team", "Team"],
          ["opponent", "Opp"],
          ["seriesCode", "Series"],
          ["GP", "GP"],
          ["PTS", "PTS"],
          ["TS", "TS"],
          ["ORTG", "ORTG"],
        ]
      : [
          ["name", "Player"],
          ["year", "Year"],
          ["team", "Team"],
          ["opponent", "Opp"],
          ["PTS", "PTS"],
          ["TS", "TS"],
          ["ORTG", "ORTG"],
          ["gameId", "Game ID"],
        ];

    tableBox.innerHTML = table(rows.slice(0, 100), cols);
  } catch (err) {
    console.error(err);
    tableBox.innerHTML = `<p class="note">Failed to load leaderboards.</p>`;
  }
}

function initGlobalLeaderboards() {
  const picker = document.getElementById("globalLeaderboardType");
  if (!picker) return;

  picker.addEventListener("input", updateGlobalLeaderboard);
  updateGlobalLeaderboard();
}


loadIndex().catch(err => {
  console.error(err);
  els.indexStatus.textContent = "Failed to load player index";
});


function setActiveSideNav(tab) {
  document.querySelectorAll("#sideNav button").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.tab === tab || btn.dataset.global === tab);
  });
}

function renderSelectedTab(tab) {
  if (!state.current && tab !== "leaderboards") {
    els.view.classList.remove("empty");
    els.view.innerHTML = `<div class="empty-state">Search a player first.</div>`;
    return;
  }

  if (tab === "leaderboards") {
    state.tab = "leaderboards";
    setActiveSideNav("leaderboards");
    if (els.globalPanel) els.globalPanel.classList.add("open");
    els.view.classList.add("empty");
    els.view.innerHTML = `<div class="empty-state">Global Leaderboards</div>`;
    updateGlobalLeaderboard?.();
    return;
  }

  if (els.globalPanel) els.globalPanel.classList.remove("open");
  state.tab = tab;
  setActiveSideNav(tab);
  renderPlayer();
}

document.getElementById("sideNav")?.addEventListener("click", (e) => {
  const btn = e.target.closest("button");
  if (!btn) return;

  if (btn.dataset.global) {
    renderSelectedTab(btn.dataset.global);
    return;
  }

  if (btn.dataset.tab) {
    renderSelectedTab(btn.dataset.tab);
  }
});

/* V2 patch: computed relative four-factor columns */
if (!globalThis.__ptlRelativeFourFactorsPatch) {
  globalThis.__ptlRelativeFourFactorsPatch = true;

  var RELATIVE_FOUR_FACTOR_KEYS = [
    "rTeamEFG",
    "rTeamTS",
    "rTeamFTr",
    "rTeamTOVBetter"
  ];

  try {
    if (Array.isArray(SIX_FACTOR_COL_KEYS)) {
      for (var i = RELATIVE_FOUR_FACTOR_KEYS.length - 1; i >= 0; i--) {
        var k = RELATIVE_FOUR_FACTOR_KEYS[i];
        if (!SIX_FACTOR_COL_KEYS.includes(k)) SIX_FACTOR_COL_KEYS.unshift(k);
      }
    }
  } catch (e) {}

  var __oldPrettyLabelRel = prettyLabel;
  prettyLabel = function (key) {
    var labels = {
      rTeamEFG: "rTeam eFG vs Opp",
      rTeamTS: "rTeam TS vs Opp",
      rTeamFTr: "rTeam FTr vs Opp",
      rTeamTOVBetter: "rTeam TOV% vs Opp"
    };
    return labels[key] || __oldPrettyLabelRel(key);
  };

  function factorNum(row, keys) {
    for (var i = 0; i < keys.length; i++) {
      var v = firstValue(row, keys[i]);
      if (v !== "" && v !== null && v !== undefined) {
        var n = Number(v);
        if (Number.isFinite(n)) return n;
      }
    }
    return null;
  }

  function computedFourFactorValue(row, key) {
    if (!row) return null;

    if (key === "rTeamEFG") {
      var existing = factorNum(row, ["teamEFGvsOppAllowed"]);
      if (existing !== null) return existing;
      var team = factorNum(row, ["teamEFG"]);
      var opp = factorNum(row, ["oppAllowedEFG"]);
      return team !== null && opp !== null ? team - opp : null;
    }

    if (key === "rTeamTS") {
      var existingTS = factorNum(row, ["teamTSvsOppAllowed"]);
      if (existingTS !== null) return existingTS;
      var teamTS = factorNum(row, ["teamTS"]);
      var oppTS = factorNum(row, ["oppAllowedTS"]);
      return teamTS !== null && oppTS !== null ? teamTS - oppTS : null;
    }

    if (key === "rTeamFTr") {
      var existingFTr = factorNum(row, ["teamFTrvsOppAllowed"]);
      if (existingFTr !== null) return existingFTr;
      var teamFTr = factorNum(row, ["teamFTr"]);
      var oppFTr = factorNum(row, ["oppAllowedFTr"]);
      return teamFTr !== null && oppFTr !== null ? teamFTr - oppFTr : null;
    }

    if (key === "rTeamTOVBetter") {
      var teamTOV = factorNum(row, ["teamTOVPct"]);
      var oppTOV = factorNum(row, ["oppAllowedTOVPct"]);
      // For turnovers, lower is better, so positive means team protected the ball better than opponent usually allows.
      return teamTOV !== null && oppTOV !== null ? oppTOV - teamTOV : null;
    }

    return null;
  }

  var __oldHasAnyValueRel = hasAnyValue;
  hasAnyValue = function (rows, key) {
    if (RELATIVE_FOUR_FACTOR_KEYS.includes(key)) {
      return rows.some(function (r) {
        return computedFourFactorValue(r, key) !== null;
      });
    }
    return __oldHasAnyValueRel(rows, key);
  };

  var __oldTableValueRel = tableValue;
  tableValue = function (row, key) {
    if (RELATIVE_FOUR_FACTOR_KEYS.includes(key)) {
      var v = computedFourFactorValue(row, key);
      if (v === null) return "—";
      var sign = v > 0 ? "+" : "";
      return sign + v.toFixed(1);
    }
    return __oldTableValueRel(row, key);
  };
}

/* V2 patch: Adj TS% and rAdj TS% */
if (!globalThis.__ptlAdjTsPatch) {
  globalThis.__ptlAdjTsPatch = true;

  var ADJ_TS_KEYS = ["playerTSCalc", "adjTS", "rAdjTS"];

  try {
    if (Array.isArray(ADVANCED_COL_KEYS)) {
      for (var i = ADJ_TS_KEYS.length - 1; i >= 0; i--) {
        var k = ADJ_TS_KEYS[i];
        if (!ADVANCED_COL_KEYS.includes(k)) ADVANCED_COL_KEYS.unshift(k);
      }
    }
  } catch (e) {}

  function adjTsNumber(row, keys) {
    for (var i = 0; i < keys.length; i++) {
      var v = firstValue(row, keys[i]);
      if (v !== "" && v !== null && v !== undefined) {
        var n = Number(v);
        if (Number.isFinite(n)) return n;
      }
    }
    return null;
  }

  function playerTSFromRow(row) {
    var direct = adjTsNumber(row, ["TS", "TS%", "tsPct", "playerTS", "playerTSPct"]);
    if (direct !== null) return direct;

    var pts = adjTsNumber(row, ["PTS", "points"]);
    var fga = adjTsNumber(row, ["FGA", "fga"]);
    var fta = adjTsNumber(row, ["FTA", "fta"]);

    if (pts === null || fga === null || fta === null) return null;

    var denom = 2 * (fga + 0.44 * fta);
    if (!denom) return null;

    return 100 * pts / denom;
  }

  function leagueAvgTSFromRow(row) {
    return adjTsNumber(row, [
      "leagueAvgTS",
      "leagueTS",
      "lgTS",
      "avgTS",
      "seasonAvgTS",
      "playoffAvgTS"
    ]);
  }

  function oppAllowedTSFromRow(row) {
    return adjTsNumber(row, [
      "oppAllowedTS",
      "opponentAllowedTS",
      "oppTSAllowed",
      "defenseAllowedTS"
    ]);
  }

  function computedAdjTS(row, key) {
    var playerTS = playerTSFromRow(row);
    var oppAllowedTS = oppAllowedTSFromRow(row);
    var leagueTS = leagueAvgTSFromRow(row);

    if (key === "playerTSCalc") return playerTS;

    if (key === "rAdjTS") {
      if (playerTS === null || oppAllowedTS === null) return null;
      return playerTS - oppAllowedTS;
    }

    if (key === "adjTS") {
      if (playerTS === null) return null;

      if (leagueTS !== null && oppAllowedTS !== null) {
        return playerTS + (leagueTS - oppAllowedTS);
      }

      // fallback: if no league TS exists, use player TS.
      // rAdjTS still works as player TS - opponent allowed TS.
      return playerTS;
    }

    return null;
  }

  var __oldPrettyLabelAdjTS = prettyLabel;
  prettyLabel = function (key) {
    var labels = {
      playerTSCalc: "Player TS%",
      adjTS: "Adj TS%",
      rAdjTS: "rAdj TS"
    };
    return labels[key] || __oldPrettyLabelAdjTS(key);
  };

  var __oldHasAnyValueAdjTS = hasAnyValue;
  hasAnyValue = function (rows, key) {
    if (ADJ_TS_KEYS.includes(key)) {
      return rows.some(function (r) {
        return computedAdjTS(r, key) !== null;
      });
    }
    return __oldHasAnyValueAdjTS(rows, key);
  };

  var __oldTableValueAdjTS = tableValue;
  tableValue = function (row, key) {
    if (ADJ_TS_KEYS.includes(key)) {
      var v = computedAdjTS(row, key);
      if (v === null) return "—";

      if (key === "rAdjTS") {
        var sign = v > 0 ? "+" : "";
        return sign + v.toFixed(1);
      }

      return v.toFixed(1);
    }

    return __oldTableValueAdjTS(row, key);
  };
}

/* V2 fix: real Adj TS uses year league TS instead of falling back to Player TS */
if (!globalThis.__ptlRealAdjTsFix) {
  globalThis.__ptlRealAdjTsFix = true;

  state.seasonContext = state.seasonContext || null;

  async function loadSeasonContext() {
    try {
      const res = await fetch("./data/indexes/season-context.json?v=" + Date.now());
      state.seasonContext = await res.json();
    } catch (err) {
      console.warn("No season context loaded for Adj TS", err);
      state.seasonContext = { byYear: {} };
    }
  }

  function realAdjNum(row, keys) {
    for (let i = 0; i < keys.length; i++) {
      const v = firstValue(row, keys[i]);
      if (v !== "" && v !== null && v !== undefined) {
        const n = Number(v);
        if (Number.isFinite(n)) return n;
      }
    }
    return null;
  }

  function realPlayerTS(row) {
    const direct = realAdjNum(row, ["TS", "TS%", "tsPct", "playerTS", "playerTSPct"]);
    if (direct !== null) return direct;

    const pts = realAdjNum(row, ["PTS", "points"]);
    const fga = realAdjNum(row, ["FGA", "fga"]);
    const fta = realAdjNum(row, ["FTA", "fta"]);

    if (pts === null || fga === null || fta === null) return null;

    const denom = 2 * (fga + 0.44 * fta);
    if (!denom) return null;

    return 100 * pts / denom;
  }

  function realOppAllowedTS(row) {
    return realAdjNum(row, [
      "oppAllowedTS",
      "opponentAllowedTS",
      "oppTSAllowed",
      "defenseAllowedTS"
    ]);
  }

  function realLeagueTS(row) {
    const direct = realAdjNum(row, [
      "leagueAvgTS",
      "leagueTS",
      "lgTS",
      "avgTS",
      "seasonAvgTS",
      "playoffAvgTS"
    ]);
    if (direct !== null) return direct;

    const year = rowYear(row);
    const ctx = state.seasonContext?.byYear?.[year];
    return ctx && Number.isFinite(Number(ctx.leagueTS)) ? Number(ctx.leagueTS) : null;
  }

  function realComputedAdjTS(row, key) {
    const playerTS = realPlayerTS(row);
    const oppAllowedTS = realOppAllowedTS(row);
    const leagueTS = realLeagueTS(row);

    if (key === "playerTSCalc") return playerTS;

    if (key === "rAdjTS") {
      if (playerTS === null || oppAllowedTS === null) return null;
      return playerTS - oppAllowedTS;
    }

    if (key === "adjTS") {
      if (playerTS === null || oppAllowedTS === null || leagueTS === null) return null;
      return playerTS + (leagueTS - oppAllowedTS);
    }

    return null;
  }

  const oldHasAnyValueRealAdjTS = hasAnyValue;
  hasAnyValue = function(rows, key) {
    if (["playerTSCalc", "adjTS", "rAdjTS"].includes(key)) {
      return rows.some(r => realComputedAdjTS(r, key) !== null);
    }
    return oldHasAnyValueRealAdjTS(rows, key);
  };

  const oldTableValueRealAdjTS = tableValue;
  tableValue = function(row, key) {
    if (["playerTSCalc", "adjTS", "rAdjTS"].includes(key)) {
      const v = realComputedAdjTS(row, key);
      if (v === null) return "—";

      if (key === "rAdjTS") {
        const sign = v > 0 ? "+" : "";
        return sign + v.toFixed(1);
      }

      return v.toFixed(1);
    }

    return oldTableValueRealAdjTS(row, key);
  };

  const oldLoadIndexPromise = loadIndex;
  loadIndex = async function() {
    await oldLoadIndexPromise();
    await loadSeasonContext();
  };
}

document.addEventListener("input", function(e) {
  if (e.target && (e.target.id === "stretchYear" || e.target.id === "stretchMode")) {
    const start = document.getElementById("stretchStart");
    const end = document.getElementById("stretchEnd");
    if (start) start.dataset.rangeKey = "";
    if (end) end.dataset.rangeKey = "";
  }
});

/* FINAL FIX: prefer real stored Adj TS / rAdj TS, and fix From/To Stretch dropdowns */
if (!globalThis.__ptlFinalAdjTsAndStretchFix) {
  globalThis.__ptlFinalAdjTsAndStretchFix = true;

  function rawField(row, names) {
    if (!row) return null;
    for (const name of names) {
      if (row[name] !== undefined && row[name] !== null && row[name] !== "" && row[name] !== "—") {
        const n = Number(row[name]);
        return Number.isFinite(n) ? n : row[name];
      }
    }
    return null;
  }

  function rawPlayerTS(row) {
    const raw = rawField(row, [
      "playerTS", "playerTSPct", "PlayerTS", "PLAYER_TS",
      "TS", "TS%", "tsPct"
    ]);
    if (raw !== null) return Number(raw);

    const pts = Number(rawField(row, ["PTS", "points"]));
    const fga = Number(rawField(row, ["FGA", "fga"]));
    const fta = Number(rawField(row, ["FTA", "fta"]));

    if (!Number.isFinite(pts) || !Number.isFinite(fga) || !Number.isFinite(fta)) return null;

    const denom = 2 * (fga + 0.44 * fta);
    if (!denom) return null;

    return 100 * pts / denom;
  }

  function rawAdjTS(row) {
    return rawField(row, [
      "adjTS", "AdjTS", "ADJ_TS", "adjustedTS", "AdjustedTS", "ADJUSTED_TS",
      "playerAdjTS", "PlayerAdjTS", "PLAYER_ADJ_TS"
    ]);
  }

  function rawRAdjTS(row) {
    return rawField(row, [
      "rAdjTS", "RAdjTS", "RADJ_TS", "r_adjusted_ts",
      "relativeAdjTS", "RelativeAdjTS",
      "playerRAdjTS", "PlayerRAdjTS", "PLAYER_RADJ_TS",

      // fallback because a lot of the old package may store this as rTS/RTS
      "rTS", "RTS", "rTs"
    ]);
  }

  function finalLeagueTSForRow(row) {
    const year = rowYear(row);
    const ctx = state.seasonContext?.byYear?.[year];

    if (ctx && Number.isFinite(Number(ctx.leagueTS))) {
      return Number(ctx.leagueTS);
    }

    const raw = rawField(row, [
      "leagueAvgTS", "leagueTS", "lgTS", "avgTS", "seasonAvgTS", "playoffAvgTS"
    ]);

    return raw === null ? null : Number(raw);
  }

  function finalAdjTSValue(row, key) {
    const playerTS = rawPlayerTS(row);
    const storedAdj = rawAdjTS(row);
    const storedRAdj = rawRAdjTS(row);
    const leagueTS = finalLeagueTSForRow(row);

    if (key === "playerTSCalc") {
      return playerTS;
    }

    if (key === "rAdjTS") {
      if (storedRAdj !== null && Number.isFinite(Number(storedRAdj))) {
        return Number(storedRAdj);
      }

      if (storedAdj !== null && leagueTS !== null) {
        return Number(storedAdj) - leagueTS;
      }

      if (playerTS !== null && leagueTS !== null) {
        return playerTS - leagueTS;
      }

      return null;
    }

    if (key === "adjTS") {
      if (storedAdj !== null && Number.isFinite(Number(storedAdj))) {
        return Number(storedAdj);
      }

      if (storedRAdj !== null && leagueTS !== null) {
        return leagueTS + Number(storedRAdj);
      }

      // Last fallback: do NOT use opponent-allowed TS here.
      // This prevents the Harden 2015 GSW +12.2 bug.
      return playerTS;
    }

    return null;
  }

  const oldHasAnyValueFinalAdjTS = hasAnyValue;
  hasAnyValue = function(rows, key) {
    if (["playerTSCalc", "adjTS", "rAdjTS"].includes(key)) {
      return rows.some(r => finalAdjTSValue(r, key) !== null);
    }
    return oldHasAnyValueFinalAdjTS(rows, key);
  };

  const oldTableValueFinalAdjTS = tableValue;
  tableValue = function(row, key) {
    if (["playerTSCalc", "adjTS", "rAdjTS"].includes(key)) {
      const v = finalAdjTSValue(row, key);
      if (v === null || v === undefined || Number.isNaN(Number(v))) return "—";

      if (key === "rAdjTS") {
        const n = Number(v);
        return `${n > 0 ? "+" : ""}${n.toFixed(1)}`;
      }

      return Number(v).toFixed(1);
    }

    return oldTableValueFinalAdjTS(row, key);
  };

  function finalStretchRows(mode, year) {
    const rows = mode === "series" ? (state.current?.series || []) : (state.current?.games || []);

    return rows
      .filter(r => String(rowYear(r)) === String(year))
      .slice()
      .sort((a, b) => {
        const ad = String(get(a, ["date", "gameDate", "GAME_DATE", "gameId", "GAME_ID"]) || "");
        const bd = String(get(b, ["date", "gameDate", "GAME_DATE", "gameId", "GAME_ID"]) || "");
        return ad.localeCompare(bd);
      });
  }

  function finalGameLabel(row, i) {
    const date = get(row, ["date", "gameDate", "GAME_DATE", "gameId", "GAME_ID"]) || "No date";
    const team = rowTeam(row);
    const opp = rowOpp(row);
    const pts = tableValue(row, "PTS");
    return `G${i + 1} • ${date} • ${team} vs ${opp} • ${pts} PTS`;
  }

  function finalSeriesLabel(row, i) {
    const y = rowYear(row);
    const team = rowTeam(row);
    const opp = rowOpp(row);
    const code = get(row, ["seriesCode", "series", "round"]) || "";
    const pts = tableValue(row, "PTS");
    return `S${i + 1} • ${y} ${team} vs ${opp}${code ? " • " + code : ""} • ${pts} PTS`;
  }

  function finalPopulateStretchPickers() {
    const year = document.getElementById("stretchYear")?.value || "";
    const mode = document.getElementById("stretchMode")?.value || "games";
    const start = document.getElementById("stretchStart");
    const end = document.getElementById("stretchEnd");

    if (!start || !end || !state.current) return;

    const rows = finalStretchRows(mode, year);

    if (!rows.length) {
      start.innerHTML = `<option value="">No ${mode === "series" ? "series" : "games"} found</option>`;
      end.innerHTML = `<option value="">No ${mode === "series" ? "series" : "games"} found</option>`;
      return;
    }

    const options = rows.map((row, i) => {
      const label = mode === "series" ? finalSeriesLabel(row, i) : finalGameLabel(row, i);
      return `<option value="${i}">${label}</option>`;
    }).join("");

    const oldStart = start.value;
    const oldEnd = end.value;

    start.innerHTML = options;
    end.innerHTML = options;

    start.value = oldStart && Number(oldStart) < rows.length ? oldStart : "0";
    end.value = oldEnd && Number(oldEnd) < rows.length ? oldEnd : String(rows.length - 1);
  }

  function finalMetricNum(row, key) {
    const rendered = tableValue(row, key);
    if (rendered !== "—" && rendered !== null && rendered !== undefined) {
      const n = Number(String(rendered).replace("+", ""));
      if (Number.isFinite(n)) return n;
    }

    const raw = rawField(row, [key]);
    return raw === null ? null : Number(raw);
  }

  function finalAvg(rows, key) {
    const vals = rows.map(r => finalMetricNum(r, key)).filter(v => Number.isFinite(v));
    if (!vals.length) return null;
    return vals.reduce((a, b) => a + b, 0) / vals.length;
  }

  function finalSum(rows, key) {
    const vals = rows.map(r => finalMetricNum(r, key)).filter(v => Number.isFinite(v));
    if (!vals.length) return null;
    return vals.reduce((a, b) => a + b, 0);
  }

  const oldUpdateStretchFinal = updateStretch;
  updateStretch = function() {
    const year = document.getElementById("stretchYear")?.value || "";
    const mode = document.getElementById("stretchMode")?.value || "games";
    const metricKey = document.getElementById("stretchMetric")?.value || "PTS";
    const out = document.getElementById("stretchOutput");

    if (!out || !state.current) return;

    finalPopulateStretchPickers();

    const rows = finalStretchRows(mode, year);
    if (!rows.length) {
      out.innerHTML = `<p class="note">No rows found for that year.</p>`;
      return;
    }

    let startIdx = Number(document.getElementById("stretchStart")?.value || 0);
    let endIdx = Number(document.getElementById("stretchEnd")?.value || rows.length - 1);

    if (startIdx > endIdx) {
      const temp = startIdx;
      startIdx = endIdx;
      endIdx = temp;
    }

    const selected = rows.slice(startIdx, endIdx + 1);
    const signed = metricKey.toLowerCase().includes("radj") || metricKey.toLowerCase().includes("net");

    const avgVal = finalAvg(selected, metricKey);
    const totalPts = finalSum(selected, "PTS");
    const totalMin = finalSum(selected, "MIN");

    const summaryRows = [
      { label: "Start", value: mode === "series" ? finalSeriesLabel(selected[0], startIdx) : finalGameLabel(selected[0], startIdx) },
      { label: "End", value: mode === "series" ? finalSeriesLabel(selected[selected.length - 1], endIdx) : finalGameLabel(selected[selected.length - 1], endIdx) },
      { label: mode === "series" ? "Series Count" : "Game Count", value: selected.length },
      { label: `${metricKey} Avg`, value: avgVal === null ? "—" : `${signed && avgVal > 0 ? "+" : ""}${avgVal.toFixed(1)}` },
      { label: "Total Points", value: totalPts === null ? "—" : totalPts.toFixed(1) },
      { label: "Total Minutes", value: totalMin === null ? "—" : totalMin.toFixed(1) },
    ];

    const detailCols = mode === "series"
      ? [
          ["year", "Year"], ["team", "Team"], ["opponent", "Opp"], ["seriesCode", "Series"],
          ["GP", "GP"], ["MIN", "MIN"], ["PTS", "PTS"], ["REB", "REB"], ["AST", "AST"],
          ["playerTSCalc", "Player TS"], ["adjTS", "Adj TS"], ["rAdjTS", "rAdj TS"],
          ["ORTG", "ORTG"], ["DRTG", "DRTG"], ["adjNET", "Adj NET"]
        ]
      : [
          ["year", "Year"], ["date", "Date"], ["team", "Team"], ["opponent", "Opp"],
          ["MIN", "MIN"], ["PTS", "PTS"], ["REB", "REB"], ["AST", "AST"],
          ["playerTSCalc", "Player TS"], ["adjTS", "Adj TS"], ["rAdjTS", "rAdj TS"],
          ["ORTG", "ORTG"], ["DRTG", "DRTG"], ["adjNET", "Adj NET"], ["gameId", "Game ID"]
        ];

    out.innerHTML = `
      <h3>Selected ${mode === "series" ? "Series" : "Game"} Stretch</h3>
      ${richTable(summaryRows, [["label", "Item"], ["value", "Value"]])}

      <div style="height:14px"></div>

      <h3>Rows Included</h3>
      ${richTable(selected, detailCols)}
    `;
  };

  document.addEventListener("input", function(e) {
    if (!e.target) return;

    if (["stretchYear", "stretchMode"].includes(e.target.id)) {
      setTimeout(() => {
        finalPopulateStretchPickers();
        updateStretch();
      }, 0);
    }

    if (["stretchStart", "stretchEnd", "stretchMetric"].includes(e.target.id)) {
      setTimeout(() => updateStretch(), 0);
    }
  });
}

/* HARD FIX: Adj TS / rAdj TS must come from real stored pipeline fields only */
if (!globalThis.__ptlStopFakeAdjTS) {
  globalThis.__ptlStopFakeAdjTS = true;

  function trueStoredNumber(row, names) {
    if (!row) return null;
    for (const name of names) {
      if (row[name] !== undefined && row[name] !== null && row[name] !== "" && row[name] !== "—") {
        const n = Number(row[name]);
        if (Number.isFinite(n)) return n;
      }
    }
    return null;
  }

  function truePlayerTS(row) {
    const direct = trueStoredNumber(row, [
      "TS", "TS%", "tsPct", "playerTS", "playerTSPct", "PLAYER_TS"
    ]);

    if (direct !== null) return direct;

    const pts = trueStoredNumber(row, ["PTS", "points"]);
    const fga = trueStoredNumber(row, ["FGA", "fga"]);
    const fta = trueStoredNumber(row, ["FTA", "fta"]);

    if (pts === null || fga === null || fta === null) return null;

    const denom = 2 * (fga + 0.44 * fta);
    if (!denom) return null;

    return 100 * pts / denom;
  }

  function trueStoredAdjTS(row) {
    return trueStoredNumber(row, [
      "adjTS",
      "AdjTS",
      "ADJ_TS",
      "adj_ts",
      "adjustedTS",
      "AdjustedTS",
      "ADJUSTED_TS",
      "playerAdjTS",
      "PlayerAdjTS",
      "PLAYER_ADJ_TS"
    ]);
  }

  function trueStoredRAdjTS(row) {
    return trueStoredNumber(row, [
      "rAdjTS",
      "RAdjTS",
      "RADJ_TS",
      "r_adj_ts",
      "radjTS",
      "radj_ts",
      "relativeAdjTS",
      "RelativeAdjTS",
      "PLAYER_RADJ_TS",
      "playerRAdjTS"
    ]);
  }

  function trueAdjTSValue(row, key) {
    if (key === "playerTSCalc") {
      return truePlayerTS(row);
    }

    if (key === "adjTS") {
      return trueStoredAdjTS(row);
    }

    if (key === "rAdjTS") {
      return trueStoredRAdjTS(row);
    }

    return null;
  }

  const oldHasAnyValueStopFakeAdjTS = hasAnyValue;
  hasAnyValue = function(rows, key) {
    if (["playerTSCalc", "adjTS", "rAdjTS"].includes(key)) {
      return rows.some(r => trueAdjTSValue(r, key) !== null);
    }
    return oldHasAnyValueStopFakeAdjTS(rows, key);
  };

  const oldTableValueStopFakeAdjTS = tableValue;
  tableValue = function(row, key) {
    if (["playerTSCalc", "adjTS", "rAdjTS"].includes(key)) {
      const v = trueAdjTSValue(row, key);

      if (v === null || v === undefined || Number.isNaN(Number(v))) return "—";

      if (key === "rAdjTS") {
        return `${v > 0 ? "+" : ""}${v.toFixed(1)}`;
      }

      return v.toFixed(1);
    }

    return oldTableValueStopFakeAdjTS(row, key);
  };
}


/* Clean Stretch Lab event listener */
if (!globalThis.__ptlCleanStretchEvents) {
  globalThis.__ptlCleanStretchEvents = true;
  document.addEventListener("input", function(e) {
    if (!e.target) return;
    if (["stretchYear", "stretchMode", "stretchMetric", "stretchStart", "stretchEnd"].includes(e.target.id)) {
      setTimeout(() => {
        cleanPopulateStretchDropdowns();
        updateStretch();
      }, 0);
    }
  });
}

/* FORCE STRETCH LAB CONTROLLER — final override */
if (!globalThis.__PTL_FORCE_STRETCH_CONTROLLER__) {
  globalThis.__PTL_FORCE_STRETCH_CONTROLLER__ = true;

  function sfGet(row, keys) {
    for (const k of keys) {
      if (row && row[k] !== undefined && row[k] !== null && row[k] !== "" && row[k] !== "—") return row[k];
    }
    return "";
  }

  function sfYear(row) {
    return String(sfGet(row, ["year", "season", "YEAR", "SEASON"]));
  }

  function sfOpp(row) {
    return String(sfGet(row, ["opponent", "opp", "OPP", "Opponent"]));
  }

  function sfRound(row) {
    return String(sfGet(row, ["round", "ROUND", "seriesRound", "series", "seriesCode"]) || "Series");
  }

  function sfDate(row) {
    return String(sfGet(row, ["date", "gameDate", "GAME_DATE", "gameDateText", "gameId", "GAME_ID"]) || "Game");
  }

  function sfVal(row, key) {
    if (typeof tableValue === "function") {
      const v = tableValue(row, key);
      if (v !== undefined && v !== null && v !== "—") return v;
    }
    return sfGet(row, [key]);
  }

  function sfRows() {
    const year = document.getElementById("stretchYear")?.value || "";
    const mode = document.getElementById("stretchMode")?.value || "games";
    const rows = mode === "series" ? (state.current?.series || []) : (state.current?.games || []);

    return rows
      .filter(r => sfYear(r) === String(year))
      .slice()
      .sort((a, b) => sfDate(a).localeCompare(sfDate(b)));
  }

  function sfLabel(row, i) {
    const mode = document.getElementById("stretchMode")?.value || "games";

    if (mode === "series") {
      return `S${i + 1} • ${sfYear(row)} • ${sfRound(row)} • vs ${sfOpp(row)} • ${sfVal(row, "PTS/75")} PTS/75`;
    }

    return `G${i + 1} • ${sfDate(row)} • vs ${sfOpp(row)} • ${sfVal(row, "PTS")} PTS`;
  }

  function sfCurrentKey() {
    const player = state.current?.meta?.slug || state.current?.meta?.name || "";
    const year = document.getElementById("stretchYear")?.value || "";
    const mode = document.getElementById("stretchMode")?.value || "";
    return `${player}|${year}|${mode}`;
  }

  function sfFillDropdowns(force = false) {
    const start = document.getElementById("stretchStart");
    const end = document.getElementById("stretchEnd");

    if (!start || !end || !state.current) return;

    const key = sfCurrentKey();

    if (!force && start.dataset.sfKey === key && end.dataset.sfKey === key && start.options.length && end.options.length) {
      return;
    }

    const rows = sfRows();

    if (!rows.length) {
      start.innerHTML = `<option value="">No rows found</option>`;
      end.innerHTML = `<option value="">No rows found</option>`;
      start.dataset.sfKey = key;
      end.dataset.sfKey = key;
      return;
    }

    const html = rows.map((row, i) => `<option value="${i}">${sfLabel(row, i)}</option>`).join("");

    start.innerHTML = html;
    end.innerHTML = html;

    start.value = "0";
    end.value = String(rows.length - 1);

    start.dataset.sfKey = key;
    end.dataset.sfKey = key;
  }

  function sfNumber(row, key) {
    const v = sfVal(row, key);
    const n = Number(String(v).replace("+", ""));
    return Number.isFinite(n) ? n : null;
  }

  function sfAvg(rows, key) {
    const vals = rows.map(r => sfNumber(r, key)).filter(v => v !== null);
    if (!vals.length) return null;
    return vals.reduce((a, b) => a + b, 0) / vals.length;
  }

  function sfSum(rows, key) {
    const vals = rows.map(r => sfNumber(r, key)).filter(v => v !== null);
    if (!vals.length) return null;
    return vals.reduce((a, b) => a + b, 0);
  }

  function sfFmt(v, signed = false) {
    if (v === null || v === undefined || Number.isNaN(Number(v))) return "—";
    return `${signed && v > 0 ? "+" : ""}${Number(v).toFixed(1)}`;
  }

  renderStretch = function() {
    const allRows = (state.current?.games || []).concat(state.current?.series || []);
    const years = [...new Set(allRows.map(sfYear).filter(Boolean))]
      .sort((a, b) => Number(b) - Number(a));

    const yearOptions = years.map(y => `<option value="${y}">${y}</option>`).join("");

    setTimeout(() => {
      sfFillDropdowns(true);
      updateStretch();
    }, 100);

    return `
      <section class="panel court-section-panel">
        <h3>Stretch Lab</h3>

        <div class="toolbar">
          <select id="stretchYear">${yearOptions}</select>

          <select id="stretchMode">
            <option value="games">Game Stretch</option>
            <option value="series">Series Stretch</option>
          </select>

          <select id="stretchMetric">
            <option value="PTS">Points</option>
            <option value="PTS/75">PTS/75</option>
            <option value="TS%">TS%</option>
            <option value="AdjTS%">AdjTS%</option>
            <option value="rTS">rTS</option>
            <option value="rAdjTS">rAdjTS</option>
            <option value="ORTG">ORTG</option>
            <option value="DRTG">DRTG</option>
            <option value="REB">Rebounds</option>
            <option value="AST">Assists</option>
          </select>
        </div>

        <div class="toolbar">
          <div style="width:100%">
            <div class="note">FROM</div>
            <select id="stretchStart"></select>
          </div>

          <div style="width:100%">
            <div class="note">TO</div>
            <select id="stretchEnd"></select>
          </div>
        </div>

        <p class="note">Pick the exact start and end game/series.</p>

        <div id="stretchOutput" style="margin-top:14px"></div>
      </section>
    `;
  };

  updateStretch = function() {
    const out = document.getElementById("stretchOutput");
    if (!out || !state.current) return;

    sfFillDropdowns(false);

    const rows = sfRows();
    if (!rows.length) {
      out.innerHTML = `<p class="note">No rows found.</p>`;
      return;
    }

    const metric = document.getElementById("stretchMetric")?.value || "PTS";
    const mode = document.getElementById("stretchMode")?.value || "games";

    let startIdx = Number(document.getElementById("stretchStart")?.value || 0);
    let endIdx = Number(document.getElementById("stretchEnd")?.value || rows.length - 1);

    if (startIdx > endIdx) [startIdx, endIdx] = [endIdx, startIdx];

    const selected = rows.slice(startIdx, endIdx + 1);
    const signed = metric.toLowerCase().includes("radj") || metric.toLowerCase().includes("rts") || metric.toLowerCase().includes("net");

    const summary = [
      { label: "From", value: sfLabel(selected[0], startIdx) },
      { label: "To", value: sfLabel(selected[selected.length - 1], endIdx) },
      { label: mode === "series" ? "Series Count" : "Game Count", value: selected.length },
      { label: `${metric} Avg`, value: sfFmt(sfAvg(selected, metric), signed) },
      { label: "Total Points", value: sfFmt(sfSum(selected, "PTS")) },
      { label: "Total Minutes", value: sfFmt(sfSum(selected, "MIN")) },
    ];

    const cols = mode === "series"
      ? [
          ["year", "Year"], ["round", "Round"], ["opponent", "Opp"], ["GAMES", "Games"],
          ["MIN", "MIN"], ["PTS/75", "PTS/75"], ["TS%", "TS%"],
          ["AdjTS%", "AdjTS%"], ["rTS", "rTS"], ["rAdjTS", "rAdjTS"]
        ]
      : [
          ["year", "Year"], ["date", "Date"], ["opponent", "Opp"],
          ["MIN", "MIN"], ["PTS", "PTS"], ["PTS/75", "PTS/75"], ["TS%", "TS%"],
          ["AdjTS%", "AdjTS%"], ["rTS", "rTS"], ["rAdjTS", "rAdjTS"], ["gameId", "Game ID"]
        ];

    out.innerHTML = `
      <h3>Selected ${mode === "series" ? "Series" : "Game"} Stretch</h3>
      ${richTable(summary, [["label", "Item"], ["value", "Value"]])}

      <div style="height:14px"></div>

      <h3>Rows Included</h3>
      ${richTable(selected, cols)}
    `;
  };

  document.addEventListener("change", function(e) {
    if (!e.target) return;

    if (["stretchYear", "stretchMode"].includes(e.target.id)) {
      sfFillDropdowns(true);
      updateStretch();
    }

    if (["stretchStart", "stretchEnd", "stretchMetric"].includes(e.target.id)) {
      updateStretch();
    }
  });

  setInterval(() => {
    const start = document.getElementById("stretchStart");
    const end = document.getElementById("stretchEnd");
    if (start && end && (!start.options.length || !end.options.length || start.value === "" || end.value === "")) {
      sfFillDropdowns(true);
      updateStretch();
    }
  }, 500);
}

/* FINAL Stretch Lab: auto profile stats, no metric picker */
if (!globalThis.__PTL_STRETCH_AUTO_PROFILE__) {
  globalThis.__PTL_STRETCH_AUTO_PROFILE__ = true;

  function apGet(row, keys) {
    for (const k of keys) {
      if (row && row[k] !== undefined && row[k] !== null && row[k] !== "" && row[k] !== "—") return row[k];
    }
    return null;
  }

  function apNum(row, keys) {
    const v = apGet(row, keys);
    if (v === null) return null;
    const n = Number(String(v).replace("+", ""));
    return Number.isFinite(n) ? n : null;
  }

  function apYear(row) {
    return String(apGet(row, ["year", "season", "YEAR", "SEASON"]) || "");
  }

  function apOpp(row) {
    return String(apGet(row, ["opponent", "opp", "OPP", "Opponent"]) || "");
  }

  function apRound(row) {
    return String(apGet(row, ["round", "ROUND", "seriesRound", "series", "seriesCode"]) || "Series");
  }

  function apDate(row) {
    return String(apGet(row, ["date", "gameDate", "GAME_DATE", "gameDateText", "gameId", "GAME_ID"]) || "Game");
  }

  function apRows(mode, year) {
    const rows = mode === "series" ? (state.current?.series || []) : (state.current?.games || []);
    return rows
      .filter(r => apYear(r) === String(year))
      .slice()
      .sort((a, b) => apDate(a).localeCompare(apDate(b)));
  }

  function apLabel(row, i, mode) {
    if (mode === "series") {
      const pp75 = apGet(row, ["PTS/75", "PP75", "ptsPer75"]) ?? "";
      return `S${i + 1} • ${apYear(row)} • ${apRound(row)} • vs ${apOpp(row)} • ${pp75} PTS/75`;
    }

    const pts = apGet(row, ["PTS", "points"]) ?? "";
    return `G${i + 1} • ${apDate(row)} • vs ${apOpp(row)} • ${pts} PTS`;
  }

  function apBuildOptions(mode, year) {
    const rows = apRows(mode, year);
    if (!rows.length) return `<option value="">No rows found</option>`;
    return rows.map((r, i) => `<option value="${i}">${apLabel(r, i, mode)}</option>`).join("");
  }

  function apFillDropdowns(force = false) {
    const year = document.getElementById("stretchYear")?.value || "";
    const mode = document.getElementById("stretchMode")?.value || "games";
    const start = document.getElementById("stretchStart");
    const end = document.getElementById("stretchEnd");
    if (!start || !end) return;

    const key = `${state.current?.meta?.slug || state.current?.meta?.name || ""}|${year}|${mode}`;

    if (!force && start.dataset.apKey === key && end.dataset.apKey === key && start.options.length && end.options.length) {
      return;
    }

    const rows = apRows(mode, year);
    const opts = apBuildOptions(mode, year);

    start.innerHTML = opts;
    end.innerHTML = opts;

    start.value = rows.length ? "0" : "";
    end.value = rows.length ? String(rows.length - 1) : "";

    start.dataset.apKey = key;
    end.dataset.apKey = key;
  }

  function apVals(rows, keys) {
    return rows.map(r => apNum(r, keys)).filter(v => v !== null);
  }

  function apAvg(rows, keys) {
    const vals = apVals(rows, keys);
    if (!vals.length) return null;
    return vals.reduce((a, b) => a + b, 0) / vals.length;
  }

  function apSum(rows, keys) {
    const vals = apVals(rows, keys);
    if (!vals.length) return null;
    return vals.reduce((a, b) => a + b, 0);
  }

  function apFmt(v, signed = false) {
    if (v === null || v === undefined || Number.isNaN(Number(v))) return "—";
    return `${signed && v > 0 ? "+" : ""}${Number(v).toFixed(1)}`;
  }

  function apMetric(rows, key) {
    const count = rows.length || 1;

    if (key === "PPG") {
      const pts = apSum(rows, ["PTS", "points"]);
      return pts === null ? null : pts / count;
    }

    if (key === "PP75") {
      return apAvg(rows, ["PTS/75", "PP75", "ptsPer75"]);
    }

    if (key === "rTS") {
      return apAvg(rows, ["rTS", "RTS", "rTs"]);
    }

    if (key === "rAdjTS") {
      return apAvg(rows, ["rAdjTS", "RADJTS", "RADJ_TS", "RAdjTS"]);
    }

    if (key === "ORTG") {
      return apAvg(rows, ["onORTG", "onORTGStrict", "ORTG", "offRtg", "OFF_RATING"]);
    }

    if (key === "DRTG") {
      return apAvg(rows, ["onDRTG", "onDRTGStrict", "DRTG", "defRtg", "DEF_RATING"]);
    }

    if (key === "NET") {
      const direct = apAvg(rows, ["NET", "netRating", "NET_RATING", "onNET", "onNETStrict"]);
      if (direct !== null) return direct;

      const ortg = apMetric(rows, "ORTG");
      const drtg = apMetric(rows, "DRTG");
      if (ortg === null || drtg === null) return null;
      return ortg - drtg;
    }

    if (key === "rORTG") {
      const direct = apAvg(rows, ["rORTG", "relORTG"]);
      if (direct !== null) return direct;

      const vals = rows.map(r => {
        const ortg = apNum(r, ["onORTG", "onORTGStrict", "ORTG", "offRtg", "OFF_RATING"]);
        const lg = state.seasonContext?.byYear?.[apYear(r)]?.leagueORTG;
        if (ortg === null || lg === undefined || lg === null) return null;
        return ortg - Number(lg);
      }).filter(v => v !== null);

      return vals.length ? vals.reduce((a,b) => a+b, 0) / vals.length : null;
    }

    if (key === "rDRTG") {
      const direct = apAvg(rows, ["rDRTG", "relDRTG"]);
      if (direct !== null) return direct;

      const vals = rows.map(r => {
        const drtg = apNum(r, ["onDRTG", "onDRTGStrict", "DRTG", "defRtg", "DEF_RATING"]);
        const lg = state.seasonContext?.byYear?.[apYear(r)]?.leagueDRTG;
        if (drtg === null || lg === undefined || lg === null) return null;
        return Number(lg) - drtg;
      }).filter(v => v !== null);

      return vals.length ? vals.reduce((a,b) => a+b, 0) / vals.length : null;
    }

    if (key === "rNET") {
      const direct = apAvg(rows, ["rNET", "relNET", "rNet"]);
      if (direct !== null) return direct;

      const rO = apMetric(rows, "rORTG");
      const rD = apMetric(rows, "rDRTG");
      if (rO === null || rD === null) return null;
      return rO + rD;
    }

    return null;
  }

  function apFactorDelta(row, factor) {
    if (factor === "eFG") {
      const own = apNum(row, ["onEFG", "onTeamEFG", "teamEFG", "eFG%", "EFG%", "eFG"]);
      const opp = apNum(row, ["oppAllowedEFG", "oppEFGAllowed", "opponentAllowedEFG"]);
      if (own === null || opp === null) return null;
      return own - opp;
    }

    if (factor === "TOV") {
      const own = apNum(row, ["onTOVPct", "onTeamTOVPct", "teamTOVPct", "TOV%", "TOVPct"]);
      const opp = apNum(row, ["oppAllowedTOVPct", "oppTOVPctAllowed", "opponentAllowedTOVPct"]);
      if (own === null || opp === null) return null;
      return opp - own; // positive = better because lower TOV% is better
    }

    if (factor === "ORB") {
      const own = apNum(row, ["onOREBPct", "onORBPct", "onTeamOREBPct", "teamOREBPct", "teamORBPct", "ORB%", "OREB%"]);
      const opp = apNum(row, ["oppAllowedOREBPct", "oppAllowedORBPct", "oppOREBPctAllowed", "opponentAllowedOREBPct"]);
      if (own === null || opp === null) return null;
      return own - opp;
    }

    if (factor === "FTr") {
      const own = apNum(row, ["onFTr", "onTeamFTr", "teamFTr", "FTr", "FTA_RATE"]);
      const opp = apNum(row, ["oppAllowedFTr", "oppFTrAllowed", "opponentAllowedFTr"]);
      if (own === null || opp === null) return null;
      return own - opp;
    }

    return null;
  }

  function apFactorAvg(rows, factor) {
    const vals = rows.map(r => apFactorDelta(r, factor)).filter(v => v !== null);
    if (!vals.length) return null;
    return vals.reduce((a,b) => a+b, 0) / vals.length;
  }

  renderStretch = function() {
    const allRows = (state.current?.games || []).concat(state.current?.series || []);
    const years = [...new Set(allRows.map(apYear).filter(Boolean))]
      .sort((a, b) => Number(b) - Number(a));

    const year = years[0] || "";
    const mode = "games";

    const yearOptions = years.map(y => `<option value="${y}">${y}</option>`).join("");
    const startOptions = apBuildOptions(mode, year);
    const endOptions = startOptions;

    setTimeout(() => {
      apFillDropdowns(true);
      updateStretch();
    }, 100);

    return `
      <section class="panel court-section-panel">
        <h3>Stretch Lab</h3>

        <div class="toolbar">
          <select id="stretchYear">${yearOptions}</select>

          <select id="stretchMode">
            <option value="games">Game Stretch</option>
            <option value="series">Series Stretch</option>
          </select>
        </div>

        <div class="toolbar">
          <div style="width:100%">
            <div class="note">FROM</div>
            <select id="stretchStart">${startOptions}</select>
          </div>

          <div style="width:100%">
            <div class="note">TO</div>
            <select id="stretchEnd">${endOptions}</select>
          </div>
        </div>

        <p class="note">Stats below update automatically for the selected stretch.</p>

        <div id="stretchOutput" style="margin-top:14px"></div>
      </section>
    `;
  };

  updateStretch = function() {
    const out = document.getElementById("stretchOutput");
    if (!out || !state.current) return;

    apFillDropdowns(false);

    const year = document.getElementById("stretchYear")?.value || "";
    const mode = document.getElementById("stretchMode")?.value || "games";
    const rows = apRows(mode, year);

    if (!rows.length) {
      out.innerHTML = `<p class="note">No rows found for ${year}.</p>`;
      return;
    }

    let startIdx = Number(document.getElementById("stretchStart")?.value || 0);
    let endIdx = Number(document.getElementById("stretchEnd")?.value || rows.length - 1);

    if (startIdx > endIdx) [startIdx, endIdx] = [endIdx, startIdx];

    const selected = rows.slice(startIdx, endIdx + 1);

    const summary = [
      { stat: "From", value: apLabel(selected[0], startIdx, mode) },
      { stat: "To", value: apLabel(selected[selected.length - 1], endIdx, mode) },
      { stat: mode === "series" ? "Series Count" : "Game Count", value: selected.length },

      { stat: "PPG", value: apFmt(apMetric(selected, "PPG")) },
      { stat: "PP/75", value: apFmt(apMetric(selected, "PP75")) },
      { stat: "rTS", value: apFmt(apMetric(selected, "rTS"), true) },
      { stat: "rAdj TS", value: apFmt(apMetric(selected, "rAdjTS"), true) },

      { stat: "rORTG", value: apFmt(apMetric(selected, "rORTG"), true) },
      { stat: "rDRTG", value: apFmt(apMetric(selected, "rDRTG"), true) },
      { stat: "rNET", value: apFmt(apMetric(selected, "rNET"), true) },

      { stat: "Opp-Adj eFG", value: apFmt(apFactorAvg(selected, "eFG"), true) },
      { stat: "Opp-Adj TOV%", value: apFmt(apFactorAvg(selected, "TOV"), true) },
      { stat: "Opp-Adj ORB%", value: apFmt(apFactorAvg(selected, "ORB"), true) },
      { stat: "Opp-Adj FTr", value: apFmt(apFactorAvg(selected, "FTr"), true) },
    ];

    const detailCols = mode === "series"
      ? [
          ["year", "Year"], ["round", "Round"], ["opponent", "Opp"], ["GAMES", "Games"],
          ["MIN", "MIN"], ["PTS", "PTS"], ["PTS/75", "PP/75"], ["TS%", "TS%"],
          ["rTS", "rTS"], ["AdjTS%", "AdjTS%"], ["rAdjTS", "rAdjTS"],
          ["ORTG", "ORTG"], ["DRTG", "DRTG"]
        ]
      : [
          ["year", "Year"], ["date", "Date"], ["opponent", "Opp"],
          ["MIN", "MIN"], ["PTS", "PTS"], ["PTS/75", "PP/75"], ["TS%", "TS%"],
          ["rTS", "rTS"], ["AdjTS%", "AdjTS%"], ["rAdjTS", "rAdjTS"],
          ["ORTG", "ORTG"], ["DRTG", "DRTG"], ["gameId", "Game ID"]
        ];

    out.innerHTML = `
      <h3>Stretch Profile</h3>
      ${richTable(summary, [["stat", "Stat"], ["value", "Value"]])}

      <div style="height:14px"></div>

      <h3>Rows Included</h3>
      ${richTable(selected, detailCols)}
    `;
  };

  document.addEventListener("change", function(e) {
    if (!e.target) return;

    if (["stretchYear", "stretchMode"].includes(e.target.id)) {
      apFillDropdowns(true);
      updateStretch();
    }

    if (["stretchStart", "stretchEnd"].includes(e.target.id)) {
      updateStretch();
    }
  });

  setInterval(() => {
    const start = document.getElementById("stretchStart");
    const end = document.getElementById("stretchEnd");
    if (start && end && (!start.options.length || !end.options.length)) {
      apFillDropdowns(true);
      updateStretch();
    }
  }, 600);
}

/* MULTI-YEAR Stretch Lab — independent final controller */
if (!globalThis.__PTL_MULTIYEAR_STRETCH_LAB__) {
  globalThis.__PTL_MULTIYEAR_STRETCH_LAB__ = true;

  function myGet(row, keys) {
    for (const k of keys) {
      if (row && row[k] !== undefined && row[k] !== null && row[k] !== "" && row[k] !== "—") return row[k];
    }
    return null;
  }

  function myNum(row, keys) {
    const v = myGet(row, keys);
    if (v === null) return null;
    const n = Number(String(v).replace("+", ""));
    return Number.isFinite(n) ? n : null;
  }

  function myYear(row) {
    return String(myGet(row, ["year", "season", "YEAR", "SEASON"]) || "");
  }

  function myOpp(row) {
    return String(myGet(row, ["opponent", "opp", "OPP", "Opponent"]) || "");
  }

  function myRound(row) {
    return String(myGet(row, ["round", "ROUND", "seriesRound", "series", "seriesCode"]) || "Series");
  }

  function myDate(row) {
    return String(myGet(row, ["date", "gameDate", "GAME_DATE", "gameDateText", "gameId", "GAME_ID"]) || "");
  }

  function mySortKey(row, mode) {
    const y = myYear(row);
    const d = myDate(row);
    const r = myRound(row);
    const o = myOpp(row);
    return `${y}|${d}|${r}|${o}`;
  }

  function myAllYears() {
    const rows = (state.current?.games || []).concat(state.current?.series || []);
    return [...new Set(rows.map(myYear).filter(Boolean))]
      .sort((a, b) => Number(b) - Number(a));
  }

  function mySelectedYears() {
    const checked = [...document.querySelectorAll(".stretch-year-toggle:checked")]
      .map(el => String(el.value));

    if (checked.length) return checked;

    const first = myAllYears()[0];
    return first ? [first] : [];
  }

  function myRows(mode) {
    const years = new Set(mySelectedYears());
    const rows = mode === "series" ? (state.current?.series || []) : (state.current?.games || []);

    return rows
      .filter(r => years.has(myYear(r)))
      .slice()
      .sort((a, b) => mySortKey(a, mode).localeCompare(mySortKey(b, mode)));
  }

  function myVal(row, key) {
    if (typeof tableValue === "function") {
      const v = tableValue(row, key);
      if (v !== undefined && v !== null && v !== "—") return v;
    }
    return myGet(row, [key]);
  }

  function myLabel(row, i, mode) {
    if (mode === "series") {
      const pp75 = myVal(row, "PTS/75") ?? "";
      return `S${i + 1} • ${myYear(row)} • ${myRound(row)} • vs ${myOpp(row)} • ${pp75} PP/75`;
    }

    const pts = myVal(row, "PTS") ?? "";
    const date = myDate(row) || "Game";
    return `G${i + 1} • ${myYear(row)} • ${date} • vs ${myOpp(row)} • ${pts} PTS`;
  }

  function myOptions(mode) {
    const rows = myRows(mode);
    if (!rows.length) return `<option value="">No rows found</option>`;
    return rows.map((r, i) => `<option value="${i}">${myLabel(r, i, mode)}</option>`).join("");
  }

  function myFillDropdowns(force = false) {
    const mode = document.getElementById("myStretchMode")?.value || "games";
    const start = document.getElementById("myStretchStart");
    const end = document.getElementById("myStretchEnd");
    if (!start || !end) return;

    const key = `${state.current?.meta?.slug || state.current?.meta?.name || ""}|${mode}|${mySelectedYears().join(",")}`;

    if (!force && start.dataset.key === key && end.dataset.key === key && start.options.length && end.options.length) {
      return;
    }

    const rows = myRows(mode);
    const opts = myOptions(mode);

    start.innerHTML = opts;
    end.innerHTML = opts;

    start.value = rows.length ? "0" : "";
    end.value = rows.length ? String(rows.length - 1) : "";

    start.dataset.key = key;
    end.dataset.key = key;
  }

  function myVals(rows, keys) {
    return rows.map(r => myNum(r, keys)).filter(v => v !== null);
  }

  function myAvg(rows, keys) {
    const vals = myVals(rows, keys);
    if (!vals.length) return null;
    return vals.reduce((a, b) => a + b, 0) / vals.length;
  }

  function mySum(rows, keys) {
    const vals = myVals(rows, keys);
    if (!vals.length) return null;
    return vals.reduce((a, b) => a + b, 0);
  }

  function myFmt(v, signed = false) {
    if (v === null || v === undefined || Number.isNaN(Number(v))) return "—";
    return `${signed && v > 0 ? "+" : ""}${Number(v).toFixed(1)}`;
  }

  function myMetric(rows, key) {
    const count = rows.length || 1;

    if (key === "PPG") {
      const pts = mySum(rows, ["PTS", "points"]);
      return pts === null ? null : pts / count;
    }

    if (key === "PP75") return myAvg(rows, ["PTS/75", "PP75", "ptsPer75"]);
    if (key === "rTS") return myAvg(rows, ["rTS", "RTS", "rTs"]);
    if (key === "rAdjTS") return myAvg(rows, ["rAdjTS", "RADJTS", "RADJ_TS", "RAdjTS"]);

    if (key === "ORTG") return myAvg(rows, ["onORTG", "onORTGStrict", "ORTG", "offRtg", "OFF_RATING"]);
    if (key === "DRTG") return myAvg(rows, ["onDRTG", "onDRTGStrict", "DRTG", "defRtg", "DEF_RATING"]);

    if (key === "NET") {
      const direct = myAvg(rows, ["NET", "netRating", "NET_RATING", "onNET", "onNETStrict"]);
      if (direct !== null) return direct;

      const o = myMetric(rows, "ORTG");
      const d = myMetric(rows, "DRTG");
      return o === null || d === null ? null : o - d;
    }

    if (key === "rORTG") {
      const direct = myAvg(rows, ["rORTG", "relORTG"]);
      if (direct !== null) return direct;

      const vals = rows.map(r => {
        const ortg = myNum(r, ["onORTG", "onORTGStrict", "ORTG", "offRtg", "OFF_RATING"]);
        const lg = state.seasonContext?.byYear?.[myYear(r)]?.leagueORTG;
        return ortg === null || lg === undefined || lg === null ? null : ortg - Number(lg);
      }).filter(v => v !== null);

      return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null;
    }

    if (key === "rDRTG") {
      const direct = myAvg(rows, ["rDRTG", "relDRTG"]);
      if (direct !== null) return direct;

      const vals = rows.map(r => {
        const drtg = myNum(r, ["onDRTG", "onDRTGStrict", "DRTG", "defRtg", "DEF_RATING"]);
        const lg = state.seasonContext?.byYear?.[myYear(r)]?.leagueDRTG;
        return drtg === null || lg === undefined || lg === null ? null : Number(lg) - drtg;
      }).filter(v => v !== null);

      return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null;
    }

    if (key === "rNET") {
      const direct = myAvg(rows, ["rNET", "relNET", "rNet"]);
      if (direct !== null) return direct;

      const ro = myMetric(rows, "rORTG");
      const rd = myMetric(rows, "rDRTG");
      return ro === null || rd === null ? null : ro + rd;
    }

    return null;
  }

  function myFactorDelta(row, factor) {
    if (factor === "eFG") {
      const own = myNum(row, ["onEFG", "onTeamEFG", "teamEFG", "eFG%", "EFG%", "eFG"]);
      const opp = myNum(row, ["oppAllowedEFG", "oppEFGAllowed", "opponentAllowedEFG"]);
      return own === null || opp === null ? null : own - opp;
    }

    if (factor === "TOV") {
      const own = myNum(row, ["onTOVPct", "onTeamTOVPct", "teamTOVPct", "TOV%", "TOVPct"]);
      const opp = myNum(row, ["oppAllowedTOVPct", "oppTOVPctAllowed", "opponentAllowedTOVPct"]);
      return own === null || opp === null ? null : opp - own;
    }

    if (factor === "ORB") {
      const own = myNum(row, ["onOREBPct", "onORBPct", "onTeamOREBPct", "teamOREBPct", "teamORBPct", "ORB%", "OREB%"]);
      const opp = myNum(row, ["oppAllowedOREBPct", "oppAllowedORBPct", "oppOREBPctAllowed", "opponentAllowedOREBPct"]);
      return own === null || opp === null ? null : own - opp;
    }

    if (factor === "FTr") {
      const own = myNum(row, ["onFTr", "onTeamFTr", "teamFTr", "FTr", "FTA_RATE"]);
      const opp = myNum(row, ["oppAllowedFTr", "oppFTrAllowed", "opponentAllowedFTr"]);
      return own === null || opp === null ? null : own - opp;
    }

    return null;
  }

  function myFactorAvg(rows, factor) {
    const vals = rows.map(r => myFactorDelta(r, factor)).filter(v => v !== null);
    if (!vals.length) return null;
    return vals.reduce((a, b) => a + b, 0) / vals.length;
  }

  function myYearTogglesHTML() {
    const years = myAllYears();
    const latest = years[0];

    return `
      <div class="year-toggle-wrap" style="display:flex;flex-wrap:wrap;gap:8px;margin:10px 0 16px">
        ${years.map(y => `
          <label style="display:flex;align-items:center;gap:6px;border:1px solid rgba(255,255,255,.14);border-radius:999px;padding:7px 10px;background:rgba(15,20,35,.75);font-size:12px;letter-spacing:.08em">
            <input class="stretch-year-toggle" type="checkbox" value="${y}" ${y === latest ? "checked" : ""}>
            ${y}
          </label>
        `).join("")}
      </div>
    `;
  }

  renderStretch = function() {
    setTimeout(() => {
      myFillDropdowns(true);
      updateStretch();
    }, 100);

    const defaultOptions = myOptions("games");

    return `
      <section class="panel court-section-panel">
        <h3>Stretch Lab</h3>

        <div class="note">Toggle one or multiple years. Dropdowns combine every selected year.</div>
        ${myYearTogglesHTML()}

        <div class="toolbar">
          <select id="myStretchMode">
            <option value="games">Game Stretch</option>
            <option value="series">Series Stretch</option>
          </select>
        </div>

        <div class="toolbar">
          <div style="width:100%">
            <div class="note">FROM</div>
            <select id="myStretchStart">${defaultOptions}</select>
          </div>

          <div style="width:100%">
            <div class="note">TO</div>
            <select id="myStretchEnd">${defaultOptions}</select>
          </div>
        </div>

        <p class="note">Stats below update automatically for the selected multi-year stretch.</p>

        <div id="stretchOutput" style="margin-top:14px"></div>
      </section>
    `;
  };

  updateStretch = function() {
    const out = document.getElementById("stretchOutput");
    if (!out || !state.current) return;

    myFillDropdowns(false);

    const mode = document.getElementById("myStretchMode")?.value || "games";
    const rows = myRows(mode);

    if (!rows.length) {
      out.innerHTML = `<p class="note">No rows found for the selected years.</p>`;
      return;
    }

    let startIdx = Number(document.getElementById("myStretchStart")?.value || 0);
    let endIdx = Number(document.getElementById("myStretchEnd")?.value || rows.length - 1);

    if (startIdx > endIdx) [startIdx, endIdx] = [endIdx, startIdx];

    const selected = rows.slice(startIdx, endIdx + 1);

    const summary = [
      { stat: "Years", value: mySelectedYears().sort((a,b)=>Number(a)-Number(b)).join(", ") },
      { stat: "From", value: myLabel(selected[0], startIdx, mode) },
      { stat: "To", value: myLabel(selected[selected.length - 1], endIdx, mode) },
      { stat: mode === "series" ? "Series Count" : "Game Count", value: selected.length },

      { stat: "PPG", value: myFmt(myMetric(selected, "PPG")) },
      { stat: "PP/75", value: myFmt(myMetric(selected, "PP75")) },
      { stat: "rTS", value: myFmt(myMetric(selected, "rTS"), true) },
      { stat: "rAdj TS", value: myFmt(myMetric(selected, "rAdjTS"), true) },

      { stat: "rORTG", value: myFmt(myMetric(selected, "rORTG"), true) },
      { stat: "rDRTG", value: myFmt(myMetric(selected, "rDRTG"), true) },
      { stat: "rNET", value: myFmt(myMetric(selected, "rNET"), true) },

      { stat: "Opp-Adj eFG", value: myFmt(myFactorAvg(selected, "eFG"), true) },
      { stat: "Opp-Adj TOV%", value: myFmt(myFactorAvg(selected, "TOV"), true) },
      { stat: "Opp-Adj ORB%", value: myFmt(myFactorAvg(selected, "ORB"), true) },
      { stat: "Opp-Adj FTr", value: myFmt(myFactorAvg(selected, "FTr"), true) },
    ];

    const detailCols = mode === "series"
      ? [
          ["year", "Year"], ["round", "Round"], ["opponent", "Opp"], ["GAMES", "Games"],
          ["MIN", "MIN"], ["PTS", "PTS"], ["PTS/75", "PP/75"], ["TS%", "TS%"],
          ["rTS", "rTS"], ["AdjTS%", "AdjTS%"], ["rAdjTS", "rAdjTS"],
          ["ORTG", "ORTG"], ["DRTG", "DRTG"]
        ]
      : [
          ["year", "Year"], ["date", "Date"], ["opponent", "Opp"],
          ["MIN", "MIN"], ["PTS", "PTS"], ["PTS/75", "PP/75"], ["TS%", "TS%"],
          ["rTS", "rTS"], ["AdjTS%", "AdjTS%"], ["rAdjTS", "rAdjTS"],
          ["ORTG", "ORTG"], ["DRTG", "DRTG"], ["gameId", "Game ID"]
        ];

    out.innerHTML = `
      <h3>Multi-Year Stretch Profile</h3>
      ${richTable(summary, [["stat", "Stat"], ["value", "Value"]])}

      <div style="height:14px"></div>

      <h3>Rows Included</h3>
      ${richTable(selected, detailCols)}
    `;
  };

  document.addEventListener("change", function(e) {
    if (!e.target) return;

    if (e.target.classList.contains("stretch-year-toggle") || e.target.id === "myStretchMode") {
      myFillDropdowns(true);
      updateStretch();
    }

    if (e.target.id === "myStretchStart" || e.target.id === "myStretchEnd") {
      updateStretch();
    }
  });

  setInterval(() => {
    const start = document.getElementById("myStretchStart");
    const end = document.getElementById("myStretchEnd");
    if (start && end && (!start.options.length || !end.options.length)) {
      myFillDropdowns(true);
      updateStretch();
    }
  }, 600);
}

/* CLEAN Game/Series Logs — combined box + impact table */
if (!globalThis.__PTL_CLEAN_LOG_TABLES__) {
  globalThis.__PTL_CLEAN_LOG_TABLES__ = true;

  function clGet(row, keys) {
    for (const k of keys) {
      if (row && row[k] !== undefined && row[k] !== null && row[k] !== "" && row[k] !== "—") return row[k];
    }
    return null;
  }

  function clNum(row, keys) {
    const v = clGet(row, keys);
    if (v === null) return null;
    const n = Number(String(v).replace("+", ""));
    return Number.isFinite(n) ? n : null;
  }

  function clYear(row) {
    return String(clGet(row, ["year", "season", "YEAR", "SEASON"]) || "");
  }

  function clDate(row) {
    return String(clGet(row, ["date", "gameDate", "GAME_DATE", "gameDateText"]) || "");
  }

  function clTeam(row) {
    return String(clGet(row, ["team", "TEAM", "teamAbbr", "TEAM_ABBREVIATION"]) || "");
  }

  function clOpp(row) {
    return String(clGet(row, ["opponent", "opp", "OPP", "Opponent"]) || "");
  }

  function clRound(row) {
    return String(clGet(row, ["round", "ROUND", "seriesRound", "series", "seriesCode"]) || "Playoff Series");
  }

  function clLeague(row, key) {
    const y = clYear(row);
    return state.seasonContext?.byYear?.[y]?.[key] ?? null;
  }

  function clMetric(row, key) {
    if (key === "year") return clYear(row);
    if (key === "date") return clDate(row) || "—";
    if (key === "team") return clTeam(row) || "—";
    if (key === "opp") return clOpp(row) || "—";
    if (key === "round") return clRound(row);

    if (key === "PTS") return clGet(row, ["PTS", "points"]);
    if (key === "PP75") return clGet(row, ["PTS/75", "PP75", "ptsPer75"]);
    if (key === "MIN") return clGet(row, ["MIN", "minutes"]);
    if (key === "REB") return clGet(row, ["REB", "TRB", "rebounds"]);
    if (key === "AST") return clGet(row, ["AST", "assists"]);
    if (key === "TOV") return clGet(row, ["TOV", "TO", "turnovers"]);
    if (key === "FG") return clGet(row, ["FG", "FGM", "fgm"]);
    if (key === "FGA") return clGet(row, ["FGA", "fga"]);
    if (key === "3P") return clGet(row, ["3P", "3PM", "FG3M"]);
    if (key === "GAMES") return clGet(row, ["GAMES", "GP", "games", "gp"]);

    if (key === "TS") return clGet(row, ["TS%", "TS", "tsPct"]);
    if (key === "AdjTS") return clGet(row, ["AdjTS%", "adjTS", "AdjTS", "ADJTS", "ADJ_TS"]);

    if (key === "rTS") return clGet(row, ["rTS", "RTS", "rTs"]);

    if (key === "rAdjTS") {
      return clGet(row, ["rAdjTS", "RADJTS", "RADJ_TS", "RAdjTS"]);
    }

    if (key === "ORTG") return clGet(row, ["onORTG", "onORTGStrict", "ORTG", "offRtg", "OFF_RATING"]);
    if (key === "DRTG") return clGet(row, ["onDRTG", "onDRTGStrict", "DRTG", "defRtg", "DEF_RATING"]);

    if (key === "rORTG") {
      const direct = clNum(row, ["rORTG", "relORTG"]);
      if (direct !== null) return direct;

      const ortg = clNum(row, ["onORTG", "onORTGStrict", "ORTG", "offRtg", "OFF_RATING"]);
      const lg = clLeague(row, "leagueORTG");
      if (ortg === null || lg === null || lg === undefined) return null;
      return ortg - Number(lg);
    }

    if (key === "rDRTG") {
      const direct = clNum(row, ["rDRTG", "relDRTG"]);
      if (direct !== null) return direct;

      const drtg = clNum(row, ["onDRTG", "onDRTGStrict", "DRTG", "defRtg", "DEF_RATING"]);
      const lg = clLeague(row, "leagueDRTG");
      if (drtg === null || lg === null || lg === undefined) return null;

      // positive = better defense
      return Number(lg) - drtg;
    }

    if (key === "rNET") {
      const direct = clNum(row, ["rNET", "relNET", "rNet"]);
      if (direct !== null) return direct;

      const ro = clMetric(row, "rORTG");
      const rd = clMetric(row, "rDRTG");
      if (ro === null || rd === null) return null;
      return Number(ro) + Number(rd);
    }

    return clGet(row, [key]);
  }

  function clFmt(row, key, signed=false) {
    const v = clMetric(row, key);

    if (v === null || v === undefined || v === "" || v === "—") return "—";

    if (["year", "date", "team", "opp", "round"].includes(key)) {
      return String(v);
    }

    const n = Number(String(v).replace("+", ""));

    if (!Number.isFinite(n)) return String(v);

    if (["PTS", "REB", "AST", "TOV", "FG", "FGA", "3P", "GAMES"].includes(key)) {
      return String(Math.round(n * 10) / 10).replace(".0", "");
    }

    return `${signed && n > 0 ? "+" : ""}${n.toFixed(1)}`;
  }

  function clTable(rows, cols) {
    if (!rows.length) return `<p class="note">No rows found.</p>`;

    return `
      <div class="table-wrap">
        <table class="data-table clean-log-table">
          <thead>
            <tr>
              ${cols.map(c => `<th>${c.label}</th>`).join("")}
            </tr>
          </thead>
          <tbody>
            ${rows.map(row => `
              <tr>
                ${cols.map(c => {
                  const txt = clFmt(row, c.key, c.signed);
                  const cls = c.signed && txt !== "—"
                    ? (String(txt).startsWith("+") ? "pos" : "neg")
                    : "";
                  return `<td class="${cls}">${txt}</td>`;
                }).join("")}
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    `;
  }

  function clYears(rows) {
    return [...new Set(rows.map(clYear).filter(Boolean))]
      .sort((a,b) => Number(b) - Number(a));
  }

  const CLEAN_GAME_COLS = [
    { key: "year", label: "YEAR" },
    { key: "date", label: "DATE" },
    { key: "opp", label: "OPP" },

    { key: "PTS", label: "PTS" },
    { key: "PP75", label: "PP/75" },
    { key: "rAdjTS", label: "rADJ TS", signed: true },
    { key: "rTS", label: "rTS", signed: true },
    { key: "rORTG", label: "rORTG", signed: true },
    { key: "rDRTG", label: "rDRTG", signed: true },
    { key: "rNET", label: "rNET", signed: true },

    { key: "MIN", label: "MIN" },
    { key: "REB", label: "REB" },
    { key: "AST", label: "AST" },
    { key: "TOV", label: "TOV" },
    { key: "TS", label: "TS%" },
    { key: "AdjTS", label: "ADJ TS%" },
    { key: "ORTG", label: "ORTG" },
    { key: "DRTG", label: "DRTG" },
    { key: "FG", label: "FG" },
    { key: "FGA", label: "FGA" },
    { key: "3P", label: "3P" },
  ];

  const CLEAN_SERIES_COLS = [
    { key: "year", label: "YEAR" },
    { key: "round", label: "ROUND" },
    { key: "opp", label: "OPP" },
    { key: "GAMES", label: "GAMES" },

    { key: "PTS", label: "PTS" },
    { key: "PP75", label: "PP/75" },
    { key: "rAdjTS", label: "rADJ TS", signed: true },
    { key: "rTS", label: "rTS", signed: true },
    { key: "rORTG", label: "rORTG", signed: true },
    { key: "rDRTG", label: "rDRTG", signed: true },
    { key: "rNET", label: "rNET", signed: true },

    { key: "MIN", label: "MIN" },
    { key: "REB", label: "REB" },
    { key: "AST", label: "AST" },
    { key: "TOV", label: "TOV" },
    { key: "TS", label: "TS%" },
    { key: "AdjTS", label: "ADJ TS%" },
    { key: "ORTG", label: "ORTG" },
    { key: "DRTG", label: "DRTG" },
  ];

  renderGames = function() {
    const rows = state.current?.games || [];
    const years = clYears(rows);
    const yearOpts = [`<option value="all">All years</option>`]
      .concat(years.map(y => `<option value="${y}">${y}</option>`))
      .join("");

    setTimeout(() => updateGamesTable(), 80);

    return `
      <section class="panel court-section-panel">
        <h3>Game Logs</h3>

        <div class="toolbar">
          <select id="cleanGameYear">${yearOpts}</select>
          <input id="cleanGameFilter" placeholder="Filter opponent/team/date..." />
          <select id="cleanGameSort">
            <option value="date">Sort: Date/Game</option>
            <option value="pts">Sort: Points</option>
            <option value="pp75">Sort: PP/75</option>
            <option value="radjts">Sort: rAdj TS</option>
            <option value="rnet">Sort: rNET</option>
          </select>
        </div>

        <p class="note">Clean combined box + impact table. Removed low-priority shooting split columns and game ID.</p>

        <div id="cleanGamesTable"></div>
      </section>
    `;
  };

  updateGamesTable = function() {
    const out = document.getElementById("cleanGamesTable");
    if (!out || !state.current) return;

    const year = document.getElementById("cleanGameYear")?.value || "all";
    const filter = String(document.getElementById("cleanGameFilter")?.value || "").toLowerCase().trim();
    const sort = document.getElementById("cleanGameSort")?.value || "date";

    let rows = (state.current.games || []).slice();

    if (year !== "all") {
      rows = rows.filter(r => clYear(r) === year);
    }

    if (filter) {
      rows = rows.filter(r => {
        const hay = [clYear(r), clDate(r), clTeam(r), clOpp(r)].join(" ").toLowerCase();
        return hay.includes(filter);
      });
    }

    rows.sort((a,b) => {
      if (sort === "pts") return (clNum(b, ["PTS"]) ?? -999) - (clNum(a, ["PTS"]) ?? -999);
      if (sort === "pp75") return (clMetric(b, "PP75") ?? -999) - (clMetric(a, "PP75") ?? -999);
      if (sort === "radjts") return (clMetric(b, "rAdjTS") ?? -999) - (clMetric(a, "rAdjTS") ?? -999);
      if (sort === "rnet") return (clMetric(b, "rNET") ?? -999) - (clMetric(a, "rNET") ?? -999);
      return [clYear(a), clDate(a)].join("|").localeCompare([clYear(b), clDate(b)].join("|"));
    });

    out.innerHTML = clTable(rows, CLEAN_GAME_COLS);
  };

  renderSeries = function() {
    const rows = state.current?.series || [];
    const years = clYears(rows);
    const yearOpts = [`<option value="all">All years</option>`]
      .concat(years.map(y => `<option value="${y}">${y}</option>`))
      .join("");

    setTimeout(() => updateSeriesTable(), 80);

    return `
      <section class="panel court-section-panel">
        <h3>Series Logs</h3>

        <div class="toolbar">
          <select id="cleanSeriesYear">${yearOpts}</select>
          <input id="cleanSeriesFilter" placeholder="Filter opponent/round/team..." />
          <select id="cleanSeriesSort">
            <option value="year">Sort: Year/Round</option>
            <option value="pts">Sort: Points</option>
            <option value="pp75">Sort: PP/75</option>
            <option value="radjts">Sort: rAdj TS</option>
            <option value="rnet">Sort: rNET</option>
          </select>
        </div>

        <p class="note">Clean combined box + impact table. Points and relative impact are prioritized first.</p>

        <div id="cleanSeriesTable"></div>
      </section>
    `;
  };

  updateSeriesTable = function() {
    const out = document.getElementById("cleanSeriesTable");
    if (!out || !state.current) return;

    const year = document.getElementById("cleanSeriesYear")?.value || "all";
    const filter = String(document.getElementById("cleanSeriesFilter")?.value || "").toLowerCase().trim();
    const sort = document.getElementById("cleanSeriesSort")?.value || "year";

    let rows = (state.current.series || []).slice();

    if (year !== "all") {
      rows = rows.filter(r => clYear(r) === year);
    }

    if (filter) {
      rows = rows.filter(r => {
        const hay = [clYear(r), clRound(r), clTeam(r), clOpp(r)].join(" ").toLowerCase();
        return hay.includes(filter);
      });
    }

    rows.sort((a,b) => {
      if (sort === "pts") return (clNum(b, ["PTS"]) ?? -999) - (clNum(a, ["PTS"]) ?? -999);
      if (sort === "pp75") return (clMetric(b, "PP75") ?? -999) - (clMetric(a, "PP75") ?? -999);
      if (sort === "radjts") return (clMetric(b, "rAdjTS") ?? -999) - (clMetric(a, "rAdjTS") ?? -999);
      if (sort === "rnet") return (clMetric(b, "rNET") ?? -999) - (clMetric(a, "rNET") ?? -999);
      return Number(clYear(a)) - Number(clYear(b));
    });

    out.innerHTML = clTable(rows, CLEAN_SERIES_COLS);
  };

  document.addEventListener("input", function(e) {
    if (!e.target) return;
    if (["cleanGameYear", "cleanGameFilter", "cleanGameSort"].includes(e.target.id)) updateGamesTable();
    if (["cleanSeriesYear", "cleanSeriesFilter", "cleanSeriesSort"].includes(e.target.id)) updateSeriesTable();
  });

  document.addEventListener("change", function(e) {
    if (!e.target) return;
    if (["cleanGameYear", "cleanGameSort"].includes(e.target.id)) updateGamesTable();
    if (["cleanSeriesYear", "cleanSeriesSort"].includes(e.target.id)) updateSeriesTable();
  });
}

/* FORCE REAL TRANSLATOR UI — replaces old single-series translator panel */
if (!globalThis.__PTL_FORCE_REAL_TRANSLATOR_UI__) {
  globalThis.__PTL_FORCE_REAL_TRANSLATOR_UI__ = true;

  function rtGet(row, keys) {
    for (const k of keys) {
      if (row && row[k] !== undefined && row[k] !== null && row[k] !== "" && row[k] !== "—") return row[k];
    }
    return null;
  }

  function rtNum(row, keys) {
    const v = rtGet(row, keys);
    if (v === null) return null;
    const n = Number(String(v).replace("+", ""));
    return Number.isFinite(n) ? n : null;
  }

  function rtYear(row) {
    return String(rtGet(row, ["year", "season", "YEAR", "SEASON"]) || "");
  }

  function rtTeam(row) {
    return String(rtGet(row, ["team", "TEAM", "teamAbbr", "TEAM_ABBREVIATION"]) || "");
  }

  function rtOpp(row) {
    return String(rtGet(row, ["opponent", "opp", "OPP", "Opponent"]) || "");
  }

  function rtRound(row) {
    return String(rtGet(row, ["round", "ROUND", "seriesRound", "series", "seriesCode"]) || "Playoff Series");
  }

  function rtGP(row) {
    return rtNum(row, ["GAMES", "GP", "games", "gp"]) || 0;
  }

  function rtLeague(row, key) {
    return state.seasonContext?.byYear?.[rtYear(row)]?.[key] ?? null;
  }

  function rtMetric(row, key) {
    if (key === "rORTG") {
      const direct = rtNum(row, ["rORTG", "relORTG"]);
      if (direct !== null) return direct;

      const ortg = rtNum(row, ["onORTG", "onORTGStrict", "ORTG", "offRtg", "OFF_RATING"]);
      const lg = rtLeague(row, "leagueORTG");
      return ortg === null || lg === null || lg === undefined ? null : ortg - Number(lg);
    }

    if (key === "rDRTG") {
      const direct = rtNum(row, ["rDRTG", "relDRTG"]);
      if (direct !== null) return direct;

      const drtg = rtNum(row, ["onDRTG", "onDRTGStrict", "DRTG", "defRtg", "DEF_RATING"]);
      const lg = rtLeague(row, "leagueDRTG");
      return drtg === null || lg === null || lg === undefined ? null : Number(lg) - drtg;
    }

    if (key === "rNET") {
      const direct = rtNum(row, ["rNET", "relNET", "rNet"]);
      if (direct !== null) return direct;

      const ro = rtMetric(row, "rORTG");
      const rd = rtMetric(row, "rDRTG");
      return ro === null || rd === null ? null : ro + rd;
    }

    return null;
  }

  function rtSeriesKey(row) {
    return [rtYear(row), rtTeam(row), rtOpp(row), rtRound(row)].join("|");
  }

  function rtGamesForSeries(s) {
    const exact = (state.current?.games || []).filter(g => rtSeriesKey(g) === rtSeriesKey(s));
    if (exact.length) return exact;

    return (state.current?.games || []).filter(g =>
      rtYear(g) === rtYear(s) &&
      rtOpp(g) === rtOpp(s) &&
      (!rtTeam(s) || rtTeam(g) === rtTeam(s))
    );
  }

  function rtAvg(vals) {
    const good = vals.filter(v => v !== null && Number.isFinite(v));
    return good.length ? good.reduce((a,b)=>a+b,0) / good.length : null;
  }

  function rtFmt(v, signed=false) {
    if (v === null || v === undefined || Number.isNaN(Number(v))) return "—";
    return `${signed && v > 0 ? "+" : ""}${Number(v).toFixed(1)}`;
  }

  function rtTranslated(gameVals, seriesVal, threshold, cushion) {
    const vals = gameVals.filter(v => v !== null && Number.isFinite(v));
    if (!vals.length) return false;

    const hits = vals.filter(v => v >= threshold).length;
    const majority = Math.floor(vals.length / 2) + 1;

    if (hits >= majority) return true;

    if (vals.length % 2 === 0 && hits === vals.length / 2) {
      return seriesVal !== null && seriesVal >= threshold - cushion;
    }

    return false;
  }

  function rtBuild() {
    const from = Number(document.getElementById("rt2From")?.value || 2001);
    const to = Number(document.getElementById("rt2To")?.value || 2026);
    const offT = Number(document.getElementById("rt2Off")?.value || 3);
    const defT = Number(document.getElementById("rt2Def")?.value || 5);
    const netT = Number(document.getElementById("rt2Net")?.value || 4);
    const cushion = Number(document.getElementById("rt2Cushion")?.value || 0.2);
    const minGames = Number(document.getElementById("rt2MinGames")?.value || 3);

    const series = (state.current?.series || [])
      .filter(s => {
        const y = Number(rtYear(s));
        const gp = rtGP(s);
        return y >= from && y <= to && gp >= minGames;
      })
      .sort((a,b) => Number(rtYear(a)) - Number(rtYear(b)));

    const rows = series.map(s => {
      const games = rtGamesForSeries(s);

      const gOff = games.map(g => rtMetric(g, "rORTG"));
      const gDef = games.map(g => rtMetric(g, "rDRTG"));
      const gNet = games.map(g => rtMetric(g, "rNET"));

      const sOff = rtMetric(s, "rORTG") ?? rtAvg(gOff);
      const sDef = rtMetric(s, "rDRTG") ?? rtAvg(gDef);
      const sNet = rtMetric(s, "rNET") ?? rtAvg(gNet);

      const off = rtTranslated(gOff, sOff, offT, cushion);
      const def = rtTranslated(gDef, sDef, defT, cushion);
      const net = rtTranslated(gNet, sNet, netT, cushion);

      return {
        year: rtYear(s),
        round: rtRound(s),
        opp: rtOpp(s),
        games: rtGP(s) || games.length,
        rORTG: sOff,
        rDRTG: sDef,
        rNET: sNet,
        offHits: gOff.filter(v => v !== null && v >= offT).length + "/" + gOff.filter(v => v !== null).length,
        defHits: gDef.filter(v => v !== null && v >= defT).length + "/" + gDef.filter(v => v !== null).length,
        netHits: gNet.filter(v => v !== null && v >= netT).length + "/" + gNet.filter(v => v !== null).length,
        off,
        def,
        net,
        all3: off && def && net
      };
    });

    return { rows, from, to, offT, defT, netT, cushion, minGames };
  }

  function rtCard(label, value, note) {
    return `
      <div class="stat-card">
        <div class="label">${label}</div>
        <div class="value">${value}</div>
        <p class="note">${note}</p>
      </div>
    `;
  }

  function rtRenderOutput() {
    const out = document.getElementById("rt2Output");
    if (!out) return;

    const { rows, from, to, offT, defT, netT, cushion, minGames } = rtBuild();
    const total = rows.length;

    const off = rows.filter(r => r.off).length;
    const def = rows.filter(r => r.def).length;
    const net = rows.filter(r => r.net).length;
    const all3 = rows.filter(r => r.all3).length;

    const tableRows = rows.map(r => ({
      year: r.year,
      round: r.round,
      opp: r.opp,
      games: r.games,
      rORTG: rtFmt(r.rORTG, true),
      rDRTG: rtFmt(r.rDRTG, true),
      rNET: rtFmt(r.rNET, true),
      offHits: r.offHits,
      defHits: r.defHits,
      netHits: r.netHits,
      off: r.off ? "YES" : "NO",
      def: r.def ? "YES" : "NO",
      net: r.net ? "YES" : "NO",
      all3: r.all3 ? "YES" : "NO",
    }));

    out.innerHTML = `
      <div class="stat-grid">
        ${rtCard("OFFENSE TRANSLATES", `${off}/${total}`, `${from}–${to}: rORTG ≥ +${offT}. Cushion: ${cushion}.`)}
        ${rtCard("DEFENSE TRANSLATES", `${def}/${total}`, `${from}–${to}: rDRTG ≥ +${defT}. Positive is better.`)}
        ${rtCard("NET TRANSLATES", `${net}/${total}`, `${from}–${to}: rNET ≥ +${netT}.`)}
        ${rtCard("TWO-WAY / ALL 3", `${all3}/${total}`, `All 3 translated in ${all3}/${total} series. Min games: ${minGames}.`)}
      </div>

      <div style="height:14px"></div>

      <h3>Series Breakdown</h3>
      ${richTable(tableRows, [
        ["year", "Year"],
        ["round", "Round"],
        ["opp", "Opp"],
        ["games", "Games"],
        ["rORTG", "rORTG"],
        ["rDRTG", "rDRTG"],
        ["rNET", "rNET"],
        ["offHits", "Off Games"],
        ["defHits", "Def Games"],
        ["netHits", "Net Games"],
        ["off", "Off"],
        ["def", "Def"],
        ["net", "Net"],
        ["all3", "All 3"],
      ])}
    `;
  }

  function rtMountPanel() {
    const panels = [...document.querySelectorAll("section.panel, .court-section-panel")];
    const panel = panels.find(sec => {
      const h = sec.querySelector("h3");
      return h && h.textContent.trim().toLowerCase().includes("series translator");
    });

    if (!panel || !state.current) return;

    const slug = state.current?.meta?.slug || state.current?.meta?.name || "";
    if (panel.dataset.realTranslatorMounted === slug) return;

    const years = [...new Set((state.current.series || []).map(rtYear).filter(Boolean))]
      .sort((a,b) => Number(a) - Number(b));

    const minY = years[0] || "2001";
    const maxY = years[years.length - 1] || "2026";

    panel.dataset.realTranslatorMounted = slug;
    panel.innerHTML = `
      <h3>Series Translation Consistency</h3>
      <p class="note">
        Counts translation from game-by-game impact inside each series. Majority of games hitting the threshold counts automatically.
        Exactly half only counts when the series average is close enough to the threshold.
      </p>

      <div class="toolbar">
        <label class="note">From <input id="rt2From" type="number" value="${minY}" style="width:90px"></label>
        <label class="note">To <input id="rt2To" type="number" value="${maxY}" style="width:90px"></label>
        <label class="note">rORTG ≥ <input id="rt2Off" type="number" value="3" step="0.1" style="width:90px"></label>
        <label class="note">rDRTG ≥ <input id="rt2Def" type="number" value="5" step="0.1" style="width:90px"></label>
        <label class="note">rNET ≥ <input id="rt2Net" type="number" value="4" step="0.1" style="width:90px"></label>
        <label class="note">Cushion <input id="rt2Cushion" type="number" value="0.2" step="0.1" style="width:90px"></label>
        <label class="note">Min Games <input id="rt2MinGames" type="number" value="3" step="1" style="width:90px"></label>
      </div>

      <div id="rt2Output"></div>
    `;

    rtRenderOutput();
  }

  document.addEventListener("input", function(e) {
    if (!e.target) return;
    if (["rt2From", "rt2To", "rt2Off", "rt2Def", "rt2Net", "rt2Cushion", "rt2MinGames"].includes(e.target.id)) {
      rtRenderOutput();
    }
  });

  document.addEventListener("click", function() {
    setTimeout(rtMountPanel, 80);
  });

  setInterval(rtMountPanel, 500);
}

/* Translator upgrade: add rAdj TS efficiency translation */
if (!globalThis.__PTL_TRANSLATOR_RADJTS__) {
  globalThis.__PTL_TRANSLATOR_RADJTS__ = true;

  if (typeof __ptlRTMetric === "function") {
    const oldRTMetricForAdjTS = __ptlRTMetric;

    __ptlRTMetric = function(row, key) {
      if (key === "rAdjTS") {
        const direct = __ptlRTNum(row, [
          "rAdjTS",
          "RAdjTS",
          "RADJTS",
          "RADJ_TS",
          "r_adj_ts",
          "playerRAdjTS",
          "PLAYER_RADJ_TS"
        ]);

        if (direct !== null) return direct;
        return null;
      }

      return oldRTMetricForAdjTS(row, key);
    };
  }

  if (typeof __ptlRTBuild === "function") {
    __ptlRTBuild = function() {
      const from = Number(document.getElementById("rtFrom")?.value || 2001);
      const to = Number(document.getElementById("rtTo")?.value || 2026);
      const offT = Number(document.getElementById("rtOff")?.value || 3);
      const defT = Number(document.getElementById("rtDef")?.value || 5);
      const netT = Number(document.getElementById("rtNet")?.value || 4);
      const effT = Number(document.getElementById("rtEff")?.value || 2);
      const cushion = Number(document.getElementById("rtCushion")?.value || 0.2);
      const minGames = Number(document.getElementById("rtMinGames")?.value || 3);

      const series = (state.current?.series || [])
        .filter(s => {
          const y = Number(__ptlRTYear(s));
          const gp = __ptlRTGames(s);
          return y >= from && y <= to && gp >= minGames;
        })
        .sort((a, b) => Number(__ptlRTYear(a)) - Number(__ptlRTYear(b)));

      const rows = series.map(s => {
        const games = __ptlRTGamesForSeries(s);

        const gOff = games.map(g => __ptlRTMetric(g, "rORTG"));
        const gDef = games.map(g => __ptlRTMetric(g, "rDRTG"));
        const gNet = games.map(g => __ptlRTMetric(g, "rNET"));
        const gEff = games.map(g => __ptlRTMetric(g, "rAdjTS"));

        const sOff = __ptlRTMetric(s, "rORTG") ?? __ptlRTAvg(gOff);
        const sDef = __ptlRTMetric(s, "rDRTG") ?? __ptlRTAvg(gDef);
        const sNet = __ptlRTMetric(s, "rNET") ?? __ptlRTAvg(gNet);
        const sEff = __ptlRTMetric(s, "rAdjTS") ?? __ptlRTAvg(gEff);

        const off = __ptlRTTranslated(gOff, sOff, offT, cushion);
        const def = __ptlRTTranslated(gDef, sDef, defT, cushion);
        const net = __ptlRTTranslated(gNet, sNet, netT, cushion);
        const eff = __ptlRTTranslated(gEff, sEff, effT, cushion);

        return {
          year: __ptlRTYear(s),
          round: __ptlRTRound(s),
          opp: __ptlRTOpp(s),
          games: __ptlRTGames(s) || games.length,

          rORTG: sOff,
          rDRTG: sDef,
          rNET: sNet,
          rAdjTS: sEff,

          offHits: gOff.filter(v => v !== null && v >= offT).length + "/" + gOff.filter(v => v !== null).length,
          defHits: gDef.filter(v => v !== null && v >= defT).length + "/" + gDef.filter(v => v !== null).length,
          netHits: gNet.filter(v => v !== null && v >= netT).length + "/" + gNet.filter(v => v !== null).length,
          effHits: gEff.filter(v => v !== null && v >= effT).length + "/" + gEff.filter(v => v !== null).length,

          off,
          def,
          net,
          eff,
          all3: off && def && net,
          all4: off && def && net && eff,
        };
      });

      return { rows, from, to, offT, defT, netT, effT, cushion, minGames };
    };
  }

  if (typeof __ptlRTUpdate === "function") {
    __ptlRTUpdate = function() {
      const out = document.getElementById("rtOutput");
      if (!out || !state.current) return;

      const { rows, from, to, offT, defT, netT, effT, cushion, minGames } = __ptlRTBuild();
      const total = rows.length;

      const offCount = rows.filter(r => r.off).length;
      const defCount = rows.filter(r => r.def).length;
      const netCount = rows.filter(r => r.net).length;
      const effCount = rows.filter(r => r.eff).length;
      const all3Count = rows.filter(r => r.all3).length;
      const all4Count = rows.filter(r => r.all4).length;

      const tableRows = rows.map(r => ({
        year: r.year,
        round: r.round,
        opp: r.opp,
        games: r.games,

        rAdjTS: __ptlRTFmt(r.rAdjTS, true),
        rORTG: __ptlRTFmt(r.rORTG, true),
        rDRTG: __ptlRTFmt(r.rDRTG, true),
        rNET: __ptlRTFmt(r.rNET, true),

        effHits: r.effHits,
        offHits: r.offHits,
        defHits: r.defHits,
        netHits: r.netHits,

        eff: r.eff ? "YES" : "NO",
        off: r.off ? "YES" : "NO",
        def: r.def ? "YES" : "NO",
        net: r.net ? "YES" : "NO",
        all3: r.all3 ? "YES" : "NO",
        all4: r.all4 ? "YES" : "NO",
      }));

      out.innerHTML = `
        <div class="stat-grid">
          ${__ptlRTCard("EFFICIENCY TRANSLATES", `${effCount}/${total}`, `${from}–${to}: rAdj TS ≥ +${effT}. Uses verified AdjTS where available.`)}
          ${__ptlRTCard("OFFENSE TRANSLATES", `${offCount}/${total}`, `${from}–${to}: rORTG ≥ +${offT}. Cushion: ${cushion}.`)}
          ${__ptlRTCard("DEFENSE TRANSLATES", `${defCount}/${total}`, `${from}–${to}: rDRTG ≥ +${defT}. Positive is better.`)}
          ${__ptlRTCard("NET TRANSLATES", `${netCount}/${total}`, `${from}–${to}: rNET ≥ +${netT}.`)}
          ${__ptlRTCard("TWO-WAY / ALL 3", `${all3Count}/${total}`, `Offense, defense, and net translated. Min games: ${minGames}.`)}
          ${__ptlRTCard("ALL 4 INCLUDING EFF", `${all4Count}/${total}`, `Efficiency + offense + defense + net.`)}
        </div>

        <div style="height:14px"></div>

        <h3>Series Breakdown</h3>
        ${richTable(tableRows, [
          ["year", "Year"],
          ["round", "Round"],
          ["opp", "Opp"],
          ["games", "Games"],

          ["rAdjTS", "rAdj TS"],
          ["rORTG", "rORTG"],
          ["rDRTG", "rDRTG"],
          ["rNET", "rNET"],

          ["effHits", "Eff Games"],
          ["offHits", "Off Games"],
          ["defHits", "Def Games"],
          ["netHits", "Net Games"],

          ["eff", "Eff"],
          ["off", "Off"],
          ["def", "Def"],
          ["net", "Net"],
          ["all3", "All 3"],
          ["all4", "All 4"],
        ])}
      `;
    };
  }

  if (typeof __ptlRTRenderTool === "function") {
    __ptlRTRenderTool = function() {
      const years = [...new Set((state.current?.series || []).map(__ptlRTYear).filter(Boolean))]
        .sort((a, b) => Number(a) - Number(b));

      const minY = years[0] || "2001";
      const maxY = years[years.length - 1] || "2026";

      setTimeout(() => __ptlRTUpdate(), 80);

      return `
        <section class="panel court-section-panel">
          <h3>Series Translation Consistency</h3>
          <p class="note">
            Counts translation from game-by-game impact inside each series.
            Efficiency uses rAdj TS, so 2025–2026 will show blank until AdjTS is built for those seasons.
          </p>

          <div class="toolbar">
            <label class="note">From <input id="rtFrom" type="number" value="${minY}" style="width:90px"></label>
            <label class="note">To <input id="rtTo" type="number" value="${maxY}" style="width:90px"></label>
            <label class="note">rAdj TS ≥ <input id="rtEff" type="number" value="2" step="0.1" style="width:90px"></label>
            <label class="note">rORTG ≥ <input id="rtOff" type="number" value="3" step="0.1" style="width:90px"></label>
            <label class="note">rDRTG ≥ <input id="rtDef" type="number" value="5" step="0.1" style="width:90px"></label>
            <label class="note">rNET ≥ <input id="rtNet" type="number" value="4" step="0.1" style="width:90px"></label>
            <label class="note">Cushion <input id="rtCushion" type="number" value="0.2" step="0.1" style="width:90px"></label>
            <label class="note">Min Games <input id="rtMinGames" type="number" value="3" step="1" style="width:90px"></label>
          </div>

          <div id="rtOutput"></div>
        </section>
      `;
    };
  }

  document.addEventListener("input", function(e) {
    if (!e.target) return;
    if (["rtFrom", "rtTo", "rtEff", "rtOff", "rtDef", "rtNet", "rtCushion", "rtMinGames"].includes(e.target.id)) {
      __ptlRTUpdate();
    }
  });
}

/* Game Log upgrade: show season ON/OFF four factors inside game rows */
if (!globalThis.__PTL_GAMELOG_ON4F__) {
  globalThis.__PTL_GAMELOG_ON4F__ = true;

  function __ptlGLGet(row, keys) {
    for (const k of keys) {
      if (row && row[k] !== undefined && row[k] !== null && row[k] !== "" && row[k] !== "—") return row[k];
    }
    return null;
  }

  function __ptlGLNum(row, keys) {
    const v = __ptlGLGet(row, keys);
    if (v === null) return null;
    const n = Number(String(v).replace("%", ""));
    return Number.isFinite(n) ? n : null;
  }

  function __ptlGLYear(row) {
    const y = __ptlGLGet(row, ["year", "season", "SEASON", "YEAR"]);
    if (typeof y === "string" && y.includes("-")) {
      const n = Number(y.slice(0, 4));
      return Number.isFinite(n) ? String(n + 1) : String(y);
    }
    return y === null ? "" : String(y);
  }

  function __ptlGLTeam(row) {
    return String(__ptlGLGet(row, ["team", "TEAM", "teamAbbr", "TEAM_ABBREVIATION"]) || "");
  }

  function __ptlGLOpp(row) {
    return __ptlGLGet(row, ["opponent", "opp", "OPP", "Opponent", "OPPONENT"]) || "—";
  }

  function __ptlGLDate(row) {
    return __ptlGLGet(row, ["date", "gameDate", "GAME_DATE", "matchupDate"]) || "—";
  }

  function __ptlGLFmt(v, plus = false) {
    if (v === null || v === undefined || v === "" || v === "—") return "—";
    const n = Number(v);
    if (!Number.isFinite(n)) return String(v);
    const out = Math.abs(n) >= 100 ? n.toFixed(0) : n.toFixed(1);
    return plus && n > 0 ? `+${out}` : out;
  }

  function __ptlGLDelta(on, off) {
    if (on === null || off === null || on === undefined || off === undefined) return "—";
    const n = Number(on) - Number(off);
    if (!Number.isFinite(n)) return "—";
    return n > 0 ? `+${n.toFixed(1)}` : n.toFixed(1);
  }

  function __ptlGLFourFactorsForGame(game) {
    const meta = state.current?.meta || {};
    const year = __ptlGLYear(game);
    const team = __ptlGLTeam(game);

    const byTeam = meta.onCourtFourFactorsByTeam?.[year] || {};
    if (team && byTeam[team]) return byTeam[team];

    return meta.onCourtFourFactors?.[year] || null;
  }

  function __ptlGLGameRows() {
    const games = Array.isArray(state.current?.games) ? state.current.games : [];
    const yearFilter = document.getElementById("gameLogYear")?.value || "ALL";

    return games
      .filter(g => yearFilter === "ALL" || __ptlGLYear(g) === yearFilter)
      .map(g => {
        const ff = __ptlGLFourFactorsForGame(g);

        return {
          year: __ptlGLYear(g),
          date: __ptlGLDate(g),
          team: __ptlGLTeam(g) || "—",
          opp: __ptlGLOpp(g),

          pts: __ptlGLFmt(__ptlGLNum(g, ["PTS", "pts", "points"])),
          pp75: __ptlGLFmt(__ptlGLNum(g, ["PP75", "pp75", "PTS_75", "pointsPer75"])),
          rAdjTS: __ptlGLFmt(__ptlGLNum(g, ["rAdjTS", "RAdjTS", "RADJTS", "RADJ_TS"]), true),
          rTS: __ptlGLFmt(__ptlGLNum(g, ["rTS", "RTS", "r_ts"]), true),
          rORTG: __ptlGLFmt(__ptlGLNum(g, ["rORTG", "RORTG", "r_off_rating"]), true),
          rDRTG: __ptlGLFmt(__ptlGLNum(g, ["rDRTG", "RDRTG", "r_def_rating"]), true),
          rNET: __ptlGLFmt(__ptlGLNum(g, ["rNET", "RNET", "r_net_rating"]), true),
          min: __ptlGLFmt(__ptlGLNum(g, ["MIN", "min", "minutes"])),

          onMin: ff ? __ptlGLFmt(ff.onMinutes) : "—",
          offMin: ff ? __ptlGLFmt(ff.offMinutes) : "—",

          teamEFGOn: ff ? __ptlGLFmt(ff.onTeamEFG) : "—",
          teamEFGOff: ff ? __ptlGLFmt(ff.onTeamEFGOff) : "—",
          teamEFGDelta: ff ? __ptlGLDelta(ff.onTeamEFG, ff.onTeamEFGOff) : "—",

          teamORBOn: ff ? __ptlGLFmt(ff.onTeamOREBPct) : "—",
          teamORBOff: ff ? __ptlGLFmt(ff.onTeamOREBPctOff) : "—",
          teamORBDelta: ff ? __ptlGLDelta(ff.onTeamOREBPct, ff.onTeamOREBPctOff) : "—",

          teamFTROn: ff ? __ptlGLFmt(ff.onTeamFTr) : "—",
          teamFTROff: ff ? __ptlGLFmt(ff.onTeamFTrOff) : "—",
          teamFTRDelta: ff ? __ptlGLDelta(ff.onTeamFTr, ff.onTeamFTrOff) : "—",

          teamTOVOn: ff ? __ptlGLFmt(ff.onTeamTOVPct) : "—",
          teamTOVOff: ff ? __ptlGLFmt(ff.onTeamTOVPctOff) : "—",
          teamTOVDelta: ff ? __ptlGLDelta(ff.onTeamTOVPct, ff.onTeamTOVPctOff) : "—",

          oppEFGOn: ff ? __ptlGLFmt(ff.onOppEFG) : "—",
          oppEFGOff: ff ? __ptlGLFmt(ff.onOppEFGOff) : "—",
          oppEFGDelta: ff ? __ptlGLDelta(ff.onOppEFG, ff.onOppEFGOff) : "—",

          oppORBOn: ff ? __ptlGLFmt(ff.onOppOREBPct) : "—",
          oppORBOff: ff ? __ptlGLFmt(ff.onOppOREBPctOff) : "—",
          oppORBDelta: ff ? __ptlGLDelta(ff.onOppOREBPct, ff.onOppOREBPctOff) : "—",

          oppFTROn: ff ? __ptlGLFmt(ff.onOppFTr) : "—",
          oppFTROff: ff ? __ptlGLFmt(ff.onOppFTrOff) : "—",
          oppFTRDelta: ff ? __ptlGLDelta(ff.onOppFTr, ff.onOppFTrOff) : "—",

          oppTOVOn: ff ? __ptlGLFmt(ff.onOppTOVPct) : "—",
          oppTOVOff: ff ? __ptlGLFmt(ff.onOppTOVPctOff) : "—",
          oppTOVDelta: ff ? __ptlGLDelta(ff.onOppTOVPct, ff.onOppTOVPctOff) : "—",
        };
      });
  }

  renderGames = function() {
    const games = Array.isArray(state.current?.games) ? state.current.games : [];
    const years = [...new Set(games.map(__ptlGLYear).filter(Boolean))]
      .sort((a, b) => Number(b) - Number(a));

    setTimeout(() => updateGamesTable(), 80);

    return `
      <section class="panel court-section-panel">
        <div class="section-head">
          <div>
            <h3>Game Logs</h3>
            <p class="note">
              ON/OFF four-factor columns are season-level player ON data repeated on each game row for that year/team.
              Shot profile is team/opponent shot profile while the player is ON, not personal shot diet.
            </p>
          </div>
        </div>

        <div class="toolbar">
          <label class="note">
            Year
            <select id="gameLogYear">
              <option value="ALL">All</option>
              ${years.map(y => `<option value="${y}">${y}</option>`).join("")}
            </select>
          </label>
        </div>

        <div id="gamesTable"></div>
      </section>
    `;
  };

  updateGamesTable = function() {
    const box = document.getElementById("gamesTable");
    if (!box) return;

    const rows = __ptlGLGameRows();

    box.innerHTML = richTable(rows, [
      ["year", "Year"],
      ["date", "Date"],
      ["team", "Team"],
      ["opp", "Opp"],

      ["pts", "PTS"],
      ["pp75", "PP/75"],
      ["rAdjTS", "rAdj TS"],
      ["rTS", "rTS"],
      ["rORTG", "rORTG"],
      ["rDRTG", "rDRTG"],
      ["rNET", "rNET"],
      ["min", "MIN"],

      ["onMin", "ON Min"],
      ["offMin", "OFF Min"],

      ["teamEFGOn", "Team eFG ON"],
      ["teamEFGOff", "Team eFG OFF"],
      ["teamEFGDelta", "Δ eFG"],

      ["teamORBOn", "Team ORB% ON"],
      ["teamORBOff", "Team ORB% OFF"],
      ["teamORBDelta", "Δ ORB"],

      ["teamFTROn", "Team FTr ON"],
      ["teamFTROff", "Team FTr OFF"],
      ["teamFTRDelta", "Δ FTr"],

      ["teamTOVOn", "Team TOV% ON"],
      ["teamTOVOff", "Team TOV% OFF"],
      ["teamTOVDelta", "Δ TOV"],

      ["oppEFGOn", "Opp eFG ON"],
      ["oppEFGOff", "Opp eFG OFF"],
      ["oppEFGDelta", "Opp Δ eFG"],

      ["oppORBOn", "Opp ORB% ON"],
      ["oppORBOff", "Opp ORB% OFF"],
      ["oppORBDelta", "Opp Δ ORB"],

      ["oppFTROn", "Opp FTr ON"],
      ["oppFTROff", "Opp FTr OFF"],
      ["oppFTRDelta", "Opp Δ FTr"],

      ["oppTOVOn", "Opp TOV% ON"],
      ["oppTOVOff", "Opp TOV% OFF"],
      ["oppTOVDelta", "Opp Δ TOV"],
    ]);
  };

  document.addEventListener("change", function(e) {
    if (e.target && e.target.id === "gameLogYear") {
      updateGamesTable();
    }
  });
}

/* Game Log upgrade: show season ON/OFF four factors inside game rows */
if (!globalThis.__PTL_GAMELOG_ON4F__) {
  globalThis.__PTL_GAMELOG_ON4F__ = true;

  function __ptlGLGet(row, keys) {
    for (const k of keys) {
      if (row && row[k] !== undefined && row[k] !== null && row[k] !== "" && row[k] !== "—") return row[k];
    }
    return null;
  }

  function __ptlGLNum(row, keys) {
    const v = __ptlGLGet(row, keys);
    if (v === null) return null;
    const n = Number(String(v).replace("%", ""));
    return Number.isFinite(n) ? n : null;
  }

  function __ptlGLYear(row) {
    const y = __ptlGLGet(row, ["year", "season", "SEASON", "YEAR"]);
    if (typeof y === "string" && y.includes("-")) {
      const n = Number(y.slice(0, 4));
      return Number.isFinite(n) ? String(n + 1) : String(y);
    }
    return y === null ? "" : String(y);
  }

  function __ptlGLTeam(row) {
    return String(__ptlGLGet(row, ["team", "TEAM", "teamAbbr", "TEAM_ABBREVIATION"]) || "");
  }

  function __ptlGLOpp(row) {
    return __ptlGLGet(row, ["opponent", "opp", "OPP", "Opponent", "OPPONENT"]) || "—";
  }

  function __ptlGLDate(row) {
    return __ptlGLGet(row, ["date", "gameDate", "GAME_DATE", "matchupDate"]) || "—";
  }

  function __ptlGLFmt(v, plus = false) {
    if (v === null || v === undefined || v === "" || v === "—") return "—";
    const n = Number(v);
    if (!Number.isFinite(n)) return String(v);
    const out = Math.abs(n) >= 100 ? n.toFixed(0) : n.toFixed(1);
    return plus && n > 0 ? `+${out}` : out;
  }

  function __ptlGLDelta(on, off) {
    if (on === null || off === null || on === undefined || off === undefined) return "—";
    const n = Number(on) - Number(off);
    if (!Number.isFinite(n)) return "—";
    return n > 0 ? `+${n.toFixed(1)}` : n.toFixed(1);
  }

  function __ptlGLFourFactorsForGame(game) {
    const meta = state.current?.meta || {};
    const year = __ptlGLYear(game);
    const team = __ptlGLTeam(game);

    const byTeam = meta.onCourtFourFactorsByTeam?.[year] || {};
    if (team && byTeam[team]) return byTeam[team];

    return meta.onCourtFourFactors?.[year] || null;
  }

  function __ptlGLGameRows() {
    const games = Array.isArray(state.current?.games) ? state.current.games : [];
    const yearFilter = document.getElementById("gameLogYear")?.value || "ALL";

    return games
      .filter(g => yearFilter === "ALL" || __ptlGLYear(g) === yearFilter)
      .map(g => {
        const ff = __ptlGLFourFactorsForGame(g);

        return {
          year: __ptlGLYear(g),
          date: __ptlGLDate(g),
          team: __ptlGLTeam(g) || "—",
          opp: __ptlGLOpp(g),

          pts: __ptlGLFmt(__ptlGLNum(g, ["PTS", "pts", "points"])),
          pp75: __ptlGLFmt(__ptlGLNum(g, ["PP75", "pp75", "PTS_75", "pointsPer75"])),
          rAdjTS: __ptlGLFmt(__ptlGLNum(g, ["rAdjTS", "RAdjTS", "RADJTS", "RADJ_TS"]), true),
          rTS: __ptlGLFmt(__ptlGLNum(g, ["rTS", "RTS", "r_ts"]), true),
          rORTG: __ptlGLFmt(__ptlGLNum(g, ["rORTG", "RORTG", "r_off_rating"]), true),
          rDRTG: __ptlGLFmt(__ptlGLNum(g, ["rDRTG", "RDRTG", "r_def_rating"]), true),
          rNET: __ptlGLFmt(__ptlGLNum(g, ["rNET", "RNET", "r_net_rating"]), true),
          min: __ptlGLFmt(__ptlGLNum(g, ["MIN", "min", "minutes"])),

          onMin: ff ? __ptlGLFmt(ff.onMinutes) : "—",
          offMin: ff ? __ptlGLFmt(ff.offMinutes) : "—",

          teamEFGOn: ff ? __ptlGLFmt(ff.onTeamEFG) : "—",
          teamEFGOff: ff ? __ptlGLFmt(ff.onTeamEFGOff) : "—",
          teamEFGDelta: ff ? __ptlGLDelta(ff.onTeamEFG, ff.onTeamEFGOff) : "—",

          teamORBOn: ff ? __ptlGLFmt(ff.onTeamOREBPct) : "—",
          teamORBOff: ff ? __ptlGLFmt(ff.onTeamOREBPctOff) : "—",
          teamORBDelta: ff ? __ptlGLDelta(ff.onTeamOREBPct, ff.onTeamOREBPctOff) : "—",

          teamFTROn: ff ? __ptlGLFmt(ff.onTeamFTr) : "—",
          teamFTROff: ff ? __ptlGLFmt(ff.onTeamFTrOff) : "—",
          teamFTRDelta: ff ? __ptlGLDelta(ff.onTeamFTr, ff.onTeamFTrOff) : "—",

          teamTOVOn: ff ? __ptlGLFmt(ff.onTeamTOVPct) : "—",
          teamTOVOff: ff ? __ptlGLFmt(ff.onTeamTOVPctOff) : "—",
          teamTOVDelta: ff ? __ptlGLDelta(ff.onTeamTOVPct, ff.onTeamTOVPctOff) : "—",

          oppEFGOn: ff ? __ptlGLFmt(ff.onOppEFG) : "—",
          oppEFGOff: ff ? __ptlGLFmt(ff.onOppEFGOff) : "—",
          oppEFGDelta: ff ? __ptlGLDelta(ff.onOppEFG, ff.onOppEFGOff) : "—",

          oppORBOn: ff ? __ptlGLFmt(ff.onOppOREBPct) : "—",
          oppORBOff: ff ? __ptlGLFmt(ff.onOppOREBPctOff) : "—",
          oppORBDelta: ff ? __ptlGLDelta(ff.onOppOREBPct, ff.onOppOREBPctOff) : "—",

          oppFTROn: ff ? __ptlGLFmt(ff.onOppFTr) : "—",
          oppFTROff: ff ? __ptlGLFmt(ff.onOppFTrOff) : "—",
          oppFTRDelta: ff ? __ptlGLDelta(ff.onOppFTr, ff.onOppFTrOff) : "—",

          oppTOVOn: ff ? __ptlGLFmt(ff.onOppTOVPct) : "—",
          oppTOVOff: ff ? __ptlGLFmt(ff.onOppTOVPctOff) : "—",
          oppTOVDelta: ff ? __ptlGLDelta(ff.onOppTOVPct, ff.onOppTOVPctOff) : "—",
        };
      });
  }

  renderGames = function() {
    const games = Array.isArray(state.current?.games) ? state.current.games : [];
    const years = [...new Set(games.map(__ptlGLYear).filter(Boolean))]
      .sort((a, b) => Number(b) - Number(a));

    setTimeout(() => updateGamesTable(), 80);

    return `
      <section class="panel court-section-panel">
        <div class="section-head">
          <div>
            <h3>Game Logs</h3>
            <p class="note">
              ON/OFF four-factor columns are season-level player ON data repeated on each game row for that year/team.
              Shot profile is team/opponent shot profile while the player is ON, not personal shot diet.
            </p>
          </div>
        </div>

        <div class="toolbar">
          <label class="note">
            Year
            <select id="gameLogYear">
              <option value="ALL">All</option>
              ${years.map(y => `<option value="${y}">${y}</option>`).join("")}
            </select>
          </label>
        </div>

        <div id="gamesTable"></div>
      </section>
    `;
  };

  updateGamesTable = function() {
    const box = document.getElementById("gamesTable");
    if (!box) return;

    const rows = __ptlGLGameRows();

    box.innerHTML = richTable(rows, [
      ["year", "Year"],
      ["date", "Date"],
      ["team", "Team"],
      ["opp", "Opp"],

      ["pts", "PTS"],
      ["pp75", "PP/75"],
      ["rAdjTS", "rAdj TS"],
      ["rTS", "rTS"],
      ["rORTG", "rORTG"],
      ["rDRTG", "rDRTG"],
      ["rNET", "rNET"],
      ["min", "MIN"],

      ["onMin", "ON Min"],
      ["offMin", "OFF Min"],

      ["teamEFGOn", "Team eFG ON"],
      ["teamEFGOff", "Team eFG OFF"],
      ["teamEFGDelta", "Δ eFG"],

      ["teamORBOn", "Team ORB% ON"],
      ["teamORBOff", "Team ORB% OFF"],
      ["teamORBDelta", "Δ ORB"],

      ["teamFTROn", "Team FTr ON"],
      ["teamFTROff", "Team FTr OFF"],
      ["teamFTRDelta", "Δ FTr"],

      ["teamTOVOn", "Team TOV% ON"],
      ["teamTOVOff", "Team TOV% OFF"],
      ["teamTOVDelta", "Δ TOV"],

      ["oppEFGOn", "Opp eFG ON"],
      ["oppEFGOff", "Opp eFG OFF"],
      ["oppEFGDelta", "Opp Δ eFG"],

      ["oppORBOn", "Opp ORB% ON"],
      ["oppORBOff", "Opp ORB% OFF"],
      ["oppORBDelta", "Opp Δ ORB"],

      ["oppFTROn", "Opp FTr ON"],
      ["oppFTROff", "Opp FTr OFF"],
      ["oppFTRDelta", "Opp Δ FTr"],

      ["oppTOVOn", "Opp TOV% ON"],
      ["oppTOVOff", "Opp TOV% OFF"],
      ["oppTOVDelta", "Opp Δ TOV"],
    ]);
  };

  document.addEventListener("change", function(e) {
    if (e.target && e.target.id === "gameLogYear") {
      updateGamesTable();
    }
  });
}

/* Final Game Log layout: four factors as summary, not repeated per game row */
if (!globalThis.__PTL_CLEAN_ON4F_GAMELOG__) {
  globalThis.__PTL_CLEAN_ON4F_GAMELOG__ = true;

  function ptlGet(row, keys) {
    for (const k of keys) {
      if (row && row[k] !== undefined && row[k] !== null && row[k] !== "" && row[k] !== "—") return row[k];
    }
    return null;
  }

  function ptlNum(row, keys) {
    const v = ptlGet(row, keys);
    if (v === null) return null;
    const n = Number(String(v).replace("%", ""));
    return Number.isFinite(n) ? n : null;
  }

  function ptlYear(row) {
    const y = ptlGet(row, ["year", "season", "SEASON", "YEAR"]);
    if (typeof y === "string" && y.includes("-")) {
      const n = Number(y.slice(0, 4));
      return Number.isFinite(n) ? String(n + 1) : String(y);
    }
    return y === null ? "" : String(y);
  }

  function ptlTeam(row) {
    return String(ptlGet(row, ["team", "TEAM", "teamAbbr", "TEAM_ABBREVIATION"]) || "");
  }

  function ptlOpp(row) {
    return ptlGet(row, ["opponent", "opp", "OPP", "Opponent", "OPPONENT"]) || "—";
  }

  function ptlDate(row) {
    return ptlGet(row, ["date", "gameDate", "GAME_DATE", "matchupDate"]) || "—";
  }

  function ptlFmt(v, plus = false) {
    if (v === null || v === undefined || v === "" || v === "—") return "—";
    const n = Number(v);
    if (!Number.isFinite(n)) return String(v);
    const out = Math.abs(n) >= 100 ? n.toFixed(0) : n.toFixed(1);
    return plus && n > 0 ? `+${out}` : out;
  }

  function ptlDelta(on, off, lowerIsBetter = false) {
    if (on === null || off === null || on === undefined || off === undefined) return "—";
    let n = Number(on) - Number(off);
    if (!Number.isFinite(n)) return "—";

    // For opponent eFG/ORB/FTr, lower ON is better.
    // For opponent TOV%, higher ON is better, so don't flip that.
    if (lowerIsBetter) n = -n;

    return n > 0 ? `+${n.toFixed(1)}` : n.toFixed(1);
  }

  function ptlFourFactorsForYearTeam(year, team) {
    const meta = state.current?.meta || {};
    const byTeam = meta.onCourtFourFactorsByTeam?.[year] || {};
    if (team && byTeam[team]) return byTeam[team];
    return meta.onCourtFourFactors?.[year] || null;
  }

  function ptlFourFactorSummaryHTML(yearFilter) {
    const games = Array.isArray(state.current?.games) ? state.current.games : [];
    const rows = games.filter(g => yearFilter === "ALL" || ptlYear(g) === yearFilter);

    const yearTeams = [];
    const seen = new Set();

    for (const g of rows) {
      const y = ptlYear(g);
      const t = ptlTeam(g);
      const key = `${y}|${t}`;
      if (!y || !t || seen.has(key)) continue;
      seen.add(key);
      yearTeams.push({ year: y, team: t });
    }

    const cards = [];

    for (const yt of yearTeams) {
      const ff = ptlFourFactorsForYearTeam(yt.year, yt.team);
      if (!ff) continue;

      cards.push(`
        <section class="panel" style="margin-bottom:14px;">
          <div class="section-head">
            <div>
              <h3>${yt.year} ${yt.team} ON/OFF Four Factors</h3>
              <p class="note">Season-level team/opponent performance while this player is ON vs OFF the floor.</p>
            </div>
          </div>

          <div class="stat-grid">
            <div class="stat-card">
              <div class="k">TEAM eFG</div>
              <div class="v">${ptlFmt(ff.onTeamEFG)}%</div>
              <div class="s">OFF ${ptlFmt(ff.onTeamEFGOff)}% · Δ ${ptlDelta(ff.onTeamEFG, ff.onTeamEFGOff)}</div>
            </div>

            <div class="stat-card">
              <div class="k">TEAM ORB%</div>
              <div class="v">${ptlFmt(ff.onTeamOREBPct)}%</div>
              <div class="s">OFF ${ptlFmt(ff.onTeamOREBPctOff)}% · Δ ${ptlDelta(ff.onTeamOREBPct, ff.onTeamOREBPctOff)}</div>
            </div>

            <div class="stat-card">
              <div class="k">TEAM FTr</div>
              <div class="v">${ptlFmt(ff.onTeamFTr)}</div>
              <div class="s">OFF ${ptlFmt(ff.onTeamFTrOff)} · Δ ${ptlDelta(ff.onTeamFTr, ff.onTeamFTrOff)}</div>
            </div>

            <div class="stat-card">
              <div class="k">TEAM TOV%</div>
              <div class="v">${ptlFmt(ff.onTeamTOVPct)}%</div>
              <div class="s">OFF ${ptlFmt(ff.onTeamTOVPctOff)}% · Δ ${ptlDelta(ff.onTeamTOVPct, ff.onTeamTOVPctOff, true)}</div>
            </div>

            <div class="stat-card">
              <div class="k">OPP eFG</div>
              <div class="v">${ptlFmt(ff.onOppEFG)}%</div>
              <div class="s">OFF ${ptlFmt(ff.onOppEFGOff)}% · Impact ${ptlDelta(ff.onOppEFG, ff.onOppEFGOff, true)}</div>
            </div>

            <div class="stat-card">
              <div class="k">OPP ORB%</div>
              <div class="v">${ptlFmt(ff.onOppOREBPct)}%</div>
              <div class="s">OFF ${ptlFmt(ff.onOppOREBPctOff)}% · Impact ${ptlDelta(ff.onOppOREBPct, ff.onOppOREBPctOff, true)}</div>
            </div>

            <div class="stat-card">
              <div class="k">OPP FTr</div>
              <div class="v">${ptlFmt(ff.onOppFTr)}</div>
              <div class="s">OFF ${ptlFmt(ff.onOppFTrOff)} · Impact ${ptlDelta(ff.onOppFTr, ff.onOppFTrOff, true)}</div>
            </div>

            <div class="stat-card">
              <div class="k">OPP TOV%</div>
              <div class="v">${ptlFmt(ff.onOppTOVPct)}%</div>
              <div class="s">OFF ${ptlFmt(ff.onOppTOVPctOff)}% · Impact ${ptlDelta(ff.onOppTOVPct, ff.onOppTOVPctOff)}</div>
            </div>
          </div>

          <p class="note" style="margin-top:10px;">ON minutes: ${ptlFmt(ff.onMinutes)} · OFF minutes: ${ptlFmt(ff.offMinutes)}</p>
        </section>
      `);
    }

    return cards.join("");
  }

  function ptlGameLogRows() {
    const games = Array.isArray(state.current?.games) ? state.current.games : [];
    const yearFilter = document.getElementById("gameLogYear")?.value || "ALL";

    return games
      .filter(g => yearFilter === "ALL" || ptlYear(g) === yearFilter)
      .map(g => ({
        year: ptlYear(g),
        date: ptlDate(g),
        team: ptlTeam(g) || "—",
        opp: ptlOpp(g),

        pts: ptlFmt(ptlNum(g, ["PTS", "pts", "points"])),
        pp75: ptlFmt(ptlNum(g, ["PP75", "pp75", "PTS_75", "pointsPer75"])),
        rAdjTS: ptlFmt(ptlNum(g, ["rAdjTS", "RAdjTS", "RADJTS", "RADJ_TS"]), true),
        rTS: ptlFmt(ptlNum(g, ["rTS", "RTS", "r_ts"]), true),
        rORTG: ptlFmt(ptlNum(g, ["rORTG", "RORTG", "r_off_rating"]), true),
        rDRTG: ptlFmt(ptlNum(g, ["rDRTG", "RDRTG", "r_def_rating"]), true),
        rNET: ptlFmt(ptlNum(g, ["rNET", "RNET", "r_net_rating"]), true),
        min: ptlFmt(ptlNum(g, ["MIN", "min", "minutes"])),

        reb: ptlFmt(ptlNum(g, ["REB", "reb", "TRB", "trb"])),
        ast: ptlFmt(ptlNum(g, ["AST", "ast"])),
        tov: ptlFmt(ptlNum(g, ["TOV", "tov", "TO"])),
        ts: ptlFmt(ptlNum(g, ["TS%", "TS", "ts", "tsPct"])),
        adjts: ptlFmt(ptlNum(g, ["AdjTS%", "AdjTS", "adjTS"])),
        ortg: ptlFmt(ptlNum(g, ["ORTG", "ortg", "offRating"])),
        drtg: ptlFmt(ptlNum(g, ["DRTG", "drtg", "defRating"])),
      }));
  }

  renderGames = function() {
    const games = Array.isArray(state.current?.games) ? state.current.games : [];
    const years = [...new Set(games.map(ptlYear).filter(Boolean))]
      .sort((a, b) => Number(b) - Number(a));

    setTimeout(() => updateGamesTable(), 80);

    return `
      <section class="panel court-section-panel">
        <div class="section-head">
          <div>
            <h3>Game Logs</h3>
            <p class="note">
              Game rows stay game-specific. ON/OFF four factors are shown separately above the table because they are season-level.
            </p>
          </div>
        </div>

        <div class="toolbar">
          <label class="note">
            Year
            <select id="gameLogYear">
              <option value="ALL">All</option>
              ${years.map(y => `<option value="${y}">${y}</option>`).join("")}
            </select>
          </label>
        </div>

        <div id="gameFourFactorSummary"></div>
        <div id="gamesTable"></div>
      </section>
    `;
  };

  updateGamesTable = function() {
    const tableBox = document.getElementById("gamesTable");
    const summaryBox = document.getElementById("gameFourFactorSummary");
    if (!tableBox) return;

    const yearFilter = document.getElementById("gameLogYear")?.value || "ALL";

    if (summaryBox) {
      summaryBox.innerHTML = ptlFourFactorSummaryHTML(yearFilter);
    }

    const rows = ptlGameLogRows();

    tableBox.innerHTML = richTable(rows, [
      ["year", "Year"],
      ["date", "Date"],
      ["team", "Team"],
      ["opp", "Opp"],
      ["pts", "PTS"],
      ["pp75", "PP/75"],
      ["rAdjTS", "rAdj TS"],
      ["rTS", "rTS"],
      ["rORTG", "rORTG"],
      ["rDRTG", "rDRTG"],
      ["rNET", "rNET"],
      ["min", "MIN"],
      ["reb", "REB"],
      ["ast", "AST"],
      ["tov", "TOV"],
      ["ts", "TS%"],
      ["adjts", "Adj TS%"],
      ["ortg", "ORTG"],
      ["drtg", "DRTG"],
    ]);
  };

  document.addEventListener("change", function(e) {
    if (e.target && e.target.id === "gameLogYear") {
      updateGamesTable();
    }
  });
}
