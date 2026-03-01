# 🛒 Shop Na Ali — Автоматизований агрегатор "халяви"

Екосистема для автоматичного збору дешевих товарів (до $1) з AliExpress через Telegram-канали, конвертації посилань у партнерські та публікації у власний канал [@Ekcoin](https://t.me/Ekcoin).

## 📁 Структура

```
Shop_Na_Ali/
├── site/                     # 🌐 Вебсайт
│   ├── index.html            # Каталог товарів
│   ├── product.html          # Мікролендінг товару
│   ├── css/style.css         # Дизайн (dark mode + neon)
│   ├── js/app.js             # Логіка каталогу
│   ├── js/product.js         # Логіка товару
│   ├── data/products.json    # Дані (оновлюється авто)
│   ├── images/               # Фото товарів
│   └── manifest/robots/sitemap
├── parser/                   # 🤖 Telegram парсер
│   ├── main.py               # Telethon userbot
│   ├── config.py             # Конфігурація
│   ├── requirements.txt      # Залежності
│   └── .env                  # API ключі
├── n8n/
│   └── workflow.json         # n8n workflow
└── README.md
```

## 🚀 Швидкий старт

### 1. Парсер
```bash
cd parser
pip install -r requirements.txt
python main.py
```

### 2. n8n
1. Відкрити [n8n.21000.online](https://n8n.21000.online/)
2. Import workflow → `n8n/workflow.json`
3. Додати Telegram Bot credentials
4. Активувати

### 3. Сайт
Відкрити `site/index.html` або задеплоїти на Cloudflare Pages.

## 🔄 Pipeline

```
Канали-донори → Парсер → n8n webhook → Affiliate Link → TG @Ekcoin + Сайт
```

| Канал | Тип |
|-------|-----|
| `@theCheapestAliExpress` | Дешеві знахідки |
| `@AliReviewers` | Відгуки |
| `@halyavaZaliExpress` | Халява |
