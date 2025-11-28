import feedparser
from datetime import datetime
from models.db import get_db, put_db
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urlparse, urljoin

# ===============================
# ÇALIŞAN RSS KAYNAKLARI + GZT
# ===============================
RSS_FEEDS = {
    # GZT - YENİ EKLENEN (Yüksek Kalite)
    "GZT Genel": "https://www.gzt.com/rss",
    "GZT Gündem": "https://www.gzt.com/rss/gundem",
    "GZT Dünya": "https://www.gzt.com/rss/dunya",
    "GZT Teknoloji": "https://www.gzt.com/rss/teknoloji",
    "GZT Spor": "https://www.gzt.com/rss/spor",
    
    # GENEL HABER - Yüksek Kalite (ÇALIŞAN)
    "BBC Türkçe": "https://www.bbc.com/turkce/index.xml",
    "Habertürk": "https://www.haberturk.com/rss",
    "CNN Türk": "https://www.cnnturk.com/feed/rss/news",
    "Sözcü": "https://www.sozcu.com.tr/rss/",
    "Hürriyet": "https://www.hurriyet.com.tr/rss/anasayfa",
    "Cumhuriyet": "https://www.cumhuriyet.com.tr/rss/son_dakika.xml",
    "Sabah": "https://www.sabah.com.tr/rss/anasayfa.xml",
    "Posta": "https://www.posta.com.tr/rss/anasayfa.xml",
    "Yeni Şafak": "https://www.yenisafak.com/Rss",
    
    # EKONOMİ
    "Bloomberg HT": "https://www.bloomberght.com/rss",
    "Para Analiz": "https://www.paraanaliz.com/feed/",
    
    # TEKNOLOJİ
    "WebTekno": "https://www.webtekno.com/rss.xml",
    "ShiftDelete": "https://shiftdelete.net/feed",
    "TeknoLog": "https://teknolog.com/feed/",
    
    # DÜNYA
    "Euronews Türkçe": "https://tr.euronews.com/rss",
}

# ===============================
# AKILLI GÖRSEL ÇEKME SİSTEMİ
# ===============================
def extract_high_quality_image(entry, feed_url, source_name):
    """
    Çoklu yöntemle yüksek kaliteli görsel bul
    """
    image_url = ""
    
    # 1. RSS Media Tags
    if hasattr(entry, "media_content") and entry.media_content:
        images = [m for m in entry.media_content if "image" in m.get("type", "")]
        if images:
            images.sort(key=lambda x: int(x.get("width", 0)), reverse=True)
            image_url = images[0].get("url", "")
    
    if not image_url and hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
        thumbnails = entry.media_thumbnail
        if thumbnails:
            thumbnails.sort(key=lambda x: int(x.get("width", 0)), reverse=True)
            image_url = thumbnails[0].get("url", "")
    
    # 2. Enclosures
    if not image_url and hasattr(entry, "enclosures") and entry.enclosures:
        for enc in entry.enclosures:
            if "image" in enc.get("type", "").lower():
                image_url = enc.get("href", "")
                break
    
    # 3. İçerik içinden görsel ara
    if not image_url:
        content = entry.get("summary", "") or entry.get("description", "")
        img_matches = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', content, re.IGNORECASE)
        if img_matches:
            for img in img_matches:
                if not img.startswith("data:"):
                    image_url = img
                    break
    
    # 4. URL Düzeltmeleri
    if image_url:
        if image_url.startswith("//"):
            image_url = "https:" + image_url
        elif image_url.startswith("/"):
            parsed = urlparse(feed_url)
            image_url = f"{parsed.scheme}://{parsed.netloc}{image_url}"
    
    # 5. Kalite Kontrolü
    if image_url:
        if any(x in image_url.lower() for x in ["1x1", "pixel", "tracking", "beacon", "logo", "icon"]):
            return ""
        if image_url.startswith("data:"):
            return ""
    
    return image_url

# ===============================
# HABERİ NORMALIZE ET
# ===============================
def normalize(entry, source_name, feed_url):
    """
    Haber verisini temizle ve düzenle
    """
    title = entry.get("title", "").strip()
    
    # Açıklama
    description = entry.get("summary", "") or entry.get("description", "")
    if isinstance(description, list):
        description = description[0].get("value", "") if description else ""
    
    # HTML etiketlerini temizle
    description = re.sub(r'<[^>]+>', '', description)
    description = re.sub(r'\s+', ' ', description).strip()
    
    # Uzunluğu sınırla
    if len(description) > 250:
        description = description[:247] + "..."
    
    # Link
    link = entry.get("link", "").strip()
    
    # Tarih
    try:
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            published_date = datetime(*entry.published_parsed[:6])
        else:
            published_date = datetime.now()
    except:
        published_date = datetime.now()
    
    # Yüksek kaliteli görsel
    image = extract_high_quality_image(entry, feed_url, source_name)
    
    return {
        "baslik": title,
        "aciklama": description,
        "url": link,
        "gorsel": image,
        "kaynak": source_name,
        "tarih": published_date,
        "has_image": bool(image)
    }

