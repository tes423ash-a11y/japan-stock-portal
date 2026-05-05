// ==============================
// 日本株 投資ポータル
// 銘柄管理・損切り/利確ライン管理つき
// データはこのスマホ/ブラウザの localStorage に保存します。
// ==============================

const defaultStocks = [
  { id: "7011", code: "7011", name: "三菱重工業", theme: "防衛", status: "保有", entryPrice: "", stopLoss: "", targetPrice: "", earningsDate: "", memo: "防衛・宇宙・原子力も含む大型本命候補。" },
  { id: "7012", code: "7012", name: "川崎重工業", theme: "防衛", status: "監視", entryPrice: "", stopLoss: "", targetPrice: "", earningsDate: "", memo: "防衛、航空、造船、エネルギー関連を監視。" },
  { id: "5803", code: "5803", name: "フジクラ", theme: "データセンター", status: "監視", entryPrice: "", stopLoss: "", targetPrice: "", earningsDate: "", memo: "光ファイバー・データセンター関連。値動きが大きい。" },
  { id: "5802", code: "5802", name: "住友電気工業", theme: "データセンター", status: "候補", entryPrice: "", stopLoss: "", targetPrice: "", earningsDate: "", memo: "電線、光通信、自動車関連。大型で流動性あり。" },
  { id: "8035", code: "8035", name: "東京エレクトロン", theme: "半導体", status: "監視", entryPrice: "", stopLoss: "", targetPrice: "", earningsDate: "", memo: "半導体製造装置の主力。指数影響も大きい。" },
  { id: "6857", code: "6857", name: "アドバンテスト", theme: "半導体", status: "監視", entryPrice: "", stopLoss: "", targetPrice: "", earningsDate: "", memo: "半導体テスター。AI半導体需要の影響を受けやすい。" },
  { id: "4478", code: "4478", name: "freee", theme: "AI/SaaS", status: "候補", entryPrice: "", stopLoss: "", targetPrice: "", earningsDate: "", memo: "バックオフィスSaaS。成長性と赤字縮小を確認。" },
  { id: "4475", code: "4475", name: "HENNGE", theme: "AI/SaaS", status: "監視", entryPrice: "", stopLoss: "", targetPrice: "", earningsDate: "", memo: "ID管理・セキュリティSaaS。チャート形状重視。" },
  { id: "1605", code: "1605", name: "INPEX", theme: "資源", status: "監視", entryPrice: "", stopLoss: "", targetPrice: "", earningsDate: "", memo: "原油・天然ガス。資源高・円安局面で確認。" },
  { id: "5713", code: "5713", name: "住友金属鉱山", theme: "資源", status: "候補", entryPrice: "", stopLoss: "", targetPrice: "", earningsDate: "", memo: "銅・ニッケル・金価格との連動を確認。" },
  { id: "9501", code: "9501", name: "東京電力HD", theme: "電力", status: "監視", entryPrice: "", stopLoss: "", targetPrice: "", earningsDate: "", memo: "原発再稼働、電力需給、政策材料を確認。" },
  { id: "9503", code: "9503", name: "関西電力", theme: "電力", status: "候補", entryPrice: "", stopLoss: "", targetPrice: "", earningsDate: "", memo: "原発比率と電力市況を確認。" },
  { id: "5074", code: "5074", name: "テスホールディングス", theme: "蓄電池", status: "監視", entryPrice: "", stopLoss: "", targetPrice: "", earningsDate: "", memo: "再エネ・系統用蓄電池テーマ。受注残を確認。" },
  { id: "6996", code: "6996", name: "ニチコン", theme: "蓄電池", status: "候補", entryPrice: "", stopLoss: "", targetPrice: "", earningsDate: "", memo: "蓄電・電源関連。業績トレンドを確認。" },
  { id: "ipo-note", code: "0000", name: "IPO候補メモ", theme: "IPO", status: "候補", entryPrice: "", stopLoss: "", targetPrice: "", earningsDate: "", memo: "直近IPOは需給・VC・初値位置を確認。必要に応じて書き換え。" }
];

