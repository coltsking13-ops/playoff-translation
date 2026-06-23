(function(){
  const DEFAULTS = {
    off: 3,
    def: -5,
    net: 4
  };

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

  function getThresholds(){
    const off = n(document.getElementById("thresholdOffInput")?.value);
    const def = n(document.getElementById("thresholdDefInput")?.value);
    const net = n(document.getElementById("thresholdNetInput")?.value);
    return {
      off: off ?? DEFAULTS.off,
      def: def ?? DEFAULTS.def,
      net: net ?? DEFAULTS.net
    };
  }

  function ensurePanel(){
    let panel = document.getElementById("thresholdConsistencyPanel");
    if(panel) return panel;

    panel = document.createElement("section");
    panel.id = "thresholdConsistencyPanel";
    panel.className = "threshold-consistency-panel";
    panel.innerHTML = `
      <div class="threshold-consistency-head">
        <div>
          <div class="threshold-consistency-title">Rating Threshold Consistency</div>
          <div class="threshold-consistency-sub">
            Counts how often this player’s current-data rows hit your playoff impact thresholds.
            Defense uses <strong>rDRTG at or below the target</strong> because lower allowed is better.
          </div>
        </div>
        <div class="threshold-controls">
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
              <th>Rows</th>
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

    const anchor =
      document.getElementById("playerHeader") ||
      document.querySelector(".player-header") ||
      document.getElementById("seasonTableBody")?.closest("section") ||
      document.querySelector("main") ||
      document.body;

    if(anchor && anchor !== document.body){
      anchor.insertAdjacentElement("afterend", panel);
    }else{
      document.body.insertBefore(panel, document.body.firstChild);
    }

    ["thresholdOffInput","thresholdDefInput","thresholdNetInput"].forEach(id => {
      document.getElementById(id)?.addEventListener("input", () => {
        try{
          if(typeof currentPlayerId !== "undefined" && currentPlayerId){
            renderThresholdConsistency(currentPlayerId);
          }
        }catch(e){}
      });
    });

    return panel;
  }

  function getPlayer(playerId){
    try{
      return dataPackage?.players?.[playerId] || {};
    }catch(e){
      return {};
    }
  }

  function rowsFor(table, playerId){
    const p = getPlayer(playerId);
    const nbaId = String(p.nbaId || "");
    const name = String(p.name || "").toLowerCase();

    let rows = [];
    try{ rows = dataPackage?.[table] || []; }catch(e){ rows = []; }

    return rows.filter(r => {
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

  function line(label, result, kind){
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
        <td class="threshold-good">${line(level,result,"off")}</td>
        <td class="threshold-good">${line(level,result,"def")}</td>
        <td class="threshold-good">${line(level,result,"net")}</td>
        <td>${line(level,result,"two")}</td>
        <td>${line(level,result,"all")}</td>
      </tr>
    `;
  }

  function renderCards(gameResult, seriesResult, t){
    const grid = document.getElementById("thresholdSummaryGrid");
    if(!grid) return;

    grid.innerHTML = `
      <div class="threshold-card">
        <div class="threshold-label">Offensive Consistency</div>
        <div class="threshold-value">${line("Games", gameResult, "off")}</div>
        <div class="threshold-note">Games with rORTG ≥ ${signed(t.off)}. Series: ${line("Series", seriesResult, "off")}.</div>
      </div>

      <div class="threshold-card">
        <div class="threshold-label">Defensive Consistency</div>
        <div class="threshold-value">${line("Games", gameResult, "def")}</div>
        <div class="threshold-note">Games with rDRTG ≤ ${signed(t.def)}. Series: ${line("Series", seriesResult, "def")}.</div>
      </div>

      <div class="threshold-card">
        <div class="threshold-label">Net Impact Consistency</div>
        <div class="threshold-value">${line("Games", gameResult, "net")}</div>
        <div class="threshold-note">Games with rNET ≥ ${signed(t.net)}. Series: ${line("Series", seriesResult, "net")}.</div>
      </div>
    `;
  }

  window.renderThresholdConsistency = function(playerId){
    const panel = ensurePanel();
    const t = getThresholds();

    const gameRows = rowsFor("playerGames", playerId);
    const seriesRows = rowsFor("playerSeries", playerId);

    const gameResult = evaluate(gameRows, t);
    const seriesResult = evaluate(seriesRows, t);

    renderCards(gameResult, seriesResult, t);

    const body = document.getElementById("thresholdConsistencyBody");
    if(body){
      body.innerHTML = rowHtml("Games", gameResult) + rowHtml("Series", seriesResult);
    }

    panel.style.display = (gameRows.length || seriesRows.length) ? "" : "none";
  };

  function hookSelectPlayer(){
    try{
      if(typeof selectPlayer === "function" && !selectPlayer.__thresholdConsistencyHooked){
        const original = selectPlayer;
        selectPlayer = function(playerId){
          const result = original.apply(this, arguments);
          setTimeout(() => window.renderThresholdConsistency(playerId), 0);
          return result;
        };
        selectPlayer.__thresholdConsistencyHooked = true;
      }

      if(typeof currentPlayerId !== "undefined" && currentPlayerId){
        window.renderThresholdConsistency(currentPlayerId);
      }
    }catch(e){
      console.warn("Threshold consistency hook waiting:", e);
    }
  }

  if(document.readyState === "loading"){
    document.addEventListener("DOMContentLoaded", hookSelectPlayer);
  }else{
    hookSelectPlayer();
  }

  setTimeout(hookSelectPlayer, 500);
  setTimeout(hookSelectPlayer, 1500);
  setTimeout(hookSelectPlayer, 3500);
})();
