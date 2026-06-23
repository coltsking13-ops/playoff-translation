/* ============================================================
   SIX-FACTOR OVERLAY  —  six_factors_overlay.js
   v1.0  2026-06-23

   HOW TO USE:
   Add this ONE line just before </body> in index.html:
     <script src="six_factors_overlay.js"></script>

   WHAT IT DOES:
   Reads playerGames + playerSeries from the embedded DATA_PACKAGE,
   matches visible table rows to their data rows, and appends eight
   columns to every game-log, series-log, stretch-lab, and
   year-stretch-lab table:
     Tm eFG | Tm TOV | Tm FTr | Tm TS | eFG ± | TOV ± | FTr ± | TS ±

   FIELD NAMES (confirmed from live data 2026-06-23):
     teamEFG, teamTOVPct, teamFTr, teamTS
     oppAllowedEFG, oppAllowedTOVPct, oppAllowedFTr, oppAllowedTS
     teamEFG_vsOppAllowed, teamTOVPct_vsOppAllowed,
     teamFTr_vsOppAllowed, teamTS_vsOppAllowed
     hasTeamSixFactors  (boolean gate)
     gameRowId          (primary game match key)
     seriesCode         (primary series match key)

   DEBUG in browser console:
     window.__sfInject()   — re-run injection manually
     window.__sfDiag(n)    — print first n game rows with six factors
   ============================================================ */

