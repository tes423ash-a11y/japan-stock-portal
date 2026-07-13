import {
  state, READY_SETUPS, valueOf, escapeHtml, number, format, money, marketLabel, activeMarketLabel, inActiveMarket, setupLabel,
  rankClass, phaseLabel, confidenceLabel, setHtml, scoreTone, changeClass,
  changeText, freshnessInfo, sparkline, formatDate
} from './dashboard-utils.js';

export function renderSummary() {
  const candidates = (state.report.candidates || []).filter(inActiveMarket);
  const summary = state.activeMarket === 'all' ? state.report.summary || {} : {
    total: candidates.length,
    actionable: candidates.filter(item => READY_SETUPS.has(item.setupType) && ['S', 'A', 'B'].includes(item.rank)).length,
    sRank: candidates.filter(item => item.rank === 'S').length,
    aRank: candidates.filter(item => item.rank === 'A').length,
    vcpReady: candidates.filter(item => item.setupType === 'vcp_ready').length,
    breakoutReady: candidates.filter(item => item.setupType === 'breakout_ready').length,
    pullbackReady: candidates.filter(item => item.setupType === 'pullback_ready').length,
    extended: candidates.filter(item => item.setupType === 'extended').length
  };
  const cards = [
    ['分析数', summary.total ?? 0, state.activeMarket === 'all' ? '約1000銘柄' : `${activeMarketLabel()}の対象`],
    ['実行候補', summary.actionable ?? 0, 'VCP・BO・押し目'],
    ['Sランク', summary.sRank ?? 0, '最優先'],
    ['Aランク', summary.aRank ?? 0, '優先監視'],
    ['VCP接近', summary.vcpReady ?? 0, 'ピボット5%以内'],
    ['出来高BO', summary.breakoutReady ?? 0, '出来高確認済み'],
    ['押し目', summary.pullbackReady ?? 0, '支持線付近'],
    ['買い場超過', summary.extended ?? 0, '追いかけない']
  ];
  setHtml('summaryCards', cards.map(([label, value, note]) => `
    <article class="summary-card"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong><small>${escapeHtml(note)}</small></article>
  `).join(''));
}

export function renderCoverage() {
  const marketRow = state.report.marketSummary?.[state.activeMarket] || {};
  const coverage = state.activeMarket === 'all' ? state.report.coverage || {} : {
    usable: marketRow.downloadedRows ?? marketRow.selectedRows ?? 0,
    requested: marketRow.universeRows ?? marketRow.builtRows ?? marketRow.selectedRows ?? 0,
    missing: marketRow.missingRows ?? 0,
    missingSymbols: marketRow.missingSymbols || [],
    coveragePct: marketRow.coveragePct ?? 0,
    status: (number(marketRow.coveragePct) ?? 0) >= 95 ? 'good' : (number(marketRow.coveragePct) ?? 0) >= 80 ? 'degraded' : 'poor'
  };
  const usable = coverage.usable ?? coverage.downloaded ?? 0;
  const percent = number(coverage.coveragePct) ?? 0;
  const status = coverage.status || (percent >= 95 ? 'good' : percent >= 80 ? 'degraded' : 'poor');
  const missingSymbols = (coverage.missingSymbols || []).slice(0, 8);
  setHtml('coverageBanner', `
    <div class="coverage-copy"><strong>採点可能 ${escapeHtml(usable)} / ${escapeHtml(coverage.requested ?? 0)}</strong><span>${format(percent, '%')} ・ 採点不可 ${escapeHtml(coverage.missing ?? 0)}銘柄</span></div>
    <div class="coverage-meter" aria-label="採点可能データ率"><i class="${escapeHtml(status)}" style="width:${Math.max(0, Math.min(100, percent))}%"></i></div>
    ${missingSymbols.length ? `<small class="coverage-missing">採点不可: ${missingSymbols.map(escapeHtml).join(' / ')}</small>` : ''}
  `);
  const fresh = freshnessInfo();
  setHtml('freshnessBadge', `<span class="freshness-dot ${fresh.className}"></span>${escapeHtml(fresh.label)}`);
}

