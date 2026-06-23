(function(){
  console.log("FINAL READABLE TOOLS LOADED");

  function qsa(sel, root=document){ return Array.from(root.querySelectorAll(sel)); }
  function qs(sel, root=document){ return root.querySelector(sel); }
  function text(el){ return String(el?.textContent || ""); }
  function norm(s){ return String(s || "").toLowerCase().replace(/\s+/g," ").trim(); }

  function findTranslationModule(){
    const headings = qsa("h1,h2,h3,h4,.section-title,strong,b");
    const heading = headings.find(h => norm(text(h)).includes("series translation consistency"));
    if(!heading) return null;

    let el = heading;
    while(el && el !== document.body){
      const t = norm(text(el));
      const hasTable = !!qs("table", el);
      const hasCards = t.includes("offense translates") && t.includes("defense translates") && t.includes("net translates");

      if(hasTable && hasCards) return el;
      el = el.parentElement;
    }

    return heading.closest("section,.table-section,.card,.panel,div");
  }

  function forceWhiteModule(root){
    if(!root) return;

    root.classList.add("force-white-tool");

    root.style.setProperty("background", "#ffffff", "important");
    root.style.setProperty("background-color", "#ffffff", "important");
    root.style.setProperty("color", "#111827", "important");
    root.style.setProperty("opacity", "1", "important");
    root.style.setProperty("filter", "none", "important");
    root.style.setProperty("mix-blend-mode", "normal", "important");
    root.style.setProperty("backdrop-filter", "none", "important");
    root.style.setProperty("-webkit-backdrop-filter", "none", "important");

    qsa("section,.table-section,.card,.panel,.summary-card,.translate-card,.translation-card", root).forEach(el => {
      el.classList.add("force-white-tool");
      el.style.setProperty("background", "#ffffff", "important");
      el.style.setProperty("background-color", "#ffffff", "important");
      el.style.setProperty("color", "#111827", "important");
      el.style.setProperty("opacity", "1", "important");
    });

    qsa("input,select,textarea", root).forEach(el => {
      el.style.setProperty("background", "#ffffff", "important");
      el.style.setProperty("background-color", "#ffffff", "important");
      el.style.setProperty("color", "#111827", "important");
      el.style.setProperty("border", "1px solid rgba(59,92,165,.45)", "important");
    });

    qsa("option", root).forEach(el => {
      el.style.setProperty("background", "#ffffff", "important");
      el.style.setProperty("color", "#111827", "important");
    });

    qsa("table", root).forEach(table => {
      table.style.setProperty("background", "#ffffff", "important");
      table.style.setProperty("background-color", "#ffffff", "important");
      table.style.setProperty("color", "#111827", "important");
    });

    qsa("th", root).forEach(th => {
      th.style.setProperty("background", "#061d2d", "important");
      th.style.setProperty("background-color", "#061d2d", "important");
      th.style.setProperty("color", "#ffffff", "important");
      th.style.setProperty("font-weight", "1000", "important");
    });

    qsa("tbody tr", root).forEach((tr, index) => {
      const bg = index % 2 ? "#f8fafc" : "#ffffff";
      tr.style.setProperty("background", bg, "important");
      tr.style.setProperty("background-color", bg, "important");
    });

    qsa("tbody td", root).forEach(td => {
      const t = norm(text(td));
      const row = td.closest("tr");
      const rows = qsa("tbody tr", td.closest("table") || root);
      const index = rows.indexOf(row);
      const bg = index % 2 ? "#f8fafc" : "#ffffff";

      td.style.setProperty("background", bg, "important");
      td.style.setProperty("background-color", bg, "important");
      td.style.setProperty("color", "#111827", "important");
      td.style.setProperty("font-weight", "800", "important");
      td.style.setProperty("opacity", "1", "important");

      if(t === "yes"){
        td.textContent = "YES";
        td.classList.add("final-yes");
        td.style.setProperty("color", "#16a34a", "important");
        td.style.setProperty("font-weight", "1000", "important");
      }

      if(t === "no"){
        td.textContent = "NO";
        td.classList.add("final-no");
        td.style.setProperty("color", "#64748b", "important");
        td.style.setProperty("font-weight", "1000", "important");
      }
    });

    qsa("h1,h2,h3,h4,.section-title", root).forEach(el => {
      el.style.setProperty("color", "#000000", "important");
    });

    qsa("p,small,label,span", root).forEach(el => {
      if(el.closest("th")) return;
      const t = norm(text(el));

      if(t === "yes"){
        el.textContent = "YES";
        el.classList.add("final-yes");
        el.style.setProperty("color", "#16a34a", "important");
      }else if(t === "no"){
        el.textContent = "NO";
        el.classList.add("final-no");
        el.style.setProperty("color", "#64748b", "important");
      }else{
        el.style.setProperty("color", "#111827", "important");
      }
    });
  }

  function forceStretchWhite(){
    const roots = [qs("#cleanContent_stretches"), qs("#stitchContent_stretches")].filter(Boolean);

    roots.forEach(root => {
      qsa(".stat-card,.metric-card,.card", root).forEach(card => {
        card.style.setProperty("background", "#ffffff", "important");
        card.style.setProperty("background-color", "#ffffff", "important");
        card.style.setProperty("color", "#111827", "important");

        qsa("*", card).forEach(el => {
          const t = text(el).trim();
          if(t.startsWith("+")){
            el.style.setProperty("color", "#16a34a", "important");
            el.style.setProperty("font-weight", "1000", "important");
          }else{
            el.style.setProperty("color", "#111827", "important");
          }
        });
      });

      qsa("select,option,input", root).forEach(el => {
        el.style.setProperty("background", "#ffffff", "important");
        el.style.setProperty("color", "#111827", "important");
      });
    });
  }

  function run(){
    const module = findTranslationModule();
    forceWhiteModule(module);
    forceStretchWhite();
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
  setTimeout(run, 1000);
  setTimeout(run, 2200);

  const obs = new MutationObserver(() => {
    clearTimeout(window.__finalReadableTools);
    window.__finalReadableTools = setTimeout(run, 100);
  });

  obs.observe(document.body, {childList:true, subtree:true});
})();
