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
from datetime import datetime, timezone

from telethon import TelegramClient, events
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument, MessageMediaWebPage
import aiohttp

from config import (
    API_ID, API_HASH, SESSION_NAME,
    DONOR_CHANNELS, TARGET_CHANNEL,
    SEEN_DB, IMAGES_DIR,
    GITHUB_TOKEN, GITHUB_REPO, GITHUB_PRODUCTS_PATH,
)

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
log = logging.getLogger('copier')

# --- Ensure directories ---
os.makedirs(IMAGES_DIR, exist_ok=True)

# --- Deduplication ---
def load_seen():
    if os.path.exists(SEEN_DB):
        try:
            with open(SEEN_DB, 'r', encoding='utf-8') as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def save_seen(seen_set):
    with open(SEEN_DB, 'w', encoding='utf-8') as f:
        json.dump(list(seen_set), f)

seen_products = load_seen()

async def resolve_and_clean_url(url: str, session: aiohttp.ClientSession):
    """
    Resolve redirect if needed and clean AliExpress URL from ref params.
    Returns (clean_url, item_id)
    """
    final_url = url
    try:
        async with session.get(url, allow_redirects=True, timeout=15) as resp:
            final_url = str(resp.url)
    except Exception as e:
        log.warning(f"Failed to resolve URL {url}: {e}")

    # Pattern handles /item/123.html, /i/123.html, ?itemId=123, &productIds=123
    match = re.search(r'(?:/(?:item|i)/|itemId=|productIds=)(\d+)(?:\.html|&|$)', final_url, re.IGNORECASE)
    if match:
        item_id = match.group(1)
        clean_url = f"https://aliexpress.com/item/{item_id}.html"
        return clean_url, item_id
    
    return final_url, None

