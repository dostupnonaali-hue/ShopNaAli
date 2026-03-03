/**
 * Shop Na Ali — Product Page Logic
 * Loads product by ?id= from products.json, renders micro-landing
 */

(function () {
    'use strict';

    async function init() {
        const params = new URLSearchParams(window.location.search);
        const productId = params.get('id');

        if (!productId) {
            window.location.href = 'index.html';
            return;
        }

        try {
            const response = await fetch('data/products.json');
            const data = await response.json();
            const products = data.products || data || [];
            const product = products.find(p => p.id === productId);

            if (!product) {
                window.location.href = 'index.html';
                return;
            }

            renderProduct(product);
            startTimer();
        } catch (err) {
            console.error('Error loading product:', err);
            window.location.href = 'index.html';
        }
    }

    function renderProduct(product) {
        // Update page meta
        const title = `${product.title} — Shop Na Ali`;
        document.getElementById('pageTitle').textContent = title;
        document.getElementById('pageMeta').setAttribute('content', product.description || product.title);
        document.getElementById('ogTitle').setAttribute('content', title);
        const currencySymbol = product.currency === 'UAH' ? '₴' : '$';
        document.getElementById('ogDesc').setAttribute('content', `Всього ${currencySymbol}${product.price?.toFixed(2)} | ${product.title}`);
        document.getElementById('ogImage').setAttribute('content', product.image || '');

        // Update content
        document.getElementById('productImage').src = product.image || '';
        document.getElementById('productImage').alt = product.title;
        document.getElementById('productTitle').textContent = product.title;
        document.getElementById('productPrice').textContent = `${currencySymbol}${(product.price || 0).toFixed(2)}`;

        if (product.price_old) {
            document.getElementById('productPriceOld').textContent = `${currencySymbol}${product.price_old.toFixed(2)}`;
            const discount = Math.round((1 - product.price / product.price_old) * 100);
            const discountEl = document.getElementById('productDiscount');
            discountEl.textContent = `-${discount}%`;
            discountEl.style.display = 'inline-block';
        }

        if (product.promo_text) {
            const promoEl = document.getElementById('productPromo');
            promoEl.innerHTML = `✂️ ${product.promo_text}`;
            promoEl.title = 'Натисніть, щоб скопіювати';
            promoEl.style.display = 'inline-flex';
            promoEl.onclick = function (e) {
                e.preventDefault();
                navigator.clipboard.writeText(product.promo_text).then(() => {
                    const originalHtml = promoEl.innerHTML;
                    promoEl.innerHTML = `✅ Скопійовано!`;
                    setTimeout(() => promoEl.innerHTML = originalHtml, 2000);
                });
            };
        }

        document.getElementById('productRating').textContent = `⭐ ${product.rating || '—'}`;
        document.getElementById('productOrders').textContent = `${product.orders || 0} замовлень`;
        document.getElementById('productDescription').textContent = product.description || '';

        // Buy button
        const buyBtn = document.getElementById('buyButton');
        buyBtn.href = product.affiliate_link || product.link || '#';
    }

    // Countdown timer (random 2-8 hours from page load)
    function startTimer() {
        const totalSeconds = Math.floor(Math.random() * 21600) + 7200; // 2-8 hours
        let remaining = totalSeconds;

        function update() {
            const h = Math.floor(remaining / 3600);
            const m = Math.floor((remaining % 3600) / 60);
            const s = remaining % 60;

            document.getElementById('timerH').textContent = String(h).padStart(2, '0');
            document.getElementById('timerM').textContent = String(m).padStart(2, '0');
            document.getElementById('timerS').textContent = String(s).padStart(2, '0');

            if (remaining > 0) {
                remaining--;
                setTimeout(update, 1000);
            }
        }

        update();
    }

    document.addEventListener('DOMContentLoaded', init);
})();
