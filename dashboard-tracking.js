import { state, $, escapeHtml, format, inActiveMarket, marketLabel, number, setHtml, setQuickFilter } from './dashboard-utils.js?v=20260714-v5-1';
import { renderCandidates, renderRiskTable } from './dashboard-candidate-list.js?v=20260714-v5-1';

export function renderTracking() {
  const allRows = state.report.tracking || [];
  const rows = allRows.filter(inActiveMarket);
  const summary = state.activeMarket === 'all' ? state.report.trackingSummary || {} : {
    total: rows.length,
    tracking: rows.filter(item => item.status === '追跡中').length,
    twoR: rows.filter(item => item.status?.includes('2R') || (number(item.maxGainPct) ?? 0) >= 2 * (number(item.initialRiskPct) ?? Infinity)).length,
    stopped: rows.filter(item => item.status?.includes('損切り')).length,
    basis: state.report.trackingSummary?.basis
  };
  const cards = [['追跡総数', summary.total ?? 0], ['追跡中', summary.tracking ?? 0], ['2R以上', summary.twoR ?? 0], ['損切り到達', summary.stopped ?? 0]];
  setHtml('trackingSummary', cards.map(([label, value]) => `<article class="summary-card"><span>${label}</span><strong>${value}</strong></article>`).join(''));
  setHtml('trackingBasis', `<p>${escapeHtml(summary.basis || '検出日の終値を基準に日次終値で更新')}</p>`);
  setHtml('trackingList', rows.slice(0, 50).map(item => `<article class="tracking-card"><div><strong>${escapeHtml(item.symbol)} ${escapeHtml(item.name)}</strong><span>${marketLabel(item.market)} / ${escapeHtml(item.detectedAt)}検出 / ${item.days ?? 0}日</span></div><div class="tracking-metrics"><span>現在 ${format(item.currentGainPct, '%')}</span><span>最大 ${format(item.maxGainPct, '%')}</span><span>最大逆行 ${format(item.maxDrawdownPct, '%')}</span><span>${escapeHtml(item.status)}</span></div></article>`).join('') || '<p class="empty">次回以降、S/A実行候補の事後成績が蓄積されます。</p>');
}

export function focusSymbol(symbol) {
  if ($('searchInput')) $('searchInput').value = symbol;
  if ($('rankFilter')) $('rankFilter').value = 'all';
  setQuickFilter('reset');
  state.visibleLimit = 40;
  renderCandidates();
  renderRiskTable();
  window.dispatchEvent(new CustomEvent('dashboard:navigate', { detail: { page: 'candidates', resetScroll: true } }));
}

export function filterSector(label, market) {
  if ($('searchInput')) $('searchInput').value = label;
  if ($('marketFilter')) $('marketFilter').value = market || 'all';
  if ($('rankFilter')) $('rankFilter').value = 'SAB';
  setQuickFilter('reset');
  state.visibleLimit = 40;
  renderCandidates();
  renderRiskTable();
  window.dispatchEvent(new CustomEvent('dashboard:navigate', { detail: { page: 'candidates', resetScroll: true } }));
}
