const LEVERAGE_FILTERS = {
  all: ["Low", "Medium", "High", "Very High"],
  nonLow: ["Medium", "High", "Very High"],
  mediumPlus: ["Medium", "High", "Very High"],
  highPlus: ["High", "Very High"],
  veryHigh: ["Very High"],
};

let leverageManifestCache = null;
const gameLeverageCache = new Map();

async function loadLeverageManifest() {
  if (leverageManifestCache) return leverageManifestCache;

  const urls = [
    "data/leverage/manifest.json",
    "public/data/leverage/manifest.json"
  ];

  let lastError = null;

  for (const url of urls) {
    try {
      const res = await fetch(url);
      if (res.ok) {
        leverageManifestCache = await res.json();
        leverageManifestCache.__baseUrl = url.startsWith("public/") ? "public/" : "";
        return leverageManifestCache;
      }
      lastError = new Error(`Failed ${url}: ${res.status}`);
    } catch (err) {
      lastError = err;
    }
  }

  throw lastError || new Error("Leverage manifest unavailable");
}

function possibleGameIds(gameId, year) {
  const raw = String(gameId || "").replace(".csv", "").trim();
  const noZeros = raw.replace(/^0+/, "");

  return new Set([
    raw,
    noZeros,
    `${year}_${raw}`,
    `${year}_${noZeros}`,
  ]);
}

async function getLeverageFileForGame(year, gameId) {
  const manifest = await loadLeverageManifest();
  const yearInfo = manifest.years?.[String(year)];

  if (!yearInfo?.available) return null;

  const candidates = possibleGameIds(gameId, year);

  return yearInfo.files.find(file => candidates.has(String(file.game_id))) || null;
}

function parseCsv(text) {
  const rows = [];
  let row = [];
  let cell = "";
  let insideQuotes = false;

  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    const next = text[i + 1];

    if (ch === '"' && next === '"') {
      cell += '"';
      i++;
    } else if (ch === '"') {
      insideQuotes = !insideQuotes;
    } else if (ch === "," && !insideQuotes) {
      row.push(cell);
      cell = "";
    } else if ((ch === "\n" || ch === "\r") && !insideQuotes) {
      if (ch === "\r" && next === "\n") i++;
      row.push(cell);
      if (row.some(v => v !== "")) rows.push(row);
      row = [];
      cell = "";
    } else {
      cell += ch;
    }
  }

  if (cell || row.length) {
    row.push(cell);
    rows.push(row);
  }

  if (!rows.length) return [];

  const headers = rows[0].map(h => h.trim());

  return rows.slice(1).map(values => {
    const obj = {};
    headers.forEach((h, i) => {
      obj[h] = values[i] ?? "";
    });
    return obj;
  });
}

async function loadGameLeverageRows(year, gameId) {
  const fileInfo = await getLeverageFileForGame(year, gameId);
  if (!fileInfo) return [];

  const cacheKey = `${year}:${fileInfo.game_id}`;
  if (gameLeverageCache.has(cacheKey)) return gameLeverageCache.get(cacheKey);

  const manifest = await loadLeverageManifest();
  const urls = [
    fileInfo.file,
    `${manifest.__baseUrl || ""}${fileInfo.file}`
  ];

  let res = null;

  for (const url of urls) {
    try {
      res = await fetch(url);
      if (res.ok) break;
    } catch (err) {}
  }

  if (!res || !res.ok) return [];

  const rows = parseCsv(await res.text());
  gameLeverageCache.set(cacheKey, rows);
  return rows;
}

function filterLeverageRows(rows, filter = "all") {
  const allowed = new Set(LEVERAGE_FILTERS[filter] || LEVERAGE_FILTERS.all);
  return rows.filter(row => allowed.has(row.leverage_bucket));
}

async function loadSeriesLeverageRows(year, gameIds, filter = "all") {
  const allRows = [];

  for (const gameId of gameIds || []) {
    const rows = await loadGameLeverageRows(year, gameId);
    allRows.push(...filterLeverageRows(rows, filter));
  }

  return allRows;
}

window.PlayoffLeverage = {
  LEVERAGE_FILTERS,
  loadLeverageManifest,
  loadGameLeverageRows,
  loadSeriesLeverageRows,
  filterLeverageRows,
};
