(() => {
  const h = 'https:' + '//';
  const domains = {
    yahooJp: 'finance.yahoo.co.jp',
    yahooUs: 'finance.yahoo.com',
    kabutan: 'kabutan.jp',
    minkabu: 'minkabu.jp',
    minkabuUs: 'us.minkabu.jp',
    karauri: 'karauri.net',
    tvJp: 'jp.tradingview.com',
    tvUs: 'www.tradingview.com'
  };

  function symbolFromCard(card) {
    const code = card.querySelector('.candidate-code');
    return (code?.textContent || '').split('/')[0].trim().toUpperCase();
  }

  function linkList(symbol) {
    const isJp = symbol.endsWith('.T');
    const code = symbol.replace('.T', '');
    if (isJp) {
      return [
        ['Yahoo', h + domains.yahooJp + '/quote/' + code + '.T'],
        ['株探', h + domains.kabutan + '/stock/?code=' + code],
        ['みんかぶ', h + domains.minkabu + '/stock/' + code],
        ['karauri', h + domains.karauri + '/' + code + '/'],
        ['TV', h + domains.tvJp + '/symbols/TSE-' + code + '/']
      ];
    }
    return [
      ['Yahoo', h + domains.yahooUs + '/quote/' + symbol],
      ['みんかぶUS', h + domains.minkabuUs + '/stocks/' + symbol],
      ['TV', h + domains.tvUs + '/symbols/' + symbol + '/']
    ];
  }

  function enhance() {
    document.querySelectorAll('.candidate-card').forEach(card => {
      if (card.querySelector('.external-link-row')) return;
      const symbol = symbolFromCard(card);
      if (!symbol) return;
      const row = document.createElement('div');
      row.className = 'card-links external-link-row';
      linkList(symbol).forEach(([label, href]) => {
        const a = document.createElement('a');
        a.href = href;
        a.target = '_blank';
        a.rel = 'noopener noreferrer';
        a.textContent = label;
        row.appendChild(a);
      });
      card.appendChild(row);
    });
  }

  const target = document.getElementById('candidateList') || document.body;
  new MutationObserver(enhance).observe(target, { childList: true, subtree: true });
  window.addEventListener('load', enhance);
  setTimeout(enhance, 1500);
})();