const baseThemes = ["すべて", "防衛", "データセンター", "半導体", "AI/SaaS", "資源", "電力", "蓄電池", "IPO"];
const memoFields = ["今日の強いテーマ", "気になる銘柄", "決算跨ぎ候補", "損切りライン", "利確ライン"];
const storageKey = "stockPortal:managedStocks:v1";

const stockForm = document.getElementById("stockForm");
const stockCodeInput = document.getElementById("stockCode");
const generatedLinks = document.getElementById("generatedLinks");
const themeFilters = document.getElementById("themeFilters");
const watchlistGrid = document.getElementById("watchlistGrid");
const memoGrid = document.getElementById("memoGrid");
const portfolioSummary = document.getElementById("portfolioSummary");
const stockEditorForm = document.getElementById("stockEditorForm");
const resetEditorButton = document.getElementById("resetEditorButton");
const saveStockButton = document.getElementById("saveStockButton");
const themeOptions = document.getElementById("themeOptions");

let activeTheme = "すべて";
let stocks = loadStocks();

function cleanCode(value) {
  return value.replace(/[^0-9]/g, "").slice(0, 5);
}

function makeId() {
  return `stock-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function loadStocks() {
  try {
    const saved = localStorage.getItem(storageKey);
    if (!saved) return defaultStocks;
    const parsed = JSON.parse(saved);
    if (!Array.isArray(parsed)) return defaultStocks;
    return parsed.map(normalizeStock);
  } catch (error) {
    console.warn("銘柄データの読み込みに失敗しました", error);
    return defaultStocks;
  }
}

function saveStocks() {
  localStorage.setItem(storageKey, JSON.stringify(stocks));
}

function normalizeStock(stock) {
  return {
    id: stock.id || stock.code || makeId(),
    code: cleanCode(stock.code || ""),
    name: stock.name || "名称未設定",
    theme: stock.theme || "未分類",
    status: stock.status || "監視",
    entryPrice: stock.entryPrice || "",
    stopLoss: stock.stopLoss || "",
    targetPrice: stock.targetPrice || "",
    earningsDate: stock.earningsDate || "",
    memo: stock.memo || ""
  };
}

function getThemes() {
  const userThemes = [...new Set(stocks.map(stock => stock.theme).filter(Boolean))];
  return ["すべて", ...new Set([...baseThemes.filter(theme => theme !== "すべて"), ...userThemes])];
}

function getStockLinks(code) {
  return [
    { label: "株探", url: `https://kabutan.jp/stock/?code=${code}` },
    { label: "Yahoo!ファイナンス", url: `https://finance.yahoo.co.jp/quote/${code}.T` },
    { label: "TradingView", url: `https://jp.tradingview.com/symbols/TSE-${code}/` },
    { label: "TDnet", url: "https://www.release.tdnet.info/inbs/I_main_00.html" },
    { label: "EDINET", url: "https://disclosure2.edinet-fsa.go.jp/" }
  ];
}

function renderGeneratedLinks(code) {
  if (!code) {
    generatedLinks.innerHTML = "<p class='hint'>銘柄コードを入力してください。</p>";
    return;
  }

  generatedLinks.innerHTML = getStockLinks(code)
    .map(link => `<a href="${link.url}" target="_blank" rel="noopener noreferrer"><span>${link.label}</span><strong>開く →</strong></a>`)
    .join("");
}

function renderThemeFilters() {
  const themes = getThemes();
  if (!themes.includes(activeTheme)) activeTheme = "すべて";

  themeFilters.innerHTML = themes
    .map(theme => `<button type="button" class="filter-button ${theme === activeTheme ? "active" : ""}" data-theme="${theme}">${theme}</button>`)
    .join("");

  document.querySelectorAll(".filter-button").forEach(button => {
    button.addEventListener("click", () => {
      activeTheme = button.dataset.theme;
      renderAll();
    });
  });
}

