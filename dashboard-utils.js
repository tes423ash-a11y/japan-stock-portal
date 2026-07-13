export const state = {
  report: { candidates: [], themes: [], tracking: [], summary: {}, marketSummary: {} },
  activeMarket: 'all',
  sectorMarket: 'all',
  expandedSector: '',
  visibleLimit: 40,
  quickFilter: ''
};

export const READY_SETUPS = new Set(['vcp_ready', 'breakout_ready', 'pullback_ready']);
const nf = new Intl.NumberFormat('ja-JP', { maximumFractionDigits: 1 });
const moneyFormat = new Intl.NumberFormat('ja-JP', { notation: 'compact', maximumFractionDigits: 1 });

export const $ = id => document.getElementById(id);
export const valueOf = id => $(id)?.value ?? '';

export function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

export function number(value) {
  if (value === null || value === undefined) return null;
  if (typeof value === 'string' && value.trim() === '') return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function formatTimestamp(value) {
  const parsed = value ? new Date(value) : null;
  if (!parsed || Number.isNaN(parsed.getTime())) return '日時不明';
  return new Intl.DateTimeFormat('ja-JP', {
    timeZone: 'Asia/Tokyo', year: 'numeric', month: 'numeric', day: 'numeric',
    hour: '2-digit', minute: '2-digit', hour12: false
  }).format(parsed) + ' JST';
}

export function formatDate(value) {
  if (!value) return '-';
  const parsed = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return new Intl.DateTimeFormat('ja-JP', {
    timeZone: 'UTC', year: 'numeric', month: 'numeric', day: 'numeric'
  }).format(parsed);
}

export function format(value, suffix = '') {
  const parsed = number(value);
  return parsed === null ? '-' : `${nf.format(parsed)}${suffix}`;
}

export function money(value) {
  const parsed = number(value);
  return parsed && parsed > 0 ? `$${moneyFormat.format(parsed)}` : '-';
}

export function marketLabel(market) {
  return market === 'JP' ? '日本株' : market === 'US' ? '米国株' : market || '-';
}

export function activeMarketLabel() {
  return state.activeMarket === 'JP' ? '日本株' : state.activeMarket === 'US' ? '米国株' : '日米';
}

export function inActiveMarket(item) {
  return state.activeMarket === 'all' || item?.market === state.activeMarket;
}

export function setupLabel(type) {
  return {
    vcp_ready: 'VCPピボット接近',
    breakout_ready: '出来高ブレイク',
    pullback_ready: '上昇トレンドの押し目',
    trend_watch: '強いトレンド監視',
    early_stage: '初動候補',
    extended: '買い場超過',
    watch_only: '形待ち',
    avoid: '除外寄り',
    data_issue: 'データ不足',
    breakout: 'ブレイク候補',
    pullback: '押し目候補',
    theme_leader: 'テーマリーダー',
    high_volatility: '高ボラ注意'
  }[type] || type || '未分類';
}

export function rankClass(rank) {
  return rank === 'S' ? 'rank-s' : rank === 'A' ? 'rank-a' : rank === 'B' ? 'rank-b' : rank === 'C' ? 'rank-c' : 'rank-d';
}

export function phaseLabel(phase) {
  return { leading: '主導', improving: '改善', weakening: '鈍化', lagging: '劣後' }[phase] || '判定中';
}

export function confidenceLabel(confidence) {
  return confidence === 'high' ? '信頼度 高' : confidence === 'medium' ? '信頼度 中' : '信頼度 低';
}

export function setText(id, text) {
  const element = $(id);
  if (element) element.textContent = text;
}

export function setHtml(id, html) {
  const element = $(id);
  if (element) element.innerHTML = html;
}

export function scoreTone(score) {
  const parsed = number(score) ?? 0;
  if (parsed >= 85) return 'tone-strong';
  if (parsed >= 70) return 'tone-good';
  if (parsed >= 55) return 'tone-neutral';
  return 'tone-weak';
}

export function changeClass(value) {
  const parsed = number(value);
  if (parsed === null || parsed === 0) return 'neutral';
  return parsed > 0 ? 'good' : 'bad';
}

export function changeText(value, suffix = '') {
  const parsed = number(value);
  if (parsed === null) return '-';
  return `${parsed > 0 ? '+' : ''}${format(parsed, suffix)}`;
}

export function freshnessInfo() {
  const generated = state.report.generatedAt ? new Date(state.report.generatedAt) : null;
  if (!generated || Number.isNaN(generated.getTime())) return { label: '日時不明', className: 'stale' };
  const hours = Math.max(0, (Date.now() - generated.getTime()) / 3600000);
  if (hours <= 18) return { label: `${Math.round(hours)}時間前`, className: 'fresh' };
  if (hours <= 48) return { label: `${Math.round(hours)}時間前`, className: 'aging' };
  return { label: `${Math.round(hours / 24)}日前`, className: 'stale' };
}

function passRank(rank, filter) {
  if (filter === 'all') return true;
  if (filter === 'S') return rank === 'S';
  if (filter === 'SAB') return ['S', 'A', 'B'].includes(rank);
  return ['S', 'A'].includes(rank);
}

function searchText(item) {
  return [item.symbol, item.code, item.name, item.market, item.sector, item.industry, item.theme]
    .filter(Boolean).join(' ').toLowerCase();
}

function passesQuickFilter(item) {
  const metrics = item.metrics || {};
  if (!state.quickFilter) return true;
  if (state.quickFilter === 'actionable') return READY_SETUPS.has(item.setupType) && ['S', 'A', 'B'].includes(item.rank);
  if (state.quickFilter === 'nearPivot') {
    const distance = number(metrics.distanceToPivotPct);
    return distance !== null && distance >= -5 && distance <= 3;
  }
  if (state.quickFilter === 'highRs') return (number(metrics.rsRating) ?? 0) >= 80;
  if (state.quickFilter === 'pullback') return item.setupType === 'pullback_ready';
  if (state.quickFilter === 'preferred') return Boolean(item.preferenceMatch);
  return true;
}

export function filteredCandidates() {
  const query = valueOf('searchInput').trim().toLowerCase();
  const market = valueOf('marketFilter') || 'all';
  const rank = valueOf('rankFilter') || 'SA';
  const setup = valueOf('setupFilter') || 'all';
  const minimumRs = Number(valueOf('rsFilter') || 0);
  const maximumAtr = Number(valueOf('atrFilter') || 999);
  const sort = valueOf('sortSelect') || 'score';

  const rows = [...(state.report.candidates || [])].filter(item => {
    const metrics = item.metrics || {};
    if (query && !searchText(item).includes(query)) return false;
    if (market !== 'all' && item.market !== market) return false;
    if (!passRank(item.rank, rank)) return false;
    if (setup === 'ready' && !READY_SETUPS.has(item.setupType)) return false;
    if (setup !== 'all' && setup !== 'ready' && item.setupType !== setup) return false;
    if ((number(metrics.rsRating) ?? 0) < minimumRs) return false;
    if ((number(metrics.atrPct) ?? 999) > maximumAtr) return false;
    return passesQuickFilter(item);
  });

  rows.sort((a, b) => {
    const am = a.metrics || {};
    const bm = b.metrics || {};
    if (sort === 'rs') return (number(bm.rsRating) ?? -1) - (number(am.rsRating) ?? -1);
    if (sort === 'vcp') return (number(b.vcpScore) ?? -1) - (number(a.vcpScore) ?? -1);
    if (sort === 'pivot') return Math.abs(number(am.distanceToPivotPct) ?? 999) - Math.abs(number(bm.distanceToPivotPct) ?? 999);
    if (sort === 'turnover') return (number(bm.avgTradingValue20Usd) ?? 0) - (number(am.avgTradingValue20Usd) ?? 0);
    if (sort === 'atr') return (number(am.atrPct) ?? 999) - (number(bm.atrPct) ?? 999);
    return (number(b.score) ?? 0) - (number(a.score) ?? 0);
  });
  return rows;
}

export function setQuickFilter(name) {
  state.quickFilter = name === 'reset' ? '' : name;
  state.visibleLimit = 40;
  document.querySelectorAll('[data-quick-filter]').forEach(button => {
    const active = button.dataset.quickFilter === state.quickFilter;
    button.classList.toggle('active', active);
    if (button.dataset.quickFilter !== 'reset') button.setAttribute('aria-pressed', String(active));
  });
}

export function sparkline(values) {
  const clean = (values || []).map(number).filter(value => value !== null);
  if (clean.length < 2) return '<span class="sparkline-empty">履歴待ち</span>';
  const width = 120;
  const height = 34;
  const min = Math.min(...clean);
  const max = Math.max(...clean);
  const span = Math.max(1, max - min);
  const points = clean.map((value, index) => {
    const x = index * width / (clean.length - 1);
    const y = height - ((value - min) / span) * (height - 4) - 2;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
  return `<svg class="sparkline" viewBox="0 0 ${width} ${height}" role="img" aria-label="RS推移"><polyline points="${points}" /></svg>`;
}
