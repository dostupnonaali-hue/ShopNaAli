"""
Blog Post Generator for ShopDoBaksa
Generates blog posts from products.json data using Gemini AI + templates.
Pushes results to GitHub as blog_posts.json.

Usage:
  python blog_generator.py --type digest       # Weekly digest
  python blog_generator.py --type category     # Category spotlight
  python blog_generator.py --type lifehack     # Lifehack article
  python blog_generator.py --type seasonal     # Seasonal guide
  python blog_generator.py --type sale         # Sale announcement
  python blog_generator.py --dry-run           # Preview without pushing
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Load environment
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / '.env')

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN', '')
GITHUB_REPO = os.getenv('GITHUB_REPO', 'dostupnonaali-hue/ShopNaAli')
BLOG_JSON_PATH = 'site/data/blog_posts.json'
PRODUCTS_JSON_PATH = 'site/data/products.json'

# --- Gemini AI ---
GEMINI_MODEL = 'gemini-2.5-flash'
GEMINI_URL = f'https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent'


def gemini_generate(prompt: str, max_retries: int = 3, max_tokens: int = 4096) -> str:
    """Generate text using Gemini API."""
    if not GEMINI_API_KEY:
        print('[WARN] No GEMINI_API_KEY, using template fallback')
        return ''

    payload = {
        'contents': [{'parts': [{'text': prompt}]}],
        'generationConfig': {
            'temperature': 0.8,
            'maxOutputTokens': max_tokens,
        }
    }

    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(
                f'{GEMINI_URL}?key={GEMINI_API_KEY}',
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
                text = data['candidates'][0]['content']['parts'][0]['text']
                return text.strip()
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = (attempt + 1) * 15
                print(f'[WARN] Rate limited, waiting {wait}s...')
                time.sleep(wait)
            else:
                print(f'[ERROR] Gemini API error {e.code}: {e.read().decode()[:200]}')
                return ''
        except Exception as e:
            print(f'[ERROR] Gemini request failed: {e}')
            if attempt < max_retries - 1:
                time.sleep(5)
    return ''


def translate_to_polish(text: str) -> str:
    """Translate text to Polish using Gemini, converting prices to PLN."""
    if not text:
        return ''
    # First convert currency in HTML content
    text_with_pln = convert_prices_to_pln(text)
    prompt = f"""Translate the following Ukrainian HTML content to Polish. 
Keep all HTML tags intact. Only translate the text content.
Do NOT add any explanation, just output the translated HTML.

