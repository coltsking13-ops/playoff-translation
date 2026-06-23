(function(){
  console.log("UI FUNCTIONALITY FIX LOADED");

  function qs(sel, root=document){ return root.querySelector(sel); }
  function qsa(sel, root=document){ return Array.from(root.querySelectorAll(sel)); }
  function text(el){ return String(el?.textContent || ""); }
  function norm(s){ return String(s || "").toLowerCase().replace(/\s+/g," ").trim(); }

  function styleNativeOptions(){
    qsa("select").forEach(sel => {
      const inTranslate = !!sel.closest("#stitchContent_translate");
      sel.style.setProperty("font-weight","800","important");

      qsa("option", sel).forEach(opt => {
        opt.style.setProperty("background", inTranslate ? "#111827" : "#ffffff", "important");
        opt.style.setProperty("color", inTranslate ? "#ffffff" : "#111827", "important");
        opt.style.setProperty("font-weight", "800", "important");
      });
    });
  }

  function forceStretchMetricVisibility(){
    const root = qs("#stitchContent_stretches");
    if(!root) return;

    qsa(".stat-card,.metric-card", root).forEach(card => {
      const raw = text(card).trim();
      if(!raw) return;

      card.style.setProperty("background", "#0f172a", "important");
      card.style.setProperty("color", "#f8fafc", "important");

      qsa("*", card).forEach(el => {
        const t = text(el).trim();

        if(/^[-+]?\d/.test(t) || t === "—"){
          el.classList.add("stitch-force-visible-value");
          el.style.setProperty("color", t.startsWith("+") ? "#6ee787" : "#ffffff", "important");
          el.style.setProperty("font-weight", "1000", "important");
        }
      });

      const hasValue = /[-+]?\d/.test(raw) || raw.includes("—");
      const hasPlaceholder = qs(".stitch-placeholder-value", card);

      if(!hasValue && !hasPlaceholder){
        const dash = document.createElement("div");
        dash.className = "stitch-placeholder-value";
        dash.textContent = "—";
        card.appendChild(dash);
      }
    });

    qsa("*", root).forEach(el => {
      if(el.children.length) return;
      const t = text(el);
      if(t.includes("Weighted stats use POSS") && !el.dataset.methodSplit){
        el.dataset.methodSplit = "true";
        el.innerHTML = t
          .replace("Weighted stats use POSS", '<span class="stitch-method-note">Weighted stats use POSS')
          .replace("otherwise MIN.", "otherwise MIN.</span>");
      }
    });
  }

  function hideBadTranslateOverlays(){
    const root = qs("#stitchContent_translate");
    if(!root) return;

    qsa("*", root).forEach(el => {
      const t = norm(text(el));

      if(t.includes("open leverage explorer") || t.includes("optimize strategy explorer")){
        const box = el.closest(".dropdown,.popover,.tooltip,.card,.panel,button,div") || el;
        box.classList.add("stitch-kill-overlay");
        box.setAttribute("data-stitch-hidden-overlay","true");
      }

      if(t.includes("player games. series translation. real context")){
        const box = el.closest(".lab-hero,.hero,.card,.panel,section,div") || el;
        box.classList.add("stitch-translate-promo");
      }
    });
  }

  function moveActualTranslateTool(){
    const target = qs("#stitchContent_translate");
    if(!target) return;

    const already = Array.from(target.querySelectorAll("h1,h2,h3,h4,.section-title"))
      .some(h => norm(text(h)).includes("series translation consistency"));

    if(already) return;

    const heading = qsa("h1,h2,h3,h4,.section-title").find(h =>
      norm(text(h)).includes("series translation consistency")
    );

    if(!heading) return;

    const section = heading.closest(".table-section,section,.card,.panel,div");
    if(!section || target.contains(section)) return;

    section.classList.add("stitch-opaque-translate-root");
    target.insertBefore(section, target.firstChild);
  }

  function normalizeTranslateResults(){
    const root = qs("#stitchContent_translate");
    if(!root) return;

    qsa("td,span,div", root).forEach(el => {
      if(el.children.length) return;
      const t = norm(text(el));

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

    qsa("tbody td", root).forEach(td => {
      td.style.setProperty("color","#e5e7eb","important");
    });
  }

  function wireStretchButtons(){
    const root = qs("#stitchContent_stretches");
    if(!root) return;

    qsa("button", root).forEach(btn => {
      const t = norm(text(btn));

      if(t.includes("build stretch") && !btn.dataset.stitchWired){
        btn.dataset.stitchWired = "true";
        btn.addEventListener("click", () => {
          setTimeout(() => {
            try{
              if(typeof window.renderSelectedStretch === "function"){
                window.renderSelectedStretch();
              }
            }catch(e){
              console.warn("renderSelectedStretch failed", e);
            }
            forceStretchMetricVisibility();
          }, 60);
        });
      }

      if((t.includes("year stretch") || t.includes("build year")) && !btn.dataset.stitchWired){
        btn.dataset.stitchWired = "true";
        btn.addEventListener("click", () => {
          setTimeout(() => {
            try{
              if(typeof window.renderSelectedYearStretch === "function"){
                window.renderSelectedYearStretch();
              }
            }catch(e){
              console.warn("renderSelectedYearStretch failed", e);
            }
            forceStretchMetricVisibility();
          }, 60);
        });
      }
    });
  }

  function tryRenderTranslate(){
    const root = qs("#stitchContent_translate");
    if(!root) return;

    const fns = [
      "renderSeriesTranslate",
      "renderSeriesTranslation",
      "renderTranslationLab",
      "renderSeriesTranslationLab",
      "renderTranslateLab"
    ];

    for(const name of fns){
      try{
        if(typeof window[name] === "function"){
          window[name]();
          break;
        }
      }catch(e){
        console.warn(name, "failed", e);
      }
    }
  }

  function wireSidebarPageClicks(){
    qsa(".stitch-nav button,.stitch-mobile-bottom button").forEach(btn => {
      if(btn.dataset.functionFixWired) return;
      btn.dataset.functionFixWired = "true";

      btn.addEventListener("click", () => {
        setTimeout(() => {
          const page = btn.dataset.page;

          if(page === "translate"){
            moveActualTranslateTool();
            hideBadTranslateOverlays();
            normalizeTranslateResults();
            tryRenderTranslate();
          }

          if(page === "stretches"){
            styleNativeOptions();
            forceStretchMetricVisibility();
            wireStretchButtons();
          }
        }, 120);
      }, true);
    });
  }

  function run(){
    styleNativeOptions();
    moveActualTranslateTool();
    hideBadTranslateOverlays();
    normalizeTranslateResults();
    forceStretchMetricVisibility();
    wireStretchButtons();
    wireSidebarPageClicks();
  }

  if(document.readyState === "loading"){
    document.addEventListener("DOMContentLoaded", run);
  }else{
    run();
  }

  document.addEventListener("click", () => setTimeout(run, 100), true);
  document.addEventListener("change", () => setTimeout(run, 100), true);
  document.addEventListener("input", () => setTimeout(run, 100), true);

  setTimeout(run, 300);
  setTimeout(run, 1200);
  setTimeout(run, 2600);

  const obs = new MutationObserver(() => {
    clearTimeout(window.__uiFunctionalityFix);
    window.__uiFunctionalityFix = setTimeout(run, 120);
  });

  obs.observe(document.body, {childList:true, subtree:true});
})();
