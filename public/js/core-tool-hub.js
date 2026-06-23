(function(){
  function qsa(sel, root=document){ return Array.from(root.querySelectorAll(sel)); }
  function qs(sel, root=document){ return root.querySelector(sel); }
  function norm(s){ return String(s || "").toLowerCase().replace(/\s+/g, " ").trim(); }

  function isVisible(el){
    if(!el) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  }

  function bestContainer(el){
    if(!el) return null;

    const preferred = [
      "section",
      ".card",
      ".panel",
      ".content-card",
      ".profile-section",
      ".tool-section",
      ".analytics-section",
      ".lab-section",
      ".glass-card",
      ".table-wrap"
    ];

    for(const sel of preferred){
      const c = el.closest(sel);
      if(c && c !== document.body) return c;
    }

    let cur = el;
    for(let i=0; i<5 && cur && cur.parentElement && cur.parentElement !== document.body; i++){
      cur = cur.parentElement;
      if(norm(cur.textContent).length < 12000) return cur;
    }

    return el;
  }

  function findByText(phrases){
    const nodes = qsa("h1,h2,h3,h4,h5,button,summary,label,.title,.section-title,.card-title,.panel-title,div,span");
    for(const el of nodes){
      if(!isVisible(el)) continue;
      const t = norm(el.textContent);
      if(!t || t.length > 450) continue;
      if(phrases.some(p => t.includes(norm(p)))) return bestContainer(el);
    }
    return null;
  }

  function findSearch(){
    return (
      qs("input[type='search']") ||
      qs("input[placeholder*='Search']") ||
      qs("input[placeholder*='search']") ||
      qs("#playerSearch") ||
      findByText(["search player", "player search"])
    );
  }

  function findGameLog(){
    return (
      qs("#gameLog") ||
      qs("#gameLogs") ||
      qs("#playerGameLog") ||
      qs(".game-log") ||
      findByText(["game log", "game logs"])
    );
  }

  function findSeriesLog(){
    return (
      qs("#seriesLog") ||
      qs("#seriesLogs") ||
      qs("#playerSeries") ||
      qs(".series-log") ||
      findByText(["series log", "series logs"])
    );
  }

  function findSeriesLab(){
    return (
      qs("#seriesTranslatePanel") ||
      qs(".series-translate-panel") ||
      findByText(["series translation consistency", "translator tool", "series lab"])
    );
  }

  function findGameLab(){
    return (
      findByText(["game stretch", "custom game stretch", "game stretch lab", "build game stretch"]) ||
      findByText(["best game stretch", "game lab"])
    );
  }

  function findYearLab(){
    return (
      findByText(["year stretch", "custom year stretch", "build year stretch"]) ||
      findByText(["multi-year playoff stretch", "year lab"])
    );
  }

  function jump(kind){
    let target = null;

    if(kind === "search") target = findSearch();
    if(kind === "game-log") target = findGameLog();
    if(kind === "series-log") target = findSeriesLog();
    if(kind === "series-lab") target = findSeriesLab();
    if(kind === "game-lab") target = findGameLab();
    if(kind === "year-lab") target = findYearLab();

    if(!target){
      alert("That section is not visible on this page yet. Pick/search a player first, then try again.");
      return;
    }

    target.classList.add("core-section-anchor");
    target.scrollIntoView({behavior:"smooth", block:"start"});
    target.classList.add("core-pulse");
    setTimeout(() => target.classList.remove("core-pulse"), 1000);
  }

  function addHub(){
    if(qs("#coreToolHub")) return;

    const hub = document.createElement("section");
    hub.id = "coreToolHub";
    hub.className = "core-tool-hub";
    hub.innerHTML = `
      <h2>Playoff Lab Tools</h2>
      <p>Jump straight to the main tools. Nothing here hides your logs or labs.</p>
      <div class="core-tool-grid">
        <button class="core-tool-card" data-core-tool="search">
          <strong>Search Player</strong>
          <span>Find a player profile fast.</span>
        </button>
        <button class="core-tool-card" data-core-tool="series-log">
          <strong>Series Logs</strong>
          <span>Series-by-series playoff table.</span>
        </button>
        <button class="core-tool-card" data-core-tool="game-log">
          <strong>Game Logs</strong>
          <span>Game-by-game playoff table.</span>
        </button>
        <button class="core-tool-card" data-core-tool="series-lab">
          <strong>Series Lab</strong>
          <span>Translation consistency tool.</span>
        </button>
        <button class="core-tool-card" data-core-tool="game-lab">
          <strong>Game Lab</strong>
          <span>Custom game stretch tool.</span>
        </button>
        <button class="core-tool-card" data-core-tool="year-lab">
          <strong>Year Stretch Lab</strong>
          <span>Custom multi-year stretch builder.</span>
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
      const btn = e.target.closest("[data-core-tool]");
      if(!btn) return;
      jump(btn.dataset.coreTool);
    });
  }

  function unhideCleanupDamage(){
    qsa(".ui-hidden-by-cleanup").forEach(el => {
      el.classList.remove("ui-hidden-by-cleanup");
      el.style.display = "";
    });
  }

  function run(){
    unhideCleanupDamage();
    addHub();
  }

  if(document.readyState === "loading"){
    document.addEventListener("DOMContentLoaded", run);
  }else{
    run();
  }

  setTimeout(run, 500);
  setTimeout(run, 1500);
})();
