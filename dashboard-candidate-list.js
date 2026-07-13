import { state, $, READY_SETUPS, escapeHtml, number, format, marketLabel, inActiveMarket, setupLabel, setText, setHtml, filteredCandidates } from './dashboard-utils.js';
import { candidateCard } from './dashboard-candidate-card.js';

export function renderCandidates() {
  const all = filteredCandidates();
  const visible = all.slice(0, state.visibleLimit);
  const marketTotal = (state.report.candidates || []).filter(inActiveMarket).length;
  const total = state.report.candidates?.length ?? 0;
  setText('resultCount', state.activeMarket === 'all' ? `${all.length}件 / 全${total}件` : `${all.length}件 / 対象${marketTotal}件`);
  setHtml('candidateList', visible.length ? visible.map(candidateCard).join('') : '<p class="empty">条件に合う候補がありません。</p>');
  const loadMore = $('loadMore');
  if (loadMore) {
    loadMore.hidden = visible.length >= all.length;
    loadMore.textContent = `さらに表示（残り ${Math.max(0, all.length - visible.length)}件）`;
  }
}

export function renderRiskTable() {
  const rows = filteredCandidates().filter(item => READY_SETUPS.has(item.setupType)).slice(0, 200);
  setHtml('riskTable', `<table><thead><tr><th>銘柄</th><th>市場</th><th>R</th><th>型</th><th>RS</th><th>現在値</th><th>買いゾーン</th><th>損切り</th><th>リスク</th><th>2R</th><th>1%リスク時</th><th>Pivot差</th></tr></thead><tbody>${rows.map(item => {
    const metrics = item.metrics || {};
    const plan = item.tradePlan || {};
    return `<tr><td><strong>${escapeHtml(item.symbol)}</strong><br><small>${escapeHtml(item.name)}</small></td><td>${marketLabel(item.market)}</td><td>${escapeHtml(item.rank)}</td><td>${setupLabel(item.setupType)}</td><td>${format(metrics.rsRating)}</td><td>${format(item.price)}</td><td>${format(plan.entryLow)}–${format(plan.entryHigh)}</td><td>${format(plan.stop)}</td><td>${format(plan.riskPct, '%')}</td><td>${format(plan.target1)}</td><td>${format(plan.positionSizePctAt1PctRisk, '%')}</td><td>${format(metrics.distanceToPivotPct, '%')}</td></tr>`;
  }).join('')}</tbody></table>`);
}

export function renderThemes() {
  const allThemes = state.report.themeStrength?.length ? state.report.themeStrength : state.report.themes || [];
  const themes = state.activeMarket === 'all' ? allThemes : allThemes.filter(theme => !theme.market || theme.market === state.activeMarket);
  setHtml('themeGrid', themes.slice(0, 40).map(theme => {
    const label = theme.name || theme.theme || '未分類';
    const score = theme.rsScore ?? theme.strength ?? 0;
    const leaders = (theme.leaders || []).slice(0, 4).map(item => typeof item === 'string' ? item : item.symbol).filter(Boolean);
    return `<article class="theme-card"><div class="theme-card-head"><span>${marketLabel(theme.market)}</span><strong>${format(score)}</strong></div><h3>${escapeHtml(label)}</h3><p>${leaders.map(escapeHtml).join(' / ') || 'リーダー未取得'}</p><div class="theme-meter"><i style="width:${Math.max(0, Math.min(100, number(score) ?? 0))}%"></i></div><small>構成 ${theme.count ?? '-'} / 実行 ${theme.actionable ?? theme.note?.ready ?? '-'}</small></article>`;
  }).join('') || '<p class="empty">テーマデータがありません。</p>');
}
