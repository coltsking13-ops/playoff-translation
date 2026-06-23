(function(){
  function qsa(sel, root=document){ return Array.from(root.querySelectorAll(sel)); }
  function norm(s){ return String(s || "").trim().toLowerCase(); }

  function fixTranslateText(){
    const root = document.querySelector("#stitchContent_translate");
    if(!root) return;

    qsa("td,span,div", root).forEach(el => {
      if(el.children.length) return;

      const t = norm(el.textContent);

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

    // Any table cell that accidentally inherited black text gets forced readable.
    qsa("tbody td", root).forEach(td => {
      const t = norm(td.textContent);
      if(t === "yes" || t === "no") return;
      td.style.setProperty("color", "#e5e7eb", "important");
    });

    qsa("th", root).forEach(th => {
      th.style.setProperty("color", "#f8fafc", "important");
    });
  }

  if(document.readyState === "loading"){
    document.addEventListener("DOMContentLoaded", fixTranslateText);
  }else{
    fixTranslateText();
  }

  document.addEventListener("click", () => setTimeout(fixTranslateText, 100), true);
  document.addEventListener("input", () => setTimeout(fixTranslateText, 100), true);

  setTimeout(fixTranslateText, 300);
  setTimeout(fixTranslateText, 1200);

  const obs = new MutationObserver(() => {
    clearTimeout(window.__translateReadabilityTimer);
    window.__translateReadabilityTimer = setTimeout(fixTranslateText, 100);
  });

  obs.observe(document.body, {childList:true, subtree:true});
})();
