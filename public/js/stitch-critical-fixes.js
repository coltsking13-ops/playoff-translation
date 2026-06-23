(function(){
  console.log("STITCH CRITICAL FIXES LOADED");

  function qsa(sel, root=document){ return Array.from(root.querySelectorAll(sel)); }
  function qs(sel, root=document){ return root.querySelector(sel); }

  function norm(s){
    return String(s || "").toLowerCase().replace(/\s+/g," ").trim();
  }

  function cleanupDuplicates(){
    qsa("#ptlSideFeatureNav,.ptl-side-feature-nav,#ptlReferenceHome,#ptlFeaturePages,#nbaForceHeroShell,#nbaPlayerHeroShell,#finalToolHub,.final-tool-hub,.audience-tool-hub,.core-tool-hub").forEach(el => {
      if(!el.closest("#stitchApp")) el.remove();
    });
  }

  function hideBadExplorerOverlay(){
    qsa("body *").forEach(el => {
      const t = norm(el.textContent);
      if(t.includes("optimize strategy explorer")){
        const box = el.closest("[role='dialog'],.dropdown,.popover,.tooltip,.card,.panel,div");
        if(box && !box.closest(".stitch-feature-content")){
          box.setAttribute("data-stitch-hidden-overlay","true");
          box.classList.add("stitch-kill-overlay");
        }else if(box){
          box.setAttribute("data-stitch-hidden-overlay","true");
          box.classList.add("stitch-kill-overlay");
        }
      }
    });
  }

  function activePageId(){
    const p = qs(".stitch-page.active");
    return p ? p.dataset.page : "home";
  }

  function syncActiveNav(){
    const id = activePageId();
    qsa(".stitch-nav button,.stitch-mobile-bottom button").forEach(btn => {
      btn.classList.toggle("active", btn.dataset.page === id);
    });
  }

  function enforcePageIsolation(){
    const active = activePageId();

    qsa(".stitch-page").forEach(page => {
      const isActive = page.dataset.page === active;
      page.classList.toggle("active", isActive);
      page.style.display = isActive ? "block" : "none";
    });

    if(active !== "home"){
      qsa(".stitch-home .stitch-bento,.stitch-home .stitch-watermark,.stitch-home .stitch-hero-grid").forEach(el => {
        el.style.display = "none";
      });
    }else{
      qsa(".stitch-home .stitch-bento,.stitch-home .stitch-watermark,.stitch-home .stitch-hero-grid").forEach(el => {
        el.style.display = "";
      });
    }
  }

  function getDataPackage(){
    try{ if(window.dataPackage) return window.dataPackage; }catch(e){}
    try{ if(typeof dataPackage !== "undefined") return dataPackage; }catch(e){}
    return null;
  }

  function getCurrentPlayerId(){
    try{ if(window.currentPlayerId) return String(window.currentPlayerId); }catch(e){}
    try{ if(typeof currentPlayerId !== "undefined" && currentPlayerId) return String(currentPlayerId); }catch(e){}
    return "";
  }

  function selectedPlayerName(){
    const selectors = [
      "#playerName",
      ".player-name",
      ".player-title",
      "#playerHeader h1",
      "#playerHeader h2",
      ".selected-player"
    ];

    for(const sel of selectors){
      const el = qs(sel);
      const t = el && String(el.textContent || "").trim();
      if(t && t.length > 2 && t.length < 80) return t;
    }

    return "";
  }

  function playerSeriesRows(){
    const dp = getDataPackage();
    if(!dp) return [];

    const series = dp.playerSeries || dp.seriesRows || [];
    if(!Array.isArray(series)) return [];

    const pid = getCurrentPlayerId();
    const pname = selectedPlayerName().toLowerCase();

    let rows = series.filter(r => {
      const rid = String(r.playerId || "");
      const rn = String(r.playerName || r.name || "").toLowerCase();
      return (pid && rid === pid) || (pname && rn === pname);
    });

    if(!rows.length && pname){
      rows = series.filter(r => String(r.playerName || r.name || "").toLowerCase().includes(pname));
    }

    if(!rows.length){
      const lebron = series.filter(r => String(r.playerName || r.name || "").toLowerCase().includes("lebron"));
      if(lebron.length) rows = lebron;
    }

    rows = rows.slice().sort((a,b) => {
      const ay = Number(a.year || a.season || 0);
      const by = Number(b.year || b.season || 0);
      if(ay !== by) return ay - by;
      return String(a.round || a.series || "").localeCompare(String(b.round || b.series || ""));
    });

    return rows;
  }

  function cellBlank(td){
    return !String(td.textContent || "").trim();
  }

  function fixTranslateTableBlanks(){
    const tables = qsa("table").filter(table => {
      const h = norm(table.querySelector("thead")?.textContent || table.textContent || "");
      return h.includes("off hits") && h.includes("net hits") && h.includes("translate");
    });

    if(!tables.length) return;

    const rows = playerSeriesRows();
    if(!rows.length) return;

    tables.forEach(table => {
      const trs = qsa("tbody tr", table);
      trs.forEach((tr, i) => {
        const cells = qsa("td", tr);
        if(cells.length < 4) return;

        const r = rows[i];
        if(!r) return;

        const year = r.year || r.season || "";
        const series = r.round || r.series || r.seriesName || r.playoffRound || "";
        const opp = r.opponent || r.opp || r.OPP || r.opponentTeam || "";
        const games = r.games || r.GP || r.G || r.gp || "";

        if(cellBlank(cells[0])) cells[0].textContent = year;
        if(cellBlank(cells[1])) cells[1].textContent = series;
        if(cellBlank(cells[2])) cells[2].textContent = opp;
        if(cellBlank(cells[3])) cells[3].textContent = games;
      });
    });
  }

  function normalizeTranslateCards(){
    qsa(".stitch-feature-content .summary-card,.stitch-feature-content .translate-card,.stitch-feature-content .translation-card").forEach(card => {
      card.style.padding = "20px";
      qsa("p,small,span", card).forEach(el => {
        if(!el.closest("table")){
          el.style.fontSize = "13px";
          el.style.lineHeight = "18px";
        }
      });
    });
  }

  function run(){
    cleanupDuplicates();
    hideBadExplorerOverlay();
    syncActiveNav();
    enforcePageIsolation();
    fixTranslateTableBlanks();
    normalizeTranslateCards();
  }

  if(document.readyState === "loading"){
    document.addEventListener("DOMContentLoaded", run);
  }else{
    run();
  }

  document.addEventListener("click", () => setTimeout(run, 80), true);
  document.addEventListener("input", () => setTimeout(run, 80), true);

  setTimeout(run, 300);
  setTimeout(run, 1000);
  setTimeout(run, 2500);

  const obs = new MutationObserver(() => {
    clearTimeout(window.__stitchFixTimer);
    window.__stitchFixTimer = setTimeout(run, 120);
  });

  obs.observe(document.body, {childList:true, subtree:true});
})();
