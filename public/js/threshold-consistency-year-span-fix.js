(function(){
  const DEFAULTS = { off: 3, def: -5, net: 4, from: 2001, to: 2026 };
  window.__thresholdConsistencyState = window.__thresholdConsistencyState || {...DEFAULTS};

  function n(v){
    if(v === null || v === undefined || v === "") return null;
    const x = parseFloat(String(v).replace("+","").replace("%",""));
    return Number.isFinite(x) ? x : null;
  }

  function pct(a,b){ return b ? Math.round((a/b)*100) + "%" : "—"; }
  function signed(v){ const x=n(v); return x===null ? "—" : (x>0?"+":"") + x.toFixed(1); }

  function readState(){
    const s = window.__thresholdConsistencyState;
    ["FromYear","ToYear","Off","Def","Net"].forEach(k=>{
      const id = "threshold" + k + "Input";
      const el = document.getElementById(id);
      if(!el) return;
      const val = n(el.value);
      if(val === null) return;
      if(k === "FromYear") s.from = val;
      if(k === "ToYear") s.to = val;
      if(k === "Off") s.off = val;
      if(k === "Def") s.def = val;
      if(k === "Net") s.net = val;
    });
    if(s.from > s.to){
      const a = s.from;
      s.from = s.to;
      s.to = a;
    }
    return s;
  }

  function getPlayer(playerId){
    try{ return dataPackage?.players?.[playerId] || {}; }catch(e){ return {}; }
  }

  function rowsFor(table, playerId, s){
    const p = getPlayer(playerId);
    const nbaId = String(p.nbaId || "");
    const name = String(p.name || "").toLowerCase();
    let rows = [];
    try{ rows = dataPackage?.[table] || []; }catch(e){ rows = []; }

    return rows.filter(r=>{
      const y = n(r.year);
      if(y === null || y < s.from || y > s.to) return false;
      const rid = String(r.playerId || "");
      const rn = String(r.nbaId || "");
      const rname = String(r.playerName || "").toLowerCase();
      return rid === playerId || (nbaId && rn === nbaId) || (name && rname === name);
    });
  }

  function evaluate(rows, s){
    const validOff = rows.filter(r=>n(r.rORTG)!==null);
    const validDef = rows.filter(r=>n(r.rDRTG)!==null);
    const validNet = rows.filter(r=>n(r.rNET)!==null);
    const combo = rows.filter(r=>n(r.rORTG)!==null && n(r.rDRTG)!==null && n(r.rNET)!==null);

    const offHit = validOff.filter(r=>n(r.rORTG) >= s.off).length;
    const defHit = validDef.filter(r=>n(r.rDRTG) <= s.def).length;
    const netHit = validNet.filter(r=>n(r.rNET) >= s.net).length;
    const two = combo.filter(r=>n(r.rORTG) >= s.off && n(r.rDRTG) <= s.def).length;
    const all = combo.filter(r=>n(r.rORTG) >= s.off && n(r.rDRTG) <= s.def && n(r.rNET) >= s.net).length;

    return {
      rows: rows.length,
      validOff: validOff.length,
      validDef: validDef.length,
      validNet: validNet.length,
      validCombo: combo.length,
      offHit, defHit, netHit, two, all
    };
  }

  function line(r,k){
    if(k==="off") return `${r.offHit}/${r.validOff} (${pct(r.offHit,r.validOff)})`;
    if(k==="def") return `${r.defHit}/${r.validDef} (${pct(r.defHit,r.validDef)})`;
    if(k==="net") return `${r.netHit}/${r.validNet} (${pct(r.netHit,r.validNet)})`;
    if(k==="two") return `${r.two}/${r.validCombo} (${pct(r.two,r.validCombo)})`;
    if(k==="all") return `${r.all}/${r.validCombo} (${pct(r.all,r.validCombo)})`;
    return "—";
  }

  function makePanel(){
    let panel = document.getElementById("thresholdConsistencyPanel");
    if(!panel){
      panel = document.createElement("section");
      panel.id = "thresholdConsistencyPanel";
      panel.className = "threshold-consistency-panel";
      const anchor = document.getElementById("playerHeader") || document.querySelector(".player-header") || document.querySelector("main") || document.body;
      if(anchor && anchor !== document.body) anchor.insertAdjacentElement("afterend", panel);
      else document.body.insertBefore(panel, document.body.firstChild);
    }

    if(!document.getElementById("thresholdFromYearInput")){
      const s = window.__thresholdConsistencyState;
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
            <label class="threshold-control">From <input id="thresholdFromYearInput" type="number" step="1" value="${s.from}"></label>
            <label class="threshold-control">To <input id="thresholdToYearInput" type="number" step="1" value="${s.to}"></label>
            <label class="threshold-control">rORTG ≥ <input id="thresholdOffInput" type="number" step="0.1" value="${s.off}"></label>
            <label class="threshold-control">rDRTG ≤ <input id="thresholdDefInput" type="number" step="0.1" value="${s.def}"></label>
            <label class="threshold-control">rNET ≥ <input id="thresholdNetInput" type="number" step="0.1" value="${s.net}"></label>
          </div>
        </div>
        <div class="threshold-grid" id="thresholdSummaryGrid"></div>
        <div class="threshold-table-wrap">
          <table class="threshold-table">
            <thead>
              <tr>
                <th>Level</th><th>Rows In Span</th><th>Offense Hits</th><th>Defense Hits</th><th>Net Hits</th><th>Two-Way Hits</th><th>All 3 Hits</th>
              </tr>
            </thead>
            <tbody id="thresholdConsistencyBody"></tbody>
          </table>
        </div>
      `;

      ["thresholdFromYearInput","thresholdToYearInput","thresholdOffInput","thresholdDefInput","thresholdNetInput"].forEach(id=>{
        document.getElementById(id)?.addEventListener("input", ()=>{
          readState();
          if(window.currentPlayerId || typeof currentPlayerId !== "undefined"){
            window.renderThresholdConsistency(window.currentPlayerId || currentPlayerId);
          }
        });
      });
    }

    return panel;
  }

  function row(label,r){
    return `<tr>
      <td>${label}</td>
      <td>${r.rows}</td>
      <td class="threshold-good">${line(r,"off")}</td>
      <td class="threshold-good">${line(r,"def")}</td>
      <td class="threshold-good">${line(r,"net")}</td>
      <td>${line(r,"two")}</td>
      <td>${line(r,"all")}</td>
    </tr>`;
  }

  window.renderThresholdConsistency = function(playerId){
    if(!playerId) return;
    const panel = makePanel();
    const s = readState();

    const game = evaluate(rowsFor("playerGames", playerId, s), s);
    const series = evaluate(rowsFor("playerSeries", playerId, s), s);
    const span = `${Math.round(s.from)}–${Math.round(s.to)}`;

    const grid = document.getElementById("thresholdSummaryGrid");
    if(grid){
      grid.innerHTML = `
        <div class="threshold-card">
          <div class="threshold-label">Offensive Consistency</div>
          <div class="threshold-value">${line(game,"off")}</div>
          <div class="threshold-note">${span} games with rORTG ≥ ${signed(s.off)}. Series: ${line(series,"off")}.</div>
        </div>
        <div class="threshold-card">
          <div class="threshold-label">Defensive Consistency</div>
          <div class="threshold-value">${line(game,"def")}</div>
          <div class="threshold-note">${span} games with rDRTG ≤ ${signed(s.def)}. Series: ${line(series,"def")}.</div>
        </div>
        <div class="threshold-card">
          <div class="threshold-label">Net Consistency</div>
          <div class="threshold-value">${line(game,"net")}</div>
          <div class="threshold-note">${span} games with rNET ≥ ${signed(s.net)}. Series: ${line(series,"net")}.</div>
        </div>
      `;
    }

    const body = document.getElementById("thresholdConsistencyBody");
    if(body) body.innerHTML = row("Games", game) + row("Series", series);

    panel.style.display = (game.rows || series.rows) ? "" : "none";
  };

  function hook(){
    try{
      if(typeof selectPlayer === "function" && !selectPlayer.__thresholdFixedHooked){
        const old = selectPlayer;
        selectPlayer = function(playerId){
          const out = old.apply(this, arguments);
          window.currentPlayerId = playerId;
          setTimeout(()=>window.renderThresholdConsistency(playerId), 0);
          return out;
        };
        selectPlayer.__thresholdFixedHooked = true;
      }
      if(typeof currentPlayerId !== "undefined" && currentPlayerId){
        window.currentPlayerId = currentPlayerId;
        window.renderThresholdConsistency(currentPlayerId);
      }
    }catch(e){}
  }

  if(document.readyState === "loading") document.addEventListener("DOMContentLoaded", hook);
  else hook();
  setTimeout(hook, 500);
  setTimeout(hook, 1500);
})();
