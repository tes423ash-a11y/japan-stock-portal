let currentReport = { candidates: [], themes: [], tracking: [], summary: {} };
const nf = new Intl.NumberFormat('ja-JP', { maximumFractionDigits: 1 });
const money = new Intl.NumberFormat('ja-JP', { notation: 'compact', maximumFractionDigits: 1 });

function fmt(value, suffix = '') {
  if (value === undefined || value === null || value === '') return '-';
  return typeof value === 'number' ? `${nf.format(value)}${suffix}` : `${value}${suffix}`;
}

function fmtMoney(value) {
  if (!value) return '-';
  return `$${money.format(value)}`;
}

function rankClass(rank) {
  if (rank === 'S') return 'rank-s';
  if (rank === 'A') return 'rank-a';
  if (rank === 'B') return 'rank-b';
  if (rank === 'C') return 'rank-c';
  return 'rank-d';
}

function setupLabel(type) {
  return {
    breakout: 'ブレイク候補',
    pullback: '押し目候補',
    theme_leader: 'テーマリーダー',
    high_volatility: '高ボラ注意',
    trend_watch: 'トレンド監視',
    watch_only: '監視のみ',
    avoid: '除外寄り'
  }[type] || type || '未分類';
}

function marketLabel(market) {
  return market === 'JP' ? '日本株' : market === 'US' ? '米国株' : market || '-';
}

function stockLinks(item) {
  const code = item.code || String(item.symbol || '').replace('.T', '');
  if (item.market === 'US') {
    return `<a href="https://finance.yahoo.com/quote/${item.symbol}" target="_blank" rel="noopener noreferrer">Yahoo</a><a href="https://www.tradingview.com/symbols/${item.symbol}/" target="_blank" rel="noopener noreferrer">TradingView</a>`;
  }
  return `<a href="https://kabutan.jp/stock/?code=${code}" target="_blank" rel="noopener noreferrer">株探</a><a href="https://finance.yahoo.co.jp/quote/${code}.T" target="_blank" rel="noopener noreferrer">Yahoo</a><a href="https://jp.tradingview.com/symbols/TSE-${code}/" target="_blank" rel="noopener noreferrer">TradingView</a>`;
}

function renderSummary(report) {
  const s = report.summary || {};
  const cards = [
    ['対象', s.total ?? report.candidates?.length ?? 0],
    ['S', s.sRank ?? 0],
    ['A', s.aRank ?? 0],
    ['ブレイク', s.breakoutReady ?? 0],
    ['押し目', s.pullbackReady ?? 0],
    ['高ボラ', s.highVolatility ?? 0],
    ['平均', s.averageScore ?? '-']
  ];
  document.getElementById('summaryCards').innerHTML = cards.map(([label, value]) => `<article class="summary-card"><span>${label}</span><strong>${value}</strong></article>`).join('');
}

function renderMarketSummary(report) {
  const summary = report.marketSummary || {};
  const html = ['JP', 'US'].map(market => {
    const row = summary[market] || {};
    return `<article class="market-card"><span>${marketLabel(market)}</span><strong>${row.selectedRows ?? 0}銘柄</strong><p>入力 ${row.inputRows ?? 0} / S ${row.sRank ?? 0} / A ${row.aRank ?? 0} / 平均 ${row.averageScore ?? '-'}</p></article>`;
  }).join('');
  const target = document.getElementById('marketSummary');
  if (target) target.innerHTML = html;
}

function getFilters() {
  return {
    q: (document.getElementById('searchInput')?.value || '').trim().toLowerCase(),
    market: document.getElementById('marketFilter')?.value || 'all',
    rank: document.getElementById('rankFilter')?.value || 'all',
    setup: document.getElementById('setupFilter')?.value || 'all',
    sort: document.getElementById('sortSelect')?.value || 'score'
  };
}

function rankPass(rank, filter) {
  if (filter === 'S') return rank === 'S';
  if (filter === 'A') return ['S', 'A'].includes(rank);
  if (filter === 'B') return ['S', 'A', 'B'].includes(rank);
  return true;
}

