import feedparser
from datetime import datetime
from models.db import get_db, put_db
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urlparse, urljoin

# ===============================
# ÇALIŞAN + YENİ PREMIUM RSS KAYNAKLARI
# ===============================
RSS_FEEDS = {
    # GENEL HABER - Yüksek Kalite (ÇALIŞAN)
    "BBC Türkçe": "https://www.bbc.com/turkce/index.xml",
    "Habertürk": "https://www.haberturk.com/rss",
    "CNN Türk": "https://www.cnnturk.com/feed/rss/news",
    "Sözcü": "https://www.sozcu.com.tr/rss/",
    "Hürriyet": "https://www.hurriyet.com.tr/rss/anasayfa",
    "Milliyet Gündem": "https://www.milliyet.com.tr/rss/rssnew/gundemrss.xml",
    
    # YENİ EKLENDİ - YÜKSEK GÖRSELLİ
    "Cumhuriyet": "https://www.cumhuriyet.com.tr/rss/son_dakika.xml",
    "Sabah": "https://www.sabah.com.tr/rss/anasayfa.xml",
    "Posta": "https://www.posta.com.tr/rss/anasayfa.xml",
    "Yeni Şafak": "https://www.yenisafak.com/Rss",
    "Star": "https://www.star.com.tr/rss.xml",
    
    # EKONOMİ - Görsel Ağırlıklı (ÇALIŞAN)
    "Bloomberg HT": "https://www.bloomberght.com/rss",
    "Para Analiz": "https://www.paraanaliz.com/feed/",
    
    # YENİ EKONOMİ
    "Ekonomim": "https://www.ekonomim.com/rss/news.xml",
    "Dünya Gazetesi": "https://www.dunya.com/service/rss.php",
    
    # SPOR - YENİ KAYNAKLAR
    "Sporx": "https://www.sporx.com/rss",
    "A Spor": "https://www.aspor.com.tr/rss",
    "Haber Spor": "https://www.haberspor.com/rss",
    
    # TEKNOLOJİ - Premium Görseller (ÇALIŞAN)
    "WebTekno": "https://www.webtekno.com/rss.xml",
    "ShiftDelete": "https://shiftdelete.net/feed",
    
    # YENİ TEKNOLOJİ
    "TeknoLog": "https://teknolog.com/feed/",
    "Teknolojioku": "https://www.teknolojioku.com/feed/",
    
    # DÜNYA HABERLERİ
    "Euronews Türkçe": "https://tr.euronews.com/rss",
    "DW Türkçe": "https://www.dw.com/rss/rss-tur-all/rss.xml",
    
    # YAŞAM & SAĞLIK
    "Mynet Yaşam": "https://www.mynet.com/rss/yasam",
    "WebMD (TR)": "https://www.webmd.com/rss/rss.aspx?RSSSource=RSS_PUBLIC",
}

# ===============================
# AKILLI GÖRSEL ÇEKME SİSTEMİ
# ===============================
def extract_high_quality_image(entry, feed_url, source_name):
    """
    Çoklu yöntemle yüksek kaliteli görsel bul
    """
    image_url = ""
    
    # 1. RSS Media Tags (En Hızlı ve Güvenilir)
    if hasattr(entry, "media_content") and entry.media_content:
        # En büyük çözünürlüklü görseli seç
        images = [m for m in entry.media_content if "image" in m.get("type", "")]
        if images:
            # Width'e göre sırala
            images.sort(key=lambda x: int(x.get("width", 0)), reverse=True)
            image_url = images[0].get("url", "")
    
    if not image_url and hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
        thumbnails = entry.media_thumbnail
        if thumbnails:
            # En büyük thumbnail'i al
            thumbnails.sort(key=lambda x: int(x.get("width", 0)), reverse=True)
            image_url = thumbnails[0].get("url", "")
    
    # 2. Enclosures (Podcast/Video görselleri)
    if not image_url and hasattr(entry, "enclosures") and entry.enclosures:
        for enc in entry.enclosures:
            if "image" in enc.get("type", "").lower():
                image_url = enc.get("href", "")
                break
    
    # 3. İçerik içinden görsel ara (HTML parsing)
    if not image_url:
        content = entry.get("summary", "") or entry.get("description", "") or entry.get("content", [{}])[0].get("value", "")
        
        # img src bul
        img_matches = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', content, re.IGNORECASE)
        if img_matches:
            # İlk büyük görseli al (data:image hariç)
            for img in img_matches:
                if not img.startswith("data:"):
                    image_url = img
                    break
    
    # 4. URL Düzeltmeleri
    if image_url:
        # Protocol ekle
        if image_url.startswith("//"):
            image_url = "https:" + image_url
        # Relative URL'leri absolute yap
        elif image_url.startswith("/"):
            parsed = urlparse(feed_url)
            image_url = f"{parsed.scheme}://{parsed.netloc}{image_url}"
        # Query parametrelerini temizle (bazı siteler boyut parametresi ekler)
        if "?" in image_url and any(x in image_url for x in ["w=", "h=", "size="]):
            base_url = image_url.split("?")[0]
            # Eğer düşük çözünürlük parametresi varsa kaldır
            if any(x in image_url for x in ["w=100", "w=200", "w=300", "thumb", "small"]):
                image_url = base_url
    
    # 5. Kalite Kontrolü
    if image_url:
        # Çok küçük görselleri reddet
        if any(x in image_url.lower() for x in ["1x1", "pixel", "tracking", "beacon"]):
            return ""
        
        # Data URI'leri reddet
        if image_url.startswith("data:"):
            return ""
        
        # Sosyal medya ikonlarını reddet
        if any(x in image_url.lower() for x in ["facebook", "twitter", "instagram", "logo", "icon"]):
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
        "has_image": bool(image)  # Görsel var mı kontrolü
    }

# ===============================
# RSS VERİLERİNİ ÇEK + KAYDET
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
            
            # Her kaynaktan max 8 haber al (performans için)
            for entry in feed.entries[:8]:
                try:
                    item = normalize(entry, source_name, feed_url)
                    
                    # Temel validasyon
                    if not item["baslik"] or not item["url"]:
                        continue
                    
                    # Başlık çok kısa ise geç
                    if len(item["baslik"]) < 10:
                        continue
                    
                    # URL duplicate kontrolü
                    cur.execute("SELECT id FROM haberler WHERE url = %s", (item["url"],))
                    if cur.fetchone():
                        continue
                    
                    # Veritabanına ekle
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
                    
                    source_new += 1
                    new_count += 1
                    
                    if item["has_image"]:
                        source_images += 1
                        total_with_images += 1
                
                except Exception as e:
                    print(f"⚠️ Haber işleme hatası ({source_name}): {e}")
                    continue
            
            if source_new > 0:
                print(f"   ✅ {source_new} yeni haber ({source_images} görselli)")
        
        except Exception as e:
            print(f"❌ {source_name}: {str(e)[:50]}")
            failed_feeds.append(source_name)
    
    # Eski haberleri temizle (3 günden eski)
    cur.execute("""
        DELETE FROM haberler 
        WHERE tarih < NOW() - INTERVAL '3 days';
    """)
    deleted_count = cur.rowcount
    
    # Değişiklikleri kaydet
    conn.commit()
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
