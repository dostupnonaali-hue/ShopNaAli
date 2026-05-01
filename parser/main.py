"""
Shop Na Ali — Telegram Channel Copier
Monitors donor channels, resolves AliExpress shortlinks,
removes referral parameters, copies messages to target channel,
and saves products to GitHub for the website.
"""
import asyncio
import json
import os
import re
import base64
import logging
import random
from datetime import datetime, timezone
from PIL import Image
import pytesseract

from telethon import TelegramClient, events
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument, MessageMediaWebPage
import aiohttp

try:
    from deep_translator import GoogleTranslator
    _translator = GoogleTranslator(source='auto', target='uk')
    _translator_pl = GoogleTranslator(source='auto', target='pl')
except ImportError:
    _translator = None
    _translator_pl = None

from config import (
    API_ID, API_HASH, SESSION_NAME,
    DONOR_CHANNELS, TARGET_CHANNEL,
    SEEN_DB, IMAGES_DIR,
    GITHUB_TOKEN, GITHUB_REPO, GITHUB_PRODUCTS_PATH,
    AFF_SHORT_KEY, REDIRECT_PATTERNS,
)

# --- Proxy for AliExpress scraping ---
PROXY_URL = os.getenv('PROXY_URL', '')  # proxy expired 12.04.2026, disabled


# --- Proxy for AliExpress scraping ---

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
log = logging.getLogger('copier')

# --- Title translation & cleanup ---
def clean_and_translate_title(raw_title: str) -> str:
    """
    Clean AliExpress title: remove specs, model numbers, sizes, colors.
    Then translate to Ukrainian.
    """
    if not raw_title or len(raw_title) < 3:
        return raw_title
    
    title = raw_title
    
    # Remove content in 【】brackets (usually model/SKU)
    title = re.sub(r'【[^】]*】', '', title)
    # Remove content in square brackets
    title = re.sub(r'\[[^\]]*\]', '', title)
    
    # Remove size/dimension ranges (e.g., "S-5XL", "100x200cm", "36-48")
    title = re.sub(r'\b\d+[xX×]\d+\s*(?:cm|mm|m|inch)?\b', '', title)
    title = re.sub(r'\b(?:XS|S|M|L|XL|XXL|XXXL|2XL|3XL|4XL|5XL)(?:\s*[-–~]\s*(?:XS|S|M|L|XL|XXL|XXXL|2XL|3XL|4XL|5XL))?\b', '', title)
    title = re.sub(r'\b\d{2,3}\s*[-–]\s*\d{2,3}\b', '', title)
    
    # Remove volume/weight specs (e.g., "500ml", "200g")
    title = re.sub(r'\b\d+\s*(?:ml|pcs|pcs|шт|g|kg|oz|cm|mm|W|V|mAh|dBi?)\b', '', title, flags=re.IGNORECASE)
    
    # Remove color lists (e.g., "Black/White/Red")
    color_words = r'(?:Black|White|Red|Blue|Green|Pink|Purple|Yellow|Grey|Gray|Brown|Orange|Beige|Khaki|Navy|Gold|Silver)'
    title = re.sub(rf'{color_words}(?:\s*/\s*{color_words})+', '', title, flags=re.IGNORECASE)
    # Remove standalone color word at end
    title = re.sub(rf'\s+{color_words}\s*$', '', title, flags=re.IGNORECASE)
    
    # Remove "For" target phrases at end (e.g., "For iPhone 15 Pro Max")
    title = re.sub(r'\s+[Ff]or\s+(?:iPhone|Samsung|Xiaomi|Huawei|iPad|MacBook|Android|iOS).*$', '', title)
    
    # Clean up multiple spaces and trailing junk
    title = re.sub(r'\s+', ' ', title).strip(' ,.-/|&+')
    
    # Limit to ~60 chars at word boundary  
    if len(title) > 60:
        cut = title[:60].rfind(' ')
        if cut > 20:
            title = title[:cut]
    
    if not title or len(title) < 5:
        title = raw_title[:60]
    
    # Translate to Ukrainian
    if _translator:
        try:
            translated = _translator.translate(title)
            if translated and len(translated) > 3:
                # Capitalize first letter
                title = translated[0].upper() + translated[1:] if len(translated) > 1 else translated.upper()
                log.info(f'🌐 Translated: "{raw_title[:40]}..." → "{title}"')
        except Exception as e:
            log.warning(f'🌐 Translation failed: {e}')
    
    return title

def translate_to_polish(title: str) -> str:
    """Translate a product title to Polish."""
    if not title or len(title) < 3 or not _translator_pl:
        return ''
    try:
        translated = _translator_pl.translate(title)
        if translated and len(translated) > 3:
            translated = translated[0].upper() + translated[1:] if len(translated) > 1 else translated.upper()
            log.info(f'🇵🇱 Polish: "{title[:40]}..." → "{translated}"')
            return translated
    except Exception as e:
        log.warning(f'🇵🇱 Polish translation failed: {e}')
    return ''

# --- User-Agent rotation for scraping ---
_USER_AGENTS_DESKTOP = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:132.0) Gecko/20100101 Firefox/132.0',
]
_USER_AGENTS_MOBILE = [
    'Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (Linux; Android 14; SM-A546B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36',
    'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36',
]
_USER_AGENTS = _USER_AGENTS_DESKTOP + _USER_AGENTS_MOBILE

# --- Ensure directories ---
os.makedirs(IMAGES_DIR, exist_ok=True)

