(function(){
  console.log("STITCH AUDIT FIX V3 LOADED");

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

  function forceSearchInput(){
    const searchContent = qs("#stitchContent_search");
    if(!searchContent) return;

    let input = qs("#searchInput");
    if(!input) return;

    if(!searchContent.contains(input)){
      const box = input.closest(".search-box-container") || input.parentElement;
      const wrap = document.createElement("div");
      wrap.className = "table-section stitch-real-search-box";
      wrap.innerHTML = `<div class="section-title">Search Player<small>Type a player name to search the full playoff database.</small></div>`;
      wrap.appendChild(box);
      searchContent.insertBefore(wrap, searchContent.firstChild);
    }

    if(!qs(".stitch-search-guide", searchContent)){
      const guide = document.createElement("div");
      guide.className = "stitch-search-guide";
      guide.textContent = "Type a name above to search all players in the database.";
      searchContent.appendChild(guide);
    }
  }

  function restyleSearchPills(){
    const searchContent = qs("#stitchContent_search");
    if(!searchContent) return;

    qsa("button,a,.chip,.featured-chip,[role='button']", searchContent).forEach(el => {
      el.style.cursor = "pointer";
      if(!el.getAttribute("title")) el.setAttribute("title", "Open player");
    });
  }

  function restyleUpdateBadge(){
    const searchContent = qs("#stitchContent_search");
    if(!searchContent) return;

    qsa(".note-pill,.update-badge,.live-badge", searchContent).forEach(el => {
      if(norm(el.textContent).includes("updated")){
        el.classList.add("live-badge");
        const parent = el.parentElement;
        if(parent && parent.children.length > 1){
          parent.appendChild(el);
        }
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

  function removeBlackVoidPanels(){
    const translate = qs("#stitchContent_translate");
    if(!translate) return;

    qsa("div", translate).forEach(el => {
      const style = getComputedStyle(el);
      const text = norm(el.textContent);
      const rect = el.getBoundingClientRect();
      const bg = style.backgroundColor;
      const isBlackish = bg.includes("0, 0, 0") || bg.includes("2, 6, 23") || bg.includes("15, 23, 42");
      if(isBlackish && text.length < 8 && rect.width > 120 && rect.height > 120){
        el.classList.add("stitch-kill-black-panel");
      }
    });
  }

  function normalizeYesNo(){
    qsa("#stitchContent_translate td,#stitchContent_translate span,#stitchContent_translate div").forEach(el => {
      if(el.children.length) return;
      const t = norm(el.textContent);
      if(t === "yes") el.textContent = "YES";
      if(t === "no") el.textContent = "NO";
    });
  }

  function markPartialTranslateRows(){
    qsa("#stitchContent_translate table tbody tr").forEach(tr => {
      const cells = qsa("td", tr);
      if(cells.length < 4) return;
      const leftBlank = cells.slice(0,4).every(td => !td.textContent.trim());
      const hasDecision = cells.some(td => ["yes","no"].includes(norm(td.textContent)));
      if(leftBlank && hasDecision){
        tr.classList.add("stitch-partial-row");
        cells[0].textContent = "Same series";
        cells[1].textContent = "continued";
        cells[2].textContent = "—";
        cells[3].textContent = "—";
      }
    });
  }

  function fillTranslateBlankRowsFromPrevious(){
    qsa("#stitchContent_translate table tbody tr").forEach(tr => {
      const prev = tr.previousElementSibling;
      if(!prev) return;
      const cells = qsa("td", tr);
      const prevCells = qsa("td", prev);
      if(cells.length < 4 || prevCells.length < 4) return;

      for(let i=0;i<4;i++){
        if(!cells[i].textContent.trim() && prevCells[i].textContent.trim()){
          cells[i].textContent = prevCells[i].textContent.trim();
          cells[i].style.color = "#64748b";
        }
      }
    });
  }

  function fixSeriesAndGamesText(){
    const series = qs("#stitchContent_series");
    if(series){
      qsa("button,a", series).forEach(btn => {
        const t = String(btn.textContent || "");
        if(t.includes("Year Log")) btn.textContent = t.replace("Year Log", "Series Log");
      });

      qsa("p,small,div", series).forEach(el => {
        if(el.children.length) return;
        const t = String(el.textContent || "");
        if(t.includes("teamgame_report")){
          el.textContent = "Includes team and opponent shot profile data where available.";
        }
      });
    }

    const games = qs("#stitchContent_games");
    if(games){
      qsa("p,small,div", games).forEach(el => {
        if(el.children.length) return;
        const t = norm(el.textContent);
        if(t.includes("source team-game rows")){
          el.textContent = "Select a player to view their full playoff game log, including team context for each game.";
        }
      });
    }
  }

  function addEmptyStates(){
    [
      ["series", "Search for a player to see their full playoff series breakdown."],
      ["games", "Select a player to view their full playoff game log, including team context for each game."]
    ].forEach(([id,msg]) => {
      const content = qs(`#stitchContent_${id}`);
      if(!content) return;
      if(qs(".stitch-empty-state", content)) return;

      const table = qs("table", content);
      const rows = qsa("tbody tr", content).filter(r => r.textContent.trim());
      if(!table || rows.length === 0){
        const div = document.createElement("div");
        div.className = "stitch-empty-state";
        div.textContent = msg;
        content.appendChild(div);
      }
    });
  }

  function addTableHintsAndWrap(){
    qsa(".stitch-feature-content table").forEach(table => {
      if(!table.closest(".stitch-table-scroll")){
        const wrap = document.createElement("div");
        wrap.className = "stitch-table-scroll";
        table.parentElement.insertBefore(wrap, table);
        wrap.appendChild(table);
      }

      const section = table.closest(".table-section,section,.card,.panel,div");
      if(section && !qs(".stitch-table-hint", section)){
        const hint = document.createElement("div");
        hint.className = "stitch-table-hint";
        hint.textContent = "Scroll table →";
        section.insertBefore(hint, section.querySelector(".stitch-table-scroll") || table);
      }
    });
  }

  function addExpandTooltips(){
    qsa("#stitchContent_profile tbody tr td:first-child,#stitchContent_series tbody tr td:first-child").forEach(td => {
      const t = String(td.textContent || "").trim();
      if(t.startsWith(">") || t.startsWith("›") || t.startsWith("▸")){
        td.title = "Click to expand series breakdown";
        td.style.cursor = "help";
      }
    });
  }

  function stretchPlaceholders(){
    const stretch = qs("#stitchContent_stretches");
    if(!stretch) return;

    qsa(".stat-card,.metric-card,.card", stretch).forEach(card => {
      if(qs("table,input,select,button", card)) return;
      if(qs(".stitch-placeholder-value", card)) return;

      const text = String(card.textContent || "").trim();
      if(!text) return;

      const hasNumber = /[-+]?\d/.test(text);
      const hasDash = text.includes("—");
      const mostlyLabel = text.length < 40 && !hasNumber && !hasDash;
      if(mostlyLabel){
        const dash = document.createElement("div");
        dash.className = "stitch-placeholder-value";
        dash.textContent = "—";
        card.appendChild(dash);
      }
    });

    qsa("*", stretch).forEach(el => {
      if(el.children.length) return;
      const txt = String(el.textContent || "");
      if(txt.includes("Weighted stats use POSS") && !el.dataset.stitchMethodSplit){
        el.dataset.stitchMethodSplit = "true";
        el.innerHTML = txt
          .replace("Weighted stats use POSS", "<br><small>Weighted stats use POSS")
          .replace("otherwise MIN.", "otherwise MIN.</small>");
      }
    });
  }

  function collapseDataBuildBadge(){
    qsa("body *").forEach(el => {
      const t = norm(el.textContent);
      if(t.includes("data build safe")){
        el.classList.add("data-build-badge");
        el.title = "Data build safe";
      }
    });
  }

  function run(){
    cleanupDuplicateUi();
    syncNav();
    isolatePages();
    forceSearchInput();
    restyleSearchPills();
    restyleUpdateBadge();
    hideBadOverlay();
    removeBlackVoidPanels();
    normalizeYesNo();
    fillTranslateBlankRowsFromPrevious();
    markPartialTranslateRows();
    fixSeriesAndGamesText();
    addEmptyStates();
    addTableHintsAndWrap();
    addExpandTooltips();
    stretchPlaceholders();
    collapseDataBuildBadge();
  }

  if(document.readyState === "loading"){
    document.addEventListener("DOMContentLoaded", run);
  }else{
    run();
  }

  document.addEventListener("click", () => setTimeout(run, 140), true);
  document.addEventListener("input", () => setTimeout(run, 140), true);

  setTimeout(run, 400);
  setTimeout(run, 1300);
  setTimeout(run, 2800);

  const obs = new MutationObserver(() => {
    clearTimeout(window.__stitchAuditFixV3);
    window.__stitchAuditFixV3 = setTimeout(run, 160);
  });

  obs.observe(document.body, {childList:true, subtree:true});
})();
