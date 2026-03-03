"""
Shop Na Ali — Parser Configuration
Loads settings from .env file
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- Telegram API ---
_api_id = os.getenv('TELEGRAM_API_ID')
_api_hash = os.getenv('TELEGRAM_API_HASH')
if not _api_id or not _api_hash:
    raise ValueError(
        '❌ TELEGRAM_API_ID та TELEGRAM_API_HASH мають бути задані у файлі .env'
    )
API_ID = int(_api_id)
API_HASH = _api_hash
SESSION_NAME = os.getenv('SESSION_NAME', 'shopnaali_session')

# --- Donor Channels ---
DONOR_CHANNELS = [
    '@theCheapestAliExpress',
    '@AliReviewers',
    '@halyavaZaliExpress',
    '@dobaksa_shop',
]

# --- Target ---
TARGET_CHANNEL = os.getenv('TARGET_CHANNEL', '@Ekcoin')

# --- n8n Webhook ---
N8N_WEBHOOK_URL = os.getenv('N8N_WEBHOOK_URL', 'https://n8n.21000.online/webhook/aliexpress-product')

# --- AliExpress Affiliate ---
AFFILIATE_TRACKING_ID = os.getenv('AFFILIATE_TRACKING_ID', '')

# --- GitHub API (for direct products.json updates) ---
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN', '')
GITHUB_REPO = os.getenv('GITHUB_REPO', 'dostupnonaali-hue/ShopNaAli')
GITHUB_PRODUCTS_PATH = 'site/data/products.json'

# --- Paths ---
IMAGES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'site', 'images')
PRODUCTS_JSON = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'site', 'data', 'products.json')
SEEN_DB = os.path.join(os.path.dirname(__file__), 'seen_products.json')

# --- Regex patterns for AliExpress URLs ---
ALIEXPRESS_PATTERNS = [
    r'https?://(?:www\.)?aliexpress\.com/item/(\d+)\.html',
    r'https?://(?:[\w]+\.)?aliexpress\.(?:com|ru|us)/item/(\d+)\.html',
    r'https?://a\.aliexpress\.com/[\w/_-]+',
    r'https?://s\.click\.aliexpress\.com/e/[\w/_-]+',
    r'https?://(?:www\.)?aliexpress\.com/[\w/.-]*(?:\?.*)?',
]