# --- Deduplication (dict: {item_id: price}) ---
def load_seen():
    """Load seen products. Supports both old format (list) and new format (dict {id: price})."""
    if os.path.exists(SEEN_DB):
        try:
            with open(SEEN_DB, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # Old format: list of IDs → migrate to dict with price=0
            if isinstance(data, list):
                log.info(f'📦 Migrating seen_products from list ({len(data)} items) to dict format')
                return {str(pid): 0 for pid in data}
            # New format: dict {id: price}
            if isinstance(data, dict):
                return data
        except Exception:
            return {}
    return {}

def save_seen(seen_dict):
    with open(SEEN_DB, 'w', encoding='utf-8') as f:
        json.dump(seen_dict, f)

seen_products = load_seen()

def make_affiliate_link(item_id: str) -> str:
    """Build an AliExpress affiliate deep link for a given item ID."""
    clean = f'https://aliexpress.com/item/{item_id}.html'
    if AFF_SHORT_KEY:
        from urllib.parse import quote
        return f'https://s.click.aliexpress.com/deep_link.htm?aff_short_key={AFF_SHORT_KEY}&dl_target_url={quote(clean, safe="")}'
    return clean

async def resolve_and_clean_url(url: str, session: aiohttp.ClientSession):
    """
    Resolve redirect if needed and clean AliExpress URL from ref params.
    Handles direct AliExpress links AND third-party redirect URLs
    (go.skidkovoz.com, ali.pub, etc.).
    Returns (clean_url, item_id)
    """
    final_url = url
    
    # Check if this is a known redirect domain — always resolve these
    is_redirect = any(re.match(p, url) for p in REDIRECT_PATTERNS)
    
    try:
        # Use HEAD first for redirects (faster), GET as fallback
        method = session.head if is_redirect else session.get
        async with method(url, allow_redirects=True, timeout=15) as resp:
            final_url = str(resp.url)
            if is_redirect:
                log.info(f'🔀 Redirect resolved: {url[:40]}... → {final_url[:60]}...')
    except Exception as e:
        log.warning(f"Failed to resolve URL {url}: {e}")
        if is_redirect:
            # For redirect URLs, try GET as fallback
            try:
                async with session.get(url, allow_redirects=True, timeout=15) as resp:
                    final_url = str(resp.url)
                    log.info(f'🔀 Redirect resolved (GET fallback): {final_url[:60]}...')
            except Exception as e2:
                log.warning(f"Redirect GET fallback also failed: {e2}")

    # Pattern handles /item/123.html, /i/123.html, ?itemId=123, &productIds=123
    match = re.search(r'(?:/(?:item|i)/|itemId=|productIds=)(\d+)(?:\.html|&|$)', final_url, re.IGNORECASE)
    if match:
        item_id = match.group(1)
        clean_url = f"https://aliexpress.com/item/{item_id}.html"
        return clean_url, item_id
    
    return final_url, None

def _extract_from_html(html: str):
    """Extract title, image_url and price from AliExpress HTML using multiple strategies."""
    title = None
    image_url = None
    price = None

    # --- Strategy 1: Open Graph meta tags ---
    og_title = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']+)', html, re.IGNORECASE)
    if not og_title:
        og_title = re.search(r'<meta\s+content=["\']([^"\']+)["\']\s+property=["\']og:title["\']', html, re.IGNORECASE)
    if og_title:
        title = og_title.group(1).strip()
        title = re.sub(r'\s*[-|]\s*AliExpress\s*\d*$', '', title).strip()

    og_image = re.search(r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)', html, re.IGNORECASE)
    if not og_image:
        og_image = re.search(r'<meta\s+content=["\']([^"\']+)["\']\s+property=["\']og:image["\']', html, re.IGNORECASE)
    if og_image:
        image_url = og_image.group(1).strip()

    price_match = re.search(r'<meta\s+property=["\']product:price:amount["\']\s+content=["\']([\d.]+)["\']', html, re.IGNORECASE)
    if price_match:
        try:
            price = float(price_match.group(1))
        except ValueError:
            pass

    # --- Strategy 2: JSON-LD structured data ---
    if not title or not image_url:
        json_ld_matches = re.findall(r'<script\s+type=["\']application/ld\+json["\']\s*>(.*?)</script>', html, re.DOTALL | re.IGNORECASE)
        for json_str in json_ld_matches:
            try:
                ld = json.loads(json_str)
                if isinstance(ld, list):
                    ld = ld[0]
                if not title and ld.get('name'):
                    title = str(ld['name']).strip()
                    title = re.sub(r'\s*[-|]\s*AliExpress\s*\d*$', '', title).strip()
                if not image_url and ld.get('image'):
                    img = ld['image']
                    if isinstance(img, list):
                        img = img[0]
                    if isinstance(img, dict):
                        img = img.get('url', img.get('contentUrl', ''))
                    if img:
                        image_url = str(img).strip()
                if not price and ld.get('offers'):
                    offers = ld['offers']
                    if isinstance(offers, list):
                        offers = offers[0]
                    if isinstance(offers, dict) and offers.get('price'):
                        try:
                            price = float(offers['price'])
                        except (ValueError, TypeError):
                            pass
            except (json.JSONDecodeError, KeyError, IndexError):
                continue

    # --- Strategy 3: <title> tag fallback ---
    if not title:
        title_tag = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
        if title_tag:
            t = title_tag.group(1).strip()
            t = re.sub(r'\s*[-|]\s*AliExpress\s*\d*$', '', t).strip()
            if len(t) > 5 and 'aliexpress' not in t.lower():
                title = t

    # --- Strategy 4: data-image-src or itemprop ---
    if not image_url:
        itemprop_img = re.search(r'<img[^>]+itemprop=["\']image["\']\s+src=["\']([^"\']+)', html, re.IGNORECASE)
        if itemprop_img:
            image_url = itemprop_img.group(1).strip()

    return title, image_url, price

def extract_title_from_image(image_path: str) -> str:
    """
    Extract product title from AliExpress screenshot using Tesseract OCR.
    Looks for the longest text line or lines before the price.
    """
    try:
        if not os.path.exists(image_path):
            return ""
            
        # Extract text using Russian and English models
        img = Image.open(image_path)
        # Convert to grayscale for better OCR
        img = img.convert('L')
        text = pytesseract.image_to_string(img, lang='rus+eng')
        
        if not text:
            return ""
            
        lines = [line.strip() for line in text.split('\n') if len(line.strip()) > 5]
        
        # Heuristics to find the title:
        # 1. Usually the title is the longest string of text
        # 2. Or it's the text block right before the price block
        # Let's filter out known UI elements
        ignore_words = ['купить', 'buy', 'корзин', 'cart', 'доставк', 'delivery',
                        'отзыв', 'review', 'заказ', 'order', 'aliexpress',
                        'скидк', 'discount', 'монет', 'coin', 'оплат', 'pay',
                        'цвет', 'color', 'размер', 'size', 'характеристик',
                        'продавец', 'продавець', 'продаж', 'бренд', 'brand',
                        'www', 'http', 'положительн', 'позитивн', 'загальн',
                        'free shipping', 'безкоштовн', 'безплатн',
                        'товар 1/', 'товар 2/', 'товар 3/', 'товар 4/',
                        'колір', 'people gave', 'positive review',
                        'цей продавець', 'этот продавец', 'wk www']
        
        valid_lines = []
        for line in lines:
            line_lower = line.lower()
            if any(word in line_lower for word in ignore_words):
                continue
            # Skip lines that look mostly like numbers/prices/dates
            if re.match(r'^[\d\s.,₽$€₴]+$', line):
                continue
            if len(line) < 10:
                continue
            valid_lines.append(line)
        
        if valid_lines:
            # Sort by length descending, assume the longest valid line is the title
            valid_lines.sort(key=len, reverse=True)
            candidate = valid_lines[0]
            # Clean up typical OCR artifacts
            candidate = re.sub(r'[\n\r]+', ' ', candidate)
            candidate = re.sub(r'\s{2,}', ' ', candidate)
            return candidate.strip()
            
    except Exception as e:
        log.warning(f"OCR failed: {e}")
        
    return ""


async def scrape_aliexpress_product(product_url: str, session: aiohttp.ClientSession):
    """
    Scrape AliExpress product page to get title and image URL.
    Uses multiple strategies:
    1. Desktop page with OG meta / JSON-LD / <title>
    2. Mobile page (m.aliexpress.com) — less aggressive blocking
    3. URL slug extraction as last resort
    Returns {'title': str, 'image_url': str, 'price': float} or None on failure.
    """
    max_retries = 3
    
    # Extract product ID for URL construction
    item_match = re.search(r'/item/(\d+)\.html', product_url)
    pid = item_match.group(1) if item_match else None
    
    for attempt in range(max_retries):
        # Alternate between desktop and mobile on retries
        use_mobile = (attempt >= 1)  # First try desktop, then mobile
        
        if use_mobile:
            ua = random.choice(_USER_AGENTS_MOBILE)
            referer = 'https://m.aliexpress.com/'
        else:
            ua = random.choice(_USER_AGENTS_DESKTOP)
            referer = 'https://www.google.com/'
        
        headers = {
            'User-Agent': ua,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,uk;q=0.8,ru;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': referer,
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'cross-site' if not use_mobile else 'same-origin',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'Upgrade-Insecure-Requests': '1',
            'Connection': 'keep-alive',
            'DNT': '1',
        }
        
        # Build URL list based on attempt
        urls_to_try = []
        if pid:
            if use_mobile:
                urls_to_try = [
                    f'https://m.aliexpress.com/item/{pid}.html',
                    f'https://www.aliexpress.com/item/{pid}.html',
                ]
            else:
                urls_to_try = [
                    f'https://www.aliexpress.com/item/{pid}.html',
                    f'https://aliexpress.com/item/{pid}.html',
                ]
        else:
            urls_to_try = [product_url]
        
        for url in urls_to_try:
            try:
                timeout = aiohttp.ClientTimeout(total=25)
                # Use proxy for scraping
                proxy = PROXY_URL if PROXY_URL else None
                async with session.get(url, headers=headers, timeout=timeout, allow_redirects=True, proxy=proxy) as resp:
                    if resp.status != 200:
                        log.warning(f'AliExpress returned {resp.status} for {url} (attempt {attempt+1}, {"mobile" if use_mobile else "desktop"})')
                        continue
                    html = await resp.text()
                
                if len(html) < 1000:
                    log.warning(f'AliExpress returned very short page ({len(html)} chars), likely blocked (attempt {attempt+1})')
                    continue
                
                title, image_url, price = _extract_from_html(html)
                
                if title or image_url:
                    log.info(f'🔍 Scraped from AliExpress: "{(title or "?")[:60]}" | Image: {"yes" if image_url else "no"} | Price: {price} (attempt {attempt+1}, {"mobile" if use_mobile else "desktop"})')
                    return {'title': title, 'image_url': image_url, 'price': price}
                    
            except asyncio.TimeoutError:
                log.warning(f'Timeout scraping {url} (attempt {attempt+1})')
            except Exception as e:
                log.warning(f'Error scraping {url}: {e} (attempt {attempt+1})')
        
        # Wait before retry with exponential backoff
        if attempt < max_retries - 1:
            delay = (attempt + 1) * 2 + random.uniform(0, 2)
            log.info(f'Retrying scrape in {delay:.1f}s...')
            await asyncio.sleep(delay)
    
    # === LAST RESORT: extract title from URL slug ===
    if pid:
        slug_title = _extract_title_from_url_slug(product_url)
        if slug_title:
            log.info(f'📝 Extracted title from URL slug: "{slug_title[:60]}"')
            return {'title': slug_title, 'image_url': None, 'price': None}
    
    log.warning(f'Failed to scrape AliExpress after {max_retries} attempts: {product_url}')
    return None


