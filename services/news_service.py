import feedparser
from datetime import datetime
from models.db import get_db, put_db
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urlparse, urljoin

# ===============================
# PREMİUM RSS KAYNAKLARI (20+ adet)
# Sadece yüksek kaliteli görsel veren kaynaklar
# ===============================
RSS_FEEDS = {
    # GENEL HABER - Yüksek Kalite
    "AA (Genel)": "https://www.aa.com.tr/tr/rss/default",
    "TRT Haber": "https://www.trthaber.com/rss/sondakika.rss",
    "BBC Türkçe": "https://www.bbc.com/turkce/index.xml",
    "Habertürk": "https://www.haberturk.com/rss",
    "CNN Türk": "https://www.cnnturk.com/feed/rss/news",
    "NTV": "https://www.ntv.com.tr/rss",
    "Sözcü": "https://www.sozcu.com.tr/rss/",
    "Hürriyet": "https://www.hurriyet.com.tr/rss/anasayfa",
    "Milliyet": "https://www.milliyet.com.tr/rss/rssnew/gundemrss.xml",
    
    # EKONOMİ - Görsel Ağırlıklı
    "AA Ekonomi": "https://www.aa.com.tr/tr/rss/ekonomi",
    "TRT Ekonomi": "https://www.trthaber.com/rss/ekonomi.rss",
    "Bloomberg HT": "https://www.bloomberght.com/rss",
    "Dünya": "https://www.dunya.com/service/rss.php",
    "Para Analiz": "https://www.paraanaliz.com/feed/",
    
    # SPOR - Yüksek Görsel Kalitesi
    "AA Spor": "https://www.aa.com.tr/tr/rss/spor",
    "TRT Spor": "https://www.trthaber.com/rss/spor.rss",
    "Fanatik": "https://www.fanatik.com.tr/rss",
    "Fotomaç": "https://www.fotomac.com.tr/rss",
    "NTV Spor": "https://www.ntvspor.net/rss",
    
    # TEKNOLOJİ - Premium Görseller
    "WebTekno": "https://www.webtekno.com/rss.xml",
    "ShiftDelete": "https://shiftdelete.net/feed",
    "Donanım Haber": "https://www.donanimhaber.com/rss",
    "Chip Online": "https://www.chip.com.tr/rss/haber.xml",
    
    # DÜNYA - Global Haberler
    "AA Dünya": "https://www.aa.com.tr/tr/rss/dunya",
    "TRT Dünya": "https://www.trthaber.com/rss/dunya.rss",
    
    # YAŞAM & SAĞLIK
    "AA Yaşam": "https://www.aa.com.tr/tr/rss/yasam",
    "TRT Yaşam": "https://www.trthaber.com/rss/yasam.rss",
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
    
    # 4. KAYNAK ÖZEL ÇÖZÜMLER
    if not image_url:
        # AA için özel parsing
        if "aa.com.tr" in feed_url:
            if hasattr(entry, "id"):
                # AA'nın görsel URL pattern'i
                news_id = entry.id.split("/")[-1] if "/" in entry.id else ""
                if news_id:
                    image_url = f"https://cdnuploads.aa.com.tr/uploads/Contents/2024/{news_id[:2]}/{news_id}/thumbs_b_c_{news_id}.jpg"
        
        # TRT için özel parsing
        elif "trthaber.com" in feed_url:
            link = entry.get("link", "")
            if link:
                # TRT'nin görsel pattern'i
                parts = link.split("-")
                if parts:
                    news_id = parts[-1].replace(".html", "")
                    if news_id.isdigit():
                        image_url = f"https://trthaberstatic.cdn.wp.trt.com.tr/resimler/{news_id[:3]}000/{news_id}-16x9.jpg"
    
    # 5. URL Düzeltmeleri
    if image_url:
        # Protocol ekle
        if image_url.startswith("//"):
            image_url = "https:" + image_url
        # Relative URL'leri absolute yap
        elif image_url.startswith("/"):
            parsed = urlparse(feed_url)
            image_url = f"{parsed.scheme}://{parsed.netloc}{image_url}"
        # Query parametrelerini temizle (bazı siteler boyut parametresi ekler)
        # Örn: image.jpg?w=100 → image.jpg
        if "?" in image_url and any(x in image_url for x in ["w=", "h=", "size="]):
            base_url = image_url.split("?")[0]
            # Eğer düşük çözünürlük parametresi varsa kaldır
            if any(x in image_url for x in ["w=100", "w=200", "w=300", "thumb", "small"]):
                image_url = base_url
    
    # 6. Son Çare: Haber Sayfasından Çek (Yavaş ama Etkili)
    # NOT: Sadece çok önemli kaynaklarda kullan
    if not image_url and source_name in ["BBC Türkçe", "Bloomberg HT", "Hürriyet"]:
        link = entry.get("link", "")
        if link:
            try:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
                response = requests.get(link, timeout=5, headers=headers)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, "html.parser")
                    
                    # Open Graph Image (En güvenilir)
                    og_image = soup.find("meta", property="og:image")
                    if og_image and og_image.get("content"):
                        image_url = og_image["content"]
                    
                    # Twitter Card
                    if not image_url:
                        twitter_img = soup.find("meta", attrs={"name": "twitter:image"})
                        if twitter_img and twitter_img.get("content"):
                            image_url = twitter_img["content"]
                    
                    # Article içindeki ilk büyük görsel
                    if not image_url:
                        article = soup.find("article") or soup.find("div", class_=re.compile("content|article|post"))
                        if article:
                            img = article.find("img", attrs={"width": True})
                            if img and int(img.get("width", 0)) > 400:
                                image_url = img.get("src") or img.get("data-src")
                                
            except Exception as e:
                print(f"⚠️ Sayfa görsel çekme hatası ({source_name}): {e}")
    
    # 7. Kalite Kontrolü
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
