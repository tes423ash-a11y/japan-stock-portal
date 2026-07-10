import { state, $, setText, setHtml, setQuickFilter } from './dashboard-utils.js';
import { renderSummary, renderCoverage, renderMarketSummary, renderMethodology, renderActionBoard, renderSectors } from './dashboard-sectors.js';
import { renderCandidates, renderRiskTable, renderThemes } from './dashboard-candidate-list.js';
import { renderTracking, focusSymbol, filterSector } from './dashboard-tracking.js';

function renderAll() {
  const report = state.report;
  setText('reportStatus', `生成 ${report.generatedAt || '不明'} / ${report.screeningMode || '-'} / Technical SEPA/VCP v${report.schemaVersion || 1}`);
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
  ['searchInput', 'marketFilter', 'rankFilter', 'setupFilter', 'rsFilter', 'atrFilter', 'sortSelect'].forEach(id => {
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

  ['sectorSortSelect', 'sectorConfidenceFilter'].forEach(id => $(id)?.addEventListener('change', renderSectors));
  $('reloadReport')?.addEventListener('click', loadReport);
  $('loadMore')?.addEventListener('click', () => {
    state.visibleLimit += 40;
    renderCandidates();
  });

  document.querySelectorAll('[data-sector-market]').forEach(button => button.addEventListener('click', () => {
    state.sectorMarket = button.dataset.sectorMarket || 'all';
    state.expandedSector = '';
    document.querySelectorAll('[data-sector-market]').forEach(item => item.classList.toggle('active', item === button));
    renderSectors();
  }));

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
  bindControls();
  loadReport();
}

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
else init();