async def scrape_aliexpress_product(product_url: str, session: aiohttp.ClientSession):
    """
    Scrape AliExpress product page to get title and image URL
    from Open Graph meta tags.
    Returns {'title': str, 'image_url': str} or None on failure.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'uk-UA,uk;q=0.9,en;q=0.8',
    }
    try:
        async with session.get(product_url, headers=headers, timeout=20) as resp:
            if resp.status != 200:
                log.warning(f'AliExpress page returned {resp.status} for {product_url}')
                return None
            html = await resp.text()
        
        # Extract og:title
        title_match = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']+)', html, re.IGNORECASE)
        title = title_match.group(1).strip() if title_match else None
        # Clean title: remove " - AliExpress XX" suffix
        if title:
            title = re.sub(r'\s*-\s*AliExpress\s*\d*$', '', title).strip()
        
        # Extract og:image
        image_match = re.search(r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)', html, re.IGNORECASE)
        image_url = image_match.group(1).strip() if image_match else None
        
        # Try to extract price from page if possible (AliExpress often blocks this without JS, but we can check meta tags)
        price = None
        price_match = re.search(r'<meta\s+property=["\']product:price:amount["\']\s+content=["\']([\d\.]+)["\']', html, re.IGNORECASE)
        if price_match:
            try:
                price = float(price_match.group(1))
            except ValueError:
                pass
        
        if title or image_url or price:
            log.info(f'🔍 Scraped from AliExpress: "{(title or "?")[:60]}" | Price: {price}')
            return {'title': title, 'image_url': image_url, 'price': price}
        
        return None
    except Exception as e:
        log.warning(f'Failed to scrape AliExpress page: {e}')
        return None

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

# --- GitHub Direct API ---
async def save_product_to_github(product_data):
    """Save product directly to GitHub products.json via API."""
    api_url = f'https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_PRODUCTS_PATH}'
    headers = {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'ShopNaAli-Parser',
    }
    
    import random
    
    # Detect category from title + raw text
    category = detect_category(product_data.get('title', ''), product_data['raw_text'])
    
    site_product = {
        'id': product_data['id'],
        'title': product_data['title'],
        'price': product_data.get('price') or 0,
        'currency': product_data.get('currency', 'USD'),
        'category': category,
        'rating': round(random.uniform(4.7, 5.0), 1),
        'orders': random.randint(100, 2000),
        'image': product_data.get('image_path', ''),
        'link': product_data['original_link'],
        'affiliate_link': product_data['original_link'],
        'description': '',
        'promo_text': product_data.get('promo_text', ''),
        'price_note': product_data.get('price_note', ''),
        'source_channel': product_data.get('source_channel', ''),
        'added_at': product_data['timestamp'],
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            # GET current file
            async with session.get(api_url, headers=headers, timeout=15) as resp:
                if resp.status != 200:
                    log.error(f'GitHub GET failed: {resp.status}')
                    return False
                gh_data = await resp.json()
            
            sha = gh_data['sha']
            content = base64.b64decode(gh_data['content']).decode('utf-8')
            products = json.loads(content)
            
            # Add new product at the beginning
            products.setdefault('products', []).insert(0, site_product)
            
            # Encode back
            updated = base64.b64encode(
                json.dumps(products, ensure_ascii=False, indent=2).encode('utf-8')
            ).decode('utf-8')
            
            # PUT updated file
            put_body = {
                'message': f'Add product {site_product["id"]}',
                'content': updated,
                'sha': sha,
            }
            async with session.put(
                api_url,
                headers=headers,
                json=put_body,
                timeout=15,
            ) as put_resp:
                if put_resp.status == 200:
                    log.info(f'🌐 Saved to GitHub: {site_product["id"]}')
                    return True
                else:
                    error_text = await put_resp.text()
                    log.error(f'GitHub PUT failed: {put_resp.status} — {error_text}')
                    return False
    except Exception as e:
        log.error(f'GitHub API error: {e}')
        return False

# --- Telegram Client ---
client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
client.parse_mode = 'html'

@client.on(events.NewMessage(chats=DONOR_CHANNELS))
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
        
        async with aiohttp.ClientSession() as session:
            for u in urls_sorted:
                clean_url, item_id = await resolve_and_clean_url(u, session)
                if clean_url != u:
                    text_html = text_html.replace(u, '')
                else:
                    text_html = text_html.replace(u, '')
                if item_id:
                    product_ids_found.append(item_id)
                    clean_links_added.add(clean_url)
        
        # Deduplication check
        is_duplicate = False
        for pid in product_ids_found:
            if pid in seen_products:
                is_duplicate = True
                break
                
        if is_duplicate:
            log.info(f"⏭️ Skipping duplicate post; already seen product(s).")
            return
            
        # Add to seen
        for pid in product_ids_found:
            seen_products.add(pid)
        save_seen(seen_products)

        # Append clean links at the end
        if clean_links_added:
            text_html += "\n\n🔗 <b>Посилання:</b>\n"
            for cl in clean_links_added:
                # Provide a shorter display text for the link
                match = re.search(r'/item/(\d+)\.html', cl)
                display_text = f"aliexpress.com/item/{match.group(1)}.html" if match else cl
                text_html += f"👉 <a href='{cl}'>{display_text}</a>\n"

        # Replace donor channel mentions with our channel
        for donor in DONOR_CHANNELS:
            donor_name = donor.lstrip('@')
            text_html = re.sub(rf'@{donor_name}', '@Shop_DoBaksa', text_html, flags=re.IGNORECASE)
            raw_text = re.sub(rf'@{donor_name}', '@Shop_DoBaksa', raw_text, flags=re.IGNORECASE)

        # Send the modified message to Telegram
        # Telegram limits captions to 1024 chars; if longer, send text and media separately
        media_to_send = message.media if not isinstance(message.media, MessageMediaWebPage) else None
        
        if media_to_send and len(text_html) > 1024:
            await client.send_message(
                TARGET_CHANNEL,
                message=text_html,
                parse_mode='html',
                link_preview=False
            )
            await client.send_message(
                TARGET_CHANNEL,
                file=media_to_send,
            )
        else:
            await client.send_message(
                TARGET_CHANNEL,
                message=text_html,
                parse_mode='html',
                file=media_to_send,
                link_preview=False
            )
        
        log.info(f"✅ Copied message from {event.chat.title} to {TARGET_CHANNEL}")

        # --- Save products to GitHub for the website ---
        fallback_title = clean_text(raw_text)[:200]
        fallback_price = extract_price(raw_text)
        
        async with aiohttp.ClientSession() as scrape_session:
            # Only save the first product ID for the website to avoid duplicate cards
            for pid in product_ids_found[:1]:
                original_link = f"https://aliexpress.com/item/{pid}.html"
                
                # Scrape AliExpress product page for title and image
                scraped = await scrape_aliexpress_product(original_link, scrape_session)
                
                product_title = fallback_title
                image_url = ''
                
                if scraped:
                    if scraped.get('title'):
                        product_title = scraped['title'][:200]
                    
                    # Use AliExpress CDN image URL directly
                    if scraped.get('image_url'):
                        image_url = scraped['image_url']
                        log.info(f'📸 Got image URL from AliExpress')
                    
                    # Use scraped price if we couldn't find one in the text
                    if fallback_price['value'] == 0 and scraped.get('price'):
                        fallback_price = {'value': scraped['price'], 'currency': 'USD'}
                        log.info(f'💰 Found price on AliExpress page: ${scraped["price"]}')

                # Extract promo code from parentheses like "(+купон і промокод IFPU3KTD)"
                promo_match = re.search(r'\((?:.*?(?:промокод|купон|монети|знижк|code).*?)\)', raw_text, re.IGNORECASE | re.DOTALL)
                
                promo_text = ""
                if promo_match:
                    # Find sequences of 4 or more uppercase letters/numbers, allowing for '/'
                    codes = re.findall(r'[A-Z0-9/]{4,}', promo_match.group(0))
                    if codes:
                        promo_text = ' '.join(codes)

                # Extract price note — describes how to get this price
                # e.g. "з купоном+монети", "купон під товаром + монети", "+монети"
                price_note = ""
                price_note_patterns = [
                    # Parenthesized: "(з купоном + монети)", "(купон під товаром)"
                    r'\(([^)]*(?:купон|монет|знижк|промокод|code|coin)[^)]*)\)',
                    # Standalone patterns outside parentheses
                    r'(?:ціна\s+)?(?:з|із)\s+(купон\w*(?:\s*\+?\s*монет\w*)?)',
                    r'(купон\s+під\s+товаром(?:\s*\+?\s*монет\w*)?)',
                    r'(?<!\w)(\+\s*монет\w*)',
                    r'((?:з\s+)?монет(?:и|ами|ками)(?:\s*\+?\s*купон\w*)?)',
                ]
                for pattern in price_note_patterns:
                    note_match = re.search(pattern, raw_text, re.IGNORECASE)
                    if note_match:
                        note = note_match.group(1).strip()
                        # Clean up: remove excessive whitespace, trim
                        note = re.sub(r'\s+', ' ', note).strip(' .,;:!-')
                        if note and len(note) < 80:
                            # Capitalize first letter
                            price_note = note[0].upper() + note[1:] if len(note) > 1 else note.upper()
                            break

                product_data = {
                    'id': pid,
                    'title': product_title or f'Товар AliExpress #{pid}',
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
                
                # Save directly to GitHub
                await save_product_to_github(product_data)
            
    except Exception as e:
        log.error(f"⚠️ Error processing message: {e}", exc_info=True)

async def main():
    await client.start()
    me = await client.get_me()
    
    log.info(f"✅ Клієнт запущений: {me.first_name}")
    log.info(f"👂 Слухаю канали: {', '.join(DONOR_CHANNELS)}")
    log.info(f"📤 Цільовий канал: {TARGET_CHANNEL}")
    log.info(f"🌐 GitHub: {GITHUB_REPO}")
    log.info("─" * 50)
    
    await client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
