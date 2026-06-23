(function(){
  console.log("ALWAYS SEARCH BAR DATA LOADER LOADED");

  function qs(sel, root=document){ return root.querySelector(sel); }
  function qsa(sel, root=document){ return Array.from(root.querySelectorAll(sel)); }
  function norm(s){ return String(s || "").toLowerCase().replace(/\s+/g," ").trim(); }

  let playersCache = null;
  let playersPromise = null;
  let selectedIndex = -1;
  let lastResults = [];

  const FALLBACK_PLAYERS = [
    {name:"LeBron James", id:"2544", teams:"CLE, MIA, LAL", years:"2006–2026"},
    {name:"Stephen Curry", id:"201939", teams:"GSW", years:"2013–2026"},
    {name:"Kobe Bryant", id:"977", teams:"LAL", years:"1997–2012"},
    {name:"Dwyane Wade", id:"2548", teams:"MIA, CHI, CLE", years:"2004–2018"},
    {name:"Kevin Durant", id:"201142", teams:"OKC, GSW, BKN, PHX", years:"2010–2026"},
    {name:"Tim Duncan", id:"1495", teams:"SAS", years:"1998–2016"},
    {name:"Shaquille O'Neal", id:"406", teams:"LAL, MIA, PHX, CLE, BOS", years:"1997–2011"},
    {name:"Dirk Nowitzki", id:"1717", teams:"DAL", years:"2001–2019"},
    {name:"James Harden", id:"201935", teams:"OKC, HOU, BKN, PHI, LAC", years:"2010–2026"},
    {name:"Kawhi Leonard", id:"202695", teams:"SAS, TOR, LAC", years:"2012–2026"},
    {name:"Giannis Antetokounmpo", id:"203507", teams:"MIL", years:"2015–2026"}
  ].map(p => ({...p, raw:p}));

  async function fetchJson(url){
    const res = await fetch(url + (url.includes("?") ? "&" : "?") + "v=" + Date.now(), {cache:"no-store"});
    if(!res.ok) throw new Error(url + " failed " + res.status);
    return await res.json();
  }

  async function loadPlayers(){
    if(playersCache) return playersCache;
    if(playersPromise) return playersPromise;

    playersPromise = (async () => {
      const urls = [
        "./public/data/data-package.embedded.json",
        "./public/data/data-package.json",
        "./data-package.json",
        "./data/data-package.json"
      ];

      let packages = [];

      for(const url of urls){
        try{
          const json = await fetchJson(url);
          packages.push(json);
          console.log("Loaded player search data from", url);
        }catch(e){
          console.warn("Could not load", url);
        }
      }

      const rows = [];

      function addRows(arr){
        if(Array.isArray(arr)) rows.push(...arr);
      }

      for(const dp of packages){
        if(!dp || typeof dp !== "object") continue;

        addRows(dp.players);
        addRows(dp.playerProfiles);
        addRows(dp.playerIndex);
        addRows(dp.playerSeasons);
        addRows(dp.playerGames);
        addRows(dp.playerSeries);
        addRows(dp.seasons);
        addRows(dp.games);

        if(dp.data && typeof dp.data === "object"){
          addRows(dp.data.players);
          addRows(dp.data.playerProfiles);
          addRows(dp.data.playerIndex);
          addRows(dp.data.playerSeasons);
          addRows(dp.data.playerGames);
          addRows(dp.data.playerSeries);
        }

        for(const value of Object.values(dp)){
          if(Array.isArray(value) && value.length && typeof value[0] === "object"){
            const sample = value[0];
            if("playerName" in sample || "name" in sample || "PLAYER_NAME" in sample){
              addRows(value);
            }
          }
        }
      }

      // Also harvest visible featured player buttons if data package fails.
      qsa("button,a,.chip,.featured-chip,[role='button']").forEach(el => {
        const t = String(el.textContent || "").trim();
        if(t && /^[A-Za-z .'\-]+$/.test(t) && t.length > 4 && t.length < 40){
          rows.push({playerName:t});
        }
      });

      const byName = new Map();

      for(const r of rows){
        if(!r || typeof r !== "object") continue;

        const name =
          r.playerName ||
          r.name ||
          r.PLAYER_NAME ||
          r.fullName ||
          r.player ||
          "";

        if(!name) continue;

        const cleanName = String(name).trim();
        const key = norm(cleanName);
        if(!key) continue;

        const id =
          r.playerId ||
          r.id ||
          r.nbaId ||
          r.NBA_ID ||
          r.PLAYER_ID ||
          "";

        const existing = byName.get(key) || {
          raw:r,
          id:String(id || ""),
          name:cleanName,
          teams:"",
          years:""
        };

        if(!existing.id && id) existing.id = String(id);

        const team = r.team || r.TEAM || r.teamAbbr || r.teamAbbreviation || r.TEAM_ABBREVIATION || "";
        const year = r.year || r.season || r.SEASON || "";

        if(team && !existing.teams.includes(String(team))){
          existing.teams = [existing.teams, team].filter(Boolean).join(", ");
        }

        if(year && !existing.years.includes(String(year))){
          existing.years = existing.years
            ? existing.years
            : String(year);
        }

        byName.set(key, existing);
      }

      for(const p of FALLBACK_PLAYERS){
        if(!byName.has(norm(p.name))) byName.set(norm(p.name), p);
      }

      playersCache = Array.from(byName.values()).sort((a,b) => a.name.localeCompare(b.name));

      console.log("Player search loaded:", playersCache.length, "players");
      return playersCache;
    })();

    return playersPromise;
  }

  function insertSearch(){
    if(qs("#ptlAlwaysSearch")) return;

    const box = document.createElement("div");
    box.id = "ptlAlwaysSearch";
    box.innerHTML = `
      <div class="ptl-search-card">
        <div class="ptl-search-label">
          <span>Search Player</span>
          <span>type a name</span>
        </div>
        <input id="ptlAlwaysSearchInput" autocomplete="off" placeholder="Search LeBron James, Stephen Curry, Kobe Bryant..." />
        <div id="ptlAlwaysSearchResults"></div>
      </div>
    `;

    const target =
      qs("#cleanShell .clean-main") ||
      qs("#stitchApp .stitch-main") ||
      qs("main") ||
      document.body;

    target.insertBefore(box, target.firstChild);
    wireSearch();

    loadPlayers();
  }

  function wireSearch(){
    const input = qs("#ptlAlwaysSearchInput");
    const results = qs("#ptlAlwaysSearchResults");
    if(!input || !results) return;

    input.addEventListener("input", () => renderResults(input.value));
    input.addEventListener("focus", () => renderResults(input.value));

    input.addEventListener("keydown", e => {
      if(!lastResults.length) return;

      if(e.key === "ArrowDown"){
        e.preventDefault();
        selectedIndex = Math.min(selectedIndex + 1, lastResults.length - 1);
        updateActive();
      }

      if(e.key === "ArrowUp"){
        e.preventDefault();
        selectedIndex = Math.max(selectedIndex - 1, 0);
        updateActive();
      }

      if(e.key === "Enter"){
        e.preventDefault();
        const p = lastResults[selectedIndex] || lastResults[0];
        if(p) choosePlayer(p);
      }

      if(e.key === "Escape"){
        results.style.display = "none";
      }
    });

    document.addEventListener("click", e => {
      if(!e.target.closest("#ptlAlwaysSearch")){
        results.style.display = "none";
      }
    });
  }

  async function renderResults(query){
    const results = qs("#ptlAlwaysSearchResults");
    if(!results) return;

    results.style.display = "block";
    results.innerHTML = `<div class="ptl-search-empty">Loading players...</div>`;

    const players = await loadPlayers();

    query = norm(query);
    selectedIndex = -1;

    if(!query){
      lastResults = players.slice(0, 14);
    }else{
      const q = query;
      lastResults = players.filter(p => norm(p.name).includes(q)).slice(0, 18);
    }

    if(!lastResults.length){
      results.innerHTML = `<div class="ptl-search-empty">No players found yet. Try another spelling.</div>`;
      return;
    }

    results.innerHTML = lastResults.map((p, i) => `
      <button type="button" class="ptl-search-result" data-index="${i}">
        <span>
          <strong>${escapeHtml(p.name)}</strong><br>
          <small>${escapeHtml([p.years, p.teams].filter(Boolean).join(" • ") || "Open player profile")}</small>
        </span>
        <small>Open →</small>
      </button>
    `).join("");

    qsa(".ptl-search-result", results).forEach(btn => {
      btn.addEventListener("click", () => {
        const p = lastResults[Number(btn.dataset.index)];
        choosePlayer(p);
      });
    });
  }

  function updateActive(){
    qsa(".ptl-search-result").forEach((btn, i) => {
      btn.classList.toggle("active", i === selectedIndex);
    });
  }

  function choosePlayer(p){
    if(!p) return;

    const input = qs("#ptlAlwaysSearchInput");
    const results = qs("#ptlAlwaysSearchResults");

    if(input) input.value = p.name;
    if(results) results.style.display = "none";

    const ids = [
      p.id,
      p.raw?.playerId,
      p.raw?.id,
      p.raw?.nbaId,
      p.raw?.NBA_ID,
      p.raw?.PLAYER_ID
    ].filter(Boolean);

    for(const id of ids){
      try{
        if(typeof window.selectPlayer === "function"){
          window.selectPlayer(id);
          switchToProfile();
          return;
        }
      }catch(e){}
    }

    try{
      if(typeof window.selectPlayerByName === "function"){
        window.selectPlayerByName(p.name);
        switchToProfile();
        return;
      }
    }catch(e){}

    const old = qs("#searchInput");
    if(old){
      old.value = p.name;
      old.dispatchEvent(new Event("input", {bubbles:true}));

      setTimeout(() => {
        const first =
          qs(".search-dropdown button") ||
          qs(".search-result") ||
          qs("[data-player-id]");

        if(first) first.click();
      }, 150);
    }

    switchToProfile();
  }

  function switchToProfile(){
    const btn =
      qs('[data-page="profile"]') ||
      qsa("button").find(b => norm(b.textContent).includes("profile"));

    if(btn) setTimeout(() => btn.click(), 100);
  }

  function escapeHtml(str){
    return String(str).replace(/[&<>"']/g, s => ({
      "&":"&amp;",
      "<":"&lt;",
      ">":"&gt;",
      '"':"&quot;",
      "'":"&#039;"
    }[s]));
  }

  function run(){
    insertSearch();
  }

  if(document.readyState === "loading"){
    document.addEventListener("DOMContentLoaded", run);
  }else{
    run();
  }

  setTimeout(run, 500);
  setTimeout(run, 1500);
})();
