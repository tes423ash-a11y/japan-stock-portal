// ==============================
// 日本株スイング・スクリーニング支援ツール
// APIなしの静的サイトなので、候補銘柄を手入力またはCSV貼り付けで評価します。
// 保存先は localStorage です。
// ==============================

const swingStorageKey = "stockPortal:swingCandidates:v1";
const swingFilters = [
  ["all", "すべて"],
  ["rankA", "総合評価Aのみ"],
  ["rankBPlus", "B以上"],
  ["breakout", "新高値ブレイク"],
  ["bottom", "大底反転"],
  ["goodShape", "形が良い"],
  ["entry", "エントリー向き"],
  ["pullback", "押し目待ち"],
  ["watch", "様子見"],
  ["prime", "プライム"],
  ["standard", "スタンダード"],
  ["growth", "グロース"],
  ["bigTurnover", "売買代金大"],
  ["strongFlow", "資金流入強い"],
  ["strongEarnings", "業績強い"]
];

const swingCsvColumns = [
  "code", "name", "market", "price", "changePercent", "marketCap", "turnover", "turnoverRankCount",
  "earningsSummary", "salesGrowth", "opProfitGrowth", "epsGrowth", "operatingMargin", "roe", "hasUpwardRevision",
  "chartType", "chartPattern", "isMaAligned", "hasVolumeIncrease", "isBreakout", "hasLongUpperWick", "hasPostEarningsWeakness",
  "flowStrength", "flowContinuity", "theme", "themeLeadership", "watchPoint", "breakPoint", "pullbackPoint", "neckline", "ma25", "recentHigh", "entryDecision"
];

let swingCandidates = loadSwingCandidates();
let activeSwingFilter = "all";

