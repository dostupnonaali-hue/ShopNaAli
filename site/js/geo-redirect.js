/**
 * Geo-redirect for Polish visitors
 * Detects visitor country by IP and redirects to /pl/ for Polish users
 */
(function() {
    'use strict';

    // Skip if already on Polish page
    if (window.location.pathname.startsWith('/pl')) return;

    // Skip if user explicitly chose Ukrainian (via ?lang=uk parameter)
    var params = new URLSearchParams(window.location.search);
    if (params.get('lang') === 'uk') {
        localStorage.setItem('dobaksa_lang', 'uk');
        return;
    }

    // Check if user already made a language choice
    var savedLang = localStorage.getItem('dobaksa_lang');
    if (savedLang === 'uk') return;
    if (savedLang === 'pl') {
        window.location.replace('/pl/');
        return;
    }

    // Detect country via free IP geolocation API
    fetch('https://ipapi.co/json/', { cache: 'no-store' })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data && data.country_code === 'PL') {
                localStorage.setItem('dobaksa_lang', 'pl');
                window.location.replace('/pl/');
            } else {
                // Remember that user is not from Poland
                localStorage.setItem('dobaksa_lang', 'uk');
            }
        })
        .catch(function() {
            // On error, default to Ukrainian — don't redirect
        });
})();