function renderThemeOptions() {
  themeOptions.innerHTML = getThemes()
    .filter(theme => theme !== "すべて")
    .map(theme => `<option value="${theme}"></option>`)
    .join("");
}

function statusClass(status) {
  if (status === "保有") return "holding";
  if (status === "候補") return "candidate";
  return "watch";
}

function formatValue(value, suffix = "") {
  if (value === undefined || value === null || value === "") return "未入力";
  return `${Number(value).toLocaleString("ja-JP")}${suffix}`;
}

function calcRiskReward(stock) {
  const entry = Number(stock.entryPrice);
  const stop = Number(stock.stopLoss);
  const target = Number(stock.targetPrice);
  if (!entry || !stop || !target || entry <= stop) return "未計算";
  const risk = entry - stop;
  const reward = target - entry;
  if (reward <= 0) return "未計算";
  return `RR 1:${(reward / risk).toFixed(2)}`;
}

function renderPortfolioSummary() {
  const holding = stocks.filter(stock => stock.status === "保有").length;
  const watch = stocks.filter(stock => stock.status === "監視").length;
  const candidate = stocks.filter(stock => stock.status === "候補").length;
  const withStop = stocks.filter(stock => stock.stopLoss).length;

  portfolioSummary.innerHTML = `
    <div class="summary-card"><span>保有</span><strong>${holding}</strong></div>
    <div class="summary-card"><span>監視</span><strong>${watch}</strong></div>
    <div class="summary-card"><span>候補</span><strong>${candidate}</strong></div>
    <div class="summary-card"><span>損切り設定</span><strong>${withStop}</strong></div>
  `;
}

function renderWatchlist() {
  const filtered = activeTheme === "すべて" ? stocks : stocks.filter(stock => stock.theme === activeTheme);

  if (filtered.length === 0) {
    watchlistGrid.innerHTML = "<p class='empty-message'>該当する銘柄がありません。上のフォームから追加できます。</p>";
    return;
  }

  watchlistGrid.innerHTML = filtered.map(stock => {
    const links = getStockLinks(stock.code).slice(0, 3).map(link => `<a href="${link.url}" target="_blank" rel="noopener noreferrer">${link.label}</a>`).join("");

    return `
      <article class="stock-card">
        <div class="stock-card-head">
          <div>
            <span class="stock-code">${stock.code}</span>
            <h3>${stock.name}</h3>
          </div>
          <span class="status ${statusClass(stock.status)}">${stock.status}</span>
        </div>
        <span class="theme-tag">#${stock.theme}</span>

        <div class="trade-grid">
          <div><span>Entry</span><strong>${formatValue(stock.entryPrice, "円")}</strong></div>
          <div><span>損切り</span><strong>${formatValue(stock.stopLoss, "円")}</strong></div>
          <div><span>利確</span><strong>${formatValue(stock.targetPrice, "円")}</strong></div>
          <div><span>決算日</span><strong>${stock.earningsDate || "未入力"}</strong></div>
          <div class="wide"><span>R:R</span><strong>${calcRiskReward(stock)}</strong></div>
        </div>

        <p>${stock.memo || "メモ未入力"}</p>
        <div class="stock-links">${links}</div>
        <div class="card-actions">
          <button type="button" class="small-button" data-action="edit" data-id="${stock.id}">編集</button>
          <button type="button" class="small-button danger" data-action="delete" data-id="${stock.id}">削除</button>
        </div>
      </article>
    `;
  }).join("");

  document.querySelectorAll("[data-action='edit']").forEach(button => {
    button.addEventListener("click", () => fillEditor(button.dataset.id));
  });

  document.querySelectorAll("[data-action='delete']").forEach(button => {
    button.addEventListener("click", () => deleteStock(button.dataset.id));
  });
}

