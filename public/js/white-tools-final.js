(function(){
  console.log("WHITE TOOLS FINAL LOADED");

  function qs(sel, root=document){ return root.querySelector(sel); }
  function qsa(sel, root=document){ return Array.from(root.querySelectorAll(sel)); }
  function txt(el){ return String(el?.textContent || ""); }
  function norm(s){ return String(s || "").toLowerCase().replace(/\s+/g," ").trim(); }

  let currentPage = "home";

  function setPage(id){
    currentPage = id || currentPage || "home";

    qsa("#stitchApp .stitch-page").forEach(page => {
      const active = page.dataset.page === currentPage;

      page.classList.toggle("active", active);
      page.style.setProperty("display", active ? "block" : "none", "important");
      page.style.setProperty("visibility", active ? "visible" : "hidden", "important");
      page.style.setProperty("opacity", active ? "1" : "0", "important");
      page.style.setProperty("height", active ? "auto" : "0", "important");
      page.style.setProperty("max-height", active ? "none" : "0", "important");
      page.style.setProperty("overflow", active ? "visible" : "hidden", "important");
      page.style.setProperty("pointer-events", active ? "auto" : "none", "important");
    });

    qsa(".stitch-nav button,.stitch-mobile-bottom button").forEach(btn => {
      btn.classList.toggle("active", btn.dataset.page === currentPage);
    });

    cleanOldPromos();

    if(currentPage === "translate"){
      buildTranslateWhiteStage();
    }

    if(currentPage === "stretches"){
      fixStretchReadability();
    }
  }

  function wireNav(){
    qsa(".stitch-nav button,.stitch-mobile-bottom button,[data-page]").forEach(btn => {
      if(btn.dataset.whiteToolsWired) return;
      btn.dataset.whiteToolsWired = "true";

      btn.addEventListener("click", e => {
        const id = btn.dataset.page;
        if(!id) return;

        e.preventDefault();
        e.stopPropagation();

        setPage(id);
        window.scrollTo({top:0, behavior:"smooth"});
      }, true);
    });
  }

  function cleanOldPromos(){
    qsa("body *").forEach(el => {
      if(el.closest("#stitchTranslateWhiteStage")) return;

      const t = norm(txt(el));

      if(
        t.includes("player games. series translation. real context") ||
        t.includes("search any playoff player and break down production") ||
        t.includes("medium+ low leverage removed") ||
        t.includes("on-court impact layer")
      ){
        const box = el.closest(".hero,.lab-hero,.card,.panel,section,div") || el;
        if(!box.closest("#stitchPage_home .stitch-hero-grid")){
          box.classList.add("stitch-kill-old-promo");
          box.style.setProperty("display","none","important");
        }
      }
    });
  }

  function findTranslateModule(){
    const headings = qsa("h1,h2,h3,h4,.section-title,strong,b");
    const h = headings.find(x => norm(txt(x)).includes("series translation consistency"));
    if(!h) return null;

    let el = h;
    while(el && el !== document.body){
      const t = norm(txt(el));
      if(
        t.includes("offense translates") &&
        t.includes("defense translates") &&
        t.includes("net translates") &&
        qs("table", el)
      ){
        return el;
      }
      el = el.parentElement;
    }

    return h.closest("section,.table-section,.card,.panel,div");
  }

  function buildTranslateWhiteStage(){
    const content = qs("#stitchContent_translate");
    if(!content) return;

    let module = findTranslateModule();
    if(!module) return;

    let stage = qs("#stitchTranslateWhiteStage");
    if(!stage){
      stage = document.createElement("div");
      stage.id = "stitchTranslateWhiteStage";
      stage.className = "stitch-white-tool-card";
      content.insertBefore(stage, content.firstChild);
    }

    if(!stage.contains(module)){
      stage.appendChild(module);
    }

    module.classList.add("stitch-white-tool-card");

    Array.from(content.children).forEach(child => {
      if(child !== stage){
        child.classList.add("stitch-kill-old-promo");
        child.style.setProperty("display","none","important");
      }
    });

    normalizeYesNo(stage);
    wrapTables(stage);
    forceWhite(stage);
  }

  function normalizeYesNo(root=document){
    qsa("td,span,div", root).forEach(el => {
      if(el.children.length) return;

      const t = norm(txt(el));

      if(t === "yes"){
        el.textContent = "YES";
        el.classList.add("stitch-yes");
        el.classList.remove("stitch-no");
      }

      if(t === "no"){
        el.textContent = "NO";
        el.classList.add("stitch-no");
        el.classList.remove("stitch-yes");
      }
    });
  }

  function wrapTables(root=document){
    qsa("table", root).forEach(table => {
      if(table.closest(".stitch-table-scroll")) return;

      const wrap = document.createElement("div");
      wrap.className = "stitch-table-scroll";
      table.parentElement.insertBefore(wrap, table);
      wrap.appendChild(table);
    });
  }

  function forceWhite(root=document){
    qsa("section,.table-section,.card,.panel,.stat-card,.metric-card", root).forEach(el => {
      el.style.setProperty("background","#ffffff","important");
      el.style.setProperty("color","#111827","important");
      el.style.setProperty("opacity","1","important");
      el.style.setProperty("backdrop-filter","none","important");
    });

    qsa("input,select,textarea", root).forEach(el => {
      el.style.setProperty("background","#ffffff","important");
      el.style.setProperty("color","#111827","important");
    });

    qsa("option", root).forEach(el => {
      el.style.setProperty("background","#ffffff","important");
      el.style.setProperty("color","#111827","important");
    });

    qsa("tbody td", root).forEach(el => {
      el.style.setProperty("color","#111827","important");
    });
  }

  function fixStretchReadability(){
    const root = qs("#stitchContent_stretches");
    if(!root) return;

    qsa("select option", root).forEach(opt => {
      opt.style.setProperty("background","#ffffff","important");
      opt.style.setProperty("color","#111827","important");
    });

    qsa(".stat-card,.metric-card", root).forEach(card => {
      card.style.setProperty("background","#ffffff","important");
      card.style.setProperty("color","#111827","important");

      const raw = txt(card).trim();
      const hasValue = /[-+]?\d/.test(raw) || raw.includes("—");

      if(!hasValue && !qs(".stitch-placeholder-value", card)){
        const dash = document.createElement("div");
        dash.className = "stitch-placeholder-value";
        dash.textContent = "—";
        dash.style.color = "#64748b";
        dash.style.fontSize = "24px";
        dash.style.fontWeight = "1000";
        card.appendChild(dash);
      }

      qsa("*", card).forEach(el => {
        const t = txt(el).trim();
        if(/^[-+]?\d/.test(t)){
          el.classList.add("stitch-force-visible-value");
          el.style.setProperty("color", t.startsWith("+") ? "#16a34a" : "#111827", "important");
          el.style.setProperty("font-weight", "1000", "important");
        }
      });
    });

    forceWhite(root);
    wrapTables(root);
  }

  function hideDataBadge(){
    qsa("body *").forEach(el => {
      if(norm(txt(el)).includes("data build safe")){
        el.style.setProperty("display","none","important");
      }
    });
  }

  function run(){
    document.body.classList.add("stitch-merged");

    wireNav();
    cleanOldPromos();
    hideDataBadge();

    const active = qs("#stitchApp .stitch-page.active");
    if(active && active.dataset.page) currentPage = active.dataset.page;

    setPage(currentPage);

    if(currentPage === "translate") buildTranslateWhiteStage();
    if(currentPage === "stretches") fixStretchReadability();

    normalizeYesNo(document);
  }

  if(document.readyState === "loading"){
    document.addEventListener("DOMContentLoaded", run);
  }else{
    run();
  }

  document.addEventListener("click", () => setTimeout(run, 80), true);
  document.addEventListener("change", () => setTimeout(run, 80), true);
  document.addEventListener("input", () => setTimeout(run, 80), true);

  setTimeout(run, 300);
  setTimeout(run, 1000);
  setTimeout(run, 2200);

  const obs = new MutationObserver(() => {
    clearTimeout(window.__whiteToolsFinal);
    window.__whiteToolsFinal = setTimeout(run, 120);
  });

  obs.observe(document.body, {childList:true, subtree:true});
})();
