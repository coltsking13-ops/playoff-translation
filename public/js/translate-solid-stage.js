(function(){
  console.log("TRANSLATE SOLID STAGE LOADED");

  function qs(sel, root=document){ return root.querySelector(sel); }
  function qsa(sel, root=document){ return Array.from(root.querySelectorAll(sel)); }
  function txt(el){ return String(el?.textContent || ""); }
  function norm(s){ return String(s || "").toLowerCase().replace(/\s+/g," ").trim(); }

  function findTranslateModule(){
    const headings = qsa("h1,h2,h3,h4,.section-title,strong,b");
    const heading = headings.find(h => norm(txt(h)).includes("series translation consistency"));
    if(!heading) return null;

    let el = heading;
    let best = null;

    while(el && el !== document.body){
      const t = norm(txt(el));
      const hasTable = !!qs("table", el);
      const hasSummary = t.includes("offense translates") && t.includes("net translates");
      const hasInputs = !!qs("input,select", el);

      if(hasTable && hasSummary && hasInputs){
        best = el;
        break;
      }

      el = el.parentElement;
    }

    return best || heading.closest("section,.table-section,.card,.panel,div");
  }

  function solidifyTranslate(){
    const module = findTranslateModule();
    if(!module) return;

    const page = qs("#stitchPage_translate") || module.closest(".stitch-page");
    const content = qs("#stitchContent_translate") || module.parentElement;

    if(!content) return;

    let stage = qs("#stitchTranslateSolidStage");

    if(!stage){
      stage = document.createElement("div");
      stage.id = "stitchTranslateSolidStage";
      content.insertBefore(stage, content.firstChild);
    }

    if(module !== stage && !stage.contains(module)){
      stage.appendChild(module);
    }

    module.classList.add("stitch-real-translate-module");

    // Hide every other direct child in the Translate content area.
    Array.from(content.children).forEach(child => {
      if(child !== stage){
        child.classList.add("stitch-translate-hidden-junk");
        child.style.setProperty("display","none","important");
        child.style.setProperty("visibility","hidden","important");
        child.style.setProperty("opacity","0","important");
        child.style.setProperty("height","0","important");
        child.style.setProperty("overflow","hidden","important");
      }
    });

    // Make ancestors solid and non-transparent.
    [page, content, stage, module].filter(Boolean).forEach(el => {
      el.style.setProperty("position","relative","important");
      el.style.setProperty("isolation","isolate","important");
      el.style.setProperty("opacity","1","important");
      el.style.setProperty("mix-blend-mode","normal","important");
      el.style.setProperty("backdrop-filter","none","important");
      el.style.setProperty("-webkit-backdrop-filter","none","important");
    });

    if(page){
      page.style.setProperty("background","#f8f9fb","important");
      page.style.setProperty("z-index","50","important");
    }

    content.style.setProperty("background","#f8f9fb","important");
    stage.style.setProperty("background","#070b16","important");
    stage.style.setProperty("background-color","#070b16","important");
    module.style.setProperty("background","#0d1117","important");
    module.style.setProperty("background-color","#0d1117","important");

    qsa("td,span,div", module).forEach(el => {
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

    qsa("tbody td", module).forEach(td => {
      td.style.setProperty("color","#e5e7eb","important");
      td.style.setProperty("opacity","1","important");
    });

    qsa("th", module).forEach(th => {
      th.style.setProperty("color","#ffffff","important");
      th.style.setProperty("opacity","1","important");
    });

    // Hide any promo/old hero text inside the translate page.
    if(page){
      qsa("*", page).forEach(el => {
        if(stage.contains(el)) return;
        const t = norm(txt(el));
        if(
          t.includes("player games. series translation. real context") ||
          t.includes("search any playoff player") ||
          t.includes("playoff translation lab")
        ){
          const box = el.closest(".card,.panel,.hero,section,div") || el;
          if(!stage.contains(box) && box !== content && box !== page){
            box.classList.add("stitch-translate-hidden-junk");
            box.style.setProperty("display","none","important");
          }
        }
      });
    }
  }

  if(document.readyState === "loading"){
    document.addEventListener("DOMContentLoaded", solidifyTranslate);
  }else{
    solidifyTranslate();
  }

  document.addEventListener("click", () => setTimeout(solidifyTranslate, 80), true);
  document.addEventListener("scroll", () => setTimeout(solidifyTranslate, 80), true);
  document.addEventListener("input", () => setTimeout(solidifyTranslate, 80), true);

  setTimeout(solidifyTranslate, 200);
  setTimeout(solidifyTranslate, 800);
  setTimeout(solidifyTranslate, 1800);
  setTimeout(solidifyTranslate, 3200);

  const obs = new MutationObserver(() => {
    clearTimeout(window.__translateSolidStageTimer);
    window.__translateSolidStageTimer = setTimeout(solidifyTranslate, 80);
  });

  obs.observe(document.body, {childList:true, subtree:true, attributes:true});
})();