def _extract_title_from_url_slug(url: str) -> str:
    """
    Try to extract a product title from the URL slug.
    Example: https://aliexpress.com/item/Baseus-100W-USB-C-Cable_1234567890.html
    -> "Baseus 100W USB C Cable"
    """
    try:
        # Look for text before the product ID in the URL path
        match = re.search(r'/item/([A-Za-z][\w-]+?)[-_]\d+\.html', url)
        if match:
            slug = match.group(1)
            # Convert hyphens/underscores to spaces
            title = slug.replace('-', ' ').replace('_', ' ')
            # Clean up
            title = re.sub(r'\s+', ' ', title).strip()
            if len(title) > 10:
                return title
    except Exception:
        pass
    return ""

async def download_image(url: str, filepath: str, session: aiohttp.ClientSession):
    """Download image from URL to local file."""
    try:
        async with session.get(url, timeout=15) as resp:
            if resp.status == 200:
                with open(filepath, 'wb') as f:
                    f.write(await resp.read())
                return True
    except Exception as e:
        log.warning(f'Failed to download image from {url}: {e}')
    return False

def extract_price(text):
    """Try to extract price from message text."""
    if not text:
        return {'value': 0, 'currency': 'USD'}
        
    def parse_price_value(s):
        # Remove whitespace
        s = re.sub(r'\s+', '', s)
        separators = re.findall(r'[.,]', s)
        if not separators:
            return float(s)
        
        last_sep_index = max(s.rfind(','), s.rfind('.'))
        digits_after = len(s) - last_sep_index - 1
        
        if digits_after == 3:
            # It's a thousands separator
            s = s.replace(',', '').replace('.', '')
            return float(s)
        else:
            # It's a decimal separator
            s_base = s[:last_sep_index].replace(',', '').replace('.', '')
            s_dec = s[last_sep_index+1:]
            return float(f"{s_base}.{s_dec}")
            
    # UAH patterns
    uah_patterns = [
        r'(\d[\d \t\xA0.,]*\d|\d)\s*(?:грн|грив|uah|₴)',
        r'₴\s*(\d[\d \t\xA0.,]*\d|\d)',
    ]
    for pattern in uah_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            price_str = match.group(1).strip()
            price_str = price_str.strip('.,')
            if price_str:
                try:
                    return {'value': parse_price_value(price_str), 'currency': 'UAH'}
                except ValueError:
                    continue

    # USD patterns
    usd_patterns = [
        r'\$\s*(\d[\d \t\xA0.,]*\d|\d)',
        r'(\d[\d \t\xA0.,]*\d|\d)\s*\$',
        r'(\d[\d \t\xA0.,]*\d|\d)\s*(?:USD|usd|дол)',
        r'(?:ціна|цена|price|вартість)[:\s]*\$?(\d[\d \t\xA0.,]*\d|\d)',
    ]
    for pattern in usd_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            price_str = match.group(1).strip()
            price_str = price_str.strip('.,')
            if price_str:
                try:
                    return {'value': parse_price_value(price_str), 'currency': 'USD'}
                except ValueError:
                    continue

    return {'value': 0, 'currency': 'USD'}

def clean_text(text):
    """Remove spam, ads, URLs, channel mentions from original post text."""
    if not text:
        return ''
    # Remove URLs
    text = re.sub(r'https?://[^\s]+', '', text)
    # Remove emoji (most common ranges)
    text = re.sub(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U0000FE00-\U0000FE0F\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF\U00002600-\U000026FF]+', '', text)
    
    lines = text.split('\n')
    cleaned = []
    skip_patterns = [
        r'підписуйтесь|підпишись|subscribe|join',
        r'@\w+канал|@\w+channel',
        r'реклама|advertisement|sponsored',
        r'👉\s*@',
        r'^\s*@\w+\s*$',
    ]
    for line in lines:
        line = line.strip()
        if not line:
            continue
        should_skip = False
        for pattern in skip_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                should_skip = True
                break
        if not should_skip:
            cleaned.append(line)
    
    result = ' '.join(cleaned).strip()
    # Clean up extra spaces
    result = re.sub(r'\s{2,}', ' ', result)
    return result

