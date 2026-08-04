const DATA_URL = 'reports/validation.json';
const setupLabels = { vcp_ready: 'VCP', breakout_ready: 'ブレイク', pullback_ready: '押し目' };
const reasonLabels = {
  target: '2R利確', target_gap_conservative: 'ギャップ利確', stop: '損切り', stop_gap: 'ギャップ損切り',
  ambiguous_bar_stop_first: '同日両到達→損切り', max_hold: '保有期限', mark_to_market: '評価中',
  delisted_last_available_close: '上場廃止時の最終値',
};

let report = null;
let activeFilter = 'all';
let chart = null;

const escapeHtml = value => String(value ?? '').replace(/[&<>'"]/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' })[character]);
const isNumeric = value => value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value));
const fmt = (value, digits = 1, suffix = '') => isNumeric(value) ? `${Number(value).toFixed(digits)}${suffix}` : '—';
const signed = (value, digits = 2, suffix = '') => isNumeric(value) ? `${Number(value) > 0 ? '+' : ''}${Number(value).toFixed(digits)}${suffix}` : '—';
const tone = value => Number(value) > 0 ? 'positive' : Number(value) < 0 ? 'negative' : '';

function renderQuality() {
  const quality = report.quality || {};
  const config = report.config || {};
  const status = document.querySelector('#qualityStatus');
  const historical = Boolean(quality.historicalUniverseCoverage);
  status.textContent = historical ? '履歴母集団あり' : '前向き検証';
  status.className = `quality-badge ${historical ? 'pass' : 'warning'}`;
  const banner = document.querySelector('#qualityBanner');
  banner.className = `quality-banner ${historical ? '' : 'warning'}`;
  banner.textContent = quality.warning || '過去時点の上場母集団が読み込まれ、上場廃止イベントを含めて検証しています。';
  const cards = [
    ['約定', '次取引日始値', report.methodology?.signalTiming],
    ['往復コスト', `${fmt(config.fee_bps_per_side, 0)}bp手数料 + ${fmt(config.slippage_bps_per_side, 0)}bp滑り / 片道`, report.methodology?.costs],
    ['同日両到達', '損切り優先', report.methodology?.intradayAmbiguity],
    ['母集団', historical ? '過去母集団あり' : '前向き記録のみ', report.methodology?.survivorship],
  ];
  document.querySelector('#assumptionGrid').innerHTML = cards.map(([label, value, note]) => `<article class="assumption-card"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong><p>${escapeHtml(note)}</p></article>`).join('');
}

function renderSummary() {
  const summary = report.summary || {};
  const cards = [
    ['決済済み', fmt(summary.closed, 0), `全${fmt(summary.signals, 0)}シグナル`],
    ['勝率', fmt(summary.winRatePct, 1, '%'), `${fmt(summary.wins, 0)}勝`],
    ['期待値', signed(summary.expectancyR, 3, 'R'), `中央値 ${signed(summary.medianR, 3, 'R')}`],
    ['累積', signed(summary.cumulativeR, 2, 'R'), `PF ${fmt(summary.profitFactor, 2)}`],
  ];
  document.querySelector('#summaryGrid').innerHTML = cards.map(([label, value, note]) => `<article class="summary-card"><span>${escapeHtml(label)}</span><strong class="${tone(parseFloat(value))}">${escapeHtml(value)}</strong><span>${escapeHtml(note)}</span></article>`).join('');
}

function renderBreakdown(target, rows, labelMap = {}) {
  document.querySelector(target).innerHTML = (rows || []).map(row => `<div class="breakdown-row"><strong>${escapeHtml(labelMap[row.label] || row.label)}</strong><span>${escapeHtml(row.closed)}/${escapeHtml(row.total)}件</span><span>勝率 ${fmt(row.winRatePct, 0, '%')}</span><span class="${tone(row.expectancyR)}">${signed(row.expectancyR, 2, 'R')}</span></div>`).join('') || '<p>集計待ち</p>';
}