function swingId() {
  return `swing-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function toBool(value) {
  if (typeof value === "boolean") return value;
  const text = String(value || "").trim().toLowerCase();
  return ["true", "1", "yes", "y", "あり", "有", "○", "はい"].includes(text);
}

function toNumber(value) {
  const num = Number(String(value || "").replace(/,/g, ""));
  return Number.isFinite(num) ? num : 0;
}

function normalizeSwingCandidate(item = {}) {
  return {
    id: item.id || swingId(),
    code: cleanCode(item.code || ""),
    name: item.name || "名称未設定",
    market: item.market || "プライム",
    price: item.price || "",
    changePercent: item.changePercent || "",
    marketCap: item.marketCap || "",
    turnover: item.turnover || "",
    turnoverRankCount: item.turnoverRankCount || "",
    earningsSummary: item.earningsSummary || "",
    salesGrowth: item.salesGrowth || "",
    opProfitGrowth: item.opProfitGrowth || "",
    epsGrowth: item.epsGrowth || "",
    operatingMargin: item.operatingMargin || "",
    roe: item.roe || "",
    hasUpwardRevision: toBool(item.hasUpwardRevision),
    chartType: item.chartType || "新高値ブレイク",
    chartPattern: item.chartPattern || "",
    isMaAligned: toBool(item.isMaAligned),
    hasVolumeIncrease: toBool(item.hasVolumeIncrease),
    isBreakout: toBool(item.isBreakout),
    hasLongUpperWick: toBool(item.hasLongUpperWick),
    hasPostEarningsWeakness: toBool(item.hasPostEarningsWeakness),
    flowStrength: item.flowStrength || "中程度",
    flowContinuity: item.flowContinuity || "中程度",
    theme: item.theme || "",
    themeLeadership: toBool(item.themeLeadership),
    watchPoint: item.watchPoint || "",
    breakPoint: item.breakPoint || "",
    pullbackPoint: item.pullbackPoint || "",
    neckline: item.neckline || "",
    ma25: item.ma25 || "",
    recentHigh: item.recentHigh || "",
    entryDecision: item.entryDecision || "様子見"
  };
}

function loadSwingCandidates() {
  try {
    const saved = localStorage.getItem(swingStorageKey);
    return saved ? JSON.parse(saved).map(normalizeSwingCandidate) : [];
  } catch (error) {
    console.warn("スイング候補データの読み込みに失敗しました", error);
    return [];
  }
}

function saveSwingCandidates() {
  localStorage.setItem(swingStorageKey, JSON.stringify(swingCandidates));
}

function ratingPoints(value, strong = 6, middle = 3) {
  if (value === "強い") return strong;
  if (value === "中程度") return middle;
  return 0;
}

function growthScore(value, maxPoints) {
  const growth = toNumber(value);
  if (growth >= 30) return maxPoints;
  if (growth >= 20) return maxPoints * 0.8;
  if (growth >= 10) return maxPoints * 0.6;
  if (growth > 0) return maxPoints * 0.35;
  if (growth < 0) return -2;
  return 0;
}

function patternContains(candidate, words) {
  return words.some(word => String(candidate.chartPattern || "").includes(word));
}

function calcSwingScore(candidate) {
  const turnover = toNumber(candidate.turnover);
  const rankCount = toNumber(candidate.turnoverRankCount);

  let flowScore = 0;
  if (turnover >= 10000000000) flowScore += 12;
  else if (turnover >= 3000000000) flowScore += 9;
  else if (turnover >= 1000000000) flowScore += 6;
  else if (turnover >= 300000000) flowScore += 3;
  else if (turnover > 0) flowScore += 1;
  flowScore += Math.min(rankCount, 6);
  flowScore += ratingPoints(candidate.flowStrength, 5, 3);
  flowScore += ratingPoints(candidate.flowContinuity, 7, 3);
  if (candidate.hasVolumeIncrease) flowScore += 3;
  flowScore = Math.min(flowScore, 30);

  let earningsScore = 0;
  earningsScore += growthScore(candidate.salesGrowth, 5);
  earningsScore += growthScore(candidate.opProfitGrowth, 6);
  earningsScore += growthScore(candidate.epsGrowth, 6);
  if (candidate.hasUpwardRevision) earningsScore += 4;
  if (toNumber(candidate.operatingMargin) >= 15) earningsScore += 2;
  if (toNumber(candidate.roe) >= 15) earningsScore += 2;
  earningsScore += ratingPoints(candidate.earningsRating || candidate.earningsStrength, 0, 0);
  if (candidate.earningsSummary && String(candidate.earningsSummary).match(/赤字|下方|減益|失速/)) earningsScore -= 5;
  if (candidate.earningsStrength === "強い") earningsScore += 5;
  if (candidate.earningsStrength === "中程度") earningsScore += 3;
  if (candidate.earningsStrength === "弱い") earningsScore -= 5;
  earningsScore = Math.min(Math.max(earningsScore, -10), 25);

  let chartScore = 0;
  if (candidate.chartType === "新高値ブレイク") {
    chartScore += 8;
    if (patternContains(candidate, ["52週高値", "上場来高値", "高値もみ合い上放れ"])) chartScore += 8;
    if (candidate.isBreakout) chartScore += 4;
  }
  if (candidate.chartType === "大底反転") {
    chartScore += 7;
    if (patternContains(candidate, ["ダブルボトム", "逆三尊", "ネックライン", "75日線", "200日線"])) chartScore += 9;
  }
  if (candidate.chartType === "形が良い") {
    chartScore += 8;
    if (patternContains(candidate, ["三角持ち合い", "ボックス", "カップ", "押し目", "25日線", "75日線"])) chartScore += 8;
  }
  if (candidate.isMaAligned) chartScore += 6;
  if (candidate.hasVolumeIncrease) chartScore += 4;
  if (candidate.entryDecision === "エントリー向き") chartScore += 4;
  if (candidate.entryDecision === "押し目待ち") chartScore += 2;
  chartScore = Math.min(chartScore, 30);

  let themeScore = 0;
  themeScore += ratingPoints(candidate.flowContinuity, 4, 2);
  if (candidate.theme) themeScore += 3;
  if (candidate.themeLeadership) themeScore += 6;
  if (candidate.flowStrength === "強い") themeScore += 2;
  themeScore = Math.min(themeScore, 15);

  let penalty = 0;
  if (turnover > 0 && turnover < 300000000) penalty -= 4;
  if (candidate.flowContinuity === "弱い") penalty -= 4;
  if (candidate.hasLongUpperWick) penalty -= 5;
  if (candidate.hasPostEarningsWeakness) penalty -= 5;
  if ((candidate.earningsStrength === "弱い" || String(candidate.earningsSummary).match(/赤字|下方|減益/)) && candidate.themeLeadership) penalty -= 4;
  penalty = Math.max(penalty, -15);

  const score = Math.round(Math.max(0, Math.min(100, flowScore + earningsScore + chartScore + themeScore + penalty)));
  return { score, flowScore: Math.round(flowScore), earningsScore: Math.round(earningsScore), chartScore: Math.round(chartScore), themeScore: Math.round(themeScore), penalty };
}

function swingRank(score) {
  if (score >= 80) return { label: "A", className: "rank-a", text: "A評価" };
  if (score >= 65) return { label: "B", className: "rank-b", text: "B評価" };
  if (score >= 50) return { label: "C", className: "rank-c", text: "C評価" };
  return { label: "除外寄り", className: "rank-d", text: "除外寄り" };
}

function analyzeSwingCandidates() {
  return swingCandidates.map(candidate => {
    const scoreParts = calcSwingScore(candidate);
    return { ...candidate, ...scoreParts, rank: swingRank(scoreParts.score) };
  }).sort((a, b) => {
    const rankOrder = { A: 4, B: 3, C: 2, "除外寄り": 1 };
    return (rankOrder[b.rank.label] - rankOrder[a.rank.label]) || (toNumber(b.turnover) - toNumber(a.turnover)) || (ratingWeight(b.flowContinuity) - ratingWeight(a.flowContinuity));
  });
}

function ratingWeight(value) {
  if (value === "強い") return 3;
  if (value === "中程度") return 2;
  return 1;
}

function insertSwingUi() {
  const headerActions = document.querySelector(".header-actions");
  if (headerActions && !document.querySelector("a[href='#swing-screener']")) {
    const link = document.createElement("a");
    link.className = "pill-link secondary";
    link.href = "#swing-screener";
    link.textContent = "スイング抽出";
    headerActions.insertBefore(link, headerActions.lastElementChild);
  }

  const target = document.getElementById("sepa-screener") || document.getElementById("watchlist");
  if (!target || document.getElementById("swing-screener")) return;

  const section = document.createElement("section");
  section.id = "swing-screener";
  section.className = "card swing-section";
  section.innerHTML = `
    <div class="section-heading"><span class="card-label">Swing Screener</span><h2>日本株スイングスクリーナー</h2><p>候補銘柄を手入力またはCSVで登録し、新高値ブレイク・大底反転・形が良い銘柄をA/B/Cで評価します。</p></div>
    <details class="editor-section" open><summary>候補銘柄を手入力</summary><form id="swingForm" class="stock-editor-form"><input type="hidden" id="swingEditId" /><div class="form-grid">
      ${field("swingCode","証券コード","text","例：7011")}${field("swingName","銘柄名","text","例：三菱重工業")}
      ${selectField("swingMarket","市場区分",["プライム","スタンダード","グロース"])}${field("swingPrice","株価","number","例：1500")}
      ${field("swingChangePercent","前日比%","number","例：3.2")}${field("swingMarketCap","時価総額","number","例：5000000000000")}
      ${field("swingTurnover","売買代金","number","例：12000000000")}${field("swingTurnoverRankCount","20日売買代金上位回数","number","例：5")}
      ${field("swingSalesGrowth","売上成長率%","number","例：20")}${field("swingOpProfitGrowth","営業利益成長率%","number","例：30")}
      ${field("swingEpsGrowth","EPS成長率%","number","例：25")}${field("swingOperatingMargin","営業利益率%","number","例：12")}
      ${field("swingRoe","ROE%","number","例：15")}${selectField("swingEarningsStrength","業績評価",["強い","中程度","弱い"])}
      ${selectField("swingChartType","チャート分類",["新高値ブレイク","大底反転","形が良い"])}${field("swingChartPattern","チャート形状","text","例：高値もみ合い上放れ")}
      ${selectField("swingFlowStrength","当日売買代金評価",["強い","中程度","弱い"])}${selectField("swingFlowContinuity","継続的な資金流入",["強い","中程度","弱い"])}
      ${field("swingTheme","テーマ性","text","例：防衛・データセンター")}${selectField("swingEntryDecision","エントリー判断",["エントリー向き","押し目待ち","様子見"])}
      ${field("swingBreakPoint","ブレイクポイント","text","例：直近高値 1,650円")}${field("swingPullbackPoint","押し目候補","text","例：25日線付近")}
      ${field("swingNeckline","ネックライン","text","例：1,420円")}${field("swingMa25","25日線","text","例：1,480円")}
      ${field("swingRecentHigh","直近高値","text","例：1,650円")}${field("swingWatchPoint","監視ポイント","text","例：出来高を伴う高値更新")}
    </div><div class="form-grid checkbox-grid">
      ${checkField("swingHasUpwardRevision","上方修正あり")}${checkField("swingIsMaAligned","5日線 > 25日線 > 75日線")}${checkField("swingHasVolumeIncrease","出来高増加あり")}${checkField("swingIsBreakout","ブレイク済み")}${checkField("swingHasLongUpperWick","長い上ヒゲあり")}${checkField("swingHasPostEarningsWeakness","決算後失速あり")}${checkField("swingThemeLeadership","主役テーマ銘柄")}
    </div><div class="form-field full-width"><label for="swingEarningsSummary">直近決算/業績の要点</label><textarea id="swingEarningsSummary" placeholder="例：営業利益+35%、通期上方修正、受注残が高水準"></textarea></div><div class="editor-actions sticky-actions"><button type="submit" id="swingSaveButton">候補を保存</button><button type="button" id="swingResetButton" class="button-muted">入力をクリア</button></div></form></details>
    <details class="editor-section"><summary>CSV貼り付けで一括登録</summary><p class="hint">1行目に列名を入れてください。true/あり/○ はチェック項目として扱います。</p><textarea id="swingCsvInput" class="csv-box" placeholder="code,name,market,price,changePercent,marketCap,turnover,turnoverRankCount,..."></textarea><pre class="csv-example">code,name,market,price,changePercent,marketCap,turnover,turnoverRankCount,earningsSummary,salesGrowth,opProfitGrowth,epsGrowth,operatingMargin,roe,hasUpwardRevision,chartType,chartPattern,isMaAligned,hasVolumeIncrease,isBreakout,hasLongUpperWick,hasPostEarningsWeakness,flowStrength,flowContinuity,theme,themeLeadership,watchPoint,breakPoint,pullbackPoint,neckline,ma25,recentHigh,entryDecision\n7011,三菱重工業,プライム,1500,3.2,5000000000000,12000000000,6,増益・上方修正,20,30,25,12,15,true,新高値ブレイク,高値もみ合い上放れ,true,true,true,false,false,強い,強い,防衛,true,直近高値更新,1650,25日線,1420,1480,1650,押し目待ち</pre><div class="editor-actions"><button type="button" id="swingImportCsvButton">CSVを取り込む</button><button type="button" id="swingClearAllButton" class="small-button danger">候補を全削除</button></div></details>
    <div id="swingSummary" class="portfolio-summary"></div><div id="swingFilterButtons" class="filter-row"></div><div id="swingRanking" class="sepa-ranking"></div><div id="swingAutoSummary" class="swing-auto-summary"></div>
    <details class="editor-section"><summary>ChatGPT分析用プロンプト生成</summary><button type="button" id="swingPromptButton">ChatGPT分析プロンプトを生成</button><textarea id="swingPromptOutput" class="prompt-box" placeholder="ここに生成されたプロンプトが表示されます"></textarea><button type="button" id="swingCopyPromptButton" class="button-muted">コピー</button></details>
  `;
  target.insertAdjacentElement("afterend", section);
  bindSwingEvents();
  renderSwing();
}

function field(id, label, type, placeholder) {
  const inputmode = type === "number" ? "decimal" : "text";
  return `<div class="form-field"><label for="${id}">${label}</label><input id="${id}" type="${type}" inputmode="${inputmode}" step="0.1" placeholder="${placeholder}" /></div>`;
}

function selectField(id, label, options) {
  return `<div class="form-field"><label for="${id}">${label}</label><select id="${id}">${options.map(option => `<option value="${option}">${option}</option>`).join("")}</select></div>`;
}

function checkField(id, label) {
  return `<div class="form-field checkbox-field"><label for="${id}">${label}</label><input id="${id}" type="checkbox" /></div>`;
}

function bindSwingEvents() {
  document.getElementById("swingForm").addEventListener("submit", saveSwingFromForm);
  document.getElementById("swingResetButton").addEventListener("click", resetSwingForm);
  document.getElementById("swingImportCsvButton").addEventListener("click", importSwingCsv);
  document.getElementById("swingClearAllButton").addEventListener("click", clearSwingCandidates);
  document.getElementById("swingPromptButton").addEventListener("click", generateSwingPrompt);
  document.getElementById("swingCopyPromptButton").addEventListener("click", copySwingPrompt);
  document.getElementById("swingCode").addEventListener("input", event => event.target.value = cleanCode(event.target.value));
}

function getSwingFormValues() {
  return normalizeSwingCandidate({
    id: document.getElementById("swingEditId").value || swingId(),
    code: document.getElementById("swingCode").value,
    name: document.getElementById("swingName").value.trim(),
    market: document.getElementById("swingMarket").value,
    price: document.getElementById("swingPrice").value,
    changePercent: document.getElementById("swingChangePercent").value,
    marketCap: document.getElementById("swingMarketCap").value,
    turnover: document.getElementById("swingTurnover").value,
    turnoverRankCount: document.getElementById("swingTurnoverRankCount").value,
    earningsSummary: document.getElementById("swingEarningsSummary").value.trim(),
    salesGrowth: document.getElementById("swingSalesGrowth").value,
    opProfitGrowth: document.getElementById("swingOpProfitGrowth").value,
    epsGrowth: document.getElementById("swingEpsGrowth").value,
    operatingMargin: document.getElementById("swingOperatingMargin").value,
    roe: document.getElementById("swingRoe").value,
    hasUpwardRevision: document.getElementById("swingHasUpwardRevision").checked,
    earningsStrength: document.getElementById("swingEarningsStrength").value,
    chartType: document.getElementById("swingChartType").value,
    chartPattern: document.getElementById("swingChartPattern").value.trim(),
    isMaAligned: document.getElementById("swingIsMaAligned").checked,
    hasVolumeIncrease: document.getElementById("swingHasVolumeIncrease").checked,
    isBreakout: document.getElementById("swingIsBreakout").checked,
    hasLongUpperWick: document.getElementById("swingHasLongUpperWick").checked,
    hasPostEarningsWeakness: document.getElementById("swingHasPostEarningsWeakness").checked,
    flowStrength: document.getElementById("swingFlowStrength").value,
    flowContinuity: document.getElementById("swingFlowContinuity").value,
    theme: document.getElementById("swingTheme").value.trim(),
    themeLeadership: document.getElementById("swingThemeLeadership").checked,
    watchPoint: document.getElementById("swingWatchPoint").value.trim(),
    breakPoint: document.getElementById("swingBreakPoint").value.trim(),
    pullbackPoint: document.getElementById("swingPullbackPoint").value.trim(),
    neckline: document.getElementById("swingNeckline").value.trim(),
    ma25: document.getElementById("swingMa25").value.trim(),
    recentHigh: document.getElementById("swingRecentHigh").value.trim(),
    entryDecision: document.getElementById("swingEntryDecision").value
  });
}

function saveSwingFromForm(event) {
  event.preventDefault();
  const candidate = getSwingFormValues();
  if (!candidate.code || !candidate.name) {
    alert("証券コードと銘柄名を入力してください。");
    return;
  }
  const index = swingCandidates.findIndex(item => item.id === candidate.id);
  if (index >= 0) swingCandidates[index] = candidate;
  else swingCandidates.unshift(candidate);
  saveSwingCandidates();
  resetSwingForm();
  renderSwing();
}

function setValue(id, value) {
  const element = document.getElementById(id);
  if (!element) return;
  if (element.type === "checkbox") element.checked = toBool(value);
  else element.value = value || "";
}

function editSwingCandidate(id) {
  const candidate = swingCandidates.find(item => item.id === id);
  if (!candidate) return;
  setValue("swingEditId", candidate.id); setValue("swingCode", candidate.code); setValue("swingName", candidate.name); setValue("swingMarket", candidate.market);
  setValue("swingPrice", candidate.price); setValue("swingChangePercent", candidate.changePercent); setValue("swingMarketCap", candidate.marketCap); setValue("swingTurnover", candidate.turnover); setValue("swingTurnoverRankCount", candidate.turnoverRankCount);
  setValue("swingEarningsSummary", candidate.earningsSummary); setValue("swingSalesGrowth", candidate.salesGrowth); setValue("swingOpProfitGrowth", candidate.opProfitGrowth); setValue("swingEpsGrowth", candidate.epsGrowth); setValue("swingOperatingMargin", candidate.operatingMargin); setValue("swingRoe", candidate.roe); setValue("swingHasUpwardRevision", candidate.hasUpwardRevision); setValue("swingEarningsStrength", candidate.earningsStrength || "中程度");
  setValue("swingChartType", candidate.chartType); setValue("swingChartPattern", candidate.chartPattern); setValue("swingIsMaAligned", candidate.isMaAligned); setValue("swingHasVolumeIncrease", candidate.hasVolumeIncrease); setValue("swingIsBreakout", candidate.isBreakout); setValue("swingHasLongUpperWick", candidate.hasLongUpperWick); setValue("swingHasPostEarningsWeakness", candidate.hasPostEarningsWeakness);
  setValue("swingFlowStrength", candidate.flowStrength); setValue("swingFlowContinuity", candidate.flowContinuity); setValue("swingTheme", candidate.theme); setValue("swingThemeLeadership", candidate.themeLeadership); setValue("swingWatchPoint", candidate.watchPoint); setValue("swingBreakPoint", candidate.breakPoint); setValue("swingPullbackPoint", candidate.pullbackPoint); setValue("swingNeckline", candidate.neckline); setValue("swingMa25", candidate.ma25); setValue("swingRecentHigh", candidate.recentHigh); setValue("swingEntryDecision", candidate.entryDecision);
  document.getElementById("swing-screener").scrollIntoView({ behavior: "smooth", block: "start" });
}

function resetSwingForm() {
  document.getElementById("swingForm").reset();
  setValue("swingEditId", "");
}

function deleteSwingCandidate(id) {
  const candidate = swingCandidates.find(item => item.id === id);
  if (!candidate) return;
  if (!confirm(`${candidate.code} ${candidate.name} を削除しますか？`)) return;
  swingCandidates = swingCandidates.filter(item => item.id !== id);
  saveSwingCandidates();
  renderSwing();
}

function clearSwingCandidates() {
  if (!confirm("スイング候補をすべて削除しますか？")) return;
  swingCandidates = [];
  saveSwingCandidates();
  renderSwing();
}

function parseCsv(text) {
  return text.trim().split(/\r?\n/).filter(Boolean).map(line => line.split(",").map(cell => cell.trim()));
}

function importSwingCsv() {
  const text = document.getElementById("swingCsvInput").value;
  if (!text.trim()) return alert("CSVを貼り付けてください。");
  const rows = parseCsv(text);
  const header = rows.shift();
  const imported = rows.map(row => {
    const item = {};
    header.forEach((key, index) => item[key] = row[index] || "");
    return normalizeSwingCandidate(item);
  });
  swingCandidates = [...imported, ...swingCandidates];
  saveSwingCandidates();
  document.getElementById("swingCsvInput").value = "";
  renderSwing();
}

function formatMoney(value) {
  const num = toNumber(value);
  if (!num) return "未入力";
  if (num >= 1000000000000) return `${(num / 1000000000000).toFixed(1)}兆円`;
  if (num >= 100000000) return `${(num / 100000000).toFixed(0)}億円`;
  return `${num.toLocaleString("ja-JP")}円`;
}

function filteredSwing(analyzed) {
  return analyzed.filter(item => {
    if (activeSwingFilter === "rankA") return item.rank.label === "A";
    if (activeSwingFilter === "rankBPlus") return ["A", "B"].includes(item.rank.label);
    if (activeSwingFilter === "breakout") return item.chartType === "新高値ブレイク";
    if (activeSwingFilter === "bottom") return item.chartType === "大底反転";
    if (activeSwingFilter === "goodShape") return item.chartType === "形が良い";
    if (activeSwingFilter === "entry") return item.entryDecision === "エントリー向き";
    if (activeSwingFilter === "pullback") return item.entryDecision === "押し目待ち";
    if (activeSwingFilter === "watch") return item.entryDecision === "様子見";
    if (activeSwingFilter === "prime") return item.market === "プライム";
    if (activeSwingFilter === "standard") return item.market === "スタンダード";
    if (activeSwingFilter === "growth") return item.market === "グロース";
    if (activeSwingFilter === "bigTurnover") return toNumber(item.turnover) >= 1000000000;
    if (activeSwingFilter === "strongFlow") return item.flowContinuity === "強い";
    if (activeSwingFilter === "strongEarnings") return item.earningsStrength === "強い";
    return true;
  });
}

function renderSwing() {
  const analyzed = analyzeSwingCandidates();
  const filtered = filteredSwing(analyzed);
  document.getElementById("swingSummary").innerHTML = `<div class="summary-card"><span>A評価</span><strong>${analyzed.filter(i => i.rank.label === "A").length}</strong></div><div class="summary-card"><span>B以上</span><strong>${analyzed.filter(i => ["A","B"].includes(i.rank.label)).length}</strong></div><div class="summary-card"><span>資金流入強い</span><strong>${analyzed.filter(i => i.flowContinuity === "強い").length}</strong></div><div class="summary-card"><span>候補総数</span><strong>${analyzed.length}</strong></div>`;
  document.getElementById("swingFilterButtons").innerHTML = swingFilters.map(([key, label]) => `<button type="button" class="filter-button ${activeSwingFilter === key ? "active" : ""}" data-swing-filter="${key}">${label}</button>`).join("");
  document.querySelectorAll("[data-swing-filter]").forEach(button => button.addEventListener("click", () => { activeSwingFilter = button.dataset.swingFilter; renderSwing(); }));

  document.getElementById("swingRanking").innerHTML = filtered.length ? filtered.map((item, index) => `<article class="sepa-card ${item.rank.className}"><div class="sepa-card-head"><div><span class="rank-number">#${index + 1}</span><h3>${item.code} ${item.name}</h3><p>${item.market} / ${item.theme || "テーマ未入力"}</p></div><div class="score-circle"><strong>${item.score}</strong><span>${item.rank.text}</span></div></div><div class="sepa-badge-row"><span class="rank-badge ${item.rank.className}">${item.rank.text}</span><span class="rank-badge neutral">${item.chartType}</span><span class="rank-badge neutral">${item.entryDecision}</span></div><div class="trade-grid"><div><span>株価</span><strong>${formatValue(item.price, "円")}</strong></div><div><span>前日比</span><strong>${item.changePercent || "未入力"}%</strong></div><div><span>時価総額</span><strong>${formatMoney(item.marketCap)}</strong></div><div><span>売買代金</span><strong>${formatMoney(item.turnover)}</strong></div><div><span>20日上位回数</span><strong>${item.turnoverRankCount || "0"}</strong></div><div><span>資金継続</span><strong>${item.flowContinuity}</strong></div></div><p><strong>チャート：</strong>${item.chartPattern || "未入力"}</p><p><strong>業績：</strong>${item.earningsSummary || "未入力"}</p><p><strong>監視：</strong>${item.watchPoint || item.breakPoint || item.pullbackPoint || "未入力"}</p>${(item.hasLongUpperWick || item.hasPostEarningsWeakness || item.penalty < 0) ? `<div class="warning-row"><span>減点あり ${item.penalty}点</span>${item.hasLongUpperWick ? "<span>長い上ヒゲ</span>" : ""}${item.hasPostEarningsWeakness ? "<span>決算後失速</span>" : ""}</div>` : ""}<div class="card-actions"><button type="button" class="small-button" data-swing-edit="${item.id}">編集</button><button type="button" class="small-button danger" data-swing-delete="${item.id}">削除</button></div></article>`).join("") : "<p class='empty-message'>候補がありません。手入力またはCSVで登録してください。</p>";
  document.querySelectorAll("[data-swing-edit]").forEach(button => button.addEventListener("click", () => editSwingCandidate(button.dataset.swingEdit)));
  document.querySelectorAll("[data-swing-delete]").forEach(button => button.addEventListener("click", () => deleteSwingCandidate(button.dataset.swingDelete)));
  renderSwingSummaryText(analyzed);
}

