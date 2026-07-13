import { state, $, formatDate, formatTimestamp, setText, setHtml, setQuickFilter } from './dashboard-utils.js?v=20260714-v5-1';
import { renderSummary, renderCoverage, renderMarketSummary, renderMethodology, renderActionBoard, renderSectors } from './dashboard-sectors.js?v=20260714-v5-1';
import { renderCandidates, renderRiskTable, renderThemes } from './dashboard-candidate-list.js?v=20260714-v5-1';
import { renderTracking, focusSymbol, filterSector } from './dashboard-tracking.js?v=20260714-v5-1';
import { setupPageNavigation } from './dashboard-navigation.js?v=20260714-v5-1';

const MARKET_STORAGE_KEY = 'vcp-sepa-active-market-v1';
const VALID_MARKETS = new Set(['all', 'JP', 'US']);

function renderAll() {
  const report = state.report;
  const asOf = report.marketDataAsOf || {};
  const buildLabel = report.rescoredFromExistingData ? '既存終値データを再採点' : '価格履歴を新規取得';
  setText(
    'reportStatus',
    `データ基準 日本株 ${formatDate(asOf.JP)} / 米国株 ${formatDate(asOf.US)} ・ 生成 ${formatTimestamp(report.generatedAt)} ・ ${buildLabel} ・ ${report.screeningMode || '-'} ・ Technical SEPA/VCP v${report.schemaVersion || 1}`
  );
  renderCoverage();
  renderSummary();
  renderMarketSummary();
  renderMethodology();
  renderActionBoard();
  renderSectors();
  renderCandidates();
  renderRiskTable();
  renderThemes();
  renderTracking();
}

function renderMarketDependentViews() {
  renderCoverage();
  renderSummary();
  renderMarketSummary();
  renderActionBoard();
  renderSectors();
  renderCandidates();
  renderRiskTable();
  renderThemes();
  renderTracking();
}

function syncMarketControls() {
  document.querySelectorAll('[data-market-switch]').forEach(button => {
    const active = button.dataset.marketSwitch === state.activeMarket;
    button.classList.toggle('active', active);
    button.setAttribute('aria-pressed', String(active));
  });
  document.querySelectorAll('[data-sector-market]').forEach(button => {
    const active = button.dataset.sectorMarket === state.activeMarket;
    button.classList.toggle('active', active);
    button.setAttribute('aria-selected', String(active));
  });
  const marketFilter = $('marketFilter');
  if (marketFilter) marketFilter.value = state.activeMarket;
}

function setActiveMarket(market, options = {}) {
  const normalized = VALID_MARKETS.has(market) ? market : 'all';
  const changed = state.activeMarket !== normalized;
  state.activeMarket = normalized;
  state.sectorMarket = normalized;
  state.expandedSector = '';
  state.visibleLimit = 40;
  syncMarketControls();
  if (options.persist !== false) {
    try { localStorage.setItem(MARKET_STORAGE_KEY, normalized); } catch {}
  }
  if (changed || options.forceRender) renderMarketDependentViews();
}

async function loadReport() {
  setText('reportStatus', 'レポートを再読み込み中...');
  const reload = $('reloadReport');
  if (reload) reload.disabled = true;
  try {
    const response = await fetch(`reports/latest.json?ts=${Date.now()}`, { cache: 'no-store' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    if (!payload || !Array.isArray(payload.candidates)) throw new Error('invalid schema');
    state.report = payload;
    state.visibleLimit = 40;
    renderAll();
  } catch (error) {
    setText('reportStatus', `レポート読込失敗: ${error.message}。Actionsの最新実行とreports/latest.jsonを確認してください。`);
    setHtml('coverageBanner', '<div class="fatal-banner">有効なレポートがありません。</div>');
  } finally {
    if (reload) reload.disabled = false;
  }
}

function bindControls() {
  ['searchInput', 'rankFilter', 'setupFilter', 'rsFilter', 'atrFilter', 'sortSelect'].forEach(id => {
    const element = $(id);
    if (!element) return;
    const handler = () => {
      state.visibleLimit = 40;
      renderCandidates();
      renderRiskTable();
    };
    element.addEventListener('input', handler);
    element.addEventListener('change', handler);
  });

  $('marketFilter')?.addEventListener('change', event => setActiveMarket(event.target.value));
  document.querySelectorAll('[data-market-switch]').forEach(button => button.addEventListener('click', () => setActiveMarket(button.dataset.marketSwitch || 'all')));
  document.querySelectorAll('[data-sector-market]').forEach(button => button.addEventListener('click', () => setActiveMarket(button.dataset.sectorMarket || 'all')));

  ['sectorSortSelect', 'sectorConfidenceFilter'].forEach(id => $(id)?.addEventListener('change', renderSectors));
  $('reloadReport')?.addEventListener('click', loadReport);
  $('loadMore')?.addEventListener('click', () => {
    state.visibleLimit += 40;
    renderCandidates();
  });

  document.addEventListener('click', event => {
    const quick = event.target.closest('[data-quick-filter]');
    if (quick) {
      setQuickFilter(quick.dataset.quickFilter || '');
      renderCandidates();
      renderRiskTable();
      return;
    }
    const sector = event.target.closest('[data-open-sector]');
    if (sector) {
      const key = sector.dataset.openSector || '';
      state.expandedSector = state.expandedSector === key ? '' : key;
      renderSectors();
      return;
    }
    const filter = event.target.closest('[data-filter-sector]');
    if (filter) {
      setActiveMarket(filter.dataset.filterMarket || 'all');
      filterSector(filter.dataset.filterSector || '', filter.dataset.filterMarket || 'all');
      return;
    }
    const focus = event.target.closest('[data-focus-symbol]');
    if (focus) focusSymbol(focus.dataset.focusSymbol || '');
  });

  const note = $('dailyNote');
  if (note) {
    const key = 'vcp-sepa-dashboard-note-v3';
    note.value = localStorage.getItem(key) || '';
    $('saveNote')?.addEventListener('click', () => {
      localStorage.setItem(key, note.value);
      const button = $('saveNote');
      if (!button) return;
      const original = button.textContent;
      button.textContent = '保存済み';
      setTimeout(() => { button.textContent = original; }, 1200);
    });
    $('clearNote')?.addEventListener('click', () => {
      note.value = '';
      localStorage.removeItem(key);
    });
  }
}

function init() {
  setupPageNavigation();
  bindControls();
  let savedMarket = 'all';
  try { savedMarket = localStorage.getItem(MARKET_STORAGE_KEY) || 'all'; } catch {}
  setActiveMarket(savedMarket, { persist: false });
  loadReport();
}

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
else init();
