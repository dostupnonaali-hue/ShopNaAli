/**
 * ShopDoBaksa - Promos Page Dynamic Codes (Polish)
 * Loads promo codes from promos.json and renders them
 */
(function () {
    'use strict';

    var container = document.getElementById('parserPromos');
    var statsCount = document.getElementById('promoStatsCount');
    if (!container) return;

    async function init() {
        try {
            var cacheBuster = Math.floor(Date.now() / 300000);
            var resp = await fetch('../data/promos.json?v=' + cacheBuster);
            if (!resp.ok) throw new Error('Failed to load promos');
            var data = await resp.json();
            var promos = data.promos || [];

            if (statsCount) statsCount.textContent = promos.length;

            if (promos.length === 0) {
                container.innerHTML = '<p style="color:var(--text-muted);text-align:center;">Brak kodów rabatowych</p>';
                return;
            }

            container.innerHTML = promos.map(function(p) {
                var lastDate = formatDate(p.last_seen);
                var popularity = p.times_seen >= 10 ? '🔥' : (p.times_seen >= 5 ? '⭐' : '');

                return '<div class="promo-card promo-card--parser">' +
                    '<div class="promo-card__top">' +
                        '<span class="promo-card__badge-pop">' + popularity + ' ' + p.times_seen + 'x</span>' +
                        '<span class="promo-card__date">📅 ' + lastDate + '</span>' +
                    '</div>' +
                    '<div class="promo-card__code-wrap" onclick="copyCode(\'' + escapeAttr(p.code) + '\')" title="Kliknij, aby skopiować">' +
                        '<span class="promo-card__code">' + escapeHtml(p.code) + '</span>' +
                        '<button class="promo-card__copy" aria-label="Kopiuj">📋</button>' +
                    '</div>' +
                '</div>';
            }).join('');

        } catch (err) {
            console.warn('Promos not loaded:', err.message);
            container.innerHTML = '<p style="color:var(--text-muted);text-align:center;">Nie udało się załadować kodów</p>';
        }
    }

    function formatDate(dateStr) {
        if (!dateStr) return '';
        var parts = dateStr.split('-');
        if (parts.length !== 3) return dateStr;
        return parts[2] + '.' + parts[1] + '.' + parts[0];
    }

    function escapeHtml(str) {
        var div = document.createElement('div');
        div.textContent = str || '';
        return div.innerHTML;
    }

    function escapeAttr(str) {
        return (str || '').replace(/'/g, "\\'").replace(/"/g, '&quot;');
    }

    document.addEventListener('DOMContentLoaded', init);
})();
