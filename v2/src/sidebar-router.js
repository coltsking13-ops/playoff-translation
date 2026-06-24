(function () {
  function setActive(tab) {
    document.querySelectorAll("#sideNav button").forEach(btn => {
      const match = btn.dataset.tab === tab || btn.dataset.global === tab;
      btn.classList.toggle("active", match);
    });
  }

  function showLeaderboards() {
    const globalPanel = document.getElementById("globalPanel");
    const playerView = document.getElementById("playerView");

    setActive("leaderboards");

    if (globalPanel) {
      globalPanel.classList.add("open");
      globalPanel.scrollIntoView({ behavior: "smooth", block: "start" });
    }

    if (playerView) {
      playerView.classList.add("empty");
      playerView.innerHTML = `<div class="empty-state">Global Leaderboards</div>`;
    }
  }

  function routeTo(tab) {
    const globalPanel = document.getElementById("globalPanel");
    if (globalPanel) globalPanel.classList.remove("open");

    setActive(tab);

    const realTab = document.querySelector(`.tab[data-tab="${tab}"]`);
    if (realTab) {
      realTab.click();
      return;
    }

    const playerView = document.getElementById("playerView");
    if (playerView && !document.querySelector(".player-title")) {
      playerView.classList.remove("empty");
      playerView.innerHTML = `<div class="empty-state">Search a player first.</div>`;
    }
  }

  document.addEventListener("click", function (e) {
    const btn = e.target.closest("#sideNav button");
    if (!btn) return;

    e.preventDefault();

    if (btn.dataset.global === "leaderboards") {
      showLeaderboards();
      return;
    }

    if (btn.dataset.tab) {
      routeTo(btn.dataset.tab);
    }
  });
})();
