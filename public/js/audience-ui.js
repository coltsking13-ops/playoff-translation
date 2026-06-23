(function(){
  function qs(sel){ return document.querySelector(sel); }
  function qsa(sel){ return Array.from(document.querySelectorAll(sel)); }

  function textIncludes(el, words){
    const t = (el?.textContent || "").toLowerCase();
    return words.every(w => t.includes(w.toLowerCase()));
  }

  function findSectionByText(words){
    const candidates = qsa("section, .card, .panel, .content-card, div");
    return candidates.find(el => {
      if(!el || el.id === "audienceToolHub") return false;
      const rect = el.getBoundingClientRect();
      if(rect.height < 20) return false;
      return textIncludes(el, words);
    });
  }

  function scrollToTool(kind){
    let target = null;

    if(kind === "search"){
      target = qs("input[type='search'], input[placeholder*='Search'], input[placeholder*='search'], #playerSearch, .search");
    }

    if(kind === "profile"){
      target = qs("#playerHeader, .player-header, .player-profile, #playerProfile") || findSectionByText(["profile"]);
    }

    if(kind === "game"){
      target =
        qs("#gameLog, #gameLogs, #playerGameLog, .game-log, [data-section='game-log']") ||
        findSectionByText(["game", "log"]);
    }

    if(kind === "series"){
      target =
        qs("#seriesLog, #playerSeries, .series-log, [data-section='series-log']") ||
        findSectionByText(["series", "log"]);
    }

    if(kind === "translate"){
      target = qs("#seriesTranslatePanel, .series-translate-panel");
    }

    if(kind === "leaderboards"){
      target =
        qs("#leaderboards, .leaderboards, #leaders, .leaders") ||
        findSectionByText(["leader"]);
    }

    if(target){
      target.scrollIntoView({behavior:"smooth", block:"start"});
      target.classList.add("audience-pulse");
      setTimeout(() => target.classList.remove("audience-pulse"), 900);
    }
  }

  function addToolHub(){
    if(qs("#audienceToolHub")) return;

    const hub = document.createElement("section");
    hub.id = "audienceToolHub";
    hub.className = "audience-tool-hub";
    hub.innerHTML = `
      <h2>Explore the Playoff Lab</h2>
      <p>Pick a tool and jump straight into player profiles, game logs, series logs, leaderboards, or translation consistency.</p>
      <div class="audience-tool-grid">
        <button class="audience-tool-card" data-tool="search">
          <strong>Search Player</strong>
          <span>Find any playoff player fast.</span>
        </button>
        <button class="audience-tool-card" data-tool="profile">
          <strong>Player Profile</strong>
          <span>Overview, seasons, and player context.</span>
        </button>
        <button class="audience-tool-card" data-tool="game">
          <strong>Game Logs</strong>
          <span>Game-by-game playoff production.</span>
        </button>
        <button class="audience-tool-card" data-tool="series">
          <strong>Series Logs</strong>
          <span>Series-by-series playoff results.</span>
        </button>
        <button class="audience-tool-card" data-tool="translate">
          <strong>Translator Tool</strong>
          <span>See which series truly translated.</span>
        </button>
        <button class="audience-tool-card" data-tool="leaderboards">
          <strong>Leaderboards</strong>
          <span>Best peaks, seasons, and playoff runs.</span>
        </button>
      </div>
    `;

    const anchor =
      qs(".hero") ||
      qs("#home") ||
      qs("main") ||
      qs(".container") ||
      document.body;

    if(anchor === document.body){
      document.body.insertBefore(hub, document.body.firstChild);
    }else if(anchor.tagName && anchor.tagName.toLowerCase() === "main"){
      anchor.insertBefore(hub, anchor.firstChild);
    }else{
      anchor.insertAdjacentElement("afterend", hub);
    }

    hub.addEventListener("click", e => {
      const btn = e.target.closest("[data-tool]");
      if(!btn) return;
      scrollToTool(btn.dataset.tool);
    });
  }

  function getCurrentPlayerId(){
    try{
      if(window.currentPlayerId) return window.currentPlayerId;
    }catch(e){}
    try{
      if(typeof currentPlayerId !== "undefined" && currentPlayerId) return currentPlayerId;
    }catch(e){}
    return null;
  }

  function findCurrentPlayer(){
    const id = getCurrentPlayerId();
    try{
      if(id && window.dataPackage?.players?.[id]){
        return {id, ...window.dataPackage.players[id]};
      }
      if(id && typeof dataPackage !== "undefined" && dataPackage?.players?.[id]){
        return {id, ...dataPackage.players[id]};
      }
    }catch(e){}

    return null;
  }

  function addPlayerFace(){
    const player = findCurrentPlayer();
    if(!player) return;

    const nbaId = player.nbaId || player.NBA_ID || player.playerId;
    if(!nbaId) return;

    const name = player.name || player.playerName || "Player";
    const team = player.team || player.lastTeam || player.primaryTeam || "";
    const position = player.position || player.pos || "";

    const header =
      qs("#playerHeader") ||
      qs(".player-header") ||
      qs("#playerProfile") ||
      qs(".player-profile");

    if(!header) return;

    let wrap = qs("#playerFaceWrap");
    if(!wrap){
      wrap = document.createElement("div");
      wrap.id = "playerFaceWrap";
      wrap.className = "player-face-wrap";
      header.insertAdjacentElement("afterbegin", wrap);
    }

    const src = `https://cdn.nba.com/headshots/nba/latest/1040x760/${nbaId}.png`;

    wrap.innerHTML = `
      <img class="player-face-img" src="${src}" alt="${name}" loading="lazy"
           onerror="this.style.display='none'">
      <div class="player-face-meta">
        <div class="player-face-name">${name}</div>
        <div class="player-face-sub">${[position, team, nbaId ? "NBA ID " + nbaId : ""].filter(Boolean).join(" • ")}</div>
      </div>
    `;
  }

  function moveTranslatorLower(){
    // Disabled: repeated translator movement caused flicker.
    return;
  }

  function hookSelectPlayer(){
    try{
      if(typeof selectPlayer === "function" && !selectPlayer.__audienceUiHooked){
        const old = selectPlayer;
        selectPlayer = function(){
          const out = old.apply(this, arguments);
          setTimeout(() => {
            addPlayerFace();
            // moveTranslatorLower disabled;
          }, 60);
          setTimeout(() => {
            addPlayerFace();
            // moveTranslatorLower disabled;
          }, 600);
          return out;
        };
        selectPlayer.__audienceUiHooked = true;
      }
    }catch(e){}
  }

  function run(){
    addToolHub();
    hookSelectPlayer();
    addPlayerFace();
    // moveTranslatorLower disabled;
  }

  if(document.readyState === "loading"){
    document.addEventListener("DOMContentLoaded", run);
  }else{
    run();
  }

  setTimeout(run, 500);
  setTimeout(run, 1500);
  // Removed translator moving interval to prevent flicker.
})();
