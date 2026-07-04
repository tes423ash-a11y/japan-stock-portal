let currentReport = { candidates: [], themes: [], tracking: [], summary: {} };
const nf = new Intl.NumberFormat('ja-JP', { maximumFractionDigits: 1 });

function fmt(value, suffix = '') {
  if (value === undefined || value === null || value === '') return '-';
  return typeof value === 'number' ? `${nf.format(value)}${suffix}` : `${value}${suffix}`;
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

function filterCandidates(candidates) {
  const value = document.getElementById('rankFilter').value;
  if (value === 'A') return candidates.filter(x => ['S', 'A'].includes(x.rank));
  if (value === 'B') return candidates.filter(x => ['S', 'A', 'B'].includes(x.rank));
  if (value === 'breakout') return candidates.filter(x => x.setupType === 'breakout');
  if (value === 'pullback') return candidates.filter(x => x.setupType === 'pullback');
  return candidates;
}

function scoreLine(item) {
  const c = item.componentScores || {};
  const parts = [['T', c.trend], ['M', c.momentum], ['V', c.volume], ['R', c.risk], ['Theme', c.theme], ['Setup', c.setup], ['Liq', c.liquidity]];
  return `<div class="score-breakdown">${parts.map(([k, v]) => `<span>${k}: <strong>${fmt(v)}</strong></span>`).join('')}</div>`;
}

function metricsLine(item) {
  const m = item.metrics || {};
  const parts = [['20日', m.ret20Pct, '%'], ['60日', m.ret60Pct, '%'], ['ATR', m.atrPct, '%'], ['高値比', m.drawdownFromHighPct, '%'], ['売買代金USD', m.avgTradingValue20Usd, '']];
  return `<div class="score-breakdown metrics-line">${parts.map(([k, v, s]) => `<span>${k}: <strong>${fmt(v, s)}</strong></span>`).join('')}</div>`;
}

function renderCandidates(report) {
  const list = filterCandidates([...(report.candidates || [])].sort((a, b) => (b.score || 0) - (a.score || 0)));
  const target = document.getElementById('candidateList');
  if (!list.length) {
    target.innerHTML = '<p class="empty">条件に合う候補がありません。</p>';
    return;
  }
  target.innerHTML = list.map(item => {
    const reasons = (item.reasons || []).slice(0, 8).map(x => `<li>${x}</li>`).join('');
    return `<article class="candidate-card">
      <div class="candidate-head"><div><span class="candidate-code">${item.symbol || item.code} / ${item.market || '-'} / ${item.dataSource || 'unknown'}</span><h3>${item.name}</h3><span class="theme-tag">#${item.theme || '未分類'} / ${item.setup || setupLabel(item.setupType)}</span></div><span class="rank-badge ${rankClass(item.rank)}">${item.rank || '-'}</span></div>
      <div class="metric-grid"><div class="metric"><span class="metric-label">総合</span><strong>${fmt(item.score)}</strong></div><div class="metric"><span class="metric-label">型</span><strong>${setupLabel(item.setupType)}</strong></div><div class="metric"><span class="metric-label">現在値</span><strong>${fmt(item.price)}</strong></div><div class="metric"><span class="metric-label">損切り</span><strong>${fmt(item.stop)}</strong></div></div>
      ${scoreLine(item)}${metricsLine(item)}
      <p><strong>判断:</strong> ${item.action || '監視継続'}</p><ul class="reason-list">${reasons}</ul><div class="card-links">${stockLinks(item)}</div>
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
  const rows = [...(report.candidates || [])].sort((a, b) => (b.score || 0) - (a.score || 0));
  document.getElementById('riskTable').innerHTML = `<table><thead><tr><th>銘柄</th><th>市場</th><th>型</th><th>ランク</th><th>現在値</th><th>ピボット</th><th>損切り</th><th>利確1</th><th>利確2</th><th>方針</th></tr></thead><tbody>${rows.map(item => `<tr><td>${item.symbol || item.code}<br>${item.name}</td><td>${item.market || '-'}</td><td>${setupLabel(item.setupType)}</td><td>${item.rank || '-'}</td><td>${fmt(item.price)}</td><td>${fmt(item.pivot)}</td><td>${fmt(item.stop)}</td><td>${fmt(item.target1)}</td><td>${fmt(item.target2)}</td><td>${item.action || '監視'}</td></tr>`).join('')}</tbody></table>`;
}

function renderTracking(report) {
  const tracking = report.tracking || [];
  document.getElementById('trackingList').innerHTML = tracking.map(item => `<article class="tracking-card"><strong>${item.symbol} ${item.name}</strong><span>検出: ${item.detectedAt} / 経過: ${fmt(item.days, '日')}</span><p>最大上昇 ${fmt(item.maxGain, '%')} / 最大下落 ${fmt(item.maxDrawdown, '%')}</p><p class="tracking-status warn">${item.status}</p></article>`).join('') || '<p class="empty">検証データがありません。</p>';
}

function renderReport(report) {
  currentReport = report;
  document.getElementById('reportStatus').textContent = `Report: ${report.generatedAt || 'unknown'} / Universe: ${report.universe || 'unknown'}`;
  renderSummary(report); renderCandidates(report); renderThemes(report); renderRiskTable(report); renderTracking(report);
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

document.getElementById('rankFilter').addEventListener('change', () => renderCandidates(currentReport));
document.getElementById('reloadReport').addEventListener('click', loadReport);
initNotes();
loadReport();
