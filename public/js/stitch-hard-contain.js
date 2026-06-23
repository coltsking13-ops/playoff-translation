(function(){
  console.log("STITCH HARD CONTAIN LOADED");

  function qsa(sel, root=document){ return Array.from(root.querySelectorAll(sel)); }
  function qs(sel, root=document){ return root.querySelector(sel); }

  function activePage(){
    return qs("#stitchApp .stitch-page.active") || qs("#stitchPage_home");
  }

  function cleanRootBleed(){
    document.body.classList.add("stitch-merged");

    // Hide direct root app/main elements that are NOT the Stitch shell.
    Array.from(document.body.children).forEach(el => {
      if(el.id === "stitchApp") return;
      if(["SCRIPT","STYLE","LINK"].includes(el.tagName)) return;

      const tag = el.tagName.toLowerCase();
      const looksLikeOldApp =
        tag === "main" ||
        tag === "footer" ||
        el.id === "app" ||
        el.classList.contains("app") ||
        el.classList.contains("container") ||
        el.classList.contains("page");

      if(looksLikeOldApp){
        el.style.setProperty("display","none","important");
        el.style.setProperty("visibility","hidden","important");
        el.style.setProperty("height","0","important");
        el.style.setProperty("overflow","hidden","important");
      }
    });
  }

  function forceSinglePage(){
    const active = activePage();
    if(!active) return;

    qsa("#stitchApp .stitch-page").forEach(page => {
      const isActive = page === active;

      page.classList.toggle("active", isActive);

      page.style.setProperty("display", isActive ? "block" : "none", "important");
      page.style.setProperty("visibility", isActive ? "visible" : "hidden", "important");
      page.style.setProperty("height", isActive ? "auto" : "0", "important");
      page.style.setProperty("max-height", isActive ? "none" : "0", "important");
      page.style.setProperty("overflow", isActive ? "visible" : "hidden", "important");
      page.style.setProperty("opacity", isActive ? "1" : "0", "important");
      page.style.setProperty("pointer-events", isActive ? "auto" : "none", "important");
      page.style.setProperty("position", isActive ? "relative" : "absolute", "important");
    });

    const id = active.dataset.page || "home";

    qsa(".stitch-nav button,.stitch-mobile-bottom button").forEach(btn => {
      btn.classList.toggle("active", btn.dataset.page === id);
    });

    // Hard stop home cards bleeding into non-home pages.
    const home = qs("#stitchPage_home");
    if(home && id !== "home"){
      qsa(".stitch-bento,.stitch-watermark,.stitch-hero-grid", home).forEach(el => {
        el.style.setProperty("display","none","important");
      });
    }else if(home){
      qsa(".stitch-bento,.stitch-watermark,.stitch-hero-grid", home).forEach(el => {
        el.style.removeProperty("display");
      });
    }
  }

  function removeDuplicateNavs(){
    qsa("#ptlSideFeatureNav,.ptl-side-feature-nav,#ptlReferenceHome,#ptlFeaturePages,#nbaForceHeroShell,#nbaPlayerHeroShell,#finalToolHub,.final-tool-hub,.audience-tool-hub,.core-tool-hub").forEach(el => {
      if(!el.closest("#stitchApp")){
        el.remove();
      }
    });
  }

  function run(){
    cleanRootBleed();
    removeDuplicateNavs();
    forceSinglePage();
  }

  if(document.readyState === "loading"){
    document.addEventListener("DOMContentLoaded", run);
  }else{
    run();
  }

  document.addEventListener("click", () => setTimeout(run, 80), true);

  setTimeout(run, 200);
  setTimeout(run, 700);
  setTimeout(run, 1600);

  const obs = new MutationObserver(() => {
    clearTimeout(window.__stitchHardContainTimer);
    window.__stitchHardContainTimer = setTimeout(run, 80);
  });

  obs.observe(document.body, {childList:true, subtree:true});
})();
