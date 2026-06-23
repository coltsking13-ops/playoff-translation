(function(){
  console.log("REFERENCE HOME UI LOADED");

  const features = [
    ["Search Player", "search-player"],
    ["Series Logs", "series-logs"],
    ["Game Logs", "game-logs"],
    ["Series Lab", "series-lab"],
    ["Custom Stretch Lab", "custom-stretch-lab"],
    ["Year Stretch Lab", "year-stretch-lab"],
    ["Leaderboards", "leaderboards"]
  ];

  function slug(s){
    return String(s || "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "");
  }

  function makeAnchors(){
    const headings = Array.from(document.querySelectorAll("h1,h2,h3,h4"));

    for(const [label, id] of features){
      const wanted = label.toLowerCase();
      const h = headings.find(x => String(x.textContent || "").toLowerCase().includes(wanted.replace("logs","log")));
      if(h && !document.getElementById(id)){
        h.id = id;
        h.classList.add("ptl-home-anchor-spacer");
      }
    }

    // Common alternate section names
    const pairs = [
      ["search", "search-player"],
      ["series breakdown", "series-logs"],
      ["game log", "game-logs"],
      ["series translation", "series-lab"],
      ["custom stretch", "custom-stretch-lab"],
      ["year stretch", "year-stretch-lab"],
      ["leader", "leaderboards"]
    ];

    for(const [needle, id] of pairs){
      if(document.getElementById(id)) continue;
      const h = headings.find(x => String(x.textContent || "").toLowerCase().includes(needle));
      if(h){
        h.id = id;
        h.classList.add("ptl-home-anchor-spacer");
      }
    }
  }

  function insertHome(){
    if(document.getElementById("ptlReferenceHome")) return;

    makeAnchors();

    const lebronBody = "./public/images/player-bodies/2544.png";
    const lebronHead = "https://cdn.nba.com/headshots/nba/latest/1040x760/2544.png";

    const app = document.createElement("section");
    app.id = "ptlReferenceHome";
    app.className = "ptl-reference-app";

    app.innerHTML = `
      <div class="ptl-reference-frame">
        <div class="ptl-reference-sidebar">
          <div class="ptl-reference-sidebar-dot"></div>
          <div class="ptl-reference-sidebar-menu">Playoff Lab</div>
          <div class="ptl-reference-sidebar-dot"></div>
        </div>

        <div class="ptl-reference-topbar">
          <div class="ptl-reference-logo">
            <span class="ptl-reference-logo-mark"></span>
            <span>PTL</span>
          </div>

          <nav class="ptl-reference-topnav">
            <a href="#search-player">Search</a>
            <a href="#series-logs">Series</a>
            <a href="#game-logs">Games</a>
            <a href="#series-lab">Translate</a>
            <a href="#custom-stretch-lab">Stretches</a>
            <a href="#leaderboards">Leaders</a>
          </nav>

          <div class="ptl-reference-avatar">LBJ</div>
        </div>

        <div class="ptl-reference-bg-word">LEBRON</div>

        <div class="ptl-reference-main">
          <div class="ptl-reference-left">
            <div class="ptl-reference-fav">☆ Featured Player</div>

            <h1 class="ptl-reference-title">
              Playoff
              <small>Translation Lab</small>
            </h1>

            <p class="ptl-reference-subtitle">
              Game-by-game, series-by-series, and stretch-based NBA playoff analytics built to show what actually translates deep into the postseason.
            </p>

            <div class="ptl-reference-team">
              <span class="ptl-reference-team-dot"></span>
              <span>LeBron James • playoff benchmark view</span>
            </div>
          </div>

          <div class="ptl-reference-center">
            <div class="ptl-reference-ring"></div>
            <div class="ptl-reference-number">23</div>
            <div class="ptl-reference-position">F</div>
            <img class="ptl-reference-lebron" src="${lebronBody}" alt="LeBron James"
              onerror="this.onerror=function(){this.style.display='none'}; this.src='${lebronHead}'">
          </div>

          <div class="ptl-reference-right">
            <div class="ptl-reference-score-card">
              <div class="ptl-reference-score-tabs">
                <div>Core Idea</div>
                <div>Tools</div>
              </div>
              <div class="ptl-reference-score-body">
                <div class="ptl-reference-score-title">What this site answers</div>
                <div class="ptl-reference-score-copy">
                  Who keeps elite production across games, series, matchups, and eras?
                </div>
              </div>
            </div>

            <div class="ptl-reference-mini-grid">
              <div class="ptl-reference-mini">Search any playoff player</div>
              <div class="ptl-reference-mini">Build custom stretches</div>
            </div>

            <div class="ptl-reference-feature-links">
              ${features.map(([label,id]) => `<a href="#${id}"><span>${label}</span><span>→</span></a>`).join("")}
            </div>
          </div>
        </div>

        <div class="ptl-reference-info-bottom">
          <div class="ptl-reference-lines">
            <div class="ptl-reference-line"><span>Data</span><span>Playoff games, series, seasons</span></div>
            <div class="ptl-reference-line"><span>View</span><span>Player profile + custom labs</span></div>
            <div class="ptl-reference-line"><span>Focus</span><span>Translation, efficiency, context</span></div>
          </div>
          <div></div>
          <div class="ptl-reference-lines">
            <div class="ptl-reference-line"><span>Search</span><span>Find any player in the dataset</span></div>
            <div class="ptl-reference-line"><span>Build</span><span>Game, year, and series stretches</span></div>
            <div class="ptl-reference-line"><span>Compare</span><span>Leaderboards and playoff peaks</span></div>
          </div>
        </div>

        <div class="ptl-reference-floating-stats">
          <div class="ptl-reference-stat">
            <div class="ptl-reference-stat-label">Game Logs</div>
            <div class="ptl-reference-stat-value">G</div>
            <div class="ptl-reference-stat-sub">every playoff game</div>
          </div>

          <div class="ptl-reference-stat dark">
            <div class="ptl-reference-stat-label">Series Lab</div>
            <div class="ptl-reference-stat-value">S</div>
            <div class="ptl-reference-stat-sub">translation checks</div>
          </div>

          <div class="ptl-reference-stat">
            <div class="ptl-reference-stat-label">Stretch Lab</div>
            <div class="ptl-reference-stat-value">+</div>
            <div class="ptl-reference-stat-sub">custom ranges</div>
          </div>
        </div>
      </div>
    `;

    document.body.insertBefore(app, document.body.firstChild);

    const side = document.createElement("nav");
    side.id = "ptlSideFeatureNav";
    side.className = "ptl-side-feature-nav";
    side.innerHTML = features.map(([label,id]) => `<a href="#${id}">${label}</a>`).join("");
    document.body.appendChild(side);
  }

  if(document.readyState === "loading"){
    document.addEventListener("DOMContentLoaded", insertHome);
  }else{
    insertHome();
  }

  setTimeout(insertHome, 600);
})();