# --- Category Detection ---
CATEGORY_RULES = [
    {
        'slug': 'electronics',
        'hashtags': ['#електроніка', '#гаджет', '#смартфон', '#повербанк', '#навушники', '#годинник', '#pc', '#usb', '#кабель'],
        'keywords': [
            'навушник', 'earphone', 'headphone', 'earbuds', 'tws',
            'кабель', 'cable', 'usb', 'type-c', 'lightning', 'charger', 'зарядк',
            'повербанк', 'power bank', 'powerbank', 'батаре',
            'смартфон', 'phone', 'телефон',
            'годинник', 'watch', 'smartwatch', 'smart watch',
            'bluetooth', 'блютуз', 'wifi', 'wi-fi',
            'колонк', 'speaker', 'динамік',
            'флешк', 'flash', 'sd card', 'memory card', 'карта пам',
            'led', 'світлодіод', 'lamp', 'лампа', 'ліхтар', 'flashlight',
            'камера', 'camera', 'webcam', 'вебкамера',
            'клавіатур', 'keyboard', 'мишк', 'mouse', 'миш',
            'адаптер', 'adapter', 'hub', 'хаб', 'перехідник',
            'планшет', 'tablet', 'kindle',
        ],
    },
    {
        'slug': 'beauty',
        'hashtags': ['#краса', '#косметика', '#макіяж', '#догляд', '#б\'юті'],
        'keywords': [
            'косметик', 'cosmetic', 'makeup', 'макіяж',
            'крем', 'cream', 'лосьйон', 'lotion', 'сироватк', 'serum',
            'щітк', 'brush', 'пензл', 'пензлик',
            'манікюр', 'manicure', 'nail', 'нігт', 'лак',
            'маска для облич', 'face mask', 'патчі', 'patch',
            'шампунь', 'shampoo', 'бальзам', 'кондиціонер',
            'парфум', 'perfume', 'аромат', 'духи',
            'епілятор', 'epilator', 'тример', 'trimmer', 'бритв',
            'пілінг', 'peeling', 'скраб', 'scrub',
            'помада', 'lipstick', 'тіні', 'shadow', 'туш', 'mascara', 'підводк',
        ],
    },
    {
        'slug': 'home',
        'hashtags': ['#дім', '#кухня', '#їжа', '#побут', '#декор'],
        'keywords': [
            'кухн', 'kitchen', 'посуд', 'тарілк', 'чашк', 'cup', 'mug',
            'ніж', 'knife', 'різак', 'cutter', 'відкривач', 'opener',
            'контейнер', 'container', 'органайзер', 'organizer',
            'рушник', 'towel', 'серветк', 'napkin',
            'подушк', 'pillow', 'ковдр', 'blanket', 'плед',
            'декор', 'decor', 'ваза', 'vase', 'свічк', 'candle',
            'штор', 'curtain', 'carpet', 'килим',
            'полиц', 'shelf', 'гачок', 'hook', 'тримач', 'holder',
            'мило', 'soap', 'диспенсер', 'dispenser',
            'пилосос', 'vacuum', 'швабр', 'mop',
            'термос', 'thermos', 'термо',
        ],
    },
    {
        'slug': 'fashion',
        'hashtags': ['#одяг', '#мода', '#взуття', '#стиль'],
        'keywords': [
            'футболк', 't-shirt', 'tshirt', 'майк',
            'штан', 'pants', 'джинс', 'jeans', 'шорти', 'shorts',
            'куртк', 'jacket', 'пальто', 'coat', 'вітровк', 'windbreaker',
            'сукн', 'dress', 'плаття', 'спідниц', 'skirt',
            'светр', 'sweater', 'худі', 'hoodie', 'толстовк', 'sweatshirt',
            'кросівк', 'sneakers', 'взуття', 'shoes', 'черевик', 'boots',
            'шкарпетк', 'socks', 'білизн', 'underwear',
            'окуляр', 'glasses', 'sunglasses', 'сонцезахисн',
        ],
    },
    {
        'slug': 'accessories',
        'hashtags': ['#аксесуари', '#чохол', '#кейс'],
        'keywords': [
            'чохол', 'чехол', 'case', 'cover',
            'ремінець', 'strap', 'band', 'браслет', 'bracelet',
            'сумк', 'bag', 'рюкзак', 'backpack', 'гаманець', 'wallet',
            'кейс', 'поuch', 'косметичк',
            'захисне скло', 'screen protector', 'плівк', 'film',
            'ланцюжок', 'chain', 'підвіск', 'pendant', 'кольц', 'ring',
            'шарф', 'scarf', 'хустк', 'bandana',
            'кепк', 'cap', 'шапк', 'hat', 'панам',
            'пояс', 'belt', 'ремін',
        ],
    },
    {
        'slug': 'sport',
        'hashtags': ['#спорт', '#фітнес', '#тренування'],
        'keywords': [
            'спорт', 'sport', 'фітнес', 'fitness', 'gym',
            'тренажер', 'гантел', 'dumbbell', 'еспандер', 'resistance',
            'йога', 'yoga', 'килимок для', 'mat',
            'велосипед', 'bicycle', 'bike', 'велоспорт',
            'м\'яч', 'ball', 'футбол', 'football', 'баскетбол',
            'біг', 'running', 'пробіжк',
            'скакалк', 'rope', 'турнік',
            'рибалк', 'fishing', 'риболовл',
            'кемпінг', 'camping', 'намет', 'tent', 'туризм',
        ],
    },
    {
        'slug': 'toys',
        'hashtags': ['#іграшки', '#дитяче', '#діти'],
        'keywords': [
            'іграшк', 'toy', 'лего', 'lego', 'конструктор',
            'ляльк', 'doll', 'плюшев', 'plush', 'м\'яка іграшк',
            'пазл', 'puzzle', 'головоломк',
            'дитяч', 'kids', 'children', 'baby', 'дитин', 'немовля',
            'розмальовк', 'coloring', 'пластилін', 'слайм', 'slime',
            'радіокерован', 'rc ', 'дрон', 'drone', 'квадрокоптер',
        ],
    },
    {
        'slug': 'tools',
        'hashtags': ['#інструмент', '#ремонт', '#майстер'],
        'keywords': [
            'інструмент', 'tool', 'дриль', 'drill',
            'ключ', 'wrench', 'викрутк', 'screwdriver',
            'набір біт', 'bit set', 'мультитул', 'multitool',
            'паяльник', 'soldering', 'клейов', 'glue gun',
            'рулетк', 'tape measure', 'рівень', 'level',
            'пилк', 'saw', 'лобзик', 'jigsaw',
            'стяжк', 'zip tie', 'ізолент', 'tape',
            'свердл', 'drill bit', 'шліфувальн', 'sander',
        ],
    },
    {
        'slug': 'auto',
        'hashtags': ['#авто', '#автомобіль', '#машина'],
        'keywords': [
            'авто', 'auto', 'car', 'машин',
            'відеореєстратор', 'dashcam', 'dash cam',
            'тримач для телефон', 'phone holder', 'phone mount',
            'автозарядк', 'car charger',
            'килимок в авто', 'car mat',
            'ароматизатор', 'air freshener',
            'парктронік', 'parking sensor',
            'чохол на кермо', 'steering wheel',
        ],
    },
    {
        'slug': 'hot',
        'hashtags': ['#хіт', '#топ', '#бестселер', '#розпродаж'],
        'keywords': [],  # hot is primarily hashtag-based
    },
]

def detect_category(title: str, raw_text: str) -> str:
    """Detect product category from title and raw message text.
    
    Priority: hashtags in text → keywords in title → keywords in text → default 'new'.
    """
    text_lower = raw_text.lower()
    title_lower = title.lower() if title else ''
    
    # 1. Check hashtags first (highest confidence)
    for rule in CATEGORY_RULES:
        for tag in rule['hashtags']:
            if tag in text_lower:
                return rule['slug']
    
    # 2. Check keywords in title (high confidence)
    for rule in CATEGORY_RULES:
        for kw in rule['keywords']:
            if kw in title_lower:
                return rule['slug']
    
    # 3. Check keywords in full text (lower confidence)
    for rule in CATEGORY_RULES:
        for kw in rule['keywords']:
            if kw in text_lower:
                return rule['slug']
    
    return 'new'

# --- GitHub Direct API (Batch Mode) ---
_github_pending = []  # Products waiting to be flushed to GitHub
_github_flush_interval = 600  # Flush every 10 minutes (600 seconds)
_github_flush_lock = asyncio.Lock()

def queue_product_for_github(product_data):
    """Add product to the pending queue (will be flushed in batch)."""
    import random
    
    category = detect_category(product_data.get('title', ''), product_data['raw_text'])
    site_product = {
        'id': product_data['id'],
        'title': product_data['title'],
        'title_pl': product_data.get('title_pl', ''),
        'price': product_data.get('price') or 0,
        'currency': product_data.get('currency', 'USD'),
        'category': category,
        'rating': round(random.uniform(4.7, 5.0), 1),
        'orders': random.randint(100, 2000),
        'image': product_data.get('image_path', ''),
        'link': product_data['original_link'],
        'affiliate_link': make_affiliate_link(product_data['id']),
        'description': '',
        'promo_text': product_data.get('promo_text', ''),
        'price_note': product_data.get('price_note', ''),
        'source_channel': product_data.get('source_channel', ''),
        'added_at': product_data['timestamp'],
    }
    _github_pending.append(site_product)
    log.info(f'📦 Queued for GitHub: {site_product["id"]} (pending: {len(_github_pending)})')
    return True

async def _fetch_products_json_raw(session):
    """Fetch products.json via raw GitHub URL (works for files >1MB)."""
    raw_url = f'https://raw.githubusercontent.com/{GITHUB_REPO}/main/{GITHUB_PRODUCTS_PATH}'
    async with session.get(raw_url, timeout=30) as resp:
        if resp.status != 200:
            log.error(f'GitHub raw GET failed: {resp.status}')
            return None
        text = await resp.text()
        return json.loads(text)

