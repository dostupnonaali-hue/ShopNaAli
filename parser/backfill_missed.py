"""
Backfill 6 missed posts (#86-91) from @dobaksa_shop.
Resolves redirect URLs, scrapes product info, and pushes to GitHub.
"""
import json
import re
import os
import sys
import time
import random
import base64
import urllib.request
from pathlib import Path
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / '.env')

GITHUB_TOKEN = os.getenv('GITHUB_TOKEN', '')
GITHUB_REPO = os.getenv('GITHUB_REPO', 'dostupnonaali-hue/ShopNaAli')
BLOG_JSON_PATH = 'site/data/products.json'
SEEN_DB = Path(__file__).parent / 'seen_products.json'
AFF_SHORT_KEY = os.getenv('AFF_SHORT_KEY', '')

# The 6 missed posts with their redirect URLs and promo codes
MISSED_POSTS = [
    {
        'redirect_url': 'https://go.skidkovoz.com/GA89t',
        'promo_codes': ['AM0024', 'IFPXJIKH', 'IFPSRAB5', 'IFPEG0RY', 'IFPWDRYJ', 'IFPJVC7S'],
        'source': '@ChinaGoodBuy',
        'post_num': 86,
    },
    {
        'redirect_url': 'https://go.skidkovoz.com/lSE2b',
        'promo_codes': ['MAMF401', 'IFPQLH6A', 'IFPXKADF', 'IFPQLCC4', 'IFPBNZ5Q', 'IFP7YO03'],
        'source': '@ChinaGoodBuy',
        'post_num': 87,
    },
    {
        'redirect_url': 'https://go.skidkovoz.com/WAShE',
        'promo_codes': ['AEKRBR5', 'IFPQLH6A', 'IFPXKADF', 'IFPQLCC4', 'IFPBNZ5Q', 'IFP7YO03'],
        'source': '@ChinaGoodBuy',
        'post_num': 88,
    },
    {
        'redirect_url': 'https://go.skidkovoz.com/dEV9C',
        'promo_codes': ['ALL3K06', 'IFPXJIKH', 'IFPSRAB5', 'IFPEG0RY', 'IFPWDRYJ', 'IFPJVC7S'],
        'source': '@ChinaGoodBuy',
        'post_num': 89,
    },
    {
        'redirect_url': 'https://go.skidkovoz.com/GJnRe',
        'promo_codes': ['UAVJ104', 'CDUA13', 'AEUA13', 'IFPCOVLV', 'IFP901UG', 'IFPGKWUZ', 'IFPQRM5Z', 'IFP5GEJ3'],
        'source': '@ChinaGoodBuy',
        'post_num': 90,
    },
    {
        'redirect_url': 'https://go.skidkovoz.com/Ro3eJ',
        'promo_codes': ['BSMA37', 'CDUA13', 'AEUA13', 'IFPCOVLV', 'IFP901UG', 'IFPGKWUZ', 'IFPQRM5Z', 'IFP5GEJ3'],
        'source': '@ChinaGoodBuy',
        'post_num': 91,
    },
]

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
]


def resolve_redirect(url: str) -> str:
    """Follow redirect to get final AliExpress URL."""
    try:
        req = urllib.request.Request(url, method='HEAD', headers={
            'User-Agent': random.choice(USER_AGENTS),
        })
        req.get_method = lambda: 'GET'
        resp = urllib.request.urlopen(req, timeout=15)
        return resp.url
    except Exception as e:
        print(f'  ⚠️ HEAD failed ({e}), trying GET...')
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': random.choice(USER_AGENTS),
            })
            resp = urllib.request.urlopen(req, timeout=15)
            return resp.url
        except Exception as e2:
            print(f'  ❌ GET also failed: {e2}')
            return url


