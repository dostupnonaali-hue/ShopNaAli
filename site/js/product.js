/* Product detail shared by Ukrainian and Polish pages. */
(function () {
  'use strict';
  const pl = document.documentElement.lang === 'pl';
  const locale = pl ? 'pl-PL' : 'uk-UA';
  const t = (uk, po) => pl ? po : uk;
  const el = id => document.getElementById(id);
  let rates = { USD: 4.05, UAH: 0.098 };
  const placeholder = 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400"><rect width="400" height="400" fill="#e9ece6"/><path d="M150 160h100l8 110H142l8-110Zm30 0v-20a20 20 0 0 1 40 0v20" fill="none" stroke="#64715e" stroke-width="4"/></svg>');
  async function fetchJSON(url) {
    const control = new AbortController();
    const timeout = setTimeout(() => control.abort(), 8000);
    try {
      const response = await fetch(url, { signal: control.signal });
      if (!response.ok) throw new Error('HTTP ' + response.status);
      return await response.json();
    } finally { clearTimeout(timeout); }
  }
  async function loadRates() {
    if (!pl) return;
    try {
      const data = await fetchJSON('https://api.exchangerate-api.com/v4/latest/USD');
      if (Number(data.rates?.PLN) > 0) rates.USD = data.rates.PLN;
      if (Number(data.rates?.PLN) > 0 && Number(data.rates?.UAH) > 0) rates.UAH = data.rates.PLN / data.rates.UAH;
    } catch (_) { /* Keep the existing approximate PLN rates when the service is unavailable. */ }
  }
  function money(value, currency) {
    if (pl) return new Intl.NumberFormat(locale, { style: 'currency', currency: 'PLN' }).format(value * (currency === 'UAH' ? rates.UAH : currency === 'PLN' ? 1 : rates.USD));
    return new Intl.NumberFormat(locale, { style: 'currency', currency: ['UAH','USD','PLN','EUR'].includes(currency) ? currency : 'USD' }).format(value);
  }
  function purchaseURL(value) {
    try { const u = new URL(value); return ['https:', 'http:'].includes(u.protocol) ? u.href : null; } catch (_) { return null; }
  }
  function renderProduct(product) {
    const title = (pl && product.title_pl) || product.title;
    document.title = title + ' — ShopDoBaksa';
    el('pageMeta').content = product.description || title;
    el('ogTitle').content = document.title;
    el('ogDesc').content = title;
    el('ogImage').content = product.image || '';
    el('productTitle').textContent = title;
    const image = el('productImage');
    image.alt = title;
    image.onerror = function () { this.onerror = null; this.src = placeholder; };
    image.src = product.image || placeholder;
    const price = Number(product.price);
    const currency = product.currency || 'USD';
    const priceText = price > 0 ? money(price, currency) : t('Ціну уточнюйте', 'Sprawdź cenę');
    el('productPrice').textContent = priceText;
    if (Number(product.price_old) > price && price > 0) {
      el('productPriceOld').textContent = money(Number(product.price_old), currency);
      el('productDiscount').textContent = '−' + Math.round((1 - price / product.price_old) * 100) + '%';
      el('productDiscount').style.display = 'inline-block';
    }
    if (product.price_note) { el('productPriceNote').textContent = product.price_note; el('productPriceNote').hidden = false; }
    const promos = String(product.promo_text || '').split(',').map(v => v.trim()).filter(Boolean);
    if (promos.length) {
      const box = el('productPromo');
      box.className = 'product-page__promos';
      box.style.display = 'flex';
      promos.forEach(code => {
        const button = document.createElement('button');
        button.type = 'button'; button.className = 'product-page__promo'; button.dataset.copyCode = code;
        button.textContent = code + ' ⧉'; button.setAttribute('aria-label', t('Скопіювати промокод ', 'Kopiuj kod ') + code);
        box.appendChild(button);
      });
    }
    el('productRating').textContent = product.rating ? '★ ' + Number(product.rating).toFixed(1) : '—';
    el('productOrders').textContent = product.orders ? Number(product.orders).toLocaleString(locale) : '—';
    el('productDescription').textContent = product.description || '';
    el('productDescription').hidden = !product.description;
    const href = purchaseURL(product.affiliate_link) || purchaseURL(product.link);
    if (href) {
      el('buyButton').href = href; el('buyButton').hidden = false;
      el('mobileBuy').href = href; el('mobilePrice').textContent = priceText; el('mobilePurchase').hidden = false;
    }
  }
  function showError(message) {
    el('productTitle').textContent = message;
    el('productImage').src = placeholder;
    el('productImage').alt = '';
    el('productPrice').textContent = '—';
    el('productDescription').textContent = t('Повернись до каталогу та обери іншу знахідку.', 'Wróć do katalogu i wybierz inną okazję.');
    document.querySelector('.price-context').hidden = true;
    document.querySelector('.product-page__info').hidden = true;
  }
  async function init() {
    const id = new URLSearchParams(location.search).get('id');
    if (!id) { showError(t('Обери товар у каталозі', 'Wybierz produkt w katalogu')); return; }
    try {
      const [data] = await Promise.all([fetchJSON((pl ? '../' : '') + 'data/products.json?v=' + Math.floor(Date.now() / 300000)), loadRates()]);
      const products = data.products || data;
      const product = products.find(p => String(p.id) === id);
      if (!product) { showError(t('Цю знахідку вже прибрали з каталогу', 'Ta okazja nie jest już w katalogu')); return; }
      renderProduct(product);
    } catch (_) { showError(t('Не вдалося завантажити товар', 'Nie udało się wczytać produktu')); }
  }
  document.addEventListener('DOMContentLoaded', init);
})();