async def _get_file_sha(session, headers, api_url):
    """Get SHA of a file via Contents API (works regardless of file size)."""
    async with session.get(api_url, headers=headers, timeout=30) as resp:
        if resp.status != 200:
            log.error(f'GitHub SHA GET failed: {resp.status}')
            return None
        gh_data = await resp.json()
        return gh_data.get('sha')

async def flush_products_to_github():
    """Flush all pending products to GitHub in a single commit."""
    async with _github_flush_lock:
        if not _github_pending:
            return True
        
        products_to_save = list(_github_pending)
        api_url = f'https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_PRODUCTS_PATH}'
        headers = {
            'Authorization': f'token {GITHUB_TOKEN}',
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'ShopNaAli-Parser',
        }
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    # GET current SHA (Contents API works for any size, just no content for >1MB)
                    sha = await _get_file_sha(session, headers, api_url)
                    if not sha:
                        if attempt < max_retries - 1:
                            await asyncio.sleep(5)
                            continue
                        return False
                    
                    # GET current content via raw URL (no 1MB limit)
                    products = await _fetch_products_json_raw(session)
                    if products is None:
                        if attempt < max_retries - 1:
                            await asyncio.sleep(5)
                            continue
                        return False
                    
                    # Insert all pending products at the beginning
                    existing_ids = {p['id'] for p in products.get('products', [])}
                    new_products = [p for p in products_to_save if p['id'] not in existing_ids]
                    
                    if not new_products:
                        log.info('📦 All pending products already exist on GitHub, clearing queue')
                        _github_pending.clear()
                        return True
                    
                    for p in reversed(new_products):
                        products.setdefault('products', []).insert(0, p)
                    
                    # Encode back
                    updated = base64.b64encode(
                        json.dumps(products, ensure_ascii=False, indent=2).encode('utf-8')
                    ).decode('utf-8')
                    
                    # PUT updated file
                    ids_str = ', '.join(p['id'] for p in new_products[:3])
                    if len(new_products) > 3:
                        ids_str += f' +{len(new_products)-3} more'
                    put_body = {
                        'message': f'Add {len(new_products)} products: {ids_str}',
                        'content': updated,
                        'sha': sha,
                    }
                    async with session.put(
                        api_url,
                        headers=headers,
                        json=put_body,
                        timeout=60,
                    ) as put_resp:
                        if put_resp.status == 200:
                            log.info(f'🌐 Batch saved to GitHub: {len(new_products)} products')
                            _github_pending.clear()
                            return True
                        else:
                            error_text = await put_resp.text()
                            log.error(f'GitHub PUT failed: {put_resp.status} -- {error_text}')
                            if attempt < max_retries - 1 and put_resp.status >= 500:
                                await asyncio.sleep(5)
                                continue
                            return False
            except Exception as e:
                log.error(f'GitHub API error: {e}')
                if attempt < max_retries - 1:
                    await asyncio.sleep(5)
                    continue
                return False
                
        return False

async def github_flush_task():
    """Background task that periodically flushes pending products to GitHub."""
    while True:
        await asyncio.sleep(_github_flush_interval)
        if _github_pending:
            log.info(f'⏰ Auto-flushing {len(_github_pending)} products to GitHub...')
            saved = await flush_products_to_github()
            if saved:
                await update_sitemap_on_github()

async def update_sitemap_on_github():
    """Regenerate sitemap.xml on GitHub from current products.json."""
    api_base = f'https://api.github.com/repos/{GITHUB_REPO}/contents'
    headers = {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'ShopNaAli-Parser',
    }
    site_url = 'https://dobaksa.shop'
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            async with aiohttp.ClientSession() as session:
                # GET products.json via raw URL (handles >1MB files)
                products_data = await _fetch_products_json_raw(session)
                if products_data is None:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2)
                        continue
                    return
                products = products_data.get('products', [])
                
                # Build sitemap
                urls = [
                    f'  <url>\n    <loc>{site_url}/</loc>\n    <lastmod>{today}</lastmod>\n    <changefreq>daily</changefreq>\n    <priority>1.0</priority>\n  </url>',
                    f'  <url>\n    <loc>{site_url}/promos.html</loc>\n    <lastmod>{today}</lastmod>\n    <changefreq>weekly</changefreq>\n    <priority>0.8</priority>\n  </url>',
                    f'  <url>\n    <loc>{site_url}/faq.html</loc>\n    <lastmod>{today}</lastmod>\n    <changefreq>weekly</changefreq>\n    <priority>0.8</priority>\n  </url>'
                ]
                for p in products:
                    pid = p.get('id', '')
                    added = p.get('added_at', today)[:10]
                    urls.append(f'  <url>\n    <loc>{site_url}/product.html?id={pid}</loc>\n    <lastmod>{added}</lastmod>\n    <changefreq>weekly</changefreq>\n    <priority>0.7</priority>\n  </url>')
                
                sitemap_xml = f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + '\n'.join(urls) + '\n</urlset>\n'
                encoded = base64.b64encode(sitemap_xml.encode('utf-8')).decode('utf-8')
                
                # GET existing sitemap SHA
                sha = None
                async with session.get(f'{api_base}/site/sitemap.xml', headers=headers, timeout=15) as resp:
                    if resp.status == 200:
                        sha = (await resp.json()).get('sha')
                
                # PUT sitemap
                put_body = {
                    'message': f'Update sitemap ({len(products)} products)',
                    'content': encoded,
                }
                if sha:
                    put_body['sha'] = sha
                
                async with session.put(f'{api_base}/site/sitemap.xml', headers=headers, json=put_body, timeout=15) as resp:
                    if resp.status in (200, 201):
                        log.info(f'Sitemap updated: {len(products)} products')
                        return
                    else:
                        log.warning(f'Sitemap update failed: {resp.status}')
                        if attempt < max_retries - 1 and resp.status >= 500:
                            await asyncio.sleep(2)
                            continue
                        return
        except Exception as e:
            log.warning(f'Sitemap update error: {e}')
            if attempt < max_retries - 1:
                await asyncio.sleep(2)
                continue
            return

# --- Telegram Client ---
client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
client.parse_mode = 'html'

# --- Rate Limiting ---
_message_queue = asyncio.Queue()
_last_scrape_time = 0  # timestamp of last AliExpress scrape
_channel_post_counter = {}  # track how many posts per channel
SCRAPE_COOLDOWN = 30  # seconds between AliExpress scrapes
MIN_POST_DELAY = 90  # minimum seconds between processing posts
MAX_POST_DELAY = 150  # maximum seconds between processing posts
SKIP_EVERY_N = 3  # skip every Nth post from same channel in a burst

import time

# --- FAQ Tips (contextual + periodic) ---
_total_posts_sent = 0
FAQ_LINK_EVERY_N = 10  # add generic FAQ link every Nth post

_CONTEXTUAL_TIPS = {
    'coins': [
        "\n💡 <i>Як заощадити ще більше монетами →</i> <a href='https://dobaksa.shop/faq.html#coins'>Гайд</a>",
        "\n🪙 <i>Знижки до 99% за монети!</i> <a href='https://dobaksa.shop/faq.html#coins'>Дізнатись як</a>",
    ],
    'promo': [
        "\n🏷 <i>Як закріпити промокоди до розпродажу →</i> <a href='https://dobaksa.shop/faq.html#coupons'>Поради</a>",
        "\n💡 <i>Не працює промокод?</i> <a href='https://dobaksa.shop/faq.html#coupons'>Рішення тут</a>",
    ],
    'generic': [
        "\n📖 <i>Гайд для вигідних покупок:</i> <a href='https://dobaksa.shop/faq.html'>dobaksa.shop/faq</a>",
        "\n🎓 <i>Поради по AliExpress:</i> <a href='https://dobaksa.shop/faq.html'>Читати гайд</a>",
    ],
}

