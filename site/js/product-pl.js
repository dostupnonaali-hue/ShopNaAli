/**
 * ShopDoBaksa — Product Page Logic (Polish version)
 * Loads product by ?id= from products.json, renders micro-landing in Polish with PLN
 */

(function () {
    'use strict';

    // --- Exchange rates (fallback values) ---
    var rates = { USD: 4.05, UAH: 0.098 };

    async function init() {
        const params = new URLSearchParams(window.location.search);
        const productId = params.get('id');

        if (!productId) {
            window.location.href = 'index.html';
            return;
        }

        try {
            await loadExchangeRates();
            const cacheBuster = Math.floor(Date.now() / 300000);
            const response = await fetch(`../data/products.json?v=${cacheBuster}`);
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

    function renderProduct(product) {
        const productTitle = product.title_pl || product.title;
        const title = `${productTitle} — ShopDoBaksa`;
        document.getElementById('pageTitle').textContent = title;
        document.getElementById('pageMeta').setAttribute('content', product.description || productTitle);
        document.getElementById('ogTitle').setAttribute('content', title);
        var pricePLN = toPLN(product.price, product.currency);
        document.getElementById('ogDesc').setAttribute('content', `Tylko ${pricePLN.toFixed(2)} zł | ${productTitle}`);
        document.getElementById('ogImage').setAttribute('content', product.image || '');

        const fallbackImg = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0naHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmcnIHdpZHRoPSczMDAnIGhlaWdodD0nMzAwJyB2aWV3Qm94PScwIDAgMzAwIDMwMCc+PHJlY3QgZmlsbD0nIzEyMTIxYScgd2lkdGg9JzMwMCcgaGVpZ2h0PSczMDAnLz48dGV4dCBmaWxsPScjNjA2MDcwJyBmb250LWZhbWlseT0nc2Fucy1zZXJpZicgZm9udC1zaXplPScxOCcgZm9udC13ZWlnaHQ9JzYwMCcgZG9taW5hbnQtYmFzZWxpbmU9J21pZGRsZScgdGV4dC1hbmNob3I9J21pZGRsZScgeD0nNTAlJyB5PSc1MCUnPkJyYWsgb2JyYXprYTwvdGV4dD48L3N2Zz4=';
        const errorImg = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0naHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmcnIHdpZHRoPSczMDAnIGhlaWdodD0nMzAwJyB2aWV3Qm94PScwIDAgMzAwIDMwMCc+PHJlY3QgZmlsbD0nIzEyMTIxYScgd2lkdGg9JzMwMCcgaGVpZ2h0PSczMDAnLz48dGV4dCBmaWxsPScjNjA2MDcwJyBmb250LWZhbWlseT0nc2Fucy1zZXJpZicgZm9udC1zaXplPScxOCcgZm9udC13ZWlnaHQ9JzYwMCcgZG9taW5hbnQtYmFzZWxpbmU9J21pZGRsZScgdGV4dC1hbmNob3I9J21pZGRsZScgeD0nNTAlJyB5PSc1MCUnPkLFgsSFZDwvdGV4dD48L3N2Zz4=';
        const imgEl = document.getElementById('productImage');
        imgEl.src = product.image ? product.image : fallbackImg;
        imgEl.onerror = function() { this.src = errorImg; };
        imgEl.alt = productTitle;
        document.getElementById('productTitle').textContent = productTitle;
        document.getElementById('productPrice').textContent = pricePLN.toFixed(2) + ' zł';

        if (product.price_old) {
            var priceOldPLN = toPLN(product.price_old, product.currency);
            document.getElementById('productPriceOld').textContent = priceOldPLN.toFixed(2) + ' zł';
            const discount = Math.round((1 - product.price / product.price_old) * 100);
            const discountEl = document.getElementById('productDiscount');
            discountEl.textContent = `-${discount}%`;
            discountEl.style.display = 'inline-block';
        }

        if (product.promo_text) {
            const promoEl = document.getElementById('productPromo');
            const promos = product.promo_text.split(',').map(s => s.trim()).filter(Boolean);

            if (promos.length > 0) {
                promoEl.className = 'product-page__promos';
                promoEl.style.display = 'flex';

                promoEl.innerHTML = promos.map(p =>
                    `<div class="product-page__promo" title="Kliknij, aby skopiować" data-promo="${p}">✂️ ${p}</div>`
                ).join('');

                promoEl.querySelectorAll('.product-page__promo').forEach(item => {
                    item.onclick = function (e) {
                        e.preventDefault();
                        navigator.clipboard.writeText(this.dataset.promo).then(() => {
                            const originalHtml = this.innerHTML;
                            this.innerHTML = `✅ Skopiowano!`;
                            setTimeout(() => this.innerHTML = originalHtml, 2000);
                        });
                    };
                });
            }
        }

        document.getElementById('productRating').textContent = `⭐ ${product.rating || '—'}`;
        document.getElementById('productOrders').textContent = `${product.orders || 0} zamówień`;
        document.getElementById('productDescription').textContent = product.description || '';

        const buyBtn = document.getElementById('buyButton');
        buyBtn.href = product.affiliate_link || product.link || '#';
    }

    function startTimer() {
        const totalSeconds = Math.floor(Math.random() * 21600) + 7200;
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
