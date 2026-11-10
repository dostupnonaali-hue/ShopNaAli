/* Current promo discoveries; dates indicate last seen, not verified validity. */
(function () {
  'use strict';
  const pl = document.documentElement.lang === 'pl';
  const container = document.getElementById('parserPromos');
  async function init() {
    try {
      const response = await fetch((pl ? '../' : '') + 'data/promos.json?v=' + Math.floor(Date.now() / 300000));
      if (!response.ok) throw new Error('HTTP ' + response.status);
      const data = await response.json();
      const promos = (data.promos || []).slice().sort((a, b) => String(b.last_seen || '').localeCompare(String(a.last_seen || '')));
      document.getElementById('promoStatsCount').textContent = promos.length;
      if (!promos.length) { container.textContent = pl ? 'Lista kodów jest na razie pusta.' : 'Список промокодів поки порожній.'; return; }
      const fragment = document.createDocumentFragment();
      promos.forEach(promo => {
        const card = document.createElement('article');
        card.className = 'promo-card promo-card--parser';
        const top = document.createElement('div'); top.className = 'promo-card__top';
        const caption = document.createElement('span'); caption.className = 'promo-card__badge-pop'; caption.textContent = pl ? 'Kod rabatowy' : 'Промокод';
        const date = document.createElement('span'); date.className = 'promo-card__date';
        const parsed = new Date(promo.last_seen);
        date.textContent = !Number.isNaN(parsed.valueOf()) ? parsed.toLocaleDateString(pl ? 'pl-PL' : 'uk-UA') : '';
        top.append(caption, date);
        const button = document.createElement('button'); button.type = 'button'; button.className = 'promo-card__code-wrap'; button.dataset.copyCode = promo.code;
        button.setAttribute('aria-label', (pl ? 'Kopiuj kod ' : 'Скопіювати промокод ') + promo.code);
        const code = document.createElement('span'); code.className = 'promo-card__code'; code.textContent = promo.code;
        const copy = document.createElement('span'); copy.className = 'promo-card__copy'; copy.textContent = pl ? 'Kopiuj' : 'Копіювати';
        button.append(code, copy); card.append(top, button); fragment.append(card);
      });
      container.replaceChildren(fragment);
    } catch (_) { container.textContent = pl ? 'Nie udało się wczytać kodów. Odśwież stronę.' : 'Не вдалося завантажити промокоди. Онови сторінку.'; }
  }
  document.addEventListener('DOMContentLoaded', init);
})();