@client.on(events.NewMessage(chats=DONOR_CHANNELS))
async def queue_new_post(event):
    """Queue incoming posts for throttled processing."""
    channel_title = event.chat.title or str(event.chat_id)
    
    # Track posts per channel (reset counter every 10 minutes)
    now = time.time()
    channel_key = str(event.chat_id)
    if channel_key not in _channel_post_counter:
        _channel_post_counter[channel_key] = {'count': 0, 'first_seen': now}
    
    counter = _channel_post_counter[channel_key]
    # Reset counter if more than 10 minutes since first post in burst
    if now - counter['first_seen'] > 600:
        counter['count'] = 0
        counter['first_seen'] = now
    
    counter['count'] += 1
    
    # Skip every Nth post from the same channel in a burst
    if counter['count'] % SKIP_EVERY_N == 0:
        log.info(f"⏭ Throttle: skipping post #{counter['count']} from {channel_title} (every {SKIP_EVERY_N}th)")
        return
    
    # Don't queue too many messages
    if _message_queue.qsize() >= 20:
        log.info(f"⏭ Queue full ({_message_queue.qsize()}), skipping post from {channel_title}")
        return
    
    await _message_queue.put(event)
    log.info(f"📥 Queued post from {channel_title} (queue size: {_message_queue.qsize()})")


async def process_queue():
    """Process queued messages with delays between them."""
    global _last_scrape_time
    while True:
        try:
            event = await _message_queue.get()
            log.info(f"📤 Processing queued post (remaining: {_message_queue.qsize()})")
            await handle_new_post(event)
            
            # Wait between posts to avoid AliExpress rate limiting
            delay = random.uniform(MIN_POST_DELAY, MAX_POST_DELAY)
            log.info(f"⏳ Waiting {delay:.0f}s before next post...")
            await asyncio.sleep(delay)
        except Exception as e:
            log.error(f"Queue processing error: {e}", exc_info=True)
            await asyncio.sleep(10)


async def throttled_scrape(product_url: str, session: aiohttp.ClientSession):
    """Wrapper around scrape_aliexpress_product with cooldown between scrapes."""
    global _last_scrape_time
    now = time.time()
    elapsed = now - _last_scrape_time
    if elapsed < SCRAPE_COOLDOWN:
        wait_time = SCRAPE_COOLDOWN - elapsed + random.uniform(5, 15)
        log.info(f"🕐 Scrape cooldown: waiting {wait_time:.0f}s...")
        await asyncio.sleep(wait_time)
    
    result = await scrape_aliexpress_product(product_url, session)
    _last_scrape_time = time.time()
    return result


