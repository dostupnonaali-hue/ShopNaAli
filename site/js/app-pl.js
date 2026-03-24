/**
 * ShopDoBaksa - App Logic (Polish version)
 * Loads products from data/products.json and renders the catalog in Polish
 */

(function () {
    'use strict';

    // --- Config ---
    var BATCH_SIZE = 20;

    // --- Exchange rates (fallback values) ---
    var rates = { USD: 4.05, UAH: 0.098 }; // 1 USD ≈ 4.05 PLN, 1 UAH ≈ 0.098 PLN

    // --- State ---
    var allProducts = [];
    var filteredProducts = [];
    var currentFilter = 'all';
    var searchQuery = '';
    var displayCount = BATCH_SIZE;

    // --- DOM Elements ---
    var productsGrid = document.getElementById('productsGrid');
    var searchInput = document.getElementById('searchInput');
    var filtersContainer = document.getElementById('filters');
    var statsProducts = document.getElementById('statsProducts');
    var statsCategories = document.getElementById('statsCategories');

    // --- Init ---
    async function init() {
        showSkeletons(8);
        await Promise.all([loadProducts(), loadExchangeRates()]);
        renderProducts();
        updateStats();
        bindEvents();
    }

    // --- Load Exchange Rates ---
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

    // --- Convert price to PLN ---
    function toPLN(price, currency) {
        if (!price) return 0;
        if (currency === 'UAH') return price * rates.UAH;
        return price * rates.USD; // default USD
    }

    // --- Load Products ---
    async function loadProducts() {
        try {
            var cacheBuster = Math.floor(Date.now() / 300000);
            var response = await fetch('../data/products.json?v=' + cacheBuster);
            if (!response.ok) throw new Error('Failed to load products');
            var data = await response.json();
            allProducts = data.products || data || [];
            filteredProducts = allProducts.slice();
        } catch (err) {
            console.warn('Products not loaded yet:', err.message);
            allProducts = [];
            filteredProducts = [];
        }
    }

    // --- Get Polish title or fallback to original ---
    function getTitle(product) {
        return product.title_pl || product.title || '';
    }

    // --- Render Products ---
    function renderProducts() {
        if (filteredProducts.length === 0) {
            productsGrid.innerHTML = '<div class="empty-state">' +
                '<div class="empty-state__icon">\uD83D\uDCE6</div>' +
                '<h3 class="empty-state__title">Produkty pojawi\u0105 si\u0119 wkr\u00F3tce!</h3>' +
                '<p class="empty-state__text">Parser ju\u017C dzia\u0142a \u2014 nowe okazje s\u0105 dodawane automatycznie</p>' +
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
                    '<img class="product-card__image" src="' + (product.image || imgFallback) + '" alt="' + escapeHtml(title) + '" loading="lazy" onerror="this.onerror=null;this.src=\'' + imgErrorFallback + '\'">' +
                '</div>' +
                '<div class="product-card__body">' +
                    '<h3 class="product-card__title">' + escapeHtml(title) + '</h3>' +
                    '<div class="product-card__meta">' +
                        '<div><span class="product-card__price">' + pricePLN.toFixed(2) + ' z\u0142</span>' + priceOld + '</div>' +
                        '<span class="product-card__rating">' + ratingStars + '</span>' +
                    '</div>' +
                    (product.price_note ? '<div class="product-card__price-note">\uD83C\uDFF7\uFE0F ' + escapeHtml(translatePriceNote(product.price_note)) + '</div>' : '') +
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
            '<button class="load-more__btn" onclick="window._loadMore()">\uD83D\uDCE6 Poka\u017C wi\u0119cej</button>';
        productsGrid.after(wrapper);
    }

    function removeLoadMore() {
        var el = document.getElementById('loadMore');
        if (el) el.remove();
    }

    window._loadMore = function () {
        displayCount += BATCH_SIZE;
        renderProducts();
    };

    // --- Skeletons ---
    function showSkeletons(count) {
        productsGrid.innerHTML = Array.from({ length: count }, function() {
            return '<div class="skeleton skeleton-card"></div>';
        }).join('');
    }

    // --- Filter ---
    function applyFilters() {
        filteredProducts = allProducts.filter(function(product) {
            var matchesFilter = currentFilter === 'all' || product.category === currentFilter || product.badge === currentFilter;
            var titleToSearch = getTitle(product);
            var matchesSearch = !searchQuery ||
                titleToSearch.toLowerCase().includes(searchQuery.toLowerCase());
            return matchesFilter && matchesSearch;
        });
        displayCount = BATCH_SIZE;
        renderProducts();
    }

    // --- Stats ---
    function updateStats() {
        statsProducts.textContent = allProducts.length;
        var categories = new Set(allProducts.map(function(p) { return p.category; }).filter(Boolean));
        statsCategories.textContent = categories.size || '\u2014';
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

        filtersContainer.addEventListener('click', function(e) {
            var btn = e.target.closest('.filter-btn');
            if (!btn) return;
            filtersContainer.querySelectorAll('.filter-btn').forEach(function(b) { b.classList.remove('active'); });
            btn.classList.add('active');
            currentFilter = btn.dataset.filter;
            applyFilters();
        });
    }

    // --- Helpers ---
    function getBadgeText(badge) {
        var badges = { 'hot': '\uD83D\uDD25 Hit', 'new': '\uD83C\uDD95 Nowo\u015B\u0107' };
        return badges[badge] || badge;
    }

    function translatePriceNote(note) {
        if (!note) return '';
        var translations = {
            'Монетками': '🪙 Coins',
            'монетками': '🪙 Coins',
            'Монетами': '🪙 Coins',
            'монетами': '🪙 Coins'
        };
        return translations[note.trim()] || note;
    }

    function escapeHtml(str) {
        var div = document.createElement('div');
        div.textContent = str || '';
        return div.innerHTML;
    }

    // --- Global: open product page ---
    window.openProduct = function (id) {
        window.location.href = 'product.html?id=' + id;
    };

    // --- Start ---
    document.addEventListener('DOMContentLoaded', init);
})();
