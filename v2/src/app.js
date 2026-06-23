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

function renderGames() {
  const rows = state.current.games;
  return `
    <div class="panel">
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
      </div>
      <div id="gamesTable"></div>
    </div>
  `;
}

function renderSeries() {
  const rows = state.current.series;
  return `
    <div class="panel">
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
      </div>
      <div id="seriesTable"></div>
    </div>
  `;
}

function renderTranslator() {
  const rows = state.current.series;
  const options = rows.map((r, i) => {
    const y = rowYear(r);
    const opp = get(r, ["opponent", "opp", "OPP"]);
    const team = get(r, ["team", "TEAM"]);
    return `<option value="${i}">${y} ${team} vs ${opp || "—"} • ${fmt(get(r, ["PTS", "points"]))} PTS</option>`;
  }).join("");

  return `
    <div class="panel">
      <h3>Series Translator</h3>
      <select id="translatorPick">${options}</select>
      <div id="translatorOutput" style="margin-top:12px"></div>
      <p class="note">V2 translator is now fed directly from the player's own series file, so Wemby/Harden should appear if they have series rows.</p>
    </div>
  `;
}

function renderStretch() {
  return `
    <div class="panel">
      <h3>Stretch Lab</h3>
      <div class="toolbar">
        <select id="stretchYear">${yearOptions(state.current.games)}</select>
        <select id="stretchLen">
          <option value="3">3-game stretches</option>
          <option value="5" selected>5-game stretches</option>
          <option value="10">10-game stretches</option>
          <option value="20">20-game stretches</option>
        </select>
        <select id="stretchMetric">
          <option value="PTS">Points</option>
          <option value="TS">TS</option>
          <option value="ORTG">ORTG</option>
          <option value="MIN">Minutes</option>
        </select>
      </div>
      <div id="stretchOutput"></div>
    </div>
  `;
}

function attachFilters() {
  if (state.tab === "games") {
    ["yearFilter", "oppFilter", "sortFilter"].forEach(id => document.getElementById(id)?.addEventListener("input", updateGamesTable));
    updateGamesTable();
  }

  if (state.tab === "series") {
    ["yearFilter", "oppFilter", "sortFilter"].forEach(id => document.getElementById(id)?.addEventListener("input", updateSeriesTable));
    updateSeriesTable();
  }

  if (state.tab === "translator") {
    document.getElementById("translatorPick")?.addEventListener("input", updateTranslator);
    updateTranslator();
  }

  if (state.tab === "stretch") {
    ["stretchYear", "stretchLen", "stretchMetric"].forEach(id => document.getElementById(id)?.addEventListener("input", updateStretch));
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
  document.getElementById("gamesTable").innerHTML = table(rows, [
    ["year", "Year"], ["date", "Date"], ["team", "Team"], ["opponent", "Opp"],
    ["MIN", "MIN"], ["PTS", "PTS"], ["REB", "REB"], ["AST", "AST"],
    ["TS", "TS"], ["ORTG", "ORTG"], ["DRTG", "DRTG"], ["gameId", "Game ID"]
  ]);
}

function updateSeriesTable() {
  const rows = filterRows(state.current.series);
  document.getElementById("seriesTable").innerHTML = table(rows, [
    ["year", "Year"], ["team", "Team"], ["opponent", "Opp"], ["seriesCode", "Series"],
    ["GP", "GP"], ["MIN", "MIN"], ["PTS", "PTS"], ["REB", "REB"], ["AST", "AST"],
    ["TS", "TS"], ["ORTG", "ORTG"], ["DRTG", "DRTG"]
  ]);
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
  const len = Number(document.getElementById("stretchLen")?.value || 5);
  const metric = document.getElementById("stretchMetric")?.value || "PTS";

  let games = state.current.games.filter(g => !year || rowYear(g) === year);
  games = games.slice().sort((a, b) => {
    const da = String(get(a, ["date", "gameDate"]));
    const db = String(get(b, ["date", "gameDate"]));
    return da.localeCompare(db);
  });

  const stretches = [];
  for (let i = 0; i + len <= games.length; i++) {
    const chunk = games.slice(i, i + len);
    stretches.push({
      start: get(chunk[0], ["date", "gameDate", "gameId"]),
      end: get(chunk[chunk.length - 1], ["date", "gameDate", "gameId"]),
      games: len,
      avg: avg(chunk, [metric]),
    });
  }

  stretches.sort((a, b) => (b.avg ?? -99999) - (a.avg ?? -99999));

  document.getElementById("stretchOutput").innerHTML = table(stretches.slice(0, 25), [
    ["start", "Start"], ["end", "End"], ["games", "Games"], ["avg", `${metric} Avg`]
  ]);
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

loadIndex().catch(err => {
  console.error(err);
  els.indexStatus.textContent = "Failed to load player index";
});
