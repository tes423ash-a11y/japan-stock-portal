import { escapeHtml, number, format, money, marketLabel, setupLabel, rankClass } from './dashboard-utils.js?v=20260722-v6';

function scoreBreakdown(item) {
  const scores = item.componentScores || {};
  const parts = [
    ['Trend', scores.trend, 25], ['RS', scores.rs ?? scores.momentum, 20],
    ['VCP', scores.vcp ?? scores.setup, 25], ['Volume', scores.volume, 10],
    ['Risk', scores.risk, 10], ['Liq', scores.liquidity, 10]
  ];
  return `<div class="component-grid">${parts.map(([label, score, max]) => `
    <div class="component"><span>${label}</span><strong>${format(score)}<small>/${max}</small></strong><i><b style="width:${Math.max(0, Math.min(100, (number(score) ?? 0) / max * 100))}%"></b></i></div>`).join('')}</div>`;
}

function warningChips(item) {
  const warnings = item.warnings || [];
  if (!warnings.length) return '<span class="warning-chip good-chip">重大警告なし</span>';
  return warnings.map(warning => `<span class="warning-chip">${escapeHtml(warning)}</span>`).join('');
}

function zoneState(item) {
  const price = number(item.price ?? item.metrics?.price);
  const plan = item.tradePlan || {};
  const low = number(plan.entryLow);
  const high = number(plan.entryHigh);
  if (price === null || low === null || high === null) return { label: 'ゾーン未計算', className: 'neutral-chip' };
  if (price >= low && price <= high) return { label: '基準ゾーン内', className: 'good-chip' };
  if (price < low) return { label: '条件待ち', className: 'neutral-chip' };
  return { label: '基準超過', className: 'warn-chip' };
}

export function candidateCard(item) {
  const metrics = item.metrics || {};
  const plan = item.tradePlan || {};
  const quality = item.dataQuality || {};
  const zone = zoneState(item);
  const reasons = (item.reasons || []).slice(0, 7).map(reason => `<li>${escapeHtml(reason)}</li>`).join('');
  const checks = (item.trendTemplate?.checks || []).map(check => `<span>${escapeHtml(check)}</span>`).join('');
  return `
    <article class="candidate-card" data-symbol="${escapeHtml(item.symbol)}">
      <header class="candidate-head"><div><span class="candidate-code">${escapeHtml(item.symbol || item.code)} / ${marketLabel(item.market)} / ${escapeHtml(item.dataSource || '-')}</span><h3>${escapeHtml(item.name)}</h3><div class="tag-row"><span>#${escapeHtml(item.sector || item.theme || '未分類')}</span>${item.theme && item.theme !== item.sector ? `<span>#${escapeHtml(item.theme)}</span>` : ''}${item.preferenceMatch ? '<span class="preferred-tag">重点テーマ</span>' : ''}</div></div><div class="rank-stack"><span class="rank-badge ${rankClass(item.rank)}">${escapeHtml(item.rank || '-')}</span><small>${format(item.score)}点</small></div></header>
      <div class="decision-row"><span class="setup-badge">${escapeHtml(item.setup || setupLabel(item.setupType))}</span><span class="${zone.className}">${zone.label}</span><span>RS ${format(metrics.rsRating)}</span><span>VCP ${format(item.vcpScore)}/25</span><span>Trend ${item.trendTemplate?.passed ?? 0}/8</span></div>
      <div class="trade-grid"><div><span>現在値</span><strong>${format(item.price)}</strong></div><div><span>基準ゾーン</span><strong>${format(plan.entryLow)}–${format(plan.entryHigh)}</strong></div><div><span>無効化水準</span><strong>${format(plan.stop)} <small>${format(plan.riskPct, '%')}</small></strong></div><div><span>リスク換算上限</span><strong>${format(plan.positionSizePctAt1PctRisk, '%')}</strong></div></div>
      ${scoreBreakdown(item)}
      <div class="warning-row">${warningChips(item)}</div><p class="action-line"><strong>機械判定:</strong> ${escapeHtml(item.action || '監視継続')}</p>
      <details class="candidate-detail"><summary>根拠と詳細指標</summary><div class="metric-chip-row"><span>Pivot差 ${format(metrics.distanceToPivotPct, '%')}</span><span>20日 ${format(metrics.ret20Pct, '%')}</span><span>60日 ${format(metrics.ret60Pct, '%')}</span><span>120日 ${format(metrics.ret120Pct, '%')}</span><span>ATR ${format(metrics.atrPct, '%')}</span><span>出来高 ${format(metrics.latestVolumeRatio20)}x</span><span>Dry-up ${format(metrics.volumeDryUp5vs50)}x</span><span>売買代金 ${money(metrics.avgTradingValue20Usd)}</span></div><div class="trend-checks">${checks}</div><ul class="reason-list">${reasons}</ul><p class="data-quality">データ: ${escapeHtml(quality.status || '-')} / ${quality.bars ?? 0}本 / ${escapeHtml(quality.asOf || '-')}</p></details>
    </article>`;
}
