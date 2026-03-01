"""
Shop Na Ali — Telegram Channel Parser
Monitors donor channels, extracts AliExpress links and images,
sends data to n8n webhook for processing.

Based on existing copier_bot.py, extended for full product parsing.
"""

import asyncio
import json
import os
import re
import hashlib
import logging
from datetime import datetime, timezone

from telethon import TelegramClient, events
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument
import aiohttp

from config import (
    API_ID, API_HASH, SESSION_NAME,
    DONOR_CHANNELS, N8N_WEBHOOK_URL,
    IMAGES_DIR, PRODUCTS_JSON, SEEN_DB,
    ALIEXPRESS_PATTERNS,
)

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
log = logging.getLogger('shopnaali')

# --- Ensure directories ---
os.makedirs(IMAGES_DIR, exist_ok=True)
os.makedirs(os.path.dirname(PRODUCTS_JSON), exist_ok=True)

# --- Deduplication ---
def load_seen():
    """Load set of already-processed product IDs."""
    if os.path.exists(SEEN_DB):
        try:
            with open(SEEN_DB, 'r', encoding='utf-8') as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def save_seen(seen_set):
    """Persist seen product IDs."""
    with open(SEEN_DB, 'w', encoding='utf-8') as f:
        json.dump(list(seen_set), f)

seen_products = load_seen()

# --- URL Extraction ---
def extract_aliexpress_urls(text):
    """Extract all AliExpress URLs from message text."""
    urls = []
    if not text:
        return urls
    for pattern in ALIEXPRESS_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            if isinstance(match, tuple):
                match = match[0]
            # Reconstruct full URL if we captured just the product ID
            if match.isdigit():
                urls.append(f'https://aliexpress.com/item/{match}.html')
            else:
                urls.append(match)
    # Also look for raw URLs in text
    raw_urls = re.findall(r'https?://[^\s<>"\']+aliexpress[^\s<>"\']+', text, re.IGNORECASE)
    urls.extend(raw_urls)
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for url in urls:
        clean = url.rstrip('.,;:!?)>')
        if clean not in seen:
            seen.add(clean)
            unique.append(clean)
    return unique

def extract_product_id(url):
    """Extract numeric product ID from AliExpress URL."""
    match = re.search(r'/item/(\d+)\.html', url)
    if match:
        return match.group(1)
    # Fallback: hash the URL
    return hashlib.md5(url.encode()).hexdigest()[:12]

