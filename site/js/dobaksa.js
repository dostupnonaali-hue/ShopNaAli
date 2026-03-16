/**
 * ShopDoBaksa — DoBaksa Page Logic
 * Shows products under $1 / 50₴ from products.json
 */

(function () {
    'use strict';

    // --- State ---
    let cheapProducts = [];
    let filteredProducts = [];
    let currentPriceFilter = 'all';
    let searchQuery = '';

    // --- DOM ---
    const productsGrid = document.getElementById('productsGrid');
    const searchInput = document.getElementById('searchInput');
    const priceFilters = document.getElementById('priceFilters');
    const statsCheap = document.getElementById('statsCheap');
    const statsMinPrice = document.getElementById('statsMinPrice');

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
            const cacheBuster = Math.floor(Date.now() / 300000);
            const response = await fetch(`data/products.json?v=${cacheBuster}`);
            if (!response.ok) throw new Error('Failed to load products');
            const data = await response.json();
            const allProducts = data.products || data || [];

            // Filter: USD <= 1 OR UAH <= 50
            cheapProducts = allProducts.filter(p => {
                if (!p.price || p.price <= 0) return false;
                if (p.currency === 'UAH') return p.price <= 50;
                return p.price <= 1; // USD default
            });

            // Sort by price ascending
            cheapProducts.sort((a, b) => {
                const priceA = a.currency === 'UAH' ? a.price / 41 : a.price;
                const priceB = b.currency === 'UAH' ? b.price / 41 : b.price;
                return priceA - priceB;
            });

            filteredProducts = [...cheapProducts];
        } catch (err) {
            console.warn('Products not loaded:', err.message);
            cheapProducts = [];
            filteredProducts = [];
        }
    }

    // --- Render ---
    function renderProducts() {
        if (filteredProducts.length === 0) {
            productsGrid.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state__icon">🪙</div>
                    <h3 class="empty-state__title">Товарів поки немає</h3>
                    <p class="empty-state__text">Нові знахідки до 1$ з'являться автоматично — заходьте частіше!</p>
                </div>
            `;
            return;
        }

        productsGrid.innerHTML = filteredProducts.map((product, index) => {
            const badgeHTML = product.badge
                ? `<span class="product-card__badge product-card__badge--${product.badge}">${getBadgeText(product.badge)}</span>`
                : '';

            const ratingStars = '⭐'.repeat(Math.round(product.rating || 0));
            const currencySymbol = product.currency === 'UAH' ? '₴' : '$';
            const priceOld = product.price_old
                ? `<span class="product-card__price-old">${currencySymbol}${product.price_old.toFixed(2)}</span>`
                : '';

            return `
                <article class="product-card" style="animation-delay: ${index * 0.05}s" onclick="openProduct('${product.id}')">
                    <div class="product-card__image-wrap">
                        ${badgeHTML}
                        <span class="product-card__cheap-badge">${currencySymbol}${(product.price || 0).toFixed(2)}</span>
                        <img class="product-card__image" 
                             src="${product.image ? product.image : 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0naHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmcnIHdpZHRoPSczMDAnIGhlaWdodD0nMzAwJyB2aWV3Qm94PScwIDAgMzAwIDMwMCc+PHJlY3QgZmlsbD0nIzEyMTIxYScgd2lkdGg9JzMwMCcgaGVpZ2h0PSczMDAnLz48dGV4dCBmaWxsPScjNjA2MDcwJyBmb250LWZhbWlseT0nc2Fucy1zZXJpZicgZm9udC1zaXplPScxOCcgZm9udC13ZWlnaHQ9JzYwMCcgZG9taW5hbnQtYmFzZWxpbmU9J21pZGRsZScgdGV4dC1hbmNob3I9J21pZGRsZScgeD0nNTAlJyB5PSc1MCUnPtCX0L7QsdGA0LDQttC10L3QvdGPINC90LUg0LfQvdCw0LnQtNC10L3QvjwvdGV4dD48L3N2Zz4='}"
                             alt="${escapeHtml(product.title)}" 
                             loading="lazy"
                             onerror="this.onerror=null;this.src='data:image/svg+xml;base64,PHN2ZyB4bWxucz0naHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmcnIHdpZHRoPSczMDAnIGhlaWdodD0nMzAwJyB2aWV3Qm94PScwIDAgMzAwIDMwMCc+PHJlY3QgZmlsbD0nIzEyMTIxYScgd2lkdGg9JzMwMCcgaGVpZ2h0PSczMDAnLz48dGV4dCBmaWxsPScjNjA2MDcwJyBmb250LWZhbWlseT0nc2Fucy1zZXJpZicgZm9udC1zaXplPScxOCcgZm9udC13ZWlnaHQ9JzYwMCcgZG9taW5hbnQtYmFzZWxpbmU9J21pZGRsZScgdGV4dC1hbmNob3I9J21pZGRsZScgeD0nNTAlJyB5PSc1MCUnPtCf0L7QvNC40LvQutCwPC90ZXh0Pjwvc3ZnPg=='">
                    </div>
                    <div class="product-card__body">
                        <h3 class="product-card__title">${escapeHtml(product.title)}</h3>
                        <div class="product-card__meta">
                            <div>
                                <span class="product-card__price">${currencySymbol}${(product.price || 0).toFixed(2)}</span>
                                ${priceOld}
                            </div>
                            <span class="product-card__rating">${ratingStars}</span>
                        </div>
                        ${product.price_note ? `<div class="product-card__price-note">🏷️ ${escapeHtml(product.price_note)}</div>` : ''}
                        ${product.promo_text ? (() => {
                            const promos = product.promo_text.split(',').map(s => s.trim()).filter(Boolean);
                            if (!promos.length) return '';
                            return `<div class="product-card__promos">` + promos.map(p => 
                                `<div class="product-card__promo" title="Скопіювати промокод" data-promo="${escapeHtml(p)}" onclick="event.preventDefault(); event.stopPropagation(); navigator.clipboard.writeText(this.dataset.promo); const orig = this.innerHTML; this.innerHTML = '✅ Скопійовано!'; setTimeout(() => this.innerHTML = orig, 2000);">✂️ ${escapeHtml(p)}</div>`
                            ).join('') + `</div>`;
                        })() : ''}
                        <div class="product-card__orders">${product.orders || 0} замовлень</div>
                        <a href="${product.affiliate_link || product.link || '#'}" 
                           target="_blank" 
                           class="product-card__cta"
                           onclick="event.stopPropagation()">
                            🛒 Купити
                        </a>
                    </div>
                </article>
            `;
        }).join('');
    }

    // --- Skeletons ---
    function showSkeletons(count) {
        productsGrid.innerHTML = Array.from({ length: count }, () =>
            '<div class="skeleton skeleton-card"></div>'
        ).join('');
    }

    // --- Price Filter ---
    function applyFilters() {
        filteredProducts = cheapProducts.filter(product => {
            // Price sub-filter
            let matchesPrice = true;
            if (currentPriceFilter === 'usd050') {
                matchesPrice = product.currency !== 'UAH' && product.price <= 0.50;
            } else if (currentPriceFilter === 'uah25') {
                matchesPrice = product.currency === 'UAH' && product.price <= 25;
            } else if (currentPriceFilter === 'uah50') {
                matchesPrice = product.currency === 'UAH' && product.price <= 50;
            }
            // all = show everything (already filtered to <=$1 / <=50₴)

            // Search
            const matchesSearch = !searchQuery ||
                product.title.toLowerCase().includes(searchQuery.toLowerCase());

            return matchesPrice && matchesSearch;
        });
        renderProducts();
    }

    // --- Stats ---
    function updateStats() {
        statsCheap.textContent = cheapProducts.length;
        if (cheapProducts.length > 0) {
            const usdProducts = cheapProducts.filter(p => p.currency !== 'UAH');
            if (usdProducts.length > 0) {
                const minPrice = Math.min(...usdProducts.map(p => p.price));
                statsMinPrice.textContent = `$${minPrice.toFixed(2)}`;
            } else {
                const minPrice = Math.min(...cheapProducts.map(p => p.price));
                statsMinPrice.textContent = `₴${minPrice.toFixed(0)}`;
            }
        }
    }

    // --- Events ---
    function bindEvents() {
        // Search
        let searchTimeout;
        searchInput.addEventListener('input', (e) => {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                searchQuery = e.target.value.trim();
                applyFilters();
            }, 300);
        });

        // Price Filters
        priceFilters.addEventListener('click', (e) => {
            const btn = e.target.closest('.filter-btn');
            if (!btn) return;

            priceFilters.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentPriceFilter = btn.dataset.price;
            applyFilters();
        });
    }

    // --- Helpers ---
    function getBadgeText(badge) {
        const badges = { 'hot': '🔥 Хіт', 'new': '🆕 Нове' };
        return badges[badge] || badge;
    }

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str || '';
        return div.innerHTML;
    }

    // --- Global ---
    window.openProduct = function (id) {
        window.location.href = `product.html?id=${id}`;
    };

    // --- Start ---
    document.addEventListener('DOMContentLoaded', init);
})();
