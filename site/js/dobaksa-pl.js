/**
 * ShopDoBaksa - DoBaksa Page Logic (Polish version)
 * Shows products under $1 from products.json with PLN conversion
 */

(function () {
    'use strict';

    // --- Config ---
    var BATCH_SIZE = 30;

    // --- Exchange rates (fallback values) ---
    var rates = { USD: 4.05, UAH: 0.098 };

    // --- State ---
    var cheapProducts = [];
    var filteredProducts = [];
    var currentPriceFilter = 'all';
    var searchQuery = '';
    var displayCount = BATCH_SIZE;

    // --- DOM ---
    var productsGrid = document.getElementById('productsGrid');
    var searchInput = document.getElementById('searchInput');
    var priceFilters = document.getElementById('priceFilters');
    var statsCheap = document.getElementById('statsCheap');
    var statsMinPrice = document.getElementById('statsMinPrice');

    // --- Init ---
    async function init() {
        showSkeletons(8);
        await Promise.all([loadProducts(), loadExchangeRates()]);
        renderProducts();
        updateStats();
        bindEvents();
    }

    async function loadExchangeRates() {
        try {
            var resp = await fetch('https://api.exchangerate-api.com/v4/latest/USD');
            if (!resp.ok) throw new Error('Rate API error');
            var data = await resp.json();
            if (data && data.rates) {
                rates.USD = data.rates.PLN || rates.USD;
                rates.UAH = (data.rates.PLN / data.rates.UAH) || rates.UAH;
            }
        } catch (e) {
            console.warn('Using fallback exchange rates:', e.message);
        }
    }

    function toPLN(price, currency) {
        if (!price) return 0;
        if (currency === 'UAH') return price * rates.UAH;
        return price * rates.USD;
    }

    // --- Load & Filter Products ---
    async function loadProducts() {
        try {
            var cacheBuster = Math.floor(Date.now() / 300000);
            var response = await fetch('../data/products.json?v=' + cacheBuster);
            if (!response.ok) throw new Error('Failed to load products');
            var data = await response.json();
            var allProducts = data.products || data || [];

            // Filter: USD <= 1 OR UAH <= 50
            cheapProducts = allProducts.filter(function(p) {
                if (!p.price || p.price <= 0) return false;
                if (p.currency === 'UAH') return p.price <= 50;
                return p.price <= 1;
            });

            cheapProducts.sort(function(a, b) {
                var dateA = a.added_at || '';
                var dateB = b.added_at || '';
                return dateB.localeCompare(dateA);
            });

            filteredProducts = cheapProducts.slice();
        } catch (err) {
            console.warn('Products not loaded:', err.message);
            cheapProducts = [];
            filteredProducts = [];
        }
    }

    function getTitle(product) {
        return product.title_pl || product.title || '';
    }

    // --- Render ---
    function renderProducts() {
        if (filteredProducts.length === 0) {
            productsGrid.innerHTML = '<div class="empty-state">' +
                '<div class="empty-state__icon">\uD83E\uDE99</div>' +
                '<h3 class="empty-state__title">Brak produkt\u00F3w</h3>' +
                '<p class="empty-state__text">Nowe znaleziska do 1$ pojawi\u0105 si\u0119 automatycznie \u2014 wchod\u017A cz\u0119\u015Bciej!</p>' +
                '</div>';
            removeLoadMore();
            return;
        }

        var visible = filteredProducts.slice(0, displayCount);

        productsGrid.innerHTML = visible.map(function(product, index) {
            var badgeHTML = product.badge
                ? '<span class="product-card__badge product-card__badge--' + product.badge + '">' + getBadgeText(product.badge) + '</span>'
                : '';

            var ratingStars = '\u2B50'.repeat(Math.round(product.rating || 0));
            var pricePLN = toPLN(product.price, product.currency);
            var priceOldPLN = product.price_old ? toPLN(product.price_old, product.currency) : 0;
            var priceOld = priceOldPLN
                ? '<span class="product-card__price-old">' + priceOldPLN.toFixed(2) + ' z\u0142</span>'
                : '';

            var imgFallback = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0naHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmcnIHdpZHRoPSczMDAnIGhlaWdodD0nMzAwJyB2aWV3Qm94PScwIDAgMzAwIDMwMCc+PHJlY3QgZmlsbD0nIzEyMTIxYScgd2lkdGg9JzMwMCcgaGVpZ2h0PSczMDAnLz48dGV4dCBmaWxsPScjNjA2MDcwJyBmb250LWZhbWlseT0nc2Fucy1zZXJpZicgZm9udC1zaXplPScxOCcgZm9udC13ZWlnaHQ9JzYwMCcgZG9taW5hbnQtYmFzZWxpbmU9J21pZGRsZScgdGV4dC1hbmNob3I9J21pZGRsZScgeD0nNTAlJyB5PSc1MCUnPkJyYWsgb2JyYXprYTwvdGV4dD48L3N2Zz4=';
            var imgErrorFallback = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0naHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmcnIHdpZHRoPSczMDAnIGhlaWdodD0nMzAwJyB2aWV3Qm94PScwIDAgMzAwIDMwMCc+PHJlY3QgZmlsbD0nIzEyMTIxYScgd2lkdGg9JzMwMCcgaGVpZ2h0PSczMDAnLz48dGV4dCBmaWxsPScjNjA2MDcwJyBmb250LWZhbWlseT0nc2Fucy1zZXJpZicgZm9udC1zaXplPScxOCcgZm9udC13ZWlnaHQ9JzYwMCcgZG9taW5hbnQtYmFzZWxpbmU9J21pZGRsZScgdGV4dC1hbmNob3I9J21pZGRsZScgeD0nNTAlJyB5PSc1MCUnPkLFgsSFZDwvdGV4dD48L3N2Zz4=';

            var title = getTitle(product);

            var promoHTML = '';
            if (product.promo_text) {
                var promos = product.promo_text.split(',').map(function(s) { return s.trim(); }).filter(Boolean);
                if (promos.length) {
                    promoHTML = '<div class="product-card__promos">' + promos.map(function(p) {
                        return '<div class="product-card__promo" title="Skopiuj kod rabatowy" data-promo="' + escapeHtml(p) + '" onclick="event.preventDefault(); event.stopPropagation(); navigator.clipboard.writeText(this.dataset.promo); var orig = this.innerHTML; this.innerHTML = \'✅ Skopiowano!\'; setTimeout(function() { this.innerHTML = orig; }.bind(this), 2000);">✂️ ' + escapeHtml(p) + '</div>';
                    }).join('') + '</div>';
                }
            }

            return '<article class="product-card" style="animation-delay: ' + ((index % BATCH_SIZE) * 0.05) + 's" onclick="openProduct(\'' + product.id + '\')">' +
                '<div class="product-card__image-wrap">' +
                    badgeHTML +
                    '<span class="product-card__cheap-badge">' + pricePLN.toFixed(2) + ' z\u0142</span>' +
                    '<img class="product-card__image" src="' + (product.image || imgFallback) + '" alt="' + escapeHtml(title) + '" loading="lazy" onerror="this.onerror=null;this.src=\'' + imgErrorFallback + '\'">' +
                '</div>' +
                '<div class="product-card__body">' +
                    '<h3 class="product-card__title">' + escapeHtml(title) + '</h3>' +
                    '<div class="product-card__meta">' +
                        '<div><span class="product-card__price">' + pricePLN.toFixed(2) + ' z\u0142</span>' + priceOld + '</div>' +
                        '<span class="product-card__rating">' + ratingStars + '</span>' +
                    '</div>' +
                    (product.price_note ? '<div class="product-card__price-note">\uD83C\uDFF7\uFE0F ' + escapeHtml(product.price_note) + '</div>' : '') +
                    promoHTML +
                    '<div class="product-card__orders">' + (product.orders || 0) + ' zam\u00F3wie\u0144</div>' +
                    '<a href="' + (product.affiliate_link || product.link || '#') + '" target="_blank" class="product-card__cta" onclick="event.stopPropagation()">\uD83D\uDED2 Kup teraz</a>' +
                '</div>' +
            '</article>';
        }).join('');

        renderLoadMore();
    }

    // --- Load More ---
    function renderLoadMore() {
        removeLoadMore();
        if (displayCount >= filteredProducts.length) return;

        var wrapper = document.createElement('div');
        wrapper.className = 'load-more';
        wrapper.id = 'loadMore';
        var shown = Math.min(displayCount, filteredProducts.length);
        wrapper.innerHTML = '<span class="load-more__counter">Pokazano ' + shown + ' z ' + filteredProducts.length + '</span>' +
            '<button class="load-more__btn" onclick="window._loadMoreDobaksa()">\uD83D\uDCE6 Poka\u017C wi\u0119cej</button>';
        productsGrid.after(wrapper);
    }

    function removeLoadMore() {
        var el = document.getElementById('loadMore');
        if (el) el.remove();
    }

    window._loadMoreDobaksa = function () {
        displayCount += BATCH_SIZE;
        renderProducts();
    };

    // --- Skeletons ---
    function showSkeletons(count) {
        productsGrid.innerHTML = Array.from({ length: count }, function() {
            return '<div class="skeleton skeleton-card"></div>';
        }).join('');
    }

    // --- Price Filter ---
    function applyFilters() {
        filteredProducts = cheapProducts.filter(function(product) {
            var matchesPrice = true;
            var pricePLN = toPLN(product.price, product.currency);
            if (currentPriceFilter === 'usd050') {
                matchesPrice = product.currency !== 'UAH' && product.price <= 0.50;
            } else if (currentPriceFilter === 'pln5') {
                matchesPrice = pricePLN <= 5;
            } else if (currentPriceFilter === 'pln10') {
                matchesPrice = pricePLN <= 10;
            }

            var titleToSearch = getTitle(product);
            var matchesSearch = !searchQuery ||
                titleToSearch.toLowerCase().includes(searchQuery.toLowerCase());

            return matchesPrice && matchesSearch;
        });
        displayCount = BATCH_SIZE;
        renderProducts();
    }

    // --- Stats ---
    function updateStats() {
        statsCheap.textContent = cheapProducts.length;
        if (cheapProducts.length > 0) {
            var usdProducts = cheapProducts.filter(function(p) { return p.currency !== 'UAH'; });
            if (usdProducts.length > 0) {
                var minPricePLN = Math.min.apply(null, usdProducts.map(function(p) { return toPLN(p.price, p.currency); }));
                statsMinPrice.textContent = minPricePLN.toFixed(2) + ' z\u0142';
            } else {
                var minPricePLN = Math.min.apply(null, cheapProducts.map(function(p) { return toPLN(p.price, p.currency); }));
                statsMinPrice.textContent = minPricePLN.toFixed(2) + ' z\u0142';
            }
        }
    }

    // --- Events ---
    function bindEvents() {
        var searchTimeout;
        searchInput.addEventListener('input', function(e) {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(function() {
                searchQuery = e.target.value.trim();
                applyFilters();
            }, 300);
        });

        priceFilters.addEventListener('click', function(e) {
            var btn = e.target.closest('.filter-btn');
            if (!btn) return;
            priceFilters.querySelectorAll('.filter-btn').forEach(function(b) { b.classList.remove('active'); });
            btn.classList.add('active');
            currentPriceFilter = btn.dataset.price;
            applyFilters();
        });
    }

    // --- Helpers ---
    function getBadgeText(badge) {
        var badges = { 'hot': '\uD83D\uDD25 Hit', 'new': '\uD83C\uDD95 Nowo\u015B\u0107' };
        return badges[badge] || badge;
    }

    function escapeHtml(str) {
        var div = document.createElement('div');
        div.textContent = str || '';
        return div.innerHTML;
    }

    // --- Global ---
    window.openProduct = function (id) {
        window.location.href = 'product.html?id=' + id;
    };

    // --- Start ---
    document.addEventListener('DOMContentLoaded', init);
})();