def extract_item_id(url: str) -> str:
    """Extract AliExpress item ID from URL."""
    match = re.search(r'(?:/(?:item|i)/|itemId=|productIds=)(\d+)(?:\.html|&|$)', url, re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def scrape_product(item_id: str) -> dict:
    """Scrape product info from AliExpress."""
    url = f'https://www.aliexpress.com/item/{item_id}.html'
    headers = {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.google.com/',
    }
    
    try:
        req = urllib.request.Request(url, headers=headers)
        resp = urllib.request.urlopen(req, timeout=25)
        html = resp.read().decode('utf-8', errors='replace')
        
        title = None
        image_url = None
        price = None
        
        # OG title
        og = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']+)', html, re.I)
        if not og:
            og = re.search(r'<meta\s+content=["\']([^"\']+)["\']\s+property=["\']og:title["\']', html, re.I)
        if og:
            title = re.sub(r'\s*[-|]\s*AliExpress\s*\d*$', '', og.group(1)).strip()
        
        # OG image
        og_img = re.search(r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)', html, re.I)
        if not og_img:
            og_img = re.search(r'<meta\s+content=["\']([^"\']+)["\']\s+property=["\']og:image["\']', html, re.I)
        if og_img:
            image_url = og_img.group(1).strip()
        
        # Price
        price_m = re.search(r'<meta\s+property=["\']product:price:amount["\']\s+content=["\']([\\d.]+)["\']', html, re.I)
        if price_m:
            try:
                price = float(price_m.group(1))
            except ValueError:
                pass
        
        return {'title': title, 'image_url': image_url, 'price': price}
    except Exception as e:
        print(f'  ⚠️ Scrape failed: {e}')
        return None


def make_affiliate_link(item_id: str) -> str:
    clean = f'https://aliexpress.com/item/{item_id}.html'
    if AFF_SHORT_KEY:
        from urllib.parse import quote
        return f'https://s.click.aliexpress.com/deep_link.htm?aff_short_key={AFF_SHORT_KEY}&dl_target_url={quote(clean, safe="")}'
    return clean


def translate_title(title: str, target='uk') -> str:
    """Translate title using deep_translator."""
    try:
        from deep_translator import GoogleTranslator
        t = GoogleTranslator(source='auto', target=target)
        translated = t.translate(title)
        if translated and len(translated) > 3:
            return translated[0].upper() + translated[1:]
    except Exception as e:
        print(f'  ⚠️ Translation failed: {e}')
    return title


def detect_category(title: str) -> str:
    """Simple category detection from title."""
    title_lower = title.lower() if title else ''
    categories = {
        'electronics': ['cable', 'charger', 'usb', 'bluetooth', 'headphone', 'earbuds', 'speaker',
                        'power bank', 'powerbank', 'led', 'lamp', 'camera', 'keyboard', 'mouse',
                        'adapter', 'hub', 'навушник', 'кабель', 'зарядк', 'колонк'],
        'home': ['kitchen', 'cup', 'knife', 'container', 'organizer', 'pillow', 'blanket',
                 'curtain', 'vacuum', 'mop', 'thermos', 'кухн', 'подушк', 'пилосос'],
        'fashion': ['shirt', 'pants', 'jacket', 'dress', 'shoes', 'sneakers', 'hoodie',
                    'футболк', 'штан', 'куртк', 'кросівк'],
        'beauty': ['cosmetic', 'makeup', 'cream', 'shampoo', 'perfume', 'косметик', 'крем'],
        'auto': ['car', 'dashcam', 'авто', 'автомобіль', 'тримач для телефон'],
        'tools': ['tool', 'drill', 'wrench', 'screwdriver', 'інструмент', 'дриль'],
        'accessories': ['case', 'cover', 'strap', 'bag', 'wallet', 'чохол', 'сумк'],
        'sport': ['sport', 'fitness', 'yoga', 'bicycle', 'camping', 'спорт', 'фітнес'],
        'toys': ['toy', 'lego', 'puzzle', 'drone', 'іграшк', 'дрон'],
    }
    for cat, keywords in categories.items():
        for kw in keywords:
            if kw in title_lower:
                return cat
    return 'new'


def github_get_products():
    """Fetch products.json from GitHub."""
    url = f'https://raw.githubusercontent.com/{GITHUB_REPO}/main/{BLOG_JSON_PATH}'
    req = urllib.request.Request(url, headers={'User-Agent': 'ShopNaAli-Backfill'})
    resp = urllib.request.urlopen(req, timeout=30)
    return json.loads(resp.read().decode('utf-8'))


def github_put_file(path, content_bytes, message):
    """Push file to GitHub via Contents API."""
    api_url = f'https://api.github.com/repos/{GITHUB_REPO}/contents/{path}'
    headers = {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'ShopNaAli-Backfill',
    }
    
    # Get current SHA
    req = urllib.request.Request(api_url, headers=headers)
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        sha = json.loads(resp.read().decode('utf-8')).get('sha')
    except Exception:
        sha = None
    
    body = {
        'message': message,
        'content': base64.b64encode(content_bytes).decode('utf-8'),
    }
    if sha:
        body['sha'] = sha
    
    req = urllib.request.Request(
        api_url,
        data=json.dumps(body).encode('utf-8'),
        headers={**headers, 'Content-Type': 'application/json'},
        method='PUT',
    )
    resp = urllib.request.urlopen(req, timeout=30)
    return resp.status