(function () {
  'use strict';

  /* ----------------------------------------------------------
     1.  COLUMN DEFINITIONS
     ---------------------------------------------------------- */
  const GAME_COLS = [
    { key: 'teamEFG',                 label: 'Tm eFG',  fmt: 'pct1'                },
    { key: 'teamTOVPct',              label: 'Tm TOV',  fmt: 'pct1'                },
    { key: 'teamFTr',                 label: 'Tm FTr',  fmt: 'pct1'                },
    { key: 'teamTS',                  label: 'Tm TS',   fmt: 'pct1'                },
    { key: 'teamEFG_vsOppAllowed',    label: 'eFG \u00b1',   fmt: 'signed1'             },
    { key: 'teamTOVPct_vsOppAllowed', label: 'TOV \u00b1',   fmt: 'signed1', invert: true },
    { key: 'teamFTr_vsOppAllowed',    label: 'FTr \u00b1',   fmt: 'signed1'             },
    { key: 'teamTS_vsOppAllowed',     label: 'TS \u00b1',    fmt: 'signed1'             },
  ];

  const SERIES_COLS = GAME_COLS;

  const HDR_ATTR  = 'data-sf-hdr';
  const CELL_ATTR = 'data-sf-cell';

  /* ----------------------------------------------------------
     2.  FORMATTERS
     ---------------------------------------------------------- */
  function fmtVal(value, type) {
    if (value == null || value === '') return '\u2014';
    const n = typeof value === 'number' ? value : parseFloat(value);
    if (!isFinite(n)) return '\u2014';
    if (type === 'pct1')    return n.toFixed(1);
    if (type === 'signed1') return (n > 0 ? '+' : '') + n.toFixed(1);
    return n.toFixed(1);
  }

  function colourFor(col, value) {
    if (col.fmt !== 'signed1' || value == null) return null;
    const n = typeof value === 'number' ? value : parseFloat(value);
    if (!isFinite(n) || n === 0) return '#94a3b8';
    const positive = col.invert ? n < 0 : n > 0;
    return positive ? '#4ade80' : '#f87171';
  }

  /* ----------------------------------------------------------
     3.  DATA PACKAGE ACCESS
     ---------------------------------------------------------- */
  function getPkg() {
    if (window.__sfPkg) return window.__sfPkg;
    const tag = document.getElementById('dataPackage');
    if (tag) {
      try {
        const raw = tag.textContent || tag.innerHTML || '';
        if (raw.trim()) { window.__sfPkg = JSON.parse(raw); return window.__sfPkg; }
      } catch (e) { console.warn('[SF] dataPackage parse error:', e.message); }
    }
    if (window.DATA_PACKAGE) { window.__sfPkg = window.DATA_PACKAGE; return window.__sfPkg; }
    return null;
  }

  /* ----------------------------------------------------------
     4.  INDEXES
     ---------------------------------------------------------- */
  function getGameIndex() {
    if (window.__sfGameIdx) return window.__sfGameIdx;
    const pkg = getPkg();
    if (!pkg) return {};
    const idx = {};
    for (const g of (pkg.playerGames || [])) {
      if (!g.hasTeamSixFactors) continue;
      if (g.gameRowId) idx[g.gameRowId] = g;
      if (g.playerId && g.year != null && g.gameId)
        idx[`${g.playerId}|${g.year}|${g.gameId}`] = g;
      if (g.playerId && g.year != null && g.date && g.opponent)
        idx[`${g.playerId}|${g.year}|${g.date}|${g.opponent}`] = g;
    }
    window.__sfGameIdx = idx;
    const count = (pkg.playerGames || []).filter(g => g.hasTeamSixFactors).length;
    console.log(`[SF] game index ready — ${count} six-factor rows`);
    return idx;
  }

  function getSeriesIndex() {
    if (window.__sfSeriesIdx) return window.__sfSeriesIdx;
    const pkg = getPkg();
    if (!pkg) return {};
    const idx = {};
    for (const s of (pkg.playerSeries || pkg.seriesPlayers || [])) {
      if (!s.hasTeamSixFactors) continue;
      if (s.playerId && s.year != null && s.seriesCode)
        idx[`${s.playerId}|${s.year}|${s.seriesCode}`] = s;
      if (s.playerId && s.year != null && s.opponent)
        idx[`${s.playerId}|${s.year}|${s.opponent}`] = s;
    }
    window.__sfSeriesIdx = idx;
    return idx;
  }

  function invalidateIndexes() {
    window.__sfPkg = null;
    window.__sfGameIdx = null;
    window.__sfSeriesIdx = null;
  }

  /* ----------------------------------------------------------
     5.  CURRENT PLAYER + YEAR
     ---------------------------------------------------------- */
  function getContext() {
    const pid = window.currentPlayerId || window.selectedPlayerId || window.__currentPlayerId || null;
    const yr  = window.currentYear     || window.selectedYear     || window.__currentYear     || null;
    if (pid || yr) return { playerId: pid, year: yr ? parseInt(yr) : null };
    const el = document.querySelector('[data-player-id],[data-playerid],.player-profile,.player-header,#playerProfile');
    return {
      playerId: el ? (el.dataset.playerId || el.dataset.playerid || null) : null,
      year:     el ? (parseInt(el.dataset.year) || null) : null,
    };
  }

  /* ----------------------------------------------------------
     6.  HINT EXTRACTION FROM A VISIBLE <tr>
     ---------------------------------------------------------- */
  function hintsFromTr(tr, colHeaders) {
    const h = {};
    const d = tr.dataset || {};
    [['gameRowId','gamerowid'],['gameId','gameid'],['date','date'],
     ['opponent','opponent','opp'],['seriesCode','seriescode'],
     ['playerId','playerid'],['year','year']]
      .forEach(([k, ...attrs]) => {
        for (const a of attrs) {
          const v = d[a] || d[k] || tr.getAttribute(`data-${a}`) || tr.getAttribute(`data-${k}`);
          if (v != null && v !== '') { h[k] = v; break; }
        }
      });

    const cells = tr.querySelectorAll('td');
    cells.forEach((td, i) => {
      const lbl = (colHeaders[i] || '').toLowerCase().replace(/\s+/g, '');
      const v = td.textContent.trim();
      if (!v || v === '\u2014' || v === '-') return;
      if (!h.date       && lbl === 'date')                  h.date = v;
      if (!h.opponent   && /^(opp|vs|opponent|against)$/.test(lbl)) h.opponent = v;
      if (!h.gameId     && lbl === 'gameid')                h.gameId = v;
      if (!h.seriesCode && lbl === 'seriescode')            h.seriesCode = v;
      if (h.PTS == null && lbl === 'pts')  h.PTS = parseFloat(v);
      if (h.MIN == null && lbl === 'min')  h.MIN = parseFloat(v);
    });
    if (h.year) h.year = parseInt(h.year);
    return h;
  }

  /* ----------------------------------------------------------
     7.  ROW MATCHING
     ---------------------------------------------------------- */
  function matchGame(playerId, year, hint) {
    const idx = getGameIndex();
    if (hint.gameRowId && idx[hint.gameRowId]) return idx[hint.gameRowId];
    const pid = hint.playerId || playerId;
    const yr  = hint.year     || year;
    if (pid && yr && hint.gameId) {
      const r = idx[`${pid}|${yr}|${hint.gameId}`]; if (r) return r;
    }
    if (pid && yr && hint.date && hint.opponent) {
      const r = idx[`${pid}|${yr}|${hint.date}|${hint.opponent}`]; if (r) return r;
    }
    // PTS+MIN fallback scan
    if (pid && yr && (hint.PTS != null || hint.MIN != null)) {
      for (const g of ((getPkg() || {}).playerGames || [])) {
        if (g.playerId !== pid || g.year !== yr || !g.hasTeamSixFactors) continue;
        const pm = hint.PTS == null || Math.abs((g.PTS || 0) - hint.PTS) < 0.6;
        const mm = hint.MIN == null || Math.abs((g.MIN || 0) - hint.MIN) < 0.6;
        if (pm && mm) return g;
      }
    }
    return null;
  }

  function matchSeries(playerId, year, hint) {
    const idx = getSeriesIndex();
    const pid = hint.playerId || playerId;
    const yr  = hint.year     || year;
    if (pid && yr && hint.seriesCode) {
      const r = idx[`${pid}|${yr}|${hint.seriesCode}`]; if (r) return r;
    }
    if (pid && yr && hint.opponent) {
      const r = idx[`${pid}|${yr}|${hint.opponent}`]; if (r) return r;
    }
    return null;
  }

  /* ----------------------------------------------------------
     8.  TABLE TYPE DETECTION
     ---------------------------------------------------------- */
  function detectType(table) {
    let sig = [table.id, table.className];
    let el = table;
    for (let i = 0; i < 4; i++) {
      el = el.parentElement;
      if (!el) break;
      sig.push(el.id, el.className);
    }
    sig = sig.join(' ').toLowerCase();

    if (/game.?log|gamelog|game.?table|stretch.?lab|stretchlab|year.?stretch/i.test(sig)) return 'game';
    if (/series.?log|serieslog|series.?table|series.?break/i.test(sig)) return 'series';

    const hdrs = Array.from(table.querySelectorAll('thead th,thead td'))
      .map(th => th.textContent.trim().toLowerCase());
    const hasPts = hdrs.some(h => h === 'pts');
    const hasMin = hdrs.some(h => h === 'min');
    if (!hasPts && !hasMin) return null;
    const hasSeries = hdrs.some(h => /series|round/.test(h));
    const hasDate   = hdrs.some(h => h === 'date');
    if (hasSeries && !hasDate) return 'series';
    return 'game';
  }

  /* ----------------------------------------------------------
     9.  HEADER + CELL INJECTION
     ---------------------------------------------------------- */
  function injectHeaders(table, cols) {
    if (table.getAttribute(HDR_ATTR)) return;
    const rows = table.querySelectorAll('thead tr');
    if (!rows.length) return;
    const hrow = rows[rows.length - 1];
    for (const col of cols) {
      if (hrow.querySelector(`[data-sfk="${col.key}"]`)) continue;
      const th = document.createElement('th');
      th.textContent = col.label;
      th.setAttribute('data-sfk', col.key);
      th.style.cssText = 'white-space:nowrap;padding:4px 8px;font-size:0.78em;color:#a78bfa;font-weight:600;text-align:right;border-left:1px solid #1e2340';
      hrow.appendChild(th);
    }
    table.setAttribute(HDR_ATTR, '1');
  }

  function injectCells(tr, cols, dataObj) {
    if (tr.getAttribute(CELL_ATTR)) return;
    for (const col of cols) {
      if (tr.querySelector(`[data-sfk="${col.key}"]`)) continue;
      const td = document.createElement('td');
      td.setAttribute('data-sfk', col.key);
      td.style.cssText = 'white-space:nowrap;padding:4px 8px;font-size:0.82em;text-align:right;border-left:1px solid #1e2340';
      const val = dataObj != null ? dataObj[col.key] : undefined;
      td.textContent = fmtVal(val, col.fmt);
      const c = dataObj != null ? colourFor(col, val) : null;
      if (c) td.style.color = c;
      tr.appendChild(td);
    }
    tr.setAttribute(CELL_ATTR, '1');
  }

  /* ----------------------------------------------------------
     10.  PROCESS ONE TABLE
     ---------------------------------------------------------- */
  function processTable(table) {
    const type = detectType(table);
    if (!type) return;
    const cols = type === 'game' ? GAME_COLS : SERIES_COLS;
    injectHeaders(table, cols);
    const colHeaders = Array.from(table.querySelectorAll('thead th,thead td'))
      .map(th => th.textContent.trim());
    const { playerId, year } = getContext();
    table.querySelectorAll('tbody tr').forEach(tr => {
      if (tr.getAttribute(CELL_ATTR)) return;
      const hint = hintsFromTr(tr, colHeaders);
      const obj  = type === 'game'
        ? matchGame(playerId, year, hint)
        : matchSeries(playerId, year, hint);
      injectCells(tr, cols, obj);
    });
  }

  /* ----------------------------------------------------------
     11.  SCROLLABLE WRAPPERS
     ---------------------------------------------------------- */
  function makeScrollable() {
    document.querySelectorAll('table').forEach(t => {
      const p = t.parentElement;
      if (!p) return;
      if (/auto|scroll/.test(getComputedStyle(p).overflowX)) return;
      p.style.overflowX = 'auto';
      p.style.webkitOverflowScrolling = 'touch';
    });
  }

  /* ----------------------------------------------------------
     12.  MAIN RUN
     ---------------------------------------------------------- */
  function run() {
    if (!getPkg()) { console.warn('[SF] package not ready yet'); return; }
    document.querySelectorAll('table').forEach(processTable);
    makeScrollable();
  }

  /* ----------------------------------------------------------
     13.  SCHEDULE + OBSERVER
     ---------------------------------------------------------- */
  let _t = null;
  function schedule(reset) {
    if (reset) {
      invalidateIndexes();
      document.querySelectorAll(`[${HDR_ATTR}]`).forEach(el => el.removeAttribute(HDR_ATTR));
      document.querySelectorAll(`[${CELL_ATTR}]`).forEach(el => el.removeAttribute(CELL_ATTR));
    }
    clearTimeout(_t);
    _t = setTimeout(run, 150);
  }

  function watchCtx() {
    const tryWatch = (key, reset) => {
      if (!(key in window)) return;
      let v = window[key];
      try {
        Object.defineProperty(window, key, {
          configurable: true,
          get() { return v; },
          set(nv) { const ch = nv !== v; v = nv; if (ch) schedule(reset); },
        });
      } catch (_) {}
    };
    tryWatch('currentPlayerId',  true);
    tryWatch('selectedPlayerId', true);
    tryWatch('currentYear',      true);
    tryWatch('selectedYear',     true);
    tryWatch('DATA_PACKAGE',     false);
  }

  function startObserver() {
    new MutationObserver(muts => {
      for (const m of muts) {
        for (const n of m.addedNodes) {
          if (n.nodeType !== 1) continue;
          if (n.tagName === 'TABLE' || n.tagName === 'TBODY' || n.tagName === 'TR' ||
              n.querySelector?.('table,tbody,tr')) {
            schedule(false); return;
          }
        }
      }
    }).observe(document.documentElement, { childList: true, subtree: true });
  }

  /* ----------------------------------------------------------
     14.  BOOTSTRAP
     ---------------------------------------------------------- */
  function bootstrap() {
    watchCtx();
    startObserver();
    run();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bootstrap);
  } else {
    bootstrap();
  }

  /* ----------------------------------------------------------
     15.  DEBUG HELPERS
     ---------------------------------------------------------- */
  window.__sfInject = run;
  window.__sfDiag = function (n = 5) {
    const pkg = getPkg();
    if (!pkg) { console.log('[SF] no package'); return; }
    (pkg.playerGames || []).filter(g => g.hasTeamSixFactors).slice(0, n).forEach(g =>
      console.table({
        player: g.playerName, year: g.year, gameId: g.gameId,
        gameRowId: g.gameRowId, team: g.team, opp: g.opponent,
        teamEFG: g.teamEFG, teamTOV: g.teamTOVPct, teamFTr: g.teamFTr, teamTS: g.teamTS,
        'eFG\u00b1': g.teamEFG_vsOppAllowed, 'TOV\u00b1': g.teamTOVPct_vsOppAllowed,
        'FTr\u00b1': g.teamFTr_vsOppAllowed, 'TS\u00b1': g.teamTS_vsOppAllowed,
      })
    );
  };

  console.log('[SixFactorOverlay] v1.0 loaded');

})();
