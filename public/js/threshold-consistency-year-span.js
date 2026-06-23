(function(){
  const DEFAULTS = { off: 3, def: -5, net: 4, from: 2001, to: 2026 };

  function n(v){
    if(v === null || v === undefined || v === "" || Number.isNaN(v)) return null;
    const x = parseFloat(String(v).replace("+","").replace("%",""));
    return Number.isFinite(x) ? x : null;
  }

  function pct(hit,total){
    if(!total) return "—";
    return Math.round((hit / total) * 100) + "%";
  }

  function signed(v){
    const x = n(v);
    if(x === null) return "—";
    return (x > 0 ? "+" : "") + x.toFixed(1);
  }

  function getPlayer(playerId){
    try{ return dataPackage?.players?.[playerId] || {}; }
    catch(e){ return {}; }
  }

  function getFilters(){
    const off = n(document.getElementById("thresholdOffInput")?.value);
    const def = n(document.getElementById("thresholdDefInput")?.value);
    const net = n(document.getElementById("thresholdNetInput")?.value);
    const from = n(document.getElementById("thresholdFromYearInput")?.value);
    const to = n(document.getElementById("thresholdToYearInput")?.value);

    let y1 = from ?? DEFAULTS.from;
    let y2 = to ?? DEFAULTS.to;
    if(y1 > y2) [y1, y2] = [y2, y1];

    return {
      off: off ?? DEFAULTS.off,
      def: def ?? DEFAULTS.def,
      net: net ?? DEFAULTS.net,
      from: y1,
      to: y2
    };
  }

  function rowsFor(table, playerId, filters){
    const p = getPlayer(playerId);
    const nbaId = String(p.nbaId || "");
    const name = String(p.name || "").toLowerCase();

    let rows = [];
    try{ rows = dataPackage?.[table] || []; }catch(e){ rows = []; }

    return rows.filter(r => {
      const y = n(r.year);
      if(y === null || y < filters.from || y > filters.to) return false;

      const rid = String(r.playerId || "");
      const rn = String(r.nbaId || "");
      const rname = String(r.playerName || "").toLowerCase();

      return rid === playerId || (nbaId && rn === nbaId) || (name && rname === name);
    });
  }

  function evaluate(rows, t){
    const validOff = rows.filter(r => n(r.rORTG) !== null);
    const validDef = rows.filter(r => n(r.rDRTG) !== null);
    const validNet = rows.filter(r => n(r.rNET) !== null);

    const offHit = validOff.filter(r => n(r.rORTG) >= t.off);
    const defHit = validDef.filter(r => n(r.rDRTG) <= t.def);
    const netHit = validNet.filter(r => n(r.rNET) >= t.net);

    const validCombo = rows.filter(r => n(r.rORTG) !== null && n(r.rDRTG) !== null && n(r.rNET) !== null);
    const twoWayHit = validCombo.filter(r => n(r.rORTG) >= t.off && n(r.rDRTG) <= t.def);
    const allThreeHit = validCombo.filter(r => n(r.rORTG) >= t.off && n(r.rDRTG) <= t.def && n(r.rNET) >= t.net);

    return {
      rows: rows.length,
      validOff: validOff.length,
      validDef: validDef.length,
      validNet: validNet.length,
      validCombo: validCombo.length,
      offHit: offHit.length,
      defHit: defHit.length,
      netHit: netHit.length,
      twoWayHit: twoWayHit.length,
      allThreeHit: allThreeHit.length
    };
  }

  function line(result, kind){
    if(kind === "off") return `${result.offHit}/${result.validOff} (${pct(result.offHit,result.validOff)})`;
    if(kind === "def") return `${result.defHit}/${result.validDef} (${pct(result.defHit,result.validDef)})`;
    if(kind === "net") return `${result.netHit}/${result.validNet} (${pct(result.netHit,result.validNet)})`;
    if(kind === "two") return `${result.twoWayHit}/${result.validCombo} (${pct(result.twoWayHit,result.validCombo)})`;
    if(kind === "all") return `${result.allThreeHit}/${result.validCombo} (${pct(result.allThreeHit,result.validCombo)})`;
    return "—";
  }

  function rowHtml(level, result){
    return `
      <tr>
        <td>${level}</td>
        <td>${result.rows}</td>
        <td class="threshold-good">${line(result,"off")}</td>
        <td class="threshold-good">${line(result,"def")}</td>
        <td class="threshold-good">${line(result,"net")}</td>
        <td>${line(result,"two")}</td>
        <td>${line(result,"all")}</td>
      </tr>
    `;
  }

  function ensurePanel(){
    let panel = document.getElementById("thresholdConsistencyPanel");

    if(!panel){
      panel = document.createElement("section");
      panel.id = "thresholdConsistencyPanel";
      panel.className = "threshold-consistency-panel";

      const anchor =
        document.getElementById("playerHeader") ||
        document.querySelector(".player-header") ||
        document.getElementById("seasonTableBody")?.closest("section") ||
        document.querySelector("main") ||
        document.body;

      if(anchor && anchor !== document.body) anchor.insertAdjacentElement("afterend", panel);
      else document.body.insertBefore(panel, document.body.firstChild);
    }

    panel.innerHTML = `
      <div class="threshold-consistency-head">
        <div>
          <div class="threshold-consistency-title">Rating Threshold Consistency</div>
          <div class="threshold-consistency-sub">
            Pick a year span and count how often this player hit your rORTG, rDRTG, and rNET thresholds.
            Defense uses <strong>rDRTG ≤ target</strong> because lower defensive rating is better.
          </div>
        </div>

        <div class="threshold-controls">
          <label class="threshold-control">From <input id="thresholdFromYearInput" type="number" step="1" value="${DEFAULTS.from}"></label>
          <label class="threshold-control">To <input id="thresholdToYearInput" type="number" step="1" value="${DEFAULTS.to}"></label>
          <label class="threshold-control">rORTG ≥ <input id="thresholdOffInput" type="number" step="0.1" value="${DEFAULTS.off}"></label>
          <label class="threshold-control">rDRTG ≤ <input id="thresholdDefInput" type="number" step="0.1" value="${DEFAULTS.def}"></label>
          <label class="threshold-control">rNET ≥ <input id="thresholdNetInput" type="number" step="0.1" value="${DEFAULTS.net}"></label>
        </div>
      </div>

      <div class="threshold-grid" id="thresholdSummaryGrid"></div>

      <div class="threshold-table-wrap">
        <table class="threshold-table">
          <thead>
            <tr>
              <th>Level</th>
              <th>Rows In Span</th>
              <th>Offense Hits</th>
              <th>Defense Hits</th>
              <th>Net Hits</th>
              <th>Two-Way Hits</th>
              <th>All 3 Hits</th>
            </tr>
          </thead>
          <tbody id="thresholdConsistencyBody"></tbody>
        </table>
      </div>
    `;

    ["thresholdFromYearInput","thresholdToYearInput","thresholdOffInput","thresholdDefInput","thresholdNetInput"].forEach(id => {
      document.getElementById(id)?.addEventListener("input", () => {
        try{
          if(typeof currentPlayerId !== "undefined" && currentPlayerId){
            window.renderThresholdConsistency(currentPlayerId);
          }
        }catch(e){}
      });
    });

    return panel;
  }

  function renderCards(gameResult, seriesResult, t){
    const grid = document.getElementById("thresholdSummaryGrid");
    if(!grid) return;

    const span = `${Math.round(t.from)}–${Math.round(t.to)}`;

    grid.innerHTML = `
      <div class="threshold-card">
        <div class="threshold-label">Offensive Consistency</div>
        <div class="threshold-value">${line(gameResult, "off")}</div>
        <div class="threshold-note">${span} games with rORTG ≥ ${signed(t.off)}. Series: ${line(seriesResult, "off")}.</div>
      </div>

      <div class="threshold-card">
        <div class="threshold-label">Defensive Consistency</div>
        <div class="threshold-value">${line(gameResult, "def")}</div>
        <div class="threshold-note">${span} games with rDRTG ≤ ${signed(t.def)}. Series: ${line(seriesResult, "def")}.</div>
      </div>

      <div class="threshold-card">
        <div class="threshold-label">Net Consistency</div>
        <div class="threshold-value">${line(gameResult, "net")}</div>
        <div class="threshold-note">${span} games with rNET ≥ ${signed(t.net)}. Series: ${line(seriesResult, "net")}.</div>
      </div>
    `;
  }

  window.renderThresholdConsistency = function(playerId){
    const panel = ensurePanel();
    const t = getFilters();

    const gameRows = rowsFor("playerGames", playerId, t);
    const seriesRows = rowsFor("playerSeries", playerId, t);

    const gameResult = evaluate(gameRows, t);
    const seriesResult = evaluate(seriesRows, t);

    renderCards(gameResult, seriesResult, t);

    const body = document.getElementById("thresholdConsistencyBody");
    if(body){
      body.innerHTML = rowHtml("Games", gameResult) + rowHtml("Series", seriesResult);
    }

    panel.style.display = (gameRows.length || seriesRows.length) ? "" : "none";
  };

  function hook(){
    try{
      if(typeof selectPlayer === "function" && !selectPlayer.__thresholdYearSpanHooked){
        const original = selectPlayer;
        selectPlayer = function(playerId){
          const result = original.apply(this, arguments);
          setTimeout(() => window.renderThresholdConsistency(playerId), 0);
          return result;
        };
        selectPlayer.__thresholdYearSpanHooked = true;
      }

      if(typeof currentPlayerId !== "undefined" && currentPlayerId){
        window.renderThresholdConsistency(currentPlayerId);
      }
    }catch(e){}
  }

  if(document.readyState === "loading") document.addEventListener("DOMContentLoaded", hook);
  else hook();

  setTimeout(hook, 500);
  setTimeout(hook, 1500);
  setTimeout(hook, 3000);
})();
