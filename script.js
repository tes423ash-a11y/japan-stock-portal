// ==============================
// 日本株 投資ポータル
// 初心者でも編集しやすいように、データと処理を分けています。
// ==============================

// テーマ別ウォッチリストの元データです。
// 銘柄を追加したい場合は、この配列に同じ形で追加してください。
const stocks = [
  { code: "7011", name: "三菱重工業", theme: "防衛", status: "保有", memo: "防衛・宇宙・原子力も含む大型本命候補。" },
  { code: "7012", name: "川崎重工業", theme: "防衛", status: "監視", memo: "防衛、航空、造船、エネルギー関連を監視。" },
  { code: "5803", name: "フジクラ", theme: "データセンター", status: "監視", memo: "光ファイバー・データセンター関連。値動きが大きい。" },
  { code: "5802", name: "住友電気工業", theme: "データセンター", status: "候補", memo: "電線、光通信、自動車関連。大型で流動性あり。" },
  { code: "8035", name: "東京エレクトロン", theme: "半導体", status: "監視", memo: "半導体製造装置の主力。指数影響も大きい。" },
  { code: "6857", name: "アドバンテスト", theme: "半導体", status: "監視", memo: "半導体テスター。AI半導体需要の影響を受けやすい。" },
  { code: "4478", name: "freee", theme: "AI/SaaS", status: "候補", memo: "バックオフィスSaaS。成長性と赤字縮小を確認。" },
  { code: "4475", name: "HENNGE", theme: "AI/SaaS", status: "監視", memo: "ID管理・セキュリティSaaS。チャート形状重視。" },
  { code: "1605", name: "INPEX", theme: "資源", status: "監視", memo: "原油・天然ガス。資源高・円安局面で確認。" },
  { code: "5713", name: "住友金属鉱山", theme: "資源", status: "候補", memo: "銅・ニッケル・金価格との連動を確認。" },
  { code: "9501", name: "東京電力HD", theme: "電力", status: "監視", memo: "原発再稼働、電力需給、政策材料を確認。" },
  { code: "9503", name: "関西電力", theme: "電力", status: "候補", memo: "原発比率と電力市況を確認。" },
  { code: "5074", name: "テスホールディングス", theme: "蓄電池", status: "監視", memo: "再エネ・系統用蓄電池テーマ。受注残を確認。" },
  { code: "6996", name: "ニチコン", theme: "蓄電池", status: "候補", memo: "蓄電・電源関連。業績トレンドを確認。" },
  { code: "0000", name: "IPO候補メモ", theme: "IPO", status: "候補", memo: "直近IPOは需給・VC・初値位置を確認。必要に応じて書き換え。" }
];

const themes = ["すべて", "防衛", "データセンター", "半導体", "AI/SaaS", "資源", "電力", "蓄電池", "IPO"];
const memoFields = ["今日の強いテーマ", "気になる銘柄", "決算跨ぎ候補", "損切りライン", "利確ライン"];

const stockForm = document.getElementById("stockForm");
const stockCodeInput = document.getElementById("stockCode");
const generatedLinks = document.getElementById("generatedLinks");
const themeFilters = document.getElementById("themeFilters");
const watchlistGrid = document.getElementById("watchlistGrid");
const memoGrid = document.getElementById("memoGrid");

let activeTheme = "すべて";

function cleanCode(value) {
  return value.replace(/[^0-9]/g, "").slice(0, 5);
}

function getStockLinks(code) {
  return [
    { label: "株探", url: `https://kabutan.jp/stock/?code=${code}` },
    { label: "Yahoo!ファイナンス", url: `https://finance.yahoo.co.jp/quote/${code}.T` },
    { label: "TradingView", url: `https://jp.tradingview.com/symbols/TSE-${code}/` },
    { label: "TDnet", url: `https://www.release.tdnet.info/inbs/I_main_00.html` },
    { label: "EDINET", url: `https://disclosure2.edinet-fsa.go.jp/` }
  ];
}

function renderGeneratedLinks(code) {
  if (!code) {
    generatedLinks.innerHTML = "<p class='hint'>銘柄コードを入力してください。</p>";
    return;
  }

  const links = getStockLinks(code)
    .map(link => `<a href="${link.url}" target="_blank" rel="noopener noreferrer"><span>${link.label}</span><strong>開く →</strong></a>`)
    .join("");

  generatedLinks.innerHTML = links;
}

function renderThemeFilters() {
  themeFilters.innerHTML = themes
    .map(theme => `<button type="button" class="filter-button ${theme === activeTheme ? "active" : ""}" data-theme="${theme}">${theme}</button>`)
    .join("");

  document.querySelectorAll(".filter-button").forEach(button => {
    button.addEventListener("click", () => {
      activeTheme = button.dataset.theme;
      renderThemeFilters();
      renderWatchlist();
    });
  });
}

function statusClass(status) {
  if (status === "保有") return "holding";
  if (status === "候補") return "candidate";
  return "watch";
}

function renderWatchlist() {
  const filtered = activeTheme === "すべて" ? stocks : stocks.filter(stock => stock.theme === activeTheme);

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
        <p>${stock.memo}</p>
        <div class="stock-links">${links}</div>
      </article>
    `;
  }).join("");
}

function renderMemos() {
  memoGrid.innerHTML = memoFields.map(field => {
    const storageKey = `stockPortalMemo:${field}`;
    const savedValue = localStorage.getItem(storageKey) || "";
    return `
      <div class="memo-item">
        <label for="${storageKey}">${field}</label>
        <textarea id="${storageKey}" data-storage-key="${storageKey}" placeholder="ここにメモを入力">${savedValue}</textarea>
      </div>
    `;
  }).join("");

  document.querySelectorAll("textarea[data-storage-key]").forEach(textarea => {
    textarea.addEventListener("input", () => {
      localStorage.setItem(textarea.dataset.storageKey, textarea.value);
    });
  });
}

stockCodeInput.addEventListener("input", () => {
  stockCodeInput.value = cleanCode(stockCodeInput.value);
});

stockForm.addEventListener("submit", event => {
  event.preventDefault();
  const code = cleanCode(stockCodeInput.value);
  renderGeneratedLinks(code);
});

renderThemeFilters();
renderWatchlist();
renderMemos();
renderGeneratedLinks("7011");
