(function(){
  function qs(sel, root=document){ return root.querySelector(sel); }
  function qsa(sel, root=document){ return Array.from(root.querySelectorAll(sel)); }
  function norm(s){ return String(s || "").toLowerCase().replace(/\s+/g, " ").trim(); }

  function visible(el){
    if(!el) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  }

  function removeDuplicateHubs(){
    qsa("#audienceToolHub, #coreToolHub, .audience-tool-hub, .core-tool-hub").forEach(el => el.remove());
  }

  function bestSectionFromHeading(el){
    if(!el) return null;

    const candidates = [
      "section",
      ".panel",
      ".card",
      ".content-card",
      ".analytics-section",
      ".tool-section",
      ".profile-section",
      ".lab-section",
      ".glass-card"
    ];

    for(const sel of candidates){
      const c = el.closest(sel);
      if(c && c !== document.body) return c;
    }

    let cur = el;
    for(let i=0; i<6 && cur && cur.parentElement && cur.parentElement !== document.body; i++){
      cur = cur.parentElement;
      const txt = norm(cur.textContent);
      if(txt.length > 80 && txt.length < 20000) return cur;
    }

    return el;
  }

  function findHeadingExact(title){
    const target = norm(title);
    const nodes = qsa("h1,h2,h3,h4,h5,.title,.section-title,.card-title,.panel-title,summary");
    return nodes.find(el => visible(el) && norm(el.textContent) === target);
  }

  function findHeadingIncludes(title){
    const target = norm(title);
    const nodes = qsa("h1,h2,h3,h4,h5,.title,.section-title,.card-title,.panel-title,summary");
    return nodes.find(el => visible(el) && norm(el.textContent).includes(target));
  }

  function hideNamedSections(){
    const titles = [
      "Leverage Explorer",
      "Team Rank / Led Team",
      "On-Court Team Profile",
      "On Court Team Profile",
      "Shot Profile & Playmaking"
    ];

    titles.forEach(title => {
      const h = findHeadingExact(title) || findHeadingIncludes(title);
      const sec = bestSectionFromHeading(h);
      if(sec) sec.classList.add("final-hidden-section");
    });
  }

  function addHub(){
    if(qs("#finalToolHub")) return;

    const hub = document.createElement("section");
    hub.id = "finalToolHub";
    hub.className = "final-tool-hub";
    hub.innerHTML = `
      <h2>Playoff Lab Tools</h2>
      <p>Jump to the main sections.</p>
      <div class="final-tool-grid">
        <button class="final-tool-card" data-jump="search">Search Player<span>Find a player profile fast.</span></button>
        <button class="final-tool-card" data-jump="series-log">Series Logs<span>Series-by-series playoff table.</span></button>
        <button class="final-tool-card" data-jump="game-log">Game Logs<span>Game-by-game playoff table.</span></button>
        <button class="final-tool-card" data-jump="series-lab">Series Lab<span>Translation consistency tool.</span></button>
        <button class="final-tool-card" data-jump="game-lab">Game Lab<span>Custom game stretch builder.</span></button>
        <button class="final-tool-card" data-jump="year-lab">Year Stretch Lab<span>Custom multi-year stretch builder.</span></button>
      </div>
    `;

    const anchor = qs("main") || qs(".container") || document.body;
    if(anchor === document.body){
      document.body.insertBefore(hub, document.body.firstChild);
    }else{
      anchor.insertBefore(hub, anchor.firstChild);
    }

    hub.addEventListener("click", e => {
      const btn = e.target.closest("[data-jump]");
      if(!btn) return;
      jump(btn.dataset.jump);
    });
  }

  function findByText(phrases){
    const nodes = qsa("h1,h2,h3,h4,h5,button,summary,label,.title,.section-title,.card-title,.panel-title,div,span");
    for(const el of nodes){
      if(!visible(el)) continue;
      const t = norm(el.textContent);
      if(!t || t.length > 500) continue;
      if(phrases.some(p => t.includes(norm(p)))) return bestSectionFromHeading(el);
    }
    return null;
  }

  function findTarget(kind){
    if(kind === "search"){
      return qs("input[type='search']") || qs("input[placeholder*='Search']") || qs("#playerSearch") || findByText(["search player"]);
    }
    if(kind === "series-log"){
      return qs("#seriesLog") || qs("#playerSeries") || qs(".series-log") || findByText(["series log", "series logs"]);
    }
    if(kind === "game-log"){
      return qs("#gameLog") || qs("#playerGameLog") || qs(".game-log") || findByText(["game log", "game logs"]);
    }
    if(kind === "series-lab"){
      return qs("#seriesTranslatePanel") || qs(".series-translate-panel") || findByText(["series translation consistency", "translator tool"]);
    }
    if(kind === "game-lab"){
      return findByText(["build stretch", "game stretch", "custom game stretch"]);
    }
    if(kind === "year-lab"){
      return findByText(["build year stretch", "multi-year playoff stretch", "year stretch"]);
    }
    return null;
  }

  function jump(kind){
    const target = findTarget(kind);
    if(!target){
      alert("Pick/search a player first, then try that section.");
      return;
    }

    target.scrollIntoView({behavior:"smooth", block:"start"});
    target.classList.add("final-pulse");
    setTimeout(() => target.classList.remove("final-pulse"), 1000);
  }

  function findCustomGameStretchSection(){
    return findByText(["build stretch", "game stretch", "custom game stretch"]);
  }

  function addShowGameLogButton(){
    const section = findCustomGameStretchSection();
    if(!section || section.querySelector("#finalShowGameLogBtn")) return;

    const tables = qsa("table", section);
    if(!tables.length) return;

    const table = tables[tables.length - 1];
    const wrap = table.closest(".table-wrap") || table.parentElement;
    if(!wrap) return;

    wrap.classList.add("final-log-collapsed");

    const row = document.createElement("div");
    row.className = "final-log-toggle-row";

    const btn = document.createElement("button");
    btn.id = "finalShowGameLogBtn";
    btn.className = "final-log-toggle-btn";
    btn.type = "button";
    btn.textContent = "+ Show Game Log";

    const note = document.createElement("span");
    note.className = "final-log-toggle-note";
    note.textContent = "Open the custom stretch game-by-game table.";

    btn.addEventListener("click", () => {
      const closed = wrap.classList.toggle("final-log-collapsed");
      btn.textContent = closed ? "+ Show Game Log" : "− Hide Game Log";
    });

    row.appendChild(btn);
    row.appendChild(note);
    wrap.insertAdjacentElement("beforebegin", row);
  }

  function run(){
    removeDuplicateHubs();
    addHub();
    hideNamedSections();
    addShowGameLogButton();
  }

  if(document.readyState === "loading"){
    document.addEventListener("DOMContentLoaded", run);
  }else{
    run();
  }

  setTimeout(run, 500);
  setTimeout(run, 1500);
  setTimeout(run, 3000);

  let last = 0;
  const observer = new MutationObserver(() => {
    const now = Date.now();
    if(now - last < 1000) return;
    last = now;
    setTimeout(run, 80);
  });

  observer.observe(document.body, {childList:true, subtree:true});
})();
