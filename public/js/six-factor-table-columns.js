(function () {
  console.log("PTL six-factor render hooks loaded");

  const DATA_URLS = [
    "./public/data/data-package.embedded.json",
    "./public/data/data-package.json",
    "./data-package.json",
    "./data/data-package.json"
  ];

  const GAME_COLS = [
    { key: "teamEFG", label: "Tm eFG" },
    { key: "teamTOVPct", label: "Tm TOV" },
    { key: "teamFTr", label: "Tm FTr" },
    { key: "teamTS", label: "Tm TS" },
    { key: "teamEFGvsOppAllowed", label: "eFG ±" },
    { key: "teamTOVPctvsOppAllowed", label: "TOV ±", invert: true },
    { key: "teamFTrvsOppAllowed", label: "FTr ±" },
    { key: "teamTSvsOppAllowed", label: "TS ±" }
  ];

  let pkgPromise = null;
  let mapsPromise = null;

  function cleanId(x) {
    return String(x || "").toLowerCase().replace(/[^a-z0-9]/g, "");
  }

  function getYear(r) {
    return String(r?.year || r?.season || r?.SEASON || "");
  }

  function getGameId(r) {
    return String(r?.gameId || r?.GAME_ID || r?.nbaGameId || r?.game_id || "").replace(/^00/, "");
  }

  function getPlayerId(r) {
    return cleanId(r?.playerId || r?.PLAYER_ID || r?.nbaId || r?.NBA_ID || "");
  }

  function getOpp(r) {
    return String(r?.opponent || r?.opp || r?.OPP || r?.opponentTeam || "").toUpperCase();
  }

  function getSeriesCode(r) {
    return String(r?.seriesCode || r?.series || r?.seriesId || "");
  }

  async function fetchJson(url) {
    const res = await fetch(url + "?v=" + Date.now(), { cache: "no-store" });
    if (!res.ok) throw new Error(url + " failed " + res.status);
    return await res.json();
  }

  async function loadPackage() {
    if (pkgPromise) return pkgPromise;

    pkgPromise = (async () => {
      for (const url of DATA_URLS) {
        try {
          const data = await fetchJson(url);
          console.log("Six-factor hooks loaded JSON:", url);
          return data;
        } catch (e) {
          console.warn("Could not load", url, e);
        }
      }

      if (window.dataPackage) return window.dataPackage;
      if (window.__DATA_PACKAGE__) return window.__DATA_PACKAGE__;

      throw new Error("No data package found for six factors");
    })();

    return pkgPromise;
  }

  async function buildMaps() {
    if (mapsPromise) return mapsPromise;

    mapsPromise = loadPackage().then(pkg => {
      const games = Array.isArray(pkg.playerGames) ? pkg.playerGames : [];
      const series = Array.isArray(pkg.playerSeries)
        ? pkg.playerSeries
        : Array.isArray(pkg.seriesPlayers)
          ? pkg.seriesPlayers
          : [];

      const gameByRowId = new Map();
      const gameByKey = new Map();
      const seriesByKey = new Map();

      for (const r of games) {
        if (!r || !r.hasTeamSixFactors) continue;

        const rowId = cleanId(r.gameRowId);
        const pid = getPlayerId(r);
        const year = getYear(r);
        const gid = getGameId(r);

        if (rowId) gameByRowId.set(rowId, r);
        if (pid && year && gid) gameByKey.set(`${pid}|${year}|${gid}`, r);
      }

      for (const r of series) {
        if (!r || !r.hasTeamSeriesSixFactors) continue;

        const pid = getPlayerId(r);
        const year = getYear(r);
        const sc = getSeriesCode(r);
        const opp = getOpp(r);

        if (pid && year && sc) seriesByKey.set(`${pid}|${year}|${sc}`, r);
        if (pid && year && opp) seriesByKey.set(`${pid}|${year}|${opp}`, r);
      }

      console.log("Six-factor maps:", {
        gameRows: gameByRowId.size,
        gameKeys: gameByKey.size,
        seriesKeys: seriesByKey.size
      });

      return { gameByRowId, gameByKey, seriesByKey };
    });

    return mapsPromise;
  }

  function resolveGameRow(row, maps) {
    if (!row) return null;
    if (row.hasTeamSixFactors) return row;

    const rowId = cleanId(row.gameRowId);
    if (rowId && maps.gameByRowId.has(rowId)) return maps.gameByRowId.get(rowId);

    const pid = getPlayerId(row);
    const year = getYear(row);
    const gid = getGameId(row);

    if (pid && year && gid) {
      return maps.gameByKey.get(`${pid}|${year}|${gid}`) || null;
    }

    return null;
  }

  function resolveSeriesRow(row, maps) {
    if (!row) return null;
    if (row.hasTeamSeriesSixFactors) return row;

    const pid = getPlayerId(row);
    const year = getYear(row);
    const sc = getSeriesCode(row);
    const opp = getOpp(row);

    if (pid && year && sc) {
      const hit = maps.seriesByKey.get(`${pid}|${year}|${sc}`);
      if (hit) return hit;
    }

    if (pid && year && opp) {
      const hit = maps.seriesByKey.get(`${pid}|${year}|${opp}`);
      if (hit) return hit;
    }

    return null;
  }

  function fmt(row, col) {
    if (!row || row[col.key] === undefined || row[col.key] === null || row[col.key] === "") return "";

    const n = Number(row[col.key]);
    if (!Number.isFinite(n)) return "";

    if (col.key.includes("vsOppAllowed")) {
      return (n > 0 ? "+" : "") + n.toFixed(1);
    }

    return n.toFixed(1);
  }

  function cls(row, col) {
    if (!row || !col.key.includes("vsOppAllowed")) return "";

    const n = Number(row[col.key]);
    if (!Number.isFinite(n)) return "";

    const good = col.invert ? n < 0 : n > 0;
    const bad = col.invert ? n > 0 : n < 0;

    if (good) return "ptl-six-pos";
    if (bad) return "ptl-six-neg";
    return "ptl-six-muted";
  }

  function cleanOld(table) {
    table.querySelectorAll("[data-six-factor-cell='1'], [data-six-factor-head='1']").forEach(el => el.remove());
  }

  function addHeaders(table) {
    const headRow = table.querySelector("thead tr") || table.querySelector("tr");
    if (!headRow) return;

    for (const col of GAME_COLS) {
      const th = document.createElement("th");
      th.textContent = col.label;
      th.dataset.sixFactorHead = "1";
      th.className = "ptl-six-th";
      headRow.appendChild(th);
    }
  }

  function bodyRows(tbody) {
    return Array.from(tbody.querySelectorAll("tr")).filter(tr => tr.children.length);
  }

  async function injectTable(tbodyId, rows, kind) {
    const tbody = document.getElementById(tbodyId);
    if (!tbody || !Array.isArray(rows)) return;

    const table = tbody.closest("table");
    if (!table) return;

    const maps = await buildMaps();

    cleanOld(table);
    addHeaders(table);

    table.classList.add("ptl-six-factor-enhanced");

    const trs = bodyRows(tbody);

    trs.forEach((tr, i) => {
      const sourceRow = rows[i];
      const dataRow = kind === "series"
        ? resolveSeriesRow(sourceRow, maps)
        : resolveGameRow(sourceRow, maps);

      for (const col of GAME_COLS) {
        const td = document.createElement("td");
        td.dataset.sixFactorCell = "1";
        td.className = "ptl-six-td " + cls(dataRow, col);
        td.textContent = fmt(dataRow, col);
        tr.appendChild(td);
      }
    });

    console.log(`Injected six factors into ${tbodyId}:`, trs.length, "visible rows");
  }

  function hookRenderFunction(name, tbodyId, kind) {
    const fn = window[name];
    if (typeof fn !== "function" || fn.__sixFactorHooked) return false;

    window[name] = function (rows, ...rest) {
      const result = fn.call(this, rows, ...rest);
      setTimeout(() => injectTable(tbodyId, rows, kind), 0);
      setTimeout(() => injectTable(tbodyId, rows, kind), 250);
      return result;
    };

    window[name].__sixFactorHooked = true;
    console.log("Hooked", name, "for six factors");
    return true;
  }

  function installHooks() {
    hookRenderFunction("renderGameTable", "gameTableBody", "game");
    hookRenderFunction("renderSeriesTable", "seriesTableBody", "series");
  }

  window.sfSixFactorRefresh = function () {
    installHooks();

    console.log("sfSixFactorRefresh ran. Hooks:", {
      renderGameTable: typeof window.renderGameTable,
      renderSeriesTable: typeof window.renderSeriesTable
    });
  };

  let tries = 0;
  const timer = setInterval(() => {
    installHooks();
    tries += 1;

    if (
      tries > 40 ||
      (window.renderGameTable?.__sixFactorHooked && window.renderSeriesTable?.__sixFactorHooked)
    ) {
      clearInterval(timer);
    }
  }, 250);

  document.addEventListener("DOMContentLoaded", installHooks);
})();