function filterCandidates(candidates) {
  const f = getFilters();
  return candidates.filter(item => {
    const haystack = `${item.symbol || ''} ${item.code || ''} ${item.name || ''} ${item.theme || ''} ${item.market || ''}`.toLowerCase();
    if (f.q && !haystack.includes(f.q)) return false;
    if (f.market !== 'all' && item.market !== f.market) return false;
    if (!rankPass(item.rank, f.rank)) return false;
    if (f.setup !== 'all' && item.setupType !== f.setup) return false;
    return true;
  }).sort((a, b) => {
    if (f.sort === 'turnover') return (b.metrics?.avgTradingValue20Usd || 0) - (a.metrics?.avgTradingValue20Usd || 0);
    if (f.sort === 'atr') return (a.metrics?.atrPct ?? 999) - (b.metrics?.atrPct ?? 999);
    if (f.sort === 'ret60') return (b.metrics?.ret60Pct ?? -999) - (a.metrics?.ret60Pct ?? -999);
    return (b.score || 0) - (a.score || 0);
  });
}

function scoreLine(item) {
  const c = item.componentScores || {};
  const parts = [['T', c.trend], ['M', c.momentum], ['V', c.volume], ['R', c.risk], ['Theme', c.theme], ['Setup', c.setup], ['Liq', c.liquidity]];
  return `<div class="score-breakdown">${parts.map(([k, v]) => `<span>${k}: <strong>${fmt(v)}</strong></span>`).join('')}</div>`;
}

function metricsLine(item) {
  const m = item.metrics || {};
  const parts = [
    ['20日', fmt(m.ret20Pct, '%')],
    ['60日', fmt(m.ret60Pct, '%')],
    ['ATR', fmt(m.atrPct, '%')],
    ['高値比', fmt(m.drawdownFromHighPct, '%')],
    ['売買代金', fmtMoney(m.avgTradingValue20Usd)]
  ];
  return `<div class="score-breakdown metrics-line">${parts.map(([k, v]) => `<span>${k}: <strong>${v}</strong></span>`).join('')}</div>`;
}

function priorityText(item) {
  if (item.rank === 'S') return '最優先';
  if (item.rank === 'A') return '優先監視';
  if (item.setupType === 'high_volatility') return 'サイズ注意';
  if (item.setupType === 'avoid') return '見送り寄り';
  return '監視';
}

function renderCandidates(report) {
  const all = report.candidates || [];
  const list = filterCandidates(all);
  const target = document.getElementById('candidateList');
  const counter = document.getElementById('resultCount');
  if (counter) counter.textContent = `${list.length} / ${all.length}件を表示中`;
  if (!list.length) {
    target.innerHTML = '<p class="empty">条件に合う候補がありません。</p>';
    return;
  }
  target.innerHTML = list.map(item => {
    const reasons = (item.reasons || []).slice(0, 7).map(x => `<li>${x}</li>`).join('');
    return `<article class="candidate-card">
      <div class="candidate-head">
        <div><span class="candidate-code">${item.symbol || item.code} / ${marketLabel(item.market)} / ${item.dataSource || 'unknown'}</span><h3>${item.name}</h3><span class="theme-tag">#${item.theme || '未分類'} / ${item.setup || setupLabel(item.setupType)}</span></div>
        <div class="rank-stack"><span class="rank-badge ${rankClass(item.rank)}">${item.rank || '-'}</span><small>${priorityText(item)}</small></div>
      </div>
      <div class="metric-grid"><div class="metric"><span class="metric-label">総合</span><strong>${fmt(item.score)}</strong></div><div class="metric"><span class="metric-label">型</span><strong>${setupLabel(item.setupType)}</strong></div><div class="metric"><span class="metric-label">現在値</span><strong>${fmt(item.price)}</strong></div><div class="metric"><span class="metric-label">損切り</span><strong>${fmt(item.stop)}</strong></div></div>
      ${scoreLine(item)}${metricsLine(item)}
      <p class="action-line"><strong>判断:</strong> ${item.action || '監視継続'}</p><ul class="reason-list">${reasons}</ul><div class="card-links">${stockLinks(item)}</div>
    </article>`;
  }).join('');
}

