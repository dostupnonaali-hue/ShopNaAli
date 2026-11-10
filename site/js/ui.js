/* Shared navigation and accessible page interactions. */
(function () {
  'use strict';
  const pl = document.documentElement.lang === 'pl';
  const toggle = document.getElementById('menuToggle');
  const menu = document.getElementById('siteMenu');
  const backdrop = document.getElementById('menuBackdrop');
  const close = document.getElementById('menuClose');
  let restoreFocus = null;
  const background = Array.from(document.body.children).filter(el => el !== menu && el !== backdrop && el.tagName !== 'SCRIPT');
  const inertBefore = new Map();
  function setMenu(open) {
    if (open) {
      restoreFocus = document.activeElement;
      background.forEach(el => { inertBefore.set(el, el.inert); el.inert = true; });
    } else {
      background.forEach(el => { el.inert = inertBefore.get(el) || false; });
      inertBefore.clear();
    }
    menu.hidden = !open;
    backdrop.hidden = !open;
    toggle.setAttribute('aria-expanded', String(open));
    document.body.classList.toggle('menu-open', open);
    if (open) close.focus(); else if (restoreFocus) restoreFocus.focus();
  }
  toggle.addEventListener('click', () => setMenu(menu.hidden));
  close.addEventListener('click', () => setMenu(false));
  backdrop.addEventListener('click', () => setMenu(false));
  document.addEventListener('keydown', event => {
    if (menu.hidden) return;
    if (event.key === 'Escape') { event.preventDefault(); setMenu(false); }
    if (event.key === 'Tab') {
      const items = Array.from(menu.querySelectorAll('a[href],button:not([disabled])'));
      const first = items[0], last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
  });
  window.matchMedia('(min-width: 901px)').addEventListener('change', event => { if (event.matches && !menu.hidden) setMenu(false); });

  // Keep the same product or article when switching languages.
  document.querySelectorAll('[data-language]').forEach(link => {
    const url = new URL(link.href);
    const current = new URLSearchParams(location.search);
    for (const key of ['id', 'search']) if (current.has(key)) url.searchParams.set(key, current.get(key));
    if (link.dataset.language === 'uk') url.searchParams.set('lang', 'uk');
    link.href = url.href;
    link.addEventListener('click', () => {
      if (document.querySelector('.site-search').dataset.searchMode === 'local') {
        const query = document.getElementById('searchInput').value.trim();
        if (query) url.searchParams.set('search', query); else url.searchParams.delete('search');
        link.href = url.href;
      }
      try { localStorage.setItem('dobaksa_lang', link.dataset.language); } catch (_) { /* Browsing without storage is supported. */ }
    });
  });
  const search = document.querySelector('.site-search');
  if (search.dataset.searchMode === 'local') {
    search.addEventListener('submit', event => {
      event.preventDefault();
      document.getElementById('searchInput').dispatchEvent(new Event('input', { bubbles: true }));
      const target = document.getElementById('catalog') || document.getElementById('productsGrid');
      if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  }

  const top = document.getElementById('backTop');
  function updateTop() { top.hidden = window.scrollY < 550; }
  window.addEventListener('scroll', updateTop, { passive: true });
  updateTop();
  top.addEventListener('click', () => { window.scrollTo({ top: 0, behavior: 'smooth' }); });

  let toastTimeout;
  function toast(message) {
    const el = document.getElementById('uiToast');
    el.textContent = message;
    el.classList.add('is-visible');
    clearTimeout(toastTimeout);
    toastTimeout = setTimeout(() => el.classList.remove('is-visible'), 3000);
  }
  async function copy(value, message) {
    try { await navigator.clipboard.writeText(value); toast(message); }
    catch (_) { toast(pl ? 'Nie udało się skopiować. Zaznacz i skopiuj tekst ręcznie.' : 'Не вдалося скопіювати. Виділи й скопіюй текст вручну.'); }
  }
  window.copyCode = code => copy(code, pl ? 'Kod skopiowany' : 'Промокод скопійовано');
  document.addEventListener('click', event => {
    const promo = event.target.closest('[data-copy-code]');
    if (promo) window.copyCode(promo.dataset.copyCode);
    if (event.target.closest('[data-copy-url]')) copy(location.href, pl ? 'Link skopiowany' : 'Посилання скопійовано');
  });

  // Native details keep the guide usable without JavaScript.
  const faqSearch = document.getElementById('faqSearch');
  if (faqSearch) {
    const sections = Array.from(document.querySelectorAll('.faq-section'));
    const items = Array.from(document.querySelectorAll('.faq-item'));
    let wasSearching = false;
    function filterGuide() {
      const query = faqSearch.value.trim().toLocaleLowerCase();
      let found = 0;
      items.forEach(item => {
        const match = !query || item.textContent.toLocaleLowerCase().includes(query);
        item.hidden = !match;
        if (query) item.open = match;
        else if (wasSearching) item.open = false;
        if (match) found++;
      });
      wasSearching = Boolean(query);
      sections.forEach(section => { section.hidden = !Array.from(section.querySelectorAll('.faq-item')).some(item => !item.hidden); });
      document.getElementById('faqResultCount').textContent = (pl ? 'Odpowiedzi: ' : 'Відповідей: ') + found;
      document.getElementById('faqEmpty').hidden = found !== 0;
    }
    faqSearch.addEventListener('input', filterGuide);
    filterGuide();
    document.querySelectorAll('.faq-nav__link').forEach(link => link.addEventListener('click', () => {
      faqSearch.value = ''; filterGuide();
      document.querySelectorAll('.faq-nav__link').forEach(el => el.classList.toggle('is-active', el === link));
    }));
  }

  const promoSearch = document.getElementById('promoSearch');
  if (promoSearch) {
    const container = document.getElementById('parserPromos');
    const more = document.getElementById('promoLoadMore');
    const count = document.getElementById('promoResultCount');
    let limit = 18;
    function filterCodes() {
      const cards = Array.from(container.querySelectorAll('.promo-card'));
      const query = promoSearch.value.trim().toLowerCase();
      const matches = cards.filter(card => card.textContent.toLowerCase().includes(query));
      cards.forEach(card => { card.hidden = true; });
      matches.slice(0, limit).forEach(card => { card.hidden = false; });
      more.hidden = matches.length <= limit;
      count.textContent = cards.length ? (pl ? 'Wyświetlono ' : 'Показано ') + Math.min(limit, matches.length) + (pl ? ' z ' : ' з ') + matches.length : '';
      document.getElementById('promoEmpty').hidden = !cards.length || matches.length > 0;
    }
    promoSearch.addEventListener('input', () => { limit = 18; filterCodes(); });
    more.addEventListener('click', () => { limit += 18; filterCodes(); });
    new MutationObserver(filterCodes).observe(container, { childList: true });
    filterCodes();
  }
})();
