(function(){
  console.log("STITCH AUDIT FIX V2 LOADED");

  function qs(sel, root=document){ return root.querySelector(sel); }
  function qsa(sel, root=document){ return Array.from(root.querySelectorAll(sel)); }
  function norm(s){ return String(s || "").toLowerCase().replace(/\s+/g," ").trim(); }

  function cleanupDuplicateUi(){
    qsa("#ptlSideFeatureNav,.ptl-side-feature-nav,#ptlReferenceHome,#ptlFeaturePages,#nbaForceHeroShell,#nbaPlayerHeroShell,#finalToolHub,.final-tool-hub,.audience-tool-hub,.core-tool-hub,.ptl-reference-app,.ptl-feature-pages").forEach(el => {
      if(!el.closest("#stitchApp")) el.remove();
    });
  }

  function activePageId(){
    const p = qs(".stitch-page.active");
    return p ? p.dataset.page : "home";
  }

  function syncNav(){
    const id = activePageId();
    qsa(".stitch-nav button,.stitch-mobile-bottom button").forEach(btn => {
      btn.classList.toggle("active", btn.dataset.page === id);
    });
  }

  function isolatePages(){
    const id = activePageId();

    qsa(".stitch-page").forEach(page => {
      const active = page.dataset.page === id;
      page.classList.toggle("active", active);
      page.style.display = active ? "block" : "none";
    });

    qsa(".stitch-home .stitch-bento,.stitch-home .stitch-watermark,.stitch-home .stitch-hero-grid").forEach(el => {
      el.style.display = id === "home" ? "" : "none";
    });
  }

  function moveSearchInputIfNeeded(){
    const searchContent = qs("#stitchContent_search");
    if(!searchContent) return;

    const visibleSearch = qs("#searchInput", searchContent);
    if(visibleSearch) return;

    const realInput = qs("#searchInput");
    if(!realInput) return;

    const box = realInput.closest(".search-box-container") || realInput.parentElement;
    if(!box) return;

    const wrap = document.createElement("div");
    wrap.className = "table-section stitch-real-search-box";
    wrap.innerHTML = `<div class="section-title">Search Player<small>Type a player name to open their playoff profile.</small></div>`;
    wrap.appendChild(box);
    searchContent.insertBefore(wrap, searchContent.firstChild);
  }

  function restyleFeaturedPlayers(){
    const searchContent = qs("#stitchContent_search");
    if(!searchContent) return;

    qsa("button,a,.chip,.featured-chip,[role='button']", searchContent).forEach(el => {
      el.style.cursor = "pointer";
      el.setAttribute("title", el.textContent.trim() || "Open player");
    });

    qsa(".note-pill", searchContent).forEach(el => {
      if(norm(el.textContent).includes("updated")){
        el.classList.add("live-badge");
      }
    });
  }

  function hideBadOverlay(){
    qsa("body *").forEach(el => {
      const t = norm(el.textContent);
      if(t.includes("optimize strategy explorer")){
        const box = el.closest("[role='dialog'],.dropdown,.popover,.tooltip,.card,.panel,div") || el;
        box.setAttribute("data-stitch-hidden-overlay","true");
        box.classList.add("stitch-kill-overlay");
      }
    });
  }

  function normalizeYesNo(){
    qsa("#stitchContent_translate td,#stitchContent_translate span").forEach(el => {
      const t = norm(el.textContent);
      if(t === "yes") el.textContent = "YES";
      if(t === "no") el.textContent = "NO";
    });
  }

  function fillTranslateBlankRows(){
    const tables = qsa("#stitchContent_translate table").filter(table => {
      const txt = norm(table.textContent);
      return txt.includes("off hits") || txt.includes("off translate") || txt.includes("net hits");
    });

    tables.forEach(table => {
      let last = ["","","",""];

      qsa("tbody tr", table).forEach(tr => {
        const cells = qsa("td", tr);
        if(cells.length < 4) return;

        for(let i=0;i<4;i++){
          const value = String(cells[i].textContent || "").trim();
          if(value){
            last[i] = value;
          }else if(last[i]){
            cells[i].textContent = last[i];
            cells[i].style.color = "#64748b";
          }
        }
      });
    });
  }

  function fixSeriesButtonLabel(){
    const series = qs("#stitchContent_series");
    if(!series) return;

    qsa("button,a", series).forEach(btn => {
      const t = String(btn.textContent || "");
      if(t.includes("Year Log")){
        btn.textContent = t.replace("Year Log", "Series Log");
      }
    });
  }

  function addEmptyStates(){
    [
      ["series", "Search for a player to see their full playoff series breakdown."],
      ["games", "Select a player to view their full playoff game log, including game-level context."]
    ].forEach(([id, msg]) => {
      const content = qs(`#stitchContent_${id}`);
      if(!content) return;

      const table = qs("table", content);
      const rows = qsa("tbody tr", content).filter(r => r.textContent.trim());
      const already = qs(".stitch-empty-state", content);

      if(!table && !already){
        const div = document.createElement("div");
        div.className = "stitch-empty-state";
        div.textContent = msg;
        content.appendChild(div);
      }else if(table && rows.length === 0 && !already){
        const div = document.createElement("div");
        div.className = "stitch-empty-state";
        div.textContent = msg;
        table.closest(".table-section,section,div")?.appendChild(div);
      }
    });
  }

  function plainLanguageCopy(){
    const games = qs("#stitchContent_games");
    if(!games) return;

    qsa("p,small", games).forEach(el => {
      const t = norm(el.textContent);
      if(t.includes("source team-game rows")){
        el.textContent = "Select a player to view their full playoff game log, including team context for each game.";
      }
    });
  }

  function fixStretchCards(){
    const stretch = qs("#stitchContent_stretches");
    if(!stretch) return;

    qsa(".stat-card,.metric-card,.card", stretch).forEach(card => {
      if(qs("table,input,select,button", card)) return;

      const text = String(card.textContent || "").trim();
      if(!text) return;

      const hasNumber = /[-+]?\d/.test(text);
      const hasDash = text.includes("—") || text.includes("-");
      if(!hasNumber && !hasDash && text.length < 40){
        const dash = document.createElement("div");
        dash.className = "stitch-placeholder-value";
        dash.textContent = "—";
        dash.style.fontSize = "28px";
        dash.style.fontWeight = "900";
        dash.style.color = "#64748b";
        dash.style.marginTop = "10px";
        card.appendChild(dash);
      }
    });

    qsa("p,div,span", stretch).forEach(el => {
      if(el.children.length > 0) return;
      const txt = String(el.textContent || "");
      if(txt.includes("Weighted stats use POSS")){
        el.innerHTML = txt.replace("Weighted stats use POSS", "<br><small>Weighted stats use POSS").replace("otherwise MIN.", "otherwise MIN.</small>");
      }
    });
  }

  function wrapWideTables(){
    qsa(".stitch-feature-content table").forEach(table => {
      const parent = table.parentElement;
      if(!parent || parent.classList.contains("stitch-table-scroll")) return;
      if(parent.classList.contains("table-wrapper") || parent.classList.contains("table-wrap") || parent.classList.contains("table-container")) return;

      const wrap = document.createElement("div");
      wrap.className = "stitch-table-scroll";
      wrap.style.overflowX = "auto";
      wrap.style.borderRadius = "14px";
      parent.insertBefore(wrap, table);
      wrap.appendChild(table);
    });
  }

  function collapseBuildBadge(){
    qsa("body *").forEach(el => {
      const t = norm(el.textContent);
      if(t === "data build safe" || t.includes("data build safe")){
        el.classList.add("data-build-badge");
        el.title = "Data build safe";
      }
    });
  }

  function run(){
    cleanupDuplicateUi();
    syncNav();
    isolatePages();
    moveSearchInputIfNeeded();
    restyleFeaturedPlayers();
    hideBadOverlay();
    normalizeYesNo();
    fillTranslateBlankRows();
    fixSeriesButtonLabel();
    addEmptyStates();
    plainLanguageCopy();
    fixStretchCards();
    wrapWideTables();
    collapseBuildBadge();
  }

  if(document.readyState === "loading"){
    document.addEventListener("DOMContentLoaded", run);
  }else{
    run();
  }

  document.addEventListener("click", () => setTimeout(run, 120), true);
  document.addEventListener("input", () => setTimeout(run, 120), true);

  setTimeout(run, 400);
  setTimeout(run, 1200);
  setTimeout(run, 2600);

  const obs = new MutationObserver(() => {
    clearTimeout(window.__stitchAuditFixV2);
    window.__stitchAuditFixV2 = setTimeout(run, 150);
  });

  obs.observe(document.body, {childList:true, subtree:true});
})();