{text_with_pln}"""
    result = gemini_generate(prompt, max_tokens=8192)
    # Clean up possible markdown wrapping
    result = re.sub(r'^```html?\s*\n?', '', result)
    result = re.sub(r'\n?```\s*$', '', result)
    return result.strip()


# --- PLN Exchange Rates ---
PLN_RATES = {'USD': 4.05, 'UAH': 0.098}  # Fallback rates


def fetch_pln_rates():
    """Fetch current PLN exchange rates."""
    global PLN_RATES
    try:
        req = urllib.request.Request('https://api.exchangerate-api.com/v4/latest/USD')
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            if data and 'rates' in data:
                PLN_RATES['USD'] = data['rates'].get('PLN', 4.05)
                uah_rate = data['rates'].get('UAH', 41.0)
                PLN_RATES['UAH'] = PLN_RATES['USD'] / uah_rate
                print(f'   PLN rates: 1 USD = {PLN_RATES["USD"]:.2f} PLN, 1 UAH = {PLN_RATES["UAH"]:.4f} PLN')
    except Exception as e:
        print(f'[WARN] Using fallback PLN rates: {e}')


def to_pln(price: float, currency: str = 'USD') -> float:
    """Convert price to PLN."""
    if currency == 'UAH':
        return price * PLN_RATES['UAH']
    return price * PLN_RATES['USD']


def convert_prices_to_pln(html: str) -> str:
    """Replace ₴ and $ price patterns in HTML with PLN equivalents."""
    import re
    # Replace patterns like "₴123" or "123 ₴" or "$12.34"
    def replace_uah(m):
        val = float(m.group(1))
        pln = val * PLN_RATES['UAH']
        return f'{pln:.2f} zł'

    def replace_usd(m):
        val = float(m.group(1))
        pln = val * PLN_RATES['USD']
        return f'{pln:.2f} zł'

    # ₴123 or ₴123.45
    html = re.sub(r'₴(\d+\.?\d*)', replace_uah, html)
    # 123 ₴
    html = re.sub(r'(\d+\.?\d*)\s*₴', replace_uah, html)
    # $12.34
    html = re.sub(r'\$(\d+\.?\d*)', replace_usd, html)
    return html


# --- GitHub API ---
def github_get_file(path: str):
    """Get file content and SHA from GitHub."""
    # Get SHA via Contents API
    api_url = f'https://api.github.com/repos/{GITHUB_REPO}/contents/{path}'
    req = urllib.request.Request(api_url, headers={
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'ShopDoBaksa-BlogGenerator',
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            meta = json.loads(resp.read())
            sha = meta.get('sha')
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None, None
        raise

    # Get content via raw URL (works for large files)
    raw_url = f'https://raw.githubusercontent.com/{GITHUB_REPO}/main/{path}'
    req2 = urllib.request.Request(raw_url)
    try:
        with urllib.request.urlopen(req2, timeout=30) as resp:
            content = json.loads(resp.read())
            return content, sha
    except Exception:
        return None, sha


def github_put_file(path: str, content: str, sha: str = None, message: str = ''):
    """Create or update a file on GitHub."""
    import base64
    api_url = f'https://api.github.com/repos/{GITHUB_REPO}/contents/{path}'
    payload = {
        'message': message or f'blog: update {path}',
        'content': base64.b64encode(content.encode('utf-8')).decode('ascii'),
    }
    if sha:
        payload['sha'] = sha

    req = urllib.request.Request(
        api_url,
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Authorization': f'token {GITHUB_TOKEN}',
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'ShopDoBaksa-BlogGenerator',
            'Content-Type': 'application/json',
        },
        method='PUT',
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


# --- Products Data ---
def load_products():
    """Load products — local first, GitHub fallback."""
    # Try local file first (fast)
    local = Path(__file__).parent.parent / 'site' / 'data' / 'products.json'
    if local.exists():
        print('   Loading products from local file...')
        with open(local, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('products', [])
    # Fallback: GitHub
    print('   Loading products from GitHub...')
    data, _ = github_get_file(PRODUCTS_JSON_PATH)
    if data and 'products' in data:
        return data['products']
    return []


def load_blog_posts():
    """Load existing blog posts from GitHub."""
    data, sha = github_get_file(BLOG_JSON_PATH)
    if data and 'posts' in data:
        return data['posts'], sha
    return [], sha


# --- Slug Generation ---
def make_slug(title: str) -> str:
    """Generate URL-friendly slug from title."""
    # Transliterate Ukrainian
    translit = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'h', 'ґ': 'g', 'д': 'd', 'е': 'e',
        'є': 'ye', 'ж': 'zh', 'з': 'z', 'и': 'y', 'і': 'i', 'ї': 'yi', 'й': 'y',
        'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r',
        'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch',
        'ш': 'sh', 'щ': 'shch', 'ь': '', 'ю': 'yu', 'я': 'ya', 'ъ': '', 'ы': 'y',
        'э': 'e',
    }
    slug = title.lower()
    result = []
    for ch in slug:
        if ch in translit:
            result.append(translit[ch])
        elif ch.isascii() and (ch.isalnum() or ch == ' ' or ch == '-'):
            result.append(ch)
        else:
            result.append(' ')
    slug = '-'.join(''.join(result).split())
    slug = re.sub(r'-+', '-', slug).strip('-')
    return slug[:80]


# --- Post Generators ---

CATEGORY_NAMES_UK = {
    'electronics': 'Електроніка',
    'home': 'Дім та кухня',
    'fashion': 'Мода та одяг',
    'beauty': 'Краса та догляд',
    'accessories': 'Аксесуари',
    'sport': 'Спорт та туризм',
    'toys': 'Іграшки та діти',
    'tools': 'Інструменти',
    'auto': 'Авто',
}

TIPS_UK = [
    'Використовуйте монети (Coins) для додаткової знижки — іноді до 95%!',
    'Додайте товар у кошик і зачекайте 1-2 дні — часто з\'являється купон.',
    'Перевіряйте розділ "Центр купонів" — там завжди є приховані знижки.',
    'Комбінуйте промокод + купон магазину + монети для максимальної економії.',
    'Замовляйте Choice-товари для безкоштовної доставки.',
    'Підписуйтесь на улюблені магазини — вони дарують купони підписникам.',
    'Перед оплатою завжди перевіряйте вкладку "Отримати купони" у кошику.',
    'Порівнюйте ціни в додатку та на сайті — іноді відрізняються.',
]


def generate_digest(products: list) -> dict:
    """Generate weekly TOP-10 digest."""
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    week_start = week_ago.strftime('%d.%m')
    week_end = now.strftime('%d.%m')

    # Get recent products, sorted by rating * orders
    recent = [p for p in products if p.get('added_at', '') >= week_ago.isoformat()[:10]]
    if len(recent) < 5:
        recent = products  # Use all if not enough recent

    scored = sorted(recent, key=lambda p: (p.get('rating', 0) * p.get('orders', 0)), reverse=True)
    top10 = scored[:10]
    top_ids = [p['id'] for p in top10]

    title = f'ТОП-10 знахідок тижня: {week_start} – {week_end}'
    import random
    tip = random.choice(TIPS_UK)

    # Build content HTML
    items_html = ''
    for i, p in enumerate(top10, 1):
        price = f"${p.get('price', 0):.2f}" if p.get('currency') == 'USD' else f"{p.get('price', 0):.0f} ₴"
        cat = CATEGORY_NAMES_UK.get(p.get('category', ''), 'Інше')
        promo = f' | Промокод: <strong>{p["promo_text"]}</strong>' if p.get('promo_text') else ''
        items_html += f'<p><strong>{i}. {p.get("title", "Товар")}</strong> — {price} ⭐{p.get("rating", 4.8)}{promo}<br><em>{cat} | {p.get("orders", 0)} замовлень</em></p>\n'

    # Generate intro with AI
    ai_intro = ''
    if GEMINI_API_KEY:
        product_names = ', '.join([p.get('title', '')[:40] for p in top10[:5]])
        prompt = f"""Напиши короткий вступ (2-3 речення) для щотижневого дайджесту знахідок з AliExpress.
