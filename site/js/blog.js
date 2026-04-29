/**
 * Blog page logic — ShopDoBaksa
 * Handles both blog list and single article views
 * Language: Ukrainian (UA)
 */
(function () {
  'use strict';

  var LANG = 'uk';
  var DATA_PATH = 'data/blog_posts.json';
  var PRODUCTS_PATH = 'data/products.json';

  // --- Helpers ---
  function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function formatDate(iso) {
    if (!iso) return '';
    var d = new Date(iso);
    var months = ['січня', 'лютого', 'березня', 'квітня', 'травня', 'червня',
      'липня', 'серпня', 'вересня', 'жовтня', 'листопада', 'грудня'];
    return d.getDate() + ' ' + months[d.getMonth()] + ' ' + d.getFullYear();
  }

  function getCategoryLabel(cat) {
    var labels = {
      digest: '📊 Дайджест',
      category: '🏷️ Огляд',
      seasonal: '🌿 Сезонний гайд',
      lifehack: '💡 Лайфхак',
      sale: '🔥 Розпродаж'
    };
    return labels[cat] || '📝 Стаття';
  }

  function getCategoryClass(cat) {
    return 'blog-tag--' + (cat || 'default');
  }

  // --- Data Loading ---
  async function loadPosts() {
    var cacheBuster = Math.floor(Date.now() / 300000);
    try {
      var resp = await fetch(DATA_PATH + '?v=' + cacheBuster);
      var data = await resp.json();
      return data.posts || [];
    } catch (e) {
      console.error('Failed to load blog posts:', e);
      return [];
    }
  }

  async function loadProducts() {
    var cacheBuster = Math.floor(Date.now() / 300000);
    try {
      var resp = await fetch(PRODUCTS_PATH + '?v=' + cacheBuster);
      var data = await resp.json();
      return data.products || [];
    } catch (e) {
      return [];
    }
  }

  // --- Blog List Rendering ---
  function renderBlogList(posts, filter) {
    var grid = document.getElementById('blogGrid');
    var emptyState = document.getElementById('blogEmpty');
    if (!grid) return;

    var filtered = posts;
    if (filter && filter !== 'all') {
      filtered = posts.filter(function (p) { return p.type === filter; });
    }

    // Sort by date descending
    filtered.sort(function (a, b) {
      return new Date(b.published_at) - new Date(a.published_at);
    });

    if (filtered.length === 0) {
      grid.innerHTML = '';
      if (emptyState) emptyState.style.display = 'block';
      return;
    }

    if (emptyState) emptyState.style.display = 'none';

    var html = filtered.map(function (post) {
      var coverStyle = post.cover_image
        ? 'background-image: url(' + escapeHtml(post.cover_image) + ')'
        : '';
      var coverClass = post.cover_image ? 'blog-card__cover' : 'blog-card__cover blog-card__cover--empty';

      return '<a href="blog.html?id=' + escapeHtml(post.id) + '" class="blog-card">' +
        '<div class="' + coverClass + '" style="' + coverStyle + '">' +
        '<span class="blog-card__tag ' + getCategoryClass(post.type) + '">' + getCategoryLabel(post.type) + '</span>' +
        '</div>' +
        '<div class="blog-card__body">' +
        '<h2 class="blog-card__title">' + escapeHtml(post.title) + '</h2>' +
        '<p class="blog-card__excerpt">' + escapeHtml(post.excerpt) + '</p>' +
        '<div class="blog-card__meta">' +
        '<span>📅 ' + formatDate(post.published_at) + '</span>' +
        '<span>⏱️ ' + (post.reading_time || 3) + ' хв</span>' +
        '</div>' +
        '</div>' +
        '</a>';
    }).join('');

    grid.innerHTML = html;
  }

  // --- Single Article Rendering ---
  async function renderArticle(posts, postId) {
    var listSection = document.getElementById('blogListSection');
    var articleSection = document.getElementById('blogArticleSection');
    if (!listSection || !articleSection) return;

    var post = posts.find(function (p) { return p.id === postId; });
    if (!post) {
      listSection.style.display = 'none';
      articleSection.innerHTML = '<div class="blog-empty"><h2>Статтю не знайдено 😕</h2><p><a href="blog.html">← Повернутися до блогу</a></p></div>';
      articleSection.style.display = 'block';
      return;
    }

    listSection.style.display = 'none';
    articleSection.style.display = 'block';

    // Update page title and meta
    document.title = post.title + ' — Блог ShopDoBaksa';
    var metaDesc = document.querySelector('meta[name="description"]');
    if (metaDesc) metaDesc.setAttribute('content', post.excerpt || '');

    // OG tags
    var ogTitle = document.querySelector('meta[property="og:title"]');
    if (ogTitle) ogTitle.setAttribute('content', post.title);
    var ogDesc = document.querySelector('meta[property="og:description"]');
    if (ogDesc) ogDesc.setAttribute('content', post.excerpt || '');

    // Render article
    var coverHtml = post.cover_image
      ? '<div class="blog-article__cover"><img src="' + escapeHtml(post.cover_image) + '" alt="' + escapeHtml(post.title) + '"></div>'
      : '';

    var productsHtml = '';
    if (post.products && post.products.length > 0) {
      var allProducts = await loadProducts();
      var relatedProducts = post.products.map(function (pid) {
        return allProducts.find(function (p) { return p.id === pid; });
      }).filter(Boolean);

      if (relatedProducts.length > 0) {
        productsHtml = '<section class="blog-article__products">' +
          '<h3>🛒 Товари зі статті</h3>' +
          '<div class="blog-products-grid">' +
          relatedProducts.map(function (p) {
            var imgSrc = p.image || 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 300"><rect fill="%23161622" width="300" height="300"/><text x="150" y="150" text-anchor="middle" fill="%23444" font-size="14">No Image</text></svg>';
            var link = p.affiliate_link || p.link || '#';
            return '<a href="' + escapeHtml(link) + '" target="_blank" rel="noopener" class="blog-product-card">' +
              '<img src="' + escapeHtml(imgSrc) + '" alt="' + escapeHtml(p.title) + '" loading="lazy">' +
              '<div class="blog-product-card__info">' +
              '<span class="blog-product-card__title">' + escapeHtml(p.title) + '</span>' +
              '<span class="blog-product-card__price">$' + (p.price || 0).toFixed(2) + '</span>' +
              '</div>' +
              '</a>';
          }).join('') +
          '</div>' +
          '</section>';
      }
    }

    articleSection.innerHTML =
      '<nav class="breadcrumbs" aria-label="Навігація">' +
      '<a href="index.html" class="breadcrumbs__link">Головна</a>' +
      '<span class="breadcrumbs__sep">›</span>' +
      '<a href="blog.html" class="breadcrumbs__link">Блог</a>' +
      '<span class="breadcrumbs__sep">›</span>' +
      '<span class="breadcrumbs__current">' + escapeHtml(post.title) + '</span>' +
      '</nav>' +
      coverHtml +
      '<article class="blog-article">' +
      '<div class="blog-article__header">' +
      '<span class="blog-card__tag ' + getCategoryClass(post.type) + '">' + getCategoryLabel(post.type) + '</span>' +
      '<h1 class="blog-article__title">' + escapeHtml(post.title) + '</h1>' +
      '<div class="blog-article__meta">' +
      '<span>📅 ' + formatDate(post.published_at) + '</span>' +
      '<span>⏱️ ' + (post.reading_time || 3) + ' хв читання</span>' +
      '</div>' +
      '</div>' +
      '<div class="blog-article__content">' + (post.content || '') + '</div>' +
      productsHtml +
      '<div class="blog-article__footer">' +
      '<a href="blog.html" class="blog-article__back">← Усі статті</a>' +
      '<div class="blog-article__share">' +
      '<span>Поділитися:</span>' +
      '<a href="https://t.me/share/url?url=' + encodeURIComponent('https://dobaksa.shop/blog.html?id=' + post.id) + '&text=' + encodeURIComponent(post.title) + '" target="_blank" rel="noopener" class="blog-share-btn">✈️ Telegram</a>' +
      '</div>' +
      '</div>' +
      '</article>';
  }

  // --- Filters ---
  function initFilters(posts) {
    var buttons = document.querySelectorAll('.blog-filter-btn');
    buttons.forEach(function (btn) {
      btn.addEventListener('click', function () {
        buttons.forEach(function (b) { b.classList.remove('active'); });
        btn.classList.add('active');
        var filter = btn.getAttribute('data-filter');
        renderBlogList(posts, filter);
      });
    });
  }

  // --- Init ---
  async function init() {
    var posts = await loadPosts();
    var params = new URLSearchParams(window.location.search);
    var postId = params.get('id');

    if (postId) {
      await renderArticle(posts, postId);
    } else {
      renderBlogList(posts, 'all');
      initFilters(posts);

      // Update stats
      var statsEl = document.getElementById('blogStatsCount');
      if (statsEl) statsEl.textContent = posts.length;
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
