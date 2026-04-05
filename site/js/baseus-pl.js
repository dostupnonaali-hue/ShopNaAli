/**
 * ShopDoBaksa - Baseus Brand Page Logic (Polish)
 * Shows only products with "Baseus" in the title from products.json
 */

(function () {
    'use strict';

    // --- Config ---
    var BATCH_SIZE = 30;
    var BRAND_KEYWORD = 'baseus';

    // --- Exchange rates (fallback values) ---
    var rates = { USD: 4.05, UAH: 0.098 }; // 1 USD ≈ 4.05 PLN, 1 UAH ≈ 0.098 PLN

    // --- State ---
    var brandProducts = [];
    var filteredProducts = [];
    var currentSort = 'new';
    var searchQuery = '';
    var displayCount = BATCH_SIZE;

    // --- DOM ---
    var productsGrid = document.getElementById('productsGrid');
    var searchInput = document.getElementById('searchInput');
    var sortFilters = document.getElementById('sortFilters');
    var statsCount = document.getElementById('statsCount');
    var statsMinPrice = document.getElementById('statsMinPrice');

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

    // --- Load & Filter Products ---
    async function loadProducts() {
        try {
            var cacheBuster = Math.floor(Date.now() / 300000);
            var response = await fetch('../data/products.json?v=' + cacheBuster);
            if (!response.ok) throw new Error('Failed to load products');
            var data = await response.json();
            var allProducts = data.products || data || [];

            // Filter: only products with "baseus" in the title (case-insensitive)
            // Check both original title and title_pl
            brandProducts = allProducts.filter(function(p) {
                var title = (p.title || '').toLowerCase();
                var titlePl = (p.title_pl || '').toLowerCase();
                return title.includes(BRAND_KEYWORD) || titlePl.includes(BRAND_KEYWORD);
            });

            // Sort by date descending (newest first)
            brandProducts.sort(function(a, b) {
                var dateA = a.added_at || '';
                var dateB = b.added_at || '';
                return dateB.localeCompare(dateA);
            });

            filteredProducts = brandProducts.slice();
        } catch (err) {
            console.warn('Products not loaded:', err.message);
            brandProducts = [];
            filteredProducts = [];
        }
    }

    // --- Render ---
    function renderProducts() {
        if (filteredProducts.length === 0) {
            productsGrid.innerHTML = '<div class="empty-state">' +
                '<div class="empty-state__icon">\uD83D\uDD0B</div>' +
                '<h3 class="empty-state__title">Brak produkt\u00F3w Baseus</h3>' +
                '<p class="empty-state__text">Nowe produkty Baseus pojawi\u0105 si\u0119 automatycznie \u2014 wracaj cz\u0119\u015Bciej!</p>' +
                '</div>';
            removeLoadMore();
            return;
        }

        var visible = filteredProducts.slice(0, displayCount);

        productsGrid.innerHTML = visible.map(function(product, index) {
            var displayTitle = product.title_pl || product.title || '';

            var badgeHTML = product.badge
                ? '<span class="product-card__badge product-card__badge--' + product.badge + '">' + getBadgeText(product.badge) + '</span>'
                : '';

            var ratingStars = '\u2B50'.repeat(Math.round(product.rating || 0));
            var pricePLN = toPLN(product.price, product.currency);
            var priceDisplay = pricePLN.toFixed(2) + ' z\u0142';

            var imgFallback = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0naHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmcnIHdpZHRoPSczMDAnIGhlaWdodD0nMzAwJyB2aWV3Qm94PScwIDAgMzAwIDMwMCc+PHJlY3QgZmlsbD0nIzEyMTIxYScgd2lkdGg9JzMwMCcgaGVpZ2h0PSczMDAnLz48dGV4dCBmaWxsPScjNjA2MDcwJyBmb250LWZhbWlseT0nc2Fucy1zZXJpZicgZm9udC1zaXplPScxOCcgZm9udC13ZWlnaHQ9JzYwMCcgZG9taW5hbnQtYmFzZWxpbmU9J21pZGRsZScgdGV4dC1hbmNob3I9J21pZGRsZScgeD0nNTAlJyB5PSc1MCUnPkJyYWsgb2JyYXprYTwvdGV4dD48L3N2Zz4=';
            var imgErrorFallback = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0naHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmcnIHdpZHRoPSczMDAnIGhlaWdodD0nMzAwJyB2aWV3Qm94PScwIDAgMzAwIDMwMCc+PHJlY3QgZmlsbD0nIzEyMTIxYScgd2lkdGg9JzMwMCcgaGVpZ2h0PSczMDAnLz48dGV4dCBmaWxsPScjNjA2MDcwJyBmb250LWZhbWlseT0nc2Fucy1zZXJpZicgZm9udC1zaXplPScxOCcgZm9udC13ZWlnaHQ9JzYwMCcgZG9taW5hbnQtYmFzZWxpbmU9J21pZGRsZScgdGV4dC1hbmNob3I9J21pZGRsZScgeD0nNTAlJyB5PSc1MCUnPkIzxIVkPC90ZXh0Pjwvc3ZnPg==';

            var promoHTML = '';
            if (product.promo_text) {
                var promos = product.promo_text.split(',').map(function(s) { return s.trim(); }).filter(Boolean);
                if (promos.length) {
                    promoHTML = '<div class="product-card__promos">' + promos.map(function(p) {
                        return '<div class="product-card__promo" title="Skopiuj kod" data-promo="' + escapeHtml(p) + '" onclick="event.preventDefault(); event.stopPropagation(); navigator.clipboard.writeText(this.dataset.promo); var orig = this.innerHTML; this.innerHTML = \'\u2705 Skopiowano!\'; setTimeout(function() { this.innerHTML = orig; }.bind(this), 2000);">\u2702\uFE0F ' + escapeHtml(p) + '</div>';
                    }).join('') + '</div>';
                }
            }

            return '<article class="product-card" style="animation-delay: ' + ((index % BATCH_SIZE) * 0.05) + 's" onclick="openProduct(\'' + product.id + '\')">' +
                '<div class="product-card__image-wrap">' +
                    badgeHTML +
                    '<span class="product-card__cheap-badge">' + priceDisplay + '</span>' +
                    '<img class="product-card__image" src="' + (product.image || imgFallback) + '" alt="' + escapeHtml(displayTitle) + '" loading="lazy" onerror="this.onerror=null;this.src=\'' + imgErrorFallback + '\'">' +
                '</div>' +
                '<div class="product-card__body">' +
                    '<h3 class="product-card__title">' + escapeHtml(displayTitle) + '</h3>' +
                    '<div class="product-card__meta">' +
                        '<div><span class="product-card__price">' + priceDisplay + '</span></div>' +
                        '<span class="product-card__rating">' + ratingStars + '</span>' +
                    '</div>' +
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
            '<button class="load-more__btn" onclick="window._loadMoreBaseus()">\uD83D\uDCE6 Poka\u017C wi\u0119cej</button>';
        productsGrid.after(wrapper);
    }

    function removeLoadMore() {
        var el = document.getElementById('loadMore');
        if (el) el.remove();
    }

    window._loadMoreBaseus = function () {
        displayCount += BATCH_SIZE;
        renderProducts();
    };

    // --- Skeletons ---
    function showSkeletons(count) {
        productsGrid.innerHTML = Array.from({ length: count }, function() {
            return '<div class="skeleton skeleton-card"></div>';
        }).join('');
    }

    // --- Sort & Filter ---
    function applyFilters() {
        filteredProducts = brandProducts.filter(function(product) {
            var title = (product.title_pl || product.title || '').toLowerCase();
            var matchesSearch = !searchQuery || title.includes(searchQuery.toLowerCase());
            return matchesSearch;
        });

        // Sort
        if (currentSort === 'new') {
            filteredProducts.sort(function(a, b) {
                return (b.added_at || '').localeCompare(a.added_at || '');
            });
        } else if (currentSort === 'cheap') {
            filteredProducts.sort(function(a, b) {
                return toPLN(a.price, a.currency) - toPLN(b.price, b.currency);
            });
        } else if (currentSort === 'expensive') {
            filteredProducts.sort(function(a, b) {
                return toPLN(b.price, b.currency) - toPLN(a.price, a.currency);
            });
        } else if (currentSort === 'popular') {
            filteredProducts.sort(function(a, b) {
                return (b.orders || 0) - (a.orders || 0);
            });
        }

        displayCount = BATCH_SIZE;
        renderProducts();
    }

    // --- Stats ---
    function updateStats() {
        statsCount.textContent = brandProducts.length;
        if (brandProducts.length > 0) {
            var prices = brandProducts.map(function(p) { return toPLN(p.price, p.currency) || 999; });
            var minPrice = Math.min.apply(null, prices);
            statsMinPrice.textContent = minPrice.toFixed(2) + ' z\u0142';
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

        sortFilters.addEventListener('click', function(e) {
            var btn = e.target.closest('.filter-btn');
            if (!btn) return;
            sortFilters.querySelectorAll('.filter-btn').forEach(function(b) { b.classList.remove('active'); });
            btn.classList.add('active');
            currentSort = btn.dataset.sort;
            applyFilters();
        });
    }

    // --- Helpers ---
    function getBadgeText(badge) {
        var badges = { 'hot': '\uD83D\uDD25 Hit', 'new': '\uD83C\uDD95 Nowe' };
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