function renderThemes(report) {
  const themes = report.themes || [];
  document.getElementById('themeGrid').innerHTML = themes.map(theme => {
    const note = typeof theme.note === 'object' ? Object.entries(theme.note).map(([k, v]) => `${setupLabel(k)} ${v}`).join(' / ') : (theme.note || '');
    return `<article class="theme-card"><span>${(theme.leaders || []).join(' / ') || 'leaders未設定'}</span><strong>${theme.name}</strong><p>${note}</p><div class="theme-meter"><i style="width:${Math.max(0, Math.min(100, theme.strength || 0))}%"></i></div><span>Strength ${fmt(theme.strength)}</span></article>`;
  }).join('') || '<p class="empty">テーマデータがありません。</p>';
}

function renderRiskTable(report) {
  const rows = filterCandidates(report.candidates || []);
  document.getElementById('riskTable').innerHTML = `<table><thead><tr><th>銘柄</th><th>市場</th><th>型</th><th>ランク</th><th>現在値</th><th>ピボット</th><th>損切り</th><th>利確1</th><th>売買代金</th><th>方針</th></tr></thead><tbody>${rows.map(item => `<tr><td>${item.symbol || item.code}<br>${item.name}</td><td>${marketLabel(item.market)}</td><td>${setupLabel(item.setupType)}</td><td>${item.rank || '-'}</td><td>${fmt(item.price)}</td><td>${fmt(item.pivot)}</td><td>${fmt(item.stop)}</td><td>${fmt(item.target1)}</td><td>${fmtMoney(item.metrics?.avgTradingValue20Usd)}</td><td>${item.action || '監視'}</td></tr>`).join('')}</tbody></table>`;
}

function renderTracking(report) {
  const tracking = report.tracking || [];
  document.getElementById('trackingList').innerHTML = tracking.map(item => `<article class="tracking-card"><strong>${item.symbol} ${item.name}</strong><span>検出: ${item.detectedAt} / 経過: ${fmt(item.days, '日')}</span><p>最大上昇 ${fmt(item.maxGain, '%')} / 最大下落 ${fmt(item.maxDrawdown, '%')}</p><p class="tracking-status warn">${item.status}</p></article>`).join('') || '<p class="empty">検証データがありません。</p>';
}

function renderReport(report) {
  currentReport = report;
  document.getElementById('reportStatus').textContent = `Report: ${report.generatedAt || 'unknown'} / Universe: ${report.universe || 'unknown'} / JP・US別トップ${report.screeningTopNPerMarket || '-'}`;
  renderSummary(report); renderMarketSummary(report); renderCandidates(report); renderThemes(report); renderRiskTable(report); renderTracking(report);
}

async function loadReport() {
  try {
    const response = await fetch(`reports/latest.json?ts=${Date.now()}`);
    if (!response.ok) throw new Error('report not found');
    renderReport(await response.json());
  } catch (error) {
    document.getElementById('reportStatus').textContent = 'reports/latest.json が未生成です。Actionsを実行してください。';
    renderReport(currentReport);
  }
}

function initNotes() {
  const key = 'vcp-sepa-dashboard-note';
  const textarea = document.getElementById('dailyNote');
  textarea.value = localStorage.getItem(key) || '';
  document.getElementById('saveNote').addEventListener('click', () => { localStorage.setItem(key, textarea.value); alert('メモを保存しました'); });
  document.getElementById('clearNote').addEventListener('click', () => { textarea.value = ''; localStorage.removeItem(key); });
}

['searchInput', 'marketFilter', 'rankFilter', 'setupFilter', 'sortSelect'].forEach(id => {
  document.getElementById(id)?.addEventListener('input', () => { renderCandidates(currentReport); renderRiskTable(currentReport); });
  document.getElementById(id)?.addEventListener('change', () => { renderCandidates(currentReport); renderRiskTable(currentReport); });
});
document.getElementById('reloadReport').addEventListener('click', loadReport);
initNotes();
loadReport();
