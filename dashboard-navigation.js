export const PAGE_ORDER = ['overview', 'candidates', 'sectors', 'plan', 'review'];

export const PAGE_LABELS = {
  overview: '概況',
  candidates: '候補銘柄',
  sectors: 'セクター',
  plan: '売買計画',
  review: '記録'
};

const HASH_TO_PAGE = {
  '#overview': 'overview',
  '#command-center': 'overview',
  '#action-board': 'overview',
  '#candidates': 'candidates',
  '#candidate-finder': 'candidates',
  '#sector-strength': 'sectors',
  '#sectors': 'sectors',
  '#risk-plan': 'plan',
  '#theme-rankings': 'plan',
  '#plan': 'plan',
  '#tracking': 'review',
  '#notes': 'review',
  '#review': 'review'
};

export function pageFromHash(hash) {
  return HASH_TO_PAGE[String(hash || '').toLowerCase()] || 'overview';
}

export function pageIndexFromScroll(scrollLeft, viewportWidth, pageCount = PAGE_ORDER.length) {
  const width = Number(viewportWidth);
  const count = Math.max(1, Number(pageCount) || 1);
  if (!Number.isFinite(width) || width <= 0) return 0;
  const raw = Math.round((Number(scrollLeft) || 0) / width);
  return Math.max(0, Math.min(count - 1, raw));
}

export function setupPageNavigation() {
  const rail = document.getElementById('pageRail');
  if (!rail) return { goToPage: () => {} };

  const pages = PAGE_ORDER.map(page => rail.querySelector(`[data-page="${page}"]`)).filter(Boolean);
  const buttons = [...document.querySelectorAll('[data-page-target]')];
  const label = document.getElementById('activePageLabel');
  const position = document.getElementById('pagePosition');
  const prefersReducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  let activePage = 'overview';
  let scrollFrame = 0;

  function syncActivePage(page, updateHistory = true) {
    if (!PAGE_ORDER.includes(page) || page === activePage && document.body.dataset.activePage === page) return;
    activePage = page;
    document.body.dataset.activePage = page;
    pages.forEach(panel => panel.classList.toggle('active', panel.dataset.page === page));
    buttons.forEach(button => {
      const active = button.dataset.pageTarget === page;
      button.classList.toggle('active', active);
      if (active) button.setAttribute('aria-current', 'page');
      else button.removeAttribute('aria-current');
    });
    document.querySelectorAll('[data-page-dot]').forEach(dot => dot.classList.toggle('active', dot.dataset.pageDot === page));
    if (label) label.textContent = PAGE_LABELS[page];
    if (position) position.textContent = `${PAGE_ORDER.indexOf(page) + 1} / ${PAGE_ORDER.length}`;
    if (updateHistory && history.replaceState) history.replaceState(null, '', `#${page}`);
  }

  function goToPage(page, options = {}) {
    const normalized = PAGE_ORDER.includes(page) ? page : 'overview';
    const index = PAGE_ORDER.indexOf(normalized);
    const panel = pages[index];
    if (!panel) return;
    const behavior = options.behavior || (prefersReducedMotion ? 'auto' : 'smooth');
    rail.scrollTo({ left: panel.offsetLeft, top: 0, behavior });
    if (options.resetScroll) panel.scrollTo({ top: 0, behavior });
    syncActivePage(normalized, options.updateHistory !== false);
  }

  buttons.forEach(button => {
    button.addEventListener('click', () => goToPage(button.dataset.pageTarget || 'overview'));
    button.addEventListener('keydown', event => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      let index = PAGE_ORDER.indexOf(button.dataset.pageTarget || activePage);
      if (event.key === 'ArrowLeft') index = Math.max(0, index - 1);
      if (event.key === 'ArrowRight') index = Math.min(PAGE_ORDER.length - 1, index + 1);
      if (event.key === 'Home') index = 0;
      if (event.key === 'End') index = PAGE_ORDER.length - 1;
      const targetPage = PAGE_ORDER[index];
      goToPage(targetPage);
      buttons.find(item => item.dataset.pageTarget === targetPage)?.focus();
    });
  });

  rail.addEventListener('scroll', () => {
    if (scrollFrame) return;
    scrollFrame = requestAnimationFrame(() => {
      scrollFrame = 0;
      const page = PAGE_ORDER[pageIndexFromScroll(rail.scrollLeft, rail.clientWidth, pages.length)];
      if (page) syncActivePage(page);
    });
  }, { passive: true });

  window.addEventListener('resize', () => goToPage(activePage, { behavior: 'auto', updateHistory: false }));
  window.addEventListener('dashboard:navigate', event => {
    goToPage(event.detail?.page || 'overview', { resetScroll: Boolean(event.detail?.resetScroll) });
  });

  activePage = '';
  const initialPage = pageFromHash(location.hash);
  requestAnimationFrame(() => goToPage(initialPage, { behavior: 'auto', updateHistory: false }));
  return { goToPage };
}
