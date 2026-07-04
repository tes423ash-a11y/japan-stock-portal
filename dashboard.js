const fallbackReport = {
  generatedAt: "demo",
  universe: "sample",
  summary: {
    total: 8,
    aRank: 3,
    breakoutReady: 2,
    pullbackReady: 2,
    averageScore: 78
  },
  candidates: [
    {
      symbol: "7011.T",
      code: "7011",
      name: "三菱重工業",
      market: "JP",
      theme: "防衛・重工",
      rank: "A",
      score: 91,
      setup: "SEPA継続・高値圏押し目",
      price: 2450,
      pivot: 2520,
      stop: 2310,
      target1: 2730,
      target2: 3000,
      rr: 2.1,
      trendScore: 28,
      vcpScore: 18,
      rsScore: 14,
      riskLabel: "許容",
      action: "押し目または高値更新待ち",
      reasons: ["50/150/200日線の上", "テーマ資金が継続", "損切り幅が許容範囲"]
    },
    {
      symbol: "MU",
      code: "MU",
      name: "Micron Technology",
      market: "US",
      theme: "HBM・メモリ",
      rank: "A",
      score: 89,
      setup: "SEPA継続・ブレイク後維持",
      price: 146.2,
      pivot: 148.5,
      stop: 136.8,
      target1: 168,
      target2: 185,
      rr: 2.4,
      trendScore: 27,
      vcpScore: 17,
      rsScore: 15,
      riskLabel: "良好",
      action: "保有継続・追撃は小さく",
      reasons: ["RSが強い", "AIメモリテーマ", "高値圏で崩れていない"]
    },
    {
      symbol: "5803.T",
      code: "5803",
      name: "フジクラ",
      market: "JP",
      theme: "データセンター・光通信",
      rank: "B",
      score: 76,
      setup: "押し目待ち",
      price: 6900,
      pivot: 7200,
      stop: 6500,
      target1: 7900,
      target2: 8500,
      rr: 1.9,
      trendScore: 24,
      vcpScore: 14,
      rsScore: 13,
      riskLabel: "やや深い",
      action: "無理追いせず25日線反応待ち",
      reasons: ["テーマ性は強い", "ボラティリティが高い", "損切り幅に注意"]
    }
  ],
  themes: [
    { name: "HBM・メモリ", strength: 92, leaders: ["MU", "SNDK"], note: "AIサーバー需要と価格上昇期待" },
    { name: "防衛・重工", strength: 88, leaders: ["7011", "7012", "7013"], note: "政策・受注残・大型資金流入" },
    { name: "データセンター・光通信", strength: 76, leaders: ["5803", "5802"], note: "CPO/光通信のテーマ継続" },
    { name: "電力・原子力", strength: 70, leaders: ["9501", "9503"], note: "AI電力需要と再稼働材料" }
  ],
  tracking: [
    { symbol: "7011.T", name: "三菱重工業", detectedAt: "demo", days: 5, maxGain: 8.4, maxDrawdown: -2.8, status: "成功継続" },
    { symbol: "5803.T", name: "フジクラ", detectedAt: "demo", days: 5, maxGain: 3.1, maxDrawdown: -6.5, status: "要観察" },
    { symbol: "4478.T", name: "freee", detectedAt: "demo", days: 10, maxGain: 2.2, maxDrawdown: -9.4, status: "失敗" }
  ]
};

let currentReport = fallbackReport;

const yen = new Intl.NumberFormat("ja-JP", { maximumFractionDigits: 1 });

function fmt(value, suffix = "") {
  if (value === undefined || value === null || value === "") return "-";
  if (typeof value === "number") return `${yen.format(value)}${suffix}`;
  return `${value}${suffix}`;
}

function rankClass(rank) {
  if (rank === "A") return "rank-a";
  if (rank === "B") return "rank-b";
  if (rank === "C") return "rank-c";
  return "rank-d";
}

function stockLinks(item) {
  const code = item.code || String(item.symbol || "").replace(".T", "");
  if (item.market === "US") {
    return [
      ["Yahoo", `https://finance.yahoo.com/quote/${item.symbol}`],
      ["TradingView", `https://www.tradingview.com/symbols/${item.symbol}/`]
    ];
  }
  return [
    ["株探", `https://kabutan.jp/stock/?code=${code}`],
    ["Yahoo", `https://finance.yahoo.co.jp/quote/${code}.T`],
    ["TradingView", `https://jp.tradingview.com/symbols/TSE-${code}/`]
  ];
}

function renderSummary(report) {
  const summary = report.summary || {};
  const cards = [
    ["対象銘柄", summary.total ?? report.candidates?.length ?? 0],
    ["Aランク", summary.aRank ?? report.candidates?.filter(x => x.rank === "A").length ?? 0],
    ["ブレイク候補", summary.breakoutReady ?? 0],
    ["押し目候補", summary.pullbackReady ?? 0],
    ["平均スコア", summary.averageScore ?? "-"]
  ];
  document.getElementById("summaryCards").innerHTML = cards.map(([label, value]) => `
    <article class="summary-card"><span>${label}</span><strong>${value}</strong></article>
  `).join("");
}

function filterCandidates(candidates) {
  const value = document.getElementById("rankFilter").value;
  if (value === "A") return candidates.filter(item => item.rank === "A");
  if (value === "B") return candidates.filter(item => ["A", "B"].includes(item.rank));
  if (value === "breakout") return candidates.filter(item => String(item.setup || item.action || "").includes("ブレイク"));
  if (value === "pullback") return candidates.filter(item => String(item.setup || item.action || "").includes("押し目"));
  return candidates;
}