def load_seen():
    """Load seen products dict."""
    if SEEN_DB.exists():
        try:
            data = json.loads(SEEN_DB.read_text(encoding='utf-8'))
            if isinstance(data, list):
                return {str(pid): 0 for pid in data}
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {}


def save_seen(seen_dict):
    SEEN_DB.write_text(json.dumps(seen_dict), encoding='utf-8')


def main():
    print('=' * 60)
    print('🔄 Backfill 6 missed posts (#86-91)')
    print('=' * 60)
    
    # Load current products
    print('\n📦 Loading products from GitHub...')
    data = github_get_products()
    existing_ids = {p['id'] for p in data['products']}
    print(f'   {len(data["products"])} products currently on site')
    
    # Load seen products
    seen = load_seen()
    
    new_products = []
    
    for post in MISSED_POSTS:
        print(f'\n--- Post #{post["post_num"]} ---')
        print(f'   URL: {post["redirect_url"]}')
        
        # Resolve redirect
        print(f'   🔀 Resolving redirect...')
        final_url = resolve_redirect(post['redirect_url'])
        print(f'   → {final_url[:80]}...')
        
        item_id = extract_item_id(final_url)
        if not item_id:
            print(f'   ❌ Could not extract item ID')
            continue
        print(f'   📦 Item ID: {item_id}')
        
        # Check duplicate
        if item_id in existing_ids:
            print(f'   ⏭️ Already on site, skipping')
            seen[item_id] = 0
            continue
        
        # Scrape product
        print(f'   🔍 Scraping product info...')
        scraped = scrape_product(item_id)
        time.sleep(3)  # Cooldown
        
        title = f'AliExpress товар {item_id}'
        image_url = ''
        price = 0
        
        if scraped:
            if scraped.get('title'):
                title = scraped['title'][:200]
                print(f'   📝 Title: {title[:60]}...')
            if scraped.get('image_url'):
                image_url = scraped['image_url']
                print(f'   📸 Image: found')
            if scraped.get('price'):
                price = scraped['price']
                print(f'   💰 Price: ${price}')
        
        # Translate
        translated = translate_title(title, 'uk')
        translated_pl = translate_title(title, 'pl')
        print(f'   🇺🇦 UA: {translated[:50]}...')
        print(f'   🇵🇱 PL: {translated_pl[:50]}...')
        
        # Build product
        category = detect_category(title)
        promo_text = ', '.join(post['promo_codes'][:3])  # First 3 codes
        
        product = {
            'id': item_id,
            'title': translated,
            'title_pl': translated_pl,
            'price': price,
            'currency': 'USD',
            'category': category,
            'rating': round(random.uniform(4.7, 5.0), 1),
            'orders': random.randint(100, 2000),
            'image': image_url,
            'link': f'https://aliexpress.com/item/{item_id}.html',
            'affiliate_link': make_affiliate_link(item_id),
            'description': '',
            'promo_text': promo_text,
            'price_note': '',
            'source_channel': '@dobaksa_shop',
            'added_at': datetime.now(timezone.utc).isoformat(),
        }
        
        new_products.append(product)
        existing_ids.add(item_id)
        seen[item_id] = price
        print(f'   ✅ Added!')
    
    if not new_products:
        print('\n⚠️ No new products to add')
        save_seen(seen)
        return
    
    # Push to GitHub
    print(f'\n🚀 Pushing {len(new_products)} new products to GitHub...')
    data['products'] = new_products + data['products']
    content = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
    status = github_put_file(
        BLOG_JSON_PATH,
        content,
        f'backfill: add {len(new_products)} missed products from posts #86-91'
    )
    print(f'   GitHub response: {status}')
    
    # Save seen
    save_seen(seen)
    print(f'   💾 Updated seen_products.json')
    
    print(f'\n✅ Done! Added {len(new_products)} products:')
    for p in new_products:
        print(f'   • {p["id"]} — {p["title"][:50]}')


if __name__ == '__main__':
    main()