async def handle_new_post(event):
    """Process new posts from donor channels."""
    try:
        message = event.message
        
        # Get text with HTML formatting (for Telegram forwarding)
        text_html = message.text or ''
        # Get raw plain text (for URL extraction and GitHub/site data)
        raw_text = message.raw_text or ''
        
        # Find all URLs in raw text
        urls = set(re.findall(r'https?://[^\s<"]+', raw_text))
        
        # Also check for redirect URLs that may not look like AliExpress
        redirect_urls = set()
        for u in list(urls):
            for rp in REDIRECT_PATTERNS:
                if re.match(rp, u):
                    redirect_urls.add(u)
                    break
        if redirect_urls:
            log.info(f'🔀 Found {len(redirect_urls)} redirect URL(s): {", ".join(u[:40] for u in redirect_urls)}')
        
        # Also extract URLs from inline buttons
        if message.reply_markup and hasattr(message.reply_markup, 'rows'):
            for row in message.reply_markup.rows:
                for button in row.buttons:
                    if hasattr(button, 'url') and button.url:
                        urls.add(button.url)
        
        # If there's no text and no URLs
        if not raw_text and not urls:
            # If it's part of an album (multiple photos), skip the extra photos to keep only one
            if message.grouped_id:
                log.info(f"⏭ Skipped extra album photo from {event.chat.title}")
                return
            
            media_to_send = message.media if not isinstance(message.media, MessageMediaWebPage) else None
            if media_to_send:
                # Otherwise, it's a standalone media message, forward it
                await client.send_message(TARGET_CHANNEL, file=media_to_send)
                log.info(f"✅ Copied media-only message from {event.chat.title}")
            return
        
        # Resolve and clean URLs
        urls_sorted = sorted(list(urls), key=len, reverse=True)
        product_ids_found = []
        clean_links_added = set()
        
        # Limit processing if there are 3 or more links
        limit_to_first = len(urls_sorted) >= 3
        
        async with aiohttp.ClientSession() as session:
            for u in urls_sorted:
                if limit_to_first and len(product_ids_found) >= 1:
                    # If we have 3+ links, we only process the first valid product
                    text_html = text_html.replace(u, '')
                    continue
                    
                clean_url, item_id = await resolve_and_clean_url(u, session)
                if clean_url != u:
                    text_html = text_html.replace(u, '')
                else:
                    text_html = text_html.replace(u, '')
                if item_id:
                    product_ids_found.append(item_id)
                    clean_links_added.add(clean_url)
        
        # Deduplication check (allow re-post if price changed >5%)
        is_duplicate = False
        new_price_value = extract_price(raw_text).get('value', 0)
        for pid in product_ids_found:
            if pid in seen_products:
                old_price = seen_products[pid]
                if old_price and new_price_value and old_price > 0:
                    change = abs(new_price_value - old_price) / old_price
                    if change > 0.05:  # >5% price change → allow re-post
                        log.info(f'💰 Price changed for {pid}: {old_price} → {new_price_value} ({change:.0%}), re-posting')
                        continue  # not a duplicate
                is_duplicate = True
                break
                
        if is_duplicate:
            log.info(f"⏭️ Skipping duplicate post; already seen product(s) at same price.")
            return
            
        # Add/update in seen with current price
        for pid in product_ids_found:
            seen_products[pid] = new_price_value
        save_seen(seen_products)

        # --- Extract product info FIRST, then build clean post ---
        # Build fallback title: skip price/instruction lines
        _fb_lines = clean_text(raw_text).split('\n')
        _fb_cleaned = []
        for _fbl in _fb_lines:
            _fbl_s = _fbl.strip()
            if not _fbl_s or len(_fbl_s) < 5:
                continue
            _fbl_low = _fbl_s.lower()
            # Skip lines that are just prices, coin info, or delivery instructions
            if re.match(r'^[\d\s.,\u20bd\$\u20ac\u20b4грнuah]+$', _fbl_s):
                continue
            if any(w in _fbl_low for w in ['монет', 'coin', 'як замовити', 'как заказать',
                    'безкоштовн', 'доставк', 'з монетами', 'грн з ', 'грн с ',
                    'підписуй', 'subscribe', 'ціна на', 'цена на']):
                continue
            _fb_cleaned.append(_fbl_s)
        fallback_title = ' '.join(_fb_cleaned)[:200] if _fb_cleaned else clean_text(raw_text)[:200]
        fallback_price = extract_price(raw_text)
        
        # Extract coins/монети info from raw text
        coins_info = ""
        coins_match = re.search(r'(\d+)\s*(?:coins?|монет)', raw_text, re.IGNORECASE)
        if coins_match:
            coins_info = f"{coins_match.group(1)} coins"
        elif re.search(r'монет|coins?', raw_text, re.IGNORECASE):
            coins_info = "монетками"

        # Extract ALL promo codes
        promo_codes = []
        # 1. Find codes after keywords like "промокод", "купон", "promo", "code", "coupon"
        keyword_matches = re.finditer(r'(?:промокод|купон|promo|code|coupon)[:\s]*([A-Z0-9]{4,})', raw_text, re.IGNORECASE)
        for m in keyword_matches:
            code = m.group(1).upper()
            if code not in promo_codes:
                promo_codes.append(code)
        # 2. Find codes mentioned with "на вибір" pattern (e.g. "промокод на вибір ASUA03, UAAFF03, UAS3")
        choice_match = re.search(r'(?:на\s+вибір|choose)[:\s]*([A-Z0-9,\s]{4,})', raw_text, re.IGNORECASE)
        if choice_match:
            for code in re.findall(r'[A-Z0-9]{3,}', choice_match.group(1)):
                code = code.upper()
                if code not in promo_codes:
                    promo_codes.append(code)
        # 3. Fallback: find codes in parentheses near promo keywords
        if not promo_codes:
            paren_match = re.search(r'\((?:.*?(?:промокод|купон|code|coupon).*?)\)', raw_text, re.IGNORECASE | re.DOTALL)
            if paren_match:
                codes = re.findall(r'[A-Z0-9]{4,}', paren_match.group(0))
                for code in codes:
                    code = code.upper()
                    if code not in promo_codes:
                        promo_codes.append(code)
        promo_text = ", ".join(promo_codes)

        # Extract price note (ONLY for coins/shipping, NOT promo codes)
        price_note = ""
        price_note_patterns = [
            r'\(([^)]*(?:монет|знижк|coin)[^)]*)\)',
            r'(?:ціна\s+)?(?:з|із)\s+(купон\w*(?:\s*\+?\s*монет\w*)?)',
            r'(купон\s+під\s+товаром(?:\s*\+?\s*монет\w*)?)',
            r'(?<!\w)(\+\s*монет\w*)',
            r'((?:з\s+)?монет(?:и|ами|ками)(?:\s*\+?\s*купон\w*)?)',
        ]
        for pattern in price_note_patterns:
            note_match = re.search(pattern, raw_text, re.IGNORECASE)
            if note_match:
                note = note_match.group(1).strip()
                # Skip if this note is just about a promo code
                if re.search(r'промокод|promo|code|coupon', note, re.IGNORECASE):
                    continue
                note = re.sub(r'\s+', ' ', note).strip(' .,;:!-')
                if note and len(note) < 80:
                    price_note = note[0].upper() + note[1:] if len(note) > 1 else note.upper()
                    break

        # Scrape AliExpress for title and image BEFORE sending to TG
        product_title = fallback_title
        image_url = ''
        scraped = None
        translated_title = ''
        
        if product_ids_found:
            pid = product_ids_found[0]
            original_link = f"https://aliexpress.com/item/{pid}.html"
            affiliate_link = make_affiliate_link(pid)
            
            async with aiohttp.ClientSession() as scrape_session:
                scraped = await throttled_scrape(original_link, scrape_session)
            
            if scraped:
                if scraped.get('title'):
                    product_title = scraped['title'][:200]
                    translated_title = clean_and_translate_title(product_title)
                if scraped.get('image_url'):
                    image_url = scraped['image_url']
                    log.info(f'📸 Got image URL from AliExpress')
                if fallback_price['value'] == 0 and scraped.get('price'):
                    fallback_price = {'value': scraped['price'], 'currency': 'USD'}
            
            # --- PRIMARY IMAGE: Download from Telegram message ---
            if not image_url and message.media:
                try:
                    import tempfile, os
                    tmp_path = os.path.join(tempfile.gettempdir(), f'tg_img_{pid}.jpg')
                    downloaded = None
                    
                    if isinstance(message.media, MessageMediaWebPage):
                        # Extract photo from WebPage preview
                        webpage = message.media.webpage
                        if hasattr(webpage, 'photo') and webpage.photo:
                            downloaded = await client.download_media(webpage.photo, file=tmp_path)
                            log.info(f'📸 Downloading image from WebPage preview')
                        elif hasattr(webpage, 'document') and webpage.document:
                            downloaded = await client.download_media(webpage.document, file=tmp_path)
                            log.info(f'📸 Downloading document from WebPage preview')
                    else:
                        # Regular photo/document media
                        downloaded = await client.download_media(message.media, file=tmp_path)
                    
                    if downloaded and os.path.exists(downloaded):
                        with open(downloaded, 'rb') as img_file:
                            img_bytes = img_file.read()
                        
                        if len(img_bytes) > 1000:  # Skip tiny/broken files
                            img_b64 = base64.b64encode(img_bytes).decode('utf-8')
                            gh_img_path = f'site/images/products/{pid}.jpg'
                            gh_api_url = f'https://api.github.com/repos/{GITHUB_REPO}/contents/{gh_img_path}'
                            gh_headers = {
                                'Authorization': f'token {GITHUB_TOKEN}',
                                'Accept': 'application/vnd.github.v3+json',
                                'User-Agent': 'ShopNaAli-Parser',
                            }
                            
                            async with aiohttp.ClientSession() as gh_session:
                                # Check if image already exists
                                sha = None
                                async with gh_session.get(gh_api_url, headers=gh_headers, timeout=aiohttp.ClientTimeout(total=10)) as check_resp:
                                    if check_resp.status == 200:
                                        sha = (await check_resp.json()).get('sha')
                                
                                put_body = {
                                    'message': f'Add product image {pid}',
                                    'content': img_b64,
                                }
                                if sha:
                                    put_body['sha'] = sha
                                
                                async with gh_session.put(gh_api_url, headers=gh_headers, json=put_body, timeout=aiohttp.ClientTimeout(total=30)) as put_resp:
                                    if put_resp.status in (200, 201):
                                        image_url = f'https://raw.githubusercontent.com/{GITHUB_REPO}/main/{gh_img_path}'
                                        log.info(f'📸 Uploaded Telegram image to GitHub: {gh_img_path}')
                                    else:
                                        log.warning(f'📸 Failed to upload image to GitHub: {put_resp.status}')
                        
                        # Apply OCR if we still don't have a good title
                        # fallback_title is usually just the price in @Shark_ali
                        if product_title == fallback_title and downloaded and os.path.exists(downloaded):
                            log.info(f'🔍 Title is fallback, attempting OCR on downloaded image...')
                            ocr_title = extract_title_from_image(downloaded)
                            if ocr_title:
                                log.info(f'👁️ OCR extracted title: "{ocr_title[:50]}..."')
                                product_title = ocr_title
                                translated_title = clean_and_translate_title(product_title)
                        
                        # Cleanup temp file
                        try:
                            os.remove(downloaded)
                        except:
                            pass
                except Exception as img_err:
                    log.warning(f'📸 Failed to download Telegram image: {img_err}')
        else:
            # No product IDs found — skip
            log.info(f"⏭ No AliExpress product IDs found, skipping")
            return

        # --- BRAND FILTER: only Baseus products ---
        _all_text = (product_title + ' ' + raw_text).lower()
        if 'baseus' not in _all_text:
            log.info(f"⏭ Skipping non-Baseus product: {product_title[:60]}")
            return
        
        # --- Detect category for hashtags ---
        category = detect_category(product_title, raw_text)
        
        # Build hashtags based on category
        category_hashtags = {
            'electronics': '#електроніка #гаджети',
            'beauty': '#краса #косметика',
            'home': '#дім #побут',
            'fashion': '#мода #одяг',
            'accessories': '#аксесуари',
            'sport': '#спорт #фітнес',
            'toys': '#іграшки',
            'tools': '#інструменти',
            'auto': '#авто',
            'hot': '#хіт #топ',
            'new': '#новинка',
        }
        hashtags = category_hashtags.get(category, '#aliexpress')
        hashtags += ' #aliexpress #знижки'
        
        # --- Build CLEAN minimal Telegram post ---
        # Use translated title if available, otherwise clean fallback
        display_title = translated_title or clean_and_translate_title(product_title)
        short_title = display_title[:80]
        if len(display_title) > 80:
            last_space = short_title.rfind(' ')
            if last_space > 40:
                short_title = short_title[:last_space]
        
        post_lines = []
        post_lines.append(f"<b>{short_title}</b>")
        post_lines.append("")
        
        # Price line
        price_val = fallback_price['value']
        price_curr = fallback_price['currency']
        if price_curr == 'UAH':
            price_str = f"💰 <b>{price_val:.0f} грн</b>"
        else:
            price_str = f"💰 <b>${price_val:.2f}</b>"
        
        if coins_info:
            price_str += f" ({coins_info})"
        post_lines.append(price_str)
        
        # Promo codes
        if promo_codes:
            if len(promo_codes) == 1:
                post_lines.append(f"🏷 Промокод: <code>{promo_codes[0]}</code>")
            else:
                codes_formatted = " / ".join(f"<code>{c}</code>" for c in promo_codes)
                post_lines.append(f"🏷 Промокоди: {codes_formatted}")
        
        # Price note (if different from coins_info)
        if price_note and price_note.lower() != coins_info.lower():
            post_lines.append(f"💡 {price_note}")
        
        post_lines.append("")
        post_lines.append(f"👉 <a href='{affiliate_link}'>Купити на AliExpress</a>")
        post_lines.append("")
        post_lines.append(hashtags)
        
        # --- Contextual FAQ tip ---
        global _total_posts_sent
        _total_posts_sent += 1
        faq_tip = ''
        if coins_info:
            faq_tip = random.choice(_CONTEXTUAL_TIPS['coins'])
        elif promo_text:
            faq_tip = random.choice(_CONTEXTUAL_TIPS['promo'])
        elif _total_posts_sent % FAQ_LINK_EVERY_N == 0:
            faq_tip = random.choice(_CONTEXTUAL_TIPS['generic'])
        
        if faq_tip:
            post_lines.append(faq_tip)
        
        text_html = "\n".join(post_lines)
        
        # --- Send to Telegram ---
        # Send media: for WebPage, extract the photo; for regular media, send as-is
        if isinstance(message.media, MessageMediaWebPage):
            webpage = message.media.webpage
            media_to_send = getattr(webpage, 'photo', None) or getattr(webpage, 'document', None)
        else:
            media_to_send = message.media if message.media else None
        
        await client.send_message(
            TARGET_CHANNEL,
            message=text_html,
            parse_mode='html',
            file=media_to_send,
            link_preview=False
        )
        
        log.info(f"✅ Posted: {short_title[:50]}... | {price_str}")

        # --- Save to GitHub for the website ---
        # Polish translation of title
        title_for_site = display_title or product_title or f'Товар AliExpress #{pid}'
        title_pl = translate_to_polish(product_title or display_title or '')

        product_data = {
            'id': pid,
            'title': title_for_site,
            'title_pl': title_pl,
            'price': fallback_price['value'],
            'currency': fallback_price['currency'],
            'original_link': original_link,
            'image_path': image_url,
            'promo_text': promo_text,
            'price_note': price_note,
            'source_channel': event.chat.title or str(event.chat_id),
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'raw_text': raw_text,
        }
        log.info(f'✅ New product for site: {pid} | Price: ${fallback_price or "?"}')
        
        saved = queue_product_for_github(product_data)
            
    except Exception as e:
        log.error(f"⚠️ Error processing message: {e}", exc_info=True)

