// ==============================
// 左上ハンバーガーメニュー
// 各セクションへスムーズ移動し、移動先を一瞬強調します。
// ==============================

(function initSideMenu() {
  const menuItems = [
    { label: "ホーム / 市況", target: "home", note: "市況リンク" },
    { label: "銘柄コード検索", target: "stock-search", note: "主要サイトへ" },
    { label: "銘柄追加・編集", target: "stock-manager", note: "保有・監視管理" },
    { label: "ミネルヴィニSEPAスクリーナー", target: "sepa-screener", note: "SEPA採点" },
    { label: "日本株スイングスクリーナー", target: "swing-screener", note: "短期候補抽出" },
    { label: "テーマ別ウォッチリスト", target: "watchlist", note: "テーマ監視" },
    { label: "投資メモ", target: "memo-section", note: "日々のメモ" },
    { label: "TradingViewウィジェット枠", target: "tradingview-section", note: "チャート枠" },
    { label: "使い方", target: "how-to-use", note: "操作ガイド" }
  ];

  const button = document.createElement("button");
  button.className = "menu-toggle";
  button.type = "button";
  button.setAttribute("aria-label", "メニューを開く");
  button.setAttribute("aria-expanded", "false");
  button.textContent = "☰";

  const overlay = document.createElement("div");
  overlay.className = "side-overlay";
  overlay.hidden = true;

  const menu = document.createElement("aside");
  menu.className = "side-menu";
  menu.setAttribute("aria-label", "サイト内メニュー");
  menu.setAttribute("aria-hidden", "true");
  menu.innerHTML = `
    <div class="side-menu-header">
      <div>
        <p class="side-menu-title">投資司令室メニュー</p>
        <p class="side-menu-subtitle">見たい機能へすぐ移動</p>
      </div>
      <button type="button" class="side-menu-close" aria-label="メニューを閉じる">×</button>
    </div>
    <nav class="side-menu-nav">
      ${menuItems.map(item => `<a class="side-menu-link" href="#${item.target}" data-target="${item.target}">${item.label}<span>${item.note}</span></a>`).join("")}
    </nav>
  `;

  document.body.prepend(overlay);
  document.body.prepend(menu);
  document.body.prepend(button);

  const closeButton = menu.querySelector(".side-menu-close");
  const links = menu.querySelectorAll(".side-menu-link");

  function openMenu() {
    overlay.hidden = false;
    requestAnimationFrame(() => {
      overlay.classList.add("open");
      menu.classList.add("open");
    });
    button.setAttribute("aria-expanded", "true");
    button.setAttribute("aria-label", "メニューを閉じる");
    menu.setAttribute("aria-hidden", "false");
    closeButton.focus();
  }

  function closeMenu() {
    overlay.classList.remove("open");
    menu.classList.remove("open");
    button.setAttribute("aria-expanded", "false");
    button.setAttribute("aria-label", "メニューを開く");
    menu.setAttribute("aria-hidden", "true");
    window.setTimeout(() => {
      if (!overlay.classList.contains("open")) overlay.hidden = true;
    }, 240);
  }

  function highlightSection(section) {
    section.classList.remove("section-highlight");
    void section.offsetWidth;
    section.classList.add("section-highlight");
    window.setTimeout(() => section.classList.remove("section-highlight"), 1200);
  }

  function moveToSection(targetId) {
    const section = document.getElementById(targetId);
    if (!section) return;
    closeMenu();
    window.setTimeout(() => {
      section.scrollIntoView({ behavior: "smooth", block: "start" });
      highlightSection(section);
    }, 120);
  }

  button.addEventListener("click", () => {
    const isOpen = button.getAttribute("aria-expanded") === "true";
    isOpen ? closeMenu() : openMenu();
  });

  closeButton.addEventListener("click", closeMenu);
  overlay.addEventListener("click", closeMenu);

  links.forEach(link => {
    link.addEventListener("click", event => {
      event.preventDefault();
      moveToSection(link.dataset.target);
    });
  });

  document.addEventListener("keydown", event => {
    if (event.key === "Escape") closeMenu();
  });
})();
