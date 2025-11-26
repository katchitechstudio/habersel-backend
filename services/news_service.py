import feedparser
import random
import time
from datetime import datetime, timedelta

from models.db import get_db, put_db

# ================================
# KATEGORİLER
# ================================
CATEGORIES = {
    "general": [
        "https://www.hurriyet.com.tr/rss/anasayfa",
        "https://www.milliyet.com.tr/rss/rssnew/anasayfa",
        "https://www.ntv.com.tr/son-dakika.rss",
        "https://www.sabah.com.tr/rss/anasayfa.xml",
        "https://www.cnnturk.com/feed/rss/all/news"
    ],

    "economy": [
        "https://www.hurriyet.com.tr/rss/ekonomi",
        "https://www.ntv.com.tr/ekonomi.rss",
        "https://www.milliyet.com.tr/rss/rssnew/ekonomi"
    ],

    "sports": [
        "https://www.ntvspor.net/rss",
        "https://www.fanatik.com.tr/rss/anasayfa",
        "https://www.trtspor.com.tr/rss/anasayfa.rss"
    ],

    "technology": [
        "https://www.donanimhaber.com/rss/tum",
        "https://www.webtekno.com/rss.xml"
    ],

    "magazine": [
        "https://www.sozcu.com.tr/rss/magazin.xml",
        "https://www.hurriyet.com.tr/rss/kelebek"
    ],

    "world": [
        "https://www.ntv.com.tr/dunya.rss",
        "https://www.trthaber.com/rss/dunya.rss"
    ]
}

ALL_CATEGORIES = list(CATEGORIES.keys())


# ================================
# CACHE SİSTEMİ
# ================================
news_cache = {}          # {"general": [...], "sports": [...]} 
cache_timestamp = {}     # {"general": datetime, ...}

CACHE_DURATION_MINUTES = 10


def get_cached_news(category):
    """Kategori cache süresini kontrol eder, yeniyse direkt cache döner."""
    now = datetime.now()

    if (category in news_cache and 
        category in cache_timestamp and 
        now - cache_timestamp[category] < timedelta(minutes=CACHE_DURATION_MINUTES)):
        return news_cache.get(category, [])

    # Cache süresi dolmuş → yeni RSS çek
    fetch_category_news(category)
    return news_cache.get(category, [])


# ================================
# HABER NORMALİZE FONKSİYONU
# ================================
def normalize_entry(entry):
    """RSS item'ı tek formatta normalize eder."""
    title = entry.get("title", "").strip()
    desc = entry.get("summary", "").strip()
    link = entry.get("link", "")
    published = entry.get("published", datetime.now().isoformat())
    source = entry.get("source", {}).get("title", "")

    # Görsel bulmaya çalışma
    image = ""
    if "media_thumbnail" in entry and entry.media_thumbnail:
        image = entry.media_thumbnail[0]["url"]
    elif "media_content" in entry and entry.media_content:
        image = entry.media_content[0]["url"]

    return {
        "title": title,
        "description": desc,
        "url": link,
        "image": image,
        "source": source,
        "publishedAt": published
    }


# ================================
# BİR KATEGORİYİ RSS İLE ÇEK
# ================================
def fetch_category_news(category):
    rss_list = CATEGORIES.get(category, [])
    merged_news = []

    for rss_url in rss_list:
        try:
            d = feedparser.parse(rss_url)

            for entry in d.entries:
                merged_news.append(normalize_entry(entry))

        except Exception as e:
            print(f"RSS Hatası ({rss_url}): {e}")

    # En yeni haber üstte
    merged_news = sorted(
        merged_news,
        key=lambda x: x.get("publishedAt", ""),
        reverse=True
    )

    # CACHE'E YAZ
    news_cache[category] = merged_news
    cache_timestamp[category] = datetime.now()

    # DB'ye de kaydet (3 gün saklama)
    save_news_to_db(category, merged_news)

    return len(merged_news)


# ================================
# TÜM KATEGORİLERİ ÇEK
# ================================
def fetch_all_news():
    total = 0

    # Jitter → 0–15 saniye gecikme
    delay = random.randint(0, 15)
    print(f"Jitter: {delay} saniye")
    time.sleep(delay)

    for category in ALL_CATEGORIES:
        total += fetch_category_news(category)

    return total


# ================================
# DB'YE HABER KAYDET (3 gün sakla)
# ================================
def save_news_to_db(category, news_list):
    try:
        conn = get_db()
        cur = conn.cursor()

        # 3 günden eski haberleri sil
        cur.execute("""
            DELETE FROM haberler 
            WHERE tarih < NOW() - INTERVAL '3 days';
        """)

        # Yeni haberleri ekle
        for item in news_list:
            cur.execute("""
                INSERT INTO haberler (baslik, aciklama, gorsel, kaynak, url, kategori, tarih)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (url) DO NOTHING;
            """, (
                item["title"],
                item["description"],
                item["image"],
                item["source"],
                item["url"],
                category,
                item["publishedAt"]
            ))

        conn.commit()
        cur.close()
        put_db(conn)

    except Exception as e:
        print("DB Kayıt Hatası:", e)
