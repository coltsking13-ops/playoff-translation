(function(){
  function isVisible(el){
    if (!el || !el.getBoundingClientRect) return false;
    const cs = getComputedStyle(el);
    if (cs.display === "none" || cs.visibility === "hidden" || cs.opacity === "0") return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  }

  function looksLikeDatasetText(t){
    if (!t) return false;
    t = String(t).trim();
    if (t.length < 300) return false;

    const needles = [
      '"playerId"', '"playerName"', '"nbaId"', '"gameId"', '"seriesCode"',
      '"AdjTS%"', '"rAdjTS"', '"ScoringTOV"', '"Heaves"', '"ZBounds"',
      '"teamAdjTS_source"', '"OppRSAdjTSAllowed"', '"playerGames"', '"playerSeasons"'
    ];

    let hits = 0;
    for (const n of needles) if (t.includes(n)) hits++;

    return hits >= 3 || (t.startsWith('{"') && t.includes('"playerName"')) || (t.startsWith('[{"') && t.includes('"playerName"'));
  }

  function clean(){
    // remove obvious debug/raw blocks
    document.querySelectorAll(
      'pre, code, .debug, .dev, .developer, .raw-json, [data-debug], [id*="debug" i], [class*="debug" i], [id*="raw" i], [class*="raw" i]'
    ).forEach(el => {
      if (looksLikeDatasetText(el.innerText || el.textContent || "")) {
        el.remove();
      }
    });

    // remove any visible element directly printing dataset text
    const all = Array.from(document.body.querySelectorAll("body *"));
    for (const el of all) {
      if (["SCRIPT", "STYLE", "TEXTAREA", "INPUT", "SELECT", "OPTION"].includes(el.tagName)) continue;
      if (!isVisible(el)) continue;

      const own = Array.from(el.childNodes)
        .filter(n => n.nodeType === Node.TEXT_NODE)
        .map(n => n.nodeValue)
        .join(" ")
        .trim();

      if (looksLikeDatasetText(own)) {
        el.remove();
        continue;
      }

      // only remove huge leaf-ish containers, not the whole app shell
      const txt = (el.innerText || "").trim();
      if (looksLikeDatasetText(txt) && el.children.length <= 3) {
        el.remove();
      }
    }

    // emergency: wipe body text nodes that are huge raw JSON
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    const bad = [];
    while (walker.nextNode()) {
      const node = walker.currentNode;
      const p = node.parentElement;
      if (!p || ["SCRIPT", "STYLE"].includes(p.tagName)) continue;
      if (looksLikeDatasetText(node.nodeValue)) bad.push(node);
    }
    bad.forEach(n => n.nodeValue = "");
  }

  function run(){
    clean();
    setTimeout(clean, 250);
    setTimeout(clean, 1000);
    setTimeout(clean, 2500);
    setTimeout(clean, 5000);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", run);
  else run();
})();