Дайджест за період {week_start} – {week_end}. Серед товарів: {product_names}.
Пиши українською, дружнім тоном. Не використовуй markdown. Тільки чистий текст."""
        ai_intro = gemini_generate(prompt)
        if ai_intro:
            ai_intro = f'<p>{ai_intro}</p>\n'

    content = f"""{ai_intro}<h2>🏆 Найкращі знахідки тижня</h2>
{items_html}
<h2>💡 Порада тижня</h2>
<blockquote>{tip}</blockquote>

<p>Усі товари доступні в нашому <a href="/index.html">каталозі</a>. Підписуйтесь на <a href="https://t.me/Shop_DoBaksa">Telegram</a>, щоб отримувати знахідки першими!</p>"""

    excerpt = f'Зібрали {len(top10)} найцікавіших товарів цього тижня. Від {top10[0].get("title", "гаджетів")[:30]} до {top10[-1].get("title", "аксесуарів")[:30]}.'

    # Translate to Polish
    title_pl = translate_to_polish(title)
    excerpt_pl = translate_to_polish(excerpt)
    content_pl = translate_to_polish(content)

    return {
        'id': make_slug(title),
        'type': 'digest',
        'title': title,
        'title_pl': title_pl,
        'excerpt': excerpt,
        'excerpt_pl': excerpt_pl,
        'content': content,
        'content_pl': content_pl,
        'cover_image': '',
        'category': 'digest',
        'tags': ['дайджест', 'топ', 'тиждень'],
        'products': top_ids,
        'published_at': now.isoformat(),
        'reading_time': 4,
    }


def generate_category_spotlight(products: list, category: str = None) -> dict:
    """Generate a category spotlight article."""
    import random

    # Pick category
    if not category:
        categories = list(set(p.get('category', 'new') for p in products if p.get('category') != 'new'))
        category = random.choice(categories) if categories else 'electronics'

    cat_name = CATEGORY_NAMES_UK.get(category, category.title())
    cat_products = [p for p in products if p.get('category') == category]
    cat_products.sort(key=lambda p: p.get('orders', 0), reverse=True)
    top = cat_products[:8]
    top_ids = [p['id'] for p in top]

    now = datetime.now(timezone.utc)
    month_names = ['Січень', 'Лютий', 'Березень', 'Квітень', 'Травень', 'Червень',
                   'Липень', 'Серпень', 'Вересень', 'Жовтень', 'Листопад', 'Грудень']
    month = month_names[now.month - 1]

    title = f'Найкращі товари: {cat_name} — {month} {now.year}'

    # AI content
    content = ''
    if GEMINI_API_KEY:
        product_list = '\n'.join([f'- {p.get("title", "")} ({"₴" if p.get("currency") == "UAH" else "$"}{p.get("price", 0):.2f}, {p.get("orders", 0)} замовлень)' for p in top])
        prompt = f"""Напиши статтю-огляд категорії "{cat_name}" на AliExpress за {month} {now.year}.

