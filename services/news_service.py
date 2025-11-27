import feedparser
from datetime import datetime
from models.db import get_db, put_db

# ===============================
# RSS KAYNAKLARI (4 adet)
# ===============================
RSS_FEEDS = [
    "https://www.aa.com.tr/tr/rss/sondakika",
    "https://www.aa.com.tr/tr/rss/ekonomi",
    "https://www.trthaber.com/rss/sondakika.rss",
    "https://www.trthaber.com/rss/ekonomi.rss",
    "https://www.bbc.com/turkce/index.xml",
    "https://www.bloomberght.com/rss"
]


# ===============================
# HABERİ TEK FORMATTA NORMALİZE ET
# ===============================
def normalize(entry, source_title):
    title = entry.get("title", "").strip()
    description = entry.get("summary", "").strip()
    link = entry.get("link", "").strip()

    # Yayın tarihini al
    published = entry.get("published", None)
    try:
        published_date = datetime(*entry.published_parsed[:6])
    except:
        published_date = datetime.now()

    # Görsel bul (opsiyonel)
    image = ""
    if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
        image = entry.media_thumbnail[0].get("url", "")
    elif hasattr(entry, "media_content") and entry.media_content:
        image = entry.media_content[0].get("url", "")

    return {
        "baslik": title,
        "aciklama": description,
        "url": link,
        "gorsel": image,
        "kaynak": source_title,
        "tarih": published_date
    }


# ===============================
# RSS VERİLERİNİ ÇEK + DB'YE KAYDET
# ===============================
def fetch_and_save_news():
    conn = get_db()
    cur = conn.cursor()

    new_count = 0

    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            source_title = feed.feed.get("title", "Bilinmeyen Kaynak")

            for entry in feed.entries:
                item = normalize(entry, source_title)

                # Duplicate ENGELLEME
                cur.execute("SELECT id FROM haberler WHERE url=%s", (item["url"],))
                exists = cur.fetchone()

                if exists:
                    continue  # Aynı haber varsa geç

                # Yeni haber → DB'ye ekle
                cur.execute("""
                    INSERT INTO haberler (baslik, aciklama, gorsel, kaynak, url, tarih)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    item["baslik"],
                    item["aciklama"],
                    item["gorsel"],
                    item["kaynak"],
                    item["url"],
                    item["tarih"]
                ))

                new_count += 1

        except Exception as e:
            print("RSS Hatası:", feed_url, e)

    # 3 GÜNDEN ESKİ HABERLERİ SİL
    cur.execute("""
        DELETE FROM haberler 
        WHERE created_at < NOW() - INTERVAL '3 days';
    """)

    conn.commit()
    put_db(conn)

    return new_count