export function renderMarketSummary() {
  const summary = state.report.marketSummary || {};
  setHtml('marketSummary', ['JP', 'US'].map(market => {
    const row = summary[market] || {};
    const active = state.activeMarket === 'all' || state.activeMarket === market;
    return `
      <article class="market-card ${active ? 'active-market' : 'muted-market'}">
        <div><span>${marketLabel(market)}</span><strong>${row.selectedRows ?? 0}</strong></div>
        <dl>
          <div><dt>基準日</dt><dd>${formatDate(row.asOf)}</dd></div>
          <div><dt>採点可能率</dt><dd>${format(row.coveragePct, '%')}</dd></div>
          <div><dt>S/A/B</dt><dd>${row.sRank ?? 0}/${row.aRank ?? 0}/${row.bRank ?? 0}</dd></div>
          <div><dt>履歴十分</dt><dd>${row.fullHistoryRows ?? 0}</dd></div>
          <div><dt>平均点</dt><dd>${format(row.averageScore)}</dd></div>
          <div><dt>欠損</dt><dd>${row.missingRows ?? 0}</dd></div>
        </dl>
      </article>`;
  }).join(''));
}

export function renderMethodology() {
  const methodology = state.report.methodology || {};
  const components = methodology.scoreComponents || {};
  const limitations = methodology.limitations || [];
  setHtml('methodologyText', `
    <p><strong>${escapeHtml(methodology.model || 'Technical SEPA/VCP')}</strong>。S/A/B/Cはテクニカル一次判定です。テーマ人気は総合点に加算せず、テクニカル優位性と分離しています。</p>
    <div class="method-chips">${Object.entries(components).map(([key, score]) => `<span>${escapeHtml(key)} ${escapeHtml(score)}点</span>`).join('')}</div>
    <ul>${limitations.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>`);
}

function actionBucket(title, subtitle, rows, tone) {
  const content = rows.length ? rows.slice(0, 5).map(item => {
    const metrics = item.metrics || {};
    return `
      <button class="action-row" type="button" data-focus-symbol="${escapeHtml(item.symbol)}">
        <span class="rank-dot ${rankClass(item.rank)}">${escapeHtml(item.rank)}</span>
        <span class="action-symbol"><strong>${escapeHtml(item.symbol)}</strong><small>${escapeHtml(item.name)}</small></span>
        <span class="action-stats">RS ${format(metrics.rsRating)}<br>点 ${format(item.score)}</span>
      </button>`;
  }).join('') : '<p class="empty compact-empty">該当なし</p>';
  return `<article class="action-bucket ${tone}"><header><div><h3>${escapeHtml(title)}</h3><p>${escapeHtml(subtitle)}</p></div><strong>${rows.length}</strong></header>${content}</article>`;
}

export function renderActionBoard() {
  const candidates = (state.report.candidates || []).filter(inActiveMarket);
  const marketContext = document.getElementById('actionMarketLabel');
  if (marketContext) marketContext.textContent = activeMarketLabel();
  const byScore = rows => [...rows].sort((a, b) => (number(b.score) ?? 0) - (number(a.score) ?? 0));
  const rows = type => byScore(candidates.filter(item => item.setupType === type && ['S', 'A', 'B'].includes(item.rank)));
  setHtml('actionBoard', [
    actionBucket('ブレイク確認', '出来高を伴いピボット上', rows('breakout_ready'), 'bucket-strong'),
    actionBucket('VCP待機', 'ピボット5%以内・収縮確認', rows('vcp_ready'), 'bucket-good'),
    actionBucket('押し目確認', '20日線・50日線付近', rows('pullback_ready'), 'bucket-neutral'),
    actionBucket('追いかけ禁止', '買い場を超過', byScore(candidates.filter(item => item.setupType === 'extended')), 'bucket-warn')
  ].join(''));
}

function sectorRows() {
  let rows = [...(state.report.sectorStrength || [])];
  if (state.activeMarket !== 'all') rows = rows.filter(row => row.market === state.activeMarket);
  const confidence = valueOf('sectorConfidenceFilter') || 'all';
  if (confidence === 'high') rows = rows.filter(row => row.confidence === 'high');
  if (confidence === 'medium') rows = rows.filter(row => ['high', 'medium'].includes(row.confidence));
  const sort = valueOf('sectorSortSelect') || 'rs';
  rows.sort((a, b) => {
    if (sort === 'change5d') return (number(b.change5d) ?? number(b.change1d) ?? -999) - (number(a.change5d) ?? number(a.change1d) ?? -999);
    if (sort === 'breadth') return (number(b.breadth50) ?? 0) - (number(a.breadth50) ?? 0);
    if (sort === 'ret60') return (number(b.ret60) ?? -999) - (number(a.ret60) ?? -999);
    if (sort === 'turnover') return (number(b.turnover) ?? 0) - (number(a.turnover) ?? 0);
    return (number(b.rsScore) ?? 0) - (number(a.rsScore) ?? 0);
  });
  return rows;
}

