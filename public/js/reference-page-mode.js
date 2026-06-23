(function(){
  console.log("REFERENCE PAGE MODE LOADED");

  const FEATURES = [
    { id:"search-player", label:"Search Player", big:"SEARCH", match:["search player","player search","search"] },
    { id:"series-logs", label:"Series Logs", big:"SERIES", match:["series breakdown","series log","series logs"] },
    { id:"game-logs", label:"Game Logs", big:"GAMES", match:["game log","game logs"] },
    { id:"series-lab", label:"Series Lab", big:"TRANSLATE", match:["series translation","translation lab","series lab"] },
    { id:"custom-stretch-lab", label:"Custom Stretch Lab", big:"STRETCH", match:["custom stretch lab","custom stretch"] },
    { id:"year-stretch-lab", label:"Year Stretch Lab", big:"YEARS", match:["year stretch lab","year stretch"] },
    { id:"leaderboards", label:"Leaderboards", big:"LEADERS", match:["leaderboard","leaderboards","leaders"] }
  ];

  function norm(s){
    return String(s || "").toLowerCase().replace(/\s+/g," ").trim();
  }

  function isHeading(el){
    return el && /^H[1-4]$/.test(el.tagName || "");
  }

  function headingLevel(el){
    return isHeading(el) ? parseInt(el.tagName.slice(1),10) : 99;
  }

  function findHeading(feature){
    const headings = Array.from(document.querySelectorAll("h1,h2,h3,h4"));
    return headings.find(h => {
      const t = norm(h.textContent);
      return feature.match.some(m => t.includes(m));
    });
  }

  function extractBlockFromHeading(h){
    const parent = h.parentNode;
    const startLevel = headingLevel(h);
    const block = document.createElement("div");
    block.className = "ptl-feature-extracted-block";

    let node = h;
    let moved = 0;

    while(node){
      const next = node.nextSibling;

      if(node !== h && node.nodeType === 1 && isHeading(node) && headingLevel(node) <= startLevel){
        break;
      }

      block.appendChild(node);
      moved++;
      node = next;
    }

    if(moved <= 1 && parent && parent !== document.body){
      const root = block.firstElementChild;
      if(root){
        block.appendChild(parent);
      }
    }

    return block;
  }

  function subtitleFor(id){
    const map = {
      "search-player":"Find a player and open their playoff profile, game log, series log, and stretch tools.",
      "series-logs":"Series-by-series playoff performance with efficiency, ratings, and opponent context.",
      "game-logs":"Every playoff game in the dataset, shown as a focused game-level research page.",
      "series-lab":"Test whether production translated across playoff series using your thresholds.",
      "custom-stretch-lab":"Pick any start game and end game to build a custom playoff stretch.",
      "year-stretch-lab":"Aggregate seasons across a multi-year playoff window.",
      "leaderboards":"Explore best games, best series, best stretches, and category leaders."
    };
    return map[id] || "Playoff Translation Lab feature page.";
  }

  function buildPages(){
    if(document.getElementById("ptlFeaturePages")) return;

    const pages = document.createElement("section");
    pages.id = "ptlFeaturePages";
    pages.className = "ptl-feature-pages";

    for(const feature of FEATURES){
      const h = findHeading(feature);
      if(!h) continue;

      const block = extractBlockFromHeading(h);

      const page = document.createElement("article");
      page.className = "ptl-feature-page";
      page.id = `page-${feature.id}`;
      page.dataset.featureId = feature.id;

      page.innerHTML = `
        <div class="ptl-feature-page-topbar">
          <div class="ptl-feature-page-brand">
            <span class="ptl-feature-page-mark"></span>
            <span>PTL</span>
          </div>
          <div class="ptl-feature-page-actions">
            <button type="button" data-ptl-home>Home</button>
            <a href="#ptlReferenceHome">Main Page</a>
          </div>
        </div>

        <div class="ptl-feature-page-hero">
          <div>
            <h1 class="ptl-feature-page-title">${feature.label}</h1>
            <p class="ptl-feature-page-subtitle">${subtitleFor(feature.id)}</p>
          </div>
          <div class="ptl-feature-page-bigword">${feature.big}</div>
        </div>

        <div class="ptl-feature-page-content"></div>
      `;

      page.querySelector(".ptl-feature-page-content").appendChild(block);
      pages.appendChild(page);
    }

    const home = document.getElementById("ptlReferenceHome");
    if(home){
      home.insertAdjacentElement("afterend", pages);
    }else{
      document.body.insertBefore(pages, document.body.firstChild);
    }

    document.body.classList.add("ptl-feature-mode-active");
  }

  function showPage(id){
    buildPages();

    const pages = Array.from(document.querySelectorAll(".ptl-feature-page"));
    let found = false;

    for(const page of pages){
      const active = page.dataset.featureId === id;
      page.classList.toggle("active", active);
      if(active) found = true;
    }

    if(found){
      document.body.classList.add("ptl-show-feature-page");
      const target = document.getElementById(`page-${id}`);
      if(target) target.scrollIntoView({behavior:"smooth", block:"start"});
    }else{
      showHome();
    }
  }

  function showHome(){
    document.body.classList.remove("ptl-show-feature-page");
    document.querySelectorAll(".ptl-feature-page").forEach(p => p.classList.remove("active"));
    const home = document.getElementById("ptlReferenceHome");
    if(home) home.scrollIntoView({behavior:"smooth", block:"start"});
  }

  function wireLinks(){
    document.addEventListener("click", e => {
      const homeBtn = e.target.closest("[data-ptl-home]");
      if(homeBtn){
        e.preventDefault();
        showHome();
        return;
      }

      const a = e.target.closest("a[href^='#']");
      if(!a) return;

      const id = a.getAttribute("href").slice(1);
      if(FEATURES.some(f => f.id === id)){
        e.preventDefault();
        showPage(id);
      }

      if(id === "ptlReferenceHome"){
        e.preventDefault();
        showHome();
      }
    });
  }

  function init(){
    buildPages();
    wireLinks();

    const hash = location.hash.replace("#","");
    if(FEATURES.some(f => f.id === hash)){
      setTimeout(() => showPage(hash), 200);
    }
  }

  if(document.readyState === "loading"){
    document.addEventListener("DOMContentLoaded", init);
  }else{
    init();
  }

  setTimeout(init, 800);
})();
