(function(){
  const DEFAULTS = {
    from: 2001,
    to: 2026,
    off: 3,
    def: 5,
    net: 4,
    avgCushion: 0.2,
    minGames: 3
  };

  window.__seriesTranslateState = window.__seriesTranslateState || {...DEFAULTS};

  function n(v){
    if(v === null || v === undefined || v === "") return null;
    const x = parseFloat(String(v).replace("+","").replace("%",""));
    return Number.isFinite(x) ? x : null;
  }

  function signed(v){
    const x = n(v);
    if(x === null) return "—";
    return (x > 0 ? "+" : "") + x.toFixed(1);
  }

  function readFilters(){
    const s = window.__seriesTranslateState;

    const map = {
      seriesTranslateFromYearInput: "from",
      seriesTranslateToYearInput: "to",
      seriesTranslateOffInput: "off",
      seriesTranslateDefInput: "def",
      seriesTranslateNetInput: "net",
      seriesTranslateAvgCushionInput: "avgCushion",
      seriesTranslateMinGamesInput: "minGames"
    };

    Object.entries(map).forEach(([id,key]) => {
      const el = document.getElementById(id);
      if(!el) return;
      const val = n(el.value);
      if(val !== null) s[key] = val;
    });

    if(s.from > s.to){
      const temp = s.from;
      s.from = s.to;
      s.to = temp;
    }

    return s;
  }

  function getPlayer(playerId){
    try { return dataPackage?.players?.[playerId] || {}; }
    catch(e){ return {}; }
  }

  function playerGameRows(playerId, f){
    const p = getPlayer(playerId);
    const nbaId = String(p.nbaId || p.NBA_ID || "");
    const playerName = String(p.name || p.playerName || "").toLowerCase().trim();

    let rows = [];
    try { rows = dataPackage?.playerGames || []; } catch(e){ rows = []; }

    return rows.filter(r => {
      const y = n(r.year);
      if(y === null || y < f.from || y > f.to) return false;

      const rid = String(r.playerId || "");
      const rn = String(r.nbaId || r.NBA_ID || "");
      const rname = String(r.playerName || r.name || "").toLowerCase().trim();

      const playerMatch =
        rid === String(playerId) ||
        (nbaId && rn === nbaId) ||
        (playerName && rname && rname === playerName);

      if(!playerMatch) return false;

      // Only real game-log rows. Do not let rank/helper rows into translator.
      const hasGame = !!(r.date || r.gameId || r.nbaGameId);
      const hasPlayerStats =
        r.MIN !== undefined ||
        r.PTS !== undefined ||
        r.rORTG !== undefined ||
        r.rDRTG !== undefined ||
        r.rNET !== undefined;

      return hasGame && hasPlayerStats;
    });
  }

  function groupSeries(rows, f){
    const map = new Map();

    rows.forEach(r => {
      const key = [
        r.year || "unknown",
        r.team || "team",
        r.opponent || "opp",
        r.seriesCode || r.round || "series"
      ].join("||");

      if(!map.has(key)){
        map.set(key, {
          key,
          year: r.year,
          team: r.team,
          opponent: r.opponent,
          round: r.round,
          seriesCode: r.seriesCode,
          rows: []
        });
      }

      map.get(key).rows.push(r);
    });

    return Array.from(map.values()).map(s => {
      s.rows.sort((a,b) => String(a.date||"").localeCompare(String(b.date||"")));
      return s;
    })
    .filter(s => s.rows.length >= f.minGames)
    .sort((a,b) => {
      const ay = n(a.year) || 0;
      const by = n(b.year) || 0;
      if(ay !== by) return by - ay;
      return String(a.seriesCode||a.opponent||"").localeCompare(String(b.seriesCode||b.opponent||""));
    });
  }

  function metricResult(rows, metric, threshold, direction, f){
    const valid = rows.filter(r => n(r[metric]) !== null);

    const hits = valid.filter(r => {
      const x = n(r[metric]);
      return direction === "up" ? x >= threshold : x <= threshold;
    });

    const avg = valid.length
      ? valid.reduce((sum, r) => sum + n(r[metric]), 0) / valid.length
      : null;

    const hitRate = valid.length ? hits.length / valid.length : 0;

    const majorityRule = hitRate > 0.5;

    const avgCloseEnough = avg === null
      ? false
      : (
          direction === "up"
            ? avg >= (threshold - f.avgCushion)
            : avg <= (threshold + f.avgCushion)
        );

    const halfPlusAverageRule = hitRate >= 0.5 && avgCloseEnough;

    const qualifies = valid.length >= f.minGames && (majorityRule || halfPlusAverageRule);

    return {
      valid: valid.length,
      hits: hits.length,
      avg,
      hitRate,
      majorityRule,
      avgCloseEnough,
      halfPlusAverageRule,
      qualifies,
      reason: majorityRule ? "majority" : (halfPlusAverageRule ? "50% + avg" : "no")
    };
  }

  function analyzeSeries(series, f){
    return series.map(s => {
      const off = metricResult(s.rows, "rORTG", f.off, "up", f);
      const def = metricResult(s.rows, "rDRTG", f.def, "up", f);
      const net = metricResult(s.rows, "rNET", f.net, "up", f);

      return {
        ...s,
        totalGames: s.rows.length,
        off,
        def,
        net,
        twoWay: off.qualifies && def.qualifies,
        allThree: off.qualifies && def.qualifies && net.qualifies
      };
    });
  }

  function yes(v){
    return v ? '<span class="translate-yes">YES</span>' : '<span class="translate-no">no</span>';
  }

  function hitText(x){
    if(!x.valid) return "—";

    const avg = x.avg === null || x.avg === undefined
      ? "—"
      : ((x.avg > 0 ? "+" : "") + x.avg.toFixed(1));

    let badge = "";
    if(x.qualifies && x.reason === "majority") badge = " • maj";
    if(x.qualifies && x.reason === "50% + avg") badge = " • avg";

    return `${x.hits}/${x.valid}${badge} (${avg})`;
  }

  function ensurePanel(){
    let panel = document.getElementById("seriesTranslatePanel");
    if(panel) return panel;

    panel = document.createElement("section");
    panel.id = "seriesTranslatePanel";
    panel.className = "series-translate-panel";

    const s = window.__seriesTranslateState;

    panel.innerHTML = `
      <div class="threshold-consistency-head">
        <div>
          <div class="series-translate-title">Series Translation Consistency</div>
          <div class="series-translate-sub">
            Counts series-level translation from game-by-game impact.
            Majority of games hitting the threshold counts automatically.
            Exactly half only counts when the series average is close enough to the selected threshold.
          </div>
        </div>

        <div class="threshold-controls">
          <label class="threshold-control">From <input id="seriesTranslateFromYearInput" type="number" step="1" value="${s.from}"></label>
          <label class="threshold-control">To <input id="seriesTranslateToYearInput" type="number" step="1" value="${s.to}"></label>
          <label class="threshold-control">rORTG ≥ <input id="seriesTranslateOffInput" type="number" step="0.1" value="${s.off}"></label>
          <label class="threshold-control">rDRTG ≥ <input id="seriesTranslateDefInput" type="number" step="0.1" value="${s.def}"></label>
          <label class="threshold-control">rNET ≥ <input id="seriesTranslateNetInput" type="number" step="0.1" value="${s.net}"></label>
          <label class="threshold-control">Avg Cushion <input id="seriesTranslateAvgCushionInput" type="number" step="0.1" value="${s.avgCushion}"></label>
          <label class="threshold-control">Min Games <input id="seriesTranslateMinGamesInput" type="number" step="1" value="${s.minGames}"></label>
        </div>
      </div>

      <div class="series-translate-grid" id="seriesTranslateGrid"></div>

      <div class="series-translate-table-wrap">
        <table class="series-translate-table">
          <thead>
            <tr>
              <th>Year</th>
              <th>Series</th>
              <th>Opp</th>
              <th>Games</th>
              <th>Off Hits / Avg</th>
              <th>Off Translate</th>
              <th>Def Hits / Avg</th>
              <th>Def Translate</th>
              <th>Net Hits / Avg</th>
              <th>Net Translate</th>
              <th>2-Way</th>
              <th>All 3</th>
            </tr>
          </thead>
          <tbody id="seriesTranslateBody"></tbody>
        </table>
      </div>
    `;

    const anchor =
      document.getElementById("seriesLog") ||
      document.getElementById("playerSeries") ||
      document.querySelector(".series-log") ||
      document.querySelector("[data-section='series-log']") ||
      document.getElementById("gameLog") ||
      document.getElementById("gameLogs") ||
      document.getElementById("playerGameLog") ||
      document.querySelector(".game-log") ||
      document.querySelector("[data-section='game-log']") ||
      document.querySelector("main") ||
      document.body;

    if(anchor && anchor !== document.body && anchor.tagName && anchor.tagName.toLowerCase() !== "main"){
      anchor.insertAdjacentElement("afterend", panel);
    }else if(anchor && anchor !== document.body){
      anchor.appendChild(panel);
    }else{
      document.body.appendChild(panel);
    }

    [
      "seriesTranslateFromYearInput",
      "seriesTranslateToYearInput",
      "seriesTranslateOffInput",
      "seriesTranslateDefInput",
      "seriesTranslateNetInput",
      "seriesTranslateAvgCushionInput",
      "seriesTranslateMinGamesInput"
    ].forEach(id => {
      document.getElementById(id)?.addEventListener("input", () => {
        readFilters();
        try{
          const playerId = window.currentPlayerId || currentPlayerId;
          if(playerId) window.renderSeriesTranslate(playerId);
        }catch(e){}
      });
    });

    return panel;
  }

  function renderCards(results, f){
    const grid = document.getElementById("seriesTranslateGrid");
    if(!grid) return;

    const total = results.length;
    const off = results.filter(r => r.off.qualifies).length;
    const def = results.filter(r => r.def.qualifies).length;
    const net = results.filter(r => r.net.qualifies).length;
    const two = results.filter(r => r.twoWay).length;
    const all = results.filter(r => r.allThree).length;
    const span = `${Math.round(f.from)}–${Math.round(f.to)}`;

    grid.innerHTML = `
      <div class="series-translate-card">
        <div class="series-translate-label">Offense Translates</div>
        <div class="series-translate-value">${off}/${total}</div>
        <div class="series-translate-note">${span}: rORTG ≥ ${signed(f.off)}. Average cushion: ${f.avgCushion}.</div>
      </div>

      <div class="series-translate-card">
        <div class="series-translate-label">Defense Translates</div>
        <div class="series-translate-value">${def}/${total}</div>
        <div class="series-translate-note">${span}: rDRTG ≥ ${signed(f.def)}. Positive is better here.</div>
      </div>

      <div class="series-translate-card">
        <div class="series-translate-label">Net Translates</div>
        <div class="series-translate-value">${net}/${total}</div>
        <div class="series-translate-note">${span}: rNET ≥ ${signed(f.net)}.</div>
      </div>

      <div class="series-translate-card">
        <div class="series-translate-label">Two-Way / All 3</div>
        <div class="series-translate-value">${two}/${total}</div>
        <div class="series-translate-note">All 3 translated in ${all}/${total} series. Min games: ${f.minGames}.</div>
      </div>
    `;
  }

  function renderTable(results){
    const body = document.getElementById("seriesTranslateBody");
    if(!body) return;

    body.innerHTML = results.map(r => `
      <tr>
        <td>${r.year || "—"}</td>
        <td>${r.round || r.seriesCode || "—"}</td>
        <td>${r.opponent || "—"}</td>
        <td>${r.totalGames}</td>
        <td>${hitText(r.off)}</td>
        <td>${yes(r.off.qualifies)}</td>
        <td>${hitText(r.def)}</td>
        <td>${yes(r.def.qualifies)}</td>
        <td>${hitText(r.net)}</td>
        <td>${yes(r.net.qualifies)}</td>
        <td>${yes(r.twoWay)}</td>
        <td>${yes(r.allThree)}</td>
      </tr>
    `).join("");
  }

  window.renderSeriesTranslate = function(playerId){
    if(!playerId) return;

    const panel = ensurePanel();
    const f = readFilters();

    const rows = playerGameRows(playerId, f);
    const series = groupSeries(rows, f);
    const results = analyzeSeries(series, f);

    renderCards(results, f);
    renderTable(results);

    panel.style.display = results.length ? "" : "none";
  };

  function hook(){
    try{
      if(typeof selectPlayer === "function" && !selectPlayer.__seriesTranslateOnlyHooked){
        const old = selectPlayer;
        selectPlayer = function(playerId){
          const out = old.apply(this, arguments);
          window.currentPlayerId = playerId;
          setTimeout(() => window.renderSeriesTranslate(playerId), 0);
          return out;
        };
        selectPlayer.__seriesTranslateOnlyHooked = true;
      }

      if(typeof currentPlayerId !== "undefined" && currentPlayerId){
        window.currentPlayerId = currentPlayerId;
        window.renderSeriesTranslate(currentPlayerId);
      }
    }catch(e){}
  }

  if(document.readyState === "loading") document.addEventListener("DOMContentLoaded", hook);
  else hook();

  setTimeout(hook, 500);
  setTimeout(hook, 1500);
  setTimeout(hook, 3000);
})();
