/**
 * ShopDoBaksa — Main App Logic
 * Loads products from data/products.json and renders the catalog
 */

(function () {
    'use strict';

    // --- State ---
    let allProducts = [];
    let filteredProducts = [];
    let currentFilter = 'all';
    let searchQuery = '';

    // --- DOM Elements ---
    const productsGrid = document.getElementById('productsGrid');
    const searchInput = document.getElementById('searchInput');
    const filtersContainer = document.getElementById('filters');
    const statsProducts = document.getElementById('statsProducts');
    const statsCategories = document.getElementById('statsCategories');

    // --- Init ---
    async function init() {
        showSkeletons(8);
        await loadProducts();
        renderProducts();
        updateStats();
        bindEvents();
    }

    // --- Load Products ---
    async function loadProducts() {
        try {
            const response = await fetch('data/products.json');
            if (!response.ok) throw new Error('Failed to load products');
            const data = await response.json();
            allProducts = data.products || data || [];
            filteredProducts = [...allProducts];
        } catch (err) {
            console.warn('Products not loaded yet:', err.message);
            allProducts = [];
            filteredProducts = [];
        }
    }

    // --- Render Products ---
    function renderProducts() {
        if (filteredProducts.length === 0) {
            productsGrid.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state__icon">📦</div>
                    <h3 class="empty-state__title">Товари скоро з'являться!</h3>
                    <p class="empty-state__text">Парсер вже працює — нові знахідки додаються автоматично</p>
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
                        <img class="product-card__image" 
                             src="${product.image ? product.image : 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0naHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmcnIHdpZHRoPSczMDAnIGhlaWdodD0nMzAwJyB2aWV3Qm94PScwIDAgMzAwIDMwMCc+PHJlY3QgZmlsbD0nIzEyMTIxYScgd2lkdGg9JzMwMCcgaGVpZ2h0PSczMDAnLz48dGV4dCBmaWxsPScjNjA2MDcwJyBmb250LWZhbWlseT0nc2Fucy1zZXJpZicgZm9udC1zaXplPScxOCcgZm9udC13ZWlnaHQ9JzYwMCcgZG9taW5hbnQtYmFzZWxpbmU9J21pZGRsZScgdGV4dC1hbmNob3I9J21pZGRsZScgeD0nNTAlJyB5PSc1MCUnPpfQvtCx0YDQsNC20LXQvdC90Y8g0L3QtSDQt9C90LDQudC00LXQvdC+\&lt;/dGV4dD48L3N2Zz4='}"
                             alt="${escapeHtml(product.title)}" 
                             loading="lazy"
                             onerror="this.src='data:image/svg+xml;base64,PHN2ZyB4bWxucz0naHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmcnIHdpZHRoPSczMDAnIGhlaWdodD0nMzAwJyB2aWV3Qm94PScwIDAgMzAwIDMwMCc+PHJlY3QgZmlsbD0nIzEyMTIxYScgd2lkdGg9JzMwMCcgaGVpZ2h0PSczMDAnLz48dGV4dCBmaWxsPScjNjA2MDcwJyBmb250LWZhbWlseT0nc2Fucy1zZXJpZicgZm9udC1zaXplPScxOCcgZm9udC13ZWlnaHQ9JzYwMCcgZG9taW5hbnQtYmFzZWxpbmU9J21pZGRsZScgdGV4dC1hbmNob3I9J21pZGRsZScgeD0nNTAlJyB5PSc1MCUnPpfQvtCx0YDQsNC20LXQvdC90Y8g0L/QvtC80LjQu9C60LA8L3RleHQ+PC/Ndmc+'">
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

    // --- Filter ---
    function applyFilters() {
        filteredProducts = allProducts.filter(product => {
            const matchesFilter = currentFilter === 'all' || product.category === currentFilter || product.badge === currentFilter;
            const matchesSearch = !searchQuery ||
                product.title.toLowerCase().includes(searchQuery.toLowerCase());
            return matchesFilter && matchesSearch;
        });
        renderProducts();
    }

    // --- Stats ---
    function updateStats() {
        statsProducts.textContent = allProducts.length;
        const categories = new Set(allProducts.map(p => p.category).filter(Boolean));
        statsCategories.textContent = categories.size || '—';
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

        // Filters
        filtersContainer.addEventListener('click', (e) => {
            const btn = e.target.closest('.filter-btn');
            if (!btn) return;

            filtersContainer.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentFilter = btn.dataset.filter;
            applyFilters();
        });
    }

    // --- Helpers ---
    function getBadgeText(badge) {
        const badges = {
            'hot': '🔥 Хіт',
            'new': '🆕 Нове',
        };
        return badges[badge] || badge;
    }

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str || '';
        return div.innerHTML;
    }

    // --- Global: open product page ---
    window.openProduct = function (id) {
        window.location.href = `product.html?id=${id}`;
    };

    // --- Start ---
    document.addEventListener('DOMContentLoaded', init);
})();