Ось топ товари цієї категорії:
{product_list}

Структура статті (у HTML, без markdown):
1. <h2>Вступ</h2> — 2-3 речення про категорію
2. <h2>Топ товари</h2> — коротко опиши кожен товар (1-2 речення), чому він цікавий
3. <h2>Поради при покупці</h2> — 3-4 поради специфічні для цієї категорії
4. <h2>Підсумок</h2> — коротке резюме

Пиши українською, дружнім тоном. Виводи лише HTML без обгортки у ```."""
        content = gemini_generate(prompt)
        content = re.sub(r'^```html?\s*\n?', '', content)
        content = re.sub(r'\n?```\s*$', '', content)

    if not content:
        items_html = ''
        for p in top:
            cur = '₴' if p.get('currency') == 'UAH' else '$'
            price = f"{cur}{p.get('price', 0):.2f}"
            items_html += f'<p><strong>{p.get("title", "Товар")}</strong> — {price} | ⭐{p.get("rating", 4.8)} | {p.get("orders", 0)} замовлень</p>\n'
        content = f"""<h2>Огляд категорії: {cat_name}</h2>
<p>У категорії "{cat_name}" на AliExpress зараз {len(cat_products)} товарів у нашому каталозі. Ось найпопулярніші:</p>
<h2>🏆 Топ товари</h2>
{items_html}
<p>Переглянути всі товари категорії можна в нашому <a href="/index.html">каталозі</a>.</p>"""

    excerpt = f'Огляд {len(cat_products)} товарів категорії "{cat_name}". Найкращі знахідки та поради при покупці.'

    title_pl = translate_to_polish(title)
    excerpt_pl = translate_to_polish(excerpt)
    content_pl = translate_to_polish(content)

    return {
        'id': make_slug(title),
        'type': 'category',
        'title': title,
        'title_pl': title_pl,
        'excerpt': excerpt,
        'excerpt_pl': excerpt_pl,
        'content': content,
        'content_pl': content_pl,
        'cover_image': '',
        'tags': [cat_name.lower(), 'огляд', 'категорія'],
        'products': top_ids,
        'published_at': now.isoformat(),
        'reading_time': 5,
    }


def generate_lifehack(products: list) -> dict:
    """Generate a lifehack/tips article using AI."""
    now = datetime.now(timezone.utc)

    topics = [
        ('Як отримати знижку до 95% монетами на AliExpress', 'монети, знижки, coins, AliExpress лайфхак'),
        ('5 способів отримати безкоштовну доставку з AliExpress', 'доставка, Choice, безкоштовно'),
        ('Як правильно використовувати промокоди на AliExpress', 'промокоди, купони, знижки'),
        ('Що робити якщо товар з AliExpress не прийшов', 'спір, диспут, повернення грошей'),
        ('Як знайти найдешевші товари на AliExpress', 'дешеві товари, до 1 долара, DoBaksa'),
        ('Секрети вигідних покупок на AliExpress для початківців', 'поради, новачки, гайд'),
    ]

    import random
    topic_title, tags = random.choice(topics)

    content = ''
    if GEMINI_API_KEY:
        prompt = f"""Напиши детальну статтю-лайфхак на тему: "{topic_title}"

Вимоги:
- Формат: HTML (без markdown, без обгортки ```)
- Використовуй теги: <h2>, <h3>, <p>, <ul>, <li>, <strong>, <blockquote>
- Довжина: 800-1200 слів
- Мова: українська
- Тон: дружній, практичний
- Додай конкретні покрокові інструкції
- Згадай сайт ShopDoBaksa як корисний ресурс
- Не використовуй емодзі в тексті (тільки в заголовках h2/h3 якщо доречно)"""

        content = gemini_generate(prompt)
        content = re.sub(r'^```html?\s*\n?', '', content)
        content = re.sub(r'\n?```\s*$', '', content)

    if not content:
        content = f"""<h2>{topic_title}</h2>
<p>Ця стаття містить перевірені поради та лайфхаки для покупок на AliExpress. Слідкуйте за оновленнями у нашому блозі!</p>
<p>Більше знахідок — у нашому <a href="/index.html">каталозі</a>.</p>"""

    excerpt = f'{topic_title}. Перевірені поради та покрокові інструкції.'

    title_pl = translate_to_polish(topic_title)
    excerpt_pl = translate_to_polish(excerpt)
    content_pl = translate_to_polish(content)

    return {
        'id': make_slug(topic_title),
        'type': 'lifehack',
        'title': topic_title,
        'title_pl': title_pl,
        'excerpt': excerpt,
        'excerpt_pl': excerpt_pl,
        'content': content,
        'content_pl': content_pl,
        'cover_image': '',
        'tags': [t.strip() for t in tags.split(',')],
        'products': [],
        'published_at': now.isoformat(),
        'reading_time': 6,
    }


