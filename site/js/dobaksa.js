/**
 * ShopDoBaksa - DoBaksa Page Logic
 * Shows products under $1 / 50 UAH from products.json
 */

(function () {
    'use strict';

    // --- Config ---
    var BATCH_SIZE = 30;

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
        await loadProducts();
        renderProducts();
        updateStats();
        bindEvents();
    }

    // --- Load & Filter Products ---
    async function loadProducts() {
        try {
            var cacheBuster = Math.floor(Date.now() / 300000);
            var response = await fetch('data/products.json?v=' + cacheBuster);
            if (!response.ok) throw new Error('Failed to load products');
            var data = await response.json();
            var allProducts = data.products || data || [];

            // Filter: USD <= 1 OR UAH <= 50
            cheapProducts = allProducts.filter(function(p) {
                if (!p.price || p.price <= 0) return false;
                if (p.currency === 'UAH') return p.price <= 50;
                return p.price <= 1;
            });

            // Sort by price ascending (normalize UAH to USD for sorting)
            cheapProducts.sort(function(a, b) {
                var priceA = a.currency === 'UAH' ? a.price / 41 : a.price;
                var priceB = b.currency === 'UAH' ? b.price / 41 : b.price;
                return priceA - priceB;
            });

            filteredProducts = cheapProducts.slice();
        } catch (err) {
            console.warn('Products not loaded:', err.message);
            cheapProducts = [];
            filteredProducts = [];
        }
    }

    // --- Render ---
    function renderProducts() {
        if (filteredProducts.length === 0) {
            productsGrid.innerHTML = '<div class="empty-state">' +
                '<div class="empty-state__icon">\uD83E\uDE99</div>' +
                '<h3 class="empty-state__title">\u0422\u043E\u0432\u0430\u0440\u0456\u0432 \u043F\u043E\u043A\u0438 \u043D\u0435\u043C\u0430\u0454</h3>' +
                '<p class="empty-state__text">\u041D\u043E\u0432\u0456 \u0437\u043D\u0430\u0445\u0456\u0434\u043A\u0438 \u0434\u043E 1$ \u0437\'\u044F\u0432\u043B\u044F\u0442\u044C\u0441\u044F \u0430\u0432\u0442\u043E\u043C\u0430\u0442\u0438\u0447\u043D\u043E \u2014 \u0437\u0430\u0445\u043E\u0434\u044C\u0442\u0435 \u0447\u0430\u0441\u0442\u0456\u0448\u0435!</p>' +
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
            var currencySymbol = product.currency === 'UAH' ? '\u20B4' : '$';
            var priceOld = product.price_old
                ? '<span class="product-card__price-old">' + currencySymbol + product.price_old.toFixed(2) + '</span>'
                : '';

            var imgFallback = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0naHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmcnIHdpZHRoPSczMDAnIGhlaWdodD0nMzAwJyB2aWV3Qm94PScwIDAgMzAwIDMwMCc+PHJlY3QgZmlsbD0nIzEyMTIxYScgd2lkdGg9JzMwMCcgaGVpZ2h0PSczMDAnLz48dGV4dCBmaWxsPScjNjA2MDcwJyBmb250LWZhbWlseT0nc2Fucy1zZXJpZicgZm9udC1zaXplPScxOCcgZm9udC13ZWlnaHQ9JzYwMCcgZG9taW5hbnQtYmFzZWxpbmU9J21pZGRsZScgdGV4dC1hbmNob3I9J21pZGRsZScgeD0nNTAlJyB5PSc1MCUnPtCX0L7QsdGA0LDQttC10L3QvdGPINC90LUg0LfQvdCw0LnQtNC10L3QvjwvdGV4dD48L3N2Zz4=';
            var imgErrorFallback = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0naHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmcnIHdpZHRoPSczMDAnIGhlaWdodD0nMzAwJyB2aWV3Qm94PScwIDAgMzAwIDMwMCc+PHJlY3QgZmlsbD0nIzEyMTIxYScgd2lkdGg9JzMwMCcgaGVpZ2h0PSczMDAnLz48dGV4dCBmaWxsPScjNjA2MDcwJyBmb250LWZhbWlseT0nc2Fucy1zZXJpZicgZm9udC1zaXplPScxOCcgZm9udC13ZWlnaHQ9JzYwMCcgZG9taW5hbnQtYmFzZWxpbmU9J21pZGRsZScgdGV4dC1hbmNob3I9J21pZGRsZScgeD0nNTAlJyB5PSc1MCUnPtCf0L7QvNC40LvQutCwPC90ZXh0Pjwvc3ZnPg==';

            var promoHTML = '';
            if (product.promo_text) {
                var promos = product.promo_text.split(',').map(function(s) { return s.trim(); }).filter(Boolean);
                if (promos.length) {
                    promoHTML = '<div class="product-card__promos">' + promos.map(function(p) {
                        return '<div class="product-card__promo" title="\u0421\u043A\u043E\u043F\u0456\u044E\u0432\u0430\u0442\u0438 \u043F\u0440\u043E\u043C\u043E\u043A\u043E\u0434" data-promo="' + escapeHtml(p) + '" onclick="event.preventDefault(); event.stopPropagation(); navigator.clipboard.writeText(this.dataset.promo); var orig = this.innerHTML; this.innerHTML = \'\u2705 \u0421\u043A\u043E\u043F\u0456\u0439\u043E\u0432\u0430\u043D\u043E!\'; setTimeout(function() { this.innerHTML = orig; }.bind(this), 2000);">\u2702\uFE0F ' + escapeHtml(p) + '</div>';
                    }).join('') + '</div>';
                }
            }

            return '<article class="product-card" style="animation-delay: ' + ((index % BATCH_SIZE) * 0.05) + 's" onclick="openProduct(\'' + product.id + '\')">' +
                '<div class="product-card__image-wrap">' +
                    badgeHTML +
                    '<span class="product-card__cheap-badge">' + currencySymbol + (product.price || 0).toFixed(2) + '</span>' +
                    '<img class="product-card__image" src="' + (product.image || imgFallback) + '" alt="' + escapeHtml(product.title) + '" loading="lazy" onerror="this.onerror=null;this.src=\'' + imgErrorFallback + '\'">' +
                '</div>' +
                '<div class="product-card__body">' +
                    '<h3 class="product-card__title">' + escapeHtml(product.title) + '</h3>' +
                    '<div class="product-card__meta">' +
                        '<div><span class="product-card__price">' + currencySymbol + (product.price || 0).toFixed(2) + '</span>' + priceOld + '</div>' +
                        '<span class="product-card__rating">' + ratingStars + '</span>' +
                    '</div>' +
                    (product.price_note ? '<div class="product-card__price-note">\uD83C\uDFF7\uFE0F ' + escapeHtml(product.price_note) + '</div>' : '') +
                    promoHTML +
                    '<div class="product-card__orders">' + (product.orders || 0) + ' \u0437\u0430\u043C\u043E\u0432\u043B\u0435\u043D\u044C</div>' +
                    '<a href="' + (product.affiliate_link || product.link || '#') + '" target="_blank" class="product-card__cta" onclick="event.stopPropagation()">\uD83D\uDED2 \u041A\u0443\u043F\u0438\u0442\u0438</a>' +
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
        wrapper.innerHTML = '<span class="load-more__counter">\u041F\u043E\u043A\u0430\u0437\u0430\u043D\u043E ' + shown + ' \u0437 ' + filteredProducts.length + '</span>' +
            '<button class="load-more__btn" onclick="window._loadMoreDobaksa()">\uD83D\uDCE6 \u041F\u043E\u043A\u0430\u0437\u0430\u0442\u0438 \u0449\u0435</button>';
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
            if (currentPriceFilter === 'usd050') {
                matchesPrice = product.currency !== 'UAH' && product.price <= 0.50;
            } else if (currentPriceFilter === 'uah25') {
                matchesPrice = product.currency === 'UAH' && product.price <= 25;
            } else if (currentPriceFilter === 'uah50') {
                matchesPrice = product.currency === 'UAH' && product.price <= 50;
            }

            var matchesSearch = !searchQuery ||
                product.title.toLowerCase().includes(searchQuery.toLowerCase());

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
                var minPrice = Math.min.apply(null, usdProducts.map(function(p) { return p.price; }));
                statsMinPrice.textContent = '$' + minPrice.toFixed(2);
            } else {
                var minPrice = Math.min.apply(null, cheapProducts.map(function(p) { return p.price; }));
                statsMinPrice.textContent = '\u20B4' + minPrice.toFixed(0);
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
        var badges = { 'hot': '\uD83D\uDD25 \u0425\u0456\u0442', 'new': '\uD83C\uDD95 \u041D\u043E\u0432\u0435' };
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
