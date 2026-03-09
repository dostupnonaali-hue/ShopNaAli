"""
Generate sitemap.xml from products.json on GitHub.
Run this on the server or locally to create/update sitemap.xml.
"""
import json, sys, os, base64, urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
from config import GITHUB_TOKEN, GITHUB_REPO, GITHUB_PRODUCTS_PATH

API_BASE = f'https://api.github.com/repos/{GITHUB_REPO}/contents'
HEADERS = {
    'Authorization': f'token {GITHUB_TOKEN}',
    'Accept': 'application/vnd.github.v3+json',
    'User-Agent': 'ShopNaAli-Sitemap',
}
SITE_URL = 'https://dobaksa.shop'

# Fetch products.json
req = urllib.request.Request(f'{API_BASE}/{GITHUB_PRODUCTS_PATH}', headers=HEADERS)
with urllib.request.urlopen(req, timeout=15) as resp:
    gh_data = json.loads(resp.read().decode('utf-8'))

content = base64.b64decode(gh_data['content']).decode('utf-8')
data = json.loads(content)
products = data.get('products', [])

today = datetime.now(timezone.utc).strftime('%Y-%m-%d')

# Build sitemap
urls = []
urls.append(f'''  <url>
    <loc>{SITE_URL}/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>''')

for p in products:
    pid = p.get('id', '')
    added = p.get('added_at', today)[:10]  # YYYY-MM-DD
    urls.append(f'''  <url>
    <loc>{SITE_URL}/product.html?id={pid}</loc>
    <lastmod>{added}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.7</priority>
  </url>''')

sitemap_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{chr(10).join(urls)}
</urlset>
'''

# Upload sitemap.xml to GitHub
sitemap_path = 'site/sitemap.xml'
encoded = base64.b64encode(sitemap_xml.encode('utf-8')).decode('utf-8')

# Check if file exists to get SHA
try:
    check_req = urllib.request.Request(f'{API_BASE}/{sitemap_path}', headers=HEADERS)
    with urllib.request.urlopen(check_req, timeout=15) as resp:
        existing = json.loads(resp.read().decode('utf-8'))
        sha = existing['sha']
except:
    sha = None

put_body = json.dumps({
    'message': f'Update sitemap.xml ({len(products)} products)',
    'content': encoded,
    **({"sha": sha} if sha else {}),
}).encode('utf-8')

put_req = urllib.request.Request(
    f'{API_BASE}/{sitemap_path}',
    data=put_body,
    headers={**HEADERS, 'Content-Type': 'application/json'},
    method='PUT'
)
with urllib.request.urlopen(put_req, timeout=15) as resp:
    if resp.status == 200 or resp.status == 201:
        print(f'✅ Sitemap updated: {len(products)} product URLs + homepage')
    else:
        print(f'❌ Failed: {resp.status}')
