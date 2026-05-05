// ==============================
// ミネルヴィニSEPAスクリーナー拡張
// 既存の銘柄管理にSEPA用の入力項目、採点、ランキングを追加します。
// ==============================

const sepaNumberFields = [
  "currentPrice", "ma50", "ma150", "ma200", "week52High", "week52Low",
  "rsScore", "volumeRating", "baseRating", "vcpRating", "pivotPrice",
  "epsGrowth", "salesGrowth", "opProfitGrowth", "earningsRating", "themeRating", "supplyRating"
];

let activeSepaFilter = "all";
let activeSepaTheme = "すべて";

function readRawStocksForSepa() {
  try {
    const saved = localStorage.getItem(storageKey);
    return saved ? JSON.parse(saved) : defaultStocks;
  } catch (error) {
    console.warn("SEPA用データの読み込みに失敗しました", error);
    return defaultStocks;
  }
}

function extendedNormalizeStock(stock) {
  const base = {
    id: stock.id || stock.code || makeId(),
    code: cleanCode(stock.code || ""),
    name: stock.name || "名称未設定",
    theme: stock.theme || "未分類",
    status: stock.status || "監視",
    entryPrice: stock.entryPrice || "",
    stopLoss: stock.stopLoss || "",
    targetPrice: stock.targetPrice || stock.takeProfit || "",
    earningsDate: stock.earningsDate || "",
    memo: stock.memo || "",
    isBreakout: Boolean(stock.isBreakout)
  };

  sepaNumberFields.forEach(field => {
    base[field] = stock[field] || "";
  });

  return base;
}

normalizeStock = extendedNormalizeStock;
stocks = readRawStocksForSepa().map(normalizeStock);