export function renderSectors() {
  const rows = sectorRows();
  const leadership = rows.filter(row => (number(row.rsScore) ?? 0) >= 65).slice(0, 8);
  setHtml('sectorLeadership', leadership.map(row => `
    <button class="leadership-pill ${scoreTone(row.rsScore)}" type="button" data-open-sector="${escapeHtml(row.key)}">
      <strong>${escapeHtml(row.name || row.sector || row.theme)}</strong><span>${marketLabel(row.market)} RS ${format(row.rsScore)} / 5日 ${changeText(row.change5d)}</span>
    </button>`).join('') || '<p class="empty compact-empty">強いセクターがありません。</p>');

  setHtml('sectorGrid', rows.slice(0, 24).map(row => {
    const open = state.expandedSector === row.key;
    const label = row.name || row.sector || row.theme || '未分類';
    const leaderRows = (row.leaders || []).slice(0, 8).map((item, index) => `
      <tr><td>${index + 1}</td><td><strong>${escapeHtml(item.symbol)}</strong><br><small>${escapeHtml(item.name)}</small></td><td>${escapeHtml(item.rank || '-')}</td><td>${format(item.metrics?.rsRating)}</td><td>${format(item.score)}</td><td>${setupLabel(item.setupType)}</td><td>${format(item.metrics?.distanceToPivotPct, '%')}</td></tr>`).join('');
    const detail = open ? `
      <div class="sector-detail"><div class="sector-detail-head"><p>構成 ${row.count}銘柄 / 50日線上 ${format(row.breadth50, '%')} / 200日線上 ${format(row.breadth200, '%')}</p><button type="button" data-filter-sector="${escapeHtml(label)}" data-filter-market="${escapeHtml(row.market)}">候補を表示</button></div><div class="table-wrap"><table><thead><tr><th>#</th><th>銘柄</th><th>R</th><th>RS</th><th>点</th><th>型</th><th>Pivot差</th></tr></thead><tbody>${leaderRows}</tbody></table></div></div>` : '';
    return `
      <article class="sector-card ${open ? 'open' : ''}">
        <button class="sector-toggle" type="button" data-open-sector="${escapeHtml(row.key)}"><div class="sector-title-block"><span>${marketLabel(row.market)} ・ ${confidenceLabel(row.confidence)} ・ ${phaseLabel(row.phase)}</span><strong>${escapeHtml(label)}</strong></div><div class="sector-score ${scoreTone(row.rsScore)}"><b>${format(row.rsScore)}</b><small>RS</small></div></button>
        <div class="sector-body"><div class="sector-change"><span class="${changeClass(row.change1d)}">1日 ${changeText(row.change1d)}</span><span class="${changeClass(row.change5d)}">5日 ${changeText(row.change5d)}</span></div>${sparkline(row.sparkline)}</div>
        <div class="sector-meta"><span>RS20 ${changeText(row.rs20, '%')}</span><span>RS60 ${changeText(row.rs60, '%')}</span><span>RS120 ${changeText(row.rs120, '%')}</span><span>50MA上 ${format(row.breadth50, '%')}</span><span>S/A ${row.sCount ?? 0}/${row.aCount ?? 0}</span><span>実行 ${row.actionable ?? 0}</span></div>${detail}
      </article>`;
  }).join('') || '<p class="empty">セクターデータがありません。</p>');

  setHtml('sectorTable', `<table><thead><tr><th>市場</th><th>セクター</th><th>RS</th><th>1日</th><th>5日</th><th>RS20</th><th>RS60</th><th>RS120</th><th>50MA上</th><th>銘柄数</th><th>S/A</th><th>売買代金</th></tr></thead><tbody>${rows.map(row => `
    <tr><td>${marketLabel(row.market)}</td><td>${escapeHtml(row.name || row.sector || row.theme)}</td><td>${format(row.rsScore)}</td><td class="${changeClass(row.change1d)}">${changeText(row.change1d)}</td><td class="${changeClass(row.change5d)}">${changeText(row.change5d)}</td><td>${changeText(row.rs20, '%')}</td><td>${changeText(row.rs60, '%')}</td><td>${changeText(row.rs120, '%')}</td><td>${format(row.breadth50, '%')}</td><td>${row.count ?? 0}</td><td>${row.sCount ?? 0}/${row.aCount ?? 0}</td><td>${money(row.turnover)}</td></tr>`).join('')}</tbody></table>`);
}