function renderChart() {
  const data = report.cumulativeR || [];
  const empty = document.querySelector('#chartEmpty');
  if (!data.length || !window.LightweightCharts) {
    empty.textContent = data.length ? 'チャートライブラリを読み込めませんでした。' : '決済済みレコードが貯まると累積Rを表示します。';
    return;
  }
  empty.textContent = '';
  const container = document.querySelector('#cumulativeChart');
  chart?.remove();
  chart = window.LightweightCharts.createChart(container, {
    autoSize: true,
    layout: { background: { color: '#081525' }, textColor: '#91a4bb', attributionLogo: true },
    grid: { vertLines: { color: '#16293e' }, horzLines: { color: '#16293e' } },
    rightPriceScale: { borderColor: '#20344c' }, timeScale: { borderColor: '#20344c', timeVisible: false },
    crosshair: { vertLine: { color: '#62a8ff' }, horzLine: { color: '#62a8ff' } },
  });
  const series = chart.addSeries(window.LightweightCharts.LineSeries, { color: '#55d6be', lineWidth: 3, priceFormat: { type: 'custom', formatter: value => `${value.toFixed(2)}R` } });
  series.setData(data);
  chart.timeScale().fitContent();
}

function matchesFilter(trade) {
  if (activeFilter === 'closed') return Boolean(trade.closed);
  if (activeFilter === 'open') return trade.status === 'open';
  if (activeFilter === 'issue') return ['missing_history', 'pending_next_session', 'invalid_stop', 'invalid_signal_date'].includes(trade.status);
  return true;
}

function renderTrades() {
  const rows = (report.trades || []).filter(matchesFilter);
  document.querySelector('#tradeCount').textContent = `${rows.length}件`;
  document.querySelector('#tradeList').innerHTML = rows.slice(0, 160).map(trade => {
    const status = trade.closed ? reasonLabels[trade.exitReason] || '決済済み' : trade.status === 'open' ? '保有中' : trade.status === 'pending_next_session' ? '次足待ち' : 'データ確認';
    return `<article class="trade-card"><div class="trade-symbol"><strong>${escapeHtml(trade.symbol)} ${escapeHtml(trade.name || '')}</strong><span>${escapeHtml(trade.market)} / ${escapeHtml(setupLabels[trade.setupType] || trade.setupType)} / 検出 ${escapeHtml(trade.detectedAt)}</span></div><div class="trade-metric"><span>約定</span><strong>${escapeHtml(trade.entryDate || '待機')}</strong></div><div class="trade-metric"><span>決済</span><strong>${escapeHtml(trade.exitDate || '—')}</strong></div><div class="trade-metric"><span>損益</span><strong class="${tone(trade.netReturnPct)}">${signed(trade.netReturnPct, 2, '%')}</strong></div><div class="trade-metric"><span>R</span><strong class="${tone(trade.rMultiple)}">${signed(trade.rMultiple, 2, 'R')}</strong></div><span class="status-pill ${trade.closed ? tone(trade.rMultiple) : 'pending'}">${escapeHtml(status)}</span></article>`;
  }).join('') || '<p class="quality-banner">該当する検証レコードはありません。</p>';
}

function render() {
  document.querySelector('#generatedAt').textContent = `検証更新 ${new Date(report.generatedAt).toLocaleString('ja-JP')}`;
  renderQuality(); renderSummary();
  renderBreakdown('#marketBreakdown', report.byMarket, { JP: '日本株', US: '米国株' });
  renderBreakdown('#setupBreakdown', report.bySetup, setupLabels);
  renderChart(); renderTrades();
}

async function load() {
  try {
    const response = await fetch(`${DATA_URL}?ts=${Date.now()}`, { cache: 'no-store' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    report = await response.json(); render();
  } catch (error) {
    document.querySelector('#qualityStatus').textContent = '読込失敗';
    document.querySelector('#qualityStatus').className = 'quality-badge warning';
    document.querySelector('#qualityBanner').textContent = `検証レポートを読み込めませんでした: ${error.message}`;
  }
}

document.querySelectorAll('[data-filter]').forEach(button => button.addEventListener('click', () => {
  activeFilter = button.dataset.filter;
  document.querySelectorAll('[data-filter]').forEach(item => item.classList.toggle('active', item === button));
  renderTrades();
}));
document.querySelector('#reloadValidation').addEventListener('click', load);
load();
