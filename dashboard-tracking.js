import { state, $, escapeHtml, format, setHtml } from './dashboard-utils.js';
import { renderCandidates, renderRiskTable } from './dashboard-candidate-list.js';

export function renderTracking() {
  const summary = state.report.trackingSummary || {};
  const cards = [['追跡総数', summary.total ?? 0], ['追跡中', summary.tracking ?? 0], ['2R以上', summary.twoR ?? 0], ['損切り到達', summary.stopped ?? 0]];
  setHtml('trackingSummary', cards.map(([label, value]) => `<article class="summary-card"><span>${label}</span><strong>${value}</strong></article>`).join(''));
  const rows = state.report.tracking || [];
  setHtml('trackingList', rows.slice(0, 50).map(item => `<article class="tracking-card"><div><strong>${escapeHtml(item.symbol)} ${escapeHtml(item.name)}</strong><span>${escapeHtml(item.detectedAt)}検出 / ${item.days ?? 0}日</span></div><div class="tracking-metrics"><span>現在 ${format(item.currentGainPct, '%')}</span><span>最大 ${format(item.maxGainPct, '%')}</span><span>最大逆行 ${format(item.maxDrawdownPct, '%')}</span><span>${escapeHtml(item.status)}</span></div></article>`).join('') || '<p class="empty">次回以降、S/A実行候補の事後成績が蓄積されます。</p>');
}

export function focusSymbol(symbol) {
  if ($('searchInput')) $('searchInput').value = symbol;
  if ($('rankFilter')) $('rankFilter').value = 'all';
  state.quickFilter = '';
  document.querySelectorAll('[data-quick-filter]').forEach(button => button.classList.remove('active'));
  state.visibleLimit = 40;
  renderCandidates();
  renderRiskTable();
  location.hash = '#candidates';
}

export function filterSector(label, market) {
  if ($('searchInput')) $('searchInput').value = label;
  if ($('marketFilter')) $('marketFilter').value = market || 'all';
  if ($('rankFilter')) $('rankFilter').value = 'SAB';
  state.quickFilter = '';
  state.visibleLimit = 40;
  renderCandidates();
  renderRiskTable();
  location.hash = '#candidates';
}