def generate_baseus_review(products: list) -> dict:
    """Generate a Baseus brand review article with inline product links (no cards)."""
    import random
    now = datetime.now(timezone.utc)

    # Filter Baseus products
    baseus = [p for p in products if 'baseus' in (p.get('title', '') + p.get('brand', '')).lower()]
    if not baseus:
        print('[ERROR] No Baseus products found!')
        return None

    # Sort by popularity
    baseus.sort(key=lambda p: p.get('orders', 0), reverse=True)

    # Pick 5-8 products for the article
    count = min(random.randint(5, 8), len(baseus))
    selected = baseus[:count]

    # Build product info for AI prompt
    product_info = ''
    for i, p in enumerate(selected, 1):
        cur = '₴' if p.get('currency') == 'UAH' else '$'
        price = f"{cur}{p.get('price', 0):.2f}"
        link = p.get('affiliate_link', p.get('link', '#'))
        product_info += f"{i}. {p.get('title', 'Товар')} — {price}, {p.get('orders', 0)} замовлень, рейтинг {p.get('rating', 4.5)}\n"
        product_info += f"   Посилання: {link}\n\n"

    # Generate with AI
    content = ''
    if GEMINI_API_KEY:
        prompt = f"""Напиши детальну статтю-огляд продукції бренду Baseus з AliExpress.

Ось товари для огляду (включи посилання на кожен товар у тексті статті як HTML-посилання):
{product_info}

Вимоги:
- Формат: HTML (без markdown, без обгортки ```)
- Використовуй теги: <h2>, <h3>, <p>, <ul>, <li>, <strong>, <blockquote>, <a>
- Вставляй посилання на товари ПРЯМО в текст статті, наприклад: <a href="ПОСИЛАННЯ" target="_blank" rel="noopener">Назва товару</a>
- НЕ створюй список товарів окремо — згадуй товари органічно в тексті
- Довжина: 800-1200 слів
- Мова: українська
- Тон: експертний, але дружній
- Структура:
  1. Вступ про бренд Baseus (чому він популярний, якість, сертифікація)
  2. Огляд кожного товару з описом переваг (вбудовуй посилання)
  3. Порівняння з конкурентами
  4. Поради при виборі аксесуарів Baseus
  5. Підсумок та рекомендації
- Згадай ShopDoBaksa та наш Telegram канал
- Додай емодзі лише в заголовки h2/h3"""

        content = gemini_generate(prompt)
        content = re.sub(r'^```html?\s*\n?', '', content)
        content = re.sub(r'\n?```\s*$', '', content)

    if not content:
        # Fallback template with inline links
        items_html = ''
        for p in selected:
            cur = '₴' if p.get('currency') == 'UAH' else '$'
            price = f"{cur}{p.get('price', 0):.2f}"
            link = p.get('affiliate_link', p.get('link', '#'))
            items_html += f'<p><a href="{link}" target="_blank" rel="noopener"><strong>{p.get("title", "Товар")}</strong></a> — {price}, ⭐{p.get("rating", 4.8)}, {p.get("orders", 0)} замовлень.</p>\n'
        content = f"""<h2>🔋 Baseus — бренд якому довіряють мільйони</h2>
<p>Baseus — один з найвідоміших брендів аксесуарів на AliExpress. Компанія спеціалізується на кабелях, зарядних пристроях, павербанках та аудіо-аксесуарах.</p>
<h2>🏆 Найкращі товари Baseus</h2>
{items_html}
<p>Більше товарів Baseus — на нашій <a href="/baseus.html">сторінці Baseus</a>.</p>"""

    # Create titles
    themes = [
        f'Огляд найкращих аксесуарів Baseus — {now.strftime("%B %Y")}',
        f'Топ {count} товарів Baseus з AliExpress: що варто купити',
        f'Baseus: аксесуари преміум якості за доступною ціною',
        f'Чому Baseus — найпопулярніший бренд аксесуарів на AliExpress',
    ]
    title = random.choice(themes)
    excerpt = f'Детальний огляд {count} найкращих товарів Baseus з AliExpress. Кабелі, зарядки, павербанки та не тільки.'

    # Translate to Polish (with PLN conversion)
    title_pl = translate_to_polish(title)
    excerpt_pl = translate_to_polish(excerpt)
    content_pl = translate_to_polish(content)

    return {
        'id': make_slug(title),
        'type': 'category',
        'title': title,
        'title_pl': title_pl,
        'excerpt': excerpt,
        'excerpt_pl': excerpt_pl,
        'content': content,
        'content_pl': content_pl,
        'cover_image': '',
        'tags': ['baseus', 'огляд', 'аксесуари', 'бренд'],
        'products': [],  # Empty! No product cards — links are inline
        'published_at': now.isoformat(),
        'reading_time': 7,
    }