function renderCandidates(report) {
  const list = filterCandidates([...(report.candidates || [])].sort((a, b) => (b.score || 0) - (a.score || 0)));
  const target = document.getElementById("candidateList");
  if (!list.length) {
    target.innerHTML = '<p class="empty">条件に合う候補がありません。</p>';
    return;
  }
  target.innerHTML = list.map(item => {
    const links = stockLinks(item).map(([label, url]) => `<a href="${url}" target="_blank" rel="noopener noreferrer">${label}</a>`).join("");
    const reasons = (item.reasons || []).map(reason => `<li>${reason}</li>`).join("");
    return `
      <article class="candidate-card">
        <div class="candidate-head">
          <div>
            <span class="candidate-code">${item.symbol || item.code}</span>
            <h3>${item.name}</h3>
            <span class="theme-tag">#${item.theme || "未分類"} / ${item.setup || "セットアップ未分類"}</span>
          </div>
          <span class="rank-badge ${rankClass(item.rank)}">${item.rank || "-"}</span>
        </div>
        <div class="metric-grid">
          <div class="metric"><span class="metric-label">総合スコア</span><strong>${fmt(item.score)}</strong></div>
          <div class="metric"><span class="metric-label">現在値</span><strong>${fmt(item.price)}</strong></div>
          <div class="metric"><span class="metric-label">ピボット</span><strong>${fmt(item.pivot)}</strong></div>
          <div class="metric"><span class="metric-label">初期損切り</span><strong>${fmt(item.stop)}</strong></div>
        </div>
        <p><strong>判断:</strong> ${item.action || "監視継続"}</p>
        <ul class="reason-list">${reasons}</ul>
        <div class="card-links">${links}</div>
      </article>
    `;
  }).join("");
}

function renderThemes(report) {
  const themes = report.themes || [];
  document.getElementById("themeGrid").innerHTML = themes.map(theme => `
    <article class="theme-card">
      <span>${(theme.leaders || []).join(" / ") || "leaders未設定"}</span>
      <strong>${theme.name}</strong>
      <p>${theme.note || ""}</p>
      <div class="theme-meter"><i style="width:${Math.max(0, Math.min(100, theme.strength || 0))}%"></i></div>
      <span>Strength ${fmt(theme.strength)}</span>
    </article>
  `).join("") || '<p class="empty">テーマデータがありません。</p>';
}

function renderRiskTable(report) {
  const rows = [...(report.candidates || [])].sort((a, b) => (b.score || 0) - (a.score || 0));
  document.getElementById("riskTable").innerHTML = `
    <table>
      <thead><tr><th>銘柄</th><th>ランク</th><th>現在値</th><th>ピボット</th><th>損切り</th><th>利確1</th><th>利確2</th><th>RR</th><th>方針</th></tr></thead>
      <tbody>
        ${rows.map(item => `<tr><td>${item.symbol || item.code}<br>${item.name}</td><td>${item.rank || "-"}</td><td>${fmt(item.price)}</td><td>${fmt(item.pivot)}</td><td>${fmt(item.stop)}</td><td>${fmt(item.target1)}</td><td>${fmt(item.target2)}</td><td>${fmt(item.rr)}</td><td>${item.action || "監視"}</td></tr>`).join("")}
      </tbody>
    </table>
  `;
}

function statusClass(text) {
  if (String(text).includes("成功")) return "good";
  if (String(text).includes("失敗")) return "bad";
  return "warn";
}

function renderTracking(report) {
  const tracking = report.tracking || [];
  document.getElementById("trackingList").innerHTML = tracking.map(item => `
    <article class="tracking-card">
      <strong>${item.symbol} ${item.name}</strong>
      <span>検出: ${item.detectedAt} / 経過: ${fmt(item.days, "日")}</span>
      <p>最大上昇 ${fmt(item.maxGain, "%")} / 最大下落 ${fmt(item.maxDrawdown, "%")}</p>
      <p class="tracking-status ${statusClass(item.status)}">${item.status}</p>
    </article>
  `).join("") || '<p class="empty">検証データがありません。</p>';
}

function renderReport(report) {
  currentReport = report;
  document.getElementById("reportStatus").textContent = `Report: ${report.generatedAt || "unknown"} / Universe: ${report.universe || "unknown"}`;
  renderSummary(report);
  renderCandidates(report);
  renderThemes(report);
  renderRiskTable(report);
  renderTracking(report);
}

async function loadReport() {
  try {
    const response = await fetch(`reports/latest.json?ts=${Date.now()}`);
    if (!response.ok) throw new Error("report not found");
    const report = await response.json();
    renderReport(report);
  } catch (error) {
    document.getElementById("reportStatus").textContent = "reports/latest.json が未生成のため、デモデータを表示中です。";
    renderReport(fallbackReport);
  }
}

function initNotes() {
  const key = "vcp-sepa-dashboard-note";
  const textarea = document.getElementById("dailyNote");
  textarea.value = localStorage.getItem(key) || "";
  document.getElementById("saveNote").addEventListener("click", () => {
    localStorage.setItem(key, textarea.value);
    alert("メモを保存しました");
  });
  document.getElementById("clearNote").addEventListener("click", () => {
    textarea.value = "";
    localStorage.removeItem(key);
  });
}

document.getElementById("rankFilter").addEventListener("change", () => renderCandidates(currentReport));
document.getElementById("reloadReport").addEventListener("click", loadReport);
initNotes();
loadReport();