# ===============================
# RSS VERİLERİNİ ÇEK + KAYDET (DÜZELTİLMİŞ)
# ===============================
def fetch_and_save_news():
    """
    Tüm RSS kaynaklarından haberleri çek ve veritabanına kaydet
    """
    conn = get_db()
    cur = conn.cursor()
    
    new_count = 0
    total_with_images = 0
    failed_feeds = []
    
    print(f"\n{'='*60}")
    print(f"📡 {len(RSS_FEEDS)} RSS kaynağından haber çekiliyor...")
    print(f"{'='*60}\n")
    
    for source_name, feed_url in RSS_FEEDS.items():
        try:
            # RSS'i parse et
            feed = feedparser.parse(feed_url)
            
            # Hatalı RSS kontrolü
            if feed.bozo and not feed.entries:
                print(f"❌ {source_name}: RSS hatası")
                failed_feeds.append(source_name)
                continue
            
            entries_count = len(feed.entries)
            print(f"🔍 {source_name}: {entries_count} haber bulundu")
            
            source_new = 0
            source_images = 0
            
            # Her kaynaktan max 8 haber al
            for entry in feed.entries[:8]:
                try:
                    item = normalize(entry, source_name, feed_url)
                    
                    # Temel validasyon
                    if not item["baslik"] or not item["url"]:
                        continue
                    
                    # Başlık çok kısa ise geç
                    if len(item["baslik"]) < 10:
                        continue
                    
                    # 🔥 DÜZELTME: URL duplicate kontrolü
                    cur.execute("SELECT id FROM haberler WHERE url = %s", (item["url"],))
                    if cur.fetchone():
                        continue
                    
                    # 🔥 DÜZELTME: Veritabanına ekle - Her insert kendi transaction'ında
                    try:
                        cur.execute("""
                            INSERT INTO haberler (baslik, aciklama, gorsel, kaynak, url, tarih)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            ON CONFLICT (url) DO NOTHING
                        """, (
                            item["baslik"],
                            item["aciklama"],
                            item["gorsel"],
                            item["kaynak"],
                            item["url"],
                            item["tarih"]
                        ))
                        
                        # 🔥 DÜZELTME: Her insert'ten sonra commit
                        conn.commit()
                        
                        source_new += 1
                        new_count += 1
                        
                        if item["has_image"]:
                            source_images += 1
                            total_with_images += 1
                    
                    except Exception as insert_error:
                        # 🔥 DÜZELTME: Hata olursa rollback yap
                        conn.rollback()
                        print(f"⚠️ Insert hatası ({source_name}): {str(insert_error)[:60]}")
                        continue
                
                except Exception as e:
                    conn.rollback()
                    print(f"⚠️ Haber işleme hatası ({source_name}): {str(e)[:60]}")
                    continue
            
            if source_new > 0:
                print(f"   ✅ {source_new} yeni haber ({source_images} görselli)")
        
        except Exception as e:
            print(f"❌ {source_name}: {str(e)[:50]}")
            failed_feeds.append(source_name)
    
    # 🔥 DÜZELTME: Eski haberleri temizle - Ayrı transaction
    try:
        cur.execute("""
            DELETE FROM haberler 
            WHERE tarih < NOW() - INTERVAL '3 days';
        """)
        deleted_count = cur.rowcount
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"⚠️ Temizlik hatası: {e}")
        deleted_count = 0
    
    # Connection'ı kapat
    put_db(conn)
    
    # Özet rapor
    print(f"\n{'='*60}")
    print(f"📊 ÖZET:")
    print(f"   ✅ {new_count} yeni haber eklendi")
    print(f"   🖼️  {total_with_images} haberde görsel var ({int(total_with_images/new_count*100) if new_count > 0 else 0}%)")
    print(f"   🧹 {deleted_count} eski haber silindi")
    if failed_feeds:
        print(f"   ⚠️  {len(failed_feeds)} kaynak başarısız: {', '.join(failed_feeds[:3])}")
    print(f"{'='*60}\n")
    
    return new_count