BACKFILL_LIMIT = 20  # Check last N messages per channel on startup
BACKFILL_MAX_QUEUE = 10  # Max posts to queue from backfill

async def startup_backfill():
    """Check last N messages from donor channels and process any missed posts.
    
    This catches posts that arrived while the parser was offline (restart, crash, etc).
    Only processes posts with AliExpress links that are NOT in seen_products.
    """
    log.info(f"🔄 Startup backfill: checking last {BACKFILL_LIMIT} posts from {len(DONOR_CHANNELS)} channels...")
    
    total_found = 0
    total_new = 0
    
    for channel_name in DONOR_CHANNELS:
        if total_new >= BACKFILL_MAX_QUEUE:
            log.info(f"   ⏭ Backfill queue limit reached ({BACKFILL_MAX_QUEUE}), skipping remaining channels")
            break
        try:
            entity = await client.get_entity(channel_name)
            messages = await client.get_messages(entity, limit=BACKFILL_LIMIT)
            
            channel_new = 0
            for message in messages:
                if total_new >= BACKFILL_MAX_QUEUE:
                    break
                    
                if not message.text and not message.raw_text:
                    continue
                
                raw_text = message.raw_text or ''
                
                # Find URLs
                urls = set(re.findall(r'https?://[^\s<"]+', raw_text))
                if not urls:
                    continue
                
                total_found += 1
                
                # Check for AliExpress or redirect URLs
                has_ali_url = False
                for u in urls:
                    # Check direct AliExpress
                    if 'aliexpress.com' in u or 's.click.aliexpress.com' in u:
                        has_ali_url = True
                        break
                    # Check redirect patterns
                    for rp in REDIRECT_PATTERNS:
                        if re.match(rp, u):
                            has_ali_url = True
                            break
                    if has_ali_url:
                        break
                
                if not has_ali_url:
                    continue
                
                # Resolve URLs to get item IDs
                product_ids = []
                async with aiohttp.ClientSession() as session:
                    for u in urls:
                        clean_url, item_id = await resolve_and_clean_url(u, session)
                        if item_id:
                            product_ids.append(item_id)
                
                if not product_ids:
                    continue
                
                # Skip if ANY product ID is already seen (not ALL)
                any_seen = any(pid in seen_products for pid in product_ids)
                if any_seen:
                    # Pre-mark all IDs as seen to avoid re-checking next restart
                    for pid in product_ids:
                        if pid not in seen_products:
                            seen_products[pid] = 0
                    continue
                
                # Found unseen product(s) — queue for processing
                channel_new += 1
                log.info(f"🔄 Backfill: found unseen product(s) in {channel_name}: {', '.join(product_ids)}")
                
                # Create a fake event-like object and queue for processing
                class BackfillEvent:
                    def __init__(self, msg, chat):
                        self.message = msg
                        self.chat = chat
                        self.chat_id = chat.id
                
                event = BackfillEvent(message, entity)
                await _message_queue.put(event)
                total_new += 1
            
            log.info(f"   📋 {channel_name}: checked {len(messages)} posts, {channel_new} new")
            
        except Exception as e:
            log.warning(f"   ⚠️ Backfill failed for {channel_name}: {e}")
    
    # Save updated seen_products
    save_seen(seen_products)
    log.info(f"🔄 Backfill done: {total_found} posts with URLs, {total_new} new products queued")


async def main():
    await client.start()
    me = await client.get_me()
    
    log.info(f"✅ Клієнт запущений: {me.first_name}")
    log.info(f"👂 Слухаю канали: {', '.join(DONOR_CHANNELS)}")
    log.info(f"📤 Цільовий канал: {TARGET_CHANNEL}")
    log.info(f"🌐 GitHub: {GITHUB_REPO}")
    log.info(f"⏱️ Затримка між постами: {MIN_POST_DELAY}-{MAX_POST_DELAY}с | Пропуск кожного {SKIP_EVERY_N}-го | Cooldown скрейпу: {SCRAPE_COOLDOWN}с")
    log.info(f"📦 GitHub batch mode: flush every {_github_flush_interval}s")
    log.info("─" * 50)
    
    # Start queue processor as background task
    asyncio.create_task(process_queue())
    # Start GitHub batch flusher as background task
    asyncio.create_task(github_flush_task())
    
    # Run startup backfill to catch missed posts
    try:
        await startup_backfill()
    except Exception as e:
        log.error(f"⚠️ Startup backfill error: {e}", exc_info=True)
    
    await client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