# --- Main ---
def main():
    parser = argparse.ArgumentParser(description='Blog post generator for ShopDoBaksa')
    parser.add_argument('--type', choices=['digest', 'category', 'lifehack', 'baseus', 'seasonal', 'sale'],
                        default='digest', help='Type of post to generate')
    parser.add_argument('--category', help='Category for spotlight (e.g. electronics)')
    parser.add_argument('--dry-run', action='store_true', help='Preview without pushing to GitHub')
    args = parser.parse_args()

    print(f'📝 Generating blog post: {args.type}')
    print(f'   Gemini API: {"✅" if GEMINI_API_KEY else "❌ (template mode)"}')
    print(f'   GitHub: {"✅" if GITHUB_TOKEN else "❌"}')

    # Load products
    products = load_products()
    print(f'   Products loaded: {len(products)}')

    # Fetch PLN rates for Polish content
    fetch_pln_rates()

    # Generate post
    if args.type == 'digest':
        post = generate_digest(products)
    elif args.type == 'category':
        post = generate_category_spotlight(products, args.category)
    elif args.type == 'lifehack':
        post = generate_lifehack(products)
    elif args.type == 'baseus':
        post = generate_baseus_review(products)
        if not post:
            sys.exit(1)
    else:
        print(f'[ERROR] Type "{args.type}" not yet implemented')
        sys.exit(1)

    print(f'\n✅ Generated: "{post["title"]}"')
    print(f'   ID: {post["id"]}')
    print(f'   Type: {post["type"]}')
    print(f'   Products: {len(post.get("products", []))}')
    print(f'   Reading time: {post["reading_time"]} min')
    print(f'   PL title: {post.get("title_pl", "—")}')

    if args.dry_run:
        print('\n--- DRY RUN: Content preview ---')
        print(f'Title: {post["title"]}')
        print(f'Excerpt: {post["excerpt"]}')
        print(f'Content length: {len(post.get("content", ""))} chars')
        print(f'Content PL length: {len(post.get("content_pl", ""))} chars')

        # Save locally for inspection
        preview_path = Path(__file__).parent / 'blog_preview.json'
        with open(preview_path, 'w', encoding='utf-8') as f:
            json.dump(post, f, ensure_ascii=False, indent=2)
        print(f'\nPreview saved to: {preview_path}')
        return

    # Load existing posts and add new one
    existing_posts, sha = load_blog_posts()

    # Check for duplicate
    if any(p['id'] == post['id'] for p in existing_posts):
        print(f'[WARN] Post with ID "{post["id"]}" already exists, updating...')
        existing_posts = [p for p in existing_posts if p['id'] != post['id']]

    existing_posts.insert(0, post)  # Add to beginning (newest first)

    # Keep max 50 posts
    if len(existing_posts) > 50:
        existing_posts = existing_posts[:50]

    # Push to GitHub
    blog_json = json.dumps({'posts': existing_posts}, ensure_ascii=False, indent=2)
    print(f'\nPushing to GitHub ({len(existing_posts)} total posts)...')
    github_put_file(
        BLOG_JSON_PATH,
        blog_json,
        sha,
        f'blog: add {post["type"]} — {post["title"][:50]}'
    )
    print('✅ Published successfully!')


if __name__ == '__main__':
    main()