def extract_price(text):
    """Try to extract price from message text."""
    if not text:
        return None
    # Patterns: $0.47, 0.47$, 0,47$, USD 0.47, ціна: 0.47
    patterns = [
        r'\$\s*(\d+[.,]\d{1,2})',
        r'(\d+[.,]\d{1,2})\s*\$',
        r'(\d+[.,]\d{1,2})\s*(?:USD|usd|дол)',
        r'(?:ціна|цена|price|вартість)[:\s]*\$?(\d+[.,]\d{1,2})',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            price_str = match.group(1).replace(',', '.')
            try:
                return float(price_str)
            except ValueError:
                continue
    return None

def clean_text(text):
    """Remove spam, ads, channel mentions from original post text."""
    if not text:
        return ''
    # Remove common ad patterns
    lines = text.split('\n')
    cleaned = []
    skip_patterns = [
        r'підписуйтесь|підпишись|subscribe|join',
        r'@\w+канал|@\w+channel',
        r'реклама|advertisement|sponsored',
        r'👉\s*@',
    ]
    for line in lines:
        should_skip = False
        for pattern in skip_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                should_skip = True
                break
        if not should_skip:
            cleaned.append(line)
    return '\n'.join(cleaned).strip()

# --- Telegram Client ---
client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

@client.on(events.NewMessage(chats=DONOR_CHANNELS))
async def handle_new_post(event):
    """Process new posts from donor channels."""
    try:
        message = event.message
        text = message.text or message.message or ''
        
        # Extract AliExpress URLs
        urls = extract_aliexpress_urls(text)
        
        if not urls:
            log.debug(f'No AliExpress URLs in message from {event.chat.title}')
            return
        
        for url in urls:
            product_id = extract_product_id(url)
            
            # Deduplication
            if product_id in seen_products:
                log.info(f'⏭️  Skipping duplicate: {product_id}')
                continue
            
            seen_products.add(product_id)
            save_seen(seen_products)
            
            # Download image
            image_path = None
            image_filename = None
            if message.media and isinstance(message.media, (MessageMediaPhoto, MessageMediaDocument)):
                image_filename = f'{product_id}.jpg'
                image_path = os.path.join(IMAGES_DIR, image_filename)
                try:
                    await message.download_media(file=image_path)
                    log.info(f'📸 Image saved: {image_filename}')
                except Exception as e:
                    log.warning(f'Failed to download image: {e}')
                    image_path = None
            
            # Extract data
            title = clean_text(text)[:200]  # Truncate title
            price = extract_price(text)
            
            # Build product payload
            product_data = {
                'id': product_id,
                'title': title or f'Товар AliExpress #{product_id}',
                'price': price,
                'original_link': url,
                'image_filename': image_filename,
                'image_path': f'images/{image_filename}' if image_filename else None,
                'source_channel': event.chat.title or str(event.chat_id),
                'source_channel_username': getattr(event.chat, 'username', ''),
                'raw_text': text,
                'message_id': message.id,
                'timestamp': datetime.now(timezone.utc).isoformat(),
            }
            
            log.info(f'✅ New product found: {product_id} | Price: ${price or "?"} | From: {event.chat.title}')
            
            # Send to n8n webhook
            await send_to_n8n(product_data)
            
    except Exception as e:
        log.error(f'⚠️  Error processing message: {e}', exc_info=True)

async def send_to_n8n(product_data):
    """Send product data to n8n webhook for processing."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                N8N_WEBHOOK_URL,
                json=product_data,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status == 200:
                    log.info(f'📤 Sent to n8n: {product_data["id"]}')
                else:
                    log.warning(f'n8n responded with {resp.status}: {await resp.text()}')
                    # Fallback: save locally
                    save_product_locally(product_data)
    except Exception as e:
        log.warning(f'n8n webhook failed: {e}. Saving locally.')
        save_product_locally(product_data)

def save_product_locally(product_data):
    """Fallback: save product directly to products.json."""
    try:
        products = {'products': []}
        if os.path.exists(PRODUCTS_JSON):
            with open(PRODUCTS_JSON, 'r', encoding='utf-8') as f:
                products = json.load(f)
        
        # Convert to site format
        site_product = {
            'id': product_data['id'],
            'title': product_data['title'],
            'price': product_data.get('price', 0),
            'category': 'other',
            'rating': 0,
            'orders': 0,
            'image': product_data.get('image_path', ''),
            'link': product_data['original_link'],
            'affiliate_link': '',  # Will be filled by n8n
            'description': '',
            'source_channel': product_data.get('source_channel', ''),
            'added_at': product_data['timestamp'],
        }
        
        products.setdefault('products', []).insert(0, site_product)
        
        with open(PRODUCTS_JSON, 'w', encoding='utf-8') as f:
            json.dump(products, f, ensure_ascii=False, indent=2)
        
        log.info(f'💾 Saved locally: {product_data["id"]}')
    except Exception as e:
        log.error(f'Failed to save locally: {e}')

async def main():
    """Main entry point."""
    await client.start()
    me = await client.get_me()
    
    log.info(f'✅ Клієнт запущений: {me.first_name} (@{me.username})')
    log.info(f'👂 Слухаю канали: {", ".join(DONOR_CHANNELS)}')
    log.info(f'📤 Webhook: {N8N_WEBHOOK_URL}')
    log.info('─' * 50)
    
    await client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
