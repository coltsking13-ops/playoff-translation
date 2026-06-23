(function(){
  console.log("TRANSLATE OPAQUE HOTFIX LOADED");

  function qsa(sel, root=document){ return Array.from(root.querySelectorAll(sel)); }

  function findTranslateRoot(){
    const root = document.querySelector("#stitchContent_translate");
    if(root) return root;

    const headings = qsa("h1,h2,h3,h4,.section-title");
    const h = headings.find(el =>
      String(el.textContent || "").toLowerCase().includes("series translation consistency")
    );

    return h ? h.closest("section,.table-section,.card,.panel,div") : null;
  }

  function forceOpaque(){
    const root = findTranslateRoot();
    if(!root) return;

    root.classList.add("stitch-opaque-translate-root");

    const page = root.closest(".stitch-page");
    if(page){
      page.style.setProperty("background", "#070b16", "important");
      page.style.setProperty("position", "relative", "important");
      page.style.setProperty("z-index", "50", "important");
      page.style.setProperty("isolation", "isolate", "important");
      page.style.setProperty("opacity", "1", "important");
    }

    let node = root;
    while(node && node !== document.body){
      node.style.setProperty("position", "relative", "important");
      node.style.setProperty("opacity", "1", "important");
      node.style.setProperty("mix-blend-mode", "normal", "important");
      node.style.setProperty("backdrop-filter", "none", "important");
      node.style.setProperty("-webkit-backdrop-filter", "none", "important");

      if(
        node.id === "stitchContent_translate" ||
        node.classList.contains("stitch-feature-content") ||
        node.classList.contains("stitch-opaque-translate-root")
      ){
        node.style.setProperty("background", "#070b16", "important");
        node.style.setProperty("background-color", "#070b16", "important");
      }

      node = node.parentElement;
    }

    qsa("section,.table-section,.card,.panel,table,thead,tbody,tr,td,th,input,select,textarea", root).forEach(el => {
      el.style.setProperty("opacity", "1", "important");
      el.style.setProperty("mix-blend-mode", "normal", "important");
      el.style.setProperty("backdrop-filter", "none", "important");
      el.style.setProperty("-webkit-backdrop-filter", "none", "important");
    });

    qsa("table", root).forEach(el => {
      el.style.setProperty("background", "#0b1220", "important");
      el.style.setProperty("background-color", "#0b1220", "important");
    });

    qsa("tbody td", root).forEach(el => {
      el.style.setProperty("background-color", "#151936", "important");
      el.style.setProperty("color", "#e5e7eb", "important");
    });

    qsa("th", root).forEach(el => {
      el.style.setProperty("background-color", "#07101f", "important");
      el.style.setProperty("color", "#ffffff", "important");
    });
  }

  if(document.readyState === "loading"){
    document.addEventListener("DOMContentLoaded", forceOpaque);
  }else{
    forceOpaque();
  }

  document.addEventListener("click", () => setTimeout(forceOpaque, 80), true);
  document.addEventListener("scroll", () => setTimeout(forceOpaque, 80), true);

  setTimeout(forceOpaque, 200);
  setTimeout(forceOpaque, 800);
  setTimeout(forceOpaque, 1800);

  const obs = new MutationObserver(() => {
    clearTimeout(window.__translateOpaqueHotfix);
    window.__translateOpaqueHotfix = setTimeout(forceOpaque, 80);
  });

  obs.observe(document.body, {childList:true, subtree:true, attributes:true});
})();
