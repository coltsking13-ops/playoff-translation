(function(){
  console.log("CLEAN SHELL LOADED");

  const PAGES = [
    ["home","HOME","home",""],
    ["search","SEARCH","search","Search the player database and open a playoff profile instantly."],
    ["profile","PROFILE","person","View the selected player’s playoff seasons, teams, and summary profile."],
    ["series","SERIES","leaderboard","Series-by-series performance with opponent and team context where available."],
    ["games","GAMES","sports_basketball","Every playoff game for the selected player, redesigned into a focused research page."],
    ["translate","TRANSLATE","compare_arrows","Test whether production translated across series using thresholds and consistency rules."],
    ["stretches","STRETCHES","timeline","Build custom game stretches and year stretches from the selected player’s playoff log."],
    ["leaders","LEADERS","trophy","Explore best games, best series, best stretches, and category leaders."]
  ];

  function qs(sel, root=document){ return root.querySelector(sel); }
  function qsa(sel, root=document){ return Array.from(root.querySelectorAll(sel)); }
  function txt(el){ return String(el?.textContent || ""); }
  function norm(s){ return String(s || "").toLowerCase().replace(/\s+/g," ").trim(); }

  function findByHeading(needle){
    needle = norm(needle);
    const heads = qsa("h1,h2,h3,h4,.section-title,strong,b");
    const h = heads.find(x => norm(txt(x)).includes(needle));
    if(!h) return null;
    return h.closest(".table-section,section,.card,.panel,div") || h.parentElement;
  }

  function makeShell(){
    const old = qs("#cleanShell");
    if(old) old.remove();

    const shell = document.createElement("div");
    shell.id = "cleanShell";

    const sidebar = document.createElement("aside");
    sidebar.className = "clean-sidebar";
    sidebar.innerHTML = `
      <div class="clean-logo">PT<br>LAB</div>
      <nav class="clean-nav">
        ${PAGES.map(([id,label,icon]) => `
          <button type="button" data-page="${id}">
            <span class="material-symbols-outlined">${icon}</span>
            <span>${label}</span>
          </button>
        `).join("")}
      </nav>
    `;

    const main = document.createElement("main");
    main.className = "clean-main";

    main.appendChild(buildHome());

    for(const [id,label,,copy] of PAGES.filter(p => p[0] !== "home")){
      const page = document.createElement("section");
      page.className = "clean-page";
      page.id = `cleanPage_${id}`;
      page.dataset.page = id;
      page.innerHTML = `
        <div class="clean-page-hero" data-watermark="${label}">
          <h1>${label}</h1>
          <p>${copy}</p>
        </div>
        <div class="clean-content" id="cleanContent_${id}"></div>
      `;
      main.appendChild(page);
    }

    shell.appendChild(sidebar);
    shell.appendChild(main);
    document.body.insertBefore(shell, document.body.firstChild);

    sidebar.querySelectorAll("[data-page]").forEach(btn => {
      btn.addEventListener("click", () => showPage(btn.dataset.page));
    });

    shell.querySelectorAll(".clean-home-card").forEach(btn => {
      btn.addEventListener("click", () => showPage(btn.dataset.page));
    });
  }

  function buildHome(){
    const home = document.createElement("section");
    home.className = "clean-page active";
    home.id = "cleanPage_home";
    home.dataset.page = "home";

    home.innerHTML = `
      <div class="clean-home-hero">
        <div>
          <div class="clean-kicker">Featured Profile</div>
          <h1 class="clean-home-title">Playoff<br>Translation<br>Lab</h1>
          <p class="clean-home-sub">Game-by-game, series-by-series, and stretch-based NBA playoff analytics built to show what actually translates deep into the postseason.</p>
        </div>

        <div class="clean-player-wrap">
          <img class="clean-player-img" alt="LeBron James" src="./public/images/player-bodies/2544.png"
            onerror="this.onerror=function(){this.style.display='none'};this.src='https://cdn.nba.com/headshots/nba/latest/1040x760/2544.png'">
          <div class="clean-question">
            <b>Core Question</b>
            <p>Who keeps elite production across games, series, matchups, and eras?</p>
          </div>
        </div>
      </div>

      <div class="clean-home-cards">
        <button type="button" class="clean-home-card" data-page="games">
          <span class="material-symbols-outlined">sports_basketball</span>
          <h3>Game Logs</h3>
          <p>View individual performance →</p>
        </button>
        <button type="button" class="clean-home-card" data-page="translate">
          <span class="material-symbols-outlined">leaderboard</span>
          <h3>Series Lab</h3>
          <p>Analyze translation trends →</p>
        </button>
        <button type="button" class="clean-home-card" data-page="stretches">
          <span class="material-symbols-outlined">timeline</span>
          <h3>Stretch Lab</h3>
          <p>Evaluate peak postseason runs →</p>
        </button>
      </div>
    `;

    return home;
  }

  function move(el, target){
    if(!el || !target) return false;
    target.appendChild(el);
    return true;
  }

  function placeRealSections(){
    const search = qs("#cleanContent_search");
    const profile = qs("#cleanContent_profile");
    const series = qs("#cleanContent_series");
    const games = qs("#cleanContent_games");
    const translate = qs("#cleanContent_translate");
    const stretches = qs("#cleanContent_stretches");
    const leaders = qs("#cleanContent_leaders");

    const searchInput = qs("#searchInput");
    if(searchInput){
      const box = searchInput.closest(".search-box-container") || searchInput.parentElement;
      const card = document.createElement("section");
      card.className = "clean-tool-card";
      card.innerHTML = `<div class="section-title">Search Player<small>Type a player name to search the full playoff database.</small></div>`;
      card.appendChild(box);
      search.appendChild(card);
    }else{
      search.appendChild(empty("Search input was not found. The original search script may not have loaded yet."));
    }

    const featured = qs("main > .featured-section") || qs(".featured-section") || findByHeading("featured players");
    move(featured, search);
    search.appendChild(guide("Type a name above to search all players in the database. Featured players are shortcuts."));

    move(qs("#playerHeader"), profile);
    move(qs("#seasonSection"), profile);

    const seriesSection = qs("#seriesSection") || findByHeading("series breakdown");
    move(seriesSection, series) || series.appendChild(empty("Search for a player to see their full playoff series breakdown."));

    const gameSection = qs("#gameSection") || findByHeading("game log");
    move(gameSection, games) || games.appendChild(empty("Select a player to view their full playoff game log, including team context for each game."));

    const translateSection =
      qs("#seriesTranslateSection") ||
      qs("#seriesTranslateRoot") ||
      findTranslateModule();

    move(translateSection, translate) || translate.appendChild(empty("Series Translation Consistency tool was not found yet."));

    move(qs("#stretchSection"), stretches);
    move(qs("#yearStretchSection"), stretches);
    if(!stretches.children.length){
      stretches.appendChild(empty("Select a player to build custom game and year stretches."));
    }

    const leadersSection =
      qs("#leaderboardsSection") ||
      qs("#leadersSection") ||
      findByHeading("leaderboard") ||
      findByHeading("leaders");

    move(leadersSection, leaders) || leaders.appendChild(empty("Leaderboards will appear here when the leaderboard module is available."));

    cleanupText();
    wrapTables();
    forceReadableControls();
    normalizeYesNo();
    addStretchPlaceholders();
    hideBuildBadge();
  }

  function findTranslateModule(){
    const heads = qsa("h1,h2,h3,h4,.section-title,strong,b");
    const h = heads.find(x => norm(txt(x)).includes("series translation consistency"));
    if(!h) return null;

    let el = h;
    while(el && el !== document.body){
      const t = norm(txt(el));
      if(
        t.includes("offense translates") &&
        t.includes("defense translates") &&
        t.includes("net translates")
      ){
        return el;
      }
      el = el.parentElement;
    }

    return h.closest(".table-section,section,.card,.panel,div");
  }

  function empty(message){
    const div = document.createElement("div");
    div.className = "clean-empty";
    div.textContent = message;
    return div;
  }

  function guide(message){
    const div = document.createElement("div");
    div.className = "clean-search-guide";
    div.textContent = message;
    return div;
  }

  function showPage(id){
    qsa(".clean-page").forEach(page => {
      page.classList.toggle("active", page.dataset.page === id);
    });

    qsa(".clean-nav button").forEach(btn => {
      btn.classList.toggle("active", btn.dataset.page === id);
    });

    if(id === "search"){
      setTimeout(() => {
        const input = qs("#searchInput");
        if(input) input.focus();
      }, 100);
    }

    if(id === "translate"){
      setTimeout(() => {
        tryRenderTranslate();
        normalizeYesNo();
        wrapTables();
      }, 120);
    }

    if(id === "stretches"){
      setTimeout(() => {
        addStretchPlaceholders();
        forceReadableControls();
      }, 120);
    }

    window.scrollTo({top:0, behavior:"smooth"});
  }

  function cleanupText(){
    qsa("*", qs("#cleanShell")).forEach(el => {
      if(el.children.length) return;
      let t = txt(el);

      if(t.includes("teamgame_report context")){
        el.textContent = "Includes team and opponent shot profile data where available.";
      }

      if(t.includes("Game-level team context is shown when source team-game rows exist.")){
        el.textContent = "Select a player to view their full playoff game log, including team context for each game.";
      }

      if(t.includes("Year Log") && el.closest("#cleanContent_series")){
        el.textContent = t.replace("Year Log", "Series Log");
      }
    });
  }

  function wrapTables(){
    qsa("#cleanShell table").forEach(table => {
      if(table.closest(".clean-table-scroll")) return;

      const section = table.closest("section,.table-section,.card,.panel,div");
      if(section && !qs(".clean-table-hint", section)){
        const hint = document.createElement("div");
        hint.className = "clean-table-hint";
        hint.textContent = "Scroll table →";
        section.insertBefore(hint, table);
      }

      const wrap = document.createElement("div");
      wrap.className = "clean-table-scroll";
      table.parentElement.insertBefore(wrap, table);
      wrap.appendChild(table);
    });
  }

  function forceReadableControls(){
    qsa("#cleanShell input,#cleanShell select,#cleanShell textarea").forEach(el => {
      el.style.setProperty("background","#ffffff","important");
      el.style.setProperty("color","#111827","important");
    });

    qsa("#cleanShell option").forEach(el => {
      el.style.setProperty("background","#ffffff","important");
      el.style.setProperty("color","#111827","important");
    });
  }

  function normalizeYesNo(){
    qsa("#cleanShell td,#cleanShell span,#cleanShell div").forEach(el => {
      if(el.children.length) return;
      const t = norm(txt(el));

      if(t === "yes"){
        el.textContent = "YES";
        el.classList.add("clean-yes");
        el.classList.remove("clean-no");
      }

      if(t === "no"){
        el.textContent = "NO";
        el.classList.add("clean-no");
        el.classList.remove("clean-yes");
      }
    });
  }

  function addStretchPlaceholders(){
    const root = qs("#cleanContent_stretches");
    if(!root) return;

    qsa(".stat-card,.metric-card", root).forEach(card => {
      const raw = txt(card).trim();
      const hasValue = /[-+]?\d/.test(raw) || raw.includes("—");
      if(!hasValue && !qs(".clean-placeholder", card)){
        const dash = document.createElement("div");
        dash.className = "clean-placeholder";
        dash.textContent = "—";
        card.appendChild(dash);
      }

      qsa("*", card).forEach(el => {
        const t = txt(el).trim();
        if(/^[-+]?\d/.test(t)){
          el.style.setProperty("font-weight","1000","important");
          el.style.setProperty("color", t.startsWith("+") ? "#16a34a" : "#111827", "important");
        }
      });
    });
  }

  function hideBuildBadge(){
    qsa("body *").forEach(el => {
      if(norm(txt(el)).includes("data build safe")){
        el.style.setProperty("display","none","important");
      }
    });
  }

  function tryRenderTranslate(){
    const names = [
      "renderSeriesTranslate",
      "renderSeriesTranslation",
      "renderTranslationLab",
      "renderSeriesTranslationLab",
      "renderTranslateLab"
    ];

    for(const name of names){
      try{
        if(typeof window[name] === "function"){
          window[name]();
          break;
        }
      }catch(e){
        console.warn(name, "failed", e);
      }
    }
  }

  function wireButtons(){
    qsa("#cleanShell button").forEach(btn => {
      if(btn.dataset.cleanWired) return;
      btn.dataset.cleanWired = "true";

      btn.addEventListener("click", () => {
        setTimeout(() => {
          cleanupText();
          wrapTables();
          forceReadableControls();
          normalizeYesNo();
          addStretchPlaceholders();
        }, 100);
      }, true);
    });
  }

  function init(){
    makeShell();
    placeRealSections();
    wireButtons();
    document.body.classList.add("clean-shell-active");
    showPage("home");

    setTimeout(() => {
      cleanupText();
      wrapTables();
      forceReadableControls();
      normalizeYesNo();
      addStretchPlaceholders();
      hideBuildBadge();
    }, 500);
  }

  if(document.readyState === "loading"){
    document.addEventListener("DOMContentLoaded", init);
  }else{
    init();
  }

  document.addEventListener("click", () => setTimeout(() => {
    cleanupText();
    wrapTables();
    forceReadableControls();
    normalizeYesNo();
    addStretchPlaceholders();
    hideBuildBadge();
  }, 150), true);

  document.addEventListener("change", () => setTimeout(() => {
    forceReadableControls();
    addStretchPlaceholders();
  }, 150), true);
})();
