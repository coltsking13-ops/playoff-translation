(function(){
  console.log('NBA HERO FILE LOADED');
  function getDP(){
    try{ if(window.dataPackage) return window.dataPackage; }catch(e){}
    try{ if(typeof dataPackage !== "undefined") return dataPackage; }catch(e){}
    return null;
  }

  function n(v){
    if(v === null || v === undefined || v === "") return null;
    const x = parseFloat(String(v).replace("+","").replace("%",""));
    return Number.isFinite(x) ? x : null;
  }

  function fmt(v, plus=false){
    const x = n(v);
    if(x === null) return "—";
    return (plus && x > 0 ? "+" : "") + x.toFixed(1);
  }

  function esc(s){
    return String(s ?? "").replace(/[&<>"']/g, m => ({
      "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
    }[m]));
  }

  function cls(v){
    const x = n(v);
    if(x === null) return "";
    if(x > 0) return "nba-positive";
    if(x < 0) return "nba-negative";
    return "";
  }

  function initials(name){
    return String(name || "?")
      .split(/\s+/)
      .filter(Boolean)
      .slice(0,2)
      .map(x=>x[0])
      .join("")
      .toUpperCase() || "?";
  }

  function currentId(){
    try{ if(window.currentPlayerId) return String(window.currentPlayerId); }catch(e){}
    try{ if(typeof currentPlayerId !== "undefined" && currentPlayerId) return String(currentPlayerId); }catch(e){}
    return null;
  }

  function selectedPlayer(){
    const dp = getDP();
    if(!dp || !dp.players) return null;

    const id = currentId();
    if(id && dp.players[id]) return { id, ...dp.players[id] };

    return null;
  }

  function allRowsFor(p){
    const dp = getDP();
    if(!dp || !p) return [];

    const sources = []
      .concat(dp.playerSeasons || [])
      .concat(dp.playerSeries || [])
      .concat(dp.playerGames || []);

    const pname = String(p.name || p.playerName || "").toLowerCase();
    const nbaId = String(p.nbaId || p.NBA_ID || "");

    return sources.filter(r => {
      const rid = String(r.playerId || "");
      const rid2 = String(r.nbaId || r.NBA_ID || "");
      const rn = String(r.playerName || r.name || "").toLowerCase();
      return rid === String(p.id) || (nbaId && rid2 === nbaId) || (pname && rn === pname);
    });
  }

  function pick(row, keys){
    for(const k of keys){
      if(row && row[k] !== undefined && row[k] !== null && row[k] !== "") return row[k];
    }
    return null;
  }

  function bestRow(rows){
    if(!rows.length) return {};
    const withStats = rows.filter(r => pick(r, ["PTS/75","PP75","PTS","points","TS%","rTS","rNET"]) !== null);
    return (withStats.length ? withStats : rows).slice().sort((a,b)=>(n(b.year)||0)-(n(a.year)||0))[0] || {};
  }

  function render(){
    const p = selectedPlayer();
    if(!p) return;

    const rows = allRowsFor(p);
    const row = bestRow(rows);

    const name = p.name || p.playerName || row.playerName || "Player";
    const parts = name.split(/\s+/).filter(Boolean);
    const first = parts.slice(0, -1).join(" ") || name;
    const last = parts.length > 1 ? parts[parts.length - 1] : "";
    const bg = (last || first || name).toUpperCase();

    const years = Array.from(new Set(rows.map(r => n(r.year)).filter(Boolean))).sort((a,b)=>a-b);
    const yearText = years.length ? `${years[0]}–${years[years.length-1]}` : (row.year || "—");

    const teams = Array.from(new Set(rows.map(r => r.team).filter(Boolean))).slice(0,4);
    const teamText = teams.length ? teams.join(", ") : (row.team || "NBA");

    const nbaId = p.nbaId || p.NBA_ID || row.nbaId || row.NBA_ID || "";
    const bodyImg = nbaId ? `./public/images/player-bodies/${nbaId}.png` : "";
    const headshot = nbaId ? `https://cdn.nba.com/headshots/nba/latest/1040x760/${nbaId}.png` : "";

    const jersey = p.jersey || p.number || row.jersey || row.number || (nbaId ? String(nbaId).slice(-2) : "");
    const pos = p.position || p.pos || row.position || row.pos || "";

    const pts75 = pick(row, ["PTS/75","PP75","pts75"]);
    const reb = pick(row, ["REB/G","RPG","rebounds","REB"]);
    const ast = pick(row, ["AST/G","APG","assists","AST"]);
    const rts = pick(row, ["rTS","RTS"]);
    const radjts = pick(row, ["rAdjTS","RADJTS"]);
    const rnet = pick(row, ["rNET","RNET"]);

    let shell = document.getElementById("nbaPlayerHeroShell");
    if(!shell){
      shell = document.createElement("section");
      shell.id = "nbaPlayerHeroShell";
      shell.className = "nba-player-hero-shell";
    }

    shell.innerHTML = `
      <div id="nbaPlayerHero" class="nba-player-hero">
        <div class="nba-player-hero-topbar">
          <div class="nba-player-logo"><span class="nba-logo-mark"></span><span>NBA</span></div>
          <div class="nba-player-nav">
            <span>Scores</span>
            <span>Schedule</span>
            <span>News</span>
            <span>Stats</span>
            <span>Players</span>
            <span>Teams</span>
          </div>
          <div class="nba-player-avatar">${esc(initials(name))}</div>
        </div>

        <div class="nba-bg-word">${esc(bg)}</div>

        <div class="nba-hero-main">
          <div class="nba-hero-left">
            <div class="nba-favorite"><span class="nba-favorite-dot">☆</span> Favorite</div>
            <h1 class="nba-hero-name">
              ${esc(first)}${last ? `<br>${esc(last)}` : ""}
            </h1>

            <div class="nba-hero-team">
              <span class="nba-team-dot"></span>
              <span>${esc(teamText)}</span>
            </div>

            <div class="nba-bio-grid">
              <div>
                <div class="nba-bio-label">Years</div>
                <div class="nba-bio-value">${esc(yearText)}</div>
              </div>
              <div>
                <div class="nba-bio-label">Player ID</div>
                <div class="nba-bio-value">${esc(nbaId || p.id || "—")}</div>
              </div>
            </div>
          </div>

          <div class="nba-hero-center">
            <div class="nba-hero-image-ring"></div>
            <div class="nba-hero-number">${esc(jersey)}</div>
            <div class="nba-hero-position">${esc(pos)}</div>
            ${
              nbaId
              ? `<img class="nba-hero-img" src="${esc(bodyImg)}" alt="${esc(name)}" loading="lazy"
                  onerror="this.onerror=function(){this.outerHTML='<div class=&quot;nba-hero-fallback&quot;>${esc(initials(name))}</div>'}; this.src='${esc(headshot)}'">`
              : `<div class="nba-hero-fallback">${esc(initials(name))}</div>`
            }
          </div>

          <div class="nba-hero-right">
            <div class="nba-score-card">
              <div class="nba-score-tabs">
                <div>Last Series</div>
                <div>Next View</div>
              </div>
              <div class="nba-score-main">
                <div class="nba-score-team">
                  <div class="nba-score-abbr">${esc(row.opponent || "OPP")}</div>
                  <div class="nba-score-num">${esc(fmt(pick(row, ["ORTG","offRtg","ORtg"])))}</div>
                </div>
                <div class="nba-score-status">Rating<br>Profile</div>
                <div class="nba-score-team">
                  <div class="nba-score-abbr">${esc(row.team || "TEAM")}</div>
                  <div class="nba-score-num">${esc(fmt(pick(row, ["NET","net","Net"])))}</div>
                </div>
              </div>
            </div>

            <div class="nba-video-row">
              <div class="nba-video-card"></div>
              <div class="nba-video-card"></div>
            </div>
          </div>
        </div>

        <div class="nba-bio-lines">
          <div class="nba-info-lines">
            <div class="nba-info-line"><span>Born</span><span>${esc(p.birthDate || p.born || "—")}</span></div>
            <div class="nba-info-line"><span>From</span><span>${esc(p.country || p.school || p.from || "—")}</span></div>
          </div>
          <div></div>
          <div class="nba-info-lines nba-right-lines">
            <div class="nba-info-line"><span>Debut</span><span>${esc(p.fromYear || years[0] || "—")}</span></div>
            <div class="nba-info-line"><span>Latest</span><span>${esc(row.year || years[years.length-1] || "—")}</span></div>
            <div class="nba-info-line"><span>Team</span><span>${esc(row.team || teamText || "—")}</span></div>
          </div>
        </div>

        <div class="nba-floating-stats">
          <div class="nba-stat-card">
            <div class="nba-stat-label">Points Per 75</div>
            <div class="nba-stat-value">${esc(fmt(pts75))}</div>
            <div class="nba-stat-sub ${cls(rts)}">${esc(fmt(rts, true))} rTS</div>
          </div>
          <div class="nba-stat-card dark">
            <div class="nba-stat-label">Adjusted TS</div>
            <div class="nba-stat-value">${esc(fmt(pick(row, ["AdjTS%","ADJTS%","AdjTS"])))}</div>
            <div class="nba-stat-sub ${cls(radjts)}">${esc(fmt(radjts, true))} rAdjTS</div>
          </div>
          <div class="nba-stat-card">
            <div class="nba-stat-label">Net Impact</div>
            <div class="nba-stat-value ${cls(rnet)}">${esc(fmt(rnet, true))}</div>
            <div class="nba-stat-sub">rNET</div>
          </div>
        </div>
      </div>
    `;

    const hub = document.getElementById("finalToolHub");
    if(hub){
      hub.insertAdjacentElement("afterend", shell);
    }else{
      const main = document.querySelector("main") || document.querySelector(".container") || document.body;
      main.insertBefore(shell, main.firstChild);
    }
  }

  function hook(){
    try{
      if(typeof selectPlayer === "function" && !selectPlayer.__nbaHeroHooked){
        const old = selectPlayer;
        selectPlayer = function(){
          const out = old.apply(this, arguments);
          setTimeout(render, 50);
          setTimeout(render, 500);
          return out;
        };
        selectPlayer.__nbaHeroHooked = true;
      }
    }catch(e){}
    render();
  }

  if(document.readyState === "loading"){
    document.addEventListener("DOMContentLoaded", hook);
  }else{
    hook();
  }

  setTimeout(hook, 700);
  setTimeout(render, 1600);
  setInterval(render, 2500);
})();