function names(list) {
  return list.slice(0, 8).map(item => `${item.code} ${item.name}`).join("、") || "該当なし";
}

function renderSwingSummaryText(analyzed) {
  const top10 = analyzed.slice(0, 10);
  const html = `<article class="card swing-summary-card"><h3>自動まとめ</h3><p><strong>今の市場で主役：</strong>${names(analyzed.filter(i => i.themeLeadership || i.flowContinuity === "強い"))}</p><p><strong>これから資金流入期待：</strong>${names(analyzed.filter(i => i.flowContinuity !== "弱い" && i.score >= 60))}</p><p><strong>ブレイクの質が高い：</strong>${names(analyzed.filter(i => i.chartType === "新高値ブレイク" && i.hasVolumeIncrease && i.score >= 65))}</p><p><strong>初動の大底反転：</strong>${names(analyzed.filter(i => i.chartType === "大底反転" && i.score >= 50))}</p><p><strong>形は良いがトリガー待ち：</strong>${names(analyzed.filter(i => i.chartType === "形が良い" && i.entryDecision !== "エントリー向き"))}</p><p><strong>明日以降の監視Top10：</strong>${names(top10)}</p></article>`;
  document.getElementById("swingAutoSummary").innerHTML = html;
}

function generateSwingPrompt() {
  const analyzed = analyzeSwingCandidates();
  const rows = analyzed.map(item => `- ${item.code} ${item.name} / ${item.market} / 株価:${item.price} / 前日比:${item.changePercent}% / 時価総額:${item.marketCap} / 売買代金:${item.turnover} / 20日上位:${item.turnoverRankCount}回 / 業績:${item.earningsSummary} / 分類:${item.chartType} / 形状:${item.chartPattern} / 資金継続:${item.flowContinuity} / 業績評価:${item.earningsStrength || "未入力"} / 評価:${item.rank.text} ${item.score}点 / 監視:${item.watchPoint} / 判断:${item.entryDecision}`).join("\n");
  const prompt = `あなたは日本株の短期〜スイング向けスクリーニング専門アナリストです。\n以下の候補銘柄を、新高値ブレイク、大底反転、形が良い銘柄に分類し、売買代金、業績、チャート、資金流入の継続性を重視して評価してください。\n情報不足部分は推測と断定を分けてください。最後に明日の監視リストTop10を出してください。\n\n【候補銘柄】\n${rows || "候補なし"}`;
  document.getElementById("swingPromptOutput").value = prompt;
}

function copySwingPrompt() {
  const area = document.getElementById("swingPromptOutput");
  area.select();
  navigator.clipboard?.writeText(area.value);
}

insertSwingUi();
console.log("Swing screener loaded");
