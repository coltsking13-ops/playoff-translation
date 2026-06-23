(function(){
  function qsa(sel, root=document){ return Array.from(root.querySelectorAll(sel)); }

  function norm(s){
    return String(s || "").toLowerCase().replace(/\s+/g, " ").trim();
  }

  function visible(el){
    if(!el) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  }

  function bestContainer(el){
    if(!el) return null;

    const selectors = [
      "section",
      ".card",
      ".panel",
      ".content-card",
      ".profile-section",
      ".tool-section",
      ".analytics-section",
      ".lab-section",
      ".glass-card"
    ];

    for(const sel of selectors){
      const c = el.closest(sel);
      if(c && c !== document.body) return c;
    }

    let cur = el;
    for(let i=0; i<5 && cur && cur.parentElement && cur.parentElement !== document.body; i++){
      cur = cur.parentElement;
      const t = norm(cur.textContent);
      if(t.length < 9000) return cur;
    }

    return el;
  }

  function findTextElement(needles){
    const all = qsa("h1,h2,h3,h4,h5,button,summary,.section-title,.title,.card-title,.panel-title,div,span");
    return all.find(el => {
      if(!visible(el)) return false;
      const t = norm(el.textContent);
      if(!t || t.length > 350) return false;
      return needles.some(n => t.includes(norm(n)));
    });
  }

  function hideSections(){
    const hideNeedles = [
      "leverage explorer",
      "team rank",
      "team ranks",
      "on court team profile",
      "on-court team profile",
      "on court profile",
      "on-court profile",
      "shot profile",
      "playmaking"
    ];

    hideNeedles.forEach(needle => {
      qsa("h1,h2,h3,h4,h5,button,summary,.section-title,.title,.card-title,.panel-title,div,span").forEach(el => {
        if(!visible(el)) return;
        const t = norm(el.textContent);
        if(!t || t.length > 450) return;
        if(!t.includes(norm(needle))) return;

        const c = bestContainer(el);
        if(!c) return;

        // Don't hide the whole player page or main app by accident.
        const ct = norm(c.textContent);
        if(ct.length > 15000) return;

        c.classList.add("ui-hidden-by-cleanup");
      });
    });
  }

  function findYearStretchSection(){
    const buildBtn = findTextElement(["build year stretch"]);
    if(buildBtn) return bestContainer(buildBtn);

    const label = findTextElement(["multi-year playoff stretch"]);
    if(label) return bestContainer(label);

    return null;
  }

  function findGameStretchSection(){
    const buildBtn = findTextElement(["build game stretch"]);
    if(buildBtn) return bestContainer(buildBtn);

    const label = findTextElement(["game stretch", "custom game"]);
    if(label) return bestContainer(label);

    return null;
  }

  function firstUsefulTable(section){
    if(!section) return null;

    const tables = qsa("table", section).filter(t => {
      const txt = norm(t.textContent);
      return txt.includes("year") || txt.includes("opp") || txt.includes("pts") || txt.includes("game");
    });

    return tables[0] || null;
  }

  function wrapTableIfNeeded(section, kind){
    if(!section) return;

    const table = firstUsefulTable(section);
    if(!table) return;

    const wrap = table.closest(".table-wrap,.series-translate-table-wrap,.stretch-log-table-wrap") || table.parentElement;
    if(!wrap) return;

    const id = kind === "series" ? "yearStretchSeriesToggle" : "gameStretchGameToggle";
    if(section.querySelector("#" + id)) return;

    wrap.classList.add("stretch-log-collapsed");

    const row = document.createElement("div");
    row.className = "stretch-log-toggle-row";

    const btn = document.createElement("button");
    btn.id = id;
    btn.type = "button";
    btn.className = "stretch-log-toggle-btn";
    btn.textContent = kind === "series" ? "+ Show Year Log" : "+ Show Game Log";

    const note = document.createElement("span");
    note.className = "stretch-log-toggle-note";
    note.textContent = kind === "series"
      ? "Tap to open the year-stretch series table."
      : "Tap to open the custom game-stretch table.";

    btn.addEventListener("click", () => {
      const hidden = wrap.classList.toggle("stretch-log-collapsed");
      btn.textContent = hidden
        ? (kind === "series" ? "+ Show Year Log" : "+ Show Game Log")
        : (kind === "series" ? "− Hide Year Log" : "− Hide Game Log");
    });

    row.appendChild(btn);
    row.appendChild(note);

    wrap.insertAdjacentElement("beforebegin", row);
  }

  function run(){
    hideSections();

    const yearSection = findYearStretchSection();
    wrapTableIfNeeded(yearSection, "series");

    const gameSection = findGameStretchSection();
    wrapTableIfNeeded(gameSection, "game");
  }

  if(document.readyState === "loading"){
    document.addEventListener("DOMContentLoaded", run);
  }else{
    run();
  }

  setTimeout(run, 500);
  setTimeout(run, 1500);

  // Re-apply after player/search renders, but do not move the translator tool.
  let lastRun = 0;
  const observer = new MutationObserver(() => {
    const now = Date.now();
    if(now - lastRun < 900) return;
    lastRun = now;
    setTimeout(run, 50);
  });

  observer.observe(document.body, {childList:true, subtree:true});
})();