function n(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : 0;
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function pct(value) {
  return Number.isFinite(value) ? `${value.toFixed(1)}%` : "未計算";
}

function calcTrendTemplate(stock) {
  const price = n(stock.currentPrice);
  const ma50 = n(stock.ma50);
  const ma150 = n(stock.ma150);
  const ma200 = n(stock.ma200);
  const high = n(stock.week52High);
  const low = n(stock.week52Low);
  const rs = n(stock.rsScore);

  const checks = [
    { label: "現在株価 > 50日線", passed: price > 0 && ma50 > 0 && price > ma50 },
    { label: "現在株価 > 150日線", passed: price > 0 && ma150 > 0 && price > ma150 },
    { label: "現在株価 > 200日線", passed: price > 0 && ma200 > 0 && price > ma200 },
    { label: "50日線 > 150日線", passed: ma50 > 0 && ma150 > 0 && ma50 > ma150 },
    { label: "150日線 > 200日線", passed: ma150 > 0 && ma200 > 0 && ma150 > ma200 },
    { label: "52週安値から+25%以上", passed: price > 0 && low > 0 && price >= low * 1.25 },
    { label: "52週高値から25%以内", passed: price > 0 && high > 0 && price >= high * 0.75 },
    { label: "RS 70以上", passed: rs >= 70 }
  ];

  return { checks, passed: checks.filter(check => check.passed).length, total: checks.length };
}

function growthPoints(value) {
  const growth = n(value);
  if (growth >= 30) return 5;
  if (growth >= 20) return 4;
  if (growth >= 10) return 3;
  if (growth > 0) return 2;
  return 0;
}

function calcSepaScore(stock) {
  const trend = calcTrendTemplate(stock);
  const price = n(stock.currentPrice);
  const high = n(stock.week52High);
  const rs = clamp(n(stock.rsScore), 0, 100);
  const base = clamp(n(stock.baseRating), 0, 5);
  const vcp = clamp(n(stock.vcpRating), 0, 5);
  const volume = clamp(n(stock.volumeRating), 0, 5);
  const supply = clamp(n(stock.supplyRating), 0, 5);
  const earnings = clamp(n(stock.earningsRating), 0, 5);
  const theme = clamp(n(stock.themeRating), 0, 5);

  const trendScore = (trend.passed / trend.total) * 30;
  const rsScore = (rs / 100) * 10;
  const highPositionScore = price > 0 && high > 0 ? clamp((price / high) * 5, 0, 5) : 0;
  const vcpScore = ((base + vcp) / 10) * 20;
  const flowScore = ((volume + supply) / 10) * 10;
  const growthScore = growthPoints(stock.epsGrowth) + growthPoints(stock.salesGrowth) + growthPoints(stock.opProfitGrowth);
  const themeScore = ((earnings + theme) / 10) * 10;

  return clamp(Math.round(trendScore + rsScore + highPositionScore + vcpScore + flowScore + growthScore + themeScore), 0, 100);
}

function getSepaRank(score) {
  if (score >= 80) return { label: "Aランク SEPA候補", short: "A", className: "rank-a" };
  if (score >= 65) return { label: "Bランク 監視継続", short: "B", className: "rank-b" };
  if (score >= 50) return { label: "Cランク 形待ち", short: "C", className: "rank-c" };
  return { label: "見送り", short: "D", className: "rank-d" };
}

function getVcpStatus(stock) {
  const base = n(stock.baseRating);
  const vcp = n(stock.vcpRating);
  const volume = n(stock.volumeRating);
  const price = n(stock.currentPrice);
  const pivot = n(stock.pivotPrice);

  if (pivot && price && stock.isBreakout && price > pivot * 1.08) return "追いかけ注意";
  if (base >= 4 && vcp >= 4 && volume >= 4 && stock.isBreakout) return "VCP良好";
  if (base >= 4 && vcp >= 4 && volume >= 4 && pivot && !stock.isBreakout) return "ブレイク待ち";
  if (volume > 0 && volume < 3) return "出来高不足";
  if (vcp > 0 && vcp < 3) return "収縮待ち";
  if (base > 0 && base < 3) return "ベース形成中";
  return "未評価";
}

function calcRiskMetrics(stock) {
  const entry = n(stock.entryPrice);
  const stop = n(stock.stopLoss);
  const target = n(stock.targetPrice);
  const stopLossPercent = entry && stop ? ((entry - stop) / entry) * 100 : NaN;
  const targetUpsidePercent = entry && target ? ((target - entry) / entry) * 100 : NaN;
  let rr = "未計算";
  let rrGood = false;

  if (entry && stop && target && entry > stop && target > entry) {
    const ratio = (target - entry) / (entry - stop);
    rr = `RR 1:${ratio.toFixed(2)}`;
    rrGood = ratio >= 2;
  }

  let riskClass = "neutral";
  let riskLabel = "未入力";
  if (Number.isFinite(stopLossPercent)) {
    if (stopLossPercent <= 8) {
      riskClass = "good";
      riskLabel = "損切り良好";
    } else if (stopLossPercent <= 12) {
      riskClass = "warning";
      riskLabel = "やや深い";
    } else {
      riskClass = "danger";
      riskLabel = "損切り深すぎ";
    }
  }

  return { rr, rrGood, stopLossPercent, targetUpsidePercent, riskClass, riskLabel };
}

function getEarningsAlert(stock) {
  if (!stock.earningsDate) return "";
  const today = new Date();
  const earningsDate = new Date(`${stock.earningsDate}T00:00:00`);
  today.setHours(0, 0, 0, 0);
  const diffDays = Math.ceil((earningsDate - today) / (1000 * 60 * 60 * 24));
  return diffDays >= 0 && diffDays <= 7 ? `決算${diffDays}日前` : "";
}

function analyzeStocks() {
  return stocks.map(stock => {
    const trend = calcTrendTemplate(stock);
    const sepaScore = calcSepaScore(stock);
    return {
      ...stock,
      trend,
      sepaScore,
      sepaRank: getSepaRank(sepaScore),
      vcpStatus: getVcpStatus(stock),
      risk: calcRiskMetrics(stock),
      earningsAlert: getEarningsAlert(stock)
    };
  });
}

renderPortfolioSummary = function renderPortfolioSummaryWithSepa() {
  const analyzed = analyzeStocks();
  const holding = stocks.filter(stock => stock.status === "保有").length;
  const watch = stocks.filter(stock => stock.status === "監視").length;
  const candidate = stocks.filter(stock => stock.status === "候補").length;
  const aRank = analyzed.filter(stock => stock.sepaScore >= 80).length;

  portfolioSummary.innerHTML = `<div class="summary-card"><span>保有</span><strong>${holding}</strong></div><div class="summary-card"><span>監視</span><strong>${watch}</strong></div><div class="summary-card"><span>候補</span><strong>${candidate}</strong></div><div class="summary-card"><span>Aランク</span><strong>${aRank}</strong></div>`;
};

renderWatchlist = function renderWatchlistWithSepa() {
  const analyzed = analyzeStocks();
  const filtered = activeTheme === "すべて" ? analyzed : analyzed.filter(stock => stock.theme === activeTheme);

  if (filtered.length === 0) {
    watchlistGrid.innerHTML = "<p class='empty-message'>該当する銘柄がありません。上のフォームから追加できます。</p>";
    return;
  }

  watchlistGrid.innerHTML = filtered.map(stock => {
    const links = getStockLinks(stock.code).slice(0, 3).map(link => `<a href="${link.url}" target="_blank" rel="noopener noreferrer">${link.label}</a>`).join("");
    return `<article class="stock-card ${stock.sepaRank.className}"><div class="stock-card-head"><div><span class="stock-code">${stock.code}</span><h3>${stock.name}</h3></div><span class="status ${statusClass(stock.status)}">${stock.status}</span></div><span class="theme-tag">#${stock.theme}</span><div class="sepa-badge-row"><span class="rank-badge ${stock.sepaRank.className}">${stock.sepaRank.label}</span><span class="score-badge">${stock.sepaScore}点</span></div><div class="trade-grid"><div><span>現在株価</span><strong>${formatValue(stock.currentPrice, "円")}</strong></div><div><span>Entry</span><strong>${formatValue(stock.entryPrice, "円")}</strong></div><div><span>損切り</span><strong>${formatValue(stock.stopLoss, "円")}</strong></div><div><span>利確</span><strong>${formatValue(stock.targetPrice, "円")}</strong></div><div><span>R:R</span><strong>${stock.risk.rr}</strong></div><div><span>Trend</span><strong>${stock.trend.passed}/${stock.trend.total}</strong></div></div><p>${stock.memo || "メモ未入力"}</p><div class="stock-links">${links}</div><div class="card-actions"><button type="button" class="small-button" data-action="edit" data-id="${stock.id}">編集</button><button type="button" class="small-button danger" data-action="delete" data-id="${stock.id}">削除</button></div></article>`;
  }).join("");

  document.querySelectorAll("[data-action='edit']").forEach(button => button.addEventListener("click", () => fillEditor(button.dataset.id)));
  document.querySelectorAll("[data-action='delete']").forEach(button => button.addEventListener("click", () => deleteStock(button.dataset.id)));
};

function setEditorValue(id, value) {
  const element = document.getElementById(id);
  if (element) element.value = value || "";
}

getEditorValues = function getEditorValuesWithSepa() {
  const stock = normalizeStock({
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

  sepaNumberFields.forEach(field => {
    const id = `editor${field.charAt(0).toUpperCase()}${field.slice(1)}`;
    const element = document.getElementById(id);
    if (element) stock[field] = element.value;
  });

  stock.isBreakout = document.getElementById("editorIsBreakout").checked;
  return stock;
};

fillEditor = function fillEditorWithSepa(id) {
  const stock = stocks.find(item => item.id === id);
  if (!stock) return;

  document.getElementById("editStockId").value = stock.id;
  setEditorValue("editorCode", stock.code);
  setEditorValue("editorName", stock.name);
  setEditorValue("editorTheme", stock.theme);
  setEditorValue("editorStatus", stock.status);
  setEditorValue("editorEntryPrice", stock.entryPrice);
  setEditorValue("editorStopLoss", stock.stopLoss);
  setEditorValue("editorTargetPrice", stock.targetPrice);
  setEditorValue("editorEarningsDate", stock.earningsDate);
  setEditorValue("editorMemo", stock.memo);
  setEditorValue("editorCurrentPrice", stock.currentPrice);
  setEditorValue("editorMa50", stock.ma50);
  setEditorValue("editorMa150", stock.ma150);
  setEditorValue("editorMa200", stock.ma200);
  setEditorValue("editorWeek52High", stock.week52High);
  setEditorValue("editorWeek52Low", stock.week52Low);
  setEditorValue("editorRsScore", stock.rsScore);
  setEditorValue("editorVolumeRating", stock.volumeRating);
  setEditorValue("editorBaseRating", stock.baseRating);
  setEditorValue("editorVcpRating", stock.vcpRating);
  setEditorValue("editorPivotPrice", stock.pivotPrice);
  setEditorValue("editorEpsGrowth", stock.epsGrowth);
  setEditorValue("editorSalesGrowth", stock.salesGrowth);
  setEditorValue("editorOpProfitGrowth", stock.opProfitGrowth);
  setEditorValue("editorEarningsRating", stock.earningsRating);
  setEditorValue("editorThemeRating", stock.themeRating);
  setEditorValue("editorSupplyRating", stock.supplyRating);
  document.getElementById("editorIsBreakout").checked = Boolean(stock.isBreakout);
  saveStockButton.textContent = "変更を保存";
  document.getElementById("stock-manager").scrollIntoView({ behavior: "smooth", block: "start" });
};

stockEditorForm.removeEventListener("submit", upsertStock);
upsertStock = function upsertStockWithSepa(event) {
  event.preventDefault();
  const stock = getEditorValues();
  if (!stock.code || !stock.name || !stock.theme) {
    alert("銘柄コード、銘柄名、テーマを入力してください。");
    return;
  }

  const currentId = document.getElementById("editStockId").value;
  const existingIndex = stocks.findIndex(item => item.id === currentId);
  if (existingIndex >= 0) stocks[existingIndex] = stock;
  else stocks.unshift(stock);

  saveStocks();
  activeTheme = stock.theme;
  activeSepaTheme = stock.theme;
  resetEditor();
  renderAll();
  document.getElementById("sepa-screener").scrollIntoView({ behavior: "smooth", block: "start" });
};
stockEditorForm.addEventListener("submit", upsertStock);

function renderSepaFilters() {
  const filters = [["all", "すべて"], ["rankA", "Aランクのみ"], ["rankBPlus", "Bランク以上"], ["holding", "保有のみ"], ["watch", "監視のみ"], ["candidate", "候補のみ"], ["breakout", "ブレイク済み"], ["waiting", "ブレイク待ち"]];
  sepaFilterButtons.innerHTML = filters.map(([key, label]) => `<button type="button" class="filter-button ${activeSepaFilter === key ? "active" : ""}" data-sepa-filter="${key}">${label}</button>`).join("");
  document.querySelectorAll("[data-sepa-filter]").forEach(button => button.addEventListener("click", () => {
    activeSepaFilter = button.dataset.sepaFilter;
    renderSepaScreener();
  }));
}

function filterSepaStocks(analyzed) {
  return analyzed.filter(stock => {
    if (activeSepaTheme !== "すべて" && stock.theme !== activeSepaTheme) return false;
    if (activeSepaFilter === "rankA") return stock.sepaScore >= 80;
    if (activeSepaFilter === "rankBPlus") return stock.sepaScore >= 65;
    if (activeSepaFilter === "holding") return stock.status === "保有";
    if (activeSepaFilter === "watch") return stock.status === "監視";
    if (activeSepaFilter === "candidate") return stock.status === "候補";
    if (activeSepaFilter === "breakout") return stock.isBreakout;
    if (activeSepaFilter === "waiting") return !stock.isBreakout && stock.vcpStatus === "ブレイク待ち";
    return true;
  });
}

function renderTrendChecklist(stock) {
  return stock.trend.checks.map(check => `<li class="${check.passed ? "passed" : "failed"}"><span>${check.passed ? "✓" : "—"}</span>${check.label}</li>`).join("");
}

function renderSepaScreener() {
  const analyzed = analyzeStocks().sort((a, b) => b.sepaScore - a.sepaScore);
  const filtered = filterSepaStocks(analyzed);
  const aRank = analyzed.filter(stock => stock.sepaScore >= 80).length;
  const bPlus = analyzed.filter(stock => stock.sepaScore >= 65).length;
  const breakout = analyzed.filter(stock => stock.isBreakout).length;
  const avgScore = analyzed.length ? Math.round(analyzed.reduce((sum, stock) => sum + stock.sepaScore, 0) / analyzed.length) : 0;

  sepaSummary.innerHTML = `<div class="summary-card"><span>Aランク</span><strong>${aRank}</strong></div><div class="summary-card"><span>B以上</span><strong>${bPlus}</strong></div><div class="summary-card"><span>ブレイク済み</span><strong>${breakout}</strong></div><div class="summary-card"><span>平均スコア</span><strong>${avgScore}</strong></div>`;
  sepaThemeFilter.innerHTML = getThemes().map(theme => `<option value="${theme}" ${theme === activeSepaTheme ? "selected" : ""}>${theme}</option>`).join("");
  renderSepaFilters();

  if (!filtered.length) {
    sepaRanking.innerHTML = "<p class='empty-message'>条件に合う銘柄がありません。フィルターを変更してください。</p>";
    return;
  }

  sepaRanking.innerHTML = filtered.map((stock, index) => {
    const warnings = [];
    if (stock.risk.riskClass === "warning") warnings.push("損切りやや深い");
    if (stock.risk.riskClass === "danger") warnings.push("損切り深すぎ");
    if (stock.risk.rrGood) warnings.push("R:R良好");
    if (stock.earningsAlert) warnings.push(stock.earningsAlert);
    return `<article class="sepa-card ${stock.sepaRank.className}"><div class="sepa-card-head"><div><span class="rank-number">#${index + 1}</span><h3>${stock.code} ${stock.name}</h3><p>#${stock.theme} / ${stock.status}</p></div><div class="score-circle"><strong>${stock.sepaScore}</strong><span>SEPA</span></div></div><div class="sepa-badge-row"><span class="rank-badge ${stock.sepaRank.className}">${stock.sepaRank.label}</span><span class="rank-badge neutral">Trend ${stock.trend.passed}/${stock.trend.total}</span><span class="rank-badge neutral">${stock.vcpStatus}</span></div><div class="trade-grid"><div><span>現在株価</span><strong>${formatValue(stock.currentPrice, "円")}</strong></div><div><span>RS</span><strong>${stock.rsScore || "未入力"}</strong></div><div><span>損切り率</span><strong class="${stock.risk.riskClass}">${pct(stock.risk.stopLossPercent)}</strong></div><div><span>利確余地</span><strong>${pct(stock.risk.targetUpsidePercent)}</strong></div><div><span>R:R</span><strong>${stock.risk.rr}</strong></div><div><span>決算日</span><strong>${stock.earningsDate || "未入力"}</strong></div></div>${warnings.length ? `<div class="warning-row">${warnings.map(w => `<span>${w}</span>`).join("")}</div>` : ""}<details class="trend-details"><summary>Trend Template チェックを見る</summary><ul class="trend-checklist">${renderTrendChecklist(stock)}</ul></details><div class="card-actions"><button type="button" class="small-button" data-action="edit" data-id="${stock.id}">SEPA入力を編集</button><a class="small-button link-button" href="https://jp.tradingview.com/symbols/TSE-${stock.code}/" target="_blank" rel="noopener noreferrer">チャート</a></div></article>`;
  }).join("");
  document.querySelectorAll("#sepaRanking [data-action='edit']").forEach(button => button.addEventListener("click", () => fillEditor(button.dataset.id)));
}

const baseRenderAll = renderAll;
renderAll = function renderAllWithSepa() {
  baseRenderAll();
  renderSepaScreener();
};

sepaThemeFilter.addEventListener("change", event => {
  activeSepaTheme = event.target.value;
  renderSepaScreener();
});

saveStocks();
renderAll();
console.log("SEPA screener loaded");
