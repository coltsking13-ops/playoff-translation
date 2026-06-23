(function(){
  console.log("STITCH MERGE UI LOADED");

  const FEATURES = [
    {id:"home", label:"Home", icon:"home", big:"LEBRON"},
    {id:"search", label:"Search", icon:"search", big:"SEARCH"},
    {id:"profile", label:"Profile", icon:"person", big:"PROFILE"},
    {id:"series", label:"Series", icon:"leaderboard", big:"SERIES"},
    {id:"games", label:"Games", icon:"sports_basketball", big:"GAMES"},
    {id:"translate", label:"Translate", icon:"compare_arrows", big:"TRANSLATE"},
    {id:"stretches", label:"Stretches", icon:"timeline", big:"STRETCH"},
    {id:"leaders", label:"Leaders", icon:"trophy", big:"LEADERS"}
  ];

  const FEATURE_COPY = {
    search:"Search the player database and open a playoff profile instantly.",
    profile:"A clean player dashboard with playoff seasons, summary context, and player-level stats.",
    series:"Series-by-series performance with opponent context and efficiency splits.",
    games:"Every playoff game for the selected player, redesigned into a focused research page.",
    translate:"Test whether production translated across series using thresholds and consistency rules.",
    stretches:"Build custom game stretches and year stretches from the selected player’s playoff log.",
    leaders:"Explore best games, best series, best stretches, and category leaders."
  };

  function qs(sel, root=document){ return root.querySelector(sel); }
  function qsa(sel, root=document){ return Array.from(root.querySelectorAll(sel)); }

  function createButton(f, mobile=false){
    const b = document.createElement("button");
    b.type = "button";
    b.dataset.page = f.id;
    b.innerHTML = `<span class="material-symbols-outlined">${f.icon}</span><span>${f.label}</span>`;
    b.addEventListener("click", () => showPage(f.id));
    return b;
  }

  function pageShell(id, title, copy, big){
    const page = document.createElement("section");
    page.className = "stitch-page";
    page.id = `stitchPage_${id}`;
    page.dataset.page = id;
    page.innerHTML = `
      <div class="stitch-feature-shell">
        <div class="stitch-feature-hero" data-big="${big || title}">
          <div>
            <h1>${title}</h1>
            <p>${copy || ""}</p>
          </div>
        </div>
        <div class="stitch-feature-content" id="stitchContent_${id}"></div>
      </div>
    `;
    return page;
  }

  function findExistingSections(){
    return {
      oldHero: qs("main > .hero") || qs(".hero"),
      featured: qs("main > .featured-section") || qs(".featured-section"),
      playerHeader: qs("#playerHeader"),
      seasons: qs("#seasonSection"),
      yearStretch: qs("#yearStretchSection"),
      series: qs("#seriesSection"),
      games: qs("#gameSection"),
      stretch: qs("#stretchSection"),
      teamRank: qs("#teamRankSection"),
      impact: qs("#impactSection"),
      skill: qs("#skillSection"),
      dataSources: qs("main > .data-sources") || qs(".data-sources"),
      seriesTranslate: qs("#seriesTranslateSection") || findByHeading("series translation") || findByHeading("translation"),
      leaders: qs("#leaderboardsSection") || qs("#leadersSection") || findByHeading("leaderboard") || findByHeading("leaders")
    };
  }

  function findByHeading(needle){
    needle = String(needle).toLowerCase();
    const headings = qsa("h1,h2,h3,h4,.section-title");
    const h = headings.find(x => String(x.textContent || "").toLowerCase().includes(needle));
    if(!h) return null;
    return h.closest(".table-section,section,.section,.card,.panel,div") || h.parentElement;
  }

  function move(el, target){
    if(!el || !target) return;
    target.appendChild(el);
    el.classList.remove("stitch-hidden-source");
  }

  function buildHome(){
    const home = document.createElement("section");
    home.className = "stitch-page stitch-home active";
    home.id = "stitchPage_home";
    home.dataset.page = "home";

    home.innerHTML = `
      <div class="stitch-watermark">
        <span class="name">LEBRON</span>
        <span class="num">23</span>
      </div>

      <div class="stitch-hero-grid">
        <div>
          <div class="stitch-kicker"><span>Featured Profile</span></div>
          <h1 class="stitch-title">Playoff<br>Translation<br>Lab</h1>
          <p class="stitch-subtitle">
            Game-by-game, series-by-series, and stretch-based NBA playoff analytics built to show what actually translates deep into the postseason.
          </p>
        </div>

        <div class="stitch-hero-image">
          <div class="stitch-hero-glow"></div>
          <img class="stitch-lebron-img" alt="LeBron James" src="./public/images/player-bodies/2544.png"
            onerror="this.onerror=function(){this.style.display='none'}; this.src='https://cdn.nba.com/headshots/nba/latest/1040x760/2544.png'">
          <div class="stitch-quote-card">
            <span class="material-symbols-outlined">format_quote</span>
            <p>Who keeps elite production across games, series, matchups, and eras?</p>
          </div>
        </div>
      </div>

      <div class="stitch-bento">
        <button class="stitch-bento-card" data-page="games">
          <span class="material-symbols-outlined">sports_basketball</span>
          <h3>Game Logs</h3>
          <small><span>View individual performance</span><span>→</span></small>
        </button>

        <button class="stitch-bento-card dark" data-page="translate">
          <span class="material-symbols-outlined">leaderboard</span>
          <h3>Series Lab</h3>
          <small><span>Analyze matchup trends</span><span>→</span></small>
        </button>

        <button class="stitch-bento-card" data-page="stretches">
          <span class="material-symbols-outlined">timeline</span>
          <h3>Stretch Lab</h3>
          <small><span>Evaluate peak postseason runs</span><span>→</span></small>
        </button>
      </div>
    `;

    home.querySelectorAll("[data-page]").forEach(b => {
      b.addEventListener("click", () => showPage(b.dataset.page));
    });

    return home;
  }


  function cleanupDuplicateUi(){
    document.querySelectorAll(
      "#ptlSideFeatureNav,.ptl-side-feature-nav,#ptlReferenceHome,#ptlFeaturePages,#nbaForceHeroShell,#nbaPlayerHeroShell,#finalToolHub,.final-tool-hub,.audience-tool-hub,.core-tool-hub"
    ).forEach(el => el.remove());
  }

  function buildApp(){
    cleanupDuplicateUi();
    const existingApp = qs("#stitchApp");
    if(existingApp && qs(".stitch-page", existingApp)) return;
    if(existingApp){
      console.warn("existing Stitch app missing pages; rebuilding");
      existingApp.remove();
    }

    document.body.classList.add("stitch-merged");

    const app = document.createElement("div");
    app.id = "stitchApp";

    const sidebar = document.createElement("nav");
    sidebar.className = "stitch-sidebar";
    sidebar.innerHTML = `<div class="stitch-logo">PT<br>LAB</div><div class="stitch-nav"></div>`;
    const desktopNav = sidebar.querySelector(".stitch-nav");
    FEATURES.forEach(f => desktopNav.appendChild(createButton(f)));

    const mobileTop = document.createElement("header");
    mobileTop.className = "stitch-mobile-top";
    mobileTop.innerHTML = `
      <button type="button" data-page="home"><span class="material-symbols-outlined">menu</span></button>
      <strong>Playoff Translation Lab</strong>
      <button type="button" data-page="search"><span class="material-symbols-outlined">search</span></button>
    `;
    mobileTop.querySelectorAll("[data-page]").forEach(b => b.addEventListener("click", () => showPage(b.dataset.page)));

    const mobileBottom = document.createElement("nav");
    mobileBottom.className = "stitch-mobile-bottom";
    ["home","series","games","translate","leaders"].forEach(id => {
      const f = FEATURES.find(x => x.id === id);
      mobileBottom.appendChild(createButton(f, true));
    });

    const main = document.createElement("main");
    main.className = "stitch-main";

    main.appendChild(buildHome());

    for(const f of FEATURES.filter(x => x.id !== "home")){
      main.appendChild(pageShell(f.id, f.label, FEATURE_COPY[f.id], f.big));
    }

    app.appendChild(sidebar);
    app.appendChild(mobileTop);
    app.appendChild(mobileBottom);
    app.appendChild(main);

    document.body.insertBefore(app, document.body.firstChild);

    placeRealSections();
    showPage("home", false);
  }

  function placeRealSections(){
    const s = findExistingSections();

    // Search page: move real old hero search box and featured chips.
    const searchContent = qs("#stitchContent_search");
    if(s.oldHero){
      const searchBox = qs(".search-box-container", s.oldHero);
      if(searchBox){
        const wrap = document.createElement("div");
        wrap.className = "table-section";
        wrap.innerHTML = `<div class="section-title">Search Player<small>Search the real player database.</small></div>`;
        wrap.appendChild(searchBox);
        searchContent.appendChild(wrap);
      }
    }
    move(s.featured, searchContent);

    // Profile page.
    const profileContent = qs("#stitchContent_profile");
    move(s.playerHeader, profileContent);
    move(s.seasons, profileContent);

    // Series page.
    const seriesContent = qs("#stitchContent_series");
    move(s.series, seriesContent);

    // Game page.
    const gamesContent = qs("#stitchContent_games");
    move(s.games, gamesContent);

    // Translation page.
    const translateContent = qs("#stitchContent_translate");
    move(s.seriesTranslate, translateContent);
    if(!translateContent.children.length){
      const note = document.createElement("div");
      note.className = "table-section";
      note.innerHTML = `<div class="section-title">Series Translation Lab<small>The translation module will appear here when the script loads.</small></div><div class="empty-state"><p>Select a player, then use the Series Lab from the tool hub if needed.</p></div>`;
      translateContent.appendChild(note);
    }

    // Stretch page: both custom and year stretch.
    const stretchContent = qs("#stitchContent_stretches");
    move(s.stretch, stretchContent);
    move(s.yearStretch, stretchContent);

    // Leaders page.
    const leadersContent = qs("#stitchContent_leaders");
    move(s.leaders, leadersContent);
    if(!leadersContent.children.length){
      const note = document.createElement("div");
      note.className = "table-section";
      note.innerHTML = `<div class="section-title">Leaderboards<small>Leaderboards and peak tables will appear here.</small></div><div class="empty-state"><p>Use the existing leaderboard module or add leaderboard tables here next.</p></div>`;
      leadersContent.appendChild(note);
    }

    // Hide sections user asked not to show in public UI.
    [s.teamRank, s.impact, s.skill, s.dataSources].forEach(el => {
      if(el) el.classList.add("stitch-hidden-source");
    });
  }

  function showPage(id, scroll=true){
    qsa(".stitch-page").forEach(p => p.classList.toggle("active", p.dataset.page === id));
    qsa(".stitch-nav button,.stitch-mobile-bottom button").forEach(b => b.classList.toggle("active", b.dataset.page === id));

    if(id === "search"){
      setTimeout(() => {
        const inp = qs("#searchInput");
        if(inp) inp.focus();
      }, 100);
    }

    if(scroll){
      const app = qs("#stitchApp");
      if(app) app.scrollIntoView({behavior:"smooth", block:"start"});
    }
  }

  if(document.readyState === "loading"){
    document.addEventListener("DOMContentLoaded", buildApp);
  }else{
    buildApp();
  }

  setTimeout(buildApp, 500);
})();