function getEditorValues() {
  return normalizeStock({
    id: document.getElementById("editStockId").value || makeId(),
    code: document.getElementById("editorCode").value,
    name: document.getElementById("editorName").value.trim(),
    theme: document.getElementById("editorTheme").value.trim(),
    status: document.getElementById("editorStatus").value,
    entryPrice: document.getElementById("editorEntryPrice").value,
    stopLoss: document.getElementById("editorStopLoss").value,
    targetPrice: document.getElementById("editorTargetPrice").value,
    earningsDate: document.getElementById("editorEarningsDate").value,
    memo: document.getElementById("editorMemo").value.trim()
  });
}

function resetEditor() {
  stockEditorForm.reset();
  document.getElementById("editStockId").value = "";
  document.getElementById("editorStatus").value = "監視";
  saveStockButton.textContent = "銘柄を保存";
}

function fillEditor(id) {
  const stock = stocks.find(item => item.id === id);
  if (!stock) return;

  document.getElementById("editStockId").value = stock.id;
  document.getElementById("editorCode").value = stock.code;
  document.getElementById("editorName").value = stock.name;
  document.getElementById("editorTheme").value = stock.theme;
  document.getElementById("editorStatus").value = stock.status;
  document.getElementById("editorEntryPrice").value = stock.entryPrice;
  document.getElementById("editorStopLoss").value = stock.stopLoss;
  document.getElementById("editorTargetPrice").value = stock.targetPrice;
  document.getElementById("editorEarningsDate").value = stock.earningsDate;
  document.getElementById("editorMemo").value = stock.memo;
  saveStockButton.textContent = "変更を保存";
  document.getElementById("stock-manager").scrollIntoView({ behavior: "smooth", block: "start" });
}

function deleteStock(id) {
  const stock = stocks.find(item => item.id === id);
  if (!stock) return;
  const confirmed = window.confirm(`${stock.code} ${stock.name} を削除しますか？`);
  if (!confirmed) return;
  stocks = stocks.filter(item => item.id !== id);
  saveStocks();
  resetEditor();
  renderAll();
}

function upsertStock(event) {
  event.preventDefault();
  const stock = getEditorValues();

  if (!stock.code || !stock.name || !stock.theme) {
    alert("銘柄コード、銘柄名、テーマを入力してください。");
    return;
  }

  const currentId = document.getElementById("editStockId").value;
  const existingIndex = stocks.findIndex(item => item.id === currentId);

  if (existingIndex >= 0) {
    stocks[existingIndex] = stock;
  } else {
    stocks.unshift(stock);
  }

  saveStocks();
  activeTheme = stock.theme;
  resetEditor();
  renderAll();
  document.getElementById("watchlist").scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderMemos() {
  memoGrid.innerHTML = memoFields.map(field => {
    const key = `stockPortalMemo:${field}`;
    const savedValue = localStorage.getItem(key) || "";
    return `
      <div class="memo-item">
        <label for="${key}">${field}</label>
        <textarea id="${key}" data-storage-key="${key}" placeholder="ここにメモを入力">${savedValue}</textarea>
      </div>
    `;
  }).join("");

  document.querySelectorAll("textarea[data-storage-key]").forEach(textarea => {
    textarea.addEventListener("input", () => {
      localStorage.setItem(textarea.dataset.storageKey, textarea.value);
    });
  });
}

function renderAll() {
  renderThemeOptions();
  renderThemeFilters();
  renderPortfolioSummary();
  renderWatchlist();
}

stockCodeInput.addEventListener("input", () => {
  stockCodeInput.value = cleanCode(stockCodeInput.value);
});

document.getElementById("editorCode").addEventListener("input", event => {
  event.target.value = cleanCode(event.target.value);
});

stockForm.addEventListener("submit", event => {
  event.preventDefault();
  const code = cleanCode(stockCodeInput.value);
  renderGeneratedLinks(code);
});

stockEditorForm.addEventListener("submit", upsertStock);
resetEditorButton.addEventListener("click", resetEditor);

renderAll();
renderMemos();
renderGeneratedLinks("7011");
