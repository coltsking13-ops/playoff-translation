(function(){
  function ready(fn){
    if(document.readyState !== "loading") fn();
    else document.addEventListener("DOMContentLoaded", fn);
  }

  function findMount(){
    return document.querySelector("main") ||
           document.querySelector("#app") ||
           document.querySelector(".app") ||
           document.querySelector(".container") ||
           document.body;
  }

  function addHero(){
    if(document.querySelector(".ptl-hero")) return;

    const hero = document.createElement("section");
    hero.className = "ptl-hero";
    hero.innerHTML = `
      <div class="ptl-kicker">Playoff Translation Lab</div>
      <h1>Player Games. Series Translation. Real Context.</h1>
      <p>
        Search any playoff player and break down production by game, series, opponent,
        efficiency, relative ratings, shot profile, and on-court impact as the data finishes building.
      </p>
      <div class="ptl-pill-row">
        <div class="ptl-pill"><strong>Game Logs</strong> 2001–2026</div>
        <div class="ptl-pill"><strong>Series View</strong> Player + Team Context</div>
        <div class="ptl-pill"><strong>Medium+</strong> Low Leverage Removed</div>
        <div class="ptl-pill"><strong>On-Court</strong> Impact Layer</div>
      </div>
    `;

    const mount = findMount();
    if(mount === document.body){
      document.body.insertBefore(hero, document.body.firstChild);
    } else {
      mount.insertBefore(hero, mount.firstChild);
    }
  }

  function improveLabels(){
    document.querySelectorAll("button, a, label, h1, h2, h3, h4, .tab, .nav-item").forEach(el => {
      const t = (el.textContent || "").trim().toLowerCase();

      if(t === "home") el.textContent = "Dashboard";
      if(t === "data") el.textContent = "Database";
      if(t.includes("load data")) el.textContent = "Refresh Data";
      if(t.includes("playergames")) el.textContent = el.textContent.replace(/playerGames/g, "Game Logs");
      if(t.includes("playerseries")) el.textContent = el.textContent.replace(/playerSeries/g, "Series Logs");
    });
  }

  function addStatus(){
    if(document.querySelector(".ptl-floating-status")) return;
    const div = document.createElement("div");
    div.className = "ptl-floating-status";
    div.innerHTML = `<span>●</span> Data build safe`;
    document.body.appendChild(div);
  }

  ready(function(){
    document.body.classList.add("ptl-polished");
    addHero();
    improveLabels();
    addStatus();

    setTimeout(improveLabels, 1000);
    setTimeout(improveLabels, 3000);
  });
})();
